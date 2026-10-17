# Lab 12: Proxies

> For the lab overview, architecture diagram, and key concepts, see
> [README.md](README.md).

## Environment

This lab runs **locally** on Docker Desktop. Every component is a container, so the commands are the same on
macOS, Linux, and Windows (Git Bash or WSL).

| Component | Container | Role |
| --- | --- | --- |
| nginx 1.30.6 | `lab12-proxy` | Reverse proxy: TLS, routing, cache, API keys, rate limits |
| Python service | `lab12-users`, `lab12-orders` | The two services behind the reverse proxy |
| netshoot | `lab12-sniffer` | Packet capture inside the reverse proxy's network namespace |
| Squid 6.13 | `lab12-forward-proxy` | Forward proxy: the only way out of the corporate network |
| nginx 1.30.6 | `lab12-public-site` | Two "internet" websites: `news.example.test` and `games.example.test` |
| netshoot | `lab12-workstation` | An employee laptop on the corporate network |

Host ports used: `8088` (HTTP), `8443` (HTTPS) and `18128` (Squid), all published on `127.0.0.1` only. IP
addresses in the expected outputs come from Docker and will differ on your machine; compare which component
appears, not the exact number.

### Prerequisites

- **Docker Desktop** installed and running
- **curl** and **openssl** on your machine (both ship with macOS, Linux, and Git for Windows)
- A bash terminal (macOS Terminal, Linux shell, Git Bash, or WSL)
- Lab 03 (load balancing) and Lab 06 (HTTPS) are useful background

> **Git Bash on Windows:** Git Bash rewrites any argument that starts with `/` into a Windows path, which breaks
> commands such as `docker exec lab12-workstation curl --cacert /certs/proxy.crt ...`. Run
> `export MSYS_NO_PATHCONV=1` once in each new terminal before you start. `setup.sh` already does it for its own
> commands.

### Quick Start

```bash
cd 12-proxies
chmod +x setup.sh cleanup.sh scripts/*.sh
```

Then continue with **Task 1** below, which runs `./setup.sh`.

---

## Task 1: Start the Environment and Meet the Proxy

A reverse proxy acts on behalf of servers: clients talk to the proxy and never to the services behind it. In this
task you confirm that the only door into the services is the proxy, and that the proxy hides what runs behind it.

### Step 1.1: Run the setup script

```bash
./setup.sh
```

The script generates two self-signed TLS certificates in `certs/` (ignored by git), builds the service image,
starts seven containers, waits for their health checks, and runs one request through each proxy.

Expected output (abbreviated):

```text
=== Lab 12: Proxies (nginx reverse proxy + Squid forward proxy) ===

Generating self-signed TLS certificates in certs/...
  Created proxy.crt (CN=localhost)
  Created public-site.crt (CN=news.example.test)
...
Waiting for containers to be healthy...
  All containers healthy

Smoke test through the reverse proxy...
  https://localhost:8443/users/ -> 200 OK
Smoke test through the forward proxy...
  workstation -> Squid -> http://news.example.test/ -> 200 OK

=== Environment ready ===
```

### Step 1.2: See which containers publish ports

```bash
docker compose ps --format 'table {{.Name}}\t{{.Status}}\t{{.Ports}}'
```

Expected output:

```text
NAME                  STATUS                    PORTS
lab12-forward-proxy   Up 17 seconds (healthy)   127.0.0.1:18128->3128/tcp
lab12-orders          Up 17 seconds (healthy)   5000/tcp
lab12-proxy           Up 11 seconds (healthy)   127.0.0.1:8088->8088/tcp, 127.0.0.1:8443->8443/tcp
lab12-public-site     Up 17 seconds (healthy)   80/tcp
lab12-sniffer         Up 6 seconds
lab12-users           Up 17 seconds (healthy)   5000/tcp
lab12-workstation     Up 17 seconds
```

Only the two proxies map a port to your machine, and only on `127.0.0.1`, so other computers on your network
cannot use them. The services listen on `5000/tcp` inside Docker, but nothing outside can reach that port.

### Step 1.3: Confirm that the services are isolated

The services live on `lab12-backend`, a Docker network created with `internal: true`:

```bash
docker network inspect lab12-backend -f '{{.Name}} internal={{.Internal}}'
docker exec lab12-workstation curl -sS -m 3 http://users-service:5000/
```

Expected output:

```text
lab12-backend internal=true
curl: (6) Could not resolve host: users-service (DNS server returned general failure)
```

A container on another network cannot even resolve the service name. The proxy is the single entry point.

### Step 1.4: Make a request through the proxy

```bash
curl -si --cacert certs/proxy.crt https://localhost:8443/users/
```

Expected output:

