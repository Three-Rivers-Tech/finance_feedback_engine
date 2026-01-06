# Terraform Infrastructure for Finance Feedback Engine

On-premises deployment automation for Finance Feedback Engine 2.0.

## Directory Structure

```
terraform/
├── main.tf              # Root configuration (providers, backends)
├── variables.tf         # Root input variables
├── outputs.tf           # Root outputs
├── README.md            # This file
│
├── modules/
│   ├── networking/      # VPC, firewall, security groups, DNS
│   ├── compute/         # Ubuntu hosts, K3s/Kubernetes cluster nodes
│   ├── storage/         # NFS, block storage for Postgres, backups
│   └── vault/           # HashiCorp Vault bootstrap and initialization
│
└── environments/
    ├── single-node/     # Single-node production (dev/staging)
    │   ├── terraform.tfvars
    │   ├── backend.tf
    │   └── main.tf      # Environment-specific root module
    │
    └── ha/              # High-availability multi-node (production)
        ├── terraform.tfvars
        ├── backend.tf
        └── main.tf      # Environment-specific root module
```

## Quick Start

### Prerequisites
- Terraform >= 1.5.0
- On-prem infrastructure (bare metal or proxmox VMs)
- Ubuntu 22.04 or 24.04
- Ansible (optional, for additional provisioning)

### Deploy Single-Node (Dev/Staging)

```bash
cd terraform/environments/single-node

# Initialize Terraform (downloads providers, configures backend)
terraform init

# Plan the deployment
terraform plan -out=tfplan

# Apply the plan
terraform apply tfplan

# Outputs will show:
# - Master node IP
# - Ingress IP (Nginx LB)
# - Vault unseal keys (SAVE SECURELY!)
# - Initial admin credentials
```

### Deploy HA (Production)

```bash
cd terraform/environments/ha

terraform init
terraform plan -out=tfplan
terraform apply tfplan

# Outputs will show:
# - Master node IPs (3x for HA)
# - Worker node IPs (2-5x for scalability)
# - Ingress IP (Nginx LB)
# - Vault cluster endpoints
```

## Module Descriptions

### networking/
- VPC/network configuration
- Firewall rules (UFW or iptables)
- DNS records for `ffe.three-rivers-tech.com` and `api.ffe.three-rivers-tech.com`
- Load balancer endpoints (ports 80, 443)

**Outputs:**
- `network_id`, `firewall_rules`, `dns_records`

### compute/
- Ubuntu VM provisioning (single-node or HA cluster)
- K3s or native Kubernetes cluster setup
- SSH key pair creation
- Security group/firewall attachment

**Outputs:**
- `master_ips`, `worker_ips`, `ingress_ip`, `ssh_key_path`

### storage/
- Persistent volume provisioning (Postgres data, backups)
- Block storage or NFS configuration
- Snapshot/backup automation setup

**Outputs:**
- `postgres_volume_id`, `backup_volume_id`, `storage_class_name`

### vault/
- Vault cluster bootstrap (if on-prem Vault required)
- Namespace and path initialization (`secret/<env>/app/*`, `database/<env>/ffe`, etc.)
- Authentication method setup (Kubernetes auth)
- Policy and role creation

**Outputs:**
- `vault_addr`, `vault_unseal_keys`, `vault_root_token`

## Environment-Specific Variables

Each environment directory has a `terraform.tfvars` with:

```hcl
# Single-node example
environment           = "staging"
cluster_size          = "single-node"
node_count            = 1
kubernetes_version    = "v1.29"
postgres_version      = "16"
vault_version         = "1.17"
acme_email            = "cpenrod@three-rivers-tech.com"
domain_names          = ["ffe.three-rivers-tech.com", "api.ffe.three-rivers-tech.com"]
```

## State Management

Terraform state is stored in a remote backend (S3 or local for on-prem):

```hcl
# backend.tf
terraform {
  backend "local" {
    path = "terraform.tfstate"
  }
}
```

**⚠️ CRITICAL:** Back up `terraform.tfstate` and `terraform.tfstate.backup` regularly!

## Deployment Flow

1. **Plan phase:** `terraform plan` validates configuration without making changes
2. **Apply phase:** `terraform apply` provisions infrastructure
3. **Output phase:** Display IP addresses, credentials, connection strings
4. **Manual steps:** Configure Vault unsealing, DNS updates (if manual), Helm deploy

## Rollback & Disaster Recovery

### Rollback to previous state
```bash
# List previous state versions
terraform state list

# Restore from backup (if available)
cp terraform.tfstate.backup terraform.tfstate
terraform refresh
```

### Full cluster re-provisioning
```bash
# Destroy all resources
terraform destroy

# Re-apply
terraform apply
```

## Common Issues

| Issue | Solution |
|-------|----------|
| "Provider not found" | Run `terraform init` in environment directory |
| "Invalid backend" | Check `backend.tf` path and permissions |
| "Variable not defined" | Ensure `terraform.tfvars` has all required vars |
| "Network conflict" | Check IP ranges don't overlap with existing networks |
| "Vault unsealing failed" | Retrieve unseal keys from Terraform output |

## Next Steps

1. Customize `environments/single-node/terraform.tfvars` for your infrastructure
2. Run `terraform plan` to validate configuration
3. Deploy with `terraform apply`
4. Follow Helm deployment guide in [../helm/README.md](../helm/README.md)
5. Configure Vault paths as per [Vault layout ticket (THR-43)](https://linear.app/grant-street/issue/THR-43)

## Support

- Issues: File Linear tickets (THR-39, THR-41, THR-43)
- Docs: See [DEPLOYMENT_READINESS_ASSESSMENT.md](../../DEPLOYMENT_READINESS_ASSESSMENT.md)
- Runbooks: Refer to [docs/TERRAFORM_HELM_QUICKSTART.md](../../docs/TERRAFORM_HELM_QUICKSTART.md) (in progress)

