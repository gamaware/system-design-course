# Build stage: static binary with the Crystal compiler on Alpine (musl)
FROM crystallang/crystal:1.22.0-alpine AS build
WORKDIR /src/
COPY . .
RUN shards install && \
    crystal build --release --static src/server.cr

# Runtime stage: only the tools startup.sh uses, running as a non-root user
FROM public.ecr.aws/docker/library/alpine:3.24
RUN apk add --no-cache bash curl iproute2 jq && \
    addgroup -S -g 10001 app && \
    adduser -S -u 10001 -G app -H -s /sbin/nologin app
COPY --from=build /src/startup.sh /startup.sh
COPY --from=build /src/server /server
COPY --from=build /src/code_hash.txt /code_hash.txt
# app user created above
USER 10001:10001
HEALTHCHECK --interval=10s --timeout=3s \
  CMD ["sh", "-c", "curl -f -s http://localhost:3000/health || exit 1"]
EXPOSE 3000
ENTRYPOINT ["bash", "/startup.sh"]
