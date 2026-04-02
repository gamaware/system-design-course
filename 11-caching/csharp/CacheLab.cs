using System;
using System.Diagnostics;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using StackExchange.Redis;

class CacheLab
{
    private static ConnectionMultiplexer redis = null!;
    private static IDatabase db = null!;
    private static IServer server = null!;
    private static HttpClient http = null!;
    private static string backendBase = null!;

    static async Task Main()
    {
        var redisHost = Environment.GetEnvironmentVariable("REDIS_HOST") ?? "localhost";
        var backendHost = Environment.GetEnvironmentVariable("BACKEND_HOST") ?? "localhost";
        backendBase = $"http://{backendHost}:5000";

        Console.WriteLine($"Connecting to Redis at {redisHost}:6379 ...");
        redis = ConnectionMultiplexer.Connect($"{redisHost}:6379,allowAdmin=true");
        db = redis.GetDatabase();
        server = redis.GetServer($"{redisHost}:6379");

        http = new HttpClient { BaseAddress = new Uri(backendBase) };

        Console.WriteLine("Connected. Starting exercises.\n");

        await Exercise1_CacheAside();
        await Exercise2_ReadThroughTTL();
        await Exercise3_WriteThrough();
        await Exercise4_WriteBack();
        await Exercise5_EvictionDemo();
        await Exercise6_Benchmark();

        Console.WriteLine("All exercises complete.");
        redis.Dispose();
        http.Dispose();
    }

    // ----------------------------------------------------------------
    // Exercise 1: Cache-Aside
    // ----------------------------------------------------------------
    static async Task Exercise1_CacheAside()
    {
        Console.WriteLine("========================================");
        Console.WriteLine("Exercise 1: Cache-Aside");
        Console.WriteLine("========================================\n");

        // First call - cache miss
        var sw = Stopwatch.StartNew();
        var product = await GetProduct(1);
        sw.Stop();
        Console.WriteLine($"First call  (miss): {sw.ElapsedMilliseconds} ms");
        Console.WriteLine($"  Result: {product}\n");

        // Second call - cache hit
        sw.Restart();
        product = await GetProduct(1);
        sw.Stop();
        Console.WriteLine($"Second call (hit):  {sw.ElapsedMilliseconds} ms");
        Console.WriteLine($"  Result: {product}\n");
    }

    static async Task<string> GetProduct(int id)
    {
        string key = $"product:{id}";
        var cached = db.StringGet(key);
        if (cached.HasValue)
        {
            Console.WriteLine($"  Cache HIT for {key}");
            return cached.ToString();
        }

        Console.WriteLine($"  Cache MISS for {key} - fetching from backend");
        var response = await http.GetAsync($"/products/{id}");
        response.EnsureSuccessStatusCode();
        var body = await response.Content.ReadAsStringAsync();
        db.StringSet(key, body);
        return body;
    }

    // ----------------------------------------------------------------
    // Exercise 2: Read-Through with TTL
    // ----------------------------------------------------------------
    static async Task Exercise2_ReadThroughTTL()
    {
        Console.WriteLine("========================================");
        Console.WriteLine("Exercise 2: Read-Through with TTL");
        Console.WriteLine("========================================\n");

        string key = "product:2";
        var ttl = TimeSpan.FromSeconds(30);

        var sw = Stopwatch.StartNew();
        var result = await ReadThrough(key, ttl, async () =>
        {
            var r = await http.GetAsync("/products/2");
            r.EnsureSuccessStatusCode();
            return await r.Content.ReadAsStringAsync();
        });
        sw.Stop();
        Console.WriteLine($"First call  (miss): {sw.ElapsedMilliseconds} ms");
        Console.WriteLine($"  Result: {result}");

        var remaining = db.KeyTimeToLive(key);
        Console.WriteLine($"  TTL remaining: {remaining}\n");

        sw.Restart();
        result = await ReadThrough(key, ttl, async () =>
        {
            var r = await http.GetAsync("/products/2");
            r.EnsureSuccessStatusCode();
            return await r.Content.ReadAsStringAsync();
        });
        sw.Stop();
        Console.WriteLine($"Second call (hit):  {sw.ElapsedMilliseconds} ms");
        Console.WriteLine($"  Result: {result}");

        remaining = db.KeyTimeToLive(key);
        Console.WriteLine($"  TTL remaining: {remaining}\n");
    }

