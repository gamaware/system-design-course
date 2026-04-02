package com.lab;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import redis.clients.jedis.Jedis;
import redis.clients.jedis.exceptions.JedisDataException;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.Set;
import java.util.function.Supplier;

public class CacheLab {

    private static final String REDIS_HOST = envOrDefault("REDIS_HOST", "localhost");
    private static final String BACKEND_HOST = envOrDefault("BACKEND_HOST", "localhost");
    private static final String BACKEND_URL = "http://" + BACKEND_HOST + ":5000";

    private final Jedis jedis;
    private final HttpClient httpClient;
    private final Gson gson;

    public CacheLab() {
        this.jedis = new Jedis(REDIS_HOST, 6379);
        this.httpClient = HttpClient.newHttpClient();
        this.gson = new Gson();
    }

    public static void main(String[] args) {
        CacheLab lab = new CacheLab();
        try {
            lab.jedis.ping();
            System.out.println("Connected to Redis at " + REDIS_HOST + ":6379");
            System.out.println("Backend API at " + BACKEND_URL);
            lab.jedis.flushAll();
            System.out.println("Flushed all Redis keys\n");

            lab.exerciseCacheAside();
            lab.exerciseReadThrough();
            lab.exerciseWriteThrough();
            lab.exerciseWriteBack();
            lab.exerciseEviction();
            lab.exerciseBenchmark();

            System.out.println("\n=== All exercises completed ===");
        } catch (Exception e) {
            System.err.println("Error: " + e.getMessage());
            e.printStackTrace();
        } finally {
            lab.jedis.close();
        }
    }

    // ---------------------------------------------------------------
    // Exercise 1: Cache-Aside
    // ---------------------------------------------------------------

    private void exerciseCacheAside() {
        printHeader("Exercise 1: Cache-Aside Pattern");

        System.out.println("--- First call (cache miss) ---");
        long start = System.nanoTime();
        String result1 = getProduct("1");
        long elapsed1 = System.nanoTime() - start;
        System.out.println("Result: " + result1);
        System.out.printf("Time: %.2f ms%n%n", elapsed1 / 1_000_000.0);

        System.out.println("--- Second call (cache hit) ---");
        start = System.nanoTime();
        String result2 = getProduct("1");
        long elapsed2 = System.nanoTime() - start;
        System.out.println("Result: " + result2);
        System.out.printf("Time: %.2f ms%n%n", elapsed2 / 1_000_000.0);

        System.out.printf("Speed improvement: %.1fx faster%n%n",
                (double) elapsed1 / elapsed2);
    }

    private String getProduct(String id) {
        String key = "product:" + id;
        String cached = jedis.get(key);
        if (cached != null) {
            System.out.println("  [HIT] Found in Redis");
            return cached;
        }
        System.out.println("  [MISS] Fetching from backend API");
        String data = httpGet(BACKEND_URL + "/products/" + id);
        jedis.set(key, data);
        System.out.println("  [STORE] Saved to Redis");
        return data;
    }

    // ---------------------------------------------------------------
    // Exercise 2: Read-Through with TTL
    // ---------------------------------------------------------------

    private void exerciseReadThrough() {
        printHeader("Exercise 2: Read-Through with TTL");

        String key = "product:2";
        int ttl = 30;

        System.out.println("--- Read-through with " + ttl + "s TTL ---");
        long start = System.nanoTime();
        String result = readThrough(key, ttl, () -> {
            System.out.println("  [SUPPLIER] Fetching product 2 from backend");
            return httpGet(BACKEND_URL + "/products/2");
        });
        long elapsed = System.nanoTime() - start;
        System.out.println("Result: " + result);
        System.out.printf("Time: %.2f ms%n", elapsed / 1_000_000.0);

        long remaining = jedis.ttl(key);
        System.out.println("TTL remaining: " + remaining + "s");

        System.out.println("\n--- Second read (cache hit) ---");
        start = System.nanoTime();
        result = readThrough(key, ttl, () -> {
            System.out.println("  [SUPPLIER] This should not be called");
            return httpGet(BACKEND_URL + "/products/2");
        });
        elapsed = System.nanoTime() - start;
        System.out.println("Result: " + result);
        System.out.printf("Time: %.2f ms%n", elapsed / 1_000_000.0);

        remaining = jedis.ttl(key);
        System.out.println("TTL remaining: " + remaining + "s\n");
    }

