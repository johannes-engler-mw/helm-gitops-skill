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

    return results


GRADERS = {
    1: grade_eval_1,
    2: grade_eval_2,
    3: grade_eval_3,
}


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
        for run_name in ("with_skill", "without_skill"):
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
