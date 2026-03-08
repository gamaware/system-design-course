# Linux Networking Fundamentals Lab

![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)
![Docker](https://img.shields.io/badge/Docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Networking](https://img.shields.io/badge/Networking-%23009688.svg?style=for-the-badge&logoColor=white)

## Overview

This hands-on lab teaches Linux networking fundamentals through a troubleshooting
scenario. Students will explore network interfaces, routing tables, and connectivity
tools while diagnosing and fixing a broken network configuration in a containerized
environment.

## Learning Objectives

- Inspect network interfaces and IP addresses using `ip a` and `ip link`
- Understand routing tables and default gateways using `ip r`
- Test network connectivity with `ping`, `telnet`, and `curl`
- Diagnose common network issues (down interfaces, missing routes)
- Fix network configurations using `ip link` and `ip route` commands
- Use SSH to access remote systems for troubleshooting

## Prerequisites

- Docker and Docker Compose installed
- Basic Linux command line knowledge
- No AWS account required — this lab runs entirely locally

## Architecture

```mermaid
graph TB
    subgraph frontend["Frontend Network - 172.16.238.0/24"]
        BOB_FE["Bob's Laptop<br/>eth0: 172.16.238.10"]
        SRV_FE["devapp01-web<br/>eth0: 172.16.238.20"]
    end

    subgraph backend["Backend Network - 172.16.239.0/24"]
        BOB_BE["Bob's Laptop<br/>eth1: 172.16.239.10"]
        SRV_BE["devapp01<br/>eth1: 172.16.239.20"]
    end

    BOB_FE -."BROKEN".-> SRV_FE
    BOB_BE --"OK"--> SRV_BE

    style SRV_FE fill:#ff6b6b,stroke:#333,color:#fff
    style SRV_BE fill:#51cf66,stroke:#333,color:#fff
    style BOB_FE fill:#339af0,stroke:#333,color:#fff
    style BOB_BE fill:#339af0,stroke:#333,color:#fff
```

**Scenario:** An Apache web server (`devapp01-web`) should be accessible from
Bob's laptop on port 80, but something is wrong with the network. Students must
find and fix the issue.

## Lab Structure

```text
07-networking/
├── README.md              # This file
├── docker-compose.yml     # Lab environment definition
├── setup.sh               # Start lab and introduce network issues
├── cleanup.sh             # Tear down the environment
├── Dockerfile.laptop      # Bob's laptop image
└── Dockerfile.server      # Web server image
```

## Quick Start

```bash
cd 07-networking
chmod +x setup.sh cleanup.sh
./setup.sh
```

Then connect to Bob's laptop:

```bash
docker exec -it bob-laptop bash
```

---

## Task 1: Explore Network Interfaces

Bob's laptop is connected to two networks. Your first job is to discover the
network configuration.

### Step 1.1: List all network interfaces

From inside Bob's laptop, run:

```bash
ip a
```

You will see several interfaces. Ignore `lo` (loopback, 127.0.0.1).

> **Question:** Which IP addresses are assigned to Bob's laptop on `eth0`
> and `eth1`?
>
> **Hint:** Look for `inet` lines under each interface. Both addresses
> start with `172.16.`.

### Step 1.2: Check interface status

```bash
ip link
```

> **Question:** What is the state of each interface? Look for `UP` or
> `DOWN` in the output.
>
> **Hint:** Both `eth0` and `eth1` on Bob's laptop should show `state UP`.

---

## Task 2: Understand Routing

The routing table determines where network traffic is sent.

### Step 2.1: View the routing table

```bash
ip r
```

You should see entries for each connected network and a `default` route.

> **Question:** What is the default gateway IP address?
>
> **Hint:** The `default via X.X.X.X` entry shows the gateway. In this
> lab, the gateway is the first usable IP in the subnet: `172.16.238.1`.

### Step 2.2: Understand the routing entries

Each line in the routing table tells the system how to reach a network:

```text
172.16.238.0/24 dev eth0    # Traffic to 172.16.238.x goes via eth0
172.16.239.0/24 dev eth1    # Traffic to 172.16.239.x goes via eth1
default via 172.16.238.1    # Everything else goes to the gateway
```

---

## Task 3: Test Connectivity to the Web Server

An Apache web server is running on `devapp01-web` (port 80). Let's test if
we can reach it.

### Step 3.1: Test HTTP connectivity

```bash
telnet devapp01-web 80
```

Press `Ctrl+]` then type `quit` to exit telnet, or wait for timeout.

> **Question:** Were you able to connect to port 80?
>
> **Hint:** The connection should fail or hang. Something is wrong with
> the network path to `devapp01-web`.

### Step 3.2: Test basic connectivity with ping

```bash
ping -c 3 devapp01-web
```

> **Question:** Does ping succeed? What does this tell you about the
> network path?
>
> **Hint:** Ping should fail. The hostname `devapp01-web` resolves to
> `172.16.238.20` (frontend network), but that interface may be down on
> the server.

---

## Task 4: Find an Alternative Path

The web server has two network interfaces. The hostname `devapp01` resolves
to its backend network address.

### Step 4.1: Ping the backend address

```bash
ping -c 3 devapp01
```

> **Question:** Does this ping succeed? Why does this work when
> `devapp01-web` did not?
>
> **Hint:** `devapp01` resolves to `172.16.239.20` (backend network).
> This interface is UP, unlike the frontend interface.

---

## Task 5: Troubleshoot from the Server

Since we can reach the server via the backend network, let's connect and
investigate.

### Step 5.1: Connect to the web server

Option A — SSH from Bob's laptop:

```bash
ssh bob@devapp01
```

When prompted, enter the lab credential: `caleston123`

Option B — Direct container access (from your host terminal):

```bash
docker exec -it devapp01 bash
```

### Step 5.2: Inspect interfaces on the server

```bash
ip link
```

> **Question:** What is the state of `eth0` on the server?
>
> **Hint:** `eth0` should show `state DOWN`. This is why `devapp01-web`
> (`172.16.238.20`) is unreachable.

### Step 5.3: Check the routing table

```bash
ip r
```

> **Question:** Is there a default route configured?
>
> **Hint:** There should be no `default` entry. The default route is
> missing, which would prevent the server from reaching external networks
> even after bringing eth0 back up.

---

## Task 6: Fix the Network

Now that you've identified both problems (interface down + missing route),
fix them.

### Step 6.1: Bring up the frontend interface

From inside the `devapp01` container (use `sudo` if connected via SSH):

```bash
sudo ip link set dev eth0 up
```

Verify the interface is now UP:

```bash
ip link show eth0
```

### Step 6.2: Add the missing default route

```bash
sudo ip route add default via 172.16.238.1
```

Verify the route was added:

```bash
ip r
```

### Step 6.3: Verify connectivity from Bob's laptop

Go back to Bob's laptop (`exit` from SSH, or open a new terminal):

```bash
docker exec -it bob-laptop bash
```

Test connectivity:

```bash
# Ping should now succeed
ping -c 3 devapp01-web

# Telnet to port 80 should connect
telnet devapp01-web 80

# Curl should return the web page
curl http://devapp01-web
```

Expected output from curl:

```html
<html><body><h1>Welcome to devapp01 Web Server</h1></body></html>
```

---

## Cleanup

```bash
./cleanup.sh
```

Or manually:

```bash
docker compose down -v --rmi local
```

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `setup.sh` fails with permission denied | Script not executable | `chmod +x setup.sh` |
| `docker compose` not found | Docker Compose V2 not installed | Install Docker Desktop or `docker-compose-plugin` |
| `ip link set` permission denied | Missing NET_ADMIN capability | Ensure `cap_add: NET_ADMIN` is in docker-compose.yml |
| eth0 shows a different IP | Interface ordering varies | Run `ip a` and match IPs to identify the correct interface |
| SSH connection refused | SSHD not running on server | Use `docker exec -it devapp01 bash` instead |

## Key Concepts

| Concept | Description |
| --- | --- |
| **Network Interface** | A connection point between a device and a network (e.g., `eth0`, `eth1`) |
| **IP Address** | Unique identifier assigned to each interface on a network |
| **Routing Table** | Rules that determine where to send network traffic |
| **Default Gateway** | The router used to reach networks not in the local routing table |
| **Subnet** | A logical division of an IP network (e.g., `172.16.238.0/24`) |
| **DNS Resolution** | Translating hostnames (`devapp01-web`) to IP addresses (`172.16.238.20`) |

## Conclusions

After completing this lab, you should take away these lessons:

1. **Every network connection has layers.** A working connection requires the
   interface to be UP, an IP address assigned, a route to the destination,
   and the target service listening on the expected port.

2. **Multiple interfaces provide redundancy.** The web server had two network
   paths. When one failed, the other allowed access for troubleshooting — a
   pattern used extensively in production systems.

3. **Routing is not automatic.** A system with a network interface does not
   automatically know how to reach every destination. Default routes must be
   configured to enable connectivity beyond directly connected networks.

4. **Troubleshooting is systematic.** The approach used in this lab — test
   connectivity, isolate the failure point, access via alternative path,
   inspect the server, fix and verify — applies to real-world network
   debugging at any scale.

5. **These fundamentals map directly to cloud networking.** AWS VPCs, subnets,
   route tables, and security groups are abstractions of the same concepts
   you practiced here: interfaces, IP addresses, routes, and firewalls.

## Next Steps

- [Module 03 — Load Balancing with HAProxy](../03-load-balancing-haproxy/) —
  see how traffic is distributed across multiple servers
- [Module 04 — DNS with dig and BIND9](../04-dns-dig-bind9/) — understand how
  hostnames resolve to IP addresses
