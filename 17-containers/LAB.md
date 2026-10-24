# Lab 17: Containers

> For the lab overview, architecture diagram, and key concepts, see
> [README.md](README.md).

## Prerequisites

- **Docker Desktop** installed and running (macOS or Windows), or Docker
  Engine on Linux. Give Docker at least **4 GiB of memory** (Docker Desktop
  > Settings > Resources): the Kubernetes cluster runs three nodes.
- A terminal that supports bash (macOS Terminal, Linux shell, Git Bash
  on Windows, or WSL)
- `curl`, used to call the containers
- **kind** (Kubernetes in Docker), tested with **v0.33.0**
- **kubectl**, the Kubernetes command-line client, version 1.36, 1.37 or
  1.38 (the cluster runs Kubernetes 1.37)
- Free local ports **8171**, **8172**, **5001** and **30080**
- About 3 GB of free disk space for the images

You do not need Go on your machine: the image build compiles the
application inside a container.

### Install kind and kubectl

**macOS** (Homebrew):

```bash
brew install kind kubectl
```

Docker Desktop also installs a `kubectl`. Either one works if
`kubectl version --client` reports 1.36 or later.

**Windows** (PowerShell), with winget or Chocolatey:

```powershell
winget install Kubernetes.kind
winget install Kubernetes.kubectl
# or
choco install kind kubernetes-cli
```

Close and reopen the terminal so that it finds the new commands.

**Linux** (x86-64; for ARM replace `amd64` with `arm64` and use the
matching checksum from the kind release page):

```bash
curl -fsSLo kind https://github.com/kubernetes-sigs/kind/releases/download/v0.33.0/kind-linux-amd64
echo "aee6151561422756b764a4ae28e7f44cda5af5a9eead3cc9985112b1de8d8e0d  kind" | sha256sum -c -
sudo install -m 0755 kind /usr/local/bin/kind

curl -fsSLO https://dl.k8s.io/release/v1.37.1/bin/linux/amd64/kubectl
curl -fsSLO https://dl.k8s.io/release/v1.37.1/bin/linux/amd64/kubectl.sha256
echo "$(cat kubectl.sha256)  kubectl" | sha256sum -c -
sudo install -m 0755 kubectl /usr/local/bin/kubectl
```

Both `sha256sum -c` commands must print `OK`. A checksum that does not
match means the download is not the file the project published: delete
it and download it again.

**Verify the tools:**

```bash
docker --version
kind version
kubectl version --client
```

### Windows notes

- Run the lab from **WSL** or **Git Bash**. PowerShell cannot run the
  `.sh` scripts.
- In Git Bash, run this once in every terminal you open. It stops Git Bash
  from rewriting paths such as `/sys/fs/cgroup` that belong to a container:

  ```bash
  export MSYS_NO_PATHCONV=1
  ```

- Docker Desktop must use the WSL 2 backend (the default).

## Quick Start

```bash
cd 17-containers
chmod +x setup.sh cleanup.sh scripts/*.sh
./setup.sh
```

The setup script checks the tools and the ports and downloads every image
the lab uses, so that no task waits on a download. It starts nothing: you
create every container and the cluster yourself, starting with **Task 1**.

Expected output (abbreviated):

```text
=== Lab 17: Containers (Docker and kind) ===

Checking prerequisites...
  Docker:  Docker version 29.9.2, build a82e528
  Memory:  7.7 GiB available to Docker
  kind:    v0.33.0
  kubectl: v1.37.1
...
Checking that the lab ports are free...
  port 8171: free
  port 8172: free
  port 5001: free
  port 30080: free

Downloading the pinned images (about 1.5 GB the first time)...
  nginx:1.30.6-alpine@sha256:47928bf6...
...
=== Environment ready ===
```

## How to Read the Output

All outputs below come from a real run of this lab on an Apple silicon
Mac with Docker Desktop. Container IDs, pod names, IP addresses, image
digests, timings and the way requests spread over pods will differ on
your machine. The numbers that matter (sizes, counts, error totals) should
be close.

Docker Desktop stores images with containerd, so `docker images` shows a
**DISK USAGE** column (unpacked size) and a **CONTENT SIZE** column (the
compressed download). Docker Engine on Linux may show a single **SIZE**
column instead.

Several tasks use two terminals: one for commands, one for a traffic
generator or a watch. Open the second terminal in the same `17-containers`
directory.

---

## Task 1: Your First Container

A container is a normal Linux process that the kernel isolates with
**namespaces** (what the process can see) and limits with **cgroups**
(what it can use). You will start a web server, reach it, read its logs,
and look at both mechanisms.

### Step 1.1: Run nginx

```bash
docker run -d --name lab17-first -p 127.0.0.1:8171:80 --memory 64m --cpus 0.5 \
    nginx:1.30.6-alpine@sha256:47928bf67eb62a1863cb08d9ecb52d3e704304ba614eaee17884204677702951
```

- `-d` runs the container in the background and prints its ID.
- `-p 127.0.0.1:8171:80` publishes port 80 of the container on port 8171
  of your machine, on the loopback address only.
- `--memory 64m --cpus 0.5` sets the cgroup limits.
- The image reference ends in `@sha256:...`, the **digest** of the image.
  A tag such as `1.30.6-alpine` can move to a new build; a digest names
  exactly one build. Every image in this lab is pinned this way.

Check that it runs:

```bash
docker ps --filter name=lab17-first --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
```

Expected output:

```text
NAMES         IMAGE                 STATUS         PORTS
lab17-first   nginx:1.30.6-alpine   Up 2 seconds   127.0.0.1:8171->80/tcp
```

### Step 1.2: Reach it and read the logs

```bash
curl -sI http://127.0.0.1:8171/ | head -3
docker logs lab17-first 2>&1 | tail -3
```

Expected output:

```text
HTTP/1.1 200 OK
Server: nginx/1.30.6
Date: Sat, 24 Oct 2026 16:57:34 GMT
2026/10/24 16:57:32 [notice] 1#1: start worker process 46
2026/10/24 16:57:32 [notice] 1#1: start worker process 47
172.17.0.1 - - [24/Oct/2026:16:57:34 +0000] "HEAD / HTTP/1.1" 200 0 "-" "curl/8.7.1" "-"
```

nginx writes its logs to standard output, and Docker keeps them. The last
line is your request. It comes from `172.17.0.1`, the gateway of the
Docker network: Docker forwarded the connection from port 8171.

### Step 1.3: Namespaces: what the container sees

List the processes **inside** the container:

```bash
docker exec lab17-first ps -o pid,user,comm | head -4
docker exec lab17-first hostname
```

Expected output:

```text
PID   USER     COMMAND
    1 root     nginx
   30 nginx    nginx
   31 nginx    nginx
748346c10377
```

Inside its **PID namespace**, nginx is process 1, and the container only
sees its own processes. Its **UTS namespace** gives it its own host name,
the short container ID. Now look at the same process from the host. The
second command starts a throwaway container that shares the host PID
namespace (`--pid host`) and lists every process:

