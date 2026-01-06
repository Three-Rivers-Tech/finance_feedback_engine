# =============================================================================
# Storage Module Variables
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
  description = "Kubernetes namespace for storage resources"
  type        = string
}

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

variable "fast_ssd_provisioner" {
  description = "Provisioner for fast SSD storage"
  type        = string
  default     = "kubernetes.io/no-provisioner"
}

variable "standard_provisioner" {
  description = "Provisioner for standard HDD storage"
  type        = string
  default     = "kubernetes.io/no-provisioner"
}

variable "backup_provisioner" {
  description = "Provisioner for backup storage (typically NFS)"
  type        = string
  default     = "kubernetes.io/no-provisioner"
}

variable "enable_backup_storage" {
  description = "Enable dedicated backup storage class"
  type        = bool
  default     = true
}

variable "backup_retention" {
  description = "Number of days to retain backups"
  type        = number
  default     = 30
}

variable "backup_schedule" {
  description = "Cron schedule for automated backups"
  type        = string
  default     = "0 2 * * *"  # 2 AM daily
}

variable "backup_mount_path" {
  description = "Mount path for backup storage"
  type        = string
  default     = "/mnt/backups"
}

variable "tags" {
  description = "Common tags for resources"
  type        = map(string)
  default     = {}
}
