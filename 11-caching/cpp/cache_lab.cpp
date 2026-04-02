#include <chrono>
#include <cstdlib>
#include <functional>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#include <curl/curl.h>
#include <hiredis/hiredis.h>
#include <nlohmann/json.hpp>

using json = nlohmann::json;
using Clock = std::chrono::steady_clock;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

static std::string env_or(const char* name, const char* fallback) {
    const char* val = std::getenv(name);
    return (val != nullptr) ? val : fallback;
}

static size_t curl_write_cb(char* ptr, size_t size, size_t nmemb, void* userdata) {
    auto* buf = static_cast<std::string*>(userdata);
    buf->append(ptr, size * nmemb);
    return size * nmemb;
}

// ---------------------------------------------------------------------------
// Redis wrapper
// ---------------------------------------------------------------------------

class Redis {
public:
    explicit Redis(const std::string& host, int port) {
        ctx_ = redisConnect(host.c_str(), port);
        if (ctx_ == nullptr) {
            throw std::runtime_error("Redis: allocation error");
        }
        if (ctx_->err != 0) {
            std::string msg = "Redis connect error: " + std::string(ctx_->errstr);
            redisFree(ctx_);
            ctx_ = nullptr;
            throw std::runtime_error(msg);
        }
    }

    ~Redis() {
        if (ctx_ != nullptr) {
            redisFree(ctx_);
        }
    }

    Redis(const Redis&) = delete;
    Redis& operator=(const Redis&) = delete;

    std::string get(const std::string& key) {
        auto* reply = static_cast<redisReply*>(redisCommand(ctx_, "GET %s", key.c_str()));
        if (reply == nullptr) {
            throw std::runtime_error("Redis GET failed");
        }
        std::string result;
        if (reply->type == REDIS_REPLY_STRING) {
            result.assign(reply->str, reply->len);
        }
        freeReplyObject(reply);
        return result;
    }

    void set(const std::string& key, const std::string& value) {
        auto* reply = static_cast<redisReply*>(
            redisCommand(ctx_, "SET %s %s", key.c_str(), value.c_str()));
        if (reply == nullptr) {
            throw std::runtime_error("Redis SET failed");
        }
        freeReplyObject(reply);
    }

    void setex(const std::string& key, int ttl, const std::string& value) {
        auto* reply = static_cast<redisReply*>(
            redisCommand(ctx_, "SETEX %s %d %s", key.c_str(), ttl, value.c_str()));
        if (reply == nullptr) {
            throw std::runtime_error("Redis SETEX failed");
        }
        freeReplyObject(reply);
    }

    long long ttl(const std::string& key) {
        auto* reply = static_cast<redisReply*>(redisCommand(ctx_, "TTL %s", key.c_str()));
        if (reply == nullptr) {
            throw std::runtime_error("Redis TTL failed");
        }
        long long val = reply->integer;
        freeReplyObject(reply);
        return val;
    }

    void sadd(const std::string& key, const std::string& member) {
        auto* reply = static_cast<redisReply*>(
            redisCommand(ctx_, "SADD %s %s", key.c_str(), member.c_str()));
        if (reply == nullptr) {
            throw std::runtime_error("Redis SADD failed");
        }
        freeReplyObject(reply);
    }

    std::vector<std::string> smembers(const std::string& key) {
        auto* reply = static_cast<redisReply*>(
            redisCommand(ctx_, "SMEMBERS %s", key.c_str()));
        if (reply == nullptr) {
            throw std::runtime_error("Redis SMEMBERS failed");
        }
        std::vector<std::string> result;
        if (reply->type == REDIS_REPLY_ARRAY) {
            for (size_t i = 0; i < reply->elements; ++i) {
                result.emplace_back(reply->element[i]->str, reply->element[i]->len);
            }
        }
        freeReplyObject(reply);
        return result;
    }

    void srem(const std::string& key, const std::string& member) {
        auto* reply = static_cast<redisReply*>(
            redisCommand(ctx_, "SREM %s %s", key.c_str(), member.c_str()));
        if (reply == nullptr) {
            throw std::runtime_error("Redis SREM failed");
        }
        freeReplyObject(reply);
    }

    void config_set(const std::string& param, const std::string& value) {
        auto* reply = static_cast<redisReply*>(
            redisCommand(ctx_, "CONFIG SET %s %s", param.c_str(), value.c_str()));
        if (reply == nullptr) {
            throw std::runtime_error("Redis CONFIG SET failed");
        }
        freeReplyObject(reply);
    }

