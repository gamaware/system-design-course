// Lab 11 caching exercises in Go (go-redis v9 + net/http).
//
// Same six exercises and output as the C++, C# and Java programs:
// cache-aside, read-through with TTL, write-through, write-back,
// LRU eviction and a cache miss vs hit benchmark.
package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/redis/go-redis/v9"
)

const httpTimeout = 10 * time.Second

var (
	redisHost   = envOrDefault("REDIS_HOST", "localhost")
	backendHost = envOrDefault("BACKEND_HOST", "localhost")
	backendURL  = "http://" + backendHost + ":5000"

	ctx        = context.Background()
	rdb        *redis.Client
	httpClient = &http.Client{Timeout: httpTimeout}
)

// price marshals like Gson in the Java version: 42 becomes 42.0, 31.5 stays 31.5.
type price float64

func (p price) MarshalJSON() ([]byte, error) {
	s := strconv.FormatFloat(float64(p), 'f', -1, 64)
	if !strings.Contains(s, ".") {
		s += ".0"
	}
	return []byte(s), nil
}

type productUpdate struct {
	Name  string `json:"name"`
	Price price  `json:"price"`
}

type bulkProduct struct {
	ID          int    `json:"id"`
	Name        string `json:"name"`
	Price       price  `json:"price"`
	Description string `json:"description"`
}

func main() {
	rdb = redis.NewClient(&redis.Options{Addr: redisHost + ":6379"})
	defer rdb.Close()

	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, "Error:", err)
		os.Exit(1)
	}
}

func run() error {
	if err := rdb.Ping(ctx).Err(); err != nil {
		return err
	}
	fmt.Println("Connected to Redis at " + redisHost + ":6379")
	fmt.Println("Backend API at " + backendURL)
	if err := rdb.FlushAll(ctx).Err(); err != nil {
		return err
	}
	fmt.Println("Flushed all Redis keys")
	fmt.Println()

	exercises := []func() error{
		exerciseCacheAside,
		exerciseReadThrough,
		exerciseWriteThrough,
		exerciseWriteBack,
		exerciseEviction,
		exerciseBenchmark,
	}
	for _, exercise := range exercises {
		if err := exercise(); err != nil {
			return err
		}
	}

	fmt.Println("\n=== All exercises completed ===")
	return nil
}

// ---------------------------------------------------------------
// Exercise 1: Cache-Aside
// ---------------------------------------------------------------

func exerciseCacheAside() error {
	printHeader("Exercise 1: Cache-Aside Pattern")

	fmt.Println("--- First call (cache miss) ---")
	start := time.Now()
	result1, err := getProduct("1")
	if err != nil {
		return err
	}
	elapsed1 := msSince(start)
	fmt.Println("Result: " + result1)
	fmt.Printf("Time: %.2f ms\n\n", elapsed1)

	fmt.Println("--- Second call (cache hit) ---")
	start = time.Now()
	result2, err := getProduct("1")
	if err != nil {
		return err
	}
	elapsed2 := msSince(start)
	fmt.Println("Result: " + result2)
	fmt.Printf("Time: %.2f ms\n\n", elapsed2)

	fmt.Printf("Speed improvement: %.1fx faster\n\n", elapsed1/elapsed2)
	return nil
}

func getProduct(id string) (string, error) {
	key := "product:" + id
	cached, err := rdb.Get(ctx, key).Result()
	if err == nil {
		fmt.Println("  [HIT] Found in Redis")
		return cached, nil
	}
	if !errors.Is(err, redis.Nil) {
		return "", err
	}
	fmt.Println("  [MISS] Fetching from backend API")
	data, err := httpGet(backendURL + "/products/" + id)
	if err != nil {
		return "", err
	}
	if err := rdb.Set(ctx, key, data, 0).Err(); err != nil {
		return "", err
	}
	fmt.Println("  [STORE] Saved to Redis")
	return data, nil
}

// ---------------------------------------------------------------
// Exercise 2: Read-Through with TTL
// ---------------------------------------------------------------

