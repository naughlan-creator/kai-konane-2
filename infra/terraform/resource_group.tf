# Everything lives inside the group, which is what makes teardown a single operation. 
# deployment was destroyed deliberately to stop it billing, and a resource left
# outside the group would have survived and kept charging.

resource "azurerm_resource_group" "main" {
  name     = "rg-${local.name_prefix}"
  location = var.location
  tags     = local.common_tags
}

# The only data source in this configuration. Supplies the tenant id for the
# Key Vault and the object id of the principal running apply, which is what the
# Secrets Officer role assignment is granted to.
data "azurerm_client_config" "current" {}

# Key Vault and storage account names are globally unique across all of Azure,
# not just this subscription. A fixed name works until it collides with someone
# else's, so both take a suffix.
resource "random_string" "suffix" {
  length  = 5
  special = false
  upper   = false
}