```text
HTTP/2 200
server: nginx
date: Sat, 17 Oct 2026 05:44:29 GMT
content-type: application/json
content-length: 247

{
  "service": "users-service",
  "instance": "2fe377360fcb",
  "path_seen": "/",
  "client_ip_seen": "172.19.0.4",
  "host_header": "localhost",
  "x_forwarded_for": "172.18.0.1",
  "x_forwarded_proto": "https",
  "x_real_ip": "172.18.0.1"
}
```

The service reports what it saw. Keep this output in mind: `client_ip_seen` is the proxy, not you. Task 6
explains the `x_forwarded_*` fields. Because the proxy port is published on `127.0.0.1`, Docker delivers your
requests from the gateway of `lab12-internet` (`172.18.0.1` here): that address stands for your machine.

### Step 1.5: Compare with what the service sends when nobody is in between

From inside the proxy container, call the service directly and print only the response headers:

```bash
docker exec lab12-proxy wget -S -q -O /dev/null http://users-service:5000/
```

Expected output:

```text
  HTTP/1.0 200 OK
  Server: PythonBackend/1.0 Python/3.15.0
  Date: Sat, 17 Oct 2026 05:44:29 GMT
  Content-Type: application/json
  Content-Length: 230
  X-Powered-By: python/users-service
```

Through the proxy the client saw `server: nginx` and no `X-Powered-By`. nginx replaces the upstream `Server`
header by default, `server_tokens off` hides the nginx version, and `proxy_hide_header X-Powered-By` removes the
header that names the technology. The proxy also changed the protocol: the client spoke HTTP/2 to nginx, nginx
speaks HTTP/1.1 to the service, and the Python service answers with HTTP/1.0.

> **Question:** Why does hiding `Server: PythonBackend/1.0 Python/3.15.0` from clients make the system safer,
> even though it does not fix any vulnerability?
>
> **Hint:** Think about what an attacker does first when probing a site, and how much a version number narrows
> the list of known exploits to try.

---

## Task 2: One Entry Point, Many Services (Path Routing)

The reverse proxy decides which service answers by looking at the URL path. This is the routing feature of an
API gateway, and it is different from load balancing (Lab 03): here every path goes to a **different service**,
not to another copy of the same one.

### Step 2.1: Read the routing rules

```bash
grep -nE 'location|proxy_pass' nginx/reverse-proxy.conf
```

Expected output:

```text
57:    location = /healthz {
62:    location / {
82:    # These are inherited by every location below that does not set its own.
94:    location /users/ {
95:        proxy_pass http://users_service/;
99:    location = /users/report {
100:        proxy_pass http://users_service/report;
108:    location /orders/ {
113:        proxy_pass http://orders_service/;
119:    location /legacy/users/ {
124:        proxy_pass http://users_service/;
129:    location @rate_limited {
134:    location / {
```

Lines 57 and 62 belong to the plain HTTP listener, which only redirects. From line 94 on, each `location` matches
a path prefix and `proxy_pass` names the upstream that answers it. Paths that match nothing fall into the last
`location /`.

### Step 2.2: Send requests to each route

```bash
for path in /users/ /users/profile/42 /payments/; do
    printf '%-20s ' "$path"
    curl -s --cacert certs/proxy.crt -o /dev/null -w '%{http_code}\n' "https://localhost:8443$path"
done
curl -s --cacert certs/proxy.crt https://localhost:8443/users/profile/42 | grep -E '"service"|"path_seen"'
curl -s --cacert certs/proxy.crt https://localhost:8443/payments/
```

Expected output:

```text
/users/              200
/users/profile/42    200
/payments/           404
  "service": "users-service",
  "path_seen": "/profile/42",
{"error": "no route for this path"}
```

Look at `path_seen`: the client asked for `/users/profile/42`, the service received `/profile/42`. The trailing
slash in `proxy_pass http://users_service/;` tells nginx to replace the matched prefix `/users/` with `/`. The
service does not need to know under which prefix the proxy publishes it. The `404` came from the proxy itself:
no service was contacted.

### Step 2.3: Reach the second service

The orders route answers only to clients with an API key (you will study why in Task 5):

```bash
curl -s --cacert certs/proxy.crt https://localhost:8443/orders/
API_KEY=team-alpha
curl -s --cacert certs/proxy.crt -H "X-API-Key: $API_KEY" https://localhost:8443/orders/ | grep -E 'service|instance'
```

Expected output:

```text
{"error": "missing or invalid X-API-Key"}
  "service": "orders-service",
  "instance": "70be5d2c4a07",
```

### Step 2.4: Check which upstream served each request

```bash
docker logs lab12-proxy 2>/dev/null | tail -4
docker logs lab12-orders 2>&1
```

Expected output:

