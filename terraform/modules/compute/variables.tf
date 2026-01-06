# =============================================================================
# Compute Module Variables
# =============================================================================

variable "environment" {
  description = "Deployment environment (dev, staging, production)"
  type        = string
}

variable "cluster_name" {
  description = "Kubernetes cluster name"
  type        = string
}

# =============================================================================
# NODE CONFIGURATION
# =============================================================================

variable "master_ip" {
  description = "Master node IP address"
  type        = string
}

variable "worker_ips" {
  description = "List of worker node IP addresses"
  type        = list(string)
  default     = []
}

variable "ssh_user" {
  description = "SSH user for node access"
  type        = string
  default     = "ubuntu"
}

variable "ssh_private_key_path" {
  description = "Path to SSH private key for node access"
  type        = string
  default     = "~/.ssh/id_rsa"
}

# =============================================================================
# KUBERNETES CONFIGURATION
# =============================================================================

variable "k3s_version" {
  description = "K3s version to install (e.g., v1.29.0+k3s1)"
  type        = string
  default     = "v1.29.0+k3s1"
}

variable "disable_traefik" {
  description = "Disable Traefik ingress controller (use Nginx instead)"
  type        = bool
  default     = true
}

# =============================================================================
# GPU CONFIGURATION
# =============================================================================

variable "enable_gpu" {
  description = "Enable GPU support for AI/ML workloads"
  type        = bool
  default     = true
}

variable "gpu_node_ips" {
  description = "List of node IPs with NVIDIA GPUs"
  type        = list(string)
  default     = []
}

variable "nvidia_driver_version" {
  description = "NVIDIA driver version (e.g., 535, 545). Leave empty for auto-detection."
  type        = string
  default     = "545"
}

variable "nvidia_container_toolkit_version" {
  description = "NVIDIA Container Toolkit version"
  type        = string
  default     = "v1.14.6"
}

variable "deploy_gpu_operator" {
  description = "Deploy NVIDIA GPU Operator for automated GPU management"
  type        = bool
  default     = true
}

variable "gpu_operator_version" {
  description = "NVIDIA GPU Operator Helm chart version"
  type        = string
  default     = "v23.9.1"
}

variable "enable_gpu_monitoring" {
  description = "Enable DCGM (Data Center GPU Manager) metrics exporter"
  type        = bool
  default     = true
}

variable "enable_mig" {
  description = "Enable Multi-Instance GPU (MIG) support for GPU partitioning"
  type        = bool
  default     = false
}

variable "taint_gpu_nodes" {
  description = "Taint GPU nodes to prevent non-GPU workloads from scheduling"
  type        = bool
  default     = true
}

# =============================================================================
# RESOURCE ALLOCATION
# =============================================================================

variable "gpu_resource_limit" {
  description = "GPU resource limit per pod (nvidia.com/gpu)"
  type        = number
  default     = 1
}

variable "gpu_memory_fraction" {
  description = "Fraction of GPU memory to allocate per container (0.0-1.0)"
  type        = number
  default     = 1.0

  validation {
    condition     = var.gpu_memory_fraction > 0 && var.gpu_memory_fraction <= 1.0
    error_message = "GPU memory fraction must be between 0.0 and 1.0"
  }
}

# =============================================================================
# TAGS
# =============================================================================

variable "tags" {
  description = "Common tags for resources"
  type        = map(string)
  default     = {}
}
