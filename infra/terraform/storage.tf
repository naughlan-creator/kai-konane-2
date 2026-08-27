# Durable storage for author-uploaded content images.
#
# The api writes uploads to /app/static/images and serves them from there. A
# container filesystem is ephemeral: without this, every image uploaded survives
# until the next revision and then vanishes -- and a missing image renders as a
# broken icon, not an error. Nothing in the logs, nothing in the tests, and the
# page still returns 200.

resource "azurerm_storage_account" "media" {
  # Lowercase alphanumeric only, 3-24 characters, globally unique. name_compact
  # already strips hyphens and lowercases; the suffix handles uniqueness.
  name                = "st${local.name_compact}${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  account_tier             = "Standard"
  account_replication_type = "LRS"

  https_traffic_only_enabled = true
  min_tls_version            = "TLS1_2"

  # Nothing here is served directly to a browser; the api proxies it. Leaving
  # blob public access on would let an unlisted-but-guessable URL bypass that
  # entirely.
  allow_nested_items_to_be_public = false

  tags = local.common_tags
}

resource "azurerm_storage_share" "media" {
  name               = "media"
  storage_account_id = azurerm_storage_account.media.id
  quota              = 5
}

# Registers the share with the Container Apps environment. An app can only mount
# a share that has been declared here first -- mounting one directly is not
# possible, and the error when you try names the volume rather than the missing
# registration.
resource "azurerm_container_app_environment_storage" "media" {
  name                         = "media"
  container_app_environment_id = azurerm_container_app_environment.main.id
  account_name                 = azurerm_storage_account.media.name
  share_name                   = azurerm_storage_share.media.name
  access_key                   = azurerm_storage_account.media.primary_access_key
  access_mode                  = "ReadWrite"
}