```text
172.18.0.1 "GET /users/profile/42 HTTP/2.0" status=200 cache=- client_key= upstream=172.19.0.3:5000 ...
172.18.0.1 "GET /payments/ HTTP/2.0" status=404 cache=- client_key= upstream=- rt=0.000 xff="-"
172.18.0.1 "GET /orders/ HTTP/2.0" status=401 cache=- client_key= upstream=- rt=0.000 xff="-"
172.18.0.1 "GET /orders/ HTTP/2.0" status=200 cache=- client_key=alpha upstream=172.19.0.2:5000 ...
orders-service listening on port 5000
orders-service GET / client=172.19.0.4 xff=172.18.0.1 proto=https host=localhost
```

Two different upstream addresses, one per service. The orders service logged one request, not two: the `401`
was answered by the proxy (`upstream=-`) and never reached the service.

> **Question:** The mobile team wants to move the orders service to a new cluster with a new hostname. What has
> to change in the mobile app, and what has to change in the proxy?
>
> **Hint:** Clients only know `https://localhost:8443/orders/`. Find where `orders-service` is written down.
>
> **Question:** Lab 03 also put HAProxy in front of several servers. What is the difference between what HAProxy
> decided there and what nginx decides here?
>
> **Hint:** In Lab 03 all five servers could answer any request. Can `users-service` answer `/orders/`?

---

## Task 3: TLS Termination at the Proxy

The proxy holds the certificate and the private key. Clients speak HTTPS to the proxy; the proxy speaks plain HTTP
to the services on the private network. In this task you prove it by capturing the packets on both sides.

### Step 3.1: HTTP is redirected to HTTPS

```bash
curl -s -o /dev/null -w '%{http_code} -> %{redirect_url}\n' http://localhost:8088/users/
```

Expected output:

```text
301 -> https://localhost:8443/users/
```

### Step 3.2: Inspect the certificate the proxy presents

```bash
echo | openssl s_client -connect localhost:8443 -servername localhost 2>/dev/null \
    | grep -E '^subject|^issuer|Protocol  :|Cipher    :'
openssl x509 -in certs/proxy.crt -noout -dates
openssl x509 -in certs/proxy.crt -noout -text | grep -A1 'Subject Alternative Name'
```

Expected output on macOS (LibreSSL). With OpenSSL 3 on Linux or WSL the cipher, the `subject=` format, and the
wording of curl errors (for example `self-signed certificate`) differ slightly:

```text
subject=/O=Lab 12 Proxies/CN=localhost
issuer=/O=Lab 12 Proxies/CN=localhost
    Protocol  : TLSv1.3
    Cipher    : AEAD-CHACHA20-POLY1305-SHA256
notBefore=Oct 17 05:44:14 2026 GMT
notAfter=Nov 16 05:44:14 2026 GMT
            X509v3 Subject Alternative Name:
                DNS:localhost, DNS:shop.example.test, IP Address:127.0.0.1
```

`subject` and `issuer` are the same: the certificate is self-signed. `setup.sh` generated it with `openssl req
-x509` and valid for 30 days.

### Step 3.3: Trust, or do not trust, the certificate

```bash
curl -sS https://localhost:8443/users/ > /dev/null
curl -sS --cacert certs/proxy.crt https://localhost:8443/users/ > /dev/null && echo "verified"
```

Expected output:

```text
curl: (60) SSL certificate problem: self signed certificate
More details here: https://curl.se/docs/sslcerts.html
...
verified
```

curl refuses a certificate it cannot trace to a trusted authority. `--cacert` tells curl to trust this one
certificate, which is safer than `-k` (skip verification) because a different certificate would still be rejected.

### Step 3.4: Capture the client side of the proxy

The `lab12-sniffer` container shares the network namespace of `lab12-proxy`, so it sees every packet the proxy
sends and receives. Open a **second terminal** and start a capture of the client-facing port:

```bash
docker exec lab12-sniffer timeout 15 tshark -i any -f 'tcp port 8443' -Y tls
```

Back in the **first terminal**, send a request with a recognizable value in a header:

```bash
curl -s -o /dev/null --cacert certs/proxy.crt \
    -H 'X-Lab-Marker: confidential-order-4111' https://localhost:8443/users/
```

Expected output in the second terminal:

```text
    4 0.000328250   172.18.0.1 → 172.18.0.4   TLSv1 387 Client Hello (SNI=localhost)
    6 0.001574625   172.18.0.4 → 172.18.0.1   TLSv1.3 1429 Server Hello, Change Cipher Spec, Application Data, ...
    8 0.003542500   172.18.0.1 → 172.18.0.4   TLSv1.3 132 Change Cipher Spec, Application Data
    9 0.003543542   172.18.0.1 → 172.18.0.4   TLSv1.3 154 Application Data
   10 0.003853417   172.18.0.1 → 172.18.0.4   TLSv1.3 163 Application Data
...
```

All a network observer learns is the server name in the `Client Hello` (SNI) and the size of each record. The
path, the headers, and the marker travel as encrypted `Application Data`.

### Step 3.5: Capture the service side of the proxy

