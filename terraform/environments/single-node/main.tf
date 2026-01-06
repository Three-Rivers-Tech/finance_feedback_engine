# =============================================================================
# Single-Node Environment - Main Configuration
# =============================================================================
# This configuration deploys FFE on a single node with GPU support
# Suitable for: development, testing, small production deployments
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

  backend "local" {
    path = "terraform.tfstate"
  }
}

# =============================================================================
# COMPUTE MODULE - K3s Cluster with GPU Support
# =============================================================================

module "compute" {
  source = "../../modules/compute"

  environment  = var.environment
  cluster_name = var.cluster_name

  # Node Configuration
  master_ip            = var.master_ip
  worker_ips           = var.worker_ips
  ssh_user             = var.ssh_user
  ssh_private_key_path = var.ssh_private_key_path

  # Kubernetes Configuration
  k3s_version      = var.k3s_version
  disable_traefik  = true  # We'll use Nginx ingress

  # GPU Configuration (CRITICAL FOR AI/ML WORKLOADS)
  enable_gpu                        = true
  gpu_node_ips                      = var.gpu_node_ips  # All nodes with NVIDIA GPUs
  nvidia_driver_version             = var.nvidia_driver_version
  nvidia_container_toolkit_version  = "v1.14.6"
  deploy_gpu_operator               = true
  gpu_operator_version              = "v23.9.1"
  enable_gpu_monitoring             = true
  enable_mig                        = false  # Enable for GPU partitioning
  taint_gpu_nodes                   = true   # Only GPU workloads on GPU nodes

  tags = var.tags
}

# =============================================================================
# PROVIDERS (Configured after compute module creates cluster)
# =============================================================================

provider "kubernetes" {
  config_path = module.compute.kubeconfig_path
}

provider "helm" {
  kubernetes {
    config_path = module.compute.kubeconfig_path
  }
}

# =============================================================================
# NETWORKING MODULE
# =============================================================================

module "networking" {
  source = "../../modules/networking"

  environment  = var.environment
  cluster_name = var.cluster_name

  # Domain Configuration
  domain_names = var.domain_names

  # Network Configuration
  network_cidr    = var.network_cidr
  ingress_ip      = var.ingress_ip
  ingress_class   = "nginx"
  dns_servers     = var.dns_servers

  # Firewall Configuration
  manage_firewall = var.manage_firewall
  ssh_port        = 22

  # Cloudflare Integration (optional)
  cloudflare_zone_id = var.cloudflare_zone_id

  tags = var.tags

  depends_on = [module.compute]
}

# =============================================================================
# STORAGE MODULE
# =============================================================================

module "storage" {
  source = "../../modules/storage"

  environment  = var.environment
  cluster_name = var.cluster_name
  namespace    = var.namespace

  # Storage Class Configuration
  storage_classes = {
    fast_ssd = {
      provisioner = "kubernetes.io/no-provisioner"
      type        = "ssd"
    }
    standard = {
      provisioner = "kubernetes.io/no-provisioner"
      type        = "hdd"
    }
    backup = {
      provisioner = "kubernetes.io/no-provisioner"
      type        = "nfs"
    }
  }

  # Backup Configuration
  enable_backup_storage = true
  backup_retention      = 30
  backup_schedule       = "0 2 * * *"  # 2 AM daily
  backup_mount_path     = "/mnt/backups"

  tags = var.tags

  depends_on = [module.compute]
}

# =============================================================================
# VAULT MODULE
# =============================================================================

module "vault" {
  source = "../../modules/vault"

  environment  = var.environment
  cluster_name = var.cluster_name
  namespace    = var.namespace

  # Vault Configuration
  vault_version      = var.vault_version
  vault_helm_version = var.vault_helm_version
  vault_replicas     = 1  # Single-node: 1, HA: 3+

  # Storage Configuration
  vault_storage_class = module.storage.storage_classes.fast_ssd
  vault_storage_size  = "10Gi"

  # Secret Paths
  secret_paths = {
    app      = "secret/data/${var.environment}/app"
    database = "database/${var.environment}/ffe"
    pki      = "pki/ffe"
    transit  = "transit/ffe"
  }

  acme_email = var.acme_email

  tags = var.tags

  depends_on = [module.storage]
}

# =============================================================================
# CERT-MANAGER (TLS Certificates)
# =============================================================================

resource "helm_release" "cert_manager" {
  name       = "cert-manager"
  repository = "https://charts.jetstack.io"
  chart      = "cert-manager"
  version    = var.cert_manager_version
  namespace  = "cert-manager"

  create_namespace = true

  set {
    name  = "installCRDs"
    value = "true"
  }

  set {
    name  = "global.leaderElection.namespace"
    value = "cert-manager"
  }

  depends_on = [module.compute]
}

# =============================================================================
# NGINX INGRESS CONTROLLER
# =============================================================================

resource "helm_release" "nginx_ingress" {
  name       = "nginx-ingress"
  repository = "https://kubernetes.github.io/ingress-nginx"
  chart      = "ingress-nginx"
  version    = var.nginx_ingress_version
  namespace  = "ingress-nginx"

  create_namespace = true

  set {
    name  = "controller.service.type"
    value = "LoadBalancer"
  }

  set {
    name  = "controller.service.loadBalancerIP"
    value = var.ingress_ip
  }

  depends_on = [module.compute]
}

# =============================================================================
# POSTGRESQL DATABASE (Optional)
# =============================================================================

