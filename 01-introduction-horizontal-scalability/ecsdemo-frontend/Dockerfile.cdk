# Build stage: compile the gems that have native extensions (puma, nio4r, ...)
FROM public.ecr.aws/docker/library/ruby:3.4-slim-trixie AS build

ENV BUNDLE_FROZEN=true
WORKDIR /usr/src/app

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY Gemfile Gemfile.lock ./
RUN bundle install --jobs 4 && \
    rm -rf /usr/local/bundle/cache

# Runtime stage: no compilers, runs as a non-root user
FROM public.ecr.aws/docker/library/ruby:3.4-slim-trixie

ENV BUNDLE_FROZEN=true

# iproute2, curl and jq are used by startup-cdk.sh to discover the IP and AZ
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl iproute2 jq && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd --system --gid 10001 app && \
    useradd --system --uid 10001 --gid app --home-dir /usr/src/app --shell /usr/sbin/nologin app && \
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
