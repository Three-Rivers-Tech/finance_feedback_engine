# =============================================================================
# Networking Module Variables
# =============================================================================

variable "environment" {
  description = "Deployment environment (dev, staging, production)"
  type        = string
}

variable "cluster_name" {
  description = "Kubernetes cluster name"
  type        = string
}

variable "domain_names" {
  description = "List of domain names for ingress (e.g., ffe.three-rivers-tech.com, api.ffe.three-rivers-tech.com)"
  type        = list(string)
}

variable "network_cidr" {
  description = "Network CIDR block for the deployment"
  type        = string
  default     = "10.0.0.0/16"
}

variable "subnet_count" {
  description = "Number of subnets to allocate (for documentation)"
  type        = number
  default     = 3
}

variable "ingress_ip" {
  description = "Public IP address for ingress controller (LoadBalancer or NodePort)"
  type        = string
  default     = "0.0.0.0"
}

variable "ingress_class" {
  description = "Kubernetes ingress class name"
  type        = string
  default     = "nginx"
}

variable "ingress_namespace" {
  description = "Kubernetes namespace for ingress controller"
  type        = string
  default     = "ingress-nginx"
}

variable "dns_servers" {
  description = "DNS servers for cluster"
  type        = list(string)
  default     = ["8.8.8.8", "8.8.4.4"]
}

variable "cloudflare_zone_id" {
  description = "Cloudflare Zone ID (if using Cloudflare DNS)"
  type        = string
  default     = ""
}

variable "manage_firewall" {
  description = "Whether to manage UFW firewall rules (requires sudo)"
  type        = bool
  default     = false
}

variable "ssh_port" {
  description = "SSH port to allow in firewall"
  type        = number
  default     = 22
}

variable "verify_ingress_ip" {
  description = "Whether to verify ingress IP is reachable"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Common tags for resources"
  type        = map(string)
  default     = {}
}