```bash
docker inspect -f 'pid={{.State.Pid}} ip={{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' lab17-first
docker run --rm --pid host \
    alpine:3.24@sha256:be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a \
    ps -o pid,args | grep -E 'PID|nginx: master'
```

Expected output:

```text
pid=1417 ip=172.17.0.3
PID   COMMAND
 1417 nginx: master process nginx -g daemon off;
```

The same nginx is process 1 inside the container and process 1417 on the
host. On macOS and Windows "the host" is the small Linux virtual machine
that Docker Desktop runs: containers need a Linux kernel. The container
also has its own **network namespace**, with its own IP address.

### Step 1.4: Cgroups: what the container can use

```bash
docker exec lab17-first cat /sys/fs/cgroup/memory.max /sys/fs/cgroup/cpu.max
docker exec lab17-first nproc
docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.PIDs}}' lab17-first
```

Expected output:

```text
67108864
50000 100000
18
NAME          CPU %     MEM USAGE / LIMIT   PIDS
lab17-first   0.00%     16.04MiB / 64MiB    19
```

- `memory.max` is 67,108,864 bytes: the 64 MiB you asked for.
- `cpu.max` reads "50,000 microseconds of CPU in every 100,000": half a
  CPU.
- `nproc` still reports every CPU of the machine (18 here), and nginx
  started one worker per CPU, which is why the container has 19 processes.
  A CPU limit caps **time**, not the number of CPUs a process can see.

### Step 1.5: Hit the memory limit

Start a container that allocates memory until something stops it:

```bash
docker run --name lab17-oom --memory 32m --memory-swap 32m \
    alpine:3.24@sha256:be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a \
    sh -c 'tail /dev/zero'
echo "exit code: $?"
docker inspect -f 'OOMKilled={{.State.OOMKilled}} ExitCode={{.State.ExitCode}}' lab17-oom
docker rm lab17-oom
```

Expected output:

```text
exit code: 137
OOMKilled=true ExitCode=137
lab17-oom
```

`tail /dev/zero` keeps reading a line that never ends. When the process
reached 32 MiB, the kernel's out-of-memory killer ended it with signal 9
(exit code 128 + 9 = 137). Kubernetes reports the same `OOMKilled` reason
when a pod exceeds its memory limit.

### Step 1.6: Stop it

```bash
docker stop lab17-first
docker rm lab17-first
```

`docker stop` sends `SIGTERM`, waits up to 10 seconds, then sends
`SIGKILL`. nginx exits on `SIGTERM` at once.

**Record for your report:** the PID of nginx inside the container and on
the host, the value of `memory.max`, the number of processes in the
container, and the exit code of the OOM test.

> **Question:** Two containers on the same machine both run a process with
> PID 1. How is that possible, and what does the kernel actually see?
>
> **Hint:** Compare Step 1.3 inside and outside the container.
>
> **Question:** A Java or Node.js runtime sizes its thread pool from the
> number of CPUs. What could go wrong when it runs with `--cpus 0.5` on a
> machine with 18 CPUs?
>
> **Hint:** Look at what `nproc` reported in Step 1.4.

---

## Task 2: Containerize an Application

The application is `app/main.go`, a small HTTP service. It answers `/`
with its version and host name, has a liveness endpoint (`/healthz`), a
readiness endpoint (`/readyz`) and a `/work` endpoint that burns CPU. You
will package it twice and compare the results.

Open `app/Dockerfile.single` and `app/Dockerfile` before you start.

### Step 2.1: Build the naive image

`Dockerfile.single` starts from the official Go image, copies the source,
compiles it, and ships everything:

```bash
docker build -f app/Dockerfile.single -t lab17-web:single app
```

### Step 2.2: Build the multi-stage image

`Dockerfile` has two stages. The first one compiles a static binary with
the Go image. The second one starts from `distroless/static`, an image
with no shell and no package manager, and copies only the binary. It
also sets a non-root user and a `HEALTHCHECK`:

```bash
docker build -t lab17-web:v1 app
```

### Step 2.3: Compare sizes and layers

```bash
docker images lab17-web
```

Expected output:

```text
IMAGE              ID             DISK USAGE   CONTENT SIZE   EXTRA
lab17-web:single   02a5a2c5f455       1.44GB          335MB
lab17-web:v1       9891a60a7670       15.1MB         3.39MB
```

The same program weighs 1.44 GB in one image and 15 MB in the other,
about 95 times less. Look at the layers of each:

```bash
docker history lab17-web:single --format 'table {{.CreatedBy}}\t{{.Size}}' | cut -c1-70
docker history lab17-web:v1 --format 'table {{.CreatedBy}}\t{{.Size}}' | cut -c1-70
```

Expected output (abbreviated):

```text
CREATED BY                                      SIZE
CMD ["web"]                                     0B
EXPOSE [8080/tcp]                               0B
RUN |1 VERSION=v1 /bin/sh -c go build -ldfla…   102MB
ARG VERSION=v1                                  0B
COPY . . # buildkit                             20.5kB
...
COPY /target/ / # buildkit                      290MB
...
RUN /bin/sh -c set -eux;  apt-get update;  a…   281MB
RUN /bin/sh -c set -eux;  apt-get update;  a…   208MB
RUN /bin/sh -c set -eux;  apt-get update;  a…   63.7MB
# debian.sh --arch 'arm64' out/ 'trixie' '@1…   156MB

CREATED BY                                      SIZE
ENTRYPOINT ["/web"]                             0B
HEALTHCHECK {Test:[CMD /web -healthcheck] In…   0B
EXPOSE [8080/tcp]                               0B
USER 65532:65532                                0B
COPY /out/web /web # buildkit                   5.97MB
bazel build //common:cacerts_debian13_arm64_…   319kB
...
bazel build @trixie//base-files/arm64:data_s…   741kB
```

Each instruction that changes files adds a **layer**. The naive image
carries a Debian system, compilers and the Go toolchain (the 290 MB
layer), plus 102 MB of build cache from the compile step. The multi-stage
image carries a 6 MB binary on top of a few small distroless layers.
Count the layers:

```bash
docker inspect -f '{{len .RootFS.Layers}} layers' lab17-web:single lab17-web:v1
```

### Step 2.4: Who runs the process

```bash
docker run --rm lab17-web:single id
docker run --rm --entrypoint sh lab17-web:v1
```

Expected output:

```text
uid=0(root) gid=0(root) groups=0(root)
docker: Error response from daemon: failed to create task for container: failed to create shim task: OCI runtime
create failed: runc create failed: unable to start container process: error during container init: exec: "sh":
executable file not found in $PATH
```

The naive image runs as **root** and has a shell. The distroless image
has no `sh` to start: an attacker who breaks into the process finds no
shell, no package manager and no `curl`.

### Step 2.5: Run the image and watch the health check

```bash
docker run -d --name lab17-web -p 127.0.0.1:8172:8080 lab17-web:v1
docker ps --filter name=lab17-web --format '{{.Status}}'
sleep 8
docker ps --filter name=lab17-web --format '{{.Status}}'
curl -s http://127.0.0.1:8172/
docker top lab17-web -o user,pid,args
```

