# DNS and BIND Lab

![DNS](https://img.shields.io/badge/DNS-%234285F4.svg?style=for-the-badge&logo=google-domains&logoColor=white)
![BIND](https://img.shields.io/badge/BIND9-%23326CE5.svg?style=for-the-badge&logoColor=white)
![AWS](https://img.shields.io/badge/AWS-%23FF9900.svg?style=for-the-badge&logo=amazon-aws&logoColor=white)

## Overview

This hands-on lab teaches DNS fundamentals through practical exercises using `dig` and BIND9. Students will learn how DNS works, explore different DNS record types, configure a DNS server, and understand DNS-based load balancing.

## Learning Objectives

- Understand how DNS translates domain names to IP addresses
- Use `dig` to query and diagnose DNS records
- Explore different DNS record types (A, AAAA, CNAME, MX, NS, TXT, PTR)
- Configure BIND9 as an authoritative DNS server
- Implement DNS-based load balancing with Round Robin
- Compare DNS load balancing vs HAProxy load balancing
- Validate DNS configurations with `named-checkconf` and `named-checkzone`

## Prerequisites

- AWS EC2 instance (Amazon Linux 2023 recommended)
- Open ports: 22 (SSH), 53 (DNS)
- Basic Linux command line knowledge
- SSH access to EC2 instance

## What is DNS?

**DNS (Domain Name System)** is the "phone book" of the Internet:
- Converts human-readable names (`www.google.com`) to IP addresses (`142.250.191.14`)
- Eliminates the need to memorize IP addresses
- Distributed and hierarchical for global scalability

## Lab Structure

This lab is divided into exercises that build upon each other. Execute each command and observe the results to understand DNS behavior.

---

## Exercise 1: Exploring DNS with `dig`

### What is `dig`?

`dig` (Domain Information Groper) is a command-line tool for querying DNS servers and obtaining detailed information about domains.

### Basic Syntax

```bash
dig [options] [domain] [record_type]
```

### Task 1.1: Basic DNS Queries

Execute these commands and observe the output:

```bash
# Basic query - gets A record (IP address)
dig google.com

# Show only the answer (no additional info)
dig google.com +short

# Query specific record types
dig google.com MX        # Mail servers
dig google.com NS        # Name servers
dig google.com TXT       # Text records
```

**Questions to consider:**
- What IP address does `google.com` resolve to?
- How many mail servers does Google have?
- What are the authoritative name servers for `google.com`?

### Task 1.2: Using Different DNS Servers

```bash
# Query using Google's DNS
dig @8.8.8.8 amazon.com

# Query using Cloudflare's DNS
dig @1.1.1.1 amazon.com

# Query using OpenDNS
dig @208.67.222.222 amazon.com
```

**Public DNS Servers:**
- **8.8.8.8** - Google Public DNS (fast and reliable)
- **1.1.1.1** - Cloudflare DNS (privacy-focused)
- **208.67.222.222** - OpenDNS (security filtering)

### Task 1.3: Reverse DNS Lookup

```bash
# Reverse lookup - IP to hostname
dig -x 8.8.8.8

# Try with other IPs
dig -x 1.1.1.1
```

---

## Exercise 2: DNS Record Types

### Common DNS Record Types

| Type | Purpose | Example |
|------|---------|---------|
| **A** | IPv4 address | `www.example.com → 192.168.1.10` |
| **AAAA** | IPv6 address | `www.example.com → 2001:db8::1` |
| **CNAME** | Canonical name (alias) | `blog.example.com → www.example.com` |
| **MX** | Mail server | `example.com → mail.example.com` |
| **NS** | Name server | `example.com → ns1.example.com` |
| **TXT** | Text record | `example.com → "v=spf1 mx ~all"` |
| **PTR** | Reverse lookup | `192.168.1.10 → www.example.com` |

### Task 2.1: Explore Different Record Types

```bash
# A record - IPv4 address
dig github.com A +short

# AAAA record - IPv6 address
dig github.com AAAA +short

# MX record - Mail servers
dig github.com MX +short

# NS record - Name servers
dig github.com NS +short

# TXT record - Text information
dig github.com TXT +short
```

### Task 2.2: Full DNS Information

```bash
# Get all information about a domain
dig github.com ANY

# Trace the full DNS resolution path
dig github.com +trace
```

**Observe:**
- How DNS queries traverse from root servers to authoritative servers
- The hierarchical nature of DNS resolution

---

## Exercise 3: Comparing DNS Servers

### Task 3.1: Performance Comparison

Create a simple script to compare DNS server response times:

```bash
# Test different DNS servers
for server in 8.8.8.8 1.1.1.1 208.67.222.222; do
    echo "Testing DNS server: $server"
    time dig @$server amazon.com +short
    echo "---"
done
```

**Questions:**
- Which DNS server responds fastest?
- Does the response time vary between queries?

---

## Exercise 4: Installing and Configuring BIND9

### What is BIND9?

**BIND9** (Berkeley Internet Name Domain) is the most widely used DNS server software:
- Open source, developed by ISC (Internet Systems Consortium)
- Implements all DNS standards (RFC compliant)
- Can act as authoritative and recursive DNS server
- Used by most ISPs and enterprises

### Task 4.1: Install BIND9

```bash
# Install BIND9 and utilities
sudo dnf install bind bind-utils -y

# Verify installation
named -v
```

**What did we install?**
- `bind` - The BIND9 DNS server
- `bind-utils` - Tools like `dig`, `nslookup`, `named-checkconf`

### Task 4.2: Basic BIND Configuration

Create the main configuration file:

```bash
# Backup original configuration
sudo cp /etc/named.conf /etc/named.conf.backup

# Create basic configuration
sudo tee /etc/named.conf > /dev/null << 'EOF'
options {
    listen-on port 53 { any; };
    directory "/var/named";
    allow-query { any; };
    recursion yes;
};

zone "test.local" IN {
    type master;
    file "/var/named/test.local.db";
};
EOF
```

**Configuration Explained:**

**`options` section:**
- `listen-on port 53 { any; }` - Listen on port 53 (DNS) on all interfaces
- `directory "/var/named"` - Directory for zone files
- `allow-query { any; }` - Allow queries from any IP
- `recursion yes` - Enable recursive resolution

**`zone` section:**
- Defines a DNS zone this server manages
- `type master` - This server is authoritative for this zone
- `file` - Zone file containing DNS records

### Task 4.3: Create Zone File

```bash
# Create zone file with DNS records
sudo tee /var/named/test.local.db > /dev/null << 'EOF'
$TTL 300
@   IN  SOA ns1.test.local. admin.test.local. (
        1           ; Serial
        300         ; Refresh
        180         ; Retry
        604800      ; Expire
        300         ; Minimum TTL
)

@           IN  NS      ns1.test.local.
ns1         IN  A       127.0.0.1

; Single server
web         IN  A       192.168.1.10

; DNS Load Balancing - multiple IPs for www
www         IN  A       192.168.1.10
www         IN  A       192.168.1.11
www         IN  A       192.168.1.12

; CNAME example
blog        IN  CNAME   www.test.local.

; MX record example
@           IN  MX  10  mail.test.local.
mail        IN  A       192.168.1.20
EOF

# Set proper ownership
sudo chown named:named /var/named/test.local.db
```

**Zone File Explained:**

**SOA (Start of Authority):**
- `$TTL 300` - Time to live (5 minutes)
- `Serial 1` - Version number (increment on changes)
- `Refresh 300` - How often secondary DNS checks for updates
- `Retry 180` - Retry interval if sync fails
- `Expire 604800` - When data expires without contact (7 days)

**DNS Records:**
- `NS` - Defines name server for the zone
- `A` - Maps hostname to IPv4 address
- `CNAME` - Creates an alias
- `MX` - Defines mail server with priority

---

## Exercise 5: Validating DNS Configuration

### Task 5.1: Validate Configuration Files

```bash
# Validate main configuration
sudo named-checkconf /etc/named.conf
echo "✅ Configuration validated"

# Validate zone file
sudo named-checkzone test.local /var/named/test.local.db
echo "✅ Zone file validated"
```

**What do these commands do?**

**`named-checkconf`:**
- Checks syntax of configuration file
- Detects format errors before starting service
- Validates zone file references

**`named-checkzone`:**
- Checks syntax of specific zone file
- Validates DNS records (SOA, NS, A, etc.)
- Detects common errors

### Task 5.2: Start BIND9 Service

```bash
# Start BIND9
sudo systemctl start named

# Enable on boot
sudo systemctl enable named

# Check status
sudo systemctl status named
```

---

## Exercise 6: Testing DNS Load Balancing

### Task 6.1: Query Local DNS Server

```bash
# Test basic resolution
dig @127.0.0.1 web.test.local +short

# Test CNAME
dig @127.0.0.1 blog.test.local +short

# Test MX record
dig @127.0.0.1 test.local MX +short
```

### Task 6.2: Observe DNS Load Balancing

```bash
# Query www.test.local multiple times
echo "=== DNS LOAD BALANCING TEST ==="
for i in {1..6}; do
    echo "Query $i:"
    dig @127.0.0.1 www.test.local +short
    echo "---"
    sleep 1
done
```

**Observe:**
- How the order of IP addresses changes between queries
- This is DNS Round Robin load balancing in action

---

## Exercise 7: DNS Load Balancing vs HAProxy

### DNS Load Balancing Characteristics

**How it works:**
- DNS server returns multiple IP addresses for the same hostname
- Client (browser) typically chooses the first IP
- DNS rotates the order of IPs in subsequent queries

**Algorithm:** Simple Round Robin
- DNS server rotates IPs in each response
- Does not consider current server load
- No automatic session persistence

### HAProxy Load Balancing Characteristics

**How it works:**
- Single entry point (load balancer IP)
- HAProxy intercepts all connections
- Distributes traffic using intelligent algorithms
- Monitors server health in real-time

**Algorithms available:**
- Round Robin, Least Connections, Weighted, Source Hash, etc.
- Considers current server state
- Automatic health checks
- Configurable session persistence

### Comparison Table

| Aspect | DNS Load Balancing | HAProxy Load Balancing |
|--------|-------------------|------------------------|
| **Algorithm** | Simple Round Robin | Multiple intelligent algorithms |
| **Health Checks** | ❌ Not automatic | ✅ Automatic and configurable |
| **Session Persistence** | ❌ Limited (TTL-based) | ✅ Multiple options |
| **Latency** | ✅ Very low | ⚠️ Additional hop |
| **Scalability** | ✅ Very high | ⚠️ Limited by LB capacity |
| **Cost** | ✅ Very low | ⚠️ Requires additional infrastructure |
| **Flexibility** | ❌ Basic | ✅ Very high |
| **Failover** | ⚠️ Slow (depends on TTL) | ✅ Fast (seconds) |

### When to Use Each

**Use DNS Load Balancing when:**
- You need maximum global scalability
- Servers are relatively stable
- Cost is a primary concern
- Application doesn't require session persistence
- You can tolerate slow failover (minutes)

**Use HAProxy when:**
- You need advanced balancing algorithms
- You require automatic health checks
- Application needs session persistence
- You need fast failover (seconds)
- You want granular traffic control

**Use both (hybrid) when:**
- You have multiple data centers
- DNS for geographic distribution
- HAProxy for local balancing in each DC

---

## Exercise 8: Advanced DNS Queries

### Task 8.1: DNS Query Tracing

```bash
# Trace full DNS resolution path
dig www.google.com +trace

# Show query time
dig www.google.com +stats
```

### Task 8.2: Batch Queries

```bash
# Query multiple domains
for domain in google.com amazon.com github.com; do
    echo "Resolving $domain:"
    dig $domain +short
    echo "---"
done
```

---

## Troubleshooting

### BIND won't start

```bash
# Check configuration syntax
sudo named-checkconf

# Check zone files
sudo named-checkzone test.local /var/named/test.local.db

# Check logs
sudo journalctl -u named -n 50

# Check SELinux (if enabled)
sudo ausearch -m avc -ts recent
```

### DNS queries not working

```bash
# Check if BIND is running
sudo systemctl status named

# Check if port 53 is listening
sudo ss -tulpn | grep :53

# Test locally first
dig @127.0.0.1 test.local

# Check firewall
sudo firewall-cmd --list-all
```

### Zone file errors

```bash
# Validate zone file
sudo named-checkzone test.local /var/named/test.local.db

# Check file permissions
ls -l /var/named/test.local.db

# Should be owned by named:named
sudo chown named:named /var/named/test.local.db
```

---

## Useful Diagnostic Commands

```bash
# View current DNS configuration
cat /etc/resolv.conf

# Test with different tools
nslookup google.com
host google.com
dig google.com

# Monitor DNS queries in real-time
sudo tcpdump -i any port 53

# View BIND statistics
sudo rndc stats
sudo cat /var/named/data/named_stats.txt

# Reload BIND configuration
sudo rndc reload

# Flush DNS cache
sudo rndc flush
```

---

## Key Concepts Summary

1. **DNS** translates domain names to IP addresses using a distributed system
2. **`dig`** is the primary tool for DNS diagnostics
3. **BIND9** is the most widely used DNS server software
4. **DNS Load Balancing** uses simple Round Robin but is highly scalable
5. **HAProxy** offers more intelligent algorithms but requires more infrastructure
6. **Both approaches** have valid use cases and can be combined

---

## Cleanup

To remove the lab setup:

```bash
# Stop BIND
sudo systemctl stop named
sudo systemctl disable named

# Remove configuration
sudo rm /etc/named.conf
sudo rm /var/named/test.local.db

# Restore original configuration
sudo mv /etc/named.conf.backup /etc/named.conf
```

---

## Additional Resources

- [BIND9 Official Documentation](https://www.isc.org/bind/)
- [ICANN Accredited Registrars](https://www.icann.org/en/contracted-parties/accredited-registrars/list-of-accredited-registrars)
- [DNS RFC Standards](https://www.ietf.org/rfc/)
- [AWS Route 53 Documentation](https://docs.aws.amazon.com/route53/)

## Author

Created by [Alex Garcia](https://github.com/gamaware)

- [LinkedIn Profile](https://www.linkedin.com/in/gamaware/)
- [Personal Website](https://alexgarcia.info/)

## License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.