    static async Task<string> ReadThrough(string key, TimeSpan ttl, Func<Task<string>> fetchFunction)
    {
        var cached = db.StringGet(key);
        if (cached.HasValue)
        {
            Console.WriteLine($"  Cache HIT for {key}");
            return cached.ToString();
        }

        Console.WriteLine($"  Cache MISS for {key} - fetching from backend");
        var value = await fetchFunction();
        db.StringSet(key, value, ttl);
        return value;
    }

    // ----------------------------------------------------------------
    // Exercise 3: Write-Through
    // ----------------------------------------------------------------
    static async Task Exercise3_WriteThrough()
    {
        Console.WriteLine("========================================");
        Console.WriteLine("Exercise 3: Write-Through");
        Console.WriteLine("========================================\n");

        var updated = JsonSerializer.Serialize(new { name = "Widget", price = 99.99 });
        await UpdateProduct(1, updated);

        var fromCache = db.StringGet("product:1");
        Console.WriteLine($"Read from Redis after write-through:");
        Console.WriteLine($"  {fromCache}\n");
    }

    static async Task UpdateProduct(int id, string jsonData)
    {
        string key = $"product:{id}";
        Console.WriteLine($"  Writing to backend PUT /products/{id} ...");
        var content = new StringContent(jsonData, Encoding.UTF8, "application/json");
        var response = await http.PutAsync($"/products/{id}", content);
        response.EnsureSuccessStatusCode();
        var responseBody = await response.Content.ReadAsStringAsync();
        Console.WriteLine($"  Backend updated (status {(int)response.StatusCode})");

        Console.WriteLine($"  Writing to Redis key {key} ...");
        db.StringSet(key, responseBody);
        Console.WriteLine("  Redis updated\n");
    }

    // ----------------------------------------------------------------
    // Exercise 4: Write-Back (Write-Behind)
    // ----------------------------------------------------------------
    static async Task Exercise4_WriteBack()
    {
        Console.WriteLine("========================================");
        Console.WriteLine("Exercise 4: Write-Back (Write-Behind)");
        Console.WriteLine("========================================\n");

        // Update products 3, 4, 5 asynchronously (Redis only)
        for (int id = 3; id <= 5; id++)
        {
            var data = JsonSerializer.Serialize(new { name = $"Product {id}", price = id * 10.0 });
            UpdateProductAsync(id, data);
        }
        Console.WriteLine("  All 3 products written to Redis (dirty)\n");

        var dirty = db.SetMembers("dirty_keys");
        Console.WriteLine($"  Dirty keys: {string.Join(", ", dirty)}\n");

        // Flush dirty keys to backend
        Console.WriteLine("  Flushing dirty keys to backend ...");
        await FlushDirty();
        Console.WriteLine();
    }

    static void UpdateProductAsync(int id, string jsonData)
    {
        string key = $"product:{id}";
        Console.WriteLine($"  [async] Writing product:{id} to Redis only");
        db.StringSet(key, jsonData);
        db.SetAdd("dirty_keys", key);
    }

    static async Task FlushDirty()
    {
        var dirtyKeys = db.SetMembers("dirty_keys");
        Console.WriteLine($"  Found {dirtyKeys.Length} dirty key(s) to flush");

        foreach (var key in dirtyKeys)
        {
            var value = db.StringGet(key.ToString());
            if (!value.HasValue)
            {
                Console.WriteLine($"  WARNING: {key} not found in Redis, skipping");
                continue;
            }

            // Extract id from key format "product:{id}"
            var parts = key.ToString().Split(':');
            var id = parts[1];

            Console.WriteLine($"  Flushing {key} -> PUT /products/{id}");
            var content = new StringContent(value.ToString(), Encoding.UTF8, "application/json");
            var response = await http.PutAsync($"/products/{id}", content);
            response.EnsureSuccessStatusCode();

            db.SetRemove("dirty_keys", key);
        }

        Console.WriteLine("  Flush complete");
    }

