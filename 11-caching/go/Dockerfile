# syntax=docker/dockerfile:1

# --- Build stage ---
FROM golang:1.27.2-trixie AS build

WORKDIR /src

COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod go mod download

COPY main.go ./
RUN --mount=type=cache,target=/go/pkg/mod \
    CGO_ENABLED=0 go build -trimpath -o /out/cache-lab .

# --- Runtime stage ---
FROM debian:trixie-20261005-slim

WORKDIR /app

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

COPY --from=build /out/cache-lab ./cache-lab

USER 10001:10001

ENTRYPOINT ["./cache-lab"]