    std::string info_stat(const std::string& field) {
        auto* reply = static_cast<redisReply*>(redisCommand(ctx_, "INFO stats"));
        if (reply == nullptr) {
            throw std::runtime_error("Redis INFO failed");
        }
        std::string info(reply->str, reply->len);
        freeReplyObject(reply);

        std::istringstream stream(info);
        std::string line;
        while (std::getline(stream, line)) {
            if (line.rfind(field + ":", 0) == 0) {
                auto val = line.substr(field.size() + 1);
                while (!val.empty() && (val.back() == '\r' || val.back() == '\n')) {
                    val.pop_back();
                }
                return val;
            }
        }
        return "";
    }

    void flushdb() {
        auto* reply = static_cast<redisReply*>(redisCommand(ctx_, "FLUSHDB"));
        if (reply == nullptr) {
            throw std::runtime_error("Redis FLUSHDB failed");
        }
        freeReplyObject(reply);
    }

    void del(const std::string& key) {
        auto* reply = static_cast<redisReply*>(
            redisCommand(ctx_, "DEL %s", key.c_str()));
        if (reply == nullptr) {
            throw std::runtime_error("Redis DEL failed");
        }
        freeReplyObject(reply);
    }

private:
    redisContext* ctx_ = nullptr;
};

// ---------------------------------------------------------------------------
// HTTP client wrapper
// ---------------------------------------------------------------------------

class HttpClient {
public:
    HttpClient() {
        curl_global_init(CURL_GLOBAL_DEFAULT);
    }

    ~HttpClient() {
        curl_global_cleanup();
    }

    HttpClient(const HttpClient&) = delete;
    HttpClient& operator=(const HttpClient&) = delete;

    std::string http_get(const std::string& url) {
        CURL* curl = curl_easy_init();
        if (curl == nullptr) {
            throw std::runtime_error("curl_easy_init failed");
        }
        std::string body;
        curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, curl_write_cb);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, &body);
        curl_easy_setopt(curl, CURLOPT_TIMEOUT, 10L);
        CURLcode res = curl_easy_perform(curl);
        long http_code = 0;
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
        curl_easy_cleanup(curl);
        if (res != CURLE_OK) {
            throw std::runtime_error(std::string("HTTP GET failed: ") + curl_easy_strerror(res));
        }
        if (http_code < 200 || http_code >= 300) {
            throw std::runtime_error("HTTP GET " + url + " returned status "
                                     + std::to_string(http_code));
        }
        return body;
    }

    std::string http_put(const std::string& url, const std::string& json_body) {
        CURL* curl = curl_easy_init();
        if (curl == nullptr) {
            throw std::runtime_error("curl_easy_init failed");
        }
        std::string body;
        struct curl_slist* headers = nullptr;
        headers = curl_slist_append(headers, "Content-Type: application/json");
        curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
        curl_easy_setopt(curl, CURLOPT_CUSTOMREQUEST, "PUT");
        curl_easy_setopt(curl, CURLOPT_POSTFIELDS, json_body.c_str());
        curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, curl_write_cb);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, &body);
        curl_easy_setopt(curl, CURLOPT_TIMEOUT, 10L);
        CURLcode res = curl_easy_perform(curl);
        long http_code = 0;
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
        curl_slist_free_all(headers);
        curl_easy_cleanup(curl);
        if (res != CURLE_OK) {
            throw std::runtime_error(std::string("HTTP PUT failed: ") + curl_easy_strerror(res));
        }
        if (http_code < 200 || http_code >= 300) {
            throw std::runtime_error("HTTP PUT " + url + " returned status "
                                     + std::to_string(http_code));
        }
        return body;
    }
};

// ---------------------------------------------------------------------------
// Timing helper
// ---------------------------------------------------------------------------

static double elapsed_ms(Clock::time_point start) {
    auto end = Clock::now();
    return std::chrono::duration<double, std::milli>(end - start).count();
}

