# A container app, with the parts that differ between the three exposed and the
# parts that do not hidden.
#
# The three apps in this system differ in about eight ways and agree in about
# thirty: same identity model, same log destination, same probe shape, same
# revision mode, same registry. Writing them out three times means three places
# to update and two of them get forgotten -- which is not hypothetical, it is
# what the hand-rolled `az containerapp create` commands this replaces did.
#
# The interface below is evidence-based rather than guessed: it is exactly the
# set of things the api, web and gateway were observed to disagree about.

variable "name" {
  type        = string
  description = "App name. Becomes part of the internal FQDN."
}

variable "resource_group_name" {
  type = string
}

variable "container_app_environment_id" {
  type = string
}

variable "image" {
  type        = string
  description = "Fully qualified image reference including tag"
}

variable "identity_id" {
  type        = string
  description = "User-assigned managed identity resource id, used to resolve Key Vault references at container start"
}

variable "external_ingress" {
  type        = bool
  default     = false
  description = "true puts the app on the public internet. Exactly one app in this system should set it."
}

variable "target_port" {
  type        = number
  default     = 5000
  description = "Port the container listens on. Ingress answers on 80/443 regardless."
}

variable "env" {
  type        = map(string)
  default     = {}
  description = "Plain environment variables. Anything sensitive belongs in secret_refs -- values here are readable by anyone with reader access to the app."
}

variable "secret_refs" {
  type        = map(string)
  default     = {}
  description = "Map of env var name to the name of a secret defined on the app. Rendered as secretRef, so the value never appears in the app definition."
}

variable "secrets" {
  type = map(object({
    key_vault_secret_id = string
  }))
  default     = {}
  description = "Secrets to define on the app, as Key Vault references resolved at runtime by the identity. The value is not in the template and rotating it in the vault needs no redeploy."
}

variable "cpu" {
  type        = number
  default     = 0.25
  description = "vCPU per replica. Container Apps accepts only specific cpu/memory pairs."
}

variable "memory" {
  type        = string
  default     = "0.5Gi"
  description = "Memory per replica. Must pair with cpu: 0.25 goes with 0.5Gi, 0.5 with 1Gi."
}

variable "min_replicas" {
  type    = number
  default = 0
}

variable "max_replicas" {
  type    = number
  default = 2
}

variable "liveness_path" {
  type        = string
  default     = "/healthz"
  description = "Path for the liveness probe. Empty disables it."
}

variable "readiness_path" {
  type        = string
  default     = ""
  description = "Path for the readiness probe. Empty disables it."
}

variable "volume_mounts" {
  type = map(object({
    storage_name = string
  }))
  default     = {}
  description = "Azure Files shares to mount, keyed by mount path"
}

variable "tags" {
  type    = map(string)
  default = {}
}