Expected output:

```text
Up Less than a second (health: starting)
Up 7 seconds (healthy)
version=v1 host=0d93d3cfb03b uptime=7s
USER                PID                 COMMAND
65532               6635                /web
```

Docker ran `/web -healthcheck` inside the container every 10 seconds; the
first success turned the status to `healthy`. The process runs as user
65532 (`nonroot`). The host name in the answer is the container ID.

### Step 2.6: Graceful shutdown

```bash
docker stop lab17-web
docker logs lab17-web
docker rm lab17-web
```

Expected output (the log):

```text
2026/10/24 16:58:29 lab17-web v1 listening on :8080 (host 0d93d3cfb03b, ready after 0s)
2026/10/24 16:58:29 ready to receive traffic
2026/10/24 16:58:36 GET / from 172.17.0.1:59634
2026/10/24 16:59:02 SIGTERM received: finishing in-flight requests
2026/10/24 16:59:02 stopped
```

The application catches `SIGTERM`, finishes the requests in progress and
exits. Kubernetes sends the same signal before it removes a pod, which
matters for the zero-downtime update of Task 8.

**Record for your report:** the size of both images (disk usage and
content size), the number of layers of each, the user each one runs as,
and the health status of `lab17-web`.

> **Question:** Why does `app/Dockerfile` copy `go.mod` before `main.go`
> instead of copying the whole directory at once?
>
> **Hint:** Docker reuses a layer when its instruction and its inputs did
> not change. Which file changes more often?
>
> **Question:** The multi-stage image has no shell. How would you debug a
> running container built from it?
>
> **Hint:** Look up `docker debug` and `kubectl debug` with an ephemeral
> container.

---

## Task 3: Images and Registries

A **registry** stores images so that other machines can pull them. Docker
Hub is a public registry; Amazon ECR, GitHub Container Registry and
Harbor are others. You will run a private registry as a container, push
the image, delete it locally and pull it back.

### Step 3.1: Start the registry

```bash
docker run -d --name lab17-registry --restart unless-stopped -p 127.0.0.1:5001:5000 \
    registry:2.8.3@sha256:a3d8aaa63ed8681a604f1dea0aa03f100d5895b6a58ace528858a7b332415373
curl -s http://localhost:5001/v2/_catalog
```

Expected output:

```text
{"repositories":[]}
```

The registry speaks the OCI distribution API over HTTP. The lab uses
port 5001 because macOS uses port 5000 for AirPlay.

### Step 3.2: Tag and push

An image name includes the registry it belongs to. Tag the image for
`localhost:5001`, then push it:

```bash
docker tag lab17-web:v1 localhost:5001/lab17-web:v1
docker push localhost:5001/lab17-web:v1
curl -s http://localhost:5001/v2/_catalog
curl -s http://localhost:5001/v2/lab17-web/tags/list
```

Expected output (abbreviated):

```text
The push refers to repository [localhost:5001/lab17-web]
c172f21841df: Pushed
...
v1: digest: sha256:d186680b852f9cb4506b912317eea7078cdfb0fb0899db76ff6990f7a3036e83 size: 856
{"repositories":["lab17-web"]}
{"name":"lab17-web","tags":["v1"]}
```

Docker pushed one blob per layer, then the **manifest** that lists them.
The digest is the SHA-256 of that manifest. Ask the registry for it:

```bash
curl -s -I -H 'Accept: application/vnd.oci.image.index.v1+json' \
    http://localhost:5001/v2/lab17-web/manifests/v1 | grep -i -E 'content-type|docker-content-digest'
```

Expected output:

```text
Content-Type: application/vnd.oci.image.index.v1+json
Docker-Content-Digest: sha256:d186680b852f9cb4506b912317eea7078cdfb0fb0899db76ff6990f7a3036e83
```

The top-level object is an **image index**: a list with one manifest per
platform (here `linux/arm64`) plus a build attestation. A machine with a
different CPU architecture picks its own entry from the same tag.

### Step 3.3: Delete the local copy and pull it back

```bash
docker image rm localhost:5001/lab17-web:v1 lab17-web:v1
docker pull localhost:5001/lab17-web:v1
docker inspect -f '{{index .RepoDigests 0}}' localhost:5001/lab17-web:v1
```

Expected output:

```text
Untagged: localhost:5001/lab17-web:v1
Untagged: lab17-web:v1
...
Digest: sha256:d186680b852f9cb4506b912317eea7078cdfb0fb0899db76ff6990f7a3036e83
Status: Downloaded newer image for localhost:5001/lab17-web:v1
localhost:5001/lab17-web@sha256:d186680b852f9cb4506b912317eea7078cdfb0fb0899db76ff6990f7a3036e83
```

The pulled image has the same digest as the pushed one: the registry
returned exactly the bytes you uploaded. Run it by digest:

```bash
docker run --rm -d --name lab17-pulled -p 127.0.0.1:8172:8080 \
    "$(docker inspect -f '{{index .RepoDigests 0}}' localhost:5001/lab17-web:v1)"
sleep 1
curl -s http://127.0.0.1:8172/
docker stop lab17-pulled
```

Expected output:

```text
version=v1 host=6a903cdfc291 uptime=1s
lab17-pulled
```

**Record for your report:** the digest of `localhost:5001/lab17-web:v1`,
the number of layers the push uploaded, and the output of the tags list.

> **Question:** Production deployments often reference images by digest
> instead of by tag. What can go wrong with a tag such as `v1` or
> `latest`?
>
> **Hint:** Push a different image with the same tag and think about what
> a node that pulls it tomorrow receives.
>
> **Question:** `lab17-registry` accepts pushes from anyone who can reach
> port 5001, over plain HTTP. What would a production registry add?
>
> **Hint:** Think about authentication, TLS, image scanning and
> immutable tags.

---

## Task 4: Create a Kubernetes Cluster

Kubernetes runs containers on a group of machines called **nodes**. The
**control plane** stores the desired state and makes decisions; the
**worker nodes** run the containers. kind builds a cluster in which every
node is a Docker container.

Open `kind/cluster.yaml`: one control plane node and two workers, the node
image pinned by digest, and port 30080 of the control plane published on
`127.0.0.1:30080` for Task 5.

### Step 4.1: Create the cluster

```bash
kind create cluster --config kind/cluster.yaml
```

Expected output (about one minute):

```text
Creating cluster "lab17" ...
 ✓ Ensuring node image (kindest/node:v1.37.0) 🖼
 ✓ Preparing nodes 📦 📦 📦
 ✓ Writing configuration 📜
 ✓ Starting control-plane 🕹️
 ✓ Installing CNI 🔌
 ✓ Installing StorageClass 💾
 ✓ Joining worker nodes 🚜
Set kubectl context to "kind-lab17"
```

kind also added a `kind-lab17` context to your kubeconfig and made it the
current one, so `kubectl` now talks to this cluster.

### Step 4.2: Connect the registry

