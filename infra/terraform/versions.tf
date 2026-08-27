terraform {
  # 1.9 introduced cross-object validation and `templatestring`. ">= 1.0" would
  # let someone run this on a version that cannot parse it, and the error would
  # point at the syntax rather than at the version.
  required_version = ">= 1.9"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # State: left as a partial configuration on purpose.
  #
  # The storage account holding state cannot be created by the configuration
  # that stores its state there, so it is bootstrapped once out of band and the
  # rest is supplied at init time:
  #
  #   terraform init \
  #     -backend-config="resource_group_name=rg-kai-konane-tfstate" \
  #     -backend-config="storage_account_name=stkaikonanetfstate" \
  #     -backend-config="container_name=tfstate" \
  #     -backend-config="key=kai-konane.tfstate"
  #
  # Commented out so `terraform init -backend=false` works with no Azure
  # credentials at all, which is what lets CI validate this on every PR.
  #
  # backend "azurerm" {}
}