static void print_header(const std::string& title) {
    std::cout << "\n"
              << "============================================================\n"
              << "  " << title << "\n"
              << "============================================================\n"
              << std::endl;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

int main() {
    std::string redis_host = env_or("REDIS_HOST", "localhost");
    std::string backend_host = env_or("BACKEND_HOST", "localhost");
    std::string base_url = "http://" + backend_host + ":5000";

    std::cout << "Connecting to Redis at " << redis_host << ":6379 ..." << std::endl;
    std::cout << "Backend API at " << base_url << std::endl;

    Redis redis(redis_host, 6379);
    HttpClient http;

    redis.flushdb();
    std::cout << "Redis FLUSHDB - starting clean.\n" << std::endl;

    // ======================================================================
    // Exercise 1: Cache-Aside
    // ======================================================================
    print_header("Exercise 1: Cache-Aside Pattern");

    auto get_product = [&](int id) -> json {
        std::string key = "product:" + std::to_string(id);
        std::string cached = redis.get(key);

        if (!cached.empty()) {
            std::cout << "  [HIT]  product:" << id << " found in cache" << std::endl;
            return json::parse(cached);
        }

        std::cout << "  [MISS] product:" << id << " - fetching from backend..." << std::endl;
        std::string url = base_url + "/products/" + std::to_string(id);
        std::string body = http.http_get(url);
        redis.set(key, body);
        return json::parse(body);
    };

    // First call - cache miss
    auto t1 = Clock::now();
    json p1 = get_product(1);
    double ms1 = elapsed_ms(t1);
    std::cout << "  Result: " << p1.dump() << std::endl;
    std::cout << "  Time:   " << ms1 << " ms\n" << std::endl;

    // Second call - cache hit
    auto t2 = Clock::now();
    json p1_cached = get_product(1);
    double ms2 = elapsed_ms(t2);
    std::cout << "  Result: " << p1_cached.dump() << std::endl;
    std::cout << "  Time:   " << ms2 << " ms\n" << std::endl;

    std::cout << "  Speedup: " << (ms1 / ms2) << "x faster from cache" << std::endl;

    // ======================================================================
    // Exercise 2: Read-Through with TTL
    // ======================================================================
    print_header("Exercise 2: Read-Through with TTL");

    auto read_through = [&](const std::string& key, int ttl_seconds,
                            std::function<std::string()> fetch_fn) -> std::string {
        std::string cached = redis.get(key);
        if (!cached.empty()) {
            std::cout << "  [HIT]  " << key << " found in cache" << std::endl;
            return cached;
        }
        std::cout << "  [MISS] " << key << " - calling fetch function..." << std::endl;
        std::string value = fetch_fn();
        redis.setex(key, ttl_seconds, value);
        std::cout << "  Stored with TTL=" << ttl_seconds << "s" << std::endl;
        return value;
    };

    int ttl_seconds = 30;
    std::string key2 = "product:2";

    auto fetch_product_2 = [&]() -> std::string {
        std::string url = base_url + "/products/2";
        return http.http_get(url);
    };

    // First call - miss
    auto t3 = Clock::now();
    std::string result2 = read_through(key2, ttl_seconds, fetch_product_2);
    double ms3 = elapsed_ms(t3);
    std::cout << "  Result: " << result2 << std::endl;
    std::cout << "  Time:   " << ms3 << " ms" << std::endl;

    long long remaining_ttl = redis.ttl(key2);
    std::cout << "  TTL remaining: " << remaining_ttl << "s\n" << std::endl;

    // Second call - hit
    auto t4 = Clock::now();
    std::string result2_cached = read_through(key2, ttl_seconds, fetch_product_2);
    double ms4 = elapsed_ms(t4);
    std::cout << "  Result: " << result2_cached << std::endl;
    std::cout << "  Time:   " << ms4 << " ms" << std::endl;

    remaining_ttl = redis.ttl(key2);
    std::cout << "  TTL remaining: " << remaining_ttl << "s" << std::endl;

    // ======================================================================
    // Exercise 3: Write-Through
    // ======================================================================
    print_header("Exercise 3: Write-Through Pattern");

    auto update_product = [&](int id, const json& data) {
        std::string key = "product:" + std::to_string(id);
        std::string url = base_url + "/products/" + std::to_string(id);
        std::string payload = data.dump();

        std::cout << "  Writing to backend: PUT " << url << std::endl;
        std::string backend_response = http.http_put(url, payload);
        std::cout << "  Backend response: " << backend_response << std::endl;

        std::cout << "  Writing to cache:  SET " << key << std::endl;
        redis.set(key, backend_response);
        std::cout << "  Write-through complete." << std::endl;
    };

    json update_data = {{"price", 99.99}};
    update_product(1, update_data);

    std::string verify = redis.get("product:1");
    std::cout << "\n  Verification - cache read: " << verify << std::endl;
    json verify_json = json::parse(verify);
    std::cout << "  Price in cache: " << verify_json.value("price", 0.0) << std::endl;

    // ======================================================================
    // Exercise 4: Write-Back (Write-Behind)
    // ======================================================================
    print_header("Exercise 4: Write-Back (Write-Behind) Pattern");

    auto update_product_async = [&](int id, const json& data) {
        std::string key = "product:" + std::to_string(id);
        std::string payload = data.dump();

        redis.set(key, payload);
        redis.sadd("dirty_keys", key);
        std::cout << "  [ASYNC] Wrote product:" << id
                  << " to cache, marked dirty" << std::endl;
    };

    auto flush_dirty = [&]() {
        std::vector<std::string> dirty = redis.smembers("dirty_keys");
        std::cout << "  Flushing " << dirty.size() << " dirty keys to backend...\n"
                  << std::endl;

        for (const auto& key : dirty) {
            // Extract product ID from key "product:N"
            std::string id_str = key.substr(key.find(':') + 1);
            std::string cached_val = redis.get(key);
            std::string url = base_url + "/products/" + id_str;

            std::cout << "  PUT " << url << " -> " << cached_val << std::endl;
            http.http_put(url, cached_val);
            redis.srem("dirty_keys", key);
            std::cout << "  Removed " << key << " from dirty_keys" << std::endl;
        }

        std::cout << "\n  Flush complete. Remaining dirty keys: "
                  << redis.smembers("dirty_keys").size() << std::endl;
    };

    update_product_async(3, {{"name", "Widget C"}, {"price", 15.00}});
    update_product_async(4, {{"name", "Widget D"}, {"price", 25.50}});
    update_product_async(5, {{"name", "Widget E"}, {"price", 35.75}});

    std::cout << std::endl;
    flush_dirty();

    // ======================================================================
    // Exercise 5: Eviction Demo
    // ======================================================================
    print_header("Exercise 5: Eviction Demo (LRU)");

    redis.flushdb();

    std::string evicted_before = redis.info_stat("evicted_keys");
    std::cout << "  Evicted keys before: " << evicted_before << std::endl;

    std::cout << "  Setting maxmemory=1mb, policy=allkeys-lru ..." << std::endl;
    redis.config_set("maxmemory-policy", "allkeys-lru");
    redis.config_set("maxmemory", "1mb");

    std::cout << "  Inserting 200 products into cache..." << std::endl;
    for (int i = 1; i <= 200; ++i) {
        json product = {
            {"id", i},
            {"name", "Product " + std::to_string(i)},
            {"price", 10.0 + i},
            {"description", std::string(500, 'x')}  // pad to force eviction
        };
        std::string key = "evict_product:" + std::to_string(i);
        try {
            redis.set(key, product.dump());
        } catch (const std::exception& e) {
            std::cout << "  Warning at key " << i << ": " << e.what() << std::endl;
        }
    }

    std::string evicted_after = redis.info_stat("evicted_keys");
    std::cout << "  Evicted keys after: " << evicted_after << std::endl;
    std::cout << "  Keys evicted during demo: "
              << (std::stoll(evicted_after) - std::stoll(evicted_before)) << std::endl;

    std::cout << "\n  Resetting maxmemory=10mb, policy=noeviction ..." << std::endl;
    redis.config_set("maxmemory", "10mb");
    redis.config_set("maxmemory-policy", "noeviction");
    std::cout << "  Eviction config restored." << std::endl;

    // ======================================================================
    // Exercise 6: Benchmark
    // ======================================================================
    print_header("Exercise 6: Benchmark - Cache Miss vs Cache Hit");

    redis.flushdb();

    const int iterations = 100;

    // --- Cache misses ---
    std::cout << "  Timing " << iterations << " cache misses..." << std::endl;
    auto miss_start = Clock::now();
    for (int i = 1; i <= iterations; ++i) {
        std::string key = "bench_product:" + std::to_string(i);
        std::string url = base_url + "/products/" + std::to_string(i);
        std::string body = http.http_get(url);
        redis.set(key, body);
    }
    double miss_total = elapsed_ms(miss_start);
    double miss_avg = miss_total / iterations;
    std::cout << "  Total:   " << miss_total << " ms" << std::endl;
    std::cout << "  Average: " << miss_avg << " ms per miss\n" << std::endl;

    // --- Cache hits ---
    std::cout << "  Timing " << iterations << " cache hits..." << std::endl;
    auto hit_start = Clock::now();
    for (int i = 1; i <= iterations; ++i) {
        std::string key = "bench_product:" + std::to_string(i);
        redis.get(key);
    }
    double hit_total = elapsed_ms(hit_start);
    double hit_avg = hit_total / iterations;
    std::cout << "  Total:   " << hit_total << " ms" << std::endl;
    std::cout << "  Average: " << hit_avg << " ms per hit\n" << std::endl;

    std::cout << "  Speedup: " << (miss_avg / hit_avg) << "x faster from cache" << std::endl;

    // --- Cleanup ---
    redis.flushdb();

    print_header("All exercises complete!");

    return 0;
}
