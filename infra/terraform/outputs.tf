# What a human or a pipeline needs after an apply.
#
# Deliberately short. An output for every attribute turns `terraform apply` into
# a wall of text nobody reads, and the two lines that matter get lost.

output "application_url" {
  value       = module.gateway.url
  description = "The public URL. The only externally reachable address in the system."
}

output "resource_group_name" {
  value       = azurerm_resource_group.main.name
  description = "Everything lives here. `az group delete --name <this>` is the whole teardown."
}

output "postgres_fqdn" {
  value       = azurerm_postgresql_flexible_server.main.fqdn
  description = "Database host, for running migrations from a workstation"
}

output "key_vault_name" {
  value       = azurerm_key_vault.main.name
  description = "Vault holding every runtime secret"
}

output "log_analytics_workspace_id" {
  value       = azurerm_log_analytics_workspace.main.workspace_id
  description = "Workspace id, for pointing a KQL query or a Grafana datasource at it"
}

output "identity_client_id" {
  value       = azurerm_user_assigned_identity.app.client_id
  description = "Client id of the user-assigned identity, for keyless auth from application code"
}

# Marked sensitive so it is redacted in console output and in CI logs.
# `terraform output -raw database_url` still prints it deliberately -- the
# marking prevents accidental disclosure, not intentional retrieval.
output "database_url" {
  value       = local.database_url
  description = "Full connection string, for running migrations"
  sensitive   = true
}
