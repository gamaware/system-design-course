# Build stage: compile the gems that have native extensions (puma, nio4r, ...)
FROM public.ecr.aws/docker/library/ruby:3.4-alpine3.24 AS build

ENV BUNDLE_FROZEN=true
WORKDIR /usr/src/app

RUN apk add --no-cache build-base yaml-dev

COPY Gemfile Gemfile.lock ./
RUN bundle install --jobs 4 && \
    rm -rf /usr/local/bundle/cache

# Runtime stage: no compilers, runs as a non-root user
FROM public.ecr.aws/docker/library/ruby:3.4-alpine3.24

ENV BUNDLE_FROZEN=true

# iproute2, curl and jq are used by startup-cdk.sh to discover the IP and AZ
RUN apk add --no-cache bash ca-certificates curl iproute2 jq tzdata yaml && \
    addgroup -S -g 10001 app && \
    adduser -S -u 10001 -G app -h /usr/src/app -H -s /sbin/nologin app && \
    install -d -o 10001 -g 10001 /usr/src/app

WORKDIR /usr/src/app
COPY --from=build /usr/local/bundle /usr/local/bundle
COPY --chown=10001:10001 . /usr/src/app

# app user created above
USER 10001:10001
RUN RAILS_ENV=production bundle exec rake assets:precompile

HEALTHCHECK --interval=10s --timeout=3s \
  CMD ["sh", "-c", "curl -f -s http://localhost:3000/health/ || exit 1"]
EXPOSE 3000
ENTRYPOINT ["bash","/usr/src/app/startup-cdk.sh"]
