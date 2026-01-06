# Terraform + Helm Deployment Quick Start

## Overview

Deploy the Finance Feedback Engine to on-premises Kubernetes (K3s) with full GPU support for AI/ML workloads.

## Prerequisites

- Ubuntu 22.04/24.04 server with NVIDIA GPU (RTX 30/40, A100, H100)
- Terraform >= 1.5.0
- SSH access to server
- Domain name (optional, for TLS)

## Quick Deploy (Single-Node with GPU)

### 1. Clone and Configure

```bash
git clone https://github.com/Three-Rivers-Tech/finance_feedback_engine.git
cd finance_feedback_engine/terraform/environments/single-node

# Copy example config
cp terraform.tfvars.example terraform.tfvars

# Edit configuration
nano terraform.tfvars
```

### 2. Required Configuration

Edit `terraform.tfvars`:

```hcl
# Your server IP
master_ip = "192.168.1.100"

# GPU nodes (same as master for single-node)
gpu_node_ips = ["192.168.1.100"]

# Domain names (or use IP)
domain_names = [
  "ffe.yourdomain.com",
  "api.ffe.yourdomain.com"
]

ingress_ip = "192.168.1.100"

# ACME email for Let's Encrypt
acme_email = "your-email@example.com"

# Database password
postgres_password = "secure-password-here"
```

### 3. Deploy Infrastructure

```bash
# Initialize Terraform
terraform init

# Review plan
terraform plan

# Deploy (takes 10-15 minutes)
terraform apply -auto-approve
```

This will:
- Install NVIDIA drivers (version 545)
- Bootstrap K3s cluster with GPU support
- Deploy NVIDIA GPU Operator
- Install cert-manager for TLS
- Deploy Nginx ingress
- Deploy PostgreSQL database
- Deploy FFE application with GPU allocation
- Configure Vault for secrets

### 4. Verify Deployment

```bash
# Set kubeconfig
export KUBECONFIG=../../modules/compute/kubeconfig.yaml

# Check cluster
kubectl get nodes -o wide

# Verify GPU detection
kubectl get nodes -o custom-columns=\
NAME:.metadata.name,\
GPU:.status.allocatable."nvidia\.com/gpu"

# Test GPU allocation
kubectl run gpu-test --rm -it \
  --image=nvidia/cuda:12.0-base \
  --restart=Never \
  -- nvidia-smi

# Check FFE application
kubectl get pods -n ffe -o wide
kubectl logs -n ffe -l app=ffe-backend

# Check GPU operator
kubectl get pods -n gpu-operator
```

### 5. Access Application

```bash
# Get ingress IP
kubectl get svc -n ingress-nginx

# Access via domain (if DNS configured)
https://ffe.yourdomain.com

# Or port-forward for local access
kubectl port-forward -n ffe svc/ffe-backend 8000:8000
# Then: http://localhost:8000
```

## Configuration Details

### GPU Configuration

The default configuration requests 1 GPU per FFE pod:

```yaml
resources:
  requests:
    nvidia.com/gpu: 1
  limits:
    nvidia.com/gpu: 1
```

To adjust GPU allocation, edit `terraform/environments/single-node/main.tf`:

```hcl
# In helm_release.ffe_backend values:
resources = {
  requests = {
    "nvidia.com/gpu" = 2  # Request 2 GPUs
  }
  limits = {
    "nvidia.com/gpu" = 2
  }
}
```

### Scaling

Single-node deployment runs 1 replica by default. To scale:

```bash
# Edit values in Helm chart
kubectl edit deployment -n ffe ffe-backend

# Or use Helm upgrade
helm upgrade ffe-backend ../../helm/ffe-backend \
  -n ffe \
  --set replicaCount=3
```

For HA deployment with multiple GPU nodes, see `terraform/environments/ha/`.

### Storage

Default storage classes:
- `fast-ssd`: SSD storage for database and critical data
- `standard`: HDD storage for logs and backups
- `backup`: NFS storage for backups (optional)

To change storage class:

```hcl
# In terraform.tfvars
postgres_storage_class = "fast-ssd"
vault_storage_class = "fast-ssd"
```

### Vault Setup

Initialize Vault after deployment:

```bash
# Get init guide
kubectl get configmap -n ffe vault-init-guide -o yaml

# Initialize Vault
kubectl exec -n ffe vault-0 -- vault operator init

# Save unseal keys and root token securely!

# Unseal Vault (3 times with different keys)
kubectl exec -n ffe vault-0 -- vault operator unseal <key1>
kubectl exec -n ffe vault-0 -- vault operator unseal <key2>
kubectl exec -n ffe vault-0 -- vault operator unseal <key3>

# Enable Kubernetes auth
kubectl exec -n ffe vault-0 -- sh /vault/init/init-script.sh
```

## Troubleshooting

