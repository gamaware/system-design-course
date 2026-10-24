"""Lab 11 caching exercises in Python (redis-py + requests).

Same six exercises and output as the C++, C# and Java programs:
cache-aside, read-through with TTL, write-through, write-back,
LRU eviction and a cache miss vs hit benchmark.
"""

import json
import os
import sys
import time
import traceback
from collections.abc import Callable

import redis
import requests


def env_or_default(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value else default


REDIS_HOST = env_or_default("REDIS_HOST", "localhost")
BACKEND_HOST = env_or_default("BACKEND_HOST", "localhost")
BACKEND_URL = f"http://{BACKEND_HOST}:5000"
HTTP_TIMEOUT_SECONDS = 10

r = redis.Redis(
    host=REDIS_HOST,
    port=6379,
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
)


def to_json(data: dict) -> str:
    """Compact JSON, the same shape Gson produces in the Java version."""
    return json.dumps(data, separators=(",", ":"))


def elapsed_ms(start_ns: int) -> float:
    return (time.perf_counter_ns() - start_ns) / 1_000_000


# ---------------------------------------------------------------
# Exercise 1: Cache-Aside
# ---------------------------------------------------------------


def exercise_cache_aside() -> None:
    print_header("Exercise 1: Cache-Aside Pattern")

    print("--- First call (cache miss) ---")
    start = time.perf_counter_ns()
    result1 = get_product("1")
    elapsed1 = elapsed_ms(start)
    print(f"Result: {result1}")
    print(f"Time: {elapsed1:.2f} ms\n")

    print("--- Second call (cache hit) ---")
    start = time.perf_counter_ns()
    result2 = get_product("1")
    elapsed2 = elapsed_ms(start)
    print(f"Result: {result2}")
    print(f"Time: {elapsed2:.2f} ms\n")

    print(f"Speed improvement: {elapsed1 / elapsed2:.1f}x faster\n")


def get_product(product_id: str) -> str:
    key = f"product:{product_id}"
    cached = r.get(key)
    if cached is not None:
        print("  [HIT] Found in Redis")
        return cached
    print("  [MISS] Fetching from backend API")
    data = http_get(f"{BACKEND_URL}/products/{product_id}")
    r.set(key, data)
    print("  [STORE] Saved to Redis")
    return data


# ---------------------------------------------------------------
# Exercise 2: Read-Through with TTL
# ---------------------------------------------------------------


def exercise_read_through() -> None:
    print_header("Exercise 2: Read-Through with TTL")

    key = "product:2"
    ttl = 30

    def fetch_product_2() -> str:
        print("  [SUPPLIER] Fetching product 2 from backend")
        return http_get(f"{BACKEND_URL}/products/2")

    def should_not_be_called() -> str:
        print("  [SUPPLIER] This should not be called")
        return http_get(f"{BACKEND_URL}/products/2")

    print(f"--- Read-through with {ttl}s TTL ---")
    start = time.perf_counter_ns()
    result = read_through(key, ttl, fetch_product_2)
    elapsed = elapsed_ms(start)
    print(f"Result: {result}")
    print(f"Time: {elapsed:.2f} ms")
    print(f"TTL remaining: {r.ttl(key)}s")

    print("\n--- Second read (cache hit) ---")
    start = time.perf_counter_ns()
    result = read_through(key, ttl, should_not_be_called)
    elapsed = elapsed_ms(start)
    print(f"Result: {result}")
    print(f"Time: {elapsed:.2f} ms")
    print(f"TTL remaining: {r.ttl(key)}s\n")


def read_through(key: str, ttl_seconds: int, fetch_function: Callable[[], str]) -> str:
    cached = r.get(key)
    if cached is not None:
        print("  [HIT] Found in Redis")
        return cached
    print("  [MISS] Cache miss, calling supplier")
    data = fetch_function()
    # SET with EX is what SETEX does; redis-py 8 deprecates its setex() helper
    r.set(key, data, ex=ttl_seconds)
    print(f"  [STORE] Saved to Redis with TTL={ttl_seconds}s")
    return data


# ---------------------------------------------------------------
# Exercise 3: Write-Through
# ---------------------------------------------------------------


def exercise_write_through() -> None:
    print_header("Exercise 3: Write-Through Pattern")

    json_data = to_json({"name": "Premium Widget", "price": 99.99})

    print(f"Updating product 1: {json_data}")
    update_product("1", json_data)

    cached = r.get("product:1")
    print(f"\nVerification - Redis now contains: {cached}")
    print("Write-through complete: both backend and cache updated\n")


def update_product(product_id: str, json_data: str) -> None:
    url = f"{BACKEND_URL}/products/{product_id}"
    print(f"  [BACKEND] PUT to {url}")
    backend_response = http_put(url, json_data)
    print(f"  [BACKEND] Response: {backend_response}")

    key = f"product:{product_id}"
    r.set(key, backend_response)
    print(f"  [CACHE] Updated Redis key: {key}")


# ---------------------------------------------------------------
# Exercise 4: Write-Back (Write-Behind)
# ---------------------------------------------------------------


def exercise_write_back() -> None:
    print_header("Exercise 4: Write-Back (Write-Behind) Pattern")

    for product_id in ("3", "4", "5"):
        json_data = to_json({"name": f"Product {product_id}", "price": float(product_id) * 10.50})
        print(f"Async update product {product_id}: {json_data}")
        update_product_async(product_id, json_data)

    print(f"\nDirty keys before flush: {format_set(r.smembers('dirty_keys'))}")

    print("\n--- Flushing dirty keys to backend ---")
    flush_dirty()

    print(f"Dirty keys after flush: {format_set(r.smembers('dirty_keys'))}")
    print()


def update_product_async(product_id: str, json_data: str) -> None:
    key = f"product:{product_id}"
    r.set(key, json_data)
    r.sadd("dirty_keys", key)
    print(f"  [CACHE] Written to Redis only, marked dirty: {key}")


def flush_dirty() -> None:
    dirty_keys = r.smembers("dirty_keys")
    print(f"  Flushing {len(dirty_keys)} dirty keys")

    for key in sorted(dirty_keys):
        data = r.get(key)
        if data is None:
            print(f"  [SKIP] {key} — no data in cache")
            r.srem("dirty_keys", key)
            continue
        # Extract product ID from key format "product:{id}"
        product_id = key.split(":", 1)[1]
        print(f"  [FLUSH] PUT {key} -> backend /products/{product_id}")
        response = http_put(f"{BACKEND_URL}/products/{product_id}", data)
        print(f"  [FLUSH] Response: {response}")
        r.srem("dirty_keys", key)


def format_set(members: set[str]) -> str:
    return "[" + ", ".join(sorted(members)) + "]"


# ---------------------------------------------------------------
# Exercise 5: Eviction Demo
# ---------------------------------------------------------------


def exercise_eviction() -> None:
    print_header("Exercise 5: Eviction Demo (LRU)")

    # Flush before reducing memory limit
    r.flushall()

    print("Setting maxmemory=1mb, policy=allkeys-lru")
    r.config_set("maxmemory-policy", "allkeys-lru")
    r.config_set("maxmemory", "1048576")

    # Reset stats to get a clean eviction count
    r.config_resetstat()

    print("Inserting 200 products into cache...")
    insert_errors = 0
    for i in range(1, 201):
        product = {
            "id": i,
            "name": f"Bulk Product {i}",
            "price": i * 1.99,
            "description": "A" * 500,
        }
        try:
            r.set(f"evict:product:{i}", to_json(product))
        except redis.exceptions.OutOfMemoryError:
            insert_errors += 1
    if insert_errors > 0:
        print(f"Insert errors (OOM before eviction): {insert_errors}")

    evicted = r.info("stats").get("evicted_keys", 0)
    print(f"Evicted keys: {evicted}")
    print(f"Keys remaining in DB: {r.dbsize()}")

    # Restore defaults
    print("\nRestoring maxmemory=10mb, policy=noeviction")
    r.config_set("maxmemory", "10485760")
    r.config_set("maxmemory-policy", "noeviction")

    # Clean up eviction keys
    r.delete(*(f"evict:product:{i}" for i in range(1, 201)))
    print()


# ---------------------------------------------------------------
# Exercise 6: Benchmark
# ---------------------------------------------------------------


def exercise_benchmark() -> None:
    print_header("Exercise 6: Benchmark — Cache Miss vs Hit")

    r.flushall()
    iterations = 100

    # Benchmark cache misses
    print(f"--- Benchmarking {iterations} cache misses ---")
    total_miss_ns = 0
    for i in range(1, iterations + 1):
        start = time.perf_counter_ns()
        get_product(str(i))
        total_miss_ns += time.perf_counter_ns() - start
    avg_miss_ms = total_miss_ns / iterations / 1_000_000
    print(f"Average cache miss latency: {avg_miss_ms:.2f} ms\n")

    # Benchmark cache hits (same keys, now cached)
    print(f"--- Benchmarking {iterations} cache hits ---")
    total_hit_ns = 0
    for i in range(1, iterations + 1):
        start = time.perf_counter_ns()
        get_product(str(i))
        total_hit_ns += time.perf_counter_ns() - start
    avg_hit_ms = total_hit_ns / iterations / 1_000_000
    print(f"Average cache hit latency:  {avg_hit_ms:.2f} ms\n")

    print(f"Cache hits are {avg_miss_ms / avg_hit_ms:.1f}x faster than misses\n")


# ---------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------


def http_get(url: str) -> str:
    response = requests.get(url, headers={"Accept": "application/json"}, timeout=HTTP_TIMEOUT_SECONDS)
    if not response.ok:
        raise RuntimeError(f"GET {url} returned status {response.status_code}: {response.text}")
    return response.text


def http_put(url: str, json_body: str) -> str:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    response = requests.put(url, data=json_body, headers=headers, timeout=HTTP_TIMEOUT_SECONDS)
    if not response.ok:
        raise RuntimeError(f"PUT {url} returned status {response.status_code}: {response.text}")
    return response.text


def print_header(title: str) -> None:
    print("=" * 60)
    print(title)
    print("=" * 60)


def main() -> int:
    try:
        r.ping()
        print(f"Connected to Redis at {REDIS_HOST}:6379")
        print(f"Backend API at {BACKEND_URL}")
        r.flushall()
        print("Flushed all Redis keys\n")

        exercise_cache_aside()
        exercise_read_through()
        exercise_write_through()
        exercise_write_back()
        exercise_eviction()
        exercise_benchmark()

        print("\n=== All exercises completed ===")
    except (redis.exceptions.RedisError, requests.RequestException, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1
    finally:
        r.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
