# =============================================================================
# Compute Module - Node Provisioning with GPU Support
# =============================================================================
# Manages compute resources for on-premises Kubernetes deployment:
# - Ubuntu node provisioning
# - K3s/Kubernetes installation
# - GPU detection and driver installation (NVIDIA)
# - GPU operator deployment for container runtime
# =============================================================================

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
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
# GPU DETECTION AND DRIVER INSTALLATION
# =============================================================================

# Detect NVIDIA GPUs on nodes
resource "null_resource" "gpu_detection" {
  for_each = var.enable_gpu ? toset(concat([var.master_ip], var.worker_ips)) : []

  triggers = {
    node_ip = each.value
  }

  provisioner "local-exec" {
    command = <<-EOT
      echo "Checking for NVIDIA GPU on ${each.value}..."
      ssh -o StrictHostKeyChecking=no ${var.ssh_user}@${each.value} "lspci | grep -i nvidia" || echo "No NVIDIA GPU detected on ${each.value}"
    EOT
  }
}

# Install NVIDIA drivers on GPU nodes
resource "null_resource" "nvidia_driver_install" {
  for_each = var.enable_gpu ? toset(var.gpu_node_ips) : []

  triggers = {
    node_ip        = each.value
    driver_version = var.nvidia_driver_version
  }

  provisioner "remote-exec" {
    connection {
      type        = "ssh"
      user        = var.ssh_user
      host        = each.value
      private_key = file(var.ssh_private_key_path)
    }

    inline = [
      "set -e",
      "echo 'Installing NVIDIA drivers on ${each.value}...'",

      # Update package lists
      "sudo apt-get update",

      # Install build essentials
      "sudo apt-get install -y build-essential dkms",

      # Add NVIDIA PPA (if using PPA method)
      "sudo add-apt-repository -y ppa:graphics-drivers/ppa || true",
      "sudo apt-get update",

      # Install NVIDIA driver (specify version or use recommended)
      var.nvidia_driver_version != "" ?
        "sudo apt-get install -y nvidia-driver-${var.nvidia_driver_version}" :
        "sudo ubuntu-drivers install --gpgpu",

      # Verify installation
      "nvidia-smi || echo 'NVIDIA driver installed, reboot may be required'",

      # Install nvidia-container-toolkit
      "distribution=$(. /etc/os-release;echo $ID$VERSION_ID)",
      "curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg",
      "curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list",
      "sudo apt-get update",
      "sudo apt-get install -y nvidia-container-toolkit",

      # Configure containerd for NVIDIA runtime (K3s uses containerd)
      "sudo nvidia-ctk runtime configure --runtime=containerd",
      "sudo systemctl restart containerd || true",

      "echo 'NVIDIA setup complete on ${each.value}'"
    ]
  }

  depends_on = [null_resource.gpu_detection]
}

# =============================================================================
# K3S INSTALLATION (Master Node)
# =============================================================================

resource "null_resource" "k3s_master" {
  triggers = {
    master_ip         = var.master_ip
    k3s_version       = var.k3s_version
    gpu_enabled       = var.enable_gpu
  }

  provisioner "remote-exec" {
    connection {
      type        = "ssh"
      user        = var.ssh_user
      host        = var.master_ip
      private_key = file(var.ssh_private_key_path)
    }

    inline = [
      "set -e",
      "echo 'Installing K3s master on ${var.master_ip}...'",

      # Install K3s with GPU support if enabled
      var.enable_gpu ?
        "curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION='${var.k3s_version}' sh -s - server --disable traefik --nvidia-runtime=true" :
        "curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION='${var.k3s_version}' sh -s - server --disable traefik",

      # Wait for K3s to be ready
      "sudo k3s kubectl wait --for=condition=Ready nodes --all --timeout=300s",

      # Get node token for workers
      "sudo cat /var/lib/rancher/k3s/server/node-token > /tmp/k3s-token",
      "chmod 644 /tmp/k3s-token",

      "echo 'K3s master installation complete'"
    ]
  }

  depends_on = [null_resource.nvidia_driver_install]
}

# Retrieve K3s token from master
resource "null_resource" "fetch_k3s_token" {
  triggers = {
    master_ip = var.master_ip
  }

  provisioner "local-exec" {
    command = "ssh -o StrictHostKeyChecking=no ${var.ssh_user}@${var.master_ip} 'sudo cat /var/lib/rancher/k3s/server/node-token' > ${path.module}/k3s-token.txt"
  }

  depends_on = [null_resource.k3s_master]
}

# Retrieve kubeconfig from master
resource "null_resource" "fetch_kubeconfig" {
  triggers = {
    master_ip = var.master_ip
  }

  provisioner "local-exec" {
    command = <<-EOT
      ssh -o StrictHostKeyChecking=no ${var.ssh_user}@${var.master_ip} 'sudo cat /etc/rancher/k3s/k3s.yaml' > ${path.module}/kubeconfig.yaml
      sed -i 's/127.0.0.1/${var.master_ip}/g' ${path.module}/kubeconfig.yaml
    EOT
  }

  depends_on = [null_resource.k3s_master]
}

# =============================================================================
# K3S WORKER NODES
# =============================================================================