Repeat the capture on port 5000, the hop from the proxy to `users-service`, and print the method, the path, and
the request headers:

```bash
docker exec lab12-sniffer timeout 15 tshark -i any -f 'tcp port 5000' -Y http -T fields \
    -e ip.src -e ip.dst -e http.request.method -e http.request.uri -e http.request.line -e http.response.code
```

Send the same `curl` from the first terminal. Expected output:

```text
172.19.0.4  172.19.0.3  GET  /  Host: localhost\r\n,X-Real-IP: 172.18.0.1\r\n,X-Forwarded-For: 172.18.0.1\r\n,
X-Forwarded-Proto: https\r\n,user-agent: curl/8.7.1\r\n,accept: */*\r\n,x-lab-marker: confidential-order-4111\r\n
172.19.0.3  172.19.0.4        /       200
```

(The first line is wrapped here for readability.) Every header is in clear text, including the marker and the
three headers that the proxy added.

### Step 3.6: Run both captures at once

The helper script captures both hops during a single request and counts where the marker is visible:

```bash
./scripts/capture-tls.sh
```

Expected output:

```text
Marker sent in a request header: X-Lab-Marker: confidential-order-4111

Hop                                 Packets   Marker found
client -> proxy  (port 8443, TLS)        22              0
proxy -> service (port 5000, HTTP)       12              1

Plain-text lines on the service hop that carry the marker:
  GET / HTTP/1.1
  x-lab-marker: confidential-order-4111
```

> **Question:** What do you gain by terminating TLS at the proxy instead of in each service? What do you give up?
>
> **Hint:** Count how many places hold a private key and need certificate renewals. Then think about who can
> read the traffic on the private network.
>
> **Question:** A bank's security policy says "data must be encrypted in transit everywhere". How would you change
> this design to comply, and what would it cost?
>
> **Hint:** Search for "TLS re-encryption" or "end-to-end TLS" and `proxy_ssl_*` directives in nginx.
>
> **Question:** The Client Hello carried `SNI=localhost` in clear text. Why does the proxy need the name before
> the encryption starts?
>
> **Hint:** One proxy can hold certificates for many domains. It has to choose one before it can answer.

---

## Task 4: Caching at the Proxy (Cold vs Warm)

`/users/report` simulates an expensive query: the service sleeps 1.5 seconds before answering. The proxy caches
that one route for 20 seconds, so repeated requests never reach the service while the copy is fresh.

### Step 4.1: Read the cache configuration

```bash
grep -nE 'proxy_cache|X-Cache-Status' nginx/reverse-proxy.conf
```

Expected output:

```text
30:proxy_cache_path /var/cache/nginx/lab12 levels=1:2 keys_zone=lab12_cache:10m
101:        proxy_cache lab12_cache;
102:        proxy_cache_valid 200 20s;
103:        proxy_cache_lock on;
104:        add_header X-Cache-Status $upstream_cache_status always;
```

### Step 4.2: Measure a cold request and the warm ones that follow

```bash
./scripts/measure-cache.sh 5
```

Expected output:

```text
#    X-Cache-Status  time (ms)   generated_at (by the service)
1    MISS               1510.0   05:44:50.926
2    HIT                   5.7   05:44:50.926
3    HIT                  5.4   05:44:50.926
4    HIT                   4.8   05:44:50.926
5    HIT                   4.6   05:44:50.926
```

The first request found the cache cold (`MISS`) and paid the full 1.5 seconds. The next four were served from
the proxy's disk in about 5 milliseconds, roughly 300 times faster. All five carry the same `generated_at`: they
are the same response.

### Step 4.3: Count how many requests reached the service

```bash
docker logs lab12-users 2>&1 | grep -c '/report'
```

Expected output:

```text
1
```

Five client requests, one service request. The other four never left the proxy.

### Step 4.4: Watch the copy expire

Wait for the 20-second lifetime to pass, then measure again:

```bash
sleep 21
./scripts/measure-cache.sh 2
```

Expected output:

```text
#    X-Cache-Status  time (ms)   generated_at (by the service)
1    EXPIRED            1509.3   05:45:13.774
2    HIT                   5.4   05:45:13.774
```

`EXPIRED` means the proxy had a copy, but it was too old, so it fetched a fresh one and cached it again.

### Step 4.5: Look at a cached entry on disk

```bash
docker exec lab12-proxy sh -c 'f=$(find /var/cache/nginx/lab12 -type f | head -1); echo "$f"; strings "$f" | head -4'
```

Expected output:

```text
/var/cache/nginx/lab12/2/2c/5844f04ca2950cc6380358f949d632c2
KEY: http://users_service/report
HTTP/1.0 200 OK
Server: PythonBackend/1.0 Python/3.15.0
```

The file name is the MD5 hash of the cache key, and `levels=1:2` spreads files across subdirectories made from
its last characters. The proxy stores the whole upstream response, headers included.

