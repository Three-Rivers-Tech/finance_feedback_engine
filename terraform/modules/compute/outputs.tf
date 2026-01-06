# =============================================================================
# Compute Module Outputs
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
  description = "Path to kubeconfig file for cluster access"
  value       = "${path.module}/kubeconfig.yaml"
}

output "k3s_version" {
  description = "Installed K3s version"
  value       = var.k3s_version
}

output "gpu_enabled" {
  description = "Whether GPU support is enabled"
  value       = var.enable_gpu
}

output "gpu_operator_deployed" {
  description = "Whether NVIDIA GPU Operator is deployed"
  value       = var.enable_gpu && var.deploy_gpu_operator
}

output "gpu_driver_version" {
  description = "NVIDIA driver version"
  value       = var.nvidia_driver_version
}

output "gpu_monitoring_enabled" {
  description = "Whether GPU monitoring (DCGM) is enabled"
  value       = var.enable_gpu_monitoring
}

output "cluster_endpoints" {
  description = "Kubernetes cluster endpoints"
  value = {
    api_server = "https://${var.master_ip}:6443"
    kubeconfig = "${path.module}/kubeconfig.yaml"
  }
}

output "gpu_configuration" {
  description = "GPU configuration summary"
  value = var.enable_gpu ? {
    enabled            = true
    node_count         = length(var.gpu_node_ips)
    node_ips           = var.gpu_node_ips
    driver_version     = var.nvidia_driver_version
    operator_deployed  = var.deploy_gpu_operator
    monitoring_enabled = var.enable_gpu_monitoring
    mig_enabled        = var.enable_mig
    nodes_tainted      = var.taint_gpu_nodes
    resource_limit     = var.gpu_resource_limit
    memory_fraction    = var.gpu_memory_fraction
  } : {
    enabled = false
  }
}

output "cluster_summary" {
  description = "Complete compute cluster summary"
  value = {
    environment     = var.environment
    cluster_name    = var.cluster_name
    master_ip       = var.master_ip
    worker_count    = length(var.worker_ips)
    total_nodes     = 1 + length(var.worker_ips)
    k3s_version     = var.k3s_version
    gpu_enabled     = var.enable_gpu
    gpu_node_count  = length(var.gpu_node_ips)
    api_server      = "https://${var.master_ip}:6443"
  }
}

output "next_steps" {
  description = "Next steps after compute provisioning"
  value = <<-EOT
    Compute cluster provisioned successfully!

    1. Set KUBECONFIG:
       export KUBECONFIG=${path.module}/kubeconfig.yaml

    2. Verify cluster:
       kubectl get nodes -o wide

    ${var.enable_gpu ? "3. Verify GPU nodes:\n       kubectl get nodes -l nvidia.com/gpu=true\n       kubectl describe node <gpu-node-name> | grep -A 10 Capacity\n\n    4. Check GPU operator status:\n       kubectl get pods -n gpu-operator\n\n    5. Test GPU allocation:\n       kubectl run gpu-test --rm -it --image=nvidia/cuda:12.0-base --restart=Never -- nvidia-smi\n" : ""}
    ${var.enable_gpu && var.enable_gpu_monitoring ? "6. Access GPU metrics:\n       kubectl port-forward -n gpu-operator svc/nvidia-dcgm-exporter 9400:9400\n       curl http://localhost:9400/metrics\n" : ""}
  EOT
}
