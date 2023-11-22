import json
import logging
import os
import re
import signal
import sys
import threading

from unicodedata import name
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException


CERT_GROUP = "cert-manager.io"
CERT_VERSION = "v1"
CERT_KIND = "Certificate"
CERT_PLURAL = "certificates"
CERT_ISSUER_NAME = os.getenv("ISSUER_NAME", "letsencrypt")
CERT_ISSUER_KIND = os.getenv("ISSUER_KIND", "ClusterIssuer")
CERT_CLEANUP = os.getenv("CERT_CLEANUP", "false").lower() in ("yes", "true", "t", "1")
PATCH_SECRETNAME = os.getenv("PATCH_SECRETNAME", "false").lower() in ("yes", "true", "t", "1")


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
        logging.info(f"{secretname} : certificate request already exists.")
        return
    except ApiException as e:
        pass

    for route in routes:
        if route.get("kind") == "Rule" and "Host" in route.get("match"):
            hostmatch = re.findall(r"Host\(([^\)]*)\)", route["match"])
            hosts = re.findall(r'`([^`]*?)`', ",".join(hostmatch))

            logging.info(f"{secretname} : requesting a new certificate for {', '.join(hosts)}")
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
                logging.exception("Exception when calling CustomObjectsApi->create_namespaced_custom_object:", e)


def delete_certificate(crds, namespace, secretname):
    """
    Delete a certificate request for certmanager based on the IngressRoute.
    """
    if CERT_CLEANUP:
        logging.info(f"{secretname} : removing certificate")
        try:
            crds.delete_namespaced_custom_object(CERT_GROUP, CERT_VERSION, namespace, CERT_PLURAL, secretname)
        except ApiException as e:
            logging.exception("Exception when calling CustomObjectsApi->delete_namespaced_custom_object:", e)


def watch_crd(group, version, plural):
    """
    Watch Traefik IngressRoute CRD and create/delete certificates based on them
    """
    #config.load_kube_config()
    config.load_incluster_config()
    crds = client.CustomObjectsApi()
    resource_version = ""

    logging.info(f"Watching {group}/{version}/{plural}")

    while True:
        stream = watch.Watch().stream(crds.list_cluster_custom_object,
                                      group=group, version=version, plural=plural,
                                      resource_version=resource_version)
        for event in stream:
            t = event["type"]
            obj = event["object"]

            # Configure where to resume streaming.
            resource_version = safe_get(obj, "metadata.resourceVersion", resource_version)

            # get information about IngressRoute
            namespace = safe_get(obj, "metadata.namespace")
            name = safe_get(obj, "metadata.name")
            secretname = safe_get(obj, "spec.tls.secretName")
            routes = safe_get(obj, 'spec.routes')

            # create or delete certificate based on event type
            if t == 'ADDED':
                # if no secretName is set, add one to the IngressRoute
                if not secretname and PATCH_SECRETNAME:
                    logging.info(f"{namespace}/{name} : no secretName found in IngressRoute, patch to add one")
                    patch = { "spec": { "tls": { "secretName": name }}}
                    crds.patch_namespaced_custom_object(group, version, namespace, plural, name, patch)
                    secretname = name
                if secretname:
                    create_certificate(crds, namespace, secretname, routes)
                else:
                    logging.info(f"{namespace}/{name} : no secretName found in IngressRoute, skipping adding")
            elif t == 'DELETED':
                if secretname:
                    delete_certificate(crds, namespace, secretname)
                else:
                    logging.info(f"{namespace}/{name} : no secretName found in IngressRoute, skipping delete")
            elif t == 'MODIFIED':
                if secretname:
                    create_certificate(crds, namespace, secretname, routes)
                else:
                    logging.info(f"{namespace}/{name} : no secretName found in IngressRoute, skipping modify")
            else:
                logging.info(f"{namespace}/{name} : unknown event type: {t}")
                logging.debug(json.dumps(obj, indent=2))


def exit_gracefully(signum, frame):
    logging.info(f"Shutting down gracefully on {signum}")
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, exit_gracefully)
    signal.signal(signal.SIGTERM, exit_gracefully)

    # deprecated traefik CRD
    th1 = threading.Thread(target=watch_crd, args=("traefik.containo.us", "v1alpha1", "ingressroutes"), daemon=True)
    th1.start()

    # new traefik CRD    
    th2 = threading.Thread(target=watch_crd, args=("traefik.io", "v1alpha1", "ingressroutes"), daemon=True)
    th2.start()

    # wait for threads to finish
    while th1.is_alive() and th2.is_alive():
        th1.join(0.1)
        th2.join(0.1)
    logging.info(f"One of the threads exited {th1.is_alive()}, {th2.is_alive()}")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
