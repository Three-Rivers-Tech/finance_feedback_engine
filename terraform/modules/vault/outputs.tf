# =============================================================================
# Vault Module Outputs
# =============================================================================

output "vault_address" {
  description = "Vault cluster address (internal)"
  value       = "http://vault.${var.namespace}.svc.cluster.local:8200"
}

output "vault_ui_service" {
  description = "Vault UI service name"
  value       = "vault-ui.${var.namespace}.svc.cluster.local"
}

output "vault_replicas" {
  description = "Number of Vault replicas"
  value       = var.vault_replicas
}

output "vault_ha_enabled" {
  description = "Whether Vault HA is enabled"
  value       = var.vault_replicas > 1
}

output "secret_paths" {
  description = "Configured Vault secret paths"
  value       = var.secret_paths
}

output "init_guide_configmap" {
  description = "ConfigMap with Vault initialization guide"
  value       = "${var.cluster_name}-vault-init"
}

output "policies_configmap" {
  description = "ConfigMap with Vault policies"
  value       = "${var.cluster_name}-vault-policies"
}

output "kubernetes_auth_role" {
  description = "Kubernetes auth role name for FFE backend"
  value       = "ffe-backend"
}

output "vault_summary" {
  description = "Vault configuration summary"
  value = {
    environment  = var.environment
    address      = "http://vault.${var.namespace}.svc.cluster.local:8200"
    replicas     = var.vault_replicas
    ha_enabled   = var.vault_replicas > 1
    storage      = "${var.vault_storage_size} (${var.vault_storage_class})"
    secret_paths = var.secret_paths
  }
}
