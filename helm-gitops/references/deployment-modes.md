# Deployment Modes Reference

## Overview

Many Helm charts offer multiple deployment modes. Understanding these options helps configure appropriate HelmRelease values for your environment.

## Workflow

When deploying a chart that supports multiple modes:

1. **Check chart documentation** for available deployment modes
2. **Identify mode options** (standalone vs clustered, stateless vs stateful)
3. **Ask user preference** based on their environment and requirements
4. **Configure HelmRelease values** accordingly

## Common Deployment Modes

### Standalone/Stateless Mode

**Characteristics**:
- No external dependencies (databases, KV stores)
- Configuration via Kubernetes resources (CRDs, ConfigMaps)
- State lost on pod restart (unless using PVCs)

**Typical Configuration**:
```yaml
spec:
  values:
    # Disable external dependencies
    etcd:
      enabled: false
    postgresql:
      enabled: false

    # Enable stateless/standalone mode
    mode: standalone
    configProvider: yaml
```

**Use cases**:
- GitOps workflows (config in Git, not external stores)
- Local development (Kind, k3d, minikube)
- Applications where config is fully managed via CRDs
- Stateless workloads (API gateways in declarative mode)

### Clustered/Stateful Mode

**Characteristics**:
- Requires external dependencies (etcd, PostgreSQL, Redis)
- Persistent configuration storage
- State preserved across restarts
- Multi-instance coordination

**Typical Configuration**:
```yaml
spec:
  values:
    # Enable external dependencies
    etcd:
      enabled: true
      replicaCount: 3

    # Enable stateful mode
    mode: cluster
    persistence:
      enabled: true
```

**Use cases**:
- High availability requirements
- Dynamic runtime configuration
- Distributed state coordination
- Applications requiring persistent storage (databases, message queues)

## Configuration Examples by Category

### API Gateways

Many API gateways support **declarative/DB-less modes** for GitOps:

```yaml
# Example: Stateless gateway configuration
spec:
  values:
    gateway:
      mode: standalone
    database: "off"
    configProvider: yaml
```

**Note**: Declarative mode may limit certain features (e.g., plugins requiring distributed state).

### Databases

Databases typically need **persistence** but can run single-instance or clustered:

```yaml
# Single instance with persistence
spec:
  values:
    architecture: standalone
    persistence:
      enabled: true
      size: 10Gi

# Clustered for HA
spec:
  values:
    architecture: replication
    replicaCount: 3
```

### Monitoring & Observability

Often deployed **stateless** for dev, **stateful** for production:

```yaml
# With persistent storage
spec:
  values:
    persistence:
      enabled: true
      storageClassName: standard
      size: 50Gi
```

## Asking User for Mode Preference

When a chart supports multiple modes, ask:

**Example prompt**:
> This chart supports multiple deployment modes:
> 1. **Standalone** - No external dependencies (etcd disabled), GitOps-native
> 2. **Clustered** - Requires etcd cluster, supports HA and distributed state
>
> Which mode would you prefer for your environment?

**Follow-up questions** (if needed):
- Is this for development/testing or production?
- Do you need high availability?
- Should configuration be stored externally or in Kubernetes CRDs?
- Do you have persistent storage available?

## Decision Factors

| Factor | Standalone/Stateless | Clustered/Stateful |
|--------|---------------------|-------------------|
| **Configuration** | Git/CRDs only | External store |
| **Dependencies** | None | etcd/DB required |
| **HA** | Limited | Full HA support |
| **Complexity** | Low | Higher |
| **GitOps Alignment** | High | Moderate |

## Key Considerations for HelmRelease

When creating HelmRelease manifests:

1. **Check chart documentation** for supported modes
2. **Ask user preference** based on their environment
3. **Disable unused dependencies** to reduce resource usage
4. **Enable persistence** for stateful workloads (databases, monitoring)
5. **Use standalone mode** when config is fully in Git/CRDs
6. **Consider environment** (dev vs production needs)

## Common Helm Value Patterns

### Disabling Dependencies

```yaml
spec:
  values:
    etcd:
      enabled: false
    postgresql:
      enabled: false
    redis:
      enabled: false
```

### Enabling Standalone Features

```yaml
spec:
  values:
    deployment:
      mode: standalone
    config:
      provider: yaml  # or 'file', 'kubernetes'
```

### Adding Persistence

```yaml
spec:
  values:
    persistence:
      enabled: true
      storageClass: standard
      size: 10Gi
```

## References

- Always consult the specific chart's `values.yaml` for available options
- Check chart README for deployment mode recommendations
- Review upstream documentation for feature limitations per mode
