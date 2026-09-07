# Azure AI Foundry, gated behind enable_ai.

resource "azurerm_cognitive_account" "ai" {
  count = var.enable_ai ? 1 : 0

  name                = "aoai-${local.name_prefix}"
  location            = var.ai_location
  resource_group_name = azurerm_resource_group.main.name

  kind     = "OpenAI"
  sku_name = "S0"

  # A stable hostname to put in configuration. Without it the endpoint is a
  # generated string that changes if the account is recreated.
  custom_subdomain_name = "aoai-${local.name_prefix}"

  public_network_access_enabled = true

  tags = local.common_tags
}

resource "azurerm_cognitive_deployment" "chat" {
  count = var.enable_ai ? 1 : 0

  name                 = "chat"
  cognitive_account_id = azurerm_cognitive_account.ai[0].id

  model {
    format  = "OpenAI"
    name    = var.ai_model_name
    version = var.ai_model_version
  }

  sku {
    name     = "Standard"
    capacity = var.ai_capacity
  }
}

# The key goes to Key Vault like every other secret -- never to an app setting.
resource "azurerm_key_vault_secret" "ai_api_key" {
  count = var.enable_ai ? 1 : 0

  name         = "ai-api-key"
  value        = azurerm_cognitive_account.ai[0].primary_access_key
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_role_assignment.kv_secrets_officer]
}

# Lets the app call the endpoint as ITSELF rather than with a key. Granted
# alongside the key so migrating to keyless auth is a client change only --
# the stronger posture, one step away.
resource "azurerm_role_assignment" "ai_user" {
  count = var.enable_ai ? 1 : 0

  scope                = azurerm_cognitive_account.ai[0].id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}