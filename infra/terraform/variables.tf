variable "subscription_id" {
  type        = string
  default     = null
  description = "Azure subscription id. Null falls back to ARM_SUBSCRIPTION_ID, which is how CI supplies it."
}

variable "location" {
  type        = string
  default     = "southafricanorth"
  description = "Azure region for the application"
}

variable "image_tag" {
  type        = string
  description = "image tag for docker images"

  validation {
    # ensures the tag is not explicitly set to 'latest'
    condition     = var.image_tag != "latest"
    error_message = "Refusing to deploy the 'latest' tag. Pin a version so a rollback has something to roll back to."
  }
}

variable "postgres_admin_password" {
  type        = string
  description = "The administrator password for the PostgreSQL server"
  sensitive   = true

  validation {
    condition     = length(var.postgres_admin_password) >= 16
    error_message = "Postgres password must be at least 16 characters"
  }
}

variable "environment" {
  type        = string
  default     = "dev"
  description = "target deployment environment"

  validation {
    # An exact set, not a suffix match. This value becomes part of every
    # resource name, and a typo producing 'prd' beside 'prod' does not error --
    # it creates a second environment, and both of them bill.
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "The environment variable must be one of: dev, staging, prod"
  }
}

variable "team_owner" {
  type        = string
  default     = "Nolan"
  description = "Name of the owner of the whole project"
}

variable "project_name" {
  type        = string
  default     = "Kai-Konane"
  description = "Name of the project"
}

variable "image_registry" {
  type        = string
  default     = "ghcr.io/naughlan-creator/kai-konane-2"
  description = "Container registry holding the api, web and gateway images"
}

variable "postgres_sku_name" {
  type        = string
  default     = "B_Standard_B1ms"
  description = "Postgres Flexible Server SKU. B_Standard_B1ms is the cheapest that exists."
}

variable "postgres_storage_mb" {
  type        = number
  default     = 32768
  description = "Postgres storage in MB. 32768 is the floor."
}

variable "postgres_version" {
  type        = string
  default     = "16"
  description = "Postgres major version"
}

variable "allowed_ip_addresses" {
  type        = list(string)
  default     = []
  description = "Public IPs allowed through the Postgres firewall, for running migrations from a workstation. Empty means Azure services only."
}

variable "log_retention_days" {
  type        = number
  default     = 30
  description = "Log Analytics retention. 30 is the included floor; beyond that bills per GB per month."
}

variable "min_replicas" {
  type        = number
  default     = 0
  description = "Minimum replicas per container app. 0 scales to zero: free when idle, at the cost of a cold start."
}

variable "max_replicas" {
  type        = number
  default     = 2
  description = "Maximum replicas per container app. The ceiling on both load and bill."
}

variable "enable_ai" {
  type        = bool
  default     = false
  description = "Provision Azure AI Foundry and deploy a model. Off by default: every other resource here has a predictable monthly cost, and this one bills per token -- so its cost is a function of traffic and, if something loops, of a bug."
}

variable "ai_location" {
  type        = string
  default     = "eastus"
  description = "Region for the AI account. Model availability is regional and rarely matches where the app runs -- which makes every call a cross-border transfer. See the data-residency note in deploy/README.md."
}

variable "ai_model_name" {
  type        = string
  default     = "gpt-4o-mini"
  description = "Model to deploy"
}

variable "ai_model_version" {
  type        = string
  default     = "2024-07-18"
  description = "Model version. Pinned for the same reason image tags are: a silently upgraded model is an unreviewed change to production behaviour."
}

variable "ai_capacity" {
  type        = number
  default     = 10
  description = "Thousands of tokens per minute. The throttle and the budget in one number -- exceed it and you get a 429 rather than a larger bill."
}