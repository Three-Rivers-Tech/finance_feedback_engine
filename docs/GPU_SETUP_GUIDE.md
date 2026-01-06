# GPU Setup Guide - Finance Feedback Engine

## Overview

The Finance Feedback Engine requires NVIDIA GPUs for AI/ML workloads (model inference, sentiment analysis, trading decisions). This guide covers GPU detection, driver installation, and Kubernetes configuration.

## Prerequisites

- Ubuntu 22.04 or 24.04 LTS
- NVIDIA GPU (RTX 30/40 series, A100, H100, or equivalent)
- Terraform >= 1.5.0
- SSH access to cluster nodes

## GPU Detection

### 1. Check for NVIDIA GPU

```bash
# On each node:
lspci | grep -i nvidia

# Expected output (example):
# 01:00.0 VGA compatible controller: NVIDIA Corporation GA102 [GeForce RTX 3090] (rev a1)
```

### 2. Verify System Compatibility

```bash
# Check Ubuntu version
lsb_release -a

# Check kernel version (should be 5.15+)
uname -r

# Check system resources
nvidia-smi  # If drivers already installed

# Check available disk space (need 20GB+ for CUDA)
df -h /
```

## Automated Setup (via Terraform)

Our Terraform compute module automates GPU setup. Configure in `terraform.tfvars`:

```hcl
# GPU Configuration
enable_gpu            = true
gpu_node_ips          = ["192.168.1.100"]  # All nodes with GPUs
nvidia_driver_version = "545"               # RTX 30/40, A100, H100

# GPU Features
deploy_gpu_operator    = true   # Kubernetes GPU automation
enable_gpu_monitoring  = true   # DCGM Prometheus metrics
enable_mig             = false  # Multi-Instance GPU (optional)
taint_gpu_nodes        = true   # Dedicated GPU workloads only
```

Then deploy:

```bash
cd terraform/environments/single-node
terraform init
terraform plan
terraform apply
```

Terraform will:
1. Detect NVIDIA GPUs via `lspci`
2. Install NVIDIA drivers (version 545 by default)
3. Install nvidia-container-toolkit
4. Configure containerd for GPU runtime
5. Bootstrap K3s with `--nvidia-runtime=true`
6. Deploy NVIDIA GPU Operator
7. Label and taint GPU nodes
8. Create kubeconfig at `../../modules/compute/kubeconfig.yaml`

## Manual Setup (Alternative)

If not using Terraform automation:

### 1. Install NVIDIA Drivers

```bash
# Add NVIDIA PPA
sudo add-apt-repository ppa:graphics-drivers/ppa
sudo apt update

# Install recommended driver
sudo ubuntu-drivers install --gpgpu

# Or install specific version
sudo apt install nvidia-driver-545

# Reboot
sudo reboot

# Verify after reboot
nvidia-smi
```

### 2. Install NVIDIA Container Toolkit

```bash
# Add NVIDIA package repository
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Install toolkit
sudo apt update
sudo apt install -y nvidia-container-toolkit

# Configure containerd
sudo nvidia-ctk runtime configure --runtime=containerd
sudo systemctl restart containerd
```

### 3. Install K3s with GPU Support

```bash
# On master node
curl -sfL https://get.k3s.io | sh -s - server \
  --disable traefik \
  --nvidia-runtime=true

# On worker nodes
curl -sfL https://get.k3s.io | K3S_URL=https://MASTER_IP:6443 \
  K3S_TOKEN=<token-from-master> sh -s - agent \
  --nvidia-runtime=true
```

### 4. Deploy NVIDIA GPU Operator

```bash
# Add Helm repo
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia
helm repo update

# Install GPU Operator
helm install gpu-operator nvidia/gpu-operator \
  --namespace gpu-operator \
  --create-namespace \
  --set operator.defaultRuntime=containerd \
  --set driver.enabled=false \
  --set toolkit.enabled=true \
  --set devicePlugin.enabled=true \
  --set dcgmExporter.enabled=true \
  --set gfd.enabled=true
```

### 5. Label GPU Nodes

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Label GPU nodes
kubectl label node <node-name> nvidia.com/gpu=true gpu=nvidia

# Optional: Taint for dedicated GPU workloads
kubectl taint node <node-name> nvidia.com/gpu=true:NoSchedule
```

## Verification

### 1. Check Driver Installation

```bash
nvidia-smi

# Expected output:
# +-----------------------------------------------------------------------------+
# | NVIDIA-SMI 545.29.06    Driver Version: 545.29.06    CUDA Version: 12.3     |
# +-----------------------------------------------------------------------------+
# | GPU  Name        Persistence-M| Bus-Id        Disp.A | Volatile Uncorr. ECC |
# | Fan  Temp  Perf  Pwr:Usage/Cap|         Memory-Usage | GPU-Util  Compute M. |
# +-----------------------------------------------------------------------------+
```

### 2. Check Kubernetes GPU Detection

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml  # Or compute module path

# Check GPU nodes
kubectl get nodes -o custom-columns=\
NAME:.metadata.name,\
GPU:.status.allocatable."nvidia\.com/gpu"

# Verify GPU capacity
kubectl describe node <gpu-node-name> | grep -A 10 "Allocatable:"

# Expected:
#  nvidia.com/gpu:     1
```

### 3. Check GPU Operator

```bash
kubectl get pods -n gpu-operator

# Expected pods:
# - nvidia-device-plugin-daemonset
# - nvidia-dcgm-exporter
# - gpu-feature-discovery
# - nvidia-operator-validator
```

### 4. Test GPU Allocation

```bash
# Run CUDA test container
kubectl run gpu-test --rm -it \
  --image=nvidia/cuda:12.0-base \
  --restart=Never \
  -- nvidia-smi

# Should show GPU info inside container
```

### 5. Test GPU Workload Scheduling

```bash
# Create test pod with GPU request
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: gpu-pod-test
spec:
  containers:
  - name: cuda-container
    image: nvidia/cuda:12.0-base
    command: ["sleep", "infinity"]
    resources:
      limits:
        nvidia.com/gpu: 1
  nodeSelector:
    nvidia.com/gpu: "true"
  tolerations:
  - key: nvidia.com/gpu
    operator: Equal
    value: "true"
    effect: NoSchedule
EOF

# Check pod placement
kubectl get pod gpu-pod-test -o wide

# Verify GPU inside pod
kubectl exec -it gpu-pod-test -- nvidia-smi

# Cleanup
kubectl delete pod gpu-pod-test
```

## FFE Application GPU Configuration

The FFE Helm chart is pre-configured for GPU workloads:

```yaml
# In helm/ffe-backend/values-production.yaml
resources:
  requests:
    cpu: "1000m"
    memory: "2Gi"
    nvidia.com/gpu: 1  # Request 1 GPU
  limits:
    cpu: "4000m"
    memory: "8Gi"
    nvidia.com/gpu: 1

# Node affinity ensures scheduling on GPU nodes
affinity:
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
      - matchExpressions:
        - key: nvidia.com/gpu
          operator: In
          values: ["true"]

# Tolerate GPU taints
tolerations:
- key: nvidia.com/gpu
  operator: Equal
  value: "true"
  effect: NoSchedule

# GPU environment variables
env:
- name: NVIDIA_VISIBLE_DEVICES
  value: "all"
- name: NVIDIA_DRIVER_CAPABILITIES
  value: "compute,utility"
```

## GPU Monitoring

### Prometheus Metrics

DCGM exporter provides GPU metrics:

```bash
# Port-forward DCGM exporter
kubectl port-forward -n gpu-operator \
  svc/nvidia-dcgm-exporter 9400:9400

# Query metrics
curl http://localhost:9400/metrics | grep DCGM

# Key metrics:
# - DCGM_FI_DEV_GPU_UTIL: GPU utilization %
# - DCGM_FI_DEV_MEM_COPY_UTIL: Memory utilization %
# - DCGM_FI_DEV_GPU_TEMP: GPU temperature
# - DCGM_FI_DEV_POWER_USAGE: Power consumption
# - DCGM_FI_DEV_FB_FREE: Free framebuffer memory
```

### Grafana Dashboard

Import NVIDIA DCGM Exporter Dashboard (ID: 12239) into Grafana for visualization.

## Troubleshooting

### Driver Issues

```bash
# Check driver version mismatch
nvidia-smi
cat /proc/driver/nvidia/version

# Reinstall drivers if mismatch
sudo apt remove --purge nvidia-*
sudo ubuntu-drivers install --gpgpu
sudo reboot
```

### Containerd Runtime Issues

```bash
# Check containerd config
sudo cat /etc/containerd/config.toml | grep nvidia

# Expected:
#   [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.nvidia]

# Reconfigure if missing
sudo nvidia-ctk runtime configure --runtime=containerd
sudo systemctl restart containerd
```

### GPU Not Detected in Kubernetes

```bash
# Check device plugin logs
kubectl logs -n gpu-operator \
  -l app=nvidia-device-plugin-daemonset

# Check node labels
kubectl get nodes --show-labels | grep gpu

# Re-label if missing
kubectl label node <node-name> nvidia.com/gpu=true --overwrite
```

### Pod Cannot Allocate GPU

```bash
# Check resource availability
kubectl describe node <gpu-node-name> | grep -A 5 "Allocated resources"

# Verify pod events
kubectl describe pod <pod-name>

# Common issues:
# - Insufficient GPU resources (all GPUs allocated)
# - Missing toleration for GPU taint
# - Incorrect nodeSelector
```

## Multi-GPU Configuration

For nodes with multiple GPUs:

```yaml
# Request multiple GPUs per pod
resources:
  limits:
    nvidia.com/gpu: 2  # 2 GPUs

# Or use GPU indexing
env:
- name: NVIDIA_VISIBLE_DEVICES
  value: "0,1"  # Use GPUs 0 and 1
```

## Multi-Instance GPU (MIG)

For A100/H100 GPUs with MIG support:

```bash
# Enable MIG in Terraform
enable_mig = true

# Or manually enable
sudo nvidia-smi -mig 1

# Create MIG instances (example: 7 instances)
sudo nvidia-smi mig -cgi 9,9,9,9,9,9,9 -C

# Verify
nvidia-smi mig -lgi
```

## Security Considerations

1. **Taint GPU Nodes**: Prevents non-GPU workloads from consuming GPU resources
2. **Resource Limits**: Always set GPU limits to prevent runaway processes
3. **Namespace Quotas**: Limit GPU allocation per namespace
4. **RBAC**: Restrict GPU resource creation to authorized users

## Performance Optimization

1. **GPU Memory**: Set `gpu_memory_fraction` in Terraform to allocate partial GPU memory
2. **CUDA Streams**: Use concurrent CUDA streams in application code
3. **Batch Size**: Tune model batch size for GPU memory utilization
4. **CPU Pinning**: Use CPU affinity for GPU-bound workloads

## Cost Optimization

1. **Time-Slicing**: Enable GPU time-slicing for multiple containers per GPU
2. **MIG Partitioning**: Partition A100/H100 GPUs for workload isolation
3. **Auto-Scaling**: Scale GPU nodes based on workload demand
4. **Preemptible Pods**: Use spot/preemptible instances for batch workloads

## References

- [NVIDIA Container Toolkit Documentation](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/overview.html)
- [NVIDIA GPU Operator Documentation](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/overview.html)
- [K3s GPU Support](https://docs.k3s.io/advanced#nvidia-container-runtime-support)
- [Kubernetes Device Plugins](https://kubernetes.io/docs/concepts/extend-kubernetes/compute-storage-net/device-plugins/)
- [DCGM Exporter Metrics](https://docs.nvidia.com/datacenter/dcgm/latest/user-guide/feature-overview.html)