func exerciseReadThrough() error {
	printHeader("Exercise 2: Read-Through with TTL")

	key := "product:2"
	ttl := 30

	fmt.Printf("--- Read-through with %ds TTL ---\n", ttl)
	start := time.Now()
	result, err := readThrough(key, ttl, func() (string, error) {
		fmt.Println("  [SUPPLIER] Fetching product 2 from backend")
		return httpGet(backendURL + "/products/2")
	})
	if err != nil {
		return err
	}
	elapsed := msSince(start)
	fmt.Println("Result: " + result)
	fmt.Printf("Time: %.2f ms\n", elapsed)
	if err := printTTL(key, ""); err != nil {
		return err
	}

	fmt.Println("\n--- Second read (cache hit) ---")
	start = time.Now()
	result, err = readThrough(key, ttl, func() (string, error) {
		fmt.Println("  [SUPPLIER] This should not be called")
		return httpGet(backendURL + "/products/2")
	})
	if err != nil {
		return err
	}
	elapsed = msSince(start)
	fmt.Println("Result: " + result)
	fmt.Printf("Time: %.2f ms\n", elapsed)
	return printTTL(key, "\n")
}

func readThrough(key string, ttlSeconds int, fetchFunction func() (string, error)) (string, error) {
	cached, err := rdb.Get(ctx, key).Result()
	if err == nil {
		fmt.Println("  [HIT] Found in Redis")
		return cached, nil
	}
	if !errors.Is(err, redis.Nil) {
		return "", err
	}
	fmt.Println("  [MISS] Cache miss, calling supplier")
	data, err := fetchFunction()
	if err != nil {
		return "", err
	}
	if err := rdb.SetEx(ctx, key, data, time.Duration(ttlSeconds)*time.Second).Err(); err != nil {
		return "", err
	}
	fmt.Printf("  [STORE] Saved to Redis with TTL=%ds\n", ttlSeconds)
	return data, nil
}

// printTTL prints the remaining TTL in whole seconds, as the TTL command reports it.
func printTTL(key, suffix string) error {
	seconds, err := rdb.Do(ctx, "TTL", key).Int64()
	if err != nil {
		return err
	}
	fmt.Printf("TTL remaining: %ds\n%s", seconds, suffix)
	return nil
}

// ---------------------------------------------------------------
// Exercise 3: Write-Through
// ---------------------------------------------------------------

func exerciseWriteThrough() error {
	printHeader("Exercise 3: Write-Through Pattern")

	jsonData, err := toJSON(productUpdate{Name: "Premium Widget", Price: 99.99})
	if err != nil {
		return err
	}

	fmt.Println("Updating product 1: " + jsonData)
	if err := updateProduct("1", jsonData); err != nil {
		return err
	}

	cached, err := rdb.Get(ctx, "product:1").Result()
	if err != nil {
		return err
	}
	fmt.Println("\nVerification - Redis now contains: " + cached)
	fmt.Println("Write-through complete: both backend and cache updated")
	fmt.Println()
	return nil
}

func updateProduct(id, jsonData string) error {
	url := backendURL + "/products/" + id
	fmt.Println("  [BACKEND] PUT to " + url)
	backendResponse, err := httpPut(url, jsonData)
	if err != nil {
		return err
	}
	fmt.Println("  [BACKEND] Response: " + backendResponse)

	key := "product:" + id
	if err := rdb.Set(ctx, key, backendResponse, 0).Err(); err != nil {
		return err
	}
	fmt.Println("  [CACHE] Updated Redis key: " + key)
	return nil
}

// ---------------------------------------------------------------
// Exercise 4: Write-Back (Write-Behind)
// ---------------------------------------------------------------

