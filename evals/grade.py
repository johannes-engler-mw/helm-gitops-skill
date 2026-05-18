#!/usr/bin/env python3
"""
Grades each run in helm-gitops-workspace/iteration-N/eval-*/{with_skill,without_skill}/
against the assertions in eval_metadata.json.

Writes grading.json per run with fields { eval_id, eval_name, expectations: [{text, passed, evidence}] }.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path("/Users/johannes.engler/repos/helm-gitops-skill")
ITERATION_DIR = ROOT / "helm-gitops-workspace" / (sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith("iteration-") else "iteration-1")


def read_all_files(root: Path) -> dict[str, str]:
    """Return {relative_path: content} for every file under root."""
    out: dict[str, str] = {}
    if not root.exists():
        return out
    for p in root.rglob("*"):
        if p.is_file():
            try:
                out[str(p.relative_to(root))] = p.read_text(errors="replace")
            except Exception:
                pass
    return out


def has_file(files: dict[str, str], pattern: str) -> tuple[bool, str]:
    """Check if any file path matches a regex pattern. Returns (matched, evidence)."""
    matches = [p for p in files if re.search(pattern, p)]
    return (bool(matches), f"matched: {matches[:3]}" if matches else f"no file matched '{pattern}'")


def has_in_any(files: dict[str, str], needle: str, *, ignore_case: bool = False) -> tuple[bool, str]:
    """Check if substring is in any file's content. Returns (matched, evidence)."""
    flags = re.IGNORECASE if ignore_case else 0
    pat = re.compile(re.escape(needle), flags)
    hits = []
    for path, content in files.items():
        if pat.search(content):
            hits.append(path)
    return (bool(hits), f"found in: {hits[:3]}" if hits else f"'{needle}' not found in any file")


def regex_in_any(files: dict[str, str], pattern: str, *, ignore_case: bool = False) -> tuple[bool, str]:
    flags = re.MULTILINE | (re.IGNORECASE if ignore_case else 0)
    pat = re.compile(pattern, flags)
    hits = []
    for path, content in files.items():
        if pat.search(content):
            hits.append(path)
    return (bool(hits), f"matched in: {hits[:3]}" if hits else f"pattern /{pattern}/ not found")


def regex_count_in_any(files: dict[str, str], pattern: str, *, ignore_case: bool = False) -> int:
    flags = re.IGNORECASE if ignore_case else 0
    pat = re.compile(pattern, flags)
    return sum(len(pat.findall(c)) for c in files.values())


# =========================================================================
# Per-eval graders
# =========================================================================


def grade_eval_1(outputs_dir: Path) -> list[dict]:
    files = read_all_files(outputs_dir)
    # SUMMARY content (may not exist)
    summary = next((c for p, c in files.items() if p.lower().endswith("summary.md")), "")

    results: list[dict] = []

    # picked_flux
    ok = regex_in_any(files, r"^kind:\s*HelmRelease", ignore_case=False)
    not_argo = not regex_in_any(files, r"^kind:\s*Application\b", ignore_case=False)[0]
    results.append({
        "text": "Generated manifests use FluxCD (kind: HelmRelease), not ArgoCD",
        "passed": ok[0] and not_argo,
        "evidence": f"{ok[1]}; no ArgoCD Application={not_argo}",
    })

    # pattern_d_layout (files under infra/loki/)
    ok = any(p.startswith("infra/loki/") or p.startswith("outputs/infra/loki/") or "/infra/loki/" in p for p in files)
    results.append({
        "text": "Files written under infra/loki/ to match Pattern D component-based layout",
        "passed": ok,
        "evidence": f"loki dir files: {[p for p in files if '/loki/' in p or p.startswith('infra/loki/')][:3]}",
    })

    # kustomization_present
    ok = any(p.endswith("kustomization.yaml") and "/loki/" in p for p in files) or any(
        p.endswith("kustomization.yaml") and "loki" in p for p in files
    )
    # broader fallback
    if not ok:
        ok = any(p.endswith("kustomization.yaml") for p in files)
    results.append({
        "text": "kustomization.yaml present in the new loki directory",
        "passed": ok,
        "evidence": f"found: {[p for p in files if 'kustomization' in p.lower()][:3]}",
    })

    # helmrepository_present
    ok = regex_in_any(files, r"^kind:\s*HelmRepository")
    results.append({
        "text": "HelmRepository resource generated (Grafana charts repo)",
        "passed": ok[0],
        "evidence": ok[1],
    })

    # chart_version_pinned: look for version: "X.Y.Z" or version: X.Y.Z, not 'latest' or empty
    pinned = regex_in_any(files, r"\bversion:\s*[\"']?\d+\.\d+\.\d+")
    has_latest = regex_in_any(files, r"\bversion:\s*[\"']?latest[\"']?\s*$", ignore_case=True)
    results.append({
        "text": "HelmRelease chart.spec.version is a specific pinned version",
        "passed": pinned[0] and not has_latest[0],
        "evidence": f"{pinned[1]}; has 'latest'={has_latest[0]}",
    })

    # persistence_50gi
    ok = regex_in_any(files, r"\b50Gi\b")
    results.append({
        "text": "Loki persistence configured at 50Gi as requested",
        "passed": ok[0],
        "evidence": ok[1],
    })

    # chart_version_current — pinned Loki chart version should be reasonably current as of grading.
    # As of May 2026: grafana-community/loki at 14.x (forked Mar 2026 — the canonical OSS chart now)
    # or grafana/loki at 7.x (now GEL-focused). Anything below floor implies stale training-knowledge.
    def _version_tuple(s: str) -> tuple[int, ...]:
        m = re.match(r"v?(\d+)\.(\d+)\.(\d+)", s.strip())
        return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)
    version_match = regex_in_any(files, r"\bversion:\s*[\"']?(\d+\.\d+\.\d+)")
    found_version = None
    for content in files.values():
        m = re.search(r"\bversion:\s*[\"']?(\d+\.\d+\.\d+)", content)
        if m:
            found_version = m.group(1)
            break
    uses_community_chart = has_in_any(files, "grafana-community")[0] or has_in_any(files, "community/loki")[0]
    if found_version is None:
        passed = False
        evidence = "no version found"
    else:
        v = _version_tuple(found_version)
        # Accept >= 13.0.0 (community fork) OR >= 6.5.0 in old repo (lenient: still close to 7.0.0)
        # Strict signal: community fork repo + version >= 13.x
        passed = (uses_community_chart and v >= (13, 0, 0)) or v >= (7, 0, 0)
        evidence = f"version={found_version}, uses_community_chart={uses_community_chart}"
    results.append({
        "text": "Chart version is current (Loki forked to grafana-community in Mar 2026; current is 14.x community / 7.x grafana)",
        "passed": passed,
        "evidence": evidence,
    })

    # no_unneeded_externalsecret — Loki with filesystem storage doesn't need an ExternalSecret.
    # Skill should correctly choose NOT to generate one. Note: this checks outputs/, not the fixture.
    has_es = regex_in_any(files, r"^kind:\s*ExternalSecret\b")
    results.append({
        "text": "No unnecessary ExternalSecret generated (Loki with filesystem storage needs no secrets)",
        "passed": not has_es[0],
        "evidence": "ExternalSecret correctly omitted" if not has_es[0] else f"unexpected ExternalSecret found: {has_es[1]}",
    })

    # namespace_present
    ok = any(p.endswith("namespace.yaml") and "/loki/" in p for p in files)
    if not ok:
        ok = any(p.endswith("namespace.yaml") for p in files)
    results.append({
        "text": "namespace.yaml generated for the new loki namespace",
        "passed": ok,
        "evidence": f"found: {[p for p in files if 'namespace' in p.lower()][:3]}",
    })

    return results


