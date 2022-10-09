FROM python:alpine

ENV PYTHONUNBUFFERED=1 \
    ISSUER_NAME=letsencrypt \
    ISSUER_KIND=ClusterIssuer \
    CERT_CLEANUP=false

RUN pip install kubernetes
COPY main.py /
CMD python /main.py
