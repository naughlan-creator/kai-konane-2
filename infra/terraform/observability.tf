# Created before anything that writes to it. The Container Apps environment
# takes a workspace id at creation time and will not accept one afterwards
# without being recreated -- and recreating the environment recreates every app
# inside it.

resource "azurerm_log_analytics_workspace" "main" {
  name                = "log-${local.name_prefix}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"

  # The single largest lever on the bill for a low-traffic system. Log Analytics
  # charges per GB ingested and per GB retained; 30 days is the included floor.
  retention_in_days = var.log_retention_days

  # A runaway log loop can cost more in a night than the compute costs in a
  # month. -1 means uncapped, which is only correct where losing data is worse
  # than an unexpected invoice.
  #
  # 0.15 GB/day is roughly 4.5 GB/month, just inside the 5 GB free grant. The
  # previous value of 1 permitted 30 GB -- six times the grant, so it was a cap
  # that would have stopped a catastrophe while allowing a steady bill. A
  # guardrail set above the threshold it is guarding is not a guardrail.
  daily_quota_gb = local.environment == "prod" ? -1 : 0.15

  tags = local.common_tags
}

# Application Insights in workspace mode, which is what OpenTelemetry exports
# to. The distinction matters: classic Application Insights had its own storage
# and its own query surface. Workspace-based writes into the workspace above, so
# traces and container stdout are queryable in one KQL statement and joinable on
# the request id the services already propagate.
resource "azurerm_application_insights" "main" {
  name                = "appi-${local.name_prefix}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"

  # Sampling is a cost control that changes what you can prove. At 100% every
  # trace exists and a rare failure is findable; below that, the trace you need
  # may simply not be there.
  sampling_percentage = local.environment == "prod" ? 20 : 100

  tags = local.common_tags
}

# An alert rule needs somewhere to send. Without an action group it evaluates,
# fires, and tells nobody.
resource "azurerm_monitor_action_group" "main" {
  name                = "ag-${local.name_prefix}"
  resource_group_name = azurerm_resource_group.main.name
  short_name          = substr(local.name_compact, 0, 12)
  tags                = local.common_tags
}

# Fires when the api starts returning 5xx.
#
# Scoped to the api rather than the gateway on purpose: the gateway returns 502
# when the api is down, so alerting there tells you something is wrong, while
# alerting here tells you what.
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "api_errors" {
  name                = "alert-${local.name_prefix}-api-5xx"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  evaluation_frequency = "PT5M"
  window_duration      = "PT15M"
  scopes               = [azurerm_log_analytics_workspace.main.id]
  severity             = 2

  criteria {
    # This query only works because the application already logs JSON with a
    # status field. Against plain text it would be a substring match that also
    # matches the number 500 appearing anywhere in a message.
    query                   = <<-QUERY
      ContainerAppConsoleLogs_CL
      | where ContainerName_s == "api"
      | extend parsed = parse_json(Log_s)
      | where toint(parsed.status) >= 500
      | summarize AggregatedValue = count() by bin(TimeGenerated, 5m)
    QUERY
    time_aggregation_method = "Total"
    threshold               = 5
    operator                = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.main.id]
  }

  tags = local.common_tags
}
