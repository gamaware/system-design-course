FROM ubuntu:24.04

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       nfs-common \
       fio \
       curl \
       ca-certificates \
       unzip \
       procps \
    && rm -rf /var/lib/apt/lists/*

# Install AWS CLI v2 (auto-detect architecture)
RUN ARCH=$(uname -m) \
    && if [ "$ARCH" = "aarch64" ]; then \
         CLI_URL="https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip"; \
       else \
         CLI_URL="https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip"; \
       fi \
    && curl -fsSL "$CLI_URL" -o "awscliv2.zip" \
    && unzip -q awscliv2.zip \
    && ./aws/install \
    && rm -rf awscliv2.zip aws/

# Create mount points
RUN mkdir -p /mnt/shared /mnt/data /mnt/backup

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["sleep", "infinity"]