> **Question:** Lab 11 cached data in Redis from inside the application. What is different when the cache lives
> in the proxy? Name one thing that is easier and one that is harder.
>
> **Hint:** Think about which code has to change to add the cache, and about what the proxy knows (only the URL
> and headers) compared with what the application knows (the meaning of the data).
>
> **Question:** `proxy_cache_lock on` is set. What would happen without it if 500 clients asked for the report in
> the same second right after it expired?
>
> **Hint:** Search for "cache stampede" or "thundering herd".
>
> **Question:** If `/users/report` returned data that is different for each logged-in user, why would this
> configuration be dangerous?
>
> **Hint:** Look at the `KEY:` line. Does it contain anything that identifies the user?

---

## Task 5: Gateway Policies: API Keys and Rate Limiting

An API gateway enforces policies before a request reaches a service. The orders route requires an `X-API-Key`
header and gives each client its own bucket of **2 requests per second** with a **burst of 3**. Requests over
the limit get `429 Too Many Requests` from the proxy.

### Step 5.1: Read the policy

```bash
sed -n '/map \$http_x_api_key/,/limit_req_log_level/p' nginx/reverse-proxy.conf
```

Expected output:

```text
map $http_x_api_key $api_client {
    default        "";
    "team-alpha"   alpha;
    "team-beta"    beta;
}

# One bucket per client name, refilled at 2 requests per second.
# Requests with an empty key are not counted here (they get a 401 anyway).
limit_req_zone $api_client zone=per_client:10m rate=2r/s;
limit_req_status 429;
limit_req_log_level warn;
```

`map` turns the key into a client name. `limit_req_zone` keeps one counter per client name. These two keys are
demo values written in the configuration; a real gateway would look keys up in a store and never commit them.

### Step 5.2: Missing or wrong keys are rejected

```bash
curl -s --cacert certs/proxy.crt -o /dev/null -w '%{http_code}\n' https://localhost:8443/orders/
curl -s --cacert certs/proxy.crt -o /dev/null -w '%{http_code}\n' -H 'X-API-Key: wrong' https://localhost:8443/orders/
```

Expected output:

```text
401
401
```

### Step 5.3: Exceed the rate limit

Send 12 requests as fast as curl can, with the `team-alpha` key:

```bash
./scripts/burst.sh team-alpha 12
```

Example output:

```text
Key: team-alpha   Requests: 12
Sequence: 200 200 200 200 429 429 429 429 429 429 429 429
  HTTP 200: 4
  HTTP 429: 8
```

In this run, one request at the base rate plus a burst of 3 got through. The bucket then ran dry, and the remaining
8 were rejected in the proxy. Your split may differ: the script sends one request after the other, so on a slower
machine the bucket refills a little during the loop and one or two more get a `200`. Check that the sequence starts
with `200` and ends with `429`.

### Step 5.4: Another client has its own bucket

Immediately after, send the same burst with the other key:

```bash
./scripts/burst.sh team-beta 12
```

Example output:

```text
Key: team-beta   Requests: 12
Sequence: 200 200 200 200 429 429 429 429 429 429 429 429
  HTTP 200: 4
  HTTP 429: 8
```

`team-alpha` had just used up its bucket, yet `team-beta` got as many `200`s as `team-alpha` did on its first
burst. A noisy client cannot starve the others.

### Step 5.5: Read the 429 response and the proxy log

```bash
API_KEY=team-alpha
for i in 1 2 3 4 5; do
    curl -s -o /dev/null --cacert certs/proxy.crt -H "X-API-Key: $API_KEY" https://localhost:8443/orders/
done
curl -si --cacert certs/proxy.crt -H "X-API-Key: $API_KEY" https://localhost:8443/orders/
docker logs lab12-proxy 2>&1 | grep -m1 'limiting requests'
```

Expected output:

```text
HTTP/2 429
server: nginx
date: Sat, 17 Oct 2026 05:45:16 GMT
content-type: application/json
content-length: 44
retry-after: 1

{"error": "rate limit exceeded, slow down"}
2026/10/17 05:45:16 [warn] 21#21: *56 limiting requests, excess: 3.856 by zone "per_client", client: ...
```

`Retry-After` tells well-behaved clients how long to wait. The `excess` value is how far over the limit the
bucket was when the request arrived.

> **Question:** nginx implements the *leaky bucket* algorithm. The class covered token bucket, fixed window, and
> sliding window. Which one behaves most like what you observed, and what does `burst=3` correspond to?
>
> **Hint:** Wait one second between two bursts and run `./scripts/burst.sh team-alpha 6`. How many `200`s do
> you get back, and why?
>
> **Question:** Why is it better to reject the excess at the proxy than to let each service count its own
> requests?
>
> **Hint:** Imagine dozens of services, each written by a different team, each with its own limiter to build
> and configure. Also count the work a service does for a request that it will reject anyway.
>
> **Question:** This lab limits by API key. What would go wrong if it limited by client IP address instead?
>
> **Hint:** Keep this question in mind until Task 8.

