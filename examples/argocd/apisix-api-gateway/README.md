# APISIX API Gateway - ArgoCD Example

This example demonstrates deploying APISIX API Gateway using ArgoCD.

## Files

- `namespace.yaml` - Creates the apisix namespace
- `apisix-application.yaml` - ArgoCD Application resource

## Deployment

1. Apply the namespace:
   ```bash
   kubectl apply -f namespace.yaml
   ```

2. Apply the Application (ensure ArgoCD is installed):
   ```bash
   kubectl apply -f apisix-application.yaml
   ```

3. Wait for sync:
   ```bash
   argocd app wait apisix
   ```

## Verification

```bash
# Check Application status
argocd app get apisix

# Check pods
kubectl get pods -n apisix

# Check services
kubectl get svc -n apisix
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
- Automated sync with self-healing
