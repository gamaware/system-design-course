FROM ubuntu:24.04

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       nfs-kernel-server \
       nfs-common \
    && rm -rf /var/lib/apt/lists/*

COPY exports /etc/exports
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 2049

ENTRYPOINT ["/entrypoint.sh"]
