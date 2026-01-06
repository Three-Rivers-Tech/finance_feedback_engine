# =============================================================================
# Vault Module Variables
# =============================================================================

variable "environment" {
  description = "Deployment environment (dev, staging, production)"
  type        = string
}

variable "cluster_name" {
  description = "Kubernetes cluster name"
  type        = string
}

variable "namespace" {
  description = "Kubernetes namespace for Vault deployment"
  type        = string
}

variable "vault_version" {
  description = "HashiCorp Vault version"
  type        = string
  default     = "1.17"
}

variable "vault_helm_version" {
  description = "Vault Helm chart version"
  type        = string
  default     = "0.27.0"
}

variable "vault_replicas" {
  description = "Number of Vault replicas (1 for standalone, 3+ for HA)"
  type        = number
  default     = 1

  validation {
    condition     = var.vault_replicas == 1 || var.vault_replicas >= 3
    error_message = "Vault replicas must be 1 (standalone) or >= 3 (HA)"
  }
}

variable "vault_storage_class" {
  description = "Storage class for Vault data"
  type        = string
  default     = "fast-ssd"
}

variable "vault_storage_size" {
  description = "Size of Vault data storage"
  type        = string
  default     = "10Gi"
}

variable "secret_paths" {
  description = "Vault secret paths configuration"
  type = map(string)
  default = {
    app      = "secret/data/dev/app"
    database = "database/dev/ffe"
    pki      = "pki/ffe"
    transit  = "transit/ffe"
  }
}

variable "acme_email" {
  description = "Email for ACME/Let's Encrypt (stored in Vault)"
  type        = string
}

variable "tags" {
  description = "Common tags for resources"
  type        = map(string)
  default     = {}
}