The nodes must pull `localhost:5001/lab17-web`, but inside a node
container `localhost` is the node itself. Read `scripts/connect-registry.sh`,
then run it:

```bash
./scripts/connect-registry.sh
```

Expected output:

```text
  lab17-control-plane: localhost:5001 -> http://lab17-registry:5000
  lab17-worker2: localhost:5001 -> http://lab17-registry:5000
  lab17-worker: localhost:5001 -> http://lab17-registry:5000
  lab17-registry joined the 'kind' Docker network
configmap/local-registry-hosting created
```

The script tells containerd, the container runtime of each node, that
`localhost:5001` means the `lab17-registry` container, and attaches the
registry to the `kind` Docker network so the nodes can reach it by name.

### Step 4.3: Nodes are containers

```bash
docker ps --filter name=lab17 --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}'
kubectl get nodes -o wide
```

Expected output:

```text
NAMES                 IMAGE                  PORTS
lab17-control-plane   kindest/node:v1.37.0   127.0.0.1:30080->30080/tcp, 127.0.0.1:58606->6443/tcp
lab17-worker2         kindest/node:v1.37.0
lab17-worker          kindest/node:v1.37.0
lab17-registry        registry:2.8.3         127.0.0.1:5001->5000/tcp
NAME                  STATUS   ROLES           AGE   VERSION   INTERNAL-IP   ...   CONTAINER-RUNTIME
lab17-control-plane   Ready    control-plane   29s   v1.37.0   172.19.0.4    ...   containerd://2.3.4
lab17-worker          Ready    <none>          18s   v1.37.0   172.19.0.2    ...   containerd://2.3.4
lab17-worker2         Ready    <none>          18s   v1.37.0   172.19.0.3    ...   containerd://2.3.4
```

Three containers play the role of three machines. Port 6443 of the
control plane is the **API server**; kubectl reaches it on a random local
port (58606 here).

### Step 4.4: The control plane

```bash
kubectl cluster-info
kubectl get pods -n kube-system -o wide | awk '{print $1, $3, $7}' | column -t
```

Expected output:

```text
Kubernetes control plane is running at https://127.0.0.1:58606
CoreDNS is running at https://127.0.0.1:58606/api/v1/namespaces/kube-system/services/kube-dns:dns/proxy
NAME                                         STATUS   NODE
coredns-559f6c778d-2zpwq                     Running  lab17-control-plane
coredns-559f6c778d-n2ltl                     Running  lab17-control-plane
etcd-lab17-control-plane                     Running  lab17-control-plane
kindnet-42mp7                                Running  lab17-control-plane
kindnet-8xm8l                                Running  lab17-worker2
kindnet-zrvjv                                Running  lab17-worker
kube-apiserver-lab17-control-plane           Running  lab17-control-plane
kube-controller-manager-lab17-control-plane  Running  lab17-control-plane
kube-proxy-cl928                             Running  lab17-control-plane
kube-proxy-r9jkc                             Running  lab17-worker
kube-proxy-vwwxv                             Running  lab17-worker2
kube-scheduler-lab17-control-plane           Running  lab17-control-plane
```

Kubernetes runs its own components as pods. Four of them form the
control plane and run only on `lab17-control-plane`:

| Component | Job |
| --- | --- |
| `kube-apiserver` | The only entry point: every client, controller and node talks to it |
| `etcd` | The key-value store that holds the state of the cluster |
| `kube-scheduler` | Chooses a node for every new pod |
| `kube-controller-manager` | Runs the control loops that move the actual state toward the desired one |

Two run on **every** node: `kube-proxy` (implements Services) and
`kindnet` (the network plugin that gives each pod an IP address). CoreDNS
resolves Service names inside the cluster.

The control plane components are **static pods**: the kubelet of the
control plane node starts them from files, before the API server exists:

```bash
docker exec lab17-control-plane ls /etc/kubernetes/manifests
kubectl describe node lab17-control-plane | grep Taints
```

Expected output:

```text
etcd.yaml
kube-apiserver.yaml
kube-controller-manager.yaml
kube-scheduler.yaml
Taints:             node-role.kubernetes.io/control-plane:NoSchedule
```

The **taint** keeps application pods off the control plane node.

### Step 4.5: Inside a worker node

```bash
docker exec lab17-worker sh -c 'ps -e -o pid,comm | grep -E "containerd$|kubelet|kube-proxy|kindnet"'
docker exec lab17-worker crictl ps
```

Expected output:

```text
    130 containerd
    246 kubelet
    418 kube-proxy
    576 kindnetd
CONTAINER       IMAGE           CREATED          STATE    NAME          ATTEMPT  ...  POD               NAMESPACE
5fc51942685a2   8e13ccc0aaa68   23 seconds ago   Running  kindnet-cni   0        ...  kindnet-zrvjv     kube-system
9c74a284c0b3f   550b682d81d41   24 seconds ago   Running  kube-proxy    0        ...  kube-proxy-r9jkc  kube-system
```

A worker runs the **kubelet**, the agent that receives pods from the API
server and asks **containerd** to start their containers. `crictl` talks
to containerd directly; at this point it shows only the two system
containers of the node.

**Record for your report:** the number of nodes and their roles, the four
control plane components and the node they run on, and the processes
that run on a worker.

> **Question:** kubectl, the scheduler, the controllers and every kubelet
> talk only to the API server, never to each other or to etcd. What does
> that design make easier, and what does it make the API server?
>
> **Hint:** Think about authentication, auditing, and what happens if the
> API server is down.
>
> **Question:** Here all nodes share one machine. What would a real
> cluster put on separate machines, and why does etcd usually run on three
> or five of them?
>
> **Hint:** Recall quorum from the high availability class.

---

## Task 5: Deploy the Application

You do not tell Kubernetes "start three containers". You declare a
**desired state**, three replicas of this image, and controllers make it
true and keep it true.

Open `k8s/deployment.yaml` and `k8s/service.yaml`. The Deployment asks
for three replicas of `localhost:5001/lab17-web:v1`, with probes, resource
requests and limits, and a non-root security context. The Service gives
the pods one stable address and publishes it on NodePort 30080.

### Step 5.1: Apply the manifests

```bash
kubectl apply -f k8s/deployment.yaml -f k8s/service.yaml
kubectl rollout status deployment/lab17-web --timeout=120s
```

Expected output:

```text
deployment.apps/lab17-web created
service/lab17-web created
Waiting for deployment "lab17-web" rollout to finish: 0 of 3 updated replicas are available...
Waiting for deployment "lab17-web" rollout to finish: 1 of 3 updated replicas are available...
Waiting for deployment "lab17-web" rollout to finish: 2 of 3 updated replicas are available...
deployment "lab17-web" successfully rolled out
```

### Step 5.2: What Kubernetes created

```bash
kubectl get deployment,replicaset,pods,service,endpointslices -l app=lab17-web -o wide
```

Expected output (trimmed):

