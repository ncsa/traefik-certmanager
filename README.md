This will create a certificate request for IngressRoute objects for Traefik. 

# Installing Cert-Manager and Traefik

The default values assume you have cert-manager installed, see also [cert-manager installation](https://cert-manager.io/docs/installation/helm/):

```bash
helm install \
  cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --version v1.9.1 \
  --set installCRDs=true
```

As well as Traefik, see also [traefik installation](https://doc.traefik.io/traefik/getting-started/install-traefik/#use-the-helm-chart):

```
helm install \
	traefik traefik/traefik \
  --namespace cert-manager \
  --create-namespace \

```

## Adding ClusterIssuer to Cert-Manager

Next you install the ClusterIssuer using `kubectl apply`

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt
spec:
  acme:
    email: manager@example.com
    server: https://acme-v02.api.letsencrypt.org/directory
    privateKeySecretRef:
      name: lets-encrypt
    solvers:
      - http01:
          ingress:
            class: ""
```

# Installing Traefik to Cert-Manager

Finally you can install the traefik-certmanager. 

```bash
kubectl apply -f traefik-certmanager.yaml
```

This will create a deployment, service account and role that can read/watch IngressRoutes and can add/delete Certficates. When starting it will check all existing IngressRoutes and see if there is a certificate for them (only for those that have a secretName). Next it will watch the addition and/or deleting of IngressRoutes. If an IngressRoute is removed, it can (false by default) remove the certificate as well.

This is an example of a IngressRoute that will be picked up by this deployment:

```yaml
apiVersion: traefik.containo.us/v1alpha1
kind: IngressRoute
metadata:
  name: traefik-dashboard
  namespace: traefik
spec:
  entryPoints:
    - websecure
  routes:
    - match: Host(`traefik.example.com`)
      kind: Rule
      services:
        - name: api@internal
          kind: TraefikService
  tls:
    secretName: trafik.example
```

