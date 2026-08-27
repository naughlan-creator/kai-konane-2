# The three apps, through one module.
#
# Ordering here is not stylistic: api and web must exist before the gateway,
# because the gateway's configuration contains their internal FQDNs and those do
# not exist until the apps do. Terraform derives that from the references
# themselves -- nothing below declares an order.

resource "azurerm_container_app_environment" "main" {
  name                       = "cae-${local.name_prefix}"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  tags = local.common_tags
}

# --- api ---------------------------------------------------------------------
# Internal ingress: reachable from inside the environment, not from the
# internet. The api holds the database connection and mints tokens; the only
# thing that should be able to reach it is the gateway.

module "api" {
  source = "./modules/container_app"

  name                         = "api"
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.main.id
  identity_id                  = azurerm_user_assigned_identity.app.id
  image                        = "${var.image_registry}/api:${var.image_tag}"

  external_ingress = false
  target_port      = 5000

  # No floor. A replica pinned at 1 bills for every second of the month whether
  # or not anyone visits: api and gateway together came to 1,944,000 vCPU-seconds
  # against a 180,000 free grant -- about eleven times over, for a system nobody
  # is browsing at 3am.
  #
  # The cost of scaling to zero is a cold start on the first request after an
  # idle period, and for this app that start is serial: gateway, then web, then
  # api. Accepted deliberately. Set min_replicas = 1 in tfvars for a demo you
  # need to be warm, and set it back afterwards.
  min_replicas = var.min_replicas
  max_replicas = var.max_replicas

  # 0.25/0.5Gi rather than 0.5/1Gi. Container Apps only accepts specific
  # cpu/memory pairs, and this is the smallest. gunicorn with two workers fits;
  # if the level-prediction model pushes it into an OOM kill, this is the first
  # value to raise -- and the point at which the free grant stops applying.
  cpu    = 0.25
  memory = "0.5Gi"

  liveness_path  = "/healthz"
  readiness_path = "/readyz"

  env = {
    APP_ENV             = "production"
    APP_VERSION         = var.image_tag
    OTEL_SERVICE_NAME   = "kai-konane-api"
    OTEL_TRACES_ENABLED = "false"
  }

  # versionless_id, not id. A versioned reference pins the app to one version of
  # the secret, so rotating it in the vault changes nothing until someone
  # redeploys -- which defeats the reason for using a vault reference.
  secrets = {
    "database-url"     = { key_vault_secret_id = azurerm_key_vault_secret.app["database-url"].versionless_id }
    "secret-key"       = { key_vault_secret_id = azurerm_key_vault_secret.app["secret-key"].versionless_id }
    "api-token-secret" = { key_vault_secret_id = azurerm_key_vault_secret.app["api-token-secret"].versionless_id }
  }

  secret_refs = {
    DATABASE_URL     = "database-url"
    SECRET_KEY       = "secret-key"
    API_TOKEN_SECRET = "api-token-secret"
  }

  volume_mounts = {
    "/app/static/images" = { storage_name = azurerm_container_app_environment_storage.media.name }
  }

  tags = local.common_tags

  # Nothing above references the role assignment, so Terraform cannot know the
  # app will fail to resolve its secrets without it.
  depends_on = [azurerm_role_assignment.kv_secrets_user]
}

# --- web ---------------------------------------------------------------------

module "web" {
  source = "./modules/container_app"

  name                         = "web"
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.main.id
  identity_id                  = azurerm_user_assigned_identity.app.id
  image                        = "${var.image_registry}/web:${var.image_tag}"

  external_ingress = false
  target_port      = 5000

  min_replicas = var.min_replicas
  max_replicas = var.max_replicas

  # No readiness probe pointing at the api, on purpose. If web reported itself
  # unready during an api outage, the site would return a connection error
  # rather than a page saying the service is unavailable -- and web is built to
  # render with the api down: its user_loader tolerates exactly that.
  liveness_path = "/healthz"

  env = {
    APP_ENV      = "production"
    APP_VERSION  = var.image_tag
    API_BASE_URL = "https://${module.api.fqdn}"

    # Empty on purpose, and the most expensive lesson in this project's history.
    #
    # API_BASE_URL is where the web *process* reaches the api. API_PUBLIC_URL is
    # where the *browser* does. Setting this to the internal FQDN puts a
    # hostname no browser can resolve into every <img src> on the site: pages
    # return 200, tests pass, and every image is broken.
    API_PUBLIC_URL = ""

    API_TIMEOUT_S       = "10"
    OTEL_SERVICE_NAME   = "kai-konane-web"
    OTEL_TRACES_ENABLED = "false"
  }

  secrets = {
    "web-secret-key" = { key_vault_secret_id = azurerm_key_vault_secret.app["web-secret-key"].versionless_id }
  }

  secret_refs = {
    SECRET_KEY = "web-secret-key"
  }

  tags = local.common_tags

  depends_on = [azurerm_role_assignment.kv_secrets_user]
}

# --- gateway -----------------------------------------------------------------
# The only app with external ingress. Everything the public reaches, it reaches
# through here.

module "gateway" {
  source = "./modules/container_app"

  name                         = "gateway"
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.main.id
  identity_id                  = azurerm_user_assigned_identity.app.id
  image                        = "${var.image_registry}/gateway:${var.image_tag}"

  external_ingress = true
  target_port      = 80

  # The public entry point, and the first hop of the cold start described on the
  # api above. Floored at 1 this is 648,000 vCPU-seconds a month on its own,
  # still 3.6x the whole free grant -- so it scales to zero too.
  min_replicas = var.min_replicas
  max_replicas = var.max_replicas

  cpu    = 0.25
  memory = "0.5Gi"

  liveness_path = "/healthz"

  env = {
    # Internal FQDNs, substituted into the nginx template by envsubst at
    # container start. The template assigns them to `set $api_upstream` before
    # proxy_pass rather than inlining them, because nginx resolves an upstream
    # once at startup when the address is a literal -- and a replaced revision
    # gets a new address.
    API_UPSTREAM = module.api.upstream
    WEB_UPSTREAM = module.web.upstream
  }

  tags = local.common_tags
}