    private String readThrough(String key, int ttlSeconds, Supplier<String> fetchFunction) {
        String cached = jedis.get(key);
        if (cached != null) {
            System.out.println("  [HIT] Found in Redis");
            return cached;
        }
        System.out.println("  [MISS] Cache miss, calling supplier");
        String data = fetchFunction.get();
        jedis.setex(key, ttlSeconds, data);
        System.out.println("  [STORE] Saved to Redis with TTL=" + ttlSeconds + "s");
        return data;
    }

    // ---------------------------------------------------------------
    // Exercise 3: Write-Through
    // ---------------------------------------------------------------

    private void exerciseWriteThrough() {
        printHeader("Exercise 3: Write-Through Pattern");

        JsonObject update = new JsonObject();
        update.addProperty("name", "Premium Widget");
        update.addProperty("price", 99.99);
        String jsonData = gson.toJson(update);

        System.out.println("Updating product 1: " + jsonData);
        updateProduct("1", jsonData);

        String cached = jedis.get("product:1");
        System.out.println("\nVerification - Redis now contains: " + cached);
        System.out.println("Write-through complete: both backend and cache updated\n");
    }

    private void updateProduct(String id, String jsonData) {
        System.out.println("  [BACKEND] PUT to " + BACKEND_URL + "/products/" + id);
        String backendResponse = httpPut(BACKEND_URL + "/products/" + id, jsonData);
        System.out.println("  [BACKEND] Response: " + backendResponse);

        String key = "product:" + id;
        jedis.set(key, jsonData);
        System.out.println("  [CACHE] Updated Redis key: " + key);
    }

    // ---------------------------------------------------------------
    // Exercise 4: Write-Back (Write-Behind)
    // ---------------------------------------------------------------

    private void exerciseWriteBack() {
        printHeader("Exercise 4: Write-Back (Write-Behind) Pattern");

        String[] ids = {"3", "4", "5"};
        for (String id : ids) {
            JsonObject product = new JsonObject();
            product.addProperty("name", "Product " + id);
            product.addProperty("price", Double.parseDouble(id) * 10.50);
            String jsonData = gson.toJson(product);

            System.out.println("Async update product " + id + ": " + jsonData);
            updateProductAsync(id, jsonData);
        }

        Set<String> dirtyKeys = jedis.smembers("dirty_keys");
        System.out.println("\nDirty keys before flush: " + dirtyKeys);

        System.out.println("\n--- Flushing dirty keys to backend ---");
        flushDirty();

        dirtyKeys = jedis.smembers("dirty_keys");
        System.out.println("Dirty keys after flush: " + dirtyKeys);
        System.out.println();
    }

    private void updateProductAsync(String id, String jsonData) {
        String key = "product:" + id;
        jedis.set(key, jsonData);
        jedis.sadd("dirty_keys", key);
        System.out.println("  [CACHE] Written to Redis only, marked dirty: " + key);
    }

    private void flushDirty() {
        Set<String> dirtyKeys = jedis.smembers("dirty_keys");
        System.out.println("  Flushing " + dirtyKeys.size() + " dirty keys");

        for (String key : dirtyKeys) {
            String data = jedis.get(key);
            if (data == null) {
                System.out.println("  [SKIP] " + key + " — no data in cache");
                jedis.srem("dirty_keys", key);
                continue;
            }
            // Extract product ID from key format "product:{id}"
            String id = key.substring(key.indexOf(':') + 1);
            System.out.println("  [FLUSH] PUT " + key + " -> backend /products/" + id);
            String response = httpPut(BACKEND_URL + "/products/" + id, data);
            System.out.println("  [FLUSH] Response: " + response);
            jedis.srem("dirty_keys", key);
        }
    }

    // ---------------------------------------------------------------
    // Exercise 5: Eviction Demo
    // ---------------------------------------------------------------

