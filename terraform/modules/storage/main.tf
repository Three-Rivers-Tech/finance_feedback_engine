# =============================================================================
# Storage Module - Persistent Storage Configuration
# =============================================================================
# Manages persistent storage for on-premises Kubernetes deployment:
# - StorageClass definitions
# - PersistentVolume templates
# - Backup storage configuration
# =============================================================================

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.24"
    }
  }
}

# =============================================================================
# STORAGE CLASSES
# =============================================================================

# Fast SSD storage class (local or NFS)
resource "kubernetes_storage_class_v1" "fast_ssd" {
  metadata {
    name = "fast-ssd"
    labels = merge(
      var.tags,
      {
        "app.kubernetes.io/component" = "storage"
        "storage-type"                = "ssd"
      }
    )
  }

  storage_provisioner    = var.fast_ssd_provisioner
  reclaim_policy         = "Retain"
  allow_volume_expansion = true
  volume_binding_mode    = "WaitForFirstConsumer"

  parameters = {
    type = "ssd"
    fsType = "ext4"
  }
}

# Standard HDD storage class
resource "kubernetes_storage_class_v1" "standard" {
  metadata {
    name = "standard"
    labels = merge(
      var.tags,
      {
        "app.kubernetes.io/component" = "storage"
        "storage-type"                = "hdd"
      }
    )
  }

  storage_provisioner    = var.standard_provisioner
  reclaim_policy         = "Retain"
  allow_volume_expansion = true
  volume_binding_mode    = "WaitForFirstConsumer"

  parameters = {
    type = "hdd"
    fsType = "ext4"
  }
}

# Backup storage class (NFS for shared access)
resource "kubernetes_storage_class_v1" "backup" {
  count = var.enable_backup_storage ? 1 : 0

  metadata {
    name = "backup"
    labels = merge(
      var.tags,
      {
        "app.kubernetes.io/component" = "storage"
        "storage-type"                = "backup"
      }
    )
  }

  storage_provisioner    = var.backup_provisioner
  reclaim_policy         = "Retain"
  allow_volume_expansion = true
  volume_binding_mode    = "Immediate"

  parameters = {
    type = "nfs"
    archiveOnDelete = "false"
  }
}

# =============================================================================
# PERSISTENT VOLUMES (Local Path - Manual Pre-provisioning)
# =============================================================================

# Note: For on-prem with local storage, PVs are typically pre-created manually
# or via local-path-provisioner. These are examples/templates.

locals {
  postgres_pv_name = "${var.cluster_name}-postgres-data"
  backup_pv_name   = "${var.cluster_name}-backup"
}

# =============================================================================
# BACKUP CONFIGURATION
# =============================================================================

# ConfigMap for backup scripts and retention policy
resource "kubernetes_config_map_v1" "backup_config" {
  count = var.enable_backup_storage ? 1 : 0

  metadata {
    name      = "${var.namespace}-backup-config"
    namespace = var.namespace
    labels = merge(
      var.tags,
      {
        "app.kubernetes.io/component" = "backup"
      }
    )
  }

  data = {
    "retention-days" = tostring(var.backup_retention)
    "backup-path"    = var.backup_mount_path
    "schedule"       = var.backup_schedule
  }
}

# =============================================================================
# OUTPUTS
# =============================================================================

output "storage_classes" {
  description = "Created storage classes"
  value = {
    fast_ssd = kubernetes_storage_class_v1.fast_ssd.metadata[0].name
    standard = kubernetes_storage_class_v1.standard.metadata[0].name
    backup   = var.enable_backup_storage ? kubernetes_storage_class_v1.backup[0].metadata[0].name : null
  }
}

output "postgres_pv_name" {
  description = "PostgreSQL persistent volume name (for manual creation)"
  value       = local.postgres_pv_name
}

output "backup_config" {
  description = "Backup configuration"
  value = var.enable_backup_storage ? {
    retention_days = var.backup_retention
    schedule       = var.backup_schedule
    mount_path     = var.backup_mount_path
  } : null
}

output "storage_summary" {
  description = "Storage configuration summary"
  value = {
    storage_classes_created = [
      kubernetes_storage_class_v1.fast_ssd.metadata[0].name,
      kubernetes_storage_class_v1.standard.metadata[0].name,
      var.enable_backup_storage ? kubernetes_storage_class_v1.backup[0].metadata[0].name : null
    ]
    backup_enabled = var.enable_backup_storage
    reclaim_policy = "Retain"
  }
}