```text
NAME                        READY   UP-TO-DATE   AVAILABLE   AGE   CONTAINERS   IMAGES
deployment.apps/lab17-web   3/3     3            3           5s    web          localhost:5001/lab17-web:v1

NAME                                   DESIRED   CURRENT   READY   AGE
replicaset.apps/lab17-web-67d987c499   3         3         3       5s

NAME                             READY   STATUS    RESTARTS   AGE   IP           NODE
pod/lab17-web-67d987c499-6lks7   1/1     Running   0          5s    10.244.1.2   lab17-worker2
pod/lab17-web-67d987c499-9l5cw   1/1     Running   0          5s    10.244.3.3   lab17-worker
pod/lab17-web-67d987c499-cb2wl   1/1     Running   0          5s    10.244.3.2   lab17-worker

NAME                TYPE       CLUSTER-IP   EXTERNAL-IP   PORT(S)        AGE
service/lab17-web   NodePort   10.96.6.33   <none>        80:30080/TCP   5s

NAME                                             ADDRESSTYPE   PORTS   ENDPOINTS
endpointslice.discovery.k8s.io/lab17-web-kxkd8   IPv4          8080    10.244.1.2,10.244.3.2,10.244.3.3
```

Read it from top to bottom: the **Deployment** created a **ReplicaSet**,
the ReplicaSet created three **pods**, the scheduler placed them on the
two workers, and the **EndpointSlice** lists the IP addresses of the pods
that are ready to receive traffic. The Service routes to those addresses.
Each kubelet pulled the image from your registry:

```bash
kubectl get events --field-selector reason=Pulled -o custom-columns=POD:.involvedObject.name,MESSAGE:.message \
    | cut -c1-110 | head -3
```

```text
POD                          MESSAGE
lab17-web-67d987c499-9l5cw   Successfully pulled image "localhost:5001/lab17-web:v1" in 65ms (737ms including
```

### Step 5.3: Reach the application

```bash
for i in 1 2 3 4 5 6; do curl -s http://127.0.0.1:30080/; done
```

Expected output:

```text
version=v1 host=lab17-web-67d987c499-6lks7 uptime=9s
version=v1 host=lab17-web-67d987c499-cb2wl uptime=9s
version=v1 host=lab17-web-67d987c499-6lks7 uptime=9s
version=v1 host=lab17-web-67d987c499-cb2wl uptime=9s
version=v1 host=lab17-web-67d987c499-9l5cw uptime=9s
version=v1 host=lab17-web-67d987c499-6lks7 uptime=10s
```

Every request opens a new connection, and kube-proxy picks one of the
ready pods for it at random. From now on you will use
`scripts/traffic.sh`, which sends about seven requests per second and
counts the answers by version and by pod:

```bash
./scripts/traffic.sh 5
```

Expected output:

```text
Sending requests to http://127.0.0.1:30080/ for 5 s (one every 0.1 s)...
  t=  1s  sent=7     errors=0    last: version=v1 host=lab17-web-67d987c499-6lks7
...
=== Summary: 28 requests in 5 s, 0 errors ===
By version:
    28 version=v1
By pod:
     4 host=lab17-web-67d987c499-6lks7
    17 host=lab17-web-67d987c499-9l5cw
     7 host=lab17-web-67d987c499-cb2wl
```

Read the logs of the pods, all at once through the Deployment:

```bash
kubectl logs deployment/lab17-web --tail=2
```

```text
Found 3 pods, using pod/lab17-web-67d987c499-6lks7
2026/10/24 17:01:54 GET / from 172.19.0.4:57655
2026/10/24 17:01:54 GET / from 172.19.0.4:55320
```

The requests come from `172.19.0.4`, the control plane node: your
connection entered there on port 30080 and kube-proxy forwarded it.

**Record for your report:** the names of the Deployment, ReplicaSet and
pods, the node of each pod, and how many requests each pod answered in
the 5-second test.

> **Question:** The pod names share the suffix `67d987c499`. Where does it
> come from, and what will change in Task 8?
>
> **Hint:** Compare the ReplicaSet name with the pod names.
>
> **Question:** The traffic test spread 28 requests 4, 17 and 7. Why not 9,
> 9 and 10?
>
> **Hint:** kube-proxy chooses a pod at random for each new connection.
> What happens to the split with 10,000 requests?

---

## Task 6: Self-Healing

A controller compares the desired state with the actual state in a loop
and acts on the difference. You will remove pieces of the actual state
and measure how long Kubernetes takes to put them back.

### Step 6.1: Delete a pod

Define a column layout that shows when each pod was created and when it
became ready, then delete one pod:

```bash
COLS='custom-columns=POD:.metadata.name,NODE:.spec.nodeName,CREATED:.metadata.creationTimestamp'
COLS="$COLS"',READY-SINCE:.status.conditions[?(@.type=="Ready")].lastTransitionTime'
kubectl get pods -l app=lab17-web -o "$COLS"
POD=$(kubectl get pods -l app=lab17-web -o jsonpath='{.items[0].metadata.name}')
kubectl delete pod "$POD" --wait=false
kubectl get pods -l app=lab17-web
```

Expected output:

```text
POD                          NODE            CREATED                READY-SINCE
lab17-web-67d987c499-6lks7   lab17-worker2   2026-10-24T17:01:39Z   2026-10-24T17:01:44Z
lab17-web-67d987c499-9l5cw   lab17-worker    2026-10-24T17:01:39Z   2026-10-24T17:01:44Z
lab17-web-67d987c499-cb2wl   lab17-worker    2026-10-24T17:01:39Z   2026-10-24T17:01:44Z
pod "lab17-web-67d987c499-6lks7" deleted from default namespace
NAME                         READY   STATUS        RESTARTS   AGE
lab17-web-67d987c499-6lks7   1/1     Terminating   0          52s
lab17-web-67d987c499-9l5cw   1/1     Running       0          52s
lab17-web-67d987c499-cb2wl   1/1     Running       0          52s
lab17-web-67d987c499-vs5ln   0/1     Running       0          1s
```

The ReplicaSet saw two pods where it wanted three and created
`...-vs5ln` within the same second. The new pod is `0/1` ready: the app
answers `/readyz` with 503 for its first 3 seconds (`READY_DELAY` in the
Deployment), so the Service does not send it traffic yet. Wait 10
seconds and look again:

```bash
sleep 10
kubectl get pods -l app=lab17-web -o "$COLS"
```

```text
POD                          NODE            CREATED                READY-SINCE
lab17-web-67d987c499-9l5cw   lab17-worker    2026-10-24T17:01:39Z   2026-10-24T17:01:44Z
lab17-web-67d987c499-cb2wl   lab17-worker    2026-10-24T17:01:39Z   2026-10-24T17:01:44Z
lab17-web-67d987c499-vs5ln   lab17-worker2   2026-10-24T17:02:30Z   2026-10-24T17:02:35Z
```

The replacement was ready 5 seconds after it was created.

### Step 6.2: Crash the process

A pod can also survive while its container dies. Kill the application
process on the node that runs the new pod (here `lab17-worker2`; use the
node from your output). The command kills every `web` process on that
node:

