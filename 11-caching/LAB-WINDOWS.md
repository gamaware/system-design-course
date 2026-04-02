# Lab 11 -- Windows Instructions

> For an overview, architecture diagrams, and key concepts, see [README.md](README.md).
> For macOS/Linux, see [LAB-MACOS.md](LAB-MACOS.md).

## Prerequisites

### Required Tools

You need Docker Desktop installed on your machine. Docker Desktop includes
Docker Engine and Docker Compose.

#### Docker Desktop

**Option 1 -- Direct download (recommended):**

Download the installer from the
[Docker Desktop page](https://www.docker.com/products/docker-desktop/) and
run the `.exe` file. Follow the installation wizard and restart your computer
when prompted.

**Option 2 -- Chocolatey:**

```powershell
choco install docker-desktop
```

**Option 3 -- winget:**

```powershell
winget install Docker.DockerDesktop
```

After installation, open Docker Desktop and wait for the engine to start
(the whale icon in the system tray should stop animating).

**Verify the installation:**

```powershell
docker --version
docker compose version
```

Expected output (versions may differ):

```text
Docker version 27.x.x, build ...
Docker Compose version v2.x.x
```

### Choose Your Language

Pick one language for the exercises. You do not need C++, C#, and Java
installed locally -- everything runs inside Docker containers.

| Language | Run Command |
| --- | --- |
| C++ | `docker compose --profile cpp up --build` |
| C# | `docker compose --profile csharp up --build` |
| Java | `docker compose --profile java up --build` |

### Prior Knowledge

- Basic understanding of key-value stores (similar to a dictionary or
  hash map)
- Familiarity with HTTP GET/PUT requests
- Basic experience with one of C++, C#, or Java

## Quick Start

```powershell
cd 11-caching
.\setup.ps1
```

Then follow the task instructions below.

---

## Task 1: Verify Prerequisites and Start the Environment

Before starting, confirm Docker is installed and start the lab environment.

### Step 1.1: Verify Docker

```powershell
docker --version
docker compose version
```

### Step 1.2: Start the environment

```powershell
.\setup.ps1
```

The script builds and starts two containers: Redis (cache) and the backend
(simulated database). It verifies both are healthy before continuing.

### Step 1.3: Verify Redis is running

```powershell
docker exec redis-cache redis-cli ping
```

Expected output:

```text
PONG
```

### Step 1.4: Verify the backend

```powershell
$start = Get-Date
$response = Invoke-RestMethod -Uri "http://localhost:5050/products/1"
$elapsed = (Get-Date) - $start
$response | ConvertTo-Json
Write-Host "Elapsed: $($elapsed.TotalMilliseconds)ms"
```

Expected output (note the ~500ms elapsed time):

```json
{
    "id": 1,
    "name": "Product 1",
    "price": 11.49,
    "category": "Books",
    "stock": 103
}
```

```text
Elapsed: 520ms
```

> **Question:** The backend takes ~500ms for every request. If your
> application serves 1,000 users per second and each user request hits
> the backend, how many backend instances would you need?
>
> **Hint:** At 500ms per request, one backend instance handles about 2
> requests per second (assuming serial processing). For 1,000 users per
> second, you would need ~500 instances. Caching can reduce this
> dramatically.

### Step 1.5: Open a Redis monitor (optional but recommended)

In a second PowerShell window, start monitoring Redis commands in real
time:

```powershell
docker exec -it redis-cache redis-cli MONITOR
```

Leave this running while you work through the tasks. You will see every
`GET`, `SET`, and other command your application sends to Redis.

---

## Task 2: Cache-Aside (Lazy Loading)

Cache-aside is the most common caching pattern. The application checks
the cache first. On a miss, it fetches from the backend, stores the
result in the cache, and returns it. On a hit, it returns directly from
the cache.

### Step 2.1: Review the source code

Open the source file for your chosen language and read through the
cache-aside exercise (Exercise 1):

| Language | File |
| --- | --- |
| C++ | `cpp\cache_lab.cpp` |
| C# | `csharp\CacheLab.cs` |
| Java | `java\src\main\java\com\lab\CacheLab.java` |

The code implements `get_product(id)` (or `GetProduct`/`getProduct`):

1. Check Redis for key `product:{id}`
2. On **miss**: GET from `http://backend:5000/products/{id}`, store in
   Redis, return
3. On **hit**: return the cached value directly

### Step 2.2: Run the cache-aside exercise

Start your chosen language container:

```powershell
# Pick ONE:
docker compose --profile cpp up --build
docker compose --profile csharp up --build
docker compose --profile java up --build
```

Watch the output. The program fetches product 1 twice:

```text
=== Exercise 1: Cache-Aside Pattern ===
First request (cache MISS):  512ms
Second request (cache HIT):    2ms
```

The first request takes ~500ms (cache miss, fetches from backend). The
second request takes under 5ms (cache hit, returns from Redis).

### Step 2.3: Inspect the cache

After the program runs, check what is stored in Redis:

```powershell
docker exec redis-cache redis-cli KEYS '*'
```

Expected output:

```text
1) "product:1"
```

View the cached value:

```powershell
docker exec redis-cache redis-cli GET product:1
```

> **Question:** What happens if the backend updates product 1's price
> after it is cached? How does the application know the cache is stale?
>
> **Hint:** It does not. Cache-aside has no built-in invalidation. The
> cache will serve the old value until the entry is explicitly deleted
> or expires. This is why TTL (Task 3) and write-through (Task 4) exist.
>
> **Question:** Cache-aside is also called "lazy loading." Why is "lazy"
> appropriate here?
>
> **Hint:** Data is only loaded into the cache when it is actually
> requested. The cache starts empty and fills up on demand, unlike
> eager loading which pre-populates the cache at startup.

---

## Task 3: Read-Through with TTL

Read-through wraps the cache-aside logic into a reusable helper. Adding
a TTL (Time-To-Live) ensures cached entries expire automatically,
preventing stale data from living in the cache indefinitely.

### Step 3.1: Understand the read-through pattern

The code refactors cache-aside into a generic function:

```text
read_through(key, ttl_seconds, fetch_function):
    value = redis.GET(key)
    if value exists:
        return value              # Cache hit
    value = fetch_function()      # Cache miss -- call the origin
    redis.SETEX(key, ttl, value)  # Store with TTL
    return value
```

This function works for any data source, not just products.

### Step 3.2: Run the read-through exercise

The program (Exercise 2) fetches product 2 using the read-through
helper with a 30-second TTL.

Watch the output:

```text
=== Exercise 2: Read-Through with TTL ===
Read-through (cache MISS): 508ms
TTL remaining: 30 seconds
```

### Step 3.3: Check the TTL

```powershell
docker exec redis-cache redis-cli TTL product:2
```

Expected output (seconds remaining, decreasing over time):

```text
(integer) 27
```

Run it again after a few seconds -- the number decreases:

```powershell
docker exec redis-cache redis-cli TTL product:2
```

```text
(integer) 22
```

### Step 3.4: Observe expiration

Wait 30 seconds, then check if the key still exists:

```powershell
Start-Sleep -Seconds 30
docker exec redis-cache redis-cli EXISTS product:2
```

Expected output:

```text
(integer) 0
```

The key is gone. The next request for product 2 will be a cache miss,
fetching fresh data from the backend.

> **Question:** How does TTL solve the stale data problem from Task 2?
> What is the trade-off between a short TTL (5s) and a long TTL (1h)?
>
> **Hint:** TTL guarantees data is at most N seconds stale. A short TTL
> means fresher data but more cache misses (more backend load). A long
> TTL means fewer misses but potentially serving outdated data. Most
> production systems use TTLs between 30 seconds and 5 minutes.
>
> **Question:** In a real system, who is responsible for the read-through
> logic -- the application or the cache? What are the implications?
>
> **Hint:** In cache-aside, the application manages the logic. In true
> read-through (e.g., AWS DAX for DynamoDB), the cache itself handles
> fetching from the origin. Application-managed gives more control;
> cache-managed is simpler for the application but requires the cache
> to understand how to reach the origin.

---

## Task 4: Write-Through

Write-through ensures the cache is always up-to-date by writing to both
the backend and the cache on every update. This eliminates stale reads
at the cost of higher write latency.

### Step 4.1: Understand the write-through pattern

```text
update_product(id, new_data):
    PUT http://backend:5000/products/{id}  # Write to origin
    redis.SET("product:{id}", new_data)    # Write to cache
    return success
```

Both writes must succeed. If the backend write fails, the cache is not
updated (maintaining consistency).

### Step 4.2: Run the write-through exercise

The program (Exercise 3) updates product 1's price to 99.99 using
write-through, then reads it back from the cache.

Watch the output:

```text
=== Exercise 3: Write-Through Pattern ===
Write-through update: 510ms
Read from cache after write: 1ms
Cached price: 99.99
```

### Step 4.3: Verify in Redis

```powershell
docker exec redis-cache redis-cli GET product:1
```

The cached value should show the updated price (99.99).

> **Question:** What is the downside of write-through?
>
> **Hint:** Every write takes at least as long as the backend write
> (~500ms) plus the Redis write (~1ms). If you write data that is
> rarely read, you are paying the cache write cost for no benefit.
> Write-through also causes "write amplification" -- writing to two
> places instead of one.
>
> **Question:** What happens if the backend write succeeds but the
> Redis write fails? How would you handle this in production?
>
> **Hint:** You would have inconsistency -- the backend has the new
> data but the cache has the old data. Production systems handle this
> with retry logic, distributed transactions, or by accepting temporary
> inconsistency and relying on TTL to eventually correct it.

---

## Task 5: Write-Back (Write-Behind)

Write-back writes to the cache immediately and flushes to the backend
asynchronously. This gives the fastest write performance but risks data
loss if the cache crashes before flushing.

### Step 5.1: Understand the write-back pattern

```text
update_product_async(id, new_data):
    redis.SET("product:{id}", new_data)   # Write to cache only
    redis.SADD("dirty_keys", "product:{id}")  # Track for later flush
    return success                        # Instant response

flush_dirty():
    for each key in redis.SMEMBERS("dirty_keys"):
        data = redis.GET(key)
        PUT http://backend:5000/products/{id}  # Flush to origin
        redis.SREM("dirty_keys", key)          # Remove from dirty set
```

### Step 5.2: Run the write-back exercise

The program (Exercise 4) updates products 3, 4, and 5 using write-back,
then flushes all dirty entries to the backend.

Watch the output:

```text
=== Exercise 4: Write-Back Pattern ===
Async write product 3: 1ms
Async write product 4: 1ms
Async write product 5: 1ms
Flushing 3 dirty keys to backend...
Flush complete: 1520ms
```

Notice the individual writes are under 5ms (Redis only). The flush takes
~1.5 seconds (3 backend writes at ~500ms each).

### Step 5.3: Check the dirty set

During the async phase (before flush), the dirty set contains the
pending keys:

```powershell
docker exec redis-cache redis-cli SMEMBERS dirty_keys
```

After flush, it should be empty:

```powershell
docker exec redis-cache redis-cli SCARD dirty_keys
```

Expected output:

```text
(integer) 0
```

> **Question:** When is write-back appropriate despite the risk of data
> loss?
>
> **Hint:** Write-back is ideal for high-frequency counters (page views,
> likes), analytics events, session data, and any data that can be
> regenerated. The key question is: "If the last N seconds of writes
> are lost, does it matter?" For page view counts, no. For bank
> transfers, absolutely yes.
>
> **Question:** How do production systems like MySQL InnoDB or the Linux
> page cache mitigate the data loss risk of write-back?
>
> **Hint:** They use a write-ahead log (WAL). Before modifying data in
> memory, they write the change to a persistent log on disk. On crash
> recovery, the log is replayed to restore lost writes. Redis has a
> similar feature called the AOF (Append Only File).

---

## Task 6: Eviction Policies

When Redis reaches its memory limit, it must decide which keys to remove.
The eviction policy determines which keys are evicted. In this task, you
configure Redis with a small memory limit and observe different eviction
behaviors.

### Step 6.1: Set a small memory limit with LRU eviction

```powershell
docker exec redis-cache redis-cli CONFIG SET maxmemory 1mb
docker exec redis-cache redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

### Step 6.2: Run the eviction exercise

The program (Exercise 5) inserts 200 products into the cache -- more
than fits in 1MB. Redis evicts the least recently used keys to make room.

Watch the output:

```text
=== Exercise 5: Eviction Policies ===
Inserting 200 products into cache (maxmemory: 1MB, policy: allkeys-lru)...
Evicted keys: 147
Keys remaining in cache: 53
```

### Step 6.3: Check eviction statistics

```powershell
docker exec redis-cache redis-cli INFO stats | Select-String "evicted_keys"
```

Expected output:

```text
evicted_keys:147
```

### Step 6.4: Observe LRU behavior

Access product 1 several times to make it "recently used":

```powershell
docker exec redis-cache redis-cli GET product:1
docker exec redis-cache redis-cli GET product:1
docker exec redis-cache redis-cli GET product:1
```

Check how long product 1 has been idle:

```powershell
docker exec redis-cache redis-cli OBJECT IDLETIME product:1
```

Expected output (seconds since last access):

```text
(integer) 0
```

Recently accessed keys have low idle time and survive LRU eviction.

### Step 6.5: Switch to LFU

```powershell
docker exec redis-cache redis-cli CONFIG SET maxmemory-policy allkeys-lfu
docker exec redis-cache redis-cli FLUSHALL
```

Access product 1 many times (high frequency):

```powershell
1..20 | ForEach-Object {
    docker exec redis-cache redis-cli SET product:1 "frequently-accessed"
    docker exec redis-cache redis-cli GET product:1
}
```

Check the frequency counter:

```powershell
docker exec redis-cache redis-cli OBJECT FREQ product:1
```

The frequency counter is higher for keys accessed more often. Under LFU
eviction, keys with low frequency are evicted first.

### Step 6.6: Switch to volatile-ttl

```powershell
docker exec redis-cache redis-cli CONFIG SET maxmemory-policy volatile-ttl
docker exec redis-cache redis-cli FLUSHALL
```

Set keys with different TTLs:

```powershell
docker exec redis-cache redis-cli SETEX short-lived 10 "expires soon"
docker exec redis-cache redis-cli SETEX long-lived 3600 "expires later"
docker exec redis-cache redis-cli SET no-ttl "never expires"
```

Under `volatile-ttl`, keys with the shortest remaining TTL are evicted
first. Keys without a TTL (`no-ttl`) are never evicted by this policy.

### Step 6.7: Reset Redis configuration

```powershell
docker exec redis-cache redis-cli CONFIG SET maxmemory 10mb
docker exec redis-cache redis-cli CONFIG SET maxmemory-policy noeviction
docker exec redis-cache redis-cli FLUSHALL
```

> **Question:** A social media feed caches the latest 100 posts per
> user. Should it use LRU or LFU? Why?
>
> **Hint:** LRU is better here. Social media feeds are time-sensitive --
> users want recent posts, not posts that were popular last week. LRU
> evicts posts that have not been viewed recently, which aligns with the
> feed's chronological nature.
>
> **Question:** An e-commerce site caches product pages. During a flash
> sale, one product gets millions of views. After the sale ends, should
> that product stay cached? Which policy handles this better?
>
> **Hint:** After the sale ends, that product is no longer popular. LFU
> would keep it cached because it has a high historical frequency count.
> LRU would eventually evict it once newer products are accessed. For
> this workload, LRU is better because it adapts to changing access
> patterns. Redis LFU does decay frequency over time, but LRU reacts
> faster.

---

## Task 7: Performance Comparison and Cleanup

### Step 7.1: Review benchmark results

The program (Exercise 6) runs a benchmark comparing cache miss and hit
performance:

```text
=== Exercise 6: Benchmark ===
100 cache misses: avg 505ms per request
100 cache hits:   avg 1ms per request
Speedup: 505x
```

### Step 7.2: Fill in the comparison table

Based on what you observed in Tasks 2-6, complete this table:

| Pattern | Read Latency (Hit) | Read Latency (Miss) | Write Latency | Consistency | Data Loss Risk |
| --- | --- | --- | --- | --- | --- |
| Cache-Aside | ~1ms | ~500ms | N/A | Eventual (stale until evicted) | None |
| Read-Through | ~1ms | ~500ms | N/A | Bounded (stale until TTL expires) | None |
| Write-Through | ~1ms | ~500ms | ~500ms | Strong (cache always current) | None |
| Write-Back | ~1ms | ~500ms | ~1ms | Eventual (dirty keys pending) | Yes (unflushed writes) |

### Step 7.3: Reflection questions

> **Question:** Netflix uses cache-aside with TTL for its video catalog.
> Why not write-through?
>
> **Hint:** Netflix's catalog has millions of titles but a relatively
> low write rate (new titles added daily, not per second). Write-through
> would add unnecessary latency to every catalog update and cache data
> that may never be read. Cache-aside with TTL is simpler and sufficient
> because catalog data does not need to be real-time fresh.
>
> **Question:** A banking application processes transfers. Which caching
> pattern should it use for account balances, and why?
>
> **Hint:** Write-through or no cache at all. Account balances require
> strong consistency -- showing a stale balance could allow double
> spending. Write-back is too risky (lost writes mean lost money).
> Cache-aside with TTL might show a stale balance for up to N seconds.
> Many banking systems skip caching for balances entirely and optimize
> the database instead.

### Step 7.4: Cleanup

```powershell
.\cleanup.ps1
```

This stops all containers, removes volumes, and deletes locally built
Docker images.

Verify nothing is left running:

```powershell
docker ps -a | Select-String "redis-cache|backend-db|cache-lab"
```

Expected output: no matching containers.
