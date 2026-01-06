# =============================================================================
# Finance Feedback Engine - Terraform Root Module (On-Premises)
# =============================================================================
# This is the root configuration file for on-prem deployment.
# Specific environment configurations (single-node, HA) are in environments/
#
# USAGE:
#   cd terraform/environments/single-node (or ha)
#   terraform init
#   terraform plan
#   terraform apply
#
# DO NOT run 'terraform init' in this directory directly.
# =============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.24"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }

  # Backend will be configured per environment in environments/*/backend.tf
  # Examples:
  # - local backend (for development)
  # - s3 backend (for shared team state)
  # - terraform cloud (for remote state + locking)
}

# =============================================================================
# INPUT VARIABLES (COMMON ACROSS ALL ENVIRONMENTS)
# =============================================================================
# Individual environments can override these in their own variables.tf

variable "environment" {
  description = "Environment name: dev, staging, production"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be dev, staging, or production."
  }
}

variable "cluster_name" {
  description = "Name of the Kubernetes cluster"
  type        = string
  default     = "ffe"
}

variable "domain_names" {
  description = "Domain names for ingress TLS certificates"
  type        = list(string)
  default     = ["ffe.three-rivers-tech.com", "api.ffe.three-rivers-tech.com"]
}

variable "acme_email" {
  description = "Email for ACME (Let's Encrypt) certificate notifications"
  type        = string
  default     = "cpenrod@three-rivers-tech.com"
  sensitive   = true
}

variable "kubernetes_version" {
  description = "Kubernetes version (e.g., v1.29, v1.30)"
  type        = string
  default     = "v1.29"
}

variable "postgres_version" {
  description = "PostgreSQL version (e.g., 16, 17)"
  type        = string
  default     = "16"
}

variable "vault_version" {
  description = "HashiCorp Vault version (e.g., 1.17, 1.18)"
  type        = string
  default     = "1.17"
}

variable "tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default = {
    Project     = "Finance Feedback Engine"
    Environment = "on-prem"
    ManagedBy   = "Terraform"
    CreatedAt   = "2026-01-06"
  }
}

# =============================================================================
# OUTPUTS (COMMON ACROSS ALL ENVIRONMENTS)
# =============================================================================
# Individual environments can append to these outputs in their outputs.tf

output "cluster_name" {
  description = "Name of the deployed Kubernetes cluster"
  value       = var.cluster_name
}

output "environment" {
  description = "Environment name"
  value       = var.environment
}

output "domain_names" {
  description = "Domain names configured for TLS"
  value       = var.domain_names
}

# =============================================================================
# NOTES FOR IMPLEMENTATION
# =============================================================================
#
# PHASE 1 (Current):
# - Scaffold Terraform module structure
# - Define variables and outputs
# - Create module skeleton files
#
# PHASE 2 (THR-39):
# - Implement networking module (VPC, firewall, DNS)
# - Implement compute module (Ubuntu provisioning, K3s bootstrap)
# - Implement storage module (PV provisioning, NFS)
# - Implement vault module (Vault bootstrap)
# - Create environment configurations (single-node, HA)
# - Test terraform plan and apply
#
# PHASE 3 (THR-41):
# - Wire into GitHub Actions CI/CD
# - Add terraform plan/apply jobs
# - Add state locking and backup automation
#
# =============================================================================