resource "null_resource" "k3s_workers" {
  for_each = toset(var.worker_ips)

  triggers = {
    worker_ip   = each.value
    k3s_version = var.k3s_version
    master_ip   = var.master_ip
  }

  provisioner "remote-exec" {
    connection {
      type        = "ssh"
      user        = var.ssh_user
      host        = each.value
      private_key = file(var.ssh_private_key_path)
    }

    inline = [
      "set -e",
      "echo 'Installing K3s worker on ${each.value}...'",

      # Get token from master (transferred via SSH)
      "K3S_TOKEN=$(ssh -o StrictHostKeyChecking=no ${var.ssh_user}@${var.master_ip} 'sudo cat /var/lib/rancher/k3s/server/node-token')",

      # Install K3s worker with GPU support if this is a GPU node
      contains(var.gpu_node_ips, each.value) ?
        "curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION='${var.k3s_version}' K3S_URL=https://${var.master_ip}:6443 K3S_TOKEN=$K3S_TOKEN sh -s - agent --nvidia-runtime=true" :
        "curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION='${var.k3s_version}' K3S_URL=https://${var.master_ip}:6443 K3S_TOKEN=$K3S_TOKEN sh -s - agent",

      "echo 'K3s worker installation complete on ${each.value}'"
    ]
  }

  depends_on = [
    null_resource.k3s_master,
    null_resource.nvidia_driver_install
  ]
}

# =============================================================================
# NVIDIA GPU OPERATOR (Kubernetes-native GPU management)
# =============================================================================

resource "helm_release" "nvidia_gpu_operator" {
  count = var.enable_gpu && var.deploy_gpu_operator ? 1 : 0

  name       = "nvidia-gpu-operator"
  repository = "https://helm.ngc.nvidia.com/nvidia"
  chart      = "gpu-operator"
  version    = var.gpu_operator_version
  namespace  = "gpu-operator"

  create_namespace = true

  values = [
    yamlencode({
      operator = {
        defaultRuntime = "containerd"
      }
      driver = {
        enabled = false  # We installed drivers manually
      }
      toolkit = {
        enabled = true
        version = var.nvidia_container_toolkit_version
      }
      devicePlugin = {
        enabled = true
        config = {
          name = "time-slicing-config"
          default = "any"
        }
      }
      dcgmExporter = {
        enabled = var.enable_gpu_monitoring
      }
      gfd = {
        enabled = true  # GPU Feature Discovery
      }
      migManager = {
        enabled = var.enable_mig  # Multi-Instance GPU
      }
      nodeStatusExporter = {
        enabled = true
      }
    })
  ]

  depends_on = [
    null_resource.k3s_master,
    null_resource.k3s_workers,
    null_resource.fetch_kubeconfig
  ]
}

# =============================================================================
# GPU NODE LABELING
# =============================================================================

# Label GPU nodes for scheduling
resource "null_resource" "label_gpu_nodes" {
  count = var.enable_gpu ? 1 : 0

  triggers = {
    gpu_nodes = join(",", var.gpu_node_ips)
  }

  provisioner "local-exec" {
    command = <<-EOT
      export KUBECONFIG=${path.module}/kubeconfig.yaml

      # Label each GPU node
      ${join("\n", [
        for ip in var.gpu_node_ips :
        "kubectl label node $(kubectl get nodes -o wide | grep ${ip} | awk '{print $1}') nvidia.com/gpu=true gpu=nvidia --overwrite || true"
      ])}

      # Add taint for GPU nodes (optional, ensures only GPU workloads run on GPU nodes)
      ${var.taint_gpu_nodes ? join("\n", [
        for ip in var.gpu_node_ips :
        "kubectl taint node $(kubectl get nodes -o wide | grep ${ip} | awk '{print $1}') nvidia.com/gpu=true:NoSchedule --overwrite || true"
      ]) : "echo 'GPU node taints disabled'"}
    EOT
  }

  depends_on = [
    null_resource.k3s_workers,
    null_resource.fetch_kubeconfig
  ]
}

# =============================================================================
# OUTPUTS
# =============================================================================

output "master_ip" {
  description = "Master node IP address"
  value       = var.master_ip
}

output "worker_ips" {
  description = "Worker node IP addresses"
  value       = var.worker_ips
}

output "gpu_node_ips" {
  description = "GPU-enabled node IP addresses"
  value       = var.gpu_node_ips
}

output "kubeconfig_path" {
  description = "Path to kubeconfig file"
  value       = "${path.module}/kubeconfig.yaml"
}

output "k3s_token_path" {
  description = "Path to K3s node token"
  value       = "${path.module}/k3s-token.txt"
  sensitive   = true
}

output "gpu_enabled" {
  description = "Whether GPU support is enabled"
  value       = var.enable_gpu
}

output "gpu_operator_deployed" {
  description = "Whether NVIDIA GPU Operator is deployed"
  value       = var.enable_gpu && var.deploy_gpu_operator
}

output "cluster_summary" {
  description = "Compute cluster summary"
  value = {
    master_ip       = var.master_ip
    worker_count    = length(var.worker_ips)
    gpu_node_count  = length(var.gpu_node_ips)
    k3s_version     = var.k3s_version
    gpu_enabled     = var.enable_gpu
    gpu_operator    = var.enable_gpu && var.deploy_gpu_operator
  }
}
