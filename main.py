# helm install \
#   cert-manager jetstack/cert-manager \
#   --namespace cert-manager \
#   --create-namespace \
#   --version v1.9.1 \
#   --set installCRDs=true

from unicodedata import name
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
import json
import re
import os


TRAEFIK_GROUP = "traefik.containo.us"
TRAEFIK_VERSION = "v1alpha1"
TRAEFIK_PLURAL = "ingressroutes"

CERT_GROUP = "cert-manager.io"
CERT_VERSION = "v1"
CERT_KIND = "Certificate"
CERT_PLURAL = "certificates"
CERT_ISSUER_NAME = os.getenv("ISSUER_NAME", "letsencrypt")
CERT_ISSUER_KIND = os.getenv("ISSUER_KIND", "ClusterIssuer")
CERT_CLEANUP = os.getenv("CERT_CLEANUP", "false").lower() in ("yes", "true", "t", "1")

def safe_get(obj, keys, default=None):
    """
    Get a value from the give dict. The key is in json format, i.e. seperated by a period.
    """
    v = obj
    for k in keys.split("."):
        if k not in v:
            return default
        v = v[k]
    return v


def create_certificate(crds, namespace, secretname, routes):
    """
    Create a certificate request for certmanager based on the IngressRoute
    """
    try:
        secret = crds.get_namespaced_custom_object(CERT_GROUP, CERT_VERSION, namespace, CERT_PLURAL, secretname)
        print(f"{secretname} : certificate already exists.")
        return
    except ApiException as e:
        pass

    for route in routes:
        if route.get("kind") == "Rule" and "Host" in route.get("match"):
            hostmatch = re.findall("Host\(([^\)]*)\)", route["match"])
            hosts = re.findall('`([^`]*?)`', ",".join(hostmatch))
        
            print(f"{secretname} : requesting a new certificate for {', '.join(hosts)}")
            body = {
                "apiVersion": f"{CERT_GROUP}/{CERT_VERSION}",
                "kind": CERT_KIND,
                "metadata": {
                    "name": secretname
                },
                "spec": {
                    "dnsNames": hosts,
                    "secretName": secretname,
                    "issuerRef": {
                        "name": CERT_ISSUER_NAME,
                        "kind": CERT_ISSUER_KIND
                    }
                }
            }
            try:
                crds.create_namespaced_custom_object(CERT_GROUP, CERT_VERSION, namespace, CERT_PLURAL, body)
            except ApiException as e:
                print("Exception when calling CustomObjectsApi->create_namespaced_custom_object: %s\n" % e)


def delete_certificate(crds, namespace, secretname):
    """
    Delete a certificate request for certmanager based on the IngressRoute.
    """
    if CERT_CLEANUP:
        print(f"{secretname} : removing certificate")
        try:
            crds.delete_namespaced_custom_object(CERT_GROUP, CERT_VERSION, namespace, CERT_PLURAL, secretname)
        except ApiException as e:
            print("Exception when calling CustomObjectsApi->delete_namespaced_custom_object: %s\n" % e)


def main():
    """
    Watch Traefik IngressRoute CRD and create/delete certificates based on them
    """
    #config.load_kube_config()
    config.load_incluster_config()
    crds = client.CustomObjectsApi()
    resource_version = ""

    while True:
        stream = watch.Watch().stream(crds.list_cluster_custom_object,
                                      TRAEFIK_GROUP, TRAEFIK_VERSION, TRAEFIK_PLURAL,
                                      resource_version=resource_version)
        for event in stream:
            t = event["type"]
            obj = event["object"]

            # Configure where to resume streaming.
            resource_version = safe_get(obj, "metadata.resourceVersion", resource_version)

            # get information about IngressRoute
            namespace = safe_get(obj, "metadata.namespace")
            secretname = safe_get(obj, "spec.tls.secretName")
            routes = safe_get(obj, 'spec.routes')

            # create a Certificate if needed
            if secretname:
                if t == 'ADDED':
                    create_certificate(crds, namespace, secretname, routes)

                elif t == 'DELETED':
                    delete_certificate(crds, namespace, secretname)

                else:           
                    print(t)
                    print(json.dumps(obj, indent=2))


if __name__ == '__main__':
    main()
