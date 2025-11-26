# CloudNativePG with External Secrets Operator - FluxCD Example

This example demonstrates deploying CloudNativePG (CNCF PostgreSQL Operator) using FluxCD with External Secrets Operator for secrets management.

## Prerequisites

- Kubernetes cluster with kubectl access
- FluxCD installed (`flux install` or `flux bootstrap`)
- External Secrets Operator installed
- External secret backend configured (Vault, AWS Secrets Manager, GCP Secret Manager, or Azure Key Vault)

## Architecture

```
┌─────────────────┐
│  External       │
│  Backend        │
│  (Vault/AWS/    │
│   GCP/Azure)    │
└────────┬────────┘
         │
         │ ESO syncs secrets
         ▼
┌─────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│ SecretStore     │──┬──▶│ ExternalSecret   │─────▶│ K8s Secret       │
│ (connection)    │  │   │ (what to sync)   │      │ (postgresql-     │
└─────────────────┘  │   └──────────────────┘      │  secrets)        │
                     │                               └─────────┬────────┘
                     │                                         │
                     │   ┌──────────────────┐                 │
                     └──▶│ HelmRelease      │◀────────────────┘
                         │ (PostgreSQL)     │  references secret
                         └──────────────────┘
```

## Files

- `namespace.yaml` - Creates the databases namespace
- `helmrepository.yaml` - CloudNativePG Helm repository
- `secretstore.yaml` - Connects to external secret backend (Vault/AWS/GCP/Azure)
- `externalsecret.yaml` - Defines which secrets to sync
- `helmrelease.yaml` - PostgreSQL HelmRelease referencing the secret
- `kustomization.yaml` - Kustomize configuration

## Installation

### Step 1: Install External Secrets Operator

```bash
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets \
  --namespace external-secrets \
  --create-namespace
```

### Step 2: Configure Secret Backend

Choose your backend and follow the appropriate guide:

**For Vault:**
```bash
# Enable Kubernetes auth in Vault
vault auth enable kubernetes

# Configure Vault to talk to Kubernetes
vault write auth/kubernetes/config \
  kubernetes_host="https://$KUBERNETES_SERVICE_HOST:$KUBERNETES_SERVICE_PORT"

# Create policy
vault policy write external-secrets - <<EOF
path "secret/data/database/*" {
  capabilities = ["read"]
}
EOF

# Create role
vault write auth/kubernetes/role/external-secrets \
  bound_service_account_names=external-secrets-sa \
  bound_service_account_namespaces=databases \
  policies=external-secrets \
  ttl=24h
```

**For AWS Secrets Manager (with IRSA):**
```bash
# Create IAM policy
aws iam create-policy \
  --policy-name ExternalSecretsPolicy \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:*:*:secret:database/*"
    }]
  }'

# Associate IAM role with Kubernetes service account
eksctl create iamserviceaccount \
  --name external-secrets-sa \
  --namespace databases \
  --cluster my-cluster \
  --attach-policy-arn arn:aws:iam::ACCOUNT_ID:policy/ExternalSecretsPolicy \
  --approve
```

**For GCP Secret Manager (with Workload Identity):**
```bash
# Create service account
gcloud iam service-accounts create external-secrets-sa

# Grant permissions
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:external-secrets-sa@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Bind Kubernetes SA to GCP SA
gcloud iam service-accounts add-iam-policy-binding \
  external-secrets-sa@PROJECT_ID.iam.gserviceaccount.com \
  --role roles/iam.workloadIdentityUser \
  --member "serviceAccount:PROJECT_ID.svc.id.goog[databases/external-secrets-sa]"
```

### Step 3: Store Secrets in Backend

**For Vault:**
```bash
vault kv put secret/database/postgresql \
  admin-password="$(openssl rand -base64 32)" \
  user-password="$(openssl rand -base64 32)"
```

**For AWS Secrets Manager:**
```bash
aws secretsmanager create-secret \
  --name database/postgresql \
  --secret-string "{\"admin-password\":\"$(openssl rand -base64 32)\",\"user-password\":\"$(openssl rand -base64 32)\"}"
```

**For GCP Secret Manager:**
```bash
echo -n "$(openssl rand -base64 32)" | gcloud secrets create database-postgresql-admin-password --data-file=-
echo -n "$(openssl rand -base64 32)" | gcloud secrets create database-postgresql-user-password --data-file=-
```

### Step 4: Update SecretStore Configuration

Edit `secretstore.yaml` to match your backend configuration:
- Update server URL, project ID, region, etc.
- Uncomment the appropriate backend section (Vault, AWS, GCP, or Azure)

### Step 5: Update ExternalSecret Configuration

If using GCP Secret Manager, update `externalsecret.yaml` to reference individual secrets:

```yaml
data:
  - secretKey: postgres-password
    remoteRef:
      key: database-postgresql-admin-password  # GCP secret name

  - secretKey: password
    remoteRef:
      key: database-postgresql-user-password   # GCP secret name
```

### Step 6: Deploy

```bash
kubectl apply -k .
```

Or with Flux:

```bash
flux create kustomization postgresql \
  --source=GitRepository/flux-system \
  --path="./examples/fluxcd/postgresql-eso" \
  --prune=true \
  --interval=10m
```

## Verification

### Check ExternalSecret Status

```bash
# View ExternalSecret
kubectl get externalsecret -n databases

# Describe for detailed status
kubectl describe externalsecret postgresql-secrets -n databases
```