    // ----------------------------------------------------------------
    // Exercise 5: Eviction Demo
    // ----------------------------------------------------------------
    static async Task Exercise5_EvictionDemo()
    {
        Console.WriteLine("========================================");
        Console.WriteLine("Exercise 5: Eviction Demo");
        Console.WriteLine("========================================\n");

        // Flush existing data before reducing memory limit
        server.FlushAllDatabases();

        // Set maxmemory to 1 MB and LRU policy
        Console.WriteLine("  Setting maxmemory=1mb, maxmemory-policy=allkeys-lru");
        server.Execute("CONFIG", "SET", "maxmemory-policy", "allkeys-lru");
        server.Execute("CONFIG", "SET", "maxmemory", "1mb");

        // Insert 200 products
        Console.WriteLine("  Inserting 200 products into cache ...");
        var largeValue = new string('x', 500);
        for (int i = 1; i <= 200; i++)
        {
            try
            {
                var data = JsonSerializer.Serialize(new { name = $"Product {i}", description = largeValue });
                db.StringSet($"evict:product:{i}", data);
            }
            catch (RedisServerException)
            {
                // OOM during eviction — some entries may not fit
            }
        }

        // Check evicted keys from INFO stats
        var info = server.InfoRaw("stats");
        foreach (var line in info.Split('\n'))
        {
            if (line.StartsWith("evicted_keys", StringComparison.OrdinalIgnoreCase))
            {
                Console.WriteLine($"  {line.Trim()}");
                break;
            }
        }

        // Reset
        Console.WriteLine("\n  Resetting maxmemory=10mb, maxmemory-policy=noeviction");
        server.Execute("CONFIG", "SET", "maxmemory", "10mb");
        server.Execute("CONFIG", "SET", "maxmemory-policy", "noeviction");
        Console.WriteLine();

        await Task.CompletedTask;
    }

    // ----------------------------------------------------------------
    // Exercise 6: Benchmark
    // ----------------------------------------------------------------
    static async Task Exercise6_Benchmark()
    {
        Console.WriteLine("========================================");
        Console.WriteLine("Exercise 6: Benchmark");
        Console.WriteLine("========================================\n");

        // Clean slate
        server.FlushAllDatabases();
        Console.WriteLine("  Flushed Redis\n");

        // 100 cache misses
        Console.WriteLine("  Timing 100 cache misses ...");
        var sw = Stopwatch.StartNew();
        for (int i = 1; i <= 100; i++)
        {
            try
            {
                var product = await GetProduct(i);
            }
            catch (HttpRequestException ex)
            {
                Console.WriteLine($"  Error fetching product {i}: {ex.Message}");
                break;
            }
        }
        sw.Stop();
        var missTotal = sw.ElapsedMilliseconds;
        Console.WriteLine($"  100 cache misses: {missTotal} ms total, {missTotal / 100.0:F1} ms avg\n");

        // 100 cache hits (same keys, now cached)
        Console.WriteLine("  Timing 100 cache hits ...");
        sw.Restart();
        for (int i = 1; i <= 100; i++)
        {
            await GetProduct(i);
        }
        sw.Stop();
        var hitTotal = sw.ElapsedMilliseconds;
        Console.WriteLine($"  100 cache hits:   {hitTotal} ms total, {hitTotal / 100.0:F1} ms avg\n");

        Console.WriteLine($"  Speedup: {(double)missTotal / Math.Max(hitTotal, 1):F1}x faster with cache\n");
    }
}
