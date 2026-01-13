---
name: helm-gitops
description: Deploy official Helm charts for open source applications to Kubernetes via GitOps. Supports both ArgoCD and FluxCD. Use when the user wants to add Helm-based applications (monitoring, API gateways, ingress controllers, cert-manager, databases, etc.) to their GitOps repository. Triggers include requests to deploy, install, or add Helm charts through ArgoCD or Flux.
---

# Helm GitOps Deployment Skill

Deploy Helm charts to Kubernetes clusters using GitOps principles with ArgoCD or FluxCD.

## Prerequisites

- **kubectl** configured with cluster access (for secrets detection in Step 3.5)
  - If unavailable, ask user to specify their secrets solution manually

## Workflow

Copy this checklist to track progress:

```
Deployment Progress:
- [ ] Step 1: Identify application from user request
- [ ] Step 2: Web search for chart details (repo, version, secrets)
- [ ] Step 3: Detect repository structure pattern
- [ ] Step 3.5: Detect secrets management solution
- [ ] Step 4: Confirm deployment method (ArgoCD/FluxCD)
- [ ] Step 5: Generate manifests with secrets adaptation
- [ ] Step 6: Save files and provide verification steps
```

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
- `{app-name} helm secrets values` (for secrets discovery)
- `{app-name} helm chart password configuration`

Extract from search results:
- **Repository URL** (e.g., `https://charts.apiseven.com`)
- **Chart name** (e.g., `apisix`)
- **Latest version** (or note if user should pin)
- **Key configuration values** for common setups
- **Dependencies** (e.g., etcd for APISIX)
- **Chart type** (single component vs combined)
- **Secret values** (passwords, API keys, tokens, certificates)
- **existingSecret support** (whether chart supports external secret references)

Prefer official charts from: ArtifactHub, vendor repos, or CNCF projects.

### Combined Chart Pattern

Some charts bundle multiple components (e.g., APISIX includes gateway + ingress-controller, kube-prometheus-stack bundles Prometheus + Grafana + Alertmanager). Configure via nested values:

```yaml
values:
  gateway:
    enabled: true
  ingress-controller:
    enabled: true
```

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

**Pattern D** is preferred for clear service isolation.

Adapt output to match existing conventions. If no clear pattern, suggest Pattern D and confirm with user.

## Step 3.5: Detect Secrets Management

After understanding the repository structure, detect which secrets management solution to use for chart values containing sensitive data.

### Detection Process

Execute a three-layer detection strategy:

#### Layer 1: Cluster Detection

```bash
# ESO
kubectl get crd externalsecrets.external-secrets.io 2>/dev/null

# Sealed Secrets
kubectl get crd sealedsecrets.bitnami.com 2>/dev/null
```

Run checks in parallel. Requires `kubectl` with cluster access.

#### Layer 2: Repository Pattern Search

```bash
grep -r "kind: ExternalSecret\|kind: SecretStore" --include="*.yaml" -l 2>/dev/null | head -10
grep -r "kind: SealedSecret" --include="*.yaml" -l 2>/dev/null | head -10
grep -r "sops:\|ENC\[AES256_GCM" --include="*.yaml" -l 2>/dev/null | head -10
```

Count occurrences to identify the predominant pattern.

#### Layer 3: Chart-Specific Secrets

From Step 2 web search, identify secret values (`*password*`, `*apiKey*`, `*token*`) and check for `existingSecret` support.

### Decision Logic

Apply this priority order to determine which secrets solution to use:

1. **If cluster has ESO + repo has ExternalSecret patterns** → Use ESO
2. **If cluster has Sealed Secrets + repo has SealedSecret patterns** → Use Sealed Secrets
3. **If repo has SOPS patterns** → Use Helm-Secrets+SOPS
4. **If multiple solutions detected** → Ask user which to prefer (show usage context)
5. **If none detected** → Ask user if they want to use native secrets or set up a solution

### Ask User (Multiple Solutions Detected)

If multiple solutions are found, prompt the user:

