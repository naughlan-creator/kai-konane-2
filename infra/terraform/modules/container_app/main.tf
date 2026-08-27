terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

resource "azurerm_container_app" "this" {
  name                         = var.name
  resource_group_name          = var.resource_group_name
  container_app_environment_id = var.container_app_environment_id

  # Single: a new revision replaces the old one and takes all traffic. Multiple
  # would allow blue/green and canary weights, which is right for a system with
  # real users and wrong for one where an orphaned revision quietly keeps
  # billing.
  revision_mode = "Single"

  identity {
    type         = "UserAssigned"
    identity_ids = [var.identity_id]
  }

  # Key Vault references, resolved at container start by the identity above. The
  # secret value is never in the template, never in state, and rotating it in
  # the vault does not require a redeploy of this configuration.
  dynamic "secret" {
    for_each = var.secrets
    content {
      name                = secret.key
      key_vault_secret_id = secret.value.key_vault_secret_id
      identity            = var.identity_id
    }
  }

  ingress {
    external_enabled = var.external_ingress
    target_port      = var.target_port

    # Container Apps terminates TLS at the edge and talks to the container over
    # plain HTTP. "auto" lets the platform negotiate; forcing HTTPS here means
    # the platform tries TLS against a gunicorn with no certificate and every
    # request 502s while the container looks perfectly healthy.
    transport = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = var.min_replicas
    max_replicas = var.max_replicas

    container {
      name   = var.name
      image  = var.image
      cpu    = var.cpu
      memory = var.memory

      dynamic "env" {
        for_each = var.env
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = var.secret_refs
        content {
          name        = env.key
          secret_name = env.value
        }
      }

      # Liveness answers "is the process alive" and must never touch a database:
      # a slow query that reads as a dead process gets the container killed,
      # which drops the connections that were making it slow.
      dynamic "liveness_probe" {
        for_each = var.liveness_path == "" ? [] : [1]
        content {
          transport               = "HTTP"
          port                    = var.target_port
          path                    = var.liveness_path
          initial_delay           = 10
          interval_seconds        = 30
          failure_count_threshold = 3
        }
      }

      # Readiness answers "can it serve traffic yet" and is the one that does
      # check the database.
      dynamic "readiness_probe" {
        for_each = var.readiness_path == "" ? [] : [1]
        content {
          transport               = "HTTP"
          port                    = var.target_port
          path                    = var.readiness_path
          interval_seconds        = 10
          failure_count_threshold = 3
        }
      }

      dynamic "volume_mounts" {
        for_each = var.volume_mounts
        content {
          name = volume_mounts.value.storage_name
          path = volume_mounts.key
        }
      }
    }

    dynamic "volume" {
      for_each = var.volume_mounts
      content {
        name         = volume.value.storage_name
        storage_name = volume.value.storage_name
        storage_type = "AzureFile"
      }
    }
  }

  tags = var.tags
}