func exerciseWriteBack() error {
	printHeader("Exercise 4: Write-Back (Write-Behind) Pattern")

	for _, id := range []string{"3", "4", "5"} {
		n, err := strconv.ParseFloat(id, 64)
		if err != nil {
			return err
		}
		jsonData, err := toJSON(productUpdate{Name: "Product " + id, Price: price(n * 10.50)})
		if err != nil {
			return err
		}
		fmt.Printf("Async update product %s: %s\n", id, jsonData)
		if err := updateProductAsync(id, jsonData); err != nil {
			return err
		}
	}

	dirtyKeys, err := rdb.SMembers(ctx, "dirty_keys").Result()
	if err != nil {
		return err
	}
	fmt.Println("\nDirty keys before flush: " + formatSet(dirtyKeys))

	fmt.Println("\n--- Flushing dirty keys to backend ---")
	if err := flushDirty(); err != nil {
		return err
	}

	dirtyKeys, err = rdb.SMembers(ctx, "dirty_keys").Result()
	if err != nil {
		return err
	}
	fmt.Println("Dirty keys after flush: " + formatSet(dirtyKeys))
	fmt.Println()
	return nil
}

func updateProductAsync(id, jsonData string) error {
	key := "product:" + id
	if err := rdb.Set(ctx, key, jsonData, 0).Err(); err != nil {
		return err
	}
	if err := rdb.SAdd(ctx, "dirty_keys", key).Err(); err != nil {
		return err
	}
	fmt.Println("  [CACHE] Written to Redis only, marked dirty: " + key)
	return nil
}

func flushDirty() error {
	dirtyKeys, err := rdb.SMembers(ctx, "dirty_keys").Result()
	if err != nil {
		return err
	}
	sort.Strings(dirtyKeys)
	fmt.Printf("  Flushing %d dirty keys\n", len(dirtyKeys))

	for _, key := range dirtyKeys {
		data, err := rdb.Get(ctx, key).Result()
		if errors.Is(err, redis.Nil) {
			fmt.Println("  [SKIP] " + key + " — no data in cache")
			if err := rdb.SRem(ctx, "dirty_keys", key).Err(); err != nil {
				return err
			}
			continue
		}
		if err != nil {
			return err
		}
		// Extract product ID from key format "product:{id}"
		id := key[strings.Index(key, ":")+1:]
		fmt.Printf("  [FLUSH] PUT %s -> backend /products/%s\n", key, id)
		response, err := httpPut(backendURL+"/products/"+id, data)
		if err != nil {
			return err
		}
		fmt.Println("  [FLUSH] Response: " + response)
		if err := rdb.SRem(ctx, "dirty_keys", key).Err(); err != nil {
			return err
		}
	}
	return nil
}

func formatSet(members []string) string {
	sort.Strings(members)
	return "[" + strings.Join(members, ", ") + "]"
}

// ---------------------------------------------------------------
// Exercise 5: Eviction Demo
// ---------------------------------------------------------------

func exerciseEviction() error {
	printHeader("Exercise 5: Eviction Demo (LRU)")

	// Flush before reducing memory limit
	if err := rdb.FlushAll(ctx).Err(); err != nil {
		return err
	}

	fmt.Println("Setting maxmemory=1mb, policy=allkeys-lru")
	if err := rdb.ConfigSet(ctx, "maxmemory-policy", "allkeys-lru").Err(); err != nil {
		return err
	}
	if err := rdb.ConfigSet(ctx, "maxmemory", "1048576").Err(); err != nil {
		return err
	}

	// Reset stats to get a clean eviction count
	if err := rdb.ConfigResetStat(ctx).Err(); err != nil {
		return err
	}

	fmt.Println("Inserting 200 products into cache...")
	insertErrors := 0
	for i := 1; i <= 200; i++ {
		jsonData, err := toJSON(bulkProduct{
			ID:          i,
			Name:        fmt.Sprintf("Bulk Product %d", i),
			Price:       price(float64(i) * 1.99),
			Description: strings.Repeat("A", 500),
		})
		if err != nil {
			return err
		}
		err = rdb.Set(ctx, fmt.Sprintf("evict:product:%d", i), jsonData, 0).Err()
		if err != nil {
			if !strings.HasPrefix(err.Error(), "OOM") {
				return err
			}
			insertErrors++
		}
	}
	if insertErrors > 0 {
		fmt.Printf("Insert errors (OOM before eviction): %d\n", insertErrors)
	}

	stats, err := rdb.Info(ctx, "stats").Result()
	if err != nil {
		return err
	}
	fmt.Printf("Evicted keys: %d\n", parseStatValue(stats, "evicted_keys"))

	dbSize, err := rdb.DBSize(ctx).Result()
	if err != nil {
		return err
	}
	fmt.Printf("Keys remaining in DB: %d\n", dbSize)

	// Restore defaults
	fmt.Println("\nRestoring maxmemory=10mb, policy=noeviction")
	if err := rdb.ConfigSet(ctx, "maxmemory", "10485760").Err(); err != nil {
		return err
	}
	if err := rdb.ConfigSet(ctx, "maxmemory-policy", "noeviction").Err(); err != nil {
		return err
	}

	// Clean up eviction keys
	keys := make([]string, 0, 200)
	for i := 1; i <= 200; i++ {
		keys = append(keys, fmt.Sprintf("evict:product:%d", i))
	}
	if err := rdb.Del(ctx, keys...).Err(); err != nil {
		return err
	}
	fmt.Println()
	return nil
}

