FROM public.ecr.aws/docker/library/node:24-trixie-slim

# set the default NODE_ENV to production
# for dev/test build with: docker build --build-arg NODE=development .
# and the testing npms will be included
ARG NODE=production
ENV NODE_ENV=${NODE}

# iproute2, curl and jq are used by startup.sh to discover the IP and AZ
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl iproute2 jq && \
    rm -rf /var/lib/apt/lists/*

# copy package info early to install npms
WORKDIR /usr/src/app
COPY package*.json ./
RUN npm ci && \
    npm cache clean --force

# copy the code
COPY . .

# run as the unprivileged "node" user (1000:1000) that ships with the node image
USER 1000:1000
HEALTHCHECK --interval=10s --timeout=3s \
  CMD ["sh", "-c", "curl -f -s http://localhost:3000/health/ || exit 1"]
EXPOSE 3000
ENTRYPOINT ["bash","/usr/src/app/startup.sh"]