def grade_eval_2(outputs_dir: Path) -> list[dict]:
    files = read_all_files(outputs_dir)
    summary = next((c for p, c in files.items() if p.lower().endswith("summary.md")), "")

    results: list[dict] = []

    # picked_argocd
    ok = regex_in_any(files, r"^kind:\s*Application\b")
    no_flux_release = not regex_in_any(files, r"^kind:\s*HelmRelease")[0]
    results.append({
        "text": "Generated manifests use ArgoCD (kind: Application), not Flux",
        "passed": ok[0] and no_flux_release,
        "evidence": f"{ok[1]}; no Flux HelmRelease={no_flux_release}",
    })

    # argocd_apps_path
    ok = any(("argocd/apps/" in p) for p in files)
    results.append({
        "text": "cert-manager Application placed under argocd/apps/",
        "passed": ok,
        "evidence": f"argocd/apps/* files: {[p for p in files if 'argocd/apps' in p][:3]}",
    })

    # chart_version_pinned: targetRevision with vX.Y.Z
    ok = regex_in_any(files, r"targetRevision:\s*[\"']?v?\d+\.\d+\.\d+")
    results.append({
        "text": "Application's targetRevision is a specific pinned chart version",
        "passed": ok[0],
        "evidence": ok[1],
    })

    # cloudflare_dns01_clusterissuer
    has_clusterissuer = regex_in_any(files, r"^kind:\s*(Cluster)?Issuer\b")
    has_cloudflare = has_in_any(files, "cloudflare", ignore_case=True)
    has_dns01 = has_in_any(files, "dns01", ignore_case=True)
    results.append({
        "text": "ClusterIssuer/Issuer with Cloudflare DNS01 solver generated",
        "passed": has_clusterissuer[0] and has_cloudflare[0] and has_dns01[0],
        "evidence": f"issuer={has_clusterissuer[0]}, cloudflare={has_cloudflare[0]}, dns01={has_dns01[0]}",
    })

    # cloudflare_token_via_secret: apiTokenSecretRef referencing a Secret
    via_secret = regex_in_any(files, r"apiTokenSecretRef|apiKeySecretRef|tokenSecretRef")
    # bad: plaintext token in yaml (look for `apiToken:` directly with non-secret-ref value)
    plaintext = regex_in_any(files, r"apiToken:\s*[\"']?[A-Za-z0-9_-]{10,}[\"']?\s*$")
    results.append({
        "text": "Cloudflare API token referenced via Secret (apiTokenSecretRef), not plaintext",
        "passed": via_secret[0] and not plaintext[0],
        "evidence": f"{via_secret[1]}; plaintext_inline={plaintext[0]}",
    })

    # chart_version_current — pinned cert-manager chart version should be reasonably current.
    # As of May 2026: latest is v1.20.2. Accept >= v1.18.0 (within ~2 minor versions).
    found_version = None
    for content in files.values():
        m = re.search(r"targetRevision:\s*[\"']?v?(\d+\.\d+\.\d+)", content)
        if m:
            found_version = m.group(1)
            break
    if found_version is None:
        passed = False
        evidence = "no targetRevision version found"
    else:
        major, minor, _patch = (int(x) for x in found_version.split("."))
        passed = (major, minor) >= (1, 18)
        evidence = f"targetRevision={found_version} (floor: v1.18.x; current: v1.20.2)"
    results.append({
        "text": "cert-manager chart version is current (within ~2 minors of v1.20.2 as of May 2026)",
        "passed": passed,
        "evidence": evidence,
    })

    # cloudflare_secret_is_placeholder — any generated Secret holding a Cloudflare API token
    # should contain a placeholder value (not a real-looking token) AND a warning comment.
    cf_secret_files = [
        (p, c) for p, c in files.items()
        if "cloudflare" in p.lower() or ("kind: Secret" in c and re.search(r"cloudflare", c, re.IGNORECASE))
    ]
    if not cf_secret_files:
        # No Cloudflare-named secret found — check if any Secret references cloudflare-api-token via apiTokenSecretRef.name
        # If there's no actual Secret manifest at all (template-only via SUMMARY), that's also OK.
        # Pass conservatively: this assertion is about avoiding committing real tokens.
        results.append({
            "text": "Cloudflare API token Secret (if generated) contains a placeholder, not a real-looking token",
            "passed": True,
            "evidence": "no Cloudflare-named Secret file found (apiTokenSecretRef pointing at out-of-band Secret is OK)",
        })
    else:
        placeholder_pat = re.compile(r"(PLACEHOLDER|YOUR[_-]|REPLACE[_-]?ME|your[_-]?token|changeme|<token>|<api[_-]?token>|example[_-]?token|TODO)", re.IGNORECASE)
        warning_pat = re.compile(r"(#\s*(WARNING|DO NOT|placeholder|TODO|replace))", re.IGNORECASE)
        any_safe = False
        any_unsafe = False
        for path, content in cf_secret_files:
            if placeholder_pat.search(content) and warning_pat.search(content):
                any_safe = True
            elif re.search(r"apiToken:\s*[\"']?[A-Za-z0-9_-]{20,}[\"']?", content):
                any_unsafe = True
        passed = any_safe and not any_unsafe
        results.append({
            "text": "Cloudflare API token Secret (if generated) contains a placeholder, not a real-looking token",
            "passed": passed,
            "evidence": f"placeholder+warning found={any_safe}, real-looking token detected={any_unsafe}",
        })

    # crd_install_handled — handle both inline (installCRDs: true) and nested (crds:\n  enabled: true)
    has_install_crds = (
        has_in_any(files, "installCRDs: true")[0]
        or regex_in_any(files, r"crds:\s*\n\s*enabled:\s*true")[0]
    )
    has_ssa = regex_in_any(files, r"ServerSideApply\s*=\s*true|ServerSideApply:\s*true")
    results.append({
        "text": "CRDs handled (installCRDs:true or ServerSideApply=true)",
        "passed": bool(has_install_crds) or has_ssa[0],
        "evidence": f"installCRDs/crds.enabled={bool(has_install_crds)}, ServerSideApply={has_ssa[0]}",
    })

    return results


