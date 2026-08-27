provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy = true
      # Without this, a vault destroyed and recreated under the same name is
      # refused for the whole soft-delete window rather than recovered.
      recover_soft_deleted_key_vaults = true
    }

    resource_group {
      prevent_deletion_if_contains_resources = true
    }
  }

  # Required from azurerm 4.0 onward. Omitting it does not fail `validate` --
  # it fails at `plan`, with a message about the subscription rather than about
  # this block. Null here falls back to ARM_SUBSCRIPTION_ID.
  subscription_id = var.subscription_id
}
