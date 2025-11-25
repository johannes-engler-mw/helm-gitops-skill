---
name: helm-gitops
description: Deploy official Helm charts for open source applications to Kubernetes via GitOps. Supports both ArgoCD and FluxCD. Use when the user wants to add Helm-based applications (monitoring, API gateways, ingress controllers, cert-manager, databases, etc.) to their GitOps repository. Triggers include requests to deploy, install, or add Helm charts through ArgoCD or Flux.
---

# Helm GitOps Deployment Skill

Deploy Helm charts to Kubernetes clusters using GitOps principles with ArgoCD or FluxCD.

## Workflow

1. **Identify the application** - Parse user request for the application name
2. **Web search for chart details** - Find official Helm chart repository, chart name, and recommended values
3. **Detect repository structure** - Examine the user's GitOps repo to understand folder conventions
4. **Ask deployment method** - Confirm ArgoCD or FluxCD if not specified
5. **Generate manifests** - Create appropriate CRDs based on the GitOps tool
6. **Provide the files** - Save to the correct location in user's repo structure

## Step 1: Identify Application

Extract the application name from user request. Examples:
- "deploy APISIX API gateway" → APISIX
- "add prometheus monitoring" → Prometheus / kube-prometheus-stack
- "install cert-manager" → cert-manager

## Step 2: Web Search for Chart Details

**Always search** to get current, accurate Helm chart information. Search queries:
- `{app-name} official helm chart`
- `{app-name} helm chart artifacthub`

Extract from search results:
- **Repository URL** (e.g., `https://charts.bitnami.com/bitnami`)
- **Chart name** (e.g., `apisix`)
- **Latest version** (or note if user should pin)
- **Key configuration values** for common setups
- **Dependencies** (e.g., etcd for APISIX)
- **Chart type** (single component vs combined)

Prefer official charts from: ArtifactHub, vendor repos, Bitnami, or CNCF projects.

### Combined Chart Pattern

Some charts bundle multiple components for simplified deployment:

- **APISIX**: `apisix` chart includes gateway + ingress-controller
- **kube-prometheus-stack**: Prometheus + Grafana + Alertmanager
- **Kong**: Gateway + ingress controller

**Configuration approach**:
```yaml
values:
  # Main component
  gateway:
    enabled: true

  # Integrated component
  ingress-controller:
    enabled: true
    config:
      # Controller-specific settings
```

**Advantages**: Simplified deployment, automatic service discovery between components, consistent versioning.

## Step 3: Detect Repository Structure

Examine the user's GitOps repository to understand conventions:

```bash
# List top-level structure
ls -la

# Look for common GitOps patterns
find . -name "*.yaml" -o -name "*.yml" | head -20

# Check for existing HelmRelease or Application resources
grep -r "kind: HelmRelease\|kind: Application" --include="*.yaml" -l 2>/dev/null | head -5
```

**Common structures to detect:**

```
# Pattern A: By type
infrastructure/
  ├── controllers/
  ├── monitoring/
  └── networking/

# Pattern B: By environment
clusters/
  ├── production/
  ├── staging/
  └── base/

# Pattern C: Flat
manifests/
  ├── app1.yaml
  └── app2.yaml

# Pattern D: Component-based (per-service directories)
infra/
  ├── kong/
  │   ├── namespace.yaml
  │   ├── helmrepository.yaml
  │   ├── helmrelease.yaml
  │   └── kustomization.yaml
  ├── apisix/
  │   └── ... (same structure)
  └── nginx-ingress/
      └── ingress-nginx.yaml (flat alternative)
```

**Pattern D Benefits**:
- Clear service isolation
- Easy to add/remove services
- Consistent structure across team
- Natural Kustomization boundaries

Adapt output to match existing conventions. If no clear pattern exists, suggest a sensible default and confirm with user.

## Step 4: Ask Deployment Method

If not specified in the request, ask:

> Which GitOps tool should I use?
> 1. **ArgoCD** - Application CRD
> 2. **FluxCD** - HelmRelease + HelmRepository CRDs

Also clarify:
- **Namespace**: Where should the application run?
- **Environment**: Is this for a specific environment (dev/staging/prod)?
- **Values overrides**: Any custom configuration needed?

## Step 5: Generate Manifests

Based on the chosen tool, read the appropriate reference:
- **ArgoCD**: See [references/argocd.md](references/argocd.md)
- **FluxCD**: See [references/flux.md](references/flux.md)

Key principles:
- Pin chart versions for reproducibility
- Use sensible defaults with clear comments for customization points
- Include resource requests/limits recommendations if available from search
- Add standard labels (app.kubernetes.io/name, app.kubernetes.io/component, etc.)

### Alpha/Beta Feature Handling

Many Helm charts include experimental features behind flags:

```yaml
values:
  # Feature flags
  kubernetes:
    enableGatewayAPI: true      # Alpha: Gateway API support
    enableServiceAPIs: false    # Deprecated feature

  features:
    experimental:
      enabled: true
```

**Documentation approach**:
- Note feature maturity (Alpha/Beta/GA) in comments
- Link to upstream documentation for feature status
- Warn about breaking changes in future versions
- Suggest stable alternatives when available

### Deploying Additional CRDs

Some applications require additional Kubernetes resources alongside the HelmRelease:

**Gateway API Resources**: GatewayClass, Gateway
**Service Mesh Resources**: Istio VirtualService, DestinationRule
**Monitoring**: ServiceMonitor, PodMonitor (Prometheus)
**Certificate Management**: Certificate, Issuer (cert-manager)

**Pattern**: Include these in the same directory structure with Kustomization:

```
infra/<app>/
├── namespace.yaml
├── helmrepository.yaml
├── helmrelease.yaml
├── gatewayclass.yaml      # Additional CRD resources
├── gateway.yaml
└── kustomization.yaml     # References all files
```

## Step 6: Provide Files

Save generated manifests to the detected/agreed location. Typical outputs:

**For FluxCD:**
- `HelmRepository` (if repo not already defined)
- `HelmRelease` with values inline or reference to ConfigMap

**For ArgoCD:**
- `Application` resource pointing to Helm chart
- Optional: `AppProject` if project isolation needed

Always explain:
- What files were created and where
- How to apply/sync the changes
- Any post-deployment verification steps
