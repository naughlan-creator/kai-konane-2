# Terraform apply — evidence

Captured 2026-08-27, from a real `terraform apply` against Azure subscription
"Azure subscription 1", immediately before tearing the environment down.

Everything named below has since been destroyed. The identifiers are retained
as a record that the configuration in [`infra/terraform/`](../../infra/terraform)
was applied and produced a working deployment, not merely that it validated.

## `terraform output`

```
application_url            = "https://gateway.nicemushroom-1e4f44c4.southafricanorth.azurecontainerapps.io"
database_url               = <sensitive>
identity_client_id         = "812f15b9-c78b-47be-8f3f-035c69e20d17"
key_vault_name             = "kv-kaikonanedevqd7l4"
log_analytics_workspace_id = "d8abc7ad-91c5-4292-8e9f-30922d9a1dea"
postgres_fqdn              = "psql-kai-konane-dev.postgres.database.azure.com"
resource_group_name        = "rg-kai-konane-dev"
```

`database_url` shows as `<sensitive>` because the output is marked so. Worth
being precise about what that does and does not mean: it redacts console and CI
output only. The value is plaintext in the state file, which is why state
belongs in restricted storage and never in git.

`terraform output -json` and `-raw` both print sensitive values in full. Only
the plain form is safe to capture.

## `terraform state list`

```
data.azurerm_client_config.current
azurerm_application_insights.main
azurerm_container_app_environment.main
azurerm_container_app_environment_storage.media
azurerm_key_vault.main
azurerm_key_vault_secret.app["api-token-secret"]
azurerm_key_vault_secret.app["database-url"]
azurerm_key_vault_secret.app["postgres-password"]
azurerm_key_vault_secret.app["secret-key"]
azurerm_key_vault_secret.app["web-secret-key"]
azurerm_log_analytics_workspace.main
azurerm_monitor_action_group.main
azurerm_postgresql_flexible_server.main
azurerm_postgresql_flexible_server_database.main
azurerm_postgresql_flexible_server_firewall_rule.azure_services
azurerm_resource_group.main
azurerm_role_assignment.kv_secrets_officer
azurerm_role_assignment.kv_secrets_user
azurerm_role_assignment.monitoring_publisher
azurerm_storage_account.media
azurerm_storage_share.media
azurerm_user_assigned_identity.app
random_password.api_token_secret
random_password.flask_secret_key
random_password.web_secret_key
random_string.suffix
module.api.azurerm_container_app.this
module.gateway.azurerm_container_app.this
module.web.azurerm_container_app.this
```

Three things this list records:

**One module, consumed three times.** The last three entries are the same
module at three addresses — api, web and gateway differ in about eight ways and
agree in about thirty, so the eight are the module's interface and the thirty
live inside it. The interface was derived from writing two of the apps out
longhand first, not guessed in advance.

**Two role assignments on the vault, not one.** `kv_secrets_user` for the app's
managed identity and `kv_secrets_officer` for the principal running apply.
Azure RBAC separates the control plane from the data plane: Contributor on a
vault lets you change the vault and read nothing inside it, so an app missing
the data-plane role starts, resolves nothing, and reports an error naming the
vault rather than the role.

**Three generated passwords, none supplied.** `SECRET_KEY`, `WEB_SECRET_KEY`
and `API_TOKEN_SECRET` are `random_password` resources. A value nobody has ever
seen cannot be pasted into a chat window or committed — which is how this
project's earlier Postgres credential reached git history.

## Teardown

Destroyed the same day. Two things got in the way, both of them guards working
as intended:

`prevent_destroy` on `azurerm_postgresql_flexible_server_database.main` refused
the plan. That is the infrastructure-level version of the `conftest.py` check
added after the test suite dropped a production database. Clearing it is a
source edit, because `lifecycle` arguments cannot be variables — a guard you
can switch off with a `-var` flag is off exactly when someone is in a hurry.

`prevent_deletion_if_contains_resources` then refused to delete the resource
group, because Azure had auto-provisioned an "Application Insights Smart
Detection" action group that Terraform never created and did not know about.
The provider offers a feature flag to skip the check; removing the stray
resource instead keeps the protection, which exists to stop Terraform deleting
somebody else's resources that happen to share a group.

Verified empty afterwards with `az group exists --name rg-kai-konane-dev`.
