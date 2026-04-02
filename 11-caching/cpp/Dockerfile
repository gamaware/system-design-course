FROM gcc:14-bookworm

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        cmake=3.25.1-1 \
        libcurl4-openssl-dev=7.88.1-10+deb12u12 \
        libhiredis-dev=0.14.1-3 \
        nlohmann-json3-dev=3.11.2-2 \
        pkg-config=1.8.1-1 \
    && rm -rf /var/lib/apt/lists/*

COPY CMakeLists.txt cache_lab.cpp ./

RUN cmake -B build -DCMAKE_BUILD_TYPE=Release \
    && cmake --build build

ENTRYPOINT ["./build/cache_lab"]