func parseStatValue(info, key string) int64 {
	for _, line := range strings.Split(info, "\n") {
		line = strings.TrimSpace(line)
		if value, found := strings.CutPrefix(line, key+":"); found {
			n, err := strconv.ParseInt(value, 10, 64)
			if err == nil {
				return n
			}
		}
	}
	return 0
}

// ---------------------------------------------------------------
// Exercise 6: Benchmark
// ---------------------------------------------------------------

func exerciseBenchmark() error {
	printHeader("Exercise 6: Benchmark — Cache Miss vs Hit")

	if err := rdb.FlushAll(ctx).Err(); err != nil {
		return err
	}
	iterations := 100

	// Benchmark cache misses
	fmt.Printf("--- Benchmarking %d cache misses ---\n", iterations)
	var totalMiss time.Duration
	for i := 1; i <= iterations; i++ {
		start := time.Now()
		if _, err := getProduct(strconv.Itoa(i)); err != nil {
			return err
		}
		totalMiss += time.Since(start)
	}
	avgMissMs := float64(totalMiss.Nanoseconds()) / float64(iterations) / 1e6
	fmt.Printf("Average cache miss latency: %.2f ms\n\n", avgMissMs)

	// Benchmark cache hits (same keys, now cached)
	fmt.Printf("--- Benchmarking %d cache hits ---\n", iterations)
	var totalHit time.Duration
	for i := 1; i <= iterations; i++ {
		start := time.Now()
		if _, err := getProduct(strconv.Itoa(i)); err != nil {
			return err
		}
		totalHit += time.Since(start)
	}
	avgHitMs := float64(totalHit.Nanoseconds()) / float64(iterations) / 1e6
	fmt.Printf("Average cache hit latency:  %.2f ms\n\n", avgHitMs)

	fmt.Printf("Cache hits are %.1fx faster than misses\n\n", avgMissMs/avgHitMs)
	return nil
}

// ---------------------------------------------------------------
// Utility functions
// ---------------------------------------------------------------

func envOrDefault(name, defaultValue string) string {
	if value := os.Getenv(name); value != "" {
		return value
	}
	return defaultValue
}

func msSince(start time.Time) float64 {
	return float64(time.Since(start).Nanoseconds()) / 1e6
}

func toJSON(v any) (string, error) {
	b, err := json.Marshal(v)
	return string(b), err
}

func httpGet(url string) (string, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return "", err
	}
	req.Header.Set("Accept", "application/json")
	return doRequest(req)
}

func httpPut(url, jsonBody string) (string, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodPut, url, strings.NewReader(jsonBody))
	if err != nil {
		return "", err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	return doRequest(req)
}

func doRequest(req *http.Request) (string, error) {
	resp, err := httpClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("HTTP %s failed: %s - %w", req.Method, req.URL, err)
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("HTTP %s failed reading body: %s - %w", req.Method, req.URL, err)
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return "", fmt.Errorf("%s %s returned status %d: %s", req.Method, req.URL, resp.StatusCode, body)
	}
	return string(body), nil
}

func printHeader(title string) {
	fmt.Println(strings.Repeat("=", 60))
	fmt.Println(title)
	fmt.Println(strings.Repeat("=", 60))
}