def grade_eval_3(outputs_dir: Path) -> list[dict]:
    files = read_all_files(outputs_dir)
    summary = next((c for p, c in files.items() if p.lower().endswith("summary.md")), "")

    results: list[dict] = []

    # chart_version_current — pinned kube-prometheus-stack version should be reasonably current.
    # As of May 2026: latest is 85.x. Accept >= 80.0.0 (within ~5 minors).
    found_version = None
    for content in files.values():
        m = re.search(r"\b(version|targetRevision):\s*[\"']?v?(\d+\.\d+\.\d+)", content)
        if m and "kube-prometheus-stack" in content:
            found_version = m.group(2)
            break
    if found_version is None:
        # Fallback: any version in the file
        for content in files.values():
            m = re.search(r"\b(version|targetRevision):\s*[\"']?v?(\d+\.\d+\.\d+)", content)
            if m:
                found_version = m.group(2)
                break
    if found_version is None:
        passed = False
        evidence = "no version found"
    else:
        major = int(found_version.split(".")[0])
        passed = major >= 80
        evidence = f"version={found_version} (floor: 80.x; current: ~85.x)"
    results.append({
        "text": "kube-prometheus-stack chart version is current (within ~5 minors of 85.x as of May 2026)",
        "passed": passed,
        "evidence": evidence,
    })

    # uses_kube_prometheus_stack
    kps = has_in_any(files, "kube-prometheus-stack")
    # negative signal: two separate charts
    sep_grafana = has_in_any(files, "chart: grafana") and not kps[0]
    results.append({
        "text": "Uses combined kube-prometheus-stack chart (not two separate Prometheus+Grafana charts)",
        "passed": kps[0],
        "evidence": kps[1],
    })

    # pattern_d_recommended — verify by directory structure only (manifest-based).
    # Accept any nesting under infra/ or infrastructure/ — both `infra/monitoring/helmrelease.yaml`
    # and `infrastructure/monitoring/kube-prometheus-stack/helmrelease.yaml` count as component grouping.
    component_dir_pat = re.compile(r"(infra|infrastructure)(/[^/]+)+/(helmrelease|application|kustomization|namespace)\.yaml", re.IGNORECASE)
    has_component_dir = any(component_dir_pat.search(p) for p in files)
    results.append({
        "text": "Output structure groups manifests in a component directory under infra/ or infrastructure/",
        "passed": has_component_dir,
        "evidence": f"component dir layout: {has_component_dir}",
    })

    # chart_version_pinned
    pinned = regex_in_any(files, r"\b(version|targetRevision):\s*[\"']?v?\d+\.\d+\.\d+")
    results.append({
        "text": "Chart version pinned to a specific release",
        "passed": pinned[0],
        "evidence": pinned[1],
    })

    # manifests_match_chosen_tool: no mixing of CRDs
    has_argo = regex_in_any(files, r"^kind:\s*Application\b")
    has_flux = regex_in_any(files, r"^kind:\s*HelmRelease")
    no_mix = not (has_argo[0] and has_flux[0])
    has_one = has_argo[0] or has_flux[0]
    results.append({
        "text": "Manifests use CRDs of one tool (no mixing of ArgoCD Application and Flux HelmRelease)",
        "passed": no_mix and has_one,
        "evidence": f"argocd={has_argo[0]}, flux={has_flux[0]}",
    })

    # no_unrequested_grafana_creds — user asked for monitoring, not credential management.
    # kube-prometheus-stack auto-generates a random Grafana admin Secret on install. Any
    # placeholder Secret, inline adminPassword, or existingSecret reference is anticipation
    # the user didn't ask for. See SKILL.md "user didn't mention auth/credentials" rule.
    defects: list[str] = []
    for path, content in files.items():
        # inline adminPassword in HelmRelease values (or ArgoCD helm.values blob)
        for m in re.finditer(r"^\s*adminPassword:\s*[\"']?([^\"'\n#]+)", content, re.MULTILINE):
            defects.append(f"{path}: inline adminPassword={m.group(1).strip()!r}")
        # Grafana-scoped existingSecret reference (anticipation in values block)
        if re.search(r"grafana", content, re.IGNORECASE):
            for m in re.finditer(r"existingSecret:\s*[\"']?([^\s\"']+)", content):
                defects.append(f"{path}: grafana existingSecret={m.group(1)!r}")
        # Standalone Secret/ExternalSecret/SealedSecret carrying grafana admin credentials
        for doc in _parse_yaml_docs(content):
            kind = doc.get("kind")
            if kind not in ("Secret", "ExternalSecret", "SealedSecret"):
                continue
            name = ((doc.get("metadata") or {}).get("name") or "").lower()
            if "grafana" in name and ("admin" in name or "credential" in name or "password" in name):
                defects.append(f"{path}: unrequested {kind} {name!r}")
                continue
            for field in ("data", "stringData"):
                block = doc.get(field) or {}
                if any(re.search(r"admin[-_]?password", k, re.IGNORECASE) for k in block):
                    defects.append(f"{path}: {kind} contains admin-password key")
                    break
    results.append({
        "text": "No unrequested Grafana credential resources (chart auto-generates admin Secret; user asked for monitoring, not credential management)",
        "passed": not defects,
        "evidence": "; ".join(defects[:3]) if defects else "no Grafana credential anticipation detected",
    })

    return results


