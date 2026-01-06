# =============================================================================
# Vault Module - HashiCorp Vault Configuration
# =============================================================================
# Deploys and configures HashiCorp Vault for secret management:
# - Vault Helm chart deployment
# - Kubernetes auth configuration
# - Secret path initialization
# =============================================================================

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.24"
    }
  }
}

# =============================================================================
# VAULT HELM DEPLOYMENT
# =============================================================================

resource "helm_release" "vault" {
  name       = "vault"
  repository = "https://helm.releases.hashicorp.com"
  chart      = "vault"
  version    = var.vault_helm_version
  namespace  = var.namespace

  values = [
    yamlencode({
      server = {
        image = {
          repository = "hashicorp/vault"
          tag        = var.vault_version
        }

        # Development/single-node or HA mode
        ha = {
          enabled  = var.vault_replicas > 1
          replicas = var.vault_replicas
          raft = {
            enabled = var.vault_replicas > 1
            config = <<-EOF
              ui = true

              listener "tcp" {
                tls_disable = 1
                address = "[::]:8200"
                cluster_address = "[::]:8201"
              }

              storage "raft" {
                path = "/vault/data"
              }

              service_registration "kubernetes" {}
            EOF
          }
        }

        # Standalone mode (single replica)
        standalone = {
          enabled = var.vault_replicas == 1
          config = <<-EOF
            ui = true

            listener "tcp" {
              tls_disable = 1
              address = "[::]:8200"
            }

            storage "file" {
              path = "/vault/data"
            }
          EOF
        }

        # Resources
        resources = {
          requests = {
            cpu    = "250m"
            memory = "256Mi"
          }
          limits = {
            cpu    = "500m"
            memory = "512Mi"
          }
        }

        # Data storage
        dataStorage = {
          enabled      = true
          size         = var.vault_storage_size
          storageClass = var.vault_storage_class
        }
      }

      # UI configuration
      ui = {
        enabled         = true
        serviceType     = "ClusterIP"
      }

      # Injector for sidecar injection
      injector = {
        enabled = true
        resources = {
          requests = {
            cpu    = "50m"
            memory = "64Mi"
          }
          limits = {
            cpu    = "100m"
            memory = "128Mi"
          }
        }
      }
    })
  ]

  depends_on = []
}

# =============================================================================
# VAULT INITIALIZATION (Post-Deployment)
# =============================================================================

# Note: Vault initialization and unsealing must be done manually or via operator
# This resource documents the required initialization steps

resource "kubernetes_config_map_v1" "vault_init_guide" {
  metadata {
    name      = "${var.cluster_name}-vault-init"
    namespace = var.namespace
    labels = merge(
      var.tags,
      {
        "app.kubernetes.io/component" = "vault"
        "app.kubernetes.io/name"      = "vault-init-guide"
      }
    )
  }

  data = {
    "init-steps.sh" = <<-EOF
      #!/bin/bash
      # Vault Initialization Guide
      # Run these commands after Vault pods are running

      # 1. Initialize Vault (run once)
      kubectl exec -n ${var.namespace} vault-0 -- vault operator init -key-shares=5 -key-threshold=3

      # Save the unseal keys and root token securely!

      # 2. Unseal Vault (required after each restart)
      kubectl exec -n ${var.namespace} vault-0 -- vault operator unseal <KEY1>
      kubectl exec -n ${var.namespace} vault-0 -- vault operator unseal <KEY2>
      kubectl exec -n ${var.namespace} vault-0 -- vault operator unseal <KEY3>

      # 3. Enable Kubernetes auth
      kubectl exec -n ${var.namespace} vault-0 -- vault login <ROOT_TOKEN>
      kubectl exec -n ${var.namespace} vault-0 -- vault auth enable kubernetes

      # 4. Configure Kubernetes auth
      kubectl exec -n ${var.namespace} vault-0 -- vault write auth/kubernetes/config \\
        kubernetes_host="https://kubernetes.default.svc:443"

      # 5. Enable secret engines
      kubectl exec -n ${var.namespace} vault-0 -- vault secrets enable -path=secret kv-v2
      kubectl exec -n ${var.namespace} vault-0 -- vault secrets enable -path=database database
      kubectl exec -n ${var.namespace} vault-0 -- vault secrets enable -path=pki pki
      kubectl exec -n ${var.namespace} vault-0 -- vault secrets enable -path=transit transit

      # 6. Create policies (see vault-policies ConfigMap)
    EOF

    "vault-paths.txt" = <<-EOF
      # Vault Secret Paths for FFE
      ${join("\n", [for path_key, path_value in var.secret_paths : "- ${path_key}: ${path_value}"])}
    EOF
  }
}

# =============================================================================
# VAULT POLICIES (HCL)
# =============================================================================

resource "kubernetes_config_map_v1" "vault_policies" {
  metadata {
    name      = "${var.cluster_name}-vault-policies"
    namespace = var.namespace
    labels = merge(
      var.tags,
      {
        "app.kubernetes.io/component" = "vault"
        "app.kubernetes.io/name"      = "vault-policies"
      }
    )
  }

  data = {
    "ffe-backend-policy.hcl" = <<-EOF
      # Policy for FFE backend to access secrets

      # Application secrets
      path "${var.secret_paths["app"]}/*" {
        capabilities = ["read", "list"]
      }

      # Database credentials (dynamic)
      path "${var.secret_paths["database"]}" {
        capabilities = ["read"]
      }

      # Transit engine for encryption
      path "${var.secret_paths["transit"]}/encrypt/*" {
        capabilities = ["update"]
      }

      path "${var.secret_paths["transit"]}/decrypt/*" {
        capabilities = ["update"]
      }
    EOF

    "apply-policies.sh" = <<-EOF
      #!/bin/bash
      # Apply Vault policies

      kubectl exec -n ${var.namespace} vault-0 -- vault policy write ffe-backend - <<POLICY
      $(cat ffe-backend-policy.hcl)
      POLICY

      # Create Kubernetes role
      kubectl exec -n ${var.namespace} vault-0 -- vault write auth/kubernetes/role/ffe-backend \\
        bound_service_account_names=ffe-backend \\
        bound_service_account_namespaces=${var.namespace} \\
        policies=ffe-backend \\
        ttl=1h
    EOF
  }
}

# =============================================================================
# OUTPUTS
# =============================================================================

output "vault_address" {
  description = "Vault cluster address"
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

output "secret_paths" {
  description = "Configured Vault secret paths"
  value       = var.secret_paths
}

output "init_guide_configmap" {
  description = "ConfigMap with Vault initialization guide"
  value       = kubernetes_config_map_v1.vault_init_guide.metadata[0].name
}

output "policies_configmap" {
  description = "ConfigMap with Vault policies"
  value       = kubernetes_config_map_v1.vault_policies.metadata[0].name
}

output "vault_summary" {
  description = "Vault configuration summary"
  value = {
    address      = "http://vault.${var.namespace}.svc.cluster.local:8200"
    replicas     = var.vault_replicas
    ha_enabled   = var.vault_replicas > 1
    secret_paths = var.secret_paths
  }
}
