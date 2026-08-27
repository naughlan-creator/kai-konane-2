locals {
  environment = var.environment

  name_prefix = lower("${var.project_name}-${local.environment}")

  # Storage accounts and Key Vaults reject hyphens and cap at 24 characters,
  # and storage accounts reject uppercase entirely.
  name_compact = substr(replace(local.name_prefix, "-", ""), 0, 16)

  common_tags = {
    Environment = local.environment
    ManagedBy   = "Terraform"
    Owner       = var.team_owner
    Project     = var.project_name
    # Points whoever finds this in the portal at the code that owns it.
    # Without it, the honest answer to "can I delete this?" is nobody knows.
    Source = "https://github.com/naughlan-creator/kai-konane-2"
  }

  # Built once so api and web cannot drift apart on a value that has to match.
  database_url = join("", [
    "postgresql://",
    azurerm_postgresql_flexible_server.main.administrator_login,
    ":",
    urlencode(var.postgres_admin_password),
    "@",
    azurerm_postgresql_flexible_server.main.fqdn,
    ":5432/",
    azurerm_postgresql_flexible_server_database.main.name,
    "?sslmode=require",
  ])
}
