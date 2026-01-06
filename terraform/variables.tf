# Finance Feedback Engine - Terraform Variables
# Define all input variables for infrastructure deployment

# ============================================================================
# ENVIRONMENT CONFIGURATION
# ============================================================================

variable "environment" {
  description = "Deployment environment (dev, staging, production)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be dev, staging, or production."
  }
}

variable "cluster_name" {
  description = "Kubernetes cluster name"
  type        = string
  default     = "ffe-cluster"
}

variable "namespace" {
  description = "Kubernetes namespace for FFE deployment"
  type        = string
  default     = "ffe"
}

# ============================================================================
# KUBERNETES CONFIGURATION
# ============================================================================

variable "kubeconfig_path" {
  description = "Path to kubeconfig file (leave empty to use current context)"
  type        = string
  default     = ""
}

variable "kubernetes_host" {
  description = "Kubernetes cluster host (alternative to kubeconfig_path)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "kubernetes_token" {
  description = "Kubernetes authentication token"
  type        = string
  default     = ""
  sensitive   = true
}

variable "kubernetes_ca_certificate" {
  description = "Kubernetes cluster CA certificate"
  type        = string
  default     = ""
  sensitive   = true
}

# ============================================================================
# NETWORKING
# ============================================================================

variable "domain_names" {
  description = "Domain names for FFE (UI and API endpoints)"
  type        = list(string)
  default     = ["ffe.three-rivers-tech.com", "api.ffe.three-rivers-tech.com"]
}

variable "network_cidr" {
  description = "Network CIDR block for on-premises deployment"
  type        = string
  default     = "10.0.0.0/16"
}

variable "dns_servers" {
  description = "DNS servers for cluster"
  type        = list(string)
  default     = ["8.8.8.8", "8.8.4.4"]
}

# ============================================================================
# TLS / ACME (Let's Encrypt)
# ============================================================================

variable "acme_email" {
  description = "Email for ACME/Let's Encrypt certificate notifications"
  type        = string
  default     = "cpenrod@three-rivers-tech.com"
}

variable "cert_manager_version" {
  description = "cert-manager Helm chart version"
  type        = string
  default     = "v1.19.2"
}

# ============================================================================
# STORAGE
# ============================================================================

variable "storage_classes" {
  description = "Storage class configurations"
  type = map(object({
    provisioner = string
    type        = string
  }))
  default = {
    fast-ssd = {
      provisioner = "kubernetes.io/no-provisioner"
      type        = "ssd"
    }
    standard = {
      provisioner = "kubernetes.io/no-provisioner"
      type        = "hdd"
    }
  }
}

variable "backup_retention_days" {
  description = "Number of days to retain backups"
  type        = number
  default     = 30
}

# ============================================================================
# DATABASE (PostgreSQL)
# ============================================================================

variable "postgres_bundled" {
  description = "Deploy PostgreSQL via Helm (true) or use external (false)"
  type        = bool
  default     = false
}

variable "postgres_endpoint" {
  description = "External PostgreSQL endpoint (if not bundled)"
  type        = string
  default     = "postgres.example.com:5432"
}

variable "postgres_password" {
  description = "PostgreSQL password"
  type        = string
  sensitive   = true
}

variable "postgres_replication_password" {
  description = "PostgreSQL replication password"
  type        = string
  sensitive   = true
}

variable "postgres_replicas" {
  description = "Number of PostgreSQL read replicas"
  type        = number
  default     = 2
}

variable "postgres_version" {
  description = "PostgreSQL version"
  type        = string
  default     = "16"
}

variable "postgres_helm_version" {
  description = "PostgreSQL Helm chart version"
  type        = string
  default     = "13.2.0"
}

variable "postgres_storage_class" {
  description = "Storage class for PostgreSQL"
  type        = string
  default     = "fast-ssd"
}

variable "postgres_volume_size" {
  description = "PostgreSQL volume size"
  type        = string
  default     = "20Gi"
}

# ============================================================================
# DATABASE URL
# ============================================================================

variable "database_url" {
  description = "PostgreSQL connection URL (postgresql+psycopg2://...)"
  type        = string
  sensitive   = true
}

# ============================================================================
# VAULT
# ============================================================================

variable "vault_version" {
  description = "HashiCorp Vault version"
  type        = string
  default     = "1.17"
}

variable "vault_ha_enabled" {
  description = "Enable Vault HA (3-node cluster)"
  type        = bool
  default     = false
}

variable "vault_storage_class" {
  description = "Storage class for Vault"
  type        = string
  default     = "fast-ssd"
}

# ============================================================================
# APPLICATION (Finance Feedback Engine)
# ============================================================================

variable "ffe_app_version" {
  description = "FFE application version/image tag"
  type        = string
  default     = "latest"
}

variable "ffe_replicas" {
  description = "Number of FFE backend replicas"
  type        = number
  default     = 1

  validation {
    condition     = var.ffe_replicas >= 1
    error_message = "FFE replicas must be at least 1."
  }
}

# ============================================================================
# INGRESS
# ============================================================================

variable "nginx_ingress_version" {
  description = "Nginx Ingress Controller Helm chart version"
  type        = string
  default     = "4.10.0"
}

# ============================================================================
# KUBERNETES VERSIONS
# ============================================================================

variable "kubernetes_version" {
  description = "Kubernetes version"
  type        = string
  default     = "v1.29"
}

# ============================================================================
# TAGS
# ============================================================================

variable "tags" {
  description = "Common tags for all resources"
  type        = map(string)
  default = {
    Project     = "Finance-Feedback-Engine"
    ManagedBy   = "Terraform"
    CreatedAt   = "2025-01-01"
  }
}
