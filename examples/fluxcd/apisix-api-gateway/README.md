# APISIX API Gateway - FluxCD Example

This example demonstrates deploying APISIX API Gateway using FluxCD.

## Files

- `namespace.yaml` - Creates the apisix namespace
- `helmrepository.yaml` - FluxCD HelmRepository resource
- `helmrelease.yaml` - FluxCD HelmRelease resource
- `kustomization.yaml` - Kustomize configuration for all resources

## Deployment

Apply all resources (ensure FluxCD is installed):
```bash
kubectl apply -k .
```

Or apply individually:
```bash
kubectl apply -f namespace.yaml
kubectl apply -f helmrepository.yaml
kubectl apply -f helmrelease.yaml
```

## Verification

```bash
# Check HelmRepository status
flux get sources helm -n apisix

# Check HelmRelease status
flux get helmreleases -n apisix

# Check pods
kubectl get pods -n apisix

# Check services
kubectl get svc -n apisix
```

## Troubleshooting

```bash
# View HelmRelease events
kubectl describe helmrelease apisix -n apisix

# View Flux logs
flux logs --level=error

# Reconcile manually
flux reconcile helmrelease apisix -n apisix
```

## Access

The gateway is exposed via NodePort. To access:

```bash
# Get the NodePort
kubectl get svc -n apisix apisix-gateway -o jsonpath='{.spec.ports[?(@.name=="http")].nodePort}'

# Access the gateway (replace NODE_IP and NODE_PORT)
curl http://NODE_IP:NODE_PORT
```

## Configuration

The example includes:
- APISIX Gateway enabled
- APISIX Ingress Controller enabled
- etcd with 3 replicas (required dependency)
- NodePort service type for local testing
- Automatic remediation on install/upgrade failures (3 retries)
- 10-minute reconciliation interval
