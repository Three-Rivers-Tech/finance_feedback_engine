# High-Availability Terraform Environment

Production-grade multi-node deployment for Finance Feedback Engine on-premises.

## Use Cases

- **Production:** Mission-critical deployments with 99.9% uptime SLA
- **Enterprise:** Large teams, compliance requirements, disaster recovery
- **Scale testing:** Load testing with realistic multi-node architecture

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│              On-Premises Network (Private/VPN)                   │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────┐                    │
│  │         Nginx Load Balancer             │                    │
│  │  (TLS termination, 80/443)              │                    │
│  └─────────────────────────────────────────┘                    │
│       │                  │                  │                    │
│       ▼                  ▼                  ▼                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │     Kubernetes Cluster (3 Master + 2-5 Workers)         │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │                                                          │  │
│  │  Master Nodes (3):          Worker Nodes (2+):          │  │
│  │  - Control Plane            - Backend Pods              │  │
│  │  - Etcd cluster             - Prometheus/Grafana        │  │
│  │  - API Server               - Autoscaling               │  │
│  │                                                          │  │
│  │  Persistent Storage:                                    │  │
│  │  - Postgres StatefulSet (PVC)                           │  │
│  │  - NFS for backups (RWMany)                             │  │
│  │  - Local volumes (fast)                                 │  │
│  │                                                          │  │
│  │  Networking:                                            │  │
│  │  - Calico CNI plugin                                    │  │
│  │  - Service mesh (optional: Istio)                       │  │
│  │                                                          │  │
│  │  Security:                                              │  │
│  │  - Vault for secret management                          │  │
│  │  - RBAC policies                                        │  │
│  │  - Network policies                                     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─────────────────────────────────────────┐                    │
│  │      Backup & Disaster Recovery         │                    │
│  │  - Daily Postgres snapshots              │                    │
│  │  - Etcd backups                          │                    │
│  │  - Off-site replication (optional)       │                    │
│  └─────────────────────────────────────────┘                    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## Prerequisites

- **Hardware:** 5+ VMs (3 master @ 4vCPU/8GB RAM, 2+ workers @ 2vCPU/4GB RAM)
- **Storage:** 100+ GB total (Postgres replication, backups)
- **Network:** Private/VPN, consistent IPs, fast interconnect (<5ms latency)
- **OS:** Ubuntu 22.04 LTS or 24.04 LTS (all nodes)
- **Tools:** Terraform 1.5+, kubectl, Helm 3.10+

## Quick Deploy

### 1. Customize Configuration

```bash
cd terraform/environments/ha

# Edit terraform.tfvars
cp terraform.tfvars.example terraform.tfvars
# Update:
# - Master node IPs (3x)
# - Worker node IPs (2+)
# - Storage paths (NFS)
# - Network CIDR ranges
# - Domain names, ACME email
```

### 2. Initialize & Plan

```bash
terraform init

# Plan shows:
# - 3 master node provisioning
# - 2-5 worker node provisioning
# - Kubernetes cluster bootstrap
# - Postgres replication setup
# - Vault cluster init
# - DNS/firewall rules
terraform plan -out=tfplan
```

### 3. Deploy

```bash
terraform apply tfplan

# Outputs:
# - Master node IPs and kubeconfig
# - Ingress IP (for DNS)
# - Postgres primary/replica endpoints
# - Vault cluster address + unseal keys
```

### 4. Verify Cluster

```bash
export KUBECONFIG=$(terraform output -raw kubeconfig_path)

# Check all nodes ready
kubectl get nodes -o wide

# Verify HA setup
kubectl get pods -A | grep -E "(etcd|kube-apiserver)"

# Check Postgres replication
kubectl exec -n ffe postgres-0 -- psql -U ffe_user -c "SELECT client_addr, state FROM pg_stat_replication;"
```

## Configuration (terraform.tfvars)

```hcl
# Environment
environment     = "production"
cluster_name    = "ffe-prod"

# Cluster sizing (HA)
cluster_size    = "ha"
master_count    = 3
worker_count    = 3  # Can scale up later

# Versions
kubernetes_version = "v1.29"
postgres_version   = "16"
vault_version      = "1.17"

# Networking
domain_names    = ["ffe.three-rivers-tech.com", "api.ffe.three-rivers-tech.com"]
acme_email      = "cpenrod@three-rivers-tech.com"
network_cidr    = "10.0.0.0/16"

# Master nodes
master_ips      = ["10.0.1.10", "10.0.1.11", "10.0.1.12"]

# Worker nodes
worker_ips      = ["10.0.2.10", "10.0.2.11", "10.0.2.12"]

# Postgres HA
postgres_replicas    = 2
postgres_primary_ip  = "10.0.3.10"

# Vault HA
vault_ha_enabled = true
vault_cluster_ips = ["10.0.4.10", "10.0.4.11", "10.0.4.12"]

# Backup storage
backup_nfs_mount = "/mnt/backups"
backup_retention_days = 30
```

## Deployment Timeline

### Day 1: Infrastructure Provisioning (2-4 hours)

