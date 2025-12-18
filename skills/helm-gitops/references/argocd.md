# ArgoCD Helm Deployment Reference

## Application CRD

ArgoCD uses a single `Application` CRD to deploy Helm charts.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: {app-name}
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: {project-name}  # default or custom AppProject
  source:
    repoURL: {helm-repo-url}
    chart: {chart-name}
    targetRevision: "{chart-version}"  # Always pin versions
    helm:
      releaseName: {release-name}
      values: |
        # Inline values here
  destination:
    server: https://kubernetes.default.svc
    namespace: {target-namespace}
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

## Source Types

### Helm Repository (recommended for public charts)

```yaml
spec:
  source:
    repoURL: https://prometheus-community.github.io/helm-charts
    chart: kube-prometheus-stack
    targetRevision: "55.5.0"
```

### OCI Registry

```yaml
spec:
  source:
    repoURL: oci://ghcr.io/stefanprodan/charts
    chart: podinfo
    targetRevision: "6.5.0"
```

### Git Repository (for charts stored in Git)

```yaml
spec:
  source:
    repoURL: https://github.com/org/repo.git
    path: charts/my-app
    targetRevision: main
```

## Values Configuration

### Inline Values

```yaml
spec:
  source:
    helm:
      values: |
        replicaCount: 3
        image:
          tag: v1.2.3
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
```

### Values from Files (Git source)

```yaml
spec:
  source:
    helm:
      valueFiles:
        - values.yaml
        - values-production.yaml
```

### Values from External Sources

```yaml
spec:
  source:
    helm:
      valuesObject:
        key: value
      # Or reference ConfigMaps/Secrets via AVP plugin
```

## Sync Policies

### Automated Sync with Self-Heal

```yaml
spec:
  syncPolicy:
    automated:
      prune: true      # Delete resources removed from Git
      selfHeal: true   # Revert manual changes
      allowEmpty: false
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
```

### Sync Options

```yaml
spec:
  syncPolicy:
    syncOptions:
      - CreateNamespace=true
      - PrunePropagationPolicy=foreground
      - PruneLast=true
      - ServerSideApply=true  # For large CRDs
      - RespectIgnoreDifferences=true
```

## Common Patterns

### With Health Checks

```yaml
spec:
  # Override default health checks
  ignoreDifferences:
    - group: apps
      kind: Deployment
      jsonPointers:
        - /spec/replicas  # Ignore HPA-managed replicas
```

### Multi-Source Application

```yaml
spec:
  sources:
    - repoURL: https://prometheus-community.github.io/helm-charts
      chart: kube-prometheus-stack
      targetRevision: "55.5.0"
      helm:
        valueFiles:
          - $values/prometheus/values.yaml
    - repoURL: https://github.com/org/config.git
      targetRevision: main
      ref: values  # Reference for $values above
```

### ApplicationSet for Multiple Environments

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: {app-name}
  namespace: argocd
spec:
  generators:
    - list:
        elements:
          - cluster: production
            url: https://prod-cluster.example.com
          - cluster: staging
            url: https://staging-cluster.example.com
  template:
    metadata:
      name: '{{cluster}}-{app-name}'
    spec:
      project: default
      source:
        repoURL: https://charts.example.com
        chart: my-app
        targetRevision: "1.0.0"
        helm:
          valueFiles:
            - values-{{cluster}}.yaml
      destination:
        server: '{{url}}'
        namespace: my-app
```

## AppProject (Optional)

For team/app isolation:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: {project-name}
  namespace: argocd
spec:
  description: "Infrastructure applications"
  sourceRepos:
    - https://prometheus-community.github.io/helm-charts
    - https://charts.jetstack.io
  destinations:
    - namespace: '*'
      server: https://kubernetes.default.svc
  clusterResourceWhitelist:
    - group: '*'
      kind: '*'
```

## File Organization

Typical ArgoCD structure:

```
argocd/
├── projects/
│   ├── infrastructure.yaml
│   └── applications.yaml
└── apps/
    ├── infrastructure/
    │   ├── cert-manager.yaml
    │   ├── ingress-nginx.yaml
    │   └── monitoring.yaml
    └── workloads/
        ├── app1.yaml
        └── app2.yaml

# Or app-of-apps pattern:
argocd/
├── root-app.yaml          # Points to apps/
└── apps/
    ├── cert-manager.yaml
    └── prometheus.yaml
```

## App-of-Apps Pattern

Bootstrap all apps with a single root application:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: root
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/org/gitops.git
    path: argocd/apps
    targetRevision: main
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

## Secrets Integration

When secrets are detected, the skill adapts Application manifest generation to integrate with your chosen solution.

**ArgoCD Consideration:** ArgoCD stores manifests in Redis cache. Use post-deployment secrets (ESO, Sealed Secrets) rather than generation-time injection for better security.

**Supported Approaches:**
- **External Secrets Operator (ESO)**: Generates ExternalSecret, uses chart's `existingSecret` pattern in Application values
- **Sealed Secrets**: Generates SealedSecret template with kubeseal commands
- **SOPS**: Requires helm-secrets plugin (complex setup - web search for details)

**For implementation details**, the skill will web search for current patterns:
- ESO: `"External Secrets Operator ArgoCD {chart-name} kubernetes"`
- Sealed Secrets: `"Sealed Secrets ArgoCD {chart-name} kubernetes"`
- SOPS: `"ArgoCD helm-secrets plugin SOPS setup"`

## Debugging

```bash
# Check application status
argocd app list
argocd app get {app-name}

# View sync status
argocd app sync {app-name} --dry-run

# Force refresh
argocd app get {app-name} --refresh

# View diff
argocd app diff {app-name}

# Debug Helm rendering
argocd app manifests {app-name} --source live
argocd app manifests {app-name} --source git
```