> I detected multiple secrets management solutions in your environment:
> - **External Secrets Operator** (found in: infrastructure/monitoring)
> - **Sealed Secrets** (found in: applications/web-apps)
>
> Which solution would you prefer for deploying {app-name}?
> 1. External Secrets Operator - Syncs from external providers (Vault, AWS, GCP, Azure)
> 2. Sealed Secrets - Encrypts secrets for Git storage
> 3. SOPS - Encrypts values files (Flux native support)
> 4. Native Kubernetes Secrets - Not recommended for GitOps

### Ask User (No Solution Detected)

If no secrets management solution is found:

> No secrets management solution detected in your cluster/repository.
>
> The {app-name} chart requires sensitive values (passwords, API keys).
> How would you like to handle secrets?
>
> 1. **External Secrets Operator** (Recommended for production)
>    - Syncs secrets from external providers
>    - Secrets never stored in Git
>    - Requires: ESO installation + backend (Vault/AWS/GCP/Azure)
>
> 2. **Sealed Secrets**
>    - Encrypts secrets for safe Git storage
>    - Good for GitOps workflows
>    - Requires: Sealed Secrets controller installation
>
> 3. **SOPS** (Flux users)
>    - Encrypts values files in Git
>    - Native Flux support
>    - Requires: SOPS configuration + encryption backend
>
> 4. **Native Kubernetes Secrets**
>    - Simple but NOT recommended for GitOps
>    - Secrets must be created manually (not stored in Git)

**Next Step**: When a solution is chosen, use web search to get current implementation details:
- ESO: Search `"External Secrets Operator {chart-name} kubernetes example"`
- Sealed Secrets: Search `"Sealed Secrets kubeseal {chart-name} kubernetes"`
- SOPS: Search `"SOPS FluxCD {chart-name} kubernetes"`

This ensures up-to-date configuration patterns and best practices.

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

Based on the chosen tool and detected secrets solution, read the appropriate references:
- **ArgoCD**: See [references/argocd.md](references/argocd.md)
- **FluxCD**: See [references/flux.md](references/flux.md)

For secrets integration, use web search to get current implementation patterns based on the detected solution.

Key principles:
- Pin chart versions for reproducibility
- Only specify values that differ from chart defaults (minimal overrides)
- This allows chart defaults to evolve without requiring manifest updates
- Essential for multi-environment setups where base + patch pattern is common
- Use sensible defaults with clear comments for customization points
- Include resource requests/limits recommendations if available from search
- Add standard labels (app.kubernetes.io/name, app.kubernetes.io/component, etc.)
- **Adapt values for secrets** based on detected solution (Step 3.5)

### Secrets Values Adaptation

Based on the detected secrets management solution, generate appropriate manifests. Use web search to find current implementation patterns:

**For External Secrets Operator:**
- Use chart's `existingSecret` pattern if supported
- Generate ExternalSecret resource referencing external provider
- Use HelmRelease `valuesFrom` to reference the secret
- Web search: `"External Secrets Operator {chart-name} kubernetes example"`

**For Sealed Secrets:**
- Generate SealedSecret template with sealing instructions
- Reference sealed secret in Helm values
- Provide kubeseal commands in comments
- Web search: `"Sealed Secrets kubeseal {chart-name} kubernetes"`

**For SOPS:**
- Generate encrypted values file template
- Configure Flux Kustomization with SOPS decryption
- Provide encryption workflow in README
- Web search: `"SOPS FluxCD {chart-name} kubernetes"`

**For Native Secrets:**
- Generate Secret template with placeholder values
- Include warning about GitOps limitations
- Provide kubectl commands for manual creation
- Recommend upgrading to ESO or Sealed Secrets

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

## Error Handling

For common failure scenarios and recovery strategies, see [references/error-handling.md](references/error-handling.md).

Key principle: **Don't guess** - ask the user for clarification with clear options and recommendations.

Covered scenarios:
- Web search failures (no chart, multiple charts, deprecated)
- Repository structure ambiguity
- Chart version issues
- Secrets detection failures
- Dependency issues