```bash
docker exec lab17-worker2 pkill -KILL -x web
sleep 4
kubectl get pods -l app=lab17-web -o wide
```

Expected output (trimmed):

```text
NAME                         READY   STATUS    RESTARTS     AGE   IP           NODE
lab17-web-67d987c499-9l5cw   1/1     Running   0            72s   10.244.3.3   lab17-worker
lab17-web-67d987c499-cb2wl   1/1     Running   0            72s   10.244.3.2   lab17-worker
lab17-web-67d987c499-vs5ln   0/1     Running   1 (4s ago)   21s   10.244.1.3   lab17-worker2
```

This time nobody replaced the pod: the **kubelet** restarted its
container in place. The pod keeps its name and its IP address, and
`RESTARTS` counts the crash. The reason of the last termination:

```bash
kubectl describe pod -l app=lab17-web | grep -A3 'Last State' | head -4
```

```text
    Last State:     Terminated
      Reason:       Error
      Exit Code:    137
```

### Step 6.3: Lose a whole node

Now stop the container that **is** the node `lab17-worker2`, as if the
machine lost power. In the **second terminal**, start the traffic
generator for 110 seconds:

```bash
./scripts/traffic.sh 110
```

In the **first terminal**, stop the node and watch the nodes and pods
every 10 seconds:

```bash
date -u +%T
docker stop lab17-worker2
for i in 1 2 3 4 5 6 7 8 9; do
    sleep 10
    echo "--- $(date -u +%T)"
    kubectl get nodes --no-headers | awk '{print $1, $2}'
    kubectl get pods -l app=lab17-web -o wide --no-headers | awk '{print $1, $3, $(NF-2)}'
done
```

Expected output (abbreviated):

```text
17:03:09
lab17-worker2
--- 17:03:19
lab17-control-plane Ready
lab17-worker Ready
lab17-worker2 Ready
lab17-web-67d987c499-9l5cw Running lab17-worker
lab17-web-67d987c499-cb2wl Running lab17-worker
lab17-web-67d987c499-vs5ln Running lab17-worker2
...
--- 17:04:10
lab17-control-plane Ready
lab17-worker Ready
lab17-worker2 NotReady
...
--- 17:04:20
lab17-control-plane Ready
lab17-worker Ready
lab17-worker2 NotReady
lab17-web-67d987c499-6mpvp Running lab17-worker
lab17-web-67d987c499-9l5cw Running lab17-worker
lab17-web-67d987c499-cb2wl Running lab17-worker
lab17-web-67d987c499-vs5ln Terminating lab17-worker2
```

Three phases:

1. **Nobody knows (about 50 s).** The node stopped at 17:03:09, but the
   control plane still reports it `Ready`. The controller manager marks a
   node `NotReady` only after its kubelet misses heartbeats for 50
   seconds.
2. **Eviction (about 10 s).** The Deployment tolerates a `NotReady` node
   for 10 seconds (`tolerationSeconds` in `k8s/deployment.yaml`; the
   default is 300). Then Kubernetes evicts the pod, and the ReplicaSet
   creates `...-6mpvp` on the healthy worker.
3. **Recovered.** Three pods run again. The old one stays `Terminating`
   because no kubelet is left to confirm that it stopped.

When the traffic generator finishes, read its summary:

```text
  t=  5s  sent=31    errors=0    last: version=v1 host=lab17-web-67d987c499-vs5ln
  t=  6s  sent=40    errors=1    last: ERROR timeout (no answer within 1 s)
...
  t= 58s  sent=131   errors=43   last: ERROR timeout (no answer within 1 s)
  t= 59s  sent=133   errors=43   last: version=v1 host=lab17-web-67d987c499-9l5cw
...
=== Summary: 568 requests in 110 s, 43 errors ===
...
Errors:
    35 ERROR timeout (no answer within 1 s)
     8 ERROR connection closed without an answer
```

For about 53 seconds, every request that kube-proxy sent to the pod on
the stopped node failed; the others succeeded. The errors stopped when
the node turned `NotReady`, because Kubernetes then marked its pod not
ready and removed it from the EndpointSlice.

### Step 6.4: Bring the node back

```bash
docker start lab17-worker2
kubectl wait --for=condition=Ready node/lab17-worker2 --timeout=120s
sleep 5
kubectl get pods -l app=lab17-web -o wide --no-headers | awk '{print $1, $3, $(NF-2)}'
```

Expected output:

```text
lab17-worker2
node/lab17-worker2 condition met
lab17-web-67d987c499-6mpvp Running lab17-worker
lab17-web-67d987c499-9l5cw Running lab17-worker
lab17-web-67d987c499-cb2wl Running lab17-worker
```

The node is back, the stale pod is gone, and all three pods still run on
`lab17-worker`. Kubernetes does not move running pods to rebalance a
cluster. A rolling restart replaces them one by one, and the scheduler
spreads the new pods over both workers:

```bash
kubectl rollout restart deployment/lab17-web
kubectl rollout status deployment/lab17-web --timeout=120s
sleep 10
kubectl get pods -l app=lab17-web -o wide --no-headers | awk '{print $(NF-2)}' | sort | uniq -c
```

Expected output (last lines):

```text
deployment "lab17-web" successfully rolled out
   1 lab17-worker
   2 lab17-worker2
```

**Record for your report:** fill in this table with your own numbers.

| Measurement | Your value |
| --- | --- |
| Time from deleting a pod to its replacement being ready (s) | |
| `RESTARTS` and exit code after killing the process | |
| Time from `docker stop` to the node turning `NotReady` (s) | |
| Time from `NotReady` to the replacement pod running (s) | |
| Failed requests while the node was down | |
| Pods per node after the node came back, before and after the restart | |

> **Question:** Why does Kubernetes wait 50 seconds before it declares a
> node `NotReady` instead of reacting after the first missed heartbeat?
>
> **Hint:** Think of a node that is slow or on a congested network, and of
> what an eviction costs.
>
> **Question:** The failed requests came from one pod out of three. What
> would make the application itself stop sending traffic to a dead pod
> sooner?
>
> **Hint:** Recall health checks and retries from the load balancing lab:
> which component could retry a timed-out request on another pod?

---

## Task 7: Scaling

### Step 7.1: Scale by hand

```bash
time (kubectl scale deployment/lab17-web --replicas=6 && \
    kubectl rollout status deployment/lab17-web --timeout=120s)
kubectl get deployment lab17-web
sleep 5
kubectl get pods -l app=lab17-web -o wide --no-headers | awk '{print $(NF-2)}' | sort | uniq -c
```

Expected output:

```text
deployment.apps/lab17-web scaled
Waiting for deployment "lab17-web" rollout to finish: 3 of 6 updated replicas are available...
Waiting for deployment "lab17-web" rollout to finish: 4 of 6 updated replicas are available...
Waiting for deployment "lab17-web" rollout to finish: 5 of 6 updated replicas are available...
deployment "lab17-web" successfully rolled out
real    0m4.901s
NAME        READY   UP-TO-DATE   AVAILABLE   AGE
lab17-web   6/6     6            6           4m52s
   3 lab17-worker
   3 lab17-worker2
```