Expected output:
```
Status:
  Conditions:
    Status:  True
    Type:    Ready
  Refresh Time:  2024-01-15T10:00:00Z
  Synced Resource Version:  1-abc123
```

### Check Kubernetes Secret

```bash
# Verify secret was created
kubectl get secret postgresql-secrets -n databases

# View secret keys (not values)
kubectl get secret postgresql-secrets -n databases -o jsonpath='{.data}' | jq 'keys'
```

Expected output:
```
[
  "password",
  "postgres-password"
]
```

### Check HelmRelease Status

```bash
# FluxCD status
flux get helmreleases -n databases

# Detailed status
kubectl describe helmrelease postgresql -n databases
```

### Check PostgreSQL Pods

```bash
# View pods
kubectl get pods -n databases

# Check logs
kubectl logs -n databases -l app.kubernetes.io/name=postgresql --tail=50
```

### Test Database Connection

```bash
# Port-forward to PostgreSQL
kubectl port-forward -n databases svc/postgresql 5432:5432 &

# Get password from secret
POSTGRES_PASSWORD=$(kubectl get secret postgresql-secrets -n databases -o jsonpath='{.data.postgres-password}' | base64 -d)
USER_PASSWORD=$(kubectl get secret postgresql-secrets -n databases -o jsonpath='{.data.password}' | base64 -d)

# Connect as admin
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -U postgres

# Connect as app user
PGPASSWORD=$USER_PASSWORD psql -h localhost -U appuser -d appdb
```

## Secret Rotation

### Step 1: Update Secret in Backend

**Vault:**
```bash
vault kv put secret/database/postgresql \
  admin-password="$(openssl rand -base64 32)" \
  user-password="$(openssl rand -base64 32)"
```

**AWS Secrets Manager:**
```bash
aws secretsmanager update-secret \
  --secret-id database/postgresql \
  --secret-string "{\"admin-password\":\"$(openssl rand -base64 32)\",\"user-password\":\"$(openssl rand -base64 32)\"}"
```

### Step 2: Wait for ESO to Sync

ESO will automatically sync based on `refreshInterval` (default: 1h in this example).

Force immediate sync:
```bash
kubectl annotate externalsecret postgresql-secrets \
  -n databases \
  force-sync="$(date +%s)" \
  --overwrite
```

### Step 3: Restart PostgreSQL

```bash
kubectl rollout restart statefulset/postgresql -n databases
```

Or install [Reloader](https://github.com/stakater/Reloader) for automatic restarts:

```bash
helm repo add stakater https://stakater.github.io/stakater-charts
helm install reloader stakater/reloader --namespace kube-system

# Add annotation to HelmRelease
kubectl annotate helmrelease postgresql \
  -n databases \
  secret.reloader.stakater.com/reload="postgresql-secrets"
```

## Troubleshooting

### ExternalSecret Not Syncing

**Check ESO controller logs:**
```bash
kubectl logs -n external-secrets deployment/external-secrets --tail=100
```

**Common issues:**
- SecretStore misconfigured (wrong credentials/URL)
- Backend connectivity issues
- Secret doesn't exist in backend
- Invalid remoteRef path

**Verify SecretStore connectivity:**
```bash
kubectl describe secretstore vault-backend -n databases
```

### Secret Not Created

**Check ExternalSecret events:**
```bash
kubectl get events -n databases --field-selector involvedObject.name=postgresql-secrets
```

**Manually test backend access:**
```bash
# For Vault
vault kv get secret/database/postgresql

# For AWS
aws secretsmanager get-secret-value --secret-id database/postgresql

# For GCP
gcloud secrets versions access latest --secret=database-postgresql-admin-password
```

### PostgreSQL Pod Not Starting

**Check pod events:**
```bash
kubectl describe pod -n databases -l app.kubernetes.io/name=postgresql
```

**Check if secret exists:**
```bash
kubectl get secret postgresql-secrets -n databases
```

**Verify HelmRelease values:**
```bash
helm get values postgresql -n databases
```

## Cleanup

```bash
# Delete all resources
kubectl delete -k .

# Or with Flux
flux delete kustomization postgresql

# Delete secrets from backend
# Vault:
vault kv delete secret/database/postgresql

# AWS:
aws secretsmanager delete-secret --secret-id database/postgresql --force-delete-without-recovery

# GCP:
gcloud secrets delete database-postgresql-admin-password --quiet
gcloud secrets delete database-postgresql-user-password --quiet
```

## Security Best Practices

1. **Use IRSA/Workload Identity** - Avoid storing backend credentials in cluster
2. **Least privilege** - Grant only necessary permissions to ESO service account
3. **Short refresh intervals** - For sensitive production secrets, use 15m-1h
4. **Monitor sync failures** - Alert on ExternalSecret sync errors
5. **Audit backend access** - Use backend audit logs to track secret access
6. **Rotate regularly** - Implement automated secret rotation
7. **Separate backends per environment** - Use different Vault paths/AWS accounts for prod/staging
8. **Backup backend keys** - Ensure disaster recovery for backend encryption keys

## Additional Resources

- [External Secrets Operator Documentation](https://external-secrets.io/)
- [CloudNativePG Documentation](https://cloudnative-pg.io/)
- [CloudNativePG Helm Chart](https://github.com/cloudnative-pg/charts)
