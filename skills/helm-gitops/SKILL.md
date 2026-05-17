---
name: helm-gitops
description: Deploy official Helm charts for open source applications to Kubernetes via GitOps. Supports both ArgoCD and FluxCD. Use when the user wants to add Helm-based applications (monitoring, API gateways, ingress controllers, cert-manager, databases, etc.) to their GitOps repository. Triggers include requests to deploy, install, or add Helm charts through ArgoCD or Flux.
license: MIT
compatibility: Requires kubectl for secrets detection; works with Claude Code, OpenAI Codex, and agentskills.io-compatible platforms
metadata:
  author: Johannes Engler
  version: "2.0.0"
---

# Helm GitOps Deployment Skill

You already know how to read a repo, pick a layout, and write a HelmRelease or Application. This skill exists for the parts that are easy to get subtly wrong: chart version currency, tool-aware secrets choices, validation, and a handful of named gotchas. Follow your normal workflow and let this skill correct you on those points.

## Always WebSearch for the chart — don't pin from training data

Helm chart versions, repo URLs, and even chart ownership change frequently. Examples we've watched bite people: Loki was forked from `grafana/loki` to `grafana-community/loki` in March 2026; APISIX moved repo hosts; kube-prometheus-stack majors ship breaking changes every few months.

Required searches before generating manifests:

- `{app-name} official helm chart` — repo URL + chart name
- `{app-name} helm chart artifacthub` — current version
- `{app-name} helm secrets values` — which values are sensitive

If WebSearch errors or returns nothing, **surface that to the user** rather than silently pinning a version you remember. A wrong-but-confident version is worse than asking.

**Pin the version your search returned, not an older one you remember being stable.** It is tempting to find `85.1.1` and pin `65.x` as a "well-tested baseline." Don't. The user chose to deploy now. If you have a real concern about the latest (known regression, breaking changelog), note it in SUMMARY.md and let the user downgrade. Default to current.

## Pick the tool from the repo, not from the user

Grep the repo first; ask only if ambiguous:

```bash
grep -rE "kind: (HelmRelease|Application)" --include="*.yaml" --include="*.yml" -l 2>/dev/null | head -5
```

Exactly one match → name it back to the user and proceed. Both/neither → ask.

Match the existing folder convention. For greenfield repos with no convention, prefer per-component directories (`infra/<app>/{namespace,helmrepository,helmrelease,kustomization}.yaml`) — easier to add/remove apps cleanly.

## Detect secrets management before generating values

Secrets choice is tool-aware, so do this **after** the tool is settled. Run these in parallel:

```bash
# Cluster — what's installed
kubectl get crd externalsecrets.external-secrets.io 2>/dev/null
kubectl get crd sealedsecrets.bitnami.com 2>/dev/null

# Repo — what's already in use
grep -rE "kind: (ExternalSecret|SecretStore|ClusterSecretStore)" --include="*.yaml" -l 2>/dev/null | head
grep -r "kind: SealedSecret" --include="*.yaml" -l 2>/dev/null | head
grep -rE "sops:|ENC\[AES256_GCM|provider: sops" --include="*.yaml" -l 2>/dev/null | head
```

Decision rules:

1. ESO in cluster AND repo → ESO
2. Sealed Secrets in cluster AND repo → Sealed Secrets
3. SOPS in repo AND tool is Flux → SOPS (native via `Kustomization.spec.decryption`)
4. SOPS in repo AND tool is ArgoCD → **ask, don't assume**. SOPS on ArgoCD needs `argocd-vault-plugin` or `helm-secrets` sidecar. Suggest ESO or Sealed Secrets unless the user confirms a plugin is configured.
5. Multiple solutions detected → ask with usage context
6. Nothing detected → ask. For Flux, list SOPS as option 3; for ArgoCD, omit SOPS from the default list (mention only as a footnote requiring a plugin)

If the chart supports `existingSecret` / `auth.existingSecret`, prefer that pattern over `valuesFrom` — cleaner and chart-idiomatic. The web search in step 1 should have surfaced this.

**Never write a real-looking secret value into Git.** Placeholder Secrets get an explicit warning header and a `# REPLACE THIS` value; never something that looks like a real token.

## Gotchas to verify before saving

These bite repeatedly:

- **FluxCD HelmRepository namespace** — if you use a namespace-scoped `HelmRepository` (recommended for isolation), `HelmRelease.spec.chart.spec.sourceRef.namespace` must match the `HelmRepository.metadata.namespace`. Mismatch silently breaks reconciliation.
- **FluxCD CRD handling** — `install.crds: CreateReplace` and `upgrade.crds: CreateReplace` are usually what you want for charts that ship CRDs (cert-manager, kube-prometheus-stack). Without these, CRD upgrades are skipped.
- **Combined charts** — if a chart bundles components (APISIX = gateway + ingress-controller; kube-prometheus-stack = Prometheus + Grafana + Alertmanager; Kong = gateway + ingress), enable the sub-components via nested values. Do **not** deploy them as separate Helm releases.
- **Minimal values overrides** — only specify values that differ from chart defaults. Inline-duplicating defaults makes upgrades fragile.

## Use the bundled examples as few-shot anchors

Before writing manifests from scratch, look at the closest matching example — they reflect the file layout, label set, and kustomization wiring this skill expects:

- `examples/argocd/apisix-api-gateway/` — Application with combined gateway + ingress + etcd
- `examples/argocd/postgresql-eso/` — Application + ESO `ExternalSecret` + `SecretStore`
- `examples/fluxcd/apisix-api-gateway/` — HelmRepository + HelmRelease + Kustomization
- `examples/fluxcd/postgresql-eso/` — same plus ESO

If your shape doesn't match any example, see [references/argocd.md](references/argocd.md) or [references/flux.md](references/flux.md) for fuller templates.

## Validate before declaring done

Generated YAML is cheap; broken YAML applied at 2am is not. Validate with the rendered form, not the raw HelmRelease:

```bash
# Per-file syntax/schema
kubectl apply --dry-run=client -f <file>.yaml

# Whole directory via kustomize
kubectl kustomize <dir> | kubectl apply --dry-run=client -f -

# Optional: render the chart to inspect actual rendered output
helm template <release-name> <chart> --version <version> --values <values.yaml>
```

If `kubectl` isn't available, fall back to `kubeconform` or `kubeval`. If none are available, say so to the user — don't silently skip.

After validation passes, save to the detected/agreed location and tell the user:

- Which files were created and where
- How to apply or sync (e.g., `flux reconcile kustomization <name>` or `argocd app sync <name>`)
- Post-deployment verification — see the Debugging sections of [references/argocd.md](references/argocd.md) / [references/flux.md](references/flux.md)

## Error handling

For unusual situations (deprecated chart, ambiguous repo layout, missing CRD dependencies, cluster not reachable for secrets detection), see [references/error-handling.md](references/error-handling.md).

Default principle: **don't guess** — surface the ambiguity with clear options and a recommendation.