def _has_inline_aws_creds(files: dict[str, str]) -> list[str]:
    """Detect AWS access key / secret access key inlined into manifest values blocks
    (HelmRelease.spec.values or ArgoCD Application.spec.source.helm.values). Returns a
    list of evidence strings. Plain Secret resources are NOT a defect — only inlined
    values are. Anchored on the *value*, not the key name."""
    inline: list[str] = []
    key_pat = re.compile(
        r"^\s*(AWS_ACCESS_KEY_ID|aws_access_key_id|access_key_id|AWS_SECRET_ACCESS_KEY|aws_secret_access_key|secret_access_key|accessKey|secretKey)\s*:\s*[\"']?([^\"'\s#]+)",
        re.MULTILINE,
    )
    for path, content in files.items():
        # Skip files that ARE a Secret resource — values inside the Secret are expected
        if re.search(r"^kind:\s*Secret\b", content, re.MULTILINE):
            continue
        for m in key_pat.finditer(content):
            val = m.group(2).strip()
            # Pointer fields like `*KeyRef`, `valueFrom`, `secretKeyRef` are not values
            # The line preceding may also indicate a valueFrom block — check 200 chars back
            ctx_start = max(0, m.start() - 200)
            ctx = content[ctx_start:m.end()]
            if re.search(r"valueFrom|secretKeyRef|envFrom|existingSecret", ctx):
                continue
            # Skip if value itself names a Secret ref (e.g. value: aws-credentials)
            if PLACEHOLDER_MARKERS.search(val):
                continue
            if len(val) >= 4 and not val.endswith("Ref") and not val in ("aws", "true", "false"):
                inline.append(f"{path}: {m.group(1)}={val[:24]!r}")
    return inline


