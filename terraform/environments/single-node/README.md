# Single-Node Terraform Environment

Development and staging deployment for Finance Feedback Engine on a single Ubuntu host.

## Use Cases

- **Development:** Local testing with full Kubernetes cluster on a single VM
- **Staging:** Integration testing before production rollout
- **Small deployments:** Cost-effective alternative for teams or POCs

## Architecture

```
┌─────────────────────────────────────────┐
│       Ubuntu 22.04/24.04 Host           │
├─────────────────────────────────────────┤
│                                         │
│  ┌─────────────────────────────────┐   │
│  │   K3s Kubernetes Cluster        │   │
│  │   (Master + Agent on same node) │   │
│  ├─────────────────────────────────┤   │
│  │  Backend Pod (FastAPI)          │   │
│  │  Postgres StatefulSet           │   │
│  │  Nginx Ingress Controller       │   │
│  │  cert-manager                   │   │
│  │  Vault Agent (optional)         │   │
│  └─────────────────────────────────┘   │
│                                         │
│  Persistent Volumes:                    │
│  - Postgres data (/var/lib/postgres)    │
│  - Backups (/backups)                   │
│  - Logs (/var/log/ffe)                  │
│                                         │
└─────────────────────────────────────────┘
```

## Prerequisites

- **Hardware:** 2+ vCPU, 4+ GB RAM, 20+ GB disk
- **OS:** Ubuntu 22.04 LTS or 24.04 LTS
- **Network:** Public or private IP reachable from deployment machine
- **Tools:** SSH key pair, Terraform 1.5+, kubectl 1.25+

## Quick Deploy

### 1. Initialize Terraform

```bash
cd terraform/environments/single-node

# Copy and customize terraform.tfvars
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your infrastructure details

# Initialize backend and download providers
terraform init
```

### 2. Plan Deployment

```bash
terraform plan -out=tfplan

# Review the plan:
# - Ubuntu host(s) to provision
# - K3s cluster initialization
# - Vault bootstrap (if enabled)
# - DNS records (if DNS module enabled)
```

### 3. Apply Deployment

```bash
terraform apply tfplan

# Outputs will show:
# - Master node IP
# - Ingress IP (for DNS pointing)
# - Kubeconfig path
# - Vault unseal keys (if Vault enabled)
```

### 4. Verify Cluster

```bash
# Set kubeconfig
export KUBECONFIG=$(terraform output -raw kubeconfig_path)

# Check cluster status
kubectl cluster-info
kubectl get nodes
kubectl get pods -A
```

## Configuration (terraform.tfvars)

```hcl
# Environment
environment    = "staging"
cluster_name   = "ffe-staging"

# Cluster sizing
cluster_size   = "single-node"
node_count     = 1

# Versions
kubernetes_version = "v1.29"
postgres_version   = "16"
vault_version      = "1.17"

# Networking
domain_names   = ["ffe.three-rivers-tech.com", "api.ffe.three-rivers-tech.com"]
acme_email     = "cpenrod@three-rivers-tech.com"

# SSL/TLS
enable_tls     = true
cert_issuer    = "letsencrypt-prod"

# Vault
enable_vault   = true
vault_unseal_keys_file = "vault-unseal-keys.txt"

# Infrastructure
ubuntu_version = "22.04"
host_ip        = "192.168.1.100"  # Or IP address of target VM
ssh_key_path   = "~/.ssh/id_rsa"
```

## Deployment Workflow

### Day 1: Infrastructure Provisioning

```bash
# 1. Provision Ubuntu host
terraform apply

# 2. Wait for K3s to initialize (~5 minutes)
terraform output -raw kubeconfig_path

# 3. Verify cluster readiness
kubectl wait --for=condition=Ready node --all --timeout=5m
```

### Day 2: Install cert-manager & Vault

```bash
# 1. Install cert-manager
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --set installCRDs=true

# 2. Unseal Vault (if using Terraform vault module)
export VAULT_ADDR="http://<vault-ip>:8200"
vault operator unseal < vault-unseal-keys.txt

# 3. Configure Vault policies and roles (see THR-43)
```

### Day 3: Deploy Finance Feedback Engine

```bash
# Deploy via Helm (see helm/README.md)
helm install ffe helm/ffe-backend \
  --namespace ffe \
  --create-namespace \
  -f helm/ffe-backend/values-staging.yaml
```

## Scaling

To upgrade from single-node to HA:

```bash
# 1. Backup state
cp terraform.tfstate terraform.tfstate.backup

# 2. Destroy single-node
terraform destroy

# 3. Switch to HA environment
cd ../ha

# 4. Deploy HA cluster
terraform apply
```

## Monitoring

```bash
# Health check
kubectl get componentstatuses

# Pod status
kubectl get pods -n ffe

# Ingress status
kubectl get ingress -n ffe
kubectl describe ingress -n ffe

# Cert-manager status
kubectl get certificate -n ffe
kubectl describe certificate ffe-tls -n ffe

# Logs
kubectl logs -n ffe deployment/ffe-backend
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| K3s failed to start | SSH to host, check `systemctl status k3s` |
| Pods stuck in pending | `kubectl describe pod <name>`, check resource limits |
| TLS cert not issuing | Check cert-manager logs, ensure DNS is resolvable |
| Database connection failed | Verify Postgres password in Vault, check network policies |

## Backup & Restore

### Backup Cluster State

```bash
# Backup Terraform state
aws s3 cp terraform.tfstate s3://ffe-backups/terraform/

# Backup Etcd (Kubernetes state)
kubectl get secrets -A -o yaml > etcd-backup.yaml

# Backup database
kubectl exec -n ffe postgres-0 -- \
  pg_dump -U ffe_user ffe > postgres-backup.sql
```

### Restore from Backup

```bash
# Restore Terraform state
aws s3 cp s3://ffe-backups/terraform/terraform.tfstate .
terraform refresh

# Restore Kubernetes secrets
kubectl apply -f etcd-backup.yaml

# Restore database
kubectl exec -n ffe postgres-0 -- \
  psql -U ffe_user ffe < postgres-backup.sql
```

## Cost Optimization

**Single-node cost reduction:**
- 1 small VM (2vCPU, 4GB RAM) vs. 3x nodes in HA
- Local storage instead of managed block storage
- No managed Kubernetes service fees

**Estimated cost:** $10-20/month on-prem hardware (electricity, cooling)

## Next Steps

1. Customize `terraform.tfvars` for your infrastructure
2. Run `terraform plan` to validate
3. Deploy with `terraform apply`
4. Follow post-deployment checklist in Runbook (THR-41)
5. Proceed to Helm deployment (helm/README.md)

## Support

- Linear tickets: THR-39, THR-41, THR-43
- Docs: DEPLOYMENT_READINESS_ASSESSMENT.md
- Runbook: TERRAFORM_HELM_QUICKSTART.md (in progress)