resource "helm_release" "postgres" {
  count = var.deploy_postgres ? 1 : 0

  name       = "postgres"
  repository = "https://charts.bitnami.com/bitnami"
  chart      = "postgresql"
  version    = var.postgres_helm_version
  namespace  = var.namespace

  create_namespace = true

  values = [
    yamlencode({
      auth = {
        postgresPassword = var.postgres_password
        database         = "ffe"
        username         = "ffe"
      }
      primary = {
        persistence = {
          enabled      = true
          storageClass = module.storage.storage_classes.fast_ssd
          size         = var.postgres_volume_size
        }
        resources = {
          requests = {
            cpu    = "500m"
            memory = "1Gi"
          }
          limits = {
            cpu    = "2000m"
            memory = "4Gi"
          }
        }
      }
    })
  ]

  depends_on = [module.storage]
}

# =============================================================================
# FFE BACKEND APPLICATION
# =============================================================================

resource "helm_release" "ffe_backend" {
  name       = "ffe-backend"
  chart      = "../../helm/ffe-backend"
  namespace  = var.namespace
  version    = var.ffe_app_version

  create_namespace = true

  values = [
    file("../../helm/ffe-backend/values.yaml"),
    file("../../helm/ffe-backend/values-${var.environment}.yaml"),
    yamlencode({
      # GPU Configuration for AI/ML Workloads
      resources = {
        requests = {
          cpu               = "1000m"
          memory            = "2Gi"
          "nvidia.com/gpu"  = 1  # Request 1 GPU per pod
        }
        limits = {
          cpu               = "4000m"
          memory            = "8Gi"
          "nvidia.com/gpu"  = 1
        }
      }

      # Node Affinity - Schedule on GPU nodes
      affinity = {
        nodeAffinity = {
          requiredDuringSchedulingIgnoredDuringExecution = {
            nodeSelectorTerms = [{
              matchExpressions = [{
                key      = "nvidia.com/gpu"
                operator = "In"
                values   = ["true"]
              }]
            }]
          }
        }
      }

      # Tolerate GPU node taints
      tolerations = [{
        key      = "nvidia.com/gpu"
        operator = "Equal"
        value    = "true"
        effect   = "NoSchedule"
      }]

      # Environment Variables for GPU
      env = [{
        name  = "NVIDIA_VISIBLE_DEVICES"
        value = "all"
      }, {
        name  = "NVIDIA_DRIVER_CAPABILITIES"
        value = "compute,utility"
      }]

      ingress = {
        enabled = true
        hosts   = var.domain_names
        tls = [{
          secretName = "ffe-tls"
          hosts      = var.domain_names
        }]
        annotations = {
          "cert-manager.io/cluster-issuer" = "letsencrypt-prod"
        }
      }

      database = {
        external = !var.deploy_postgres
        url      = var.deploy_postgres ? "postgresql://ffe:${var.postgres_password}@postgres-postgresql.${var.namespace}.svc.cluster.local:5432/ffe" : var.database_url
      }

      vault = {
        enabled = true
        address = module.vault.vault_address
        role    = "ffe-backend"
      }
    })
  ]

  depends_on = [
    helm_release.nginx_ingress,
    helm_release.cert_manager,
    module.vault,
    helm_release.postgres
  ]
}

# =============================================================================
# OUTPUTS
# =============================================================================

output "cluster_summary" {
  description = "Complete cluster deployment summary"
  value = {
    environment      = var.environment
    cluster_name     = var.cluster_name
    master_ip        = module.compute.master_ip
    api_server       = "https://${var.master_ip}:6443"
    kubeconfig       = module.compute.kubeconfig_path

    # GPU Information
    gpu_enabled      = module.compute.gpu_enabled
    gpu_nodes        = module.compute.gpu_node_ips
    gpu_driver       = module.compute.gpu_driver_version

    # Network Information
    domain_names     = var.domain_names
    ingress_ip       = var.ingress_ip

    # Storage Information
    storage_classes  = module.storage.storage_classes

    # Vault Information
    vault_address    = module.vault.vault_address
    vault_ui         = module.vault.vault_ui_service
  }
}

output "next_steps" {
  description = "Next steps after deployment"
  value = <<-EOT
    ===================================================
    Finance Feedback Engine - Single-Node Deployment
    ===================================================

    1. Set kubeconfig:
       export KUBECONFIG=${module.compute.kubeconfig_path}

    2. Verify GPU nodes:
       kubectl get nodes -l nvidia.com/gpu=true -o wide
       kubectl describe node <node-name> | grep -A 10 "Allocatable:"

    3. Test GPU allocation:
       kubectl run gpu-test --rm -it --image=nvidia/cuda:12.0-base --restart=Never -- nvidia-smi

    4. Check GPU operator:
       kubectl get pods -n gpu-operator

    5. Monitor GPU metrics:
       kubectl port-forward -n gpu-operator svc/nvidia-dcgm-exporter 9400:9400
       curl http://localhost:9400/metrics | grep DCGM

    6. Access FFE application:
       https://${var.domain_names[0]}

    7. Initialize Vault:
       kubectl exec -n ${var.namespace} vault-0 -- vault operator init

    8. Check FFE pods (should be on GPU nodes):
       kubectl get pods -n ${var.namespace} -o wide
       kubectl describe pod -n ${var.namespace} <ffe-pod-name> | grep "nvidia.com/gpu"

    GPU Nodes: ${join(", ", var.gpu_node_ips)}
    Driver Version: ${var.nvidia_driver_version}
    ===================================================
  EOT
}