def grade_eval_4(outputs_dir: Path) -> list[dict]:
    """Loki with S3 backend — chart REQUIRES user-supplied AWS credentials.
    Confirms skill still generates a secret resource when chart truly needs one,
    and prefers ExternalSecret since ESO is in the fixture repo."""
    files = read_all_files(outputs_dir)
    results: list[dict] = []

    # picked_flux
    has_flux = regex_in_any(files, r"^kind:\s*HelmRelease")[0]
    no_argo = not regex_in_any(files, r"^kind:\s*Application\b")[0]
    results.append({
        "text": "Generated manifests use FluxCD (kind: HelmRelease), not ArgoCD",
        "passed": has_flux and no_argo,
        "evidence": f"HelmRelease={has_flux}, no ArgoCD={no_argo}",
    })

    # pattern_d_layout
    in_loki = any("/loki/" in p or p.startswith("infra/loki/") for p in files)
    results.append({
        "text": "Files written under infra/loki/ (Pattern D)",
        "passed": in_loki,
        "evidence": f"loki dir files: {[p for p in files if 'loki' in p.lower()][:3]}",
    })

    # loki_s3_backend_configured
    has_bucket = has_in_any(files, "my-logs-2026")[0]
    has_s3 = (
        regex_in_any(files, r"\bs3:\s*$", ignore_case=False)[0]
        or regex_in_any(files, r"\btype:\s*[\"']?s3\b", ignore_case=True)[0]
        or regex_in_any(files, r"\bbackend:\s*[\"']?s3\b", ignore_case=True)[0]
    )
    has_region = has_in_any(files, "us-east-1")[0]
    results.append({
        "text": "Loki configured with S3 backend (bucket my-logs-2026, region us-east-1)",
        "passed": has_bucket and has_s3 and has_region,
        "evidence": f"bucket_named={has_bucket}, s3_config={has_s3}, region={has_region}",
    })

    # chart_version_pinned_current
    found_version = None
    for content in files.values():
        m = re.search(r"\bversion:\s*[\"']?(\d+\.\d+\.\d+)", content)
        if m:
            found_version = m.group(1)
            break
    if found_version is None:
        passed = False
        evidence = "no version found"
    else:
        v = tuple(int(x) for x in found_version.split("."))
        uses_community = has_in_any(files, "grafana-community")[0] or has_in_any(files, "community/loki")[0]
        passed = (uses_community and v >= (13, 0, 0)) or v >= (7, 0, 0)
        evidence = f"version={found_version}, uses_community={uses_community}"
    results.append({
        "text": "Loki chart version is pinned and current (community 14.x or grafana 7.x as of May 2026)",
        "passed": passed,
        "evidence": evidence,
    })

    # secret_resource_generated — the regression test
    has_secret = regex_in_any(files, r"^kind:\s*(Secret|ExternalSecret|SealedSecret)\b")[0]
    results.append({
        "text": "Secret/ExternalSecret/SealedSecret resource generated (chart requires AWS creds when S3 backend is enabled)",
        "passed": has_secret,
        "evidence": "secret resource present" if has_secret else "no secret resource — chart cannot reach S3 without AWS creds",
    })

    # prefers_eso_when_available
    has_es = regex_in_any(files, r"^kind:\s*ExternalSecret\b")[0]
    results.append({
        "text": "Generated secret is an ExternalSecret (ESO is installed in the fixture repo)",
        "passed": has_es,
        "evidence": "ExternalSecret found" if has_es else "no ExternalSecret — skill missed ESO preference from repo detection",
    })

    # no_inline_aws_creds
    inline = _has_inline_aws_creds(files)
    results.append({
        "text": "AWS credentials are NOT inlined into HelmRelease values",
        "passed": not inline,
        "evidence": "; ".join(inline[:3]) if inline else "no inline AWS credentials detected",
    })

    return results


def grade_eval_5(outputs_dir: Path) -> list[dict]:
    """PostgreSQL with explicit Secret-managed auth.
    User explicitly asks for credential management via Kubernetes Secret. Confirms skill
    generates a secret resource and uses existingSecret pattern (no inline auth.password)."""
    files = read_all_files(outputs_dir)
    results: list[dict] = []

    # picked_flux
    has_flux = regex_in_any(files, r"^kind:\s*HelmRelease")[0]
    results.append({
        "text": "Generated manifests use FluxCD (kind: HelmRelease)",
        "passed": has_flux,
        "evidence": "HelmRelease found" if has_flux else "no HelmRelease found",
    })

    # pattern_d_layout — accept any infra/<dir>/ structure (postgres, postgresql, db, etc.)
    component_dir_pat = re.compile(r"^(infra|infrastructure)/[^/]+/", re.IGNORECASE)
    in_component_dir = any(component_dir_pat.search(p) for p in files)
    results.append({
        "text": "Files written under infra/<postgres-dir>/ (Pattern D)",
        "passed": in_component_dir,
        "evidence": f"component dir files: {[p for p in files if component_dir_pat.search(p)][:3]}",
    })

    # uses_existing_secret_pattern — auth.existingSecret or auth.existingSecretName
    uses_existing = regex_in_any(files, r"existingSecret(Name)?:\s*[\"']?\S")[0]
    inline_pwd = regex_in_any(files, r"^\s*password:\s*[\"']?[A-Za-z0-9_]+[\"']?\s*$", ignore_case=True)[0]
    results.append({
        "text": "HelmRelease wires auth.existingSecret — does NOT inline auth.password",
        "passed": uses_existing and not inline_pwd,
        "evidence": f"existingSecret={uses_existing}, inline_password={inline_pwd}",
    })

    # chart_version_pinned
    pinned = regex_in_any(files, r"\bversion:\s*[\"']?\d+\.\d+")[0]
    results.append({
        "text": "PostgreSQL chart version is pinned",
        "passed": pinned,
        "evidence": "version pinned" if pinned else "no pinned version",
    })

    # secret_resource_generated
    has_secret = regex_in_any(files, r"^kind:\s*(Secret|ExternalSecret|SealedSecret)\b")[0]
    results.append({
        "text": "Secret/ExternalSecret/SealedSecret resource generated (user explicitly requested credential management)",
        "passed": has_secret,
        "evidence": "secret resource present" if has_secret else "no secret resource — user explicitly asked for K8s Secret management",
    })

    # prefers_eso_when_available
    has_es = regex_in_any(files, r"^kind:\s*ExternalSecret\b")[0]
    results.append({
        "text": "Generated secret is an ExternalSecret (ESO is installed in the fixture repo)",
        "passed": has_es,
        "evidence": "ExternalSecret found" if has_es else "no ExternalSecret — fell back to native Secret despite ESO",
    })

    # db_name_and_user_configured
    has_db = has_in_any(files, "appdb")[0]
    has_user = has_in_any(files, "appuser")[0]
    results.append({
        "text": "Database name 'appdb' and username 'appuser' configured in values",
        "passed": has_db and has_user,
        "evidence": f"appdb={has_db}, appuser={has_user}",
    })

    # no_inline_password — already covered by the existing_secret check, but make it explicit
    # Look for any password: <real-looking-or-placeholder> directly in helm values
    real_or_placeholder_inline = []
    for path, content in files.items():
        # Skip Secret resources — values there are expected
        if re.search(r"^kind:\s*(Secret|ExternalSecret|SealedSecret)\b", content, re.MULTILINE):
            continue
        for m in re.finditer(r"^\s*(password|adminPassword|rootPassword):\s*[\"']?([^\"'\n#]+)", content, re.MULTILINE):
            val = m.group(2).strip()
            if val and not val.startswith("$") and val != "":
                real_or_placeholder_inline.append(f"{path}: {m.group(1)}={val[:20]!r}")
    results.append({
        "text": "auth.password is NOT inlined with a placeholder value in HelmRelease values",
        "passed": not real_or_placeholder_inline,
        "evidence": "; ".join(real_or_placeholder_inline[:3]) if real_or_placeholder_inline else "no inline password in values",
    })

    return results


