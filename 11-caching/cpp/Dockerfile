FROM gcc:14.4.0-trixie AS build

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        cmake=3.31.6-2 \
        libcurl4-openssl-dev=8.14.1-2+deb13u7 \
        libhiredis-dev=1.2.0-6+b3 \
        nlohmann-json3-dev=3.11.3-2.1 \
        pkg-config=1.8.1-4 \
    && rm -rf /var/lib/apt/lists/*

COPY CMakeLists.txt cache_lab.cpp ./

RUN cmake -B build -DCMAKE_BUILD_TYPE=Release \
    && cmake --build build

FROM debian:trixie-20261005-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        libcurl4t64=8.14.1-2+deb13u7 \
        libhiredis1.1.0=1.2.0-6+b3 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /app/build/cache_lab ./build/cache_lab

ENTRYPOINT ["./build/cache_lab"]