```bash
# Provision all nodes
terraform apply

# Wait for K3s initialization on all masters
# (Automated by Terraform provisioning scripts)

# Verify 3 master nodes + 2-5 workers running
kubectl get nodes
```

### Day 2: HA Configuration (1-2 hours)

```bash
# Configure Postgres replication
kubectl exec -n ffe postgres-0 -- \
  pg_basebackup -h postgres-1 -D /var/lib/postgresql/data

# Verify Etcd cluster health
kubectl exec -n kube-system etcd-master-0 -- \
  etcdctl member list

# Test failover: kill one master, verify cluster resilience
```

### Day 3: Vault & Backup Setup (2-3 hours)

```bash
# Unseal Vault cluster
vault operator unseal

# Configure Vault policies and database auth (THR-43)
vault auth enable kubernetes
vault write auth/kubernetes/config token_reviewer_jwt=<token>

# Schedule daily backups
# (Terraform should set up cron jobs)
```

### Day 4: Helm Deployment (1 hour)

```bash
# Deploy Finance Feedback Engine
helm install ffe helm/ffe-backend \
  --namespace ffe \
  --create-namespace \
  -f helm/ffe-backend/values-production.yaml

# Verify all 3 replicas running
kubectl rollout status deployment/ffe-backend -n ffe
```

## High Availability Features

### Kubernetes HA
- **3 master nodes:** Etcd cluster, control plane quorum
- **Rolling updates:** Zero downtime deployments
- **Pod disruption budgets:** Maintain minimum availability during node maintenance
- **Anti-affinity rules:** Spread pods across nodes

### Database HA
- **Postgres replication:** Primary + 2 read replicas
- **Automatic failover:** Via Patroni or cloud-native operator
- **Backup automation:** Daily snapshots with point-in-time recovery (PITR)
- **Connection pooling:** PgBouncer for efficient connections

### Monitoring & Observability
- **Prometheus:** Multi-zone scrape configs, HA setup
- **Grafana:** Persistent dashboards, alerting
- **Logging:** ELK stack (optional, refer to plans/LOGGING_MONITORING_ARCHITECTURE.md)
- **Distributed tracing:** Jaeger or OpenTelemetry collector

## Scaling (Horizontal)

### Scale Workers Up

```bash
# Add worker nodes to terraform.tfvars
# worker_count = 5

# Apply Terraform
terraform apply

# Nodes auto-join cluster
kubectl get nodes
```

### Scale Backend Replicas

```bash
# Edit Helm values
helm upgrade ffe helm/ffe-backend \
  --set replicaCount=5 \
  --namespace ffe

# Monitor rollout
kubectl rollout status deployment/ffe-backend -n ffe
```

## Disaster Recovery

### Backup

```bash
# Automated daily:
# - Postgres pg_dump to NFS
# - Etcd snapshots
# - Kubernetes secrets/configmaps

# Manual backup
terraform output -raw kubeconfig_path > backup-kubeconfig.yaml
kubectl get all -A -o yaml > backup-all-resources.yaml
```

### Recovery Point Objective (RPO)
- **Data loss tolerance:** < 1 hour (daily backups)
- **Can improve to:** < 15 minutes (continuous replication)

### Recovery Time Objective (RTO)
- **Master node down:** < 10 minutes (auto-failover)
- **Worker node down:** < 2 minutes (pod rescheduling)
- **Full cluster down:** < 1 hour (restore from backups)

## Cost Analysis

**Hardware (on-prem):**
- 3 master nodes: $3k (amortized)
- 3 worker nodes: $2k
- Storage (NFS, backups): $500
- **Total:** ~$50/month (amortized over 5 years) vs. $1500+/month managed K8s

## Monitoring & Alerting

```bash
# Critical metrics to monitor:
# - Master node health (Etcd health, API latency)
# - Worker node capacity (CPU, memory, disk)
# - Postgres replication lag
# - Ingress TLS cert expiration (alert 30 days before)
# - Backup success/failure rate

# Set up alerts in Prometheus/Grafana (see monitoring architecture)
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Master node down | K8s auto-elects new leader, verify with `kubectl get nodes` |
| Postgres failover stuck | Check `SELECT * FROM pg_stat_replication;`, verify network |
| Ingress not routing | Check `kubectl get ingress`, verify cert-manager status |
| Vault unsealing failed | Retrieve unseal keys from Terraform state (encrypted) |
| Network latency > 100ms | Check inter-node network, consider dedicated cluster network |

## Next Steps

1. Customize `terraform.tfvars` for your infrastructure
2. Run `terraform plan` and review output
3. Deploy with `terraform apply`
4. Follow HA-specific post-deployment checklist
5. Set up backup automation and DR tests
6. Monitor with observability stack (plans/LOGGING_MONITORING_ARCHITECTURE.md)

## Support

- Linear tickets: THR-39, THR-41, THR-42, THR-43
- Docs: DEPLOYMENT_READINESS_ASSESSMENT.md, GRADUATION_PATH.md
- Runbook: TERRAFORM_HELM_QUICKSTART.md (in progress)

