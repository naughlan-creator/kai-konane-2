# Infrastructure

The Kai Konane Azure deployment, as code. Replaces the sequence of `az`
commands used for the original Container Apps deployment.

## Layout

| File | Holds |
|---|---|
| `versions.tf` | Terraform and provider constraints, and the backend note |
| `providers.tf` | The azurerm provider and its feature flags |
| `variables.tf` | Every input, typed, with validation where a wrong value has a cost |
| `locals.tf` | Naming, tagging, and the assembled database URL |
| `resource_group.tf` | The group, the caller identity, the name suffix |
| `observability.tf` | Log Analytics, Application Insights, the 5xx alert |
| `database.tf` | Postgres Flexible Server, database, firewall rules |
| `identity.tf` | User-assigned managed identity and its role assignments |
| `keyvault.tf` | The vault, the generated secrets, and the values written to it |
| `storage.tf` | Azure Files share for uploaded content images |
| `container_apps.tf` | The environment and the three apps |
| `modules/container_app/` | One app, parameterised — consumed three times |
| `outputs.tf` | The six things worth printing after an apply |

## Running it

```bash
az login
```

```bash
terraform init
```

Everything except the database password can live in `terraform.tfvars`. The
password comes from the environment, so it never reaches a file:

```bash
$env:TF_VAR_postgres_admin_password = "<at least 16 characters>"
```

```bash
terraform plan -out=tfplan
```

```bash
terraform apply tfplan
```

## Validating without an Azure account

The backend block in `versions.tf` is commented out, so these three run with no
credentials at all — which is what lets CI check this on every pull request:

```bash
terraform fmt -recursive -check ; terraform init -backend=false ; terraform validate
```

## Notes worth knowing before you change anything

**State holds every secret in plaintext.** Marking an output `sensitive` hides
it from console output, not from the state file. Local state is fine for one
person; anything shared needs the azurerm backend, whose blob lease is what
stops two concurrent applies corrupting it.

**The database has `prevent_destroy`.** `terraform destroy` will refuse. That is
deliberate — it is the infrastructure-level version of the `conftest.py` guard
added after the test suite dropped a production database. To tear down for real,
remove the block, apply, then destroy.

**`API_PUBLIC_URL` on web is empty on purpose.** It is not the same value as
`API_BASE_URL`. Setting it to the internal FQDN puts a hostname the browser
cannot resolve into every image tag on the site; pages return 200, tests pass,
and every image breaks. There is a comment in `container_apps.tf` saying so.

**Key Vault secrets use `versionless_id`.** A versioned reference pins the app
to one version, so rotating the secret in the vault changes nothing until
someone redeploys — which defeats the point of the vault reference.

**The `0.0.0.0` firewall rule is not a wildcard.** It is Azure's sentinel for
"other Azure services", and removing it stops Container Apps connecting.

## Not here yet

The Azure AI Foundry resources (`azurerm_cognitive_account` and its deployments)
belong in an `ai.tf`, gated behind an `enable_ai` variable defaulting to false —
every resource here has a predictable monthly cost, and that one bills per token.