---

## Task 6: X-Forwarded-For and X-Forwarded-Proto

Once a proxy is in the middle, the TCP connection that reaches the service comes from the proxy. The service no
longer knows the real client address or whether the client used HTTPS, unless the proxy tells it in headers. This
task compares a naive proxy rule with a correct one, side by side, in the service log.

### Step 6.1: Compare the two rules

```bash
sed -n '/Headers every proxied request/,/X-Forwarded-Proto/p;/location \/legacy\/users/,/}/p' nginx/reverse-proxy.conf
```

Expected output:

```text
    # Headers every proxied request carries to the service (Task 6).
    # These are inherited by every location below that does not set its own.
    proxy_set_header Host              $host;
    proxy_set_header X-Real-IP         $remote_addr;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    location /legacy/users/ {
        proxy_set_header Connection "";
        proxy_set_header X-Real-IP "";
        proxy_set_header X-Forwarded-For "";
        proxy_set_header X-Forwarded-Proto "";
        proxy_pass http://users_service/;
    }
```

The four headers are set at the `server` level. The `/legacy/users/` location sets headers of its own, and in nginx
that cancels the inherited ones. Its empty values also drop any forwarding headers the client sent itself: it behaves
like a proxy that forwards nothing about the client.

### Step 6.2: Before: a request through the naive rule

```bash
curl -s --cacert certs/proxy.crt https://localhost:8443/legacy/users/ | grep -E 'client_ip|host_header|x_'
```

Expected output:

```text
  "client_ip_seen": "172.19.0.4",
  "host_header": "users_service",
  "x_forwarded_for": "-",
  "x_forwarded_proto": "-",
  "x_real_ip": "-"
```

### Step 6.3: After: the same request through the correct rule

```bash
curl -s --cacert certs/proxy.crt https://localhost:8443/users/ | grep -E 'client_ip|host_header|x_'
```

Expected output:

```text
  "client_ip_seen": "172.19.0.4",
  "host_header": "localhost",
  "x_forwarded_for": "172.18.0.1",
  "x_forwarded_proto": "https",
  "x_real_ip": "172.18.0.1"
```

### Step 6.4: Compare both in the service log

```bash
docker logs lab12-users 2>&1 | tail -2
```

Expected output:

```text
users-service GET / client=172.19.0.4 xff=- proto=- host=users_service
users-service GET / client=172.19.0.4 xff=172.18.0.1 proto=https host=localhost
```

`client=` is the same in both lines: it is always the proxy (`docker inspect lab12-proxy` shows `172.19.0.4` on
`lab12-backend`). Only the headers carry the truth. Without them, the service logs the wrong client, cannot rate
limit or geolocate by client, and builds `http://` links for a user who is on `https://`.

### Step 6.5: Try to lie to the proxy

Send your own `X-Forwarded-For` and `X-Real-IP` headers, as an attacker could:

```bash
curl -s --cacert certs/proxy.crt -H 'X-Forwarded-For: 203.0.113.7' -H 'X-Real-IP: 203.0.113.7' \
    https://localhost:8443/users/ | grep -E 'x_forwarded_for|x_real_ip'
```

Expected output:

```text
  "x_forwarded_for": "203.0.113.7, 172.18.0.1",
  "x_real_ip": "172.18.0.1"
```

`$proxy_add_x_forwarded_for` **appends** the address the proxy saw to whatever the client sent, so the forged
value survives at the left of the list. `X-Real-IP` was **overwritten** with `$remote_addr`, which the client
cannot fake.

> **Question:** A service reads the first address in `X-Forwarded-For` to decide whether a request comes from the
> office network. Why is that a security hole, and which address should it read instead?
>
> **Hint:** Read the list from the right. Which entries were written by proxies you control?
>
> **Question:** Why does the service need `X-Forwarded-Proto` to build correct redirects and cookies?
>
> **Hint:** The service received plain HTTP from the proxy. What scheme would it put in a `Location:` header,
> and what happens to a cookie marked `Secure`?

---

## Task 7: The Forward Proxy: How Companies Control Outbound Traffic

Now switch sides. A forward proxy acts on behalf of **clients**. `lab12-workstation` sits on `lab12-corp`, an
internal network with no route out. Squid sits on that network and on `lab12-internet`, so it is the only way to
reach the outside world, and the company decides what goes through.

### Step 7.1: Without the proxy, the internet does not exist

```bash
docker exec -it lab12-workstation bash
```

Inside the workstation:

```bash
curl -sS -m 5 http://news.example.test/
```

Expected output:

```text
curl: (6) Could not resolve host: news.example.test (DNS server returned general failure)
```

