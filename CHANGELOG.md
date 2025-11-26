# Changelog

All notable changes to the Helm GitOps Deployment Skill will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
### Changed
### Fixed

## [1.1.0] - 2025-11-26

### Added
- **Automatic Secrets Management Detection** - Three-layer detection strategy (cluster kubectl checks, repository pattern search, chart-specific secrets discovery)
- **Support for Multiple Secrets Solutions**:
  - External Secrets Operator (ESO) - Syncs from Vault, AWS, GCP, Azure
  - Sealed Secrets - Encrypts secrets for Git storage
  - SOPS - Encrypts values files (native Flux support)
  - Native Kubernetes Secrets - Development/testing with warnings
- **Web Search Integration for Secrets** - Uses web search for current implementation details instead of bundled docs (token-efficient approach)
- **Adaptive Manifest Generation**:
  - ExternalSecret + SecretStore for ESO
  - SealedSecret templates with kubeseal commands
  - SOPS-encrypted files with Flux Kustomization decryption
  - Native Secret templates with migration recommendations
- **Minimal Example** - PostgreSQL with ESO integration (`examples/fluxcd/postgresql-eso/`)

### Changed
- **SKILL.md** - Added Step 3.5 (Detect Secrets Management) between repository detection and deployment method
- **SKILL.md Step 2** - Enhanced with secrets-focused search queries
- **SKILL.md Step 5** - Added secrets adaptation patterns with web search strategy
- **flux.md & argocd.md** - Added minimal secrets integration sections (~20 lines each) with web search references
- **CLAUDE.md** - Added secrets detection strategy documentation
- **README.md** - Added Intelligent Secrets Management feature highlight
- **Token Efficiency** - Uses web search for implementation details instead of bundled documentation

### Removed
- Bundled secrets reference files (reduced ~2,400 lines) - Now uses web search for current patterns

### Security
- Never stores plaintext secrets in Git
- Generates encrypted/reference-based resources (ExternalSecret, SealedSecret, SOPS-encrypted)
- Strong warnings for native secrets in production
- Recommends ESO or Sealed Secrets for production workloads

## [1.0.0] - 2025-11-25

### Added
- Initial release of Helm GitOps Deployment skill
- 6-step workflow for deploying Helm charts via GitOps
- Multi-tool support (ArgoCD and FluxCD)
- Web search integration for finding official Helm charts
- Automatic repository structure detection
- Support for multiple repository patterns:
  - By type (infrastructure/controllers, infrastructure/monitoring)
  - By environment (clusters/production, clusters/staging)
  - Flat structure (manifests/)
  - Component-based (infra/service-name/)
- Combined chart pattern support:
  - APISIX (gateway + ingress-controller)
  - kube-prometheus-stack (Prometheus + Grafana + Alertmanager)
  - Kong (gateway + ingress controller)
- Alpha/Beta feature handling with documentation
- Additional CRD deployment support (Gateway API, Service Mesh, Certificates)
- Comprehensive reference documentation:
  - ArgoCD deployment patterns and best practices
  - FluxCD deployment patterns and best practices
  - Deployment modes (standalone vs clustered)
- Chart version pinning for reproducibility
- Namespace creation and management
- Dependency handling (e.g., etcd for APISIX)
- Standard Kubernetes labeling (app.kubernetes.io/*)
- Resource requests/limits recommendations
- Post-deployment verification steps
- Debugging commands for both ArgoCD and FluxCD

### Features
- Natural language application identification
- Official Helm chart repository detection
- Intelligent defaults with clear customization points
- Multi-source application support (ArgoCD)
- ApplicationSet support for multi-environment deployments
- HelmRepository configuration (global and namespace-scoped)
- ConfigMap/Secret values integration
- NodePort configuration for local clusters
- Kustomization integration for FluxCD
- App-of-Apps pattern support

### Documentation
- Comprehensive README with installation and usage instructions
- MIT License
- Repository structure documentation
- Example structures for both ArgoCD and FluxCD
- Best practices for GitOps deployments
- Support for monitoring, API gateways, ingress controllers, cert-manager, databases, and more

---

## Versioning Strategy

This project uses [Semantic Versioning](https://semver.org/):
- **MAJOR** version for incompatible API changes
- **MINOR** version for added functionality in a backward compatible manner
- **PATCH** version for backward compatible bug fixes

## Categories

- **Added**: New features
- **Changed**: Changes in existing functionality
- **Deprecated**: Soon-to-be removed features
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Vulnerability fixes
