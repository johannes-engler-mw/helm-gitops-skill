# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Claude Code skill plugin for deploying Helm charts to Kubernetes clusters using GitOps principles (ArgoCD or FluxCD). The skill automates discovering official Helm charts, detecting repository structure conventions, and generating appropriate GitOps manifests.

## Repository Structure

The repository is organized into three main areas:

1. **`helm-gitops/`** - Skill definition and reference documentation
   - `SKILL.md` - Main skill workflow and instructions for Claude
   - `references/` - Detailed templates and patterns for ArgoCD, FluxCD, and deployment modes

2. **`examples/`** - Working examples for both GitOps tools
   - `argocd/` - ArgoCD Application CRD examples
   - `fluxcd/` - FluxCD HelmRelease/HelmRepository examples

3. **`.claude-plugin/`** - Plugin metadata for Claude Code marketplace
   - `plugin.json` - Skill registration and metadata
   - `marketplace.json` - Marketplace listing configuration

## Architecture Concepts

### Skill Workflow (6-Step Process)

The skill follows a structured workflow defined in `helm-gitops/SKILL.md`:

1. **Identify Application** - Parse user request for application name
2. **Web Search** - Find official Helm chart repository URL, chart name, and version via web search (always required for accurate info)
3. **Detect Repository Structure** - Examine user's GitOps repo to understand folder conventions (Pattern A-D)
4. **Ask Deployment Method** - Confirm ArgoCD or FluxCD preference if not specified
5. **Generate Manifests** - Create appropriate CRDs using reference templates
6. **Provide Files** - Save to correct location matching detected conventions

### Repository Pattern Detection

The skill adapts to four common GitOps repository patterns:

- **Pattern A**: By type (`infrastructure/controllers`, `infrastructure/monitoring`)
- **Pattern B**: By environment (`clusters/production`, `clusters/staging`)
- **Pattern C**: Flat structure (`manifests/`)
- **Pattern D**: Component-based (`infra/kong/`, `infra/apisix/`) - Preferred for clear isolation

### ArgoCD vs FluxCD Differences

**ArgoCD**: Single `Application` CRD pointing to Helm repo, inline values
**FluxCD**: Two CRDs (`HelmRepository` + `HelmRelease`), supports namespace-scoped or global repos

FluxCD's `HelmRepository` can be:
- **Global** (`flux-system` namespace) - For shared repos like Prometheus Community, Jetstack
- **Namespace-scoped** - Better isolation, easier cleanup

### Deployment Modes

Many charts support multiple deployment modes (see `references/deployment-modes.md`):

- **Standalone/Stateless** - No external dependencies (etcd disabled), GitOps-native
- **Clustered/Stateful** - Requires etcd/DB, supports HA and distributed state

Always ask user preference based on their environment (dev vs production).

### Combined Charts

Some charts bundle multiple components:
- APISIX: gateway + ingress-controller
- kube-prometheus-stack: Prometheus + Grafana + Alertmanager
- Kong: gateway + ingress controller

Configure via nested values (e.g., `gateway.enabled: true`, `ingress-controller.enabled: true`).

## Development

### Testing Examples

To validate example manifests:

```bash
# FluxCD examples
kubectl apply --dry-run=client -k examples/fluxcd/apisix-api-gateway/

# ArgoCD examples
kubectl apply --dry-run=client -f examples/argocd/apisix-api-gateway/
```

### Adding New Examples

When adding examples for new applications:

1. Create parallel structures in `examples/argocd/` and `examples/fluxcd/`
2. Include README.md with deployment and verification steps
3. Pin chart versions for reproducibility
4. Use NodePort services for local testing compatibility

### Reference Documentation Structure

The `helm-gitops/references/` directory contains templates:

- `argocd.md` - Application CRD patterns, sync policies, app-of-apps
- `flux.md` - HelmRelease/HelmRepository patterns, post-deployment verification
- `deployment-modes.md` - Standalone vs clustered configuration guidance

When modifying skill behavior, update the appropriate reference file.

## Key Implementation Details

### Web Search Requirement

The skill **must always web search** in Step 2 to get current chart information:
- Repository URL changes over time
- Chart versions update frequently
- Configuration recommendations evolve

Never assume chart details without searching.

### Version Pinning

All generated manifests must pin chart versions:
- ArgoCD: `targetRevision: "1.2.3"`
- FluxCD: `version: "1.2.3"`

This ensures reproducibility and controlled upgrades.

### Best Practices Embedded

Generated manifests should include:
- Standard Kubernetes labels (`app.kubernetes.io/*`)
- Resource requests/limits (when available from search)
- Namespace creation handling
- Dependency management (e.g., etcd for APISIX)
- Sensible defaults with clear customization points

### Alpha/Beta Feature Handling

Document feature maturity in comments:
```yaml
values:
  kubernetes:
    enableGatewayAPI: true  # Alpha: Gateway API support
```