### Step 7.2: Through the proxy, it does

```bash
curl -sS -x http://forward-proxy:3128 http://news.example.test/
```

Expected output:

```text
news.example.test: today's headlines (served to 172.18.0.3)
```

The workstation never resolved the name: it handed the full URL to Squid, and Squid resolved it and connected.
The site says it served `172.18.0.3`, which is Squid's address on `lab12-internet`, not the workstation.

### Step 7.3: Company policy: a blocked category

```bash
curl -sS -o /dev/null -w '%{http_code}\n' -x http://forward-proxy:3128 http://games.example.test/
curl -sS -i -x http://forward-proxy:3128 http://games.example.test/ | grep -iE '^HTTP|x-squid-error'
```

Expected output:

```text
403
HTTP/1.1 403 Forbidden
X-Squid-Error: ERR_ACCESS_DENIED 0
```

The rule is `acl blocked_sites dstdomain .games.example.test` plus `http_access deny blocked_sites` in
`squid/squid.conf`. The site never saw the request. The same file also denies every destination outside
`.example.test` (`http_access deny !lab_sites`), so this proxy cannot be used to reach the real internet.

### Step 7.4: A shared cache for the whole office

`news.example.test` sends `Expires` and `Cache-Control: max-age=60`, so Squid may keep a copy:

```bash
for i in 1 2 3; do curl -sS -o /dev/null -x http://forward-proxy:3128 http://news.example.test/headlines; done
exit
```

Back on your machine, read the Squid log:

```bash
docker logs lab12-forward-proxy 2>&1 | grep 'client=' | tail -4
```

Expected output:

```text
05:45:20 client=172.20.0.3 TCP_DENIED/403 GET http://games.example.test/ server=-
05:45:20 client=172.20.0.3 TCP_MISS/200 GET http://news.example.test/headlines server=172.18.0.2
05:45:20 client=172.20.0.3 TCP_MEM_HIT/200 GET http://news.example.test/headlines server=-
05:45:20 client=172.20.0.3 TCP_MEM_HIT/200 GET http://news.example.test/headlines server=-
```

One `TCP_MISS` went to the site; the two `TCP_MEM_HIT`s came from Squid's memory. With 500 employees reading the
same page, the company pays for the bandwidth once. The log also shows who asked for what: `client=172.20.0.3` is
the workstation.

### Step 7.5: What the website learns about the employee

```bash
docker logs lab12-public-site 2>/dev/null | grep 'host=news' | tail -2
```

Expected output:

```text
172.18.0.3 host=news.example.test "GET / HTTP/1.1" status=200 xff="172.20.0.3" via="1.1 b526fd700f21 (squid/6.13)"
172.18.0.3 host=news.example.test "GET /headlines HTTP/1.1" status=200 xff="172.20.0.3" via="1.1 b526fd700f21 ..."
```

The TCP connection came from Squid (`172.18.0.3`). Squid added `X-Forwarded-For` with the workstation address
(`forwarded_for on`) and a `Via` header that names itself (`via on`). Both are Squid defaults.

### Step 7.6: HTTPS through a forward proxy

From your machine (not inside the workstation shell), request an HTTPS page through Squid:

```bash
docker exec lab12-workstation curl -sS --cacert /certs/public-site.crt \
    -x http://forward-proxy:3128 https://news.example.test/private/salary-report
docker logs lab12-forward-proxy 2>&1 | grep CONNECT | tail -1
docker logs lab12-public-site 2>/dev/null | grep salary | tail -1
```

Expected output:

```text
news.example.test: today's headlines (served to 172.18.0.3)
05:45:20 client=172.20.0.3 TCP_TUNNEL/200 CONNECT news.example.test:443 server=172.18.0.2
172.18.0.3 host=news.example.test "GET /private/salary-report HTTP/1.1" status=200 xff="-" via="-"
```

For HTTPS the client asks Squid to `CONNECT` a raw tunnel to `news.example.test:443` and runs TLS through it.
Squid logs the host and port, but **not** the path `/private/salary-report`: it never saw it. For the same reason
it could not add `X-Forwarded-For` or `Via` (the site log shows `-`), and it cannot cache HTTPS responses.

### Step 7.7: Use the proxy from your own machine

Squid is also published on port 18128. Your machine cannot resolve `news.example.test`, but the proxy can:

```bash
curl -sS -m 5 http://news.example.test/
curl -sS -x http://localhost:18128 http://news.example.test/
```

Expected output:

```text
curl: (6) Could not resolve host: news.example.test
news.example.test: today's headlines (served to 172.18.0.3)
```

This is what a browser does when an operating system has a proxy configured: it sends every request to the proxy.
Command-line tools usually read the `http_proxy` and `https_proxy` environment variables instead of `-x`.