Three new pods were serving in under 5 seconds, because the image was
already on both workers. Check that all six take traffic:

```bash
./scripts/traffic.sh 10
```

Expected output (summary):

```text
=== Summary: 69 requests in 10 s, 0 errors ===
By version:
    69 version=v1
By pod:
     7 host=lab17-web-59cccf67cd-7l67n
     8 host=lab17-web-59cccf67cd-b78fd
    14 host=lab17-web-59cccf67cd-h9ttd
    12 host=lab17-web-59cccf67cd-jpcz4
    13 host=lab17-web-59cccf67cd-pl48s
    15 host=lab17-web-59cccf67cd-tjlh6
```

The Service picked up the new pods without any change to it: it selects
pods by the label `app=lab17-web`, not by name. Scale back to three:

```bash
kubectl scale deployment/lab17-web --replicas=3
sleep 10
kubectl get pods -l app=lab17-web
```

### Step 7.2 (optional): Autoscale on CPU

The **HorizontalPodAutoscaler** (HPA) changes the replica count for you.
It needs CPU measurements, which come from **metrics-server**. Install
it, and allow it to skip TLS verification of the kubelets (acceptable in
a local kind cluster only):

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/download/v0.9.0/components.yaml
kubectl patch -n kube-system deployment metrics-server --type=json \
    -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
kubectl rollout status -n kube-system deployment/metrics-server --timeout=180s
sleep 30
kubectl top pods -l app=lab17-web
```

Expected output:

```text
NAME                         CPU(cores)   MEMORY(bytes)
lab17-web-59cccf67cd-b78fd   1m           4Mi
lab17-web-59cccf67cd-jpcz4   1m           1Mi
lab17-web-59cccf67cd-tjlh6   1m           2Mi
```

Open `k8s/hpa.yaml`: between 3 and 8 replicas, targeting 50 % of the CPU
each pod requests (50m, a twentieth of a CPU). Apply it, then start a
load generator pod that calls `/work?ms=20` in a loop:

```bash
kubectl apply -f k8s/hpa.yaml
kubectl run lab17-load --restart=Never \
    --image=busybox:1.37.0@sha256:bdf57e528e45e4433820e045b29b4597825a1c9e38353532d90a01445013f82e \
    -- /bin/sh -c 'while true; do wget -q -O /dev/null "http://lab17-web/work?ms=20"; done'
for i in 1 2 3 4 5 6; do sleep 15; kubectl get hpa lab17-web --no-headers; done
```

Expected output:

```text
horizontalpodautoscaler.autoscaling/lab17-web created
pod/lab17-load created
lab17-web   Deployment/lab17-web   cpu: 2%/50%     3     8     3     36s
lab17-web   Deployment/lab17-web   cpu: 239%/50%   3     8     3     51s
lab17-web   Deployment/lab17-web   cpu: 520%/50%   3     8     6     66s
lab17-web   Deployment/lab17-web   cpu: 433%/50%   3     8     8     81s
lab17-web   Deployment/lab17-web   cpu: 249%/50%   3     8     8     96s
lab17-web   Deployment/lab17-web   cpu: 240%/50%   3     8     8     112s
```

The load pod reaches the Service by its name, `lab17-web`, through the
cluster DNS. The HPA measured 239 % of the requested CPU and doubled the
Deployment to 6 replicas, then went to the maximum of 8. Utilization
stays above 50 % because 8 is the ceiling. Stop the load and remove the
autoscaler before Task 8:

```bash
kubectl delete pod lab17-load --now
kubectl delete hpa lab17-web
kubectl scale deployment/lab17-web --replicas=3
```

Without the `delete hpa` the HPA would scale back down by itself, but
only after the default **stabilization window** of 5 minutes, which
avoids removing pods during a short dip in load.

**Record for your report:** the time to scale from 3 to 6 replicas, the
pods per node at 6 replicas, and (optional part) the CPU utilization the
HPA reported and the replica counts it chose.

> **Question:** Scaling from 3 to 6 took under 5 seconds here. List two
> things that make it slower in a real cluster.
>
> **Hint:** Where did the image come from, and was there free capacity on
> the nodes?
>
> **Question:** The HPA scales on CPU. For the payment consumer of the
> messaging lab, which metric would you scale on instead?
>
> **Hint:** Recall queue depth.

---

## Task 8: Rolling Update and Rollback

A **rolling update** replaces pods a few at a time, so the service never
goes down. Four settings in `k8s/deployment.yaml` make it work:

| Setting | Value | Effect |
| --- | --- | --- |
| `maxSurge` | 1 | At most one extra pod above the desired count during the update |
| `maxUnavailable` | 0 | Never fewer ready pods than the desired count |
| `readinessProbe` | `/readyz` every 2 s | A new pod gets traffic only after it answers 200 |
| `preStop` sleep | 5 s | An old pod keeps serving while every node removes it from the Service |

### Step 8.1: Build and push v2

```bash
docker build --build-arg VERSION=v2 -t localhost:5001/lab17-web:v2 app
docker push localhost:5001/lab17-web:v2
curl -s http://localhost:5001/v2/lab17-web/tags/list
```

Expected output (abbreviated):

```text
#8 [build 2/5] WORKDIR /src
#8 CACHED
#9 [build 3/5] COPY go.mod ./
#9 CACHED
#10 [build 4/5] COPY main.go ./
#10 CACHED
...
44136fa355b3: Layer already exists
...
v2: digest: sha256:...
{"name":"lab17-web","tags":["v2","v1"]}
```

Only the compile step and the binary layer are new: Docker reused every
other layer from its cache, and the registry already had every base
layer.

### Step 8.2: Roll out v2 under traffic

In the **second terminal**:

```bash
./scripts/traffic.sh 45
```

In the **first terminal**, a few seconds later:

```bash
kubectl rollout history deployment/lab17-web
time (kubectl set image deployment/lab17-web web=localhost:5001/lab17-web:v2 && \
    kubectl rollout status deployment/lab17-web --timeout=120s)
kubectl annotate deployment/lab17-web kubernetes.io/change-cause="v2: rolling update"
```

Expected output:

```text
deployment.apps/lab17-web
REVISION  CHANGE-CAUSE
1         <none>
2         <none>

deployment.apps/lab17-web image updated
Waiting for deployment "lab17-web" rollout to finish: 1 out of 3 new replicas have been updated...
Waiting for deployment "lab17-web" rollout to finish: 2 out of 3 new replicas have been updated...
Waiting for deployment "lab17-web" rollout to finish: 1 old replicas are pending termination...
deployment "lab17-web" successfully rolled out
real    0m14.537s
deployment.apps/lab17-web annotated
```

Revision 1 is the first deployment and revision 2 the restart of Task 6.
When the traffic generator finishes:

```text
=== Summary: 303 requests in 45 s, 0 errors ===
By version:
    97 version=v1
   206 version=v2
