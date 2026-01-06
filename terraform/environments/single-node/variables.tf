# =============================================================================
# Single-Node Environment Variables
# =============================================================================

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "cluster_name" {
  description = "Kubernetes cluster name"
  type        = string
  default     = "ffe-single"
}

variable "namespace" {
  description = "Kubernetes namespace for FFE"
  type        = string
  default     = "ffe"
}

# =============================================================================
# COMPUTE CONFIGURATION
# =============================================================================

variable "master_ip" {
  description = "Master node IP address"
  type        = string
}

variable "worker_ips" {
  description = "Worker node IP addresses (empty for single-node)"
  type        = list(string)
  default     = []
}

variable "ssh_user" {
  description = "SSH user for node access"
  type        = string
  default     = "ubuntu"
}

variable "ssh_private_key_path" {
  description = "Path to SSH private key"
  type        = string
  default     = "~/.ssh/id_rsa"
}

variable "k3s_version" {
  description = "K3s version"
  type        = string
  default     = "v1.29.0+k3s1"
}

# =============================================================================
# GPU CONFIGURATION (CRITICAL)
# =============================================================================

variable "gpu_node_ips" {
  description = "List of node IPs with NVIDIA GPUs (required for AI/ML)"
  type        = list(string)
}

variable "nvidia_driver_version" {
  description = "NVIDIA driver version (e.g., 535, 545)"
  type        = string
  default     = "545"
}

# =============================================================================
# NETWORKING CONFIGURATION
# =============================================================================

variable "domain_names" {
  description = "Domain names for ingress"
  type        = list(string)
}

variable "network_cidr" {
  description = "Network CIDR block"
  type        = string
  default     = "10.42.0.0/16"
}

variable "ingress_ip" {
  description = "Ingress controller IP address"
  type        = string
}

variable "dns_servers" {
  description = "DNS servers"
  type        = list(string)
  default     = ["8.8.8.8", "8.8.4.4"]
}

variable "manage_firewall" {
  description = "Whether to manage UFW firewall"
  type        = bool
  default     = false
}

variable "cloudflare_zone_id" {
  description = "Cloudflare zone ID (optional)"
  type        = string
  default     = ""
}

# =============================================================================
# STORAGE CONFIGURATION
# =============================================================================

# Storage provisioners are node-local for single-node deployments

# =============================================================================
# VAULT CONFIGURATION
# =============================================================================

variable "vault_version" {
  description = "Vault version"
  type        = string
  default     = "1.17"
}

variable "vault_helm_version" {
  description = "Vault Helm chart version"
  type        = string
  default     = "0.27.0"
}

variable "acme_email" {
  description = "Email for ACME certificates"
  type        = string
}

# =============================================================================
# APPLICATION CONFIGURATION
# =============================================================================

variable "ffe_app_version" {
  description = "FFE application version"
  type        = string
  default     = "0.1.0"
}

variable "deploy_postgres" {
  description = "Deploy PostgreSQL via Helm"
  type        = bool
  default     = true
}

variable "postgres_password" {
  description = "PostgreSQL password"
  type        = string
  sensitive   = true
}

variable "postgres_helm_version" {
  description = "PostgreSQL Helm chart version"
  type        = string
  default     = "13.2.0"
}

variable "postgres_volume_size" {
  description = "PostgreSQL PVC size"
  type        = string
  default     = "20Gi"
}

variable "database_url" {
  description = "External database URL (if not deploying Postgres)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "cert_manager_version" {
  description = "cert-manager version"
  type        = string
  default     = "v1.19.2"
}

variable "nginx_ingress_version" {
  description = "Nginx ingress version"
  type        = string
  default     = "4.10.0"
}

# =============================================================================
# TAGS
# =============================================================================

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default = {
    Project     = "Finance Feedback Engine"
    Environment = "single-node"
    ManagedBy   = "Terraform"
  }
}
