# Helm Charts for Finance Feedback Engine

Production-ready Helm charts for deploying Finance Feedback Engine 2.0 on Kubernetes/K3s.

## Charts

### ffe-backend
Main application deployment chart for the Finance Feedback Engine backend.

**Features:**
- FastAPI backend deployment (rolling updates)
- PostgreSQL dependency (bundled or external DSN)
- Nginx ingress with TLS (cert-manager integration)
- Vault Secret injection for sensitive values
- Health checks (liveness, readiness probes)
- Resource limits and requests
- Multi-environment support (dev, staging, production)

## Directory Structure

```
helm/
└── ffe-backend/
    ├── Chart.yaml              # Chart metadata
    ├── values.yaml             # Default values
    ├── values-dev.yaml         # Development overrides
    ├── values-staging.yaml     # Staging overrides
    ├── values-production.yaml  # Production overrides
    ├── README.md               # Chart documentation
    ├── templates/
    │   ├── deployment.yaml     # Backend pod deployment
    │   ├── service.yaml        # Kubernetes Service
    │   ├── ingress.yaml        # Nginx ingress (TLS via cert-manager)
    │   ├── configmap.yaml      # ConfigMap for non-secret config
    │   ├── secret.yaml         # Kubernetes Secret template
    │   ├── _helpers.tpl        # Template helpers
    │   └── NOTES.txt           # Post-install instructions
    │
    └── charts/                 # Subchart dependencies (optional)
        └── postgresql/         # If bundling PostgreSQL Helm chart
```

## Quick Start

### Prerequisites
- Kubernetes or K3s cluster (1.25+)
- Helm 3.10+
- cert-manager (installed and configured)
- Vault (if using Secret injection)

### Install Chart

```bash
# Validate chart syntax
helm lint helm/ffe-backend

# Install in default namespace
helm install ffe helm/ffe-backend \
  --namespace ffe \
  --create-namespace \
  -f helm/ffe-backend/values-production.yaml

# Wait for rollout
kubectl rollout status deployment/ffe-backend -n ffe

# Verify installation
kubectl get all -n ffe
```

### Upgrade Chart

```bash
helm upgrade ffe helm/ffe-backend \
  --namespace ffe \
  -f helm/ffe-backend/values-production.yaml

# Monitor rollout
kubectl rollout status deployment/ffe-backend -n ffe --watch
```

### Uninstall Chart

```bash
helm uninstall ffe --namespace ffe

# Clean up namespace (optional)
kubectl delete namespace ffe
```

## Configuration

### Environment-Specific Values

Each environment has a dedicated values file:

**values-dev.yaml:**
- Replicas: 1
- CPU/Memory: low limits (dev machines)
- Image pull policy: IfNotPresent (local images)
- Debug logging enabled

**values-staging.yaml:**
- Replicas: 2
- CPU/Memory: medium limits
- Image pull policy: Always (pull fresh images)
- Health check timeouts: relaxed
- Persistence: enabled

**values-production.yaml:**
- Replicas: 3+
- CPU/Memory: strict limits
- Image pull policy: Always
- Health checks: strict timeouts
- Persistence: enabled, high availability
- Pod disruption budgets: enabled
- Autoscaling: enabled

### Key Helm Values

```yaml
# Image configuration
image:
  repository: finance-feedback-engine
  tag: latest
  pullPolicy: Always

# Replica count (deployment)
replicaCount: 3

# Service configuration
service:
  type: ClusterIP
  port: 8000

# Ingress configuration (TLS via cert-manager)
ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: ffe.three-rivers-tech.com
      paths:
        - path: /
          pathType: Prefix
    - host: api.ffe.three-rivers-tech.com
      paths:
        - path: /api
          pathType: Prefix
  tls:
    - secretName: ffe-tls
      hosts:
        - ffe.three-rivers-tech.com
        - api.ffe.three-rivers-tech.com

# Resources (requests and limits)
resources:
  requests:
    cpu: 250m
    memory: 512Mi
  limits:
    cpu: 1000m
    memory: 2Gi

# Health probes
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /ready
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5

# Vault Secret injection (optional)
vault:
  enabled: true
  role: ffe-backend
  path: secret/data/production/app
```

## cert-manager Integration

The chart creates a TLS secret managed by cert-manager with ACME (Let's Encrypt).

**Prerequisites:**
1. cert-manager installed: `helm install cert-manager oci://quay.io/jetstack/charts/cert-manager --version v1.19.2 --namespace cert-manager --create-namespace --set crds.enabled=true`
2. ClusterIssuer configured (in Terraform or manually)

**ClusterIssuer Example:**
```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: cpenrod@three-rivers-tech.com
    privateKeySecretRef:
      name: letsencrypt-prod-key
    solvers:
      - http01:
          ingress:
            class: nginx
```

## Vault Secret Injection

The chart uses Vault Agent Injector to dynamically inject secrets into pods.

**Prerequisites:**
1. Vault installed and unsealed
2. Kubernetes auth method configured
3. Vault policies and roles created (THR-43)

**Vault Secret Paths (by environment):**
```
secret/dev/app/*
secret/staging/app/*
secret/production/app/*
database/dev/ffe
database/staging/ffe
database/production/ffe
```

## Troubleshooting

### Chart validation fails
```bash
helm lint helm/ffe-backend
# Fix any YAML errors in templates/
```

### Pod fails to start
```bash
kubectl describe pod <pod-name> -n ffe
kubectl logs <pod-name> -n ffe
```

### TLS certificate not issued
```bash
# Check cert-manager logs
kubectl logs -n cert-manager deployment/cert-manager

# Check Certificate status
kubectl get certificate -n ffe
kubectl describe certificate ffe-tls -n ffe
```

### Vault injection not working
```bash
# Check Vault Agent Injector logs
kubectl logs -n vault -l app.kubernetes.io/name=vault-agent-injector

# Verify Kubernetes auth is configured
vault auth list
```

## Advanced Topics

### Horizontal Pod Autoscaling (HPA)

```bash
# Enable in values.yaml
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 80
```

### Pod Disruption Budget (PDB)

```bash
# Ensure minimum availability during cluster updates
podDisruptionBudget:
  enabled: true
  minAvailable: 1
```

### Rolling Update Strategy

```yaml
# Default in Helm (already configured)
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1
    maxUnavailable: 0  # Zero downtime
```

## Next Steps

1. Create `templates/` files (deployment, service, ingress, etc.)
2. Define environment-specific values files
3. Test with `helm lint` and `helm template`
4. Deploy to staging cluster
5. Integrate into GitHub Actions CI/CD (THR-41)
6. Configure Vault Secret injection (THR-43)

## Support

- Issues: File Linear tickets (THR-40, THR-42, THR-43)
- Docs: See [helm/ffe-backend/README.md](ffe-backend/README.md) (in progress)
- Kubernetes: https://kubernetes.io/docs/
- Helm: https://helm.sh/docs/
- cert-manager: https://cert-manager.io/docs/

