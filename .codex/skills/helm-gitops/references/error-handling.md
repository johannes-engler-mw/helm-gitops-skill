# Error Handling

Handle common failure scenarios gracefully with clear user communication.

## Web Search Failures

**No chart found:**
```
I couldn't find an official Helm chart for "{app-name}".

Possible reasons:
- The application may not have an official Helm chart
- It might be distributed differently (Kustomize, raw manifests, operator)
- The name might be different than expected

Would you like me to:
1. Search with alternative names (e.g., "{app-name}-operator", "{app-name}-helm")
2. Look for community-maintained charts on ArtifactHub
3. Check if there's a Kubernetes operator instead
```

**Multiple charts found:**
```
I found multiple Helm charts for "{app-name}":

1. **{vendor}/chart-name** (Official)
   - Repository: https://...
   - Last updated: {date}

2. **{community}/chart-name** (Community)
   - Repository: https://...
   - Last updated: {date}

Which chart would you prefer? I recommend option 1 (official) unless you have specific requirements.
```

**Deprecated/archived chart:**
```
The Helm chart for "{app-name}" appears to be deprecated/archived.

Status: {reason - e.g., "Repository archived", "No updates in 2+ years"}
Last version: {version}

Options:
1. Use the last available version (may have security issues)
2. Look for a successor/replacement chart
3. Consider alternative deployment method (operator, raw manifests)

Would you like me to search for alternatives?
```

## Repository Structure Ambiguity

**No clear pattern detected:**
```
I couldn't detect a clear GitOps structure in your repository.

Current structure:
{show ls output}

I can create files using one of these common patterns:

1. **Component-based** (Recommended)
   infra/{app-name}/
   ├── namespace.yaml
   ├── helmrepository.yaml
   ├── helmrelease.yaml
   └── kustomization.yaml

2. **Flat structure**
   manifests/{app-name}.yaml

3. **By type**
   infrastructure/{category}/{app-name}.yaml

Which structure would you prefer?
```

**Mixed patterns detected:**
```
Your repository uses multiple organizational patterns:
- infrastructure/monitoring/ uses flat YAML files
- infrastructure/controllers/ uses component directories

For {app-name}, which pattern should I follow?
1. Match the {closest-category} pattern (flat files)
2. Use component-based directories (more organized)
3. Specify a custom location
```

## Chart Version Issues

**Version not found:**
```
Chart version "{version}" not found for {chart-name}.

Available versions:
- {latest} (latest)
- {previous-1}
- {previous-2}

Would you like me to use the latest version ({latest})?
```

**Major version jump detected:**
```
You're upgrading from {chart-name} v{old} to v{new} (major version change).

Major version upgrades may include breaking changes:
- Configuration schema changes
- Removed features
- Required migrations

Recommendations:
1. Review the chart's CHANGELOG/upgrade guide
2. Test in a non-production environment first
3. Consider intermediate upgrades if jumping multiple majors

Proceed with v{new}, or would you like me to suggest a safer upgrade path?
```

## Secrets Detection Failures

**Cluster not accessible:**
```
I couldn't connect to the Kubernetes cluster to detect secrets management.

Error: {kubectl error message}

Options:
1. Tell me which secrets solution you use (ESO, Sealed Secrets, SOPS)
2. Generate manifests without secrets integration (add later)
3. Use native Kubernetes Secrets (not recommended for GitOps)
```

**Conflicting secrets solutions:**
```
I found conflicting secrets management in your setup:
- Cluster has: External Secrets Operator
- Repository patterns suggest: Sealed Secrets (12 occurrences)

This might indicate:
- Migration in progress
- Different solutions for different apps

Which solution should I use for {app-name}?
```

## Dependency Issues

**Missing dependencies:**
```
The {app-name} chart requires dependencies that aren't deployed:
- {dependency-1}: {status - not found}
- {dependency-2}: {status - not found}

Options:
1. Deploy dependencies first (I'll create manifests for these too)
2. Use the chart's bundled dependencies (if available)
3. Point to existing external services (provide connection details)
```

## General Recovery Strategy

When encountering any error:

1. **Don't guess** - Ask the user for clarification rather than making assumptions
2. **Provide context** - Show what was found/expected to help user understand
3. **Offer options** - Give 2-3 clear paths forward with recommendations
4. **Explain implications** - Note any tradeoffs for each option
5. **Allow escape** - Always offer to skip/defer if user is unsure