> **Question:** Companies often need to see the full HTTPS URL to block malware downloads. How can a forward proxy
> do that, and what must be installed on every employee laptop for it to work?
>
> **Hint:** Search for "TLS interception" or "SSL bumping" in Squid. Whose certificate does the browser see?
>
> **Question:** Which line would you change in `squid/squid.conf` so that websites cannot learn internal addresses,
> and why would a company want that?
>
> **Hint:** Look at the comment above `forwarded_for`. Internal addresses reveal how the network is laid out.

---

## Task 8: Both Proxies in One Path

In real systems a request often crosses both kinds of proxy: the employee's company runs a forward proxy, and the
website runs a reverse proxy. The reverse proxy in this lab is also on `lab12-internet` with the name
`shop.example.test`, so the workstation can reach it, but only through Squid.

### Step 8.1: Send the request through both proxies

```bash
docker exec lab12-workstation curl -sS -m 5 --cacert /certs/proxy.crt https://shop.example.test:8443/users/
docker exec -e https_proxy=http://forward-proxy:3128 lab12-workstation \
    curl -sS --cacert /certs/proxy.crt https://shop.example.test:8443/users/
```

Expected output:

```text
curl: (6) Could not resolve host: shop.example.test (DNS server returned general failure)
{
  "service": "users-service",
  "instance": "2fe377360fcb",
  "path_seen": "/",
  "client_ip_seen": "172.19.0.4",
  "host_header": "shop.example.test",
  "x_forwarded_for": "172.18.0.3",
  "x_forwarded_proto": "https",
  "x_real_ip": "172.18.0.3"
}
```

This time curl picked up the proxy from the `https_proxy` variable. Squid allows `CONNECT` to port 8443 only
because `squid.conf` lists it in both `Safe_ports` and `SSL_ports`.

### Step 8.2: Follow the request through each log

```bash
docker logs lab12-forward-proxy 2>&1 | grep 'shop.example.test' | tail -1
docker logs lab12-proxy 2>/dev/null | grep 'GET /users/' | tail -1
docker logs lab12-users 2>&1 | tail -1
```

Expected output:

```text
05:46:50 client=172.20.0.3 TCP_TUNNEL/200 CONNECT shop.example.test:8443 server=172.18.0.4
172.18.0.3 "GET /users/ HTTP/2.0" status=200 cache=- client_key= upstream=172.19.0.3:5000 rt=0.002 xff="-"
users-service GET / client=172.19.0.4 xff=172.18.0.3 proto=https host=shop.example.test
```

Fill in what each hop knows:

| Hop | Sees the workstation (`172.20.0.3`)? | Sees the URL path? | Connection comes from |
| --- | --- | --- | --- |
| Squid (forward) | Yes | No, only `shop.example.test:8443` | the workstation |
| nginx (reverse) | No | Yes, after TLS termination | Squid (`172.18.0.3`) |
| users-service | No | Yes, rewritten to `/` | nginx (`172.19.0.4`) |

### Step 8.3: The same path over plain HTTP

Over HTTP, Squid can read and modify the request:

```bash
docker exec lab12-workstation curl -sS -o /dev/null -w '%{http_code} %{redirect_url}\n' \
    -x http://forward-proxy:3128 http://shop.example.test:8088/users/
docker logs lab12-proxy 2>/dev/null | grep 'status=301' | tail -1
```

Expected output:

```text
301 https://shop.example.test:8443/users/
172.18.0.3 "GET /users/ HTTP/1.1" status=301 cache=- client_key= upstream=- rt=0.000 xff="172.20.0.3"
```

Now nginx received `X-Forwarded-For: 172.20.0.3` from Squid, but it only answered with the redirect to HTTPS,
where that information is lost again.

> **Question:** Go back to the last question of Task 5. Every employee of a 2,000-person company reaches your shop
> through one forward proxy. What happens if your rate limit is 100 requests per minute per IP address?
>
> **Hint:** Look at the `client=` and `$remote_addr` columns above. How many distinct addresses does the shop see?
>
> **Question:** Could your reverse proxy trust the `X-Forwarded-For` that a forward proxy sends? Under which
> conditions?
>
> **Hint:** Look up nginx `set_real_ip_from`. Who controls the forward proxy, and who controls yours?
>
> **Question:** Write one sentence for each proxy in this lab that completes "it acts on behalf of ...".
>
> **Hint:** Who chose to put each proxy there, and whose identity does each one hide?

---

## Cleanup

```bash
./cleanup.sh
```

Expected output:

```text
=== Lab 12: Cleanup ===

Stopping and removing containers, networks, volumes and the backend image...
Removing generated TLS certificates...

Cleanup complete. Verify with: docker ps -a --filter name=lab12-
```

Verify that nothing is left:

```bash
docker ps -a --filter name=lab12-
docker network ls --filter name=lab12-
```

Both commands should print only their header line. The script also deletes `certs/`, so the next `./setup.sh`
generates a new key pair.