def grade_eval_6(outputs_dir: Path) -> list[dict]:
    """ExternalDNS with Route53, no IRSA — chart needs AWS credentials via Secret.
    Fixture has no secrets backend, so a native placeholder Secret is the right answer."""
    files = read_all_files(outputs_dir)
    results: list[dict] = []

    # picked_argocd
    has_argo = regex_in_any(files, r"^kind:\s*Application\b")[0]
    no_flux = not regex_in_any(files, r"^kind:\s*HelmRelease")[0]
    results.append({
        "text": "Generated manifests use ArgoCD (kind: Application), not Flux",
        "passed": has_argo and no_flux,
        "evidence": f"Application={has_argo}, no Flux HelmRelease={no_flux}",
    })

    # argocd_apps_path
    in_apps = any("argocd/apps/" in p for p in files)
    results.append({
        "text": "ExternalDNS Application placed under argocd/apps/",
        "passed": in_apps,
        "evidence": f"argocd/apps files: {[p for p in files if 'argocd/apps' in p][:3]}",
    })

    # externaldns_aws_provider — accept both legacy string form (`provider: aws`) and the
    # current structured-object form (`provider:\n  name: aws`) used by ExternalDNS chart v6+.
    has_aws_provider = (
        regex_in_any(files, r"provider:\s*[\"']?aws\b", ignore_case=True)[0]
        or regex_in_any(files, r"provider:\s*\n\s+name:\s*[\"']?aws\b", ignore_case=True)[0]
    )
    results.append({
        "text": "ExternalDNS values configure provider: aws (legacy string or structured object form)",
        "passed": has_aws_provider,
        "evidence": "provider=aws found" if has_aws_provider else "no provider=aws config",
    })

    # externaldns_domain_filter
    has_domain = has_in_any(files, "example.com")[0]
    results.append({
        "text": "domainFilter (or similar) references example.com",
        "passed": has_domain,
        "evidence": "example.com referenced" if has_domain else "example.com not referenced",
    })

    # chart_version_pinned
    pinned = regex_in_any(files, r"targetRevision:\s*[\"']?v?\d+\.\d+")[0]
    results.append({
        "text": "ExternalDNS Application targetRevision is pinned",
        "passed": pinned,
        "evidence": "pinned" if pinned else "no pinned targetRevision",
    })

    # secret_resource_generated — the regression test for case 1
    has_secret = regex_in_any(files, r"^kind:\s*Secret\b")[0]
    results.append({
        "text": "Secret resource generated for AWS credentials (no IRSA; chart requires creds)",
        "passed": has_secret,
        "evidence": "Secret found" if has_secret else "no Secret — ExternalDNS cannot reach Route53 without AWS creds",
    })

    # secret_is_placeholder
    placeholder_pat = re.compile(r"(REPLACE|PLACEHOLDER|CHANGEME|<.*>|YOUR[_-]?|TODO|FIXME)", re.IGNORECASE)
    warning_pat = re.compile(r"(WARNING|DO NOT|placeholder|TODO|replace)", re.IGNORECASE)
    secret_files = [(p, c) for p, c in files.items() if re.search(r"^kind:\s*Secret\b", c, re.MULTILINE)]
    placeholder_ok = False
    real_looking = False
    for path, content in secret_files:
        if placeholder_pat.search(content) and warning_pat.search(content):
            placeholder_ok = True
        # AWS access keys look like AKIA + 16 alphanum
        if re.search(r"AKIA[0-9A-Z]{16}", content):
            real_looking = True
    if not secret_files:
        results.append({
            "text": "Secret contains placeholder values + warning header (no real-looking AWS key)",
            "passed": False,
            "evidence": "no Secret resource to inspect (failed prior assertion)",
        })
    else:
        results.append({
            "text": "Secret contains placeholder values + warning header (no real-looking AWS key)",
            "passed": placeholder_ok and not real_looking,
            "evidence": f"placeholder+warning={placeholder_ok}, real-looking_key={real_looking}",
        })

    # no_inline_aws_creds
    inline = _has_inline_aws_creds(files)
    results.append({
        "text": "AWS credentials are NOT inlined into the helm.values block",
        "passed": not inline,
        "evidence": "; ".join(inline[:3]) if inline else "no inline AWS credentials detected",
    })

    return results


GRADERS = {
    1: grade_eval_1,
    2: grade_eval_2,
    3: grade_eval_3,
    4: grade_eval_4,
    5: grade_eval_5,
    6: grade_eval_6,
}


# =========================================================================
# Universal anti-pattern checks — run on every eval output
# These detect silent-failure-mode defects the existing pass-rate doesn't catch.
# Each check returns a passing assertion when no defect is found.
# =========================================================================

# Charts that ship CRDs and need Flux `crds: CreateReplace` (or `installCRDs: true` on
# the chart's own values) to handle CRD upgrades cleanly. Missing this means CRDs are
# installed once but never updated, which silently degrades the install over time.
KNOWN_CRD_SHIPPING_CHARTS = {
    "cert-manager",
    "kube-prometheus-stack",
    "prometheus-operator",
    "external-secrets",
    "gateway-api",
    "istio-base",
    "istiod",
    "traefik",
    "kong",
    "opentelemetry-operator",
    "grafana-operator",
    "argo-cd",
    "argo-workflows",
    "tekton-pipeline",
}

