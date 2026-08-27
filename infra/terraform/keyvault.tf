# Secrets, and the values that go in them.
#
# Nothing in this file is a literal. Every secret is either supplied as a
# sensitive variable or generated here, so no credential exists in the repo.
# They do exist in Terraform state in plaintext, which is why state belongs in a
# storage account with restricted access and never in git.

resource "azurerm_key_vault" "main" {
  # Globally unique across all of Azure and capped at 24 characters, hence both
  # the compact name and the random suffix.
  name                = "kv-${local.name_compact}${random_string.suffix.result}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  # RBAC rather than access policies. Access policies are per-vault ACLs living
  # outside the normal permission model, so nothing that audits Azure RBAC can
  # see them. RBAC is the current default and the one an auditor can query.
  rbac_authorization_enabled = true

  # Retains a deleted secret long enough to recover from a bad apply. Cannot be
  # disabled on new vaults, and is why purge_soft_delete_on_destroy is set in
  # providers.tf -- without it a destroyed vault blocks its own name for the
  # whole retention window.
  soft_delete_retention_days = 7
  purge_protection_enabled   = local.environment == "prod"

  tags = local.common_tags
}

# Generated rather than supplied. A secret nobody has ever seen cannot be pasted
# into a chat window, committed to a repo, or reused somewhere else -- which is
# exactly how this project's Render Postgres credential reached git history.
resource "random_password" "flask_secret_key" {
  length  = 64
  special = false
}

resource "random_password" "web_secret_key" {
  length  = 64
  special = false
}

# Deliberately a different value from the one above, not a copy. SECRET_KEY
# signs web's session cookie; API_TOKEN_SECRET signs the bearer tokens web
# presents to the api. Two trust boundaries -- a leak of either must not let the
# holder forge the other. services/api/app/config.py documents the same rule.
resource "random_password" "api_token_secret" {
  length  = 64
  special = false
}

locals {
  secrets = {
    "database-url"      = local.database_url
    "secret-key"        = random_password.flask_secret_key.result
    "web-secret-key"    = random_password.web_secret_key.result
    "api-token-secret"  = random_password.api_token_secret.result
    "postgres-password" = var.postgres_admin_password
  }
}

resource "azurerm_key_vault_secret" "app" {
  for_each = local.secrets

  name         = each.key
  value        = each.value
  key_vault_id = azurerm_key_vault.main.id

  # The role assignment is what makes the write possible, and nothing here
  # references it -- so Terraform has no way to infer the dependency. Without
  # depends_on the first apply fails with a 403 and the second one succeeds,
  # which is the kind of intermittent that costs an afternoon.
  depends_on = [azurerm_role_assignment.kv_secrets_officer]
}
