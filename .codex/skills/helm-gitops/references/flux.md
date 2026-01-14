# FluxCD Helm Deployment Reference

## Contents
- [Required Resources](#required-resources)
- [HelmRepository](#helmrepository) (Global vs Namespace-scoped)
- [HelmRelease](#helmrelease)
- [Common Patterns](#common-patterns) (Dependencies, ValuesFrom, Health Checks)
- [File Organization](#file-organization)
- [Kustomization for Flux](#kustomization-for-flux)
- [Post-Deployment Verification](#post-deployment-verification)
- [Secrets Integration](#secrets-integration)
- [Debugging](#debugging)

## Required Resources

FluxCD uses two CRDs to deploy Helm charts:

1. **HelmRepository** - Defines where to fetch charts from
2. **HelmRelease** - Defines what chart to deploy and how

## HelmRepository

Define once per chart repository, reuse across multiple HelmReleases.

### Global HelmRepository (Shared Across Cluster)

```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: HelmRepository
metadata:
  name: {repo-name}
  namespace: flux-system  # Global scope
spec:
  interval: 24h
  url: {repository-url}
```

**Example for Prometheus Community:**
```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: HelmRepository
metadata:
  name: prometheus-community
  namespace: flux-system
spec:
  interval: 24h
  url: https://prometheus-community.github.io/helm-charts
```

### Namespace-Scoped HelmRepository

```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: HelmRepository
metadata:
  name: {repo-name}
  namespace: {same-namespace-as-helmrelease}  # Namespace-scoped
spec:
  interval: 24h
  url: {repository-url}
```

**Example for APISIX:**
```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: HelmRepository
metadata:
  name: apisix
  namespace: apisix  # Same namespace as HelmRelease
spec:
  interval: 24h
  url: https://charts.apiseven.com
```

**When to use each**:
- **Global** (`flux-system` namespace): Multiple services use same repository (Prometheus Community, Jetstack, etc.)
- **Namespace-scoped**: Single service repository, better isolation, easier cleanup when removing service

**OCI Registry Example:**
```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: HelmRepository
metadata:
  name: podinfo
  namespace: flux-system
spec:
  type: oci
  interval: 5m
  url: oci://ghcr.io/stefanprodan/charts
```

## HelmRelease

```yaml
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: {release-name}
  namespace: {target-namespace}
spec:
  interval: 30m
  chart:
    spec:
      chart: {chart-name}
      version: "{chart-version}"  # Always pin versions
      sourceRef:
        kind: HelmRepository
        name: {repo-name}
        namespace: flux-system
  install:
    crds: CreateReplace
    remediation:
      retries: 3
  upgrade:
    crds: CreateReplace
    remediation:
      retries: 3
  values:
    # Chart-specific values here
```

## Common Patterns

### With Dependencies

When a chart depends on another (e.g., app needs database):

**Scenario 1: Service depends on infrastructure**
```yaml
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: my-app
  namespace: apps
spec:
  dependsOn:
    - name: postgresql
      namespace: databases
    - name: redis
      namespace: caching
  # ... rest of spec
```

**Scenario 2: Infrastructure deployment order**
```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: gateways
  namespace: flux-system
spec:
  dependsOn:
    - name: cert-manager  # Deploy cert-manager first
  # ... rest of spec
# Then gateway can use cert-manager issuers
```

**Scenario 3: Namespace-scoped HelmRepository reference**
```yaml
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: apisix
  namespace: apisix
spec:
  chart:
    spec:
      sourceRef:
        kind: HelmRepository
        name: apisix
        namespace: apisix  # Must match HelmRelease namespace
  # ... rest of spec
```

### Values from ConfigMap/Secret

```yaml
spec:
  valuesFrom:
    - kind: ConfigMap
      name: {app}-values
      valuesKey: values.yaml
    - kind: Secret
      name: {app}-secrets
      valuesKey: sensitive.yaml
```

### Post-Install Health Checks

```yaml
spec:
  test:
    enable: true
  postRenderers:
    - kustomize:
        patches:
          - target:
              kind: Deployment
            patch: |
              - op: add
                path: /spec/template/spec/containers/0/readinessProbe
                value:
                  httpGet:
                    path: /health
                    port: 8080
```

### Namespace Creation

Flux can create the namespace if needed:

```yaml
spec:
  install:
    createNamespace: true
```

### NodePort Configuration for Local Clusters

For local development (Kind, k3d, minikube), use NodePort services:

```yaml
spec:
  values:
    service:
      type: NodePort
      http:
        servicePort: 80
        nodePort: 30xxx  # Choose unique port 30000-32767
      https:
        servicePort: 443
        nodePort: 30xxx
```

**Common port assignments to avoid conflicts**:
- `30080/30443`: Primary gateway (Kong, NGINX)
- `30082/30444`: Secondary gateway (APISIX)
- `30090`: Prometheus
- `30000`: Grafana
- `30030`: ArgoCD

**Port conflict detection**:
```bash
# Check existing NodePort assignments before deployment
kubectl get svc --all-namespaces -o wide | grep NodePort
```

## File Organization

Typical FluxCD structure:

```
clusters/
└── my-cluster/
    └── flux-system/
        ├── gotk-components.yaml
        └── gotk-sync.yaml

infrastructure/
├── sources/           # HelmRepositories
│   ├── prometheus-community.yaml
│   └── jetstack.yaml
├── controllers/       # Ingress, cert-manager, etc.
│   ├── ingress-nginx.yaml
│   └── cert-manager.yaml
└── monitoring/        # Observability stack
    ├── kube-prometheus-stack.yaml
    └── loki.yaml

apps/
├── base/
│   └── app-name/
│       └── helmrelease.yaml
└── production/
    └── app-name/
        └── kustomization.yaml  # Patches for prod
```

## Kustomization for Flux

Tie everything together with Flux Kustomizations:

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: infrastructure
  namespace: flux-system
spec:
  interval: 10m
  sourceRef:
    kind: GitRepository
    name: flux-system
  path: ./infrastructure
  prune: true
  dependsOn:
    - name: sources
```

## Post-Deployment Verification

Comprehensive validation workflow after deployment:

### 1. Flux Resources
```bash
# Check HelmRelease status
flux get helmreleases -A

# Detailed status with conditions
kubectl describe helmrelease {name} -n {namespace}

# Check HelmRepository sync
flux get sources helm -n {namespace}
```

### 2. Kubernetes Resources
```bash
# Verify all resources created
kubectl get all -n {namespace}

# Check pod status and details
kubectl get pods -n {namespace} -o wide

# View pod logs
kubectl logs -n {namespace} deployment/{name} --tail=50
```

### 3. Service Exposure
```bash
# Check service configuration
kubectl get svc -n {namespace}

# For NodePort: Test via localhost
curl http://localhost:{nodePort}/

# For LoadBalancer: Check EXTERNAL-IP
kubectl get svc -n {namespace} -o wide
```

### 4. Application-Specific Health
```bash
# Execute health check command inside pod
kubectl exec -n {namespace} deployment/{name} -- {health-check-command}

# Example: Check admin API
kubectl exec -n {namespace} deployment/apisix -- \
  curl -s http://localhost:9180/apisix/admin/routes
```

### 5. Integration Validation
```bash
# Test connectivity to dependent services
kubectl exec -n {namespace} deployment/{name} -- nc -zv {service} {port}

# Verify CRDs if installed
kubectl get crd | grep {app-name}

# Check route/ingress configuration
kubectl get ingress,httproute -A
```

## Secrets Integration

When secrets are detected, the skill adapts manifest generation to integrate with your chosen solution:

- **External Secrets Operator (ESO)**: Generates ExternalSecret referencing backend, uses chart's `existingSecret` pattern or `valuesFrom`
- **Sealed Secrets**: Generates SealedSecret template with kubeseal commands, references in HelmRelease
- **SOPS**: Configures Kustomization with SOPS decryption, generates encrypted values file (Flux native support)
- **Native Secrets**: Creates Secret template with warnings (development/testing only)

**For implementation details**, the skill will web search for current patterns:
- ESO: `"External Secrets Operator {chart-name} kubernetes example"`
- Sealed Secrets: `"Sealed Secrets kubeseal {chart-name} kubernetes"`
- SOPS: `"SOPS FluxCD {chart-name} kubernetes"`

**Example reference**: See `/examples/fluxcd/postgresql-eso/` for a minimal ESO integration example.

## Debugging

```bash
# View Helm history
helm history {release-name} -n {namespace}

# Force reconciliation
flux reconcile helmrelease {name} -n {namespace}

# View Flux controller logs
flux logs --level=error

# Check HelmRelease events
kubectl get events -n {namespace} --field-selector involvedObject.name={name}
```
