resource "azurerm_postgresql_flexible_server" "main" {
  name                = "psql-${local.name_prefix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  version                = var.postgres_version
  administrator_login    = "kaiadmin"
  administrator_password = var.postgres_admin_password

  sku_name   = var.postgres_sku_name
  storage_mb = var.postgres_storage_mb

  # Storage on Flexible Server grows and never shrinks.
  #
  # In prod, auto-grow on: a full database is a worse problem than an unexpected
  # invoice. In dev, off: the free tier covers exactly 32 GB, and one runaway
  # table would grow past it silently and permanently -- there is no way back to
  # the free size short of rebuilding the server. Off means the failure is a
  # write error, which is loud, recoverable, and free.
  auto_grow_enabled = local.environment == "prod"

  backup_retention_days        = local.environment == "prod" ? 14 : 7
  geo_redundant_backup_enabled = false

  # Public access with a firewall, not a private endpoint. A private endpoint is
  # the stronger answer and needs a VNet, a private DNS zone and VNet
  # integration on the Container Apps environment -- which forces the more
  # expensive workload profile. Named here as a deliberate trade rather than an
  # oversight, so a security scan finding it gets a documented answer.
  public_network_access_enabled = true

  tags = local.common_tags

  lifecycle {
    # Rotating the admin password out of band is a legitimate operational act
    # (this project has one outstanding). Without this, the next apply resets it
    # back -- a silent outage where the server keeps running and every
    # connection starts failing authentication.
    #
    # zone is ignored because Azure assigns one when none is requested, and the
    # resulting diff would suggest a move that would recreate the server.
    ignore_changes = [administrator_password, zone]
  }
}

resource "azurerm_postgresql_flexible_server_database" "main" {
  name      = replace(lower(var.project_name), "-", "_")
  server_id = azurerm_postgresql_flexible_server.main.id
  collation = "en_US.utf8"
  charset   = "utf8"

  lifecycle {
    # Terraform's default on destroy is to take the data with it. This turns an
    # accidental `terraform destroy` into an error rather than a data loss
    # event. It is the infrastructure-level equivalent of the conftest.py guard
    # added after the test suite dropped the production database -- same lesson,
    # different layer.
    prevent_destroy = true
  }
}

# 0.0.0.0 is not a wildcard here. It is Azure's documented sentinel for "other
# Azure services", and it is what lets Container Apps connect at all. Reading it
# as "the whole internet" is the common mistake; removing it is the expensive
# one.
resource "azurerm_postgresql_flexible_server_firewall_rule" "azure_services" {
  name             = "AllowAzureServices"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

# Workstation access, for running migrations by hand.
#
# for_each rather than count: count addresses by index, so removing the first
# address in the list shifts every later rule down one address and Terraform
# destroys and recreates all of them. for_each keys each rule by its own value,
# so removal touches only that one.
resource "azurerm_postgresql_flexible_server_firewall_rule" "operator" {
  for_each = toset(var.allowed_ip_addresses)

  name             = "operator-${replace(each.value, ".", "-")}"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = each.value
  end_ip_address   = each.value
}
