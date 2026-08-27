# Who the running containers are, and what that lets them do.
#
# A user-assigned identity rather than system-assigned. System-assigned is
# created with the app and dies with it, so every redeploy that recreates an app
# produces a new principal id -- and every role granted to the old one silently
# stops applying. The symptom is a container that started fine last week and now
# cannot read its secrets. A user-assigned identity has a lifecycle of its own,
# so the grants outlive the apps.

resource "azurerm_user_assigned_identity" "app" {
  name                = "id-${local.name_prefix}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.common_tags
}

# Data-plane access to secret values. This is the grant people miss.
#
# Azure RBAC splits control plane from data plane: Contributor on a vault lets
# you change the vault's settings and read nothing inside it. A container app
# with Contributor and without this role starts, resolves nothing, and reports a
# permissions error naming the vault -- which reads as though the vault
# reference is wrong. It is not; the role is.
resource "azurerm_role_assignment" "kv_secrets_user" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

# Whoever runs apply needs to write the secrets in the first place. Different
# principal, different role, deliberately asymmetric: this one can set values,
# the app's can only read them.
resource "azurerm_role_assignment" "kv_secrets_officer" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

# Lets the apps write their own telemetry. Without it the OpenTelemetry exporter
# fails silently -- traces simply never arrive, and an absent trace looks
# exactly like a request that was never made.
resource "azurerm_role_assignment" "monitoring_publisher" {
  scope                = azurerm_application_insights.main.id
  role_definition_name = "Monitoring Metrics Publisher"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}
