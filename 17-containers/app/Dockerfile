# Multi-stage build: the Go toolchain compiles the binary in the first stage and stays behind;
# only the static binary reaches the final image.

# --- Build stage ---
FROM golang:1.27.2-trixie@sha256:47667934874913a449b96faa7ef4777fa285d9ec29126ee80ed61c45b7cccf0e AS build

WORKDIR /src

# Copy go.mod first: Docker reuses this layer until the module definition changes.
COPY go.mod ./
COPY main.go ./

ARG VERSION=v1
# CGO_ENABLED=0 links a static binary that runs without a C library; -s -w drops debug symbols.
RUN CGO_ENABLED=0 go build -trimpath -ldflags "-s -w -X main.version=${VERSION}" -o /out/web .

# --- Runtime stage ---
# distroless/static has CA certificates, time zones and a passwd entry for "nonroot",
# but no shell and no package manager.
FROM gcr.io/distroless/static-debian13:nonroot@sha256:18f4cc26c9ffa7f20a359298be7deadac5c607c8e03a02b8119f1a5fc2f82c99

COPY --from=build /out/web /web

# 65532 is the "nonroot" user of distroless; the process never runs as root.
USER 65532:65532
EXPOSE 8080

# The image has no curl, so the binary checks itself.
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 CMD ["/web", "-healthcheck"]

ENTRYPOINT ["/web"]