### GPU Not Detected

```bash
# Check GPU on node
ssh ubuntu@192.168.1.100 "lspci | grep -i nvidia"

# Check drivers
ssh ubuntu@192.168.1.100 "nvidia-smi"

# Check device plugin logs
kubectl logs -n gpu-operator -l app=nvidia-device-plugin-daemonset
```

### Pod Not Scheduling

```bash
# Check events
kubectl describe pod -n ffe <pod-name>

# Common issues:
# - Insufficient GPU resources: Check with kubectl describe node
# - Missing toleration: Verify pod has nvidia.com/gpu toleration
# - Image pull errors: Check registry credentials
```

### Database Connection Issues

```bash
# Check Postgres status
kubectl get pods -n ffe -l app.kubernetes.io/name=postgresql

# Check logs
kubectl logs -n ffe postgres-postgresql-0

# Test connection
kubectl exec -it -n ffe postgres-postgresql-0 -- \
  psql -U ffe -d ffe -c "SELECT version();"
```

### Certificate Issues

```bash
# Check cert-manager
kubectl get pods -n cert-manager

# Check certificate status
kubectl get certificate -n ffe

# Check ClusterIssuer
kubectl describe clusterissuer letsencrypt-prod
```

## Performance Tuning

### GPU Utilization

Monitor GPU usage:

```bash
# Port-forward DCGM exporter
kubectl port-forward -n gpu-operator \
  svc/nvidia-dcgm-exporter 9400:9400

# Query metrics
curl http://localhost:9400/metrics | grep DCGM_FI_DEV_GPU_UTIL
```

Optimize GPU usage:
1. Increase batch size in application config
2. Enable GPU time-slicing for multiple containers per GPU
3. Use MIG for A100/H100 GPUs

### Database Performance

```bash
# Monitor connections
kubectl exec -it -n ffe postgres-postgresql-0 -- \
  psql -U ffe -d ffe -c "SELECT count(*) FROM pg_stat_activity;"

# Tune resources in terraform.tfvars
postgres_resources = {
  requests = {
    cpu    = "2000m"
    memory = "4Gi"
  }
}
```

## Backup and Recovery

### Database Backup

```bash
# Manual backup
kubectl exec -n ffe postgres-postgresql-0 -- \
  pg_dump -U ffe ffe > backup.sql

# Restore
kubectl exec -i -n ffe postgres-postgresql-0 -- \
  psql -U ffe ffe < backup.sql
```

Automated backups configured in storage module (daily at 2 AM, 30-day retention).

### Vault Backup

```bash
# Backup Vault data
kubectl exec -n ffe vault-0 -- \
  vault operator raft snapshot save /tmp/vault-backup.snap

kubectl cp ffe/vault-0:/tmp/vault-backup.snap ./vault-backup.snap
```

## Cleanup

```bash
# Destroy infrastructure
cd terraform/environments/single-node
terraform destroy -auto-approve

# Manual cleanup (if needed)
ssh ubuntu@192.168.1.100 "/usr/local/bin/k3s-uninstall.sh"
```

## Next Steps

- [GPU Setup Guide](../../docs/GPU_SETUP_GUIDE.md) - Detailed GPU configuration
- [Helm Chart Documentation](../../helm/ffe-backend/README.md) - Chart customization
- [Terraform Module Reference](../../terraform/README.md) - Module details
- [API Documentation](../../docs/API.md) - Application API reference

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Kubernetes Cluster (K3s)                          │
│                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │ Nginx       │  │ Cert-Manager│  │ GPU        │ │
│  │ Ingress     │  │ (TLS)       │  │ Operator   │ │
│  └─────────────┘  └─────────────┘  └────────────┘ │
│                                                      │
│  ┌─────────────────────────────────────────────┐   │
│  │ FFE Backend (FastAPI)                       │   │
│  │ - GPU: 1x NVIDIA (nvidia.com/gpu: 1)       │   │
│  │ - CPU: 4 cores                              │   │
│  │ - Memory: 8 GB                              │   │
│  │ - Node Affinity: nvidia.com/gpu=true       │   │
│  └─────────────────────────────────────────────┘   │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐                │
│  │ PostgreSQL   │  │ Vault        │                │
│  │ (16)         │  │ (1.17)       │                │
│  └──────────────┘  └──────────────┘                │
└─────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│  Storage Layer                                      │
│  - fast-ssd: Database, Vault                        │
│  - standard: Logs, cache                            │
│  - backup: Automated backups (NFS)                  │
└─────────────────────────────────────────────────────┘
```

## Support

- Issues: [GitHub Issues](https://github.com/Three-Rivers-Tech/finance_feedback_engine/issues)
- Docs: [Documentation Index](../../docs/README.md)
- Linear: THR-39 (Terraform), THR-40 (Helm), THR-42 (TLS)
