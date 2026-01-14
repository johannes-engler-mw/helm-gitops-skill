# Helm GitOps Deployment Skill

[![Claude Code](https://img.shields.io/badge/Claude_Code-Compatible-blue)](https://github.com/anthropics/claude-code)
[![OpenAI Codex](https://img.shields.io/badge/OpenAI_Codex-Compatible-green)](https://developers.openai.com/codex)
[![Agent Skills](https://img.shields.io/badge/Agent_Skills-Standard-orange)](https://agentskills.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A universal AI agent skill for deploying official Helm charts to Kubernetes clusters using GitOps principles with ArgoCD or FluxCD.

## What It Does

This skill automates the process of adding Helm-based applications to your GitOps repository by:

1. Identifying the application from your natural language request
2. Finding official Helm charts and repository information via web search
3. Detecting your existing GitOps repository structure and conventions
4. **Detecting secrets management solutions and adapting chart values automatically**
5. Asking for deployment method preference (ArgoCD or FluxCD)
6. Generating appropriate manifest files (Application or HelmRelease CRDs)
7. Placing files in the correct location matching your repository patterns

The skill handles common deployment scenarios including monitoring tools, API gateways, ingress controllers, cert-manager, databases, and any Helm-charted open-source applications.

### Intelligent Secrets Management

The skill automatically detects and adapts to your existing secrets management solution:

- **External Secrets Operator (ESO)** - Syncs from Vault, AWS, GCP, Azure
- **Sealed Secrets** - Encrypts secrets for Git storage
- **SOPS** - Encrypts values files (native Flux support)
- **Native Kubernetes Secrets** - For development/testing

It scans your cluster and repository to identify which solution you're using, then generates appropriate manifests (ExternalSecret, SealedSecret, or SOPS-encrypted files) that integrate seamlessly with your deployment.

## Installation

This skill works with Claude Code, OpenAI Codex, VS Code, GitHub Copilot, Cursor, and other [agentskills.io](https://agentskills.io)-compatible platforms.

### Claude Code

```bash
# Add repository as marketplace
/plugin marketplace add https://github.com/johannes-engler-mw/helm-gitops-skill.git

# Install the skill
/plugin install helm-gitops
```

### OpenAI Codex

```bash
# Install using skill-installer
$skill-installer install https://github.com/johannes-engler-mw/helm-gitops-skill

# Or manual installation
git clone https://github.com/johannes-engler-mw/helm-gitops-skill.git
cp -r helm-gitops-skill/.codex/skills/helm-gitops ~/.codex/skills/
```

### VS Code / GitHub Copilot

```bash
# Clone to VS Code skills directory
git clone https://github.com/johannes-engler-mw/helm-gitops-skill.git
cp -r helm-gitops-skill/skills/helm-gitops ~/.vscode/skills/
# Or use .codex/skills/ - both work with VS Code
```

### Manual Installation (Any Platform)

```bash
git clone https://github.com/johannes-engler-mw/helm-gitops-skill.git
# Then symlink to your platform's skills directory:
# Claude Code: ln -s $(pwd)/skills/helm-gitops ~/.claude/skills/helm-gitops
# Codex: ln -s $(pwd)/.codex/skills/helm-gitops ~/.codex/skills/helm-gitops
```

## Usage

Ask Claude to deploy Helm applications in natural language or force skill usage by mentioning **helm-gitops** in your request.

**Example requests:**
- "Deploy APISIX API gateway to my cluster"
- "Add kube-prometheus-stack for monitoring"
- "Install cert-manager using FluxCD"
- "Set up NGINX ingress controller with ArgoCD"

The skill will:
- Search for the official Helm chart
- Analyze your repository structure
- Generate appropriate GitOps manifests
- Provide deployment instructions

## Supported GitOps Tools

- **ArgoCD** - Generates Application CRDs with Helm source configuration
- **FluxCD** - Generates HelmRepository and HelmRelease CRDs

## Supported Applications

The skill works with any official Helm chart, with optimized patterns for:

| Category | Examples |
|----------|----------|
| **Monitoring** | Prometheus, Grafana, kube-prometheus-stack |
| **API Gateways** | APISIX, Kong, Tyk |
| **Ingress Controllers** | NGINX Ingress, Traefik, HAProxy |
| **Certificate Management** | cert-manager |
| **Databases** | PostgreSQL, MySQL, Redis, MongoDB |
| **Message Queues** | RabbitMQ, Kafka |
| **Service Mesh** | Istio, Linkerd |

## Repository Structure

```
helm-gitops-skill/
├── skills/helm-gitops/
│   ├── SKILL.md                    # Main skill definition with workflow
│   └── references/                 # Detailed reference documentation
│       ├── argocd.md               # ArgoCD deployment patterns
│       ├── flux.md                 # FluxCD deployment patterns
│       ├── deployment-modes.md     # Standalone vs clustered deployments
│       └── error-handling.md       # Error handling guidance
├── examples/                       # Example use cases
│   ├── argocd/                     # ArgoCD examples
│   │   ├── apisix-api-gateway/
│   │   └── postgresql-eso/
│   └── fluxcd/                     # FluxCD examples
│       ├── apisix-api-gateway/
│       └── postgresql-eso/
├── .claude-plugin/                 # Plugin metadata
│   ├── plugin.json
│   └── marketplace.json
├── CLAUDE.md                       # Project-specific guidance for Claude
├── README.md
├── LICENSE
└── .gitignore
```

## Key Features

### Automatic Secrets Management Detection

The skill intelligently detects and adapts to your secrets management approach:

**Three-Layer Detection:**
1. **Cluster Detection** - Checks for installed solutions (ESO, Sealed Secrets) via kubectl
2. **Repository Patterns** - Searches Git history for ExternalSecret, SealedSecret, or SOPS usage
3. **Chart Analysis** - Identifies which Helm values contain secrets and whether chart supports `existingSecret`

**Adaptive Generation:**
- Generates ExternalSecret resources for ESO (supports Vault, AWS, GCP, Azure backends)
- Creates SealedSecret templates with kubeseal instructions for Sealed Secrets
- Produces SOPS-encrypted files with Flux decryption configuration
- Provides secure templates for any detected solution

The skill uses web search to get current implementation details for each solution, ensuring up-to-date patterns and best practices.

### Intelligent Repository Detection

The skill automatically detects your GitOps repository structure and adapts to your conventions:

- **Pattern A**: Organized by type (infrastructure/controllers, infrastructure/monitoring)
- **Pattern B**: Organized by environment (clusters/production, clusters/staging)
- **Pattern C**: Flat structure (manifests/)
- **Pattern D**: Component-based (infra/kong/, infra/apisix/)

### Version Pinning

All generated manifests include pinned chart versions for reproducibility and controlled upgrades.

### Combined Chart Support

Handles complex charts that bundle multiple components:
- **APISIX**: Gateway + ingress-controller
- **kube-prometheus-stack**: Prometheus + Grafana + Alertmanager
- **Kong**: Gateway + ingress controller

### Best Practices

- Sensible defaults with clear customization points
- Standard Kubernetes labels (app.kubernetes.io/*)
- Resource requests/limits recommendations
- Namespace creation and management
- Dependency handling (e.g., etcd for APISIX)

## Example Output

### ArgoCD Structure
```
infrastructure/api-gateway/
├── namespace.yaml
└── apisix-application.yaml
```

### FluxCD Structure
```
infra/apisix/
├── namespace.yaml
├── helmrepository.yaml
├── helmrelease.yaml
└── kustomization.yaml
```

## Requirements

- AI agent with agentskills.io support (Claude Code, OpenAI Codex, VS Code, GitHub Copilot, etc.)
- Existing GitOps repository (ArgoCD or FluxCD configured)
- Kubernetes cluster with kubectl access
- Git repository for GitOps manifests

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

MIT License - see [LICENSE](LICENSE) file for details

## Resources

### GitOps & Kubernetes
- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
- [FluxCD Documentation](https://fluxcd.io/flux/)
- [Helm Charts - ArtifactHub](https://artifacthub.io/)
- [GitOps Principles](https://opengitops.dev/)

### AI Agent Platforms
- [Agent Skills Specification](https://agentskills.io)
- [Claude Code Documentation](https://docs.claude.com/en/docs/claude-code)
- [OpenAI Codex Documentation](https://developers.openai.com/codex)
- [VS Code Agent Skills Guide](https://code.visualstudio.com/docs/copilot/customization/agent-skills)

## Support

For issues, questions, or suggestions, please open an issue on GitHub at [https://github.com/johannes-engler-mw/helm-gitops-skill](https://github.com/johannes-engler-mw/helm-gitops-skill).
