# GitOps repo (test fixture)

This is the GitOps repository for our Kubernetes cluster. We use FluxCD and organize infrastructure component-by-component under `infra/`.

Secrets are managed via External Secrets Operator, backed by HashiCorp Vault. The ESO connection lives under `infra/external-secrets/`.
