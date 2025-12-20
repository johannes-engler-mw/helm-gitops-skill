# CloudNativePG with External Secrets Operator - ArgoCD Example

Deploys CloudNativePG operator using ArgoCD with ESO for secrets management.

## Prerequisites

- ArgoCD installed
- External Secrets Operator installed
- Secret backend configured (Vault/AWS/GCP/Azure)

For ESO installation and backend setup, see the [FluxCD postgresql-eso example](../../fluxcd/postgresql-eso/README.md#installation).

## Files

| File | Purpose |
|------|---------|
| `namespace.yaml` | Creates databases namespace |
| `secretstore.yaml` | ESO backend connection |
| `externalsecret.yaml` | Secret sync configuration |
| `postgresql-application.yaml` | ArgoCD Application for operator |
| `eso-resources-application.yaml` | Optional: manage ESO resources via ArgoCD |

## Quick Start

```bash
# 1. Store secrets in backend (see FluxCD example for details)
vault kv put secret/database/postgresql \
  admin-password="$(openssl rand -base64 32)" \
  user-password="$(openssl rand -base64 32)"

# 2. Update secretstore.yaml with your backend config

# 3. Apply ESO resources
kubectl apply -f namespace.yaml
kubectl apply -f secretstore.yaml
kubectl apply -f externalsecret.yaml

# 4. Verify secret synced
kubectl get externalsecret -n databases

# 5. Deploy ArgoCD Application
kubectl apply -f postgresql-application.yaml
```

## Verification

```bash
# Check ESO
kubectl get externalsecret -n databases
kubectl get secret postgresql-secrets -n databases

# Check ArgoCD
argocd app get postgresql

# Check operator
kubectl get pods -n databases
```

## Key Differences from FluxCD

| Aspect | ArgoCD | FluxCD |
|--------|--------|--------|
| Helm deployment | `Application` CRD | `HelmRelease` + `HelmRepository` |
| CRD handling | `ServerSideApply=true` | `crds.create: true` |
| Namespace creation | `CreateNamespace=true` syncOption | `install.createNamespace: true` |
| ESO resources | Applied separately or via App-of-Apps | Part of Kustomization |

## Cleanup

```bash
argocd app delete postgresql --cascade
kubectl delete -f externalsecret.yaml
kubectl delete -f secretstore.yaml
kubectl delete -f namespace.yaml
```

See [FluxCD example](../../fluxcd/postgresql-eso/README.md) for backend cleanup commands.