Include warnings about potential breaking changes.

## Plugin Metadata

The `.claude-plugin/plugin.json` file defines:
- Skill name and description (triggers skill invocation)
- Path to SKILL.md
- Keywords for marketplace discoverability

When updating skill behavior, ensure description in `plugin.json` matches capabilities.

## Error Handling

The skill includes comprehensive error handling guidance in `SKILL.md` for common failure scenarios:

- **Web search failures**: No chart found, multiple charts, deprecated charts
- **Repository structure ambiguity**: No clear pattern, mixed patterns
- **Chart version issues**: Version not found, major version jumps
- **Secrets detection failures**: Cluster not accessible, conflicting solutions
- **Dependency issues**: Missing required dependencies

Key principle: **Don't guess** - always ask the user for clarification with clear options and recommendations.

## Common Gotchas

1. **HelmRepository namespace references** - FluxCD namespace-scoped repos must have `sourceRef.namespace` matching `HelmRelease.metadata.namespace`
2. **NodePort conflicts** - Document common port assignments (30080/30443 for primary gateway, 30082/30444 for secondary)
3. **CRD installation** - FluxCD needs `crds: CreateReplace` in install/upgrade specs
4. **Combined charts** - Don't suggest deploying ingress-controller separately if already bundled in main chart

## Secrets Management Detection and Adaptation

### Three-Layer Detection Strategy

The skill uses an intelligent, adaptive approach to secrets management:

**Layer 1: Cluster Detection**
- Runs `kubectl` commands to detect installed solutions (ESO, Sealed Secrets)
- Checks for CRDs: `externalsecrets.external-secrets.io`, `sealedsecrets.bitnami.com`
- Parallel execution for performance (~2-5 seconds)
- Results cached in memory for session

**Layer 2: Repository Pattern Detection**
- Searches GitOps repo for usage patterns with `grep`
- Counts occurrences of ExternalSecret, SealedSecret, SOPS patterns
- Identifies predominant solution from frequency analysis
- Maps patterns to understand which areas use which solution

**Layer 3: Chart-Specific Secrets Discovery**
- Enhanced web search identifies which Helm values contain secrets
- Pattern matching: `*password*`, `*apiKey*`, `*token*`, `*secret*`, `*credential*`
- Checks if chart supports `existingSecret` pattern (preferred)
- Identifies secret value paths (e.g., `auth.password`, `adminPassword`)

### Decision Logic

Priority order for automatic adaptation:
1. Cluster has ESO + repo uses ExternalSecrets → Use ESO
2. Cluster has Sealed Secrets + repo uses SealedSecrets → Use Sealed Secrets
3. Repo has SOPS patterns → Use SOPS (Flux only)
4. Multiple solutions detected → Ask user with context
5. No solution detected → Ask user to choose

### Values Generation Patterns

**For ESO:**
- Generate ExternalSecret + SecretStore resources
- Use chart's `existingSecret` pattern if supported
- Fall back to `valuesFrom` for complex values
- Support multiple backends (Vault, AWS, GCP, Azure)

**For Sealed Secrets:**
- Generate SealedSecret template with sealing instructions
- Include kubeseal commands in comments
- Reference sealed secret in Helm values
- Provide workflow documentation

**For SOPS:**
- Generate encrypted values file template
- Configure Flux Kustomization with SOPS decryption
- Include encryption workflow in README
- Native Flux support (ArgoCD requires plugin)

**For Native Secrets:**
- Generate Secret template with placeholder values
- Include strong warning about GitOps limitations
- Provide kubectl commands for manual creation
- Recommend upgrading to ESO or Sealed Secrets

### Implementation Approach

**Web Search Strategy**: Instead of bundled documentation, the skill uses web search for current implementation details:
- ESO detected → Search: `"External Secrets Operator {chart-name} kubernetes example"`
- Sealed Secrets detected → Search: `"Sealed Secrets kubeseal {chart-name} kubernetes"`
- SOPS detected → Search: `"SOPS FluxCD {chart-name} kubernetes"`

**Benefits**: Always current information, minimal token usage, leverages Claude's existing knowledge.

**Example Reference**: `/examples/fluxcd/postgresql-eso/` provides a minimal ESO integration example.

## Verification Commands

After generating manifests, provide appropriate verification commands:

**FluxCD:**
```bash
flux get helmreleases -A
kubectl describe helmrelease <name> -n <namespace>
kubectl get pods -n <namespace>
```

**ArgoCD:**
```bash
argocd app get <name>
kubectl get pods -n <namespace>
```

**Secrets (ESO):**
```bash
kubectl get externalsecret -n <namespace>
kubectl describe externalsecret <name> -n <namespace>
kubectl get secret <name> -n <namespace>
```

**Secrets (Sealed Secrets):**
```bash
kubectl get sealedsecret -n <namespace>
kubectl get secret <name> -n <namespace>
```
