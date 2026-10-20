FROM public.ecr.aws/docker/library/node:24-alpine3.24

# set the default NODE_ENV to production
# for dev/test build with: docker build --build-arg NODE=development .
# and the testing npms will be included
ARG NODE=production
ENV NODE_ENV=${NODE}

# iproute2, curl and jq are used by startup.sh to discover the IP and AZ
RUN apk add --no-cache bash ca-certificates curl iproute2 jq

# copy package info early to install npms
WORKDIR /usr/src/app
COPY package*.json ./
# npm is only needed to install the dependencies: remove it (and the
# vulnerable packages it bundles) from the final image
RUN npm ci && \
    npm cache clean --force && \
    rm -rf /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/corepack \
      /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack

# copy the code
COPY . .

# run as the unprivileged "node" user (1000:1000) that ships with the node image
USER 1000:1000
HEALTHCHECK --interval=10s --timeout=3s \
  CMD ["sh", "-c", "curl -f -s http://localhost:3000/health/ || exit 1"]
EXPOSE 3000
ENTRYPOINT ["bash","/usr/src/app/startup.sh"]