    private void exerciseEviction() {
        printHeader("Exercise 5: Eviction Demo (LRU)");

        // Flush before reducing memory limit
        jedis.flushAll();

        System.out.println("Setting maxmemory=1mb, policy=allkeys-lru");
        jedis.configSet("maxmemory-policy", "allkeys-lru");
        jedis.configSet("maxmemory", "1048576");

        // Reset stats to get a clean eviction count
        jedis.configResetStat();

        System.out.println("Inserting 200 products into cache...");
        int insertErrors = 0;
        for (int i = 1; i <= 200; i++) {
            try {
                JsonObject product = new JsonObject();
                product.addProperty("id", i);
                product.addProperty("name", "Bulk Product " + i);
                product.addProperty("price", i * 1.99);
                product.addProperty("description", "A".repeat(500));
                jedis.set("evict:product:" + i, gson.toJson(product));
            } catch (JedisDataException e) {
                if (e.getMessage() != null && e.getMessage().contains("OOM")) {
                    insertErrors++;
                } else {
                    throw e;
                }
            }
        }
        if (insertErrors > 0) {
            System.out.println("Insert errors (OOM before eviction): " + insertErrors);
        }

        String stats = jedis.info("stats");
        long evicted = parseStatValue(stats, "evicted_keys");
        System.out.println("Evicted keys: " + evicted);

        long dbSize = jedis.dbSize();
        System.out.println("Keys remaining in DB: " + dbSize);

        // Restore defaults
        System.out.println("\nRestoring maxmemory=10mb, policy=noeviction");
        jedis.configSet("maxmemory", "10485760");
        jedis.configSet("maxmemory-policy", "noeviction");

        // Clean up eviction keys
        for (int i = 1; i <= 200; i++) {
            jedis.del("evict:product:" + i);
        }
        System.out.println();
    }

    private long parseStatValue(String info, String key) {
        for (String line : info.split("\r?\n")) {
            if (line.startsWith(key + ":")) {
                return Long.parseLong(line.split(":")[1].trim());
            }
        }
        return 0;
    }

    // ---------------------------------------------------------------
    // Exercise 6: Benchmark
    // ---------------------------------------------------------------

    private void exerciseBenchmark() {
        printHeader("Exercise 6: Benchmark — Cache Miss vs Hit");

        jedis.flushAll();
        int iterations = 100;

        // Benchmark cache misses
        System.out.println("--- Benchmarking " + iterations + " cache misses ---");
        long totalMissNanos = 0;
        for (int i = 1; i <= iterations; i++) {
            long start = System.nanoTime();
            getProduct(String.valueOf(i));
            totalMissNanos += System.nanoTime() - start;
        }
        double avgMissMs = (totalMissNanos / (double) iterations) / 1_000_000.0;
        System.out.printf("Average cache miss latency: %.2f ms%n%n", avgMissMs);

        // Benchmark cache hits (same keys, now cached)
        System.out.println("--- Benchmarking " + iterations + " cache hits ---");
        long totalHitNanos = 0;
        for (int i = 1; i <= iterations; i++) {
            long start = System.nanoTime();
            getProduct(String.valueOf(i));
            totalHitNanos += System.nanoTime() - start;
        }
        double avgHitMs = (totalHitNanos / (double) iterations) / 1_000_000.0;
        System.out.printf("Average cache hit latency:  %.2f ms%n%n", avgHitMs);

        System.out.printf("Cache hits are %.1fx faster than misses%n%n",
                avgMissMs / avgHitMs);
    }

    // ---------------------------------------------------------------
    // Utility methods
    // ---------------------------------------------------------------

    private static String envOrDefault(String name, String defaultValue) {
        String value = System.getenv(name);
        return (value != null && !value.isEmpty()) ? value : defaultValue;
    }

    private String httpGet(String url) {
        try {
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .GET()
                    .header("Accept", "application/json")
                    .build();
            HttpResponse<String> response = httpClient.send(request,
                    HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                throw new RuntimeException("GET " + url + " returned status "
                        + response.statusCode() + ": " + response.body());
            }
            return response.body();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("HTTP GET interrupted: " + url, e);
        } catch (Exception e) {
            throw new RuntimeException("HTTP GET failed: " + url + " - " + e.getMessage(), e);
        }
    }

    private String httpPut(String url, String jsonBody) {
        try {
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .PUT(HttpRequest.BodyPublishers.ofString(jsonBody))
                    .header("Content-Type", "application/json")
                    .header("Accept", "application/json")
                    .build();
            HttpResponse<String> response = httpClient.send(request,
                    HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                throw new RuntimeException("PUT " + url + " returned status "
                        + response.statusCode() + ": " + response.body());
            }
            return response.body();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("HTTP PUT interrupted: " + url, e);
        } catch (Exception e) {
            throw new RuntimeException("HTTP PUT failed: " + url + " - " + e.getMessage(), e);
        }
    }

    private void printHeader(String title) {
        System.out.println("=".repeat(60));
        System.out.println(title);
        System.out.println("=".repeat(60));
    }
}
