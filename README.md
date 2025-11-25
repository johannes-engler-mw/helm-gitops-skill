# Helm GitOps Deployment Skill

A Claude Code skill for deploying official Helm charts to Kubernetes clusters using GitOps principles with ArgoCD or FluxCD.

## What It Does

This skill automates the process of adding Helm-based applications to your GitOps repository by:

1. Identifying the application from your natural language request
2. Finding official Helm charts and repository information via web search
3. Detecting your existing GitOps repository structure and conventions
4. Asking for deployment method preference (ArgoCD or FluxCD)
5. Generating appropriate manifest files (Application or HelmRelease CRDs)
6. Placing files in the correct location matching your repository patterns

The skill handles common deployment scenarios including monitoring tools, API gateways, ingress controllers, cert-manager, databases, and any Helm-charted open-source applications.

## Installation

```bash
# From marketplace (when published)
/plugin marketplace add johannes-engler-mw/helm-gitops-skill
/plugin install helm-gitops

# Or from GitHub URL
/plugin marketplace add https://github.com/johannes-engler-mw/helm-gitops-skill.git
/plugin install helm-gitops

# Or manually (clone first, then copy to your home directory)
git clone https://github.com/johannes-engler-mw/helm-gitops-skill.git
mkdir -p ~/.claude/skills
cp -r helm-gitops-skill/helm-gitops/ ~/.claude/skills/
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
├── helm-gitops/
│   ├── SKILL.md                    # Main skill definition with workflow
│   └── references/                 # Detailed reference documentation
│       ├── argocd.md               # ArgoCD deployment patterns
│       ├── flux.md                 # FluxCD deployment patterns
│       └── deployment-modes.md     # Standalone vs clustered deployments
├── examples/                       # Example use cases
│   ├── argocd/                     # ArgoCD examples
│   │   ├── apisix-api-gateway/
│   │   ├── kube-prometheus-stack/
│   │   └── nginx-ingress/
│   └── fluxcd/                     # FluxCD examples
│       ├── apisix-api-gateway/
│       ├── kube-prometheus-stack/
│       └── nginx-ingress/
├── README.md
├── LICENSE
├── CHANGELOG.md
├── prpm.json
└── .gitignore
```

## Key Features

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

- Claude Code 1.0 or higher
- Existing GitOps repository (ArgoCD or FluxCD configured)
- Kubernetes cluster with kubectl access
- Git repository for GitOps manifests

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

MIT License - see [LICENSE](LICENSE) file for details

## Resources

- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
- [FluxCD Documentation](https://fluxcd.io/flux/)
- [Helm Charts - ArtifactHub](https://artifacthub.io/)
- [Claude Code Documentation](https://docs.claude.com/en/docs/claude-code)
- [GitOps Principles](https://opengitops.dev/)

## Support

For issues, questions, or suggestions, please open an issue on GitHub at [https://github.com/johannes-engler-mw/helm-gitops-skill](https://github.com/johannes-engler-mw/helm-gitops-skill).