# Patterns that mark a Secret value as an intentional placeholder, not a real credential.
PLACEHOLDER_MARKERS = re.compile(
    r"(PLACEHOLDER|placeholder|YOUR[_-]?|REPLACE|<[^>]+>|TODO|FIXME|CHANGE[_-]?ME|changeme|example[_-]?(token|password)|XXX+|\.\.\.|BEFORE[_-](APPLYING|COMMIT|COMMITTING)|INSERT[_-]HERE)",
    re.IGNORECASE,
)

# Field names in chart values that are POINTERS to secret keys, not secret values themselves.
# E.g. grafana.admin.passwordKey: "admin-password" tells the chart which key in the existingSecret
# to read — the string "admin-password" is a key name, not a password.
SECRET_REF_FIELD_NAMES = re.compile(r"(.*Key|existingSecret|secretName|secretRef|valueFrom)$")


def _looks_like_placeholder(value: str) -> bool:
    """Return True if the string is clearly a placeholder, not a real credential."""
    if PLACEHOLDER_MARKERS.search(value):
        return True
    # SCREAMING_SNAKE_CASE strings (all caps + underscores/dashes/digits) are placeholders
    # by widespread convention. Real passwords almost never look like this.
    if re.fullmatch(r"[A-Z0-9_-]+", value) and len(value) >= 4:
        return True
    return False


def _parse_yaml_docs(content: str) -> list[dict]:
    """Best-effort YAML doc parsing; returns [] if PyYAML unavailable or content invalid."""
    try:
        import yaml  # type: ignore
    except ImportError:
        return []
    try:
        return [d for d in yaml.safe_load_all(content) if isinstance(d, dict)]
    except Exception:
        return []


def check_sourceref_namespace_match(files: dict[str, str]) -> dict:
    """Flux HelmRelease.spec.chart.spec.sourceRef.namespace must match the HelmRepository's
    metadata.namespace when both are in the same output set. Mismatch breaks reconciliation
    silently — the HelmRelease just stays pending forever."""
    helmrepos: dict[str, str] = {}  # name -> namespace
    helmreleases: list[tuple[str, str, str]] = []  # (path, sourceref_name, sourceref_namespace)

    for path, content in files.items():
        for doc in _parse_yaml_docs(content):
            kind = doc.get("kind")
            if kind == "HelmRepository":
                name = (doc.get("metadata") or {}).get("name")
                ns = (doc.get("metadata") or {}).get("namespace")
                if name and ns:
                    helmrepos[name] = ns
            elif kind == "HelmRelease":
                source_ref = (((doc.get("spec") or {}).get("chart") or {}).get("spec") or {}).get("sourceRef") or {}
                if source_ref.get("kind") == "HelmRepository":
                    helmreleases.append((path, source_ref.get("name"), source_ref.get("namespace")))

    mismatches: list[str] = []
    for path, ref_name, ref_ns in helmreleases:
        if ref_name in helmrepos:
            actual_ns = helmrepos[ref_name]
            # If sourceRef.namespace is set, it must match. If unset, Flux defaults to the
            # HelmRelease's namespace — also a mismatch risk if repo is elsewhere.
            if ref_ns is not None and ref_ns != actual_ns:
                mismatches.append(f"{path}: sourceRef.namespace={ref_ns!r} but HelmRepository {ref_name!r} is in {actual_ns!r}")

    return {
        "text": "[static] No HelmRepository sourceRef.namespace mismatch (Flux silent reconcile-break gotcha)",
        "passed": not mismatches,
        "evidence": "; ".join(mismatches) if mismatches else f"checked {len(helmreleases)} HelmRelease(s) against {len(helmrepos)} HelmRepository(ies)",
    }


def check_no_real_secret_values(files: dict[str, str]) -> dict:
    """Secret resources should contain placeholder values, never real-looking credentials.
    A real-looking value is a 8+ char string under data/stringData that doesn't match a
    placeholder marker pattern. Also check HelmRelease.spec.values for plaintext
    password/token/apiKey fields with real-looking values."""
    real_values: list[str] = []

    for path, content in files.items():
        for doc in _parse_yaml_docs(content):
            kind = doc.get("kind")
            if kind == "Secret":
                for field in ("data", "stringData"):
                    block = doc.get(field) or {}
                    for k, v in block.items():
                        if not isinstance(v, str):
                            continue
                        # For data: fields the surface form is base64-encoded. Both the length
                        # check (8+ chars to consider it a real credential) and the placeholder
                        # marker check should operate on the decoded content, not the encoding.
                        effective_value = v
                        if field == "data":
                            import base64
                            try:
                                effective_value = base64.b64decode(v, validate=True).decode("utf-8", errors="strict")
                            except Exception:
                                pass  # malformed base64; fall back to surface form
                        if len(effective_value) >= 8 and not _looks_like_placeholder(effective_value):
                            real_values.append(f"{path}: Secret.{field}.{k} appears non-placeholder ({effective_value[:20]!r})")
            elif kind == "HelmRelease":
                values = (doc.get("spec") or {}).get("values") or {}
                # Recursively scan for password-like keys with non-placeholder string values.
                # Skip *Key / existingSecret / secretName fields — those are pointers to a secret
                # key NAME, not credential values themselves.
                def _scan(obj, path_prefix=""):
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            full_path = f"{path_prefix}.{k}" if path_prefix else k
                            if SECRET_REF_FIELD_NAMES.match(k):
                                continue  # this is a pointer field, not a value
                            if isinstance(v, str) and re.search(r"(password|token|apikey|api_key|secret_key|secretkey)", k, re.IGNORECASE):
                                if len(v) >= 8 and not _looks_like_placeholder(v):
                                    real_values.append(f"{path}: HelmRelease.spec.values.{full_path} = plaintext credential ({v[:20]!r})")
                            elif isinstance(v, (dict, list)):
                                _scan(v, full_path)
                    elif isinstance(obj, list):
                        for i, item in enumerate(obj):
                            _scan(item, f"{path_prefix}[{i}]")
                _scan(values)

    return {
        "text": "[static] No real-looking secret values committed to manifests (placeholders only)",
        "passed": not real_values,
        "evidence": "; ".join(real_values[:3]) if real_values else "no plaintext credentials detected",
    }