By pod:
    47 host=lab17-web-59cccf67cd-b78fd
    18 host=lab17-web-59cccf67cd-jpcz4
    32 host=lab17-web-59cccf67cd-tjlh6
    66 host=lab17-web-5b6847c65c-46n8n
    76 host=lab17-web-5b6847c65c-drcnv
    64 host=lab17-web-5b6847c65c-zsq68
```

Zero errors while every pod was replaced. For a few seconds both versions
answered at once: a rolling update means v1 and v2 must be able to run
side by side.

### Step 8.3: A broken release

Deploy `v3`, a tag that you never pushed, and give the rollout 30 seconds.
Keep a traffic generator running in the second terminal
(`./scripts/traffic.sh 50`):

```bash
kubectl set image deployment/lab17-web web=localhost:5001/lab17-web:v3
kubectl annotate deployment/lab17-web kubernetes.io/change-cause="v3: image that was never pushed" --overwrite
kubectl rollout status deployment/lab17-web --timeout=30s
kubectl get pods -l app=lab17-web
kubectl get replicasets -l app=lab17-web
```

Expected output:

```text
deployment.apps/lab17-web image updated
deployment.apps/lab17-web annotated
Waiting for deployment "lab17-web" rollout to finish: 1 out of 3 new replicas have been updated...
error: timed out waiting for the condition
NAME                         READY   STATUS         RESTARTS   AGE
lab17-web-5b6847c65c-46n8n   1/1     Running        0          95s
lab17-web-5b6847c65c-drcnv   1/1     Running        0          105s
lab17-web-5b6847c65c-zsq68   1/1     Running        0          100s
lab17-web-fd9b99648-wtk9w    0/1     ErrImagePull   0          30s
NAME                   DESIRED   CURRENT   READY   AGE
lab17-web-59cccf67cd   0         0         0       8m13s
lab17-web-5b6847c65c   3         3         3       105s
lab17-web-67d987c499   0         0         0       12m
lab17-web-fd9b99648    1         1         0       30s
```

The rollout created one v3 pod (`maxSurge: 1`), which cannot pull its
image, and stopped there: with `maxUnavailable: 0` it may not remove a
v2 pod until a v3 pod is ready. The three v2 pods kept serving, and the
traffic generator reports **0 errors**, all `version=v2`.

### Step 8.4: Roll back

```bash
time (kubectl rollout undo deployment/lab17-web && kubectl rollout status deployment/lab17-web --timeout=60s)
kubectl rollout history deployment/lab17-web
```

Expected output:

```text
Warning: resource deployments/lab17-web was previously managed with 'kubectl apply'. Rolling back will not update the
kubectl.kubernetes.io/last-applied-configuration annotation, ...
deployment.apps/lab17-web rolled back
deployment "lab17-web" successfully rolled out
real    0m0.212s
deployment.apps/lab17-web
REVISION  CHANGE-CAUSE
1         <none>
2         <none>
4         v3: image that was never pushed
5         v2: rolling update
```

The rollback took 0.2 seconds: the v2 ReplicaSet still had its three
pods, so Kubernetes only had to delete the broken one. The old v2 revision
3 became revision 5. The warning reminds you that `k8s/deployment.yaml`
still says `v1`: in a real project you would fix the file and apply it,
so that the repository stays the source of truth.

### Step 8.5: The same update without a rolling strategy

For contrast, switch the Deployment to the `Recreate` strategy, which
stops every old pod before it starts the new ones. Start
`./scripts/traffic.sh 40` in the second terminal, then:

```bash
kubectl patch deployment lab17-web --type=merge -p '{"spec":{"strategy":{"type":"Recreate","rollingUpdate":null}}}'
time (kubectl set image deployment/lab17-web web=localhost:5001/lab17-web:v1 && \
    kubectl rollout status deployment/lab17-web --timeout=120s)
```

Expected traffic output:

```text
  t=  8s  sent=51    errors=0    last: version=v2 host=lab17-web-5b6847c65c-46n8n
  t=  9s  sent=57    errors=2    last: ERROR timeout (no answer within 1 s)
  t= 11s  sent=58    errors=3    last: ERROR timeout (no answer within 1 s)
  t= 12s  sent=59    errors=4    last: ERROR timeout (no answer within 1 s)
  t= 13s  sent=60    errors=5    last: ERROR timeout (no answer within 1 s)
  t= 14s  sent=61    errors=6    last: ERROR timeout (no answer within 1 s)
  t= 15s  sent=64    errors=6    last: version=v1 host=lab17-web-59cccf67cd-vwrwk
...
=== Summary: 225 requests in 40 s, 6 errors ===
```

For about 6 seconds no pod was ready and every request failed. Each one
waited the full 1-second timeout, which is why the count is low: a real
service with hundreds of clients would have failed hundreds of requests.

**Record for your report:** fill in this table.

| Measurement | Your value |
| --- | --- |
| Duration of the v1 to v2 rolling update (s) | |
| Requests and errors during the rolling update | |
| Requests answered by v1 and by v2 | |
| Status of the v3 pod and errors during the broken release | |
| Duration of the rollback (s) | |
| Errors and seconds without service with `Recreate` | |

> **Question:** Set `maxUnavailable: 1` and `maxSurge: 0`. How would the
> broken v3 release of Step 8.3 have affected users?
>
> **Hint:** The rollout would remove a v2 pod first. How many pods would
> serve traffic while v3 fails to start?
>
> **Question:** Remove the `readinessProbe` in your head and replay Step
> 8.2. What would users see during the 3 seconds the new pods need to
> warm up?
>
> **Hint:** Without readiness, Kubernetes considers a pod ready as soon as
> its container starts.
>
> **Question:** v1 and v2 answered side by side for a few seconds. Give an
> example of a change for which that is a problem.
>
> **Hint:** Think of a database schema change or a new API response
> format that old clients cannot read.

---

## Cleanup

```bash
./cleanup.sh
```

Expected output:

```text
=== Lab 17: Cleanup ===

Deleting the kind cluster lab17...
  Deleting cluster "lab17" ...
  Deleted nodes: ["lab17-control-plane" "lab17-worker2" "lab17-worker"]
Removing the lab containers...
  lab17-registry
Removing the images built in the lab...
  lab17-web:single
  localhost:5001/lab17-web:v2
  localhost:5001/lab17-web:v1
Removing the pinned base images...
  nginx:1.30.6-alpine
  alpine:3.24
  golang:1.27.2-trixie
  registry:2.8.3
  kindest/node:v1.37.0
Removed the Docker network kind.

Cleanup complete. The cluster, the containers, the lab images and the kind network are gone.
```

Run `./cleanup.sh --keep-images` instead if you plan to repeat the lab
and want to skip the downloads.

Verify cleanup:

```bash
docker ps -a --filter name=lab17
docker images --filter reference='*lab17*'
docker network ls --filter name=kind
kubectl config get-contexts kind-lab17
```

The first three commands should list nothing but their headers, and the
last one should report that the context `kind-lab17` was not found.
