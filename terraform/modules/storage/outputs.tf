# =============================================================================
# Storage Module Outputs
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
  value       = "${var.cluster_name}-postgres-data"
}

output "backup_pv_name" {
  description = "Backup persistent volume name (for manual creation)"
  value       = "${var.cluster_name}-backup"
}

output "backup_config" {
  description = "Backup configuration"
  value = var.enable_backup_storage ? {
    retention_days = var.backup_retention
    schedule       = var.backup_schedule
    mount_path     = var.backup_mount_path
    configmap_name = kubernetes_config_map_v1.backup_config[0].metadata[0].name
  } : null
}

output "storage_summary" {
  description = "Storage configuration summary"
  value = {
    environment         = var.environment
    cluster_name        = var.cluster_name
    storage_classes     = [
      kubernetes_storage_class_v1.fast_ssd.metadata[0].name,
      kubernetes_storage_class_v1.standard.metadata[0].name,
      var.enable_backup_storage ? kubernetes_storage_class_v1.backup[0].metadata[0].name : null
    ]
    backup_enabled      = var.enable_backup_storage
    reclaim_policy      = "Retain"
    volume_expansion    = true
  }
}