def check_crds_create_replace(files: dict[str, str]) -> dict:
    """For known CRD-shipping charts, the Flux HelmRelease must set install.crds: CreateReplace
    and ideally upgrade.crds: CreateReplace too. Otherwise CRDs are installed once and never
    upgraded — silent feature regressions over time."""
    missing: list[str] = []
    checked_charts: list[str] = []

    for path, content in files.items():
        for doc in _parse_yaml_docs(content):
            if doc.get("kind") != "HelmRelease":
                continue
            chart = (((doc.get("spec") or {}).get("chart") or {}).get("spec") or {}).get("chart")
            if chart not in KNOWN_CRD_SHIPPING_CHARTS:
                continue
            checked_charts.append(chart)
            install_crds = (((doc.get("spec") or {}).get("install") or {}).get("crds"))
            upgrade_crds = (((doc.get("spec") or {}).get("upgrade") or {}).get("crds"))
            # Acceptable values: "Create", "CreateReplace", "Skip" (skip = manual mgmt, technically OK)
            # We require at least install.crds is set to Create or CreateReplace
            if install_crds not in ("Create", "CreateReplace"):
                missing.append(f"{path}: chart={chart}, install.crds={install_crds!r} (need Create or CreateReplace)")
            elif upgrade_crds not in ("Create", "CreateReplace"):
                # Soft warning: install OK but upgrades will skip CRD updates
                missing.append(f"{path}: chart={chart}, upgrade.crds={upgrade_crds!r} (need CreateReplace for clean upgrades)")

    return {
        "text": "[static] CRD-shipping charts have crds: CreateReplace on install + upgrade",
        "passed": not missing,
        "evidence": "; ".join(missing) if missing else (
            f"checked CRD charts: {checked_charts}" if checked_charts else "no CRD-shipping charts in output (n/a)"
        ),
    }


def run_universal_checks(outputs_dir: Path) -> list[dict]:
    """Run all static anti-pattern checks against the outputs directory."""
    files = read_all_files(outputs_dir)
    return [
        check_sourceref_namespace_match(files),
        check_no_real_secret_values(files),
        check_crds_create_replace(files),
    ]


def grade_outputs_dir(eval_dir: Path, run_name: str, outputs_dir: Path) -> dict | None:
    """Grade a single outputs/ dir; returns the grading.json dict or None."""
    metadata_file = eval_dir / "eval_metadata.json"
    if not metadata_file.exists():
        return None
    metadata = json.loads(metadata_file.read_text())
    eval_id = metadata["eval_id"]
    grader = GRADERS.get(eval_id)
    if not grader:
        return None
    expectations = grader(outputs_dir)
    expectations.extend(run_universal_checks(outputs_dir))
    passed = sum(1 for e in expectations if e["passed"])
    total = len(expectations)
    return {
        "eval_id": eval_id,
        "eval_name": metadata["eval_name"],
        "run": run_name,
        "expectations": expectations,
        "summary": {"passed": passed, "total": total, "pass_rate": passed / total if total else 0},
    }


def main() -> int:
    if not ITERATION_DIR.exists():
        print(f"missing {ITERATION_DIR}", file=sys.stderr)
        return 1
    overall = []
    for eval_dir in sorted(ITERATION_DIR.glob("eval-*")):
        for run_name in ("with_skill", "without_skill", "old_skill"):
            config_dir = eval_dir / run_name
            if not config_dir.exists():
                continue
            # New layout: <config>/run-N/outputs/. Fallback: <config>/outputs/ (legacy single-replicate).
            run_subdirs = sorted(config_dir.glob("run-*"))
            if run_subdirs:
                for run_subdir in run_subdirs:
                    outputs_dir = run_subdir / "outputs"
                    if not outputs_dir.exists():
                        print(f"[skip] {eval_dir.name}/{run_name}/{run_subdir.name}: no outputs dir", file=sys.stderr)
                        continue
                    result = grade_outputs_dir(eval_dir, run_name, outputs_dir)
                    if result is None:
                        continue
                    (run_subdir / "grading.json").write_text(json.dumps(result, indent=2))
                    overall.append((eval_dir.name, f"{run_name}/{run_subdir.name}", result["summary"]))
                    print(f"{eval_dir.name}/{run_name}/{run_subdir.name}: {result['summary']['passed']}/{result['summary']['total']}")
            else:
                outputs_dir = config_dir / "outputs"
                if not outputs_dir.exists():
                    print(f"[skip] {eval_dir.name}/{run_name}: no outputs dir", file=sys.stderr)
                    continue
                result = grade_outputs_dir(eval_dir, run_name, outputs_dir)
                if result is None:
                    continue
                run_subdir = config_dir / "run-1"
                run_subdir.mkdir(exist_ok=True)
                (run_subdir / "grading.json").write_text(json.dumps(result, indent=2))
                overall.append((eval_dir.name, run_name, result["summary"]))
                print(f"{eval_dir.name}/{run_name}: {result['summary']['passed']}/{result['summary']['total']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
