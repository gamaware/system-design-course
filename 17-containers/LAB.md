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
`kubectl version --client` reports 1.36, 1.37 or 1.38.

**Windows with WSL:** in the WSL terminal, use the Linux commands below.
WSL does not see programs installed for Windows.

**Windows with Git Bash:** install the Windows versions from PowerShell,
with winget or Chocolatey, pinned to the versions this lab was tested
with:

```powershell
winget install Kubernetes.kind --version 0.33.0
winget install Kubernetes.kubectl --version 1.37.1
# or
choco install kind --version 0.33.0
choco install kubernetes-cli --version 1.37.1
```

Close and reopen Git Bash so that it finds the new commands.

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

The setup script checks the tools and the ports and downloads the images
that Docker on your machine uses, so that no task waits on them. The
Kubernetes nodes download the images of the optional part of Task 7 on
their own. It starts nothing: you
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
compressed download). Docker Engine on Linux, or Docker Desktop with the
classic image store, shows a single **SIZE** column instead, and its
image IDs, layer counts and push output differ from the ones below.

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
  exactly one build. Every image this lab names is pinned this way; the
  optional metrics-server of Task 7 comes from a fixed release manifest.

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
Date: Sat, 24 Oct 2026 17:30:57 GMT
2026/10/24 17:30:44 [notice] 1#1: start worker process 46
2026/10/24 17:30:44 [notice] 1#1: start worker process 47
172.17.0.1 - - [24/Oct/2026:17:30:57 +0000] "HEAD / HTTP/1.1" 200 0 "-" "curl/8.7.1" "-"
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
466d0e9c4a02
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
pid=43431 ip=172.17.0.2
PID   COMMAND
43431 nginx: master process nginx -g daemon off;
```

The same nginx is process 1 inside the container and process 43431 on
the host. On macOS and Windows "the host" is the small Linux virtual machine
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
lab17-first   0.00%     25.53MiB / 64MiB    19
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

`docker stop` sends the stop signal of the image (`SIGTERM` unless the
image sets another one; the nginx image uses `SIGQUIT`, its graceful
shutdown), waits up to 10 seconds, then sends `SIGKILL`. nginx exits at
once.

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
lab17-web:single   edf54a832526       1.44GB          335MB
lab17-web:v1       b1a777920ef8       15.1MB         3.39MB
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

Expected output:

```text
10 layers
14 layers
```

The small image has **more** layers: distroless ships each of its parts
(certificates, time zones, the `passwd` file) as a separate layer of a few
kilobytes. What makes an image large is what the layers contain, not how
many there are.

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
62d8bfe1e98df5f8037e7ba0cf02d3956bb9e94418d6fdff3d93bee4043500b6
Up Less than a second (health: starting)
Up 8 seconds (healthy)
version=v1 host=62d8bfe1e98d uptime=8s
USER                PID                 COMMAND
65532               11944               /web
```

Docker ran `/web -healthcheck` inside the container, about 5 seconds after
the start and every 10 seconds after that; the first success turned the
status to `healthy`. The process runs as user
65532 (`nonroot`). The host name in the answer is the container ID.

### Step 2.6: Graceful shutdown

Start a request that takes one second (`/work?ms=1000`) in the
background, stop the container while the request is still running, and
read the log:

```bash
curl -s 'http://127.0.0.1:8172/work?ms=1000' &
sleep 0.3
time docker stop lab17-web
wait
docker logs lab17-web
docker rm lab17-web
```

Expected output (your shell also prints the job number of the background
`curl`, and zsh prints the time on one line):

```text
version=v1 host=62d8bfe1e98d worked=1000ms loops=27093166
lab17-web

real    0m1.225s
...
2026/10/24 18:05:17 lab17-web v1 listening on :8080 (host 62d8bfe1e98d, ready after 0s)
2026/10/24 18:05:17 ready to receive traffic
2026/10/24 18:05:25 GET / from 172.17.0.1:63130
2026/10/24 18:05:26 SIGTERM received: finishing 1 in-flight request(s)
2026/10/24 18:05:26 GET /work?ms=1000 from 172.17.0.1:63142
2026/10/24 18:05:27 stopped
lab17-web
```

The application caught `SIGTERM`, stopped accepting new connections,
finished the request in progress and only then exited: the `curl` got
its full answer, and `docker stop` took about a second instead of
returning at once. The log line of a request is written when the request
ends, which is why `GET /work` appears after `SIGTERM`. Kubernetes sends
the same signal before it removes a pod, which matters for the
zero-downtime update of Task 8.

**Record for your report:** the size of both images (disk usage and
content size), the number of layers of each, the user each one runs as,
and the health status of `lab17-web`.

> **Question:** `app/Dockerfile` copies `go.mod` before `main.go`. This
> service uses only the standard library, so here it changes nothing. What
> would that order buy in a service with dependencies and a
> `RUN go mod download` between the two copies?
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
44136fa355b3: Pushed
...
5689407c3340: Pushed
v1: digest: sha256:b1a777920ef8517056895d500fd2c37e6e7f22556f912e7a8c636ab1e5183fbb size: 856
{"repositories":["lab17-web"]}
{"name":"lab17-web","tags":["v1"]}
```

Docker pushed 16 blobs: the 14 layers of the image and the parts of its
build attestation. Then it pushed the manifests that describe them.
The digest of the tag is the SHA-256 of the top-level manifest. Ask the
registry for it:

```bash
curl -s -I -H 'Accept: application/vnd.oci.image.index.v1+json' \
    http://localhost:5001/v2/lab17-web/manifests/v1 | grep -i -E 'content-type|docker-content-digest'
```

Expected output:

```text
Content-Type: application/vnd.oci.image.index.v1+json
Docker-Content-Digest: sha256:b1a777920ef8517056895d500fd2c37e6e7f22556f912e7a8c636ab1e5183fbb
```

The top-level object is an **image index**: a list with one image
manifest per platform (here `linux/arm64`) plus a build attestation, and
each image manifest lists the layers. A machine with a
different CPU architecture picks its own entry from the same tag. Docker
Desktop uses this digest as the image ID: compare it with the `ID` column
of Step 2.3.

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
Deleted: sha256:b1a777920ef8517056895d500fd2c37e6e7f22556f912e7a8c636ab1e5183fbb
v1: Pulling from lab17-web
...
a99dd1dd5eaf: Already exists
...
8ed8d5c24276: Pull complete
Digest: sha256:b1a777920ef8517056895d500fd2c37e6e7f22556f912e7a8c636ab1e5183fbb
Status: Downloaded newer image for localhost:5001/lab17-web:v1
localhost:5001/lab17-web:v1
localhost:5001/lab17-web@sha256:b1a777920ef8517056895d500fd2c37e6e7f22556f912e7a8c636ab1e5183fbb
```

The pulled image has the same digest as the pushed one: the registry
returned exactly the bytes you uploaded. Most layers report `Already
exists`: deleting the image removed its name, but Docker still had the
layers from the build, and a pull downloads only what is missing. Run the
image by digest:

```bash
docker run --rm -d --name lab17-pulled -p 127.0.0.1:8172:8080 \
    "$(docker inspect -f '{{index .RepoDigests 0}}' localhost:5001/lab17-web:v1)"
sleep 1
curl -s http://127.0.0.1:8172/
docker stop lab17-pulled
```

Expected output:

```text
55d21cb885c4c62152b2f9dbc497c64f9847c87a7f1cfda0c9a97a6290f10a3f
version=v1 host=55d21cb885c4 uptime=1s
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
kubectl wait --for=condition=Ready nodes --all --timeout=120s
```

Expected output (20 to 60 seconds):

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
...
node/lab17-control-plane condition met
node/lab17-worker condition met
node/lab17-worker2 condition met
```

The nodes report `NotReady` for a few seconds after `kind create` returns,
until the network plugin starts on each of them; `kubectl wait` blocks
until all three are `Ready`. kind also added a `kind-lab17` context to your kubeconfig and made it the
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
lab17-control-plane   kindest/node:v1.37.0   127.0.0.1:30080->30080/tcp, 127.0.0.1:55687->6443/tcp
lab17-worker2         kindest/node:v1.37.0
lab17-worker          kindest/node:v1.37.0
lab17-registry        registry:2.8.3         127.0.0.1:5001->5000/tcp
NAME                  STATUS   ROLES           AGE   VERSION   INTERNAL-IP   ...   CONTAINER-RUNTIME
lab17-control-plane   Ready    control-plane   28s   v1.37.0   172.19.0.3    ...   containerd://2.3.4
lab17-worker          Ready    <none>          13s   v1.37.0   172.19.0.4    ...   containerd://2.3.4
lab17-worker2         Ready    <none>          13s   v1.37.0   172.19.0.2    ...   containerd://2.3.4
```

Three containers play the role of three machines. Port 6443 of the
control plane is the **API server**; kubectl reaches it on a random local
port (55687 here).

### Step 4.4: The control plane

```bash
kubectl cluster-info
kubectl get pods -n kube-system -o wide | awk '{print $1, $3, $(NF-2)}' | column -t
```

Expected output:

```text
Kubernetes control plane is running at https://127.0.0.1:55687
CoreDNS is running at https://127.0.0.1:55687/api/v1/namespaces/kube-system/services/kube-dns:dns/proxy
...
NAME                                         STATUS   NODE
coredns-559f6c778d-cshm5                     Running  lab17-control-plane
coredns-559f6c778d-d28rt                     Running  lab17-control-plane
etcd-lab17-control-plane                     Running  lab17-control-plane
kindnet-7fzsk                                Running  lab17-worker2
kindnet-8pjqw                                Running  lab17-worker
kindnet-d44wf                                Running  lab17-control-plane
kube-apiserver-lab17-control-plane           Running  lab17-control-plane
kube-controller-manager-lab17-control-plane  Running  lab17-control-plane
kube-proxy-5q7qz                             Running  lab17-control-plane
kube-proxy-tmnz8                             Running  lab17-worker
kube-proxy-v964z                             Running  lab17-worker2
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
    129 containerd
    248 kubelet
    420 kube-proxy
    465 kindnetd
CONTAINER       IMAGE           CREATED          STATE    NAME          ...  POD               NAMESPACE
61e75e2e0e8f1   8e13ccc0aaa68   11 seconds ago   Running  kindnet-cni   ...  kindnet-8pjqw     kube-system
f8f31ad6fa307   550b682d81d41   11 seconds ago   Running  kube-proxy    ...  kube-proxy-tmnz8  kube-system
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

Open the three files in `k8s/`. `namespace.yaml` creates the `lab17`
**namespace**, a named group of objects inside the cluster; the other
manifests place their objects in it. The Deployment asks for three
replicas of `localhost:5001/lab17-web:v1`, with probes, resource requests
and limits, and a non-root security context. Its `imagePullPolicy:
Always` makes every new container ask the registry which image the tag
points to, so a tag that you push again takes effect. The Service gives
the pods one stable address and publishes it on NodePort 30080.

### Step 5.1: Apply the manifests

```bash
kubectl apply -f k8s/namespace.yaml
kubectl config set-context --current --namespace=lab17
kubectl apply -f k8s/deployment.yaml -f k8s/service.yaml
kubectl rollout status deployment/lab17-web --timeout=120s
```

The second command makes `lab17` the namespace of the `kind-lab17`
context, so every `kubectl` command of the rest of the lab works in it
without `-n lab17`.

Expected output:

```text
namespace/lab17 created
Context "kind-lab17" modified.
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
deployment.apps/lab17-web   3/3     3            3           6s    web          localhost:5001/lab17-web:v1

NAME                                   DESIRED   CURRENT   READY   AGE
replicaset.apps/lab17-web-75f757df57   3         3         3       6s

NAME                             READY   STATUS    RESTARTS   AGE   IP           NODE
pod/lab17-web-75f757df57-6wnkv   1/1     Running   0          6s    10.244.2.3   lab17-worker2
pod/lab17-web-75f757df57-88hqq   1/1     Running   0          6s    10.244.1.2   lab17-worker
pod/lab17-web-75f757df57-8vr47   1/1     Running   0          6s    10.244.2.2   lab17-worker2

NAME                TYPE       CLUSTER-IP    EXTERNAL-IP   PORT(S)        AGE
service/lab17-web   NodePort   10.96.20.23   <none>        80:30080/TCP   6s

NAME                                             ADDRESSTYPE   PORTS   ENDPOINTS
endpointslice.discovery.k8s.io/lab17-web-vm6cs   IPv4          8080    10.244.2.2,10.244.1.2,10.244.2.3
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
lab17-web-75f757df57-6wnkv   Successfully pulled image "localhost:5001/lab17-web:v1" in 30ms (343ms including
lab17-web-75f757df57-88hqq   Successfully pulled image "localhost:5001/lab17-web:v1" in 320ms (320ms including
```

### Step 5.3: Reach the application

```bash
for i in 1 2 3 4 5 6; do curl -s http://127.0.0.1:30080/; done
```

Expected output:

```text
version=v1 host=lab17-web-75f757df57-88hqq uptime=5s
version=v1 host=lab17-web-75f757df57-88hqq uptime=5s
version=v1 host=lab17-web-75f757df57-6wnkv uptime=5s
version=v1 host=lab17-web-75f757df57-6wnkv uptime=5s
version=v1 host=lab17-web-75f757df57-6wnkv uptime=5s
version=v1 host=lab17-web-75f757df57-88hqq uptime=5s
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
  t=  1s  sent=4     errors=0    last: version=v1 host=lab17-web-75f757df57-88hqq
...
=== Summary: 32 requests in 5 s, 0 errors ===
By version:
    32 version=v1
By pod:
    12 host=lab17-web-75f757df57-6wnkv
    14 host=lab17-web-75f757df57-88hqq
     6 host=lab17-web-75f757df57-8vr47
```

Read the latest lines of the log of one pod, chosen through the
Deployment:

```bash
kubectl logs deployment/lab17-web --tail=2
```

```text
Found 3 pods, using pod/lab17-web-75f757df57-8vr47
2026/10/24 18:06:15 GET / from 172.19.0.3:4258
2026/10/24 18:06:16 GET / from 172.19.0.3:32800
```

The requests come from `172.19.0.3`, the control plane node: your
connection entered there on port 30080 and kube-proxy forwarded it.

**Record for your report:** the names of the Deployment, ReplicaSet and
pods, the node of each pod, and how many requests each pod answered in
the 5-second test.

> **Question:** The pod names share the suffix `75f757df57`. Where does it
> come from, and what will change in Task 8?
>
> **Hint:** Compare the ReplicaSet name with the pod names.
>
> **Question:** The traffic test spread 32 requests 12, 14 and 6. Why not
> 11, 11 and 10?
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
lab17-web-75f757df57-6wnkv   lab17-worker2   2026-10-24T18:06:06Z   2026-10-24T18:06:12Z
lab17-web-75f757df57-88hqq   lab17-worker    2026-10-24T18:06:06Z   2026-10-24T18:06:12Z
lab17-web-75f757df57-8vr47   lab17-worker2   2026-10-24T18:06:06Z   2026-10-24T18:06:11Z
pod "lab17-web-75f757df57-6wnkv" deleted from lab17 namespace
NAME                         READY   STATUS              RESTARTS   AGE
lab17-web-75f757df57-6wnkv   1/1     Terminating         0          11s
lab17-web-75f757df57-779g8   0/1     ContainerCreating   0          0s
lab17-web-75f757df57-88hqq   1/1     Running             0          11s
lab17-web-75f757df57-8vr47   1/1     Running             0          11s
```

The ReplicaSet saw two pods where it wanted three and created
`...-779g8` at once. The new pod is not ready yet: the app answers
`/readyz` with 503 for its first 3 seconds (`READY_DELAY` in the
Deployment), so the Service does not send it traffic. The deleted pod
stays `Terminating` for 5 seconds, the `preStop` pause of Task 8. Wait 10
seconds and look again:

```bash
sleep 10
kubectl get pods -l app=lab17-web -o "$COLS"
```

```text
POD                          NODE            CREATED                READY-SINCE
lab17-web-75f757df57-779g8   lab17-worker    2026-10-24T18:06:17Z   2026-10-24T18:06:22Z
lab17-web-75f757df57-88hqq   lab17-worker    2026-10-24T18:06:06Z   2026-10-24T18:06:12Z
lab17-web-75f757df57-8vr47   lab17-worker2   2026-10-24T18:06:06Z   2026-10-24T18:06:11Z
```

The replacement was ready 5 seconds after it was created, about as fast
as the first three pods: the pull from the local registry takes less than
a second, and most of the 5 seconds are the 3 seconds of `READY_DELAY`
plus the wait for the next readiness probe.

### Step 6.2: Crash the process

A pod can also survive while its container dies. Find the node of the
newest pod and kill the application process there, from the node itself.
The command kills every `web` process on that node:

```bash
NODE=$(kubectl get pods -l app=lab17-web --sort-by=.metadata.creationTimestamp \
    -o jsonpath='{.items[-1:].spec.nodeName}')
echo "$NODE"
docker exec "$NODE" pkill -KILL -x web
sleep 4
kubectl get pods -l app=lab17-web -o wide
```

Expected output (trimmed):

```text
lab17-worker
NAME                         READY   STATUS    RESTARTS     AGE   IP           NODE
lab17-web-75f757df57-779g8   0/1     Running   1 (4s ago)   14s   10.244.1.3   lab17-worker
lab17-web-75f757df57-88hqq   0/1     Running   1 (4s ago)   25s   10.244.1.2   lab17-worker
lab17-web-75f757df57-8vr47   1/1     Running   0            25s   10.244.2.2   lab17-worker2
```

Both pods on `lab17-worker` lost their process. This time nobody
replaced them: the **kubelet** restarted each container in place. The
pods keep their names and IP addresses, and `RESTARTS` counts the crash.
For the next 3 seconds only `...-8vr47` was ready to serve. The reason of
the last termination:

```bash
kubectl describe pod -l app=lab17-web | grep -A3 'Last State' | head -4
```

```text
    Last State:     Terminated
      Reason:       Error
      Exit Code:    137
      Started:      Sat, 24 Oct 2026 12:06:17 -0600
```

Exit code 137 is `SIGKILL`, as in the memory test of Task 1.

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
18:06:36
lab17-worker2
--- 18:06:47
lab17-control-plane Ready
lab17-worker Ready
lab17-worker2 Ready
lab17-web-75f757df57-779g8 Running lab17-worker
lab17-web-75f757df57-88hqq Running lab17-worker
lab17-web-75f757df57-8vr47 Running lab17-worker2
...
--- 18:07:37
lab17-control-plane Ready
lab17-worker Ready
lab17-worker2 NotReady
lab17-web-75f757df57-779g8 Running lab17-worker
lab17-web-75f757df57-88hqq Running lab17-worker
lab17-web-75f757df57-8vr47 Running lab17-worker2
--- 18:07:47
lab17-control-plane Ready
lab17-worker Ready
lab17-worker2 NotReady
lab17-web-75f757df57-779g8 Running lab17-worker
lab17-web-75f757df57-88hqq Running lab17-worker
lab17-web-75f757df57-8vr47 Terminating lab17-worker2
lab17-web-75f757df57-fb7gr Running lab17-worker
```

Three phases:

1. **Nobody knows (about 50 s).** The node stopped at 18:06:36, but the
   control plane reported it `Ready` until 18:07:27. The controller
   manager marks a node `NotReady` only after its kubelet misses
   heartbeats for 50 seconds.
2. **Eviction (about 10 s).** The Deployment tolerates a `NotReady` node
   for 10 seconds (`tolerationSeconds` in `k8s/deployment.yaml`; the
   default is 300). Then Kubernetes evicts the pod, and the ReplicaSet
   creates `...-fb7gr` on the healthy worker.
3. **Recovered.** Three pods run again. The old one stays `Terminating`
   because no kubelet is left to confirm that it stopped.

When the traffic generator finishes, read its output:

```text
  t=  6s  sent=40    errors=0    last: version=v1 host=lab17-web-75f757df57-779g8
  t=  7s  sent=42    errors=1    last: ERROR timeout (no answer within 1 s)
...
  t= 57s  sent=149   errors=38   last: ERROR timeout (no answer within 1 s)
  t= 58s  sent=156   errors=38   last: version=v1 host=lab17-web-75f757df57-779g8
...
=== Summary: 486 requests in 110 s, 44 errors ===
By version:
   442 version=v1
By pod:
   164 host=lab17-web-75f757df57-779g8
   172 host=lab17-web-75f757df57-88hqq
    19 host=lab17-web-75f757df57-8vr47
    87 host=lab17-web-75f757df57-fb7gr
Errors:
     7 ERROR connection closed without an answer
    37 ERROR timeout (no answer within 1 s)
```

For about 50 seconds, every request that kube-proxy sent to the pod on
the stopped node failed: 38 of 109, about one in three, because one of
the three pods was there. Each failure waited the full 1-second timeout,
which is why the request rate dropped. The errors stopped when the node
turned `NotReady`: Kubernetes then marked its pod not ready and removed
it from the EndpointSlice. A few isolated errors can still appear for a
minute or two, while the network forgets the old connections (6 in this
run).

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
lab17-web-75f757df57-779g8 Running lab17-worker
lab17-web-75f757df57-88hqq Running lab17-worker
lab17-web-75f757df57-fb7gr Running lab17-worker
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
| Pods on `lab17-worker2` when you stopped it | |
| Time from `docker stop` to the node turning `NotReady` (s) | |
| Time from `NotReady` to the replacement pods running (s) | |
| Failed requests while the node was down, and for how many seconds | |
| Pods per node after the node came back, before and after the restart | |

> **Question:** Why does Kubernetes wait 50 seconds before it declares a
> node `NotReady` instead of reacting after the first missed heartbeat?
>
> **Hint:** Think of a node that is slow or on a congested network, and of
> what an eviction costs.
>
> **Question:** In this run one of the three pods was on the stopped node,
> so about one request in three failed. In your run the scheduler may have
> put two of them there. How would you make sure that losing one node
> never takes most of the replicas with it?
>
> **Hint:** Look at `topologySpreadConstraints` in `k8s/deployment.yaml`
> and what `whenUnsatisfiable: ScheduleAnyway` allows.
>
> **Question:** What would make the clients themselves stop failing during
> those 50 seconds?
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
real    0m5.019s
NAME        READY   UP-TO-DATE   AVAILABLE   AGE
lab17-web   6/6     6            6           2m51s
   3 lab17-worker
   3 lab17-worker2
```

Three new pods were serving in about 5 seconds, because the image was
already on both workers. `time` prints its result in a different format
in zsh, the default shell of macOS; the number is the same. Check that all six take traffic:

```bash
./scripts/traffic.sh 10
```

Expected output (summary):

```text
=== Summary: 66 requests in 10 s, 0 errors ===
By version:
    66 version=v1
By pod:
    12 host=lab17-web-65967f89fd-2gxfk
     6 host=lab17-web-65967f89fd-gj95j
    13 host=lab17-web-65967f89fd-qdmtk
    13 host=lab17-web-65967f89fd-rd299
     8 host=lab17-web-65967f89fd-vq868
    14 host=lab17-web-65967f89fd-xv5zm
```

The Service picked up the new pods without any change to it: it selects
pods by the label `app=lab17-web`, not by name. Scale back to three:

```bash
kubectl scale deployment/lab17-web --replicas=3
sleep 10
kubectl get pods -l app=lab17-web
```

Expected output:

```text
deployment.apps/lab17-web scaled
NAME                         READY   STATUS    RESTARTS   AGE
lab17-web-65967f89fd-2gxfk   1/1     Running   0          50s
lab17-web-65967f89fd-qdmtk   1/1     Running   0          55s
lab17-web-65967f89fd-xv5zm   1/1     Running   0          45s
```

The ReplicaSet removed the three newest pods and kept the ones that had
been running longest.

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
lab17-web-65967f89fd-2gxfk   1m           2Mi
lab17-web-65967f89fd-qdmtk   1m           1Mi
lab17-web-65967f89fd-xv5zm   1m           1Mi
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
lab17-web   Deployment/lab17-web   cpu: 78%/50%    3     8     3     15s
lab17-web   Deployment/lab17-web   cpu: 238%/50%   3     8     5     30s
lab17-web   Deployment/lab17-web   cpu: 402%/50%   3     8     8     45s
lab17-web   Deployment/lab17-web   cpu: 262%/50%   3     8     8     60s
lab17-web   Deployment/lab17-web   cpu: 230%/50%   3     8     8     75s
lab17-web   Deployment/lab17-web   cpu: 244%/50%   3     8     8     90s
```

The load pod reaches the Service by its name, `lab17-web`, through the
cluster DNS. Every 15 seconds the HPA computes the replicas it needs as
current replicas x measured utilization / target, and it adds pods in
steps: it went to 5, and 15 seconds later to the maximum of 8.
Utilization stays above 50 % because 8 is the ceiling. Read its
decisions:

```bash
kubectl describe hpa lab17-web | sed -n '/Events/,$p'
```

```text
Events:
  Type    Reason             Age   From                       Message
  ----    ------             ----  ----                       -------
  Normal  SuccessfulRescale  75s   horizontal-pod-autoscaler  New size: 5; reason: cpu resource utilization ...
  Normal  SuccessfulRescale  60s   horizontal-pod-autoscaler  New size: 8; reason: cpu resource utilization ...
```

Stop the load and remove the autoscaler before Task 8:

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

> **Question:** Scaling from 3 to 6 took about 5 seconds here. List two
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
...
#10 [build 3/5] COPY go.mod ./
#10 CACHED
#11 [build 4/5] COPY main.go ./
#11 CACHED
#12 [build 5/5] RUN CGO_ENABLED=0 go build -trimpath -ldflags "-s -w -X main.version=v2" -o /out/web .
#12 DONE 3.0s
...
The push refers to repository [localhost:5001/lab17-web]
2780920e5dbf: Layer already exists
52630fc75a18: Layer already exists
...
c440148646e2: Pushed
...
5ef0d3184855: Pushed
...
v2: digest: sha256:42d562b6218105c18f801472c3ce2e9339152b466449a8a161a0f5ae3ec321a9 size: 856
{"name":"lab17-web","tags":["v2","v1"]}
```

A changed build argument invalidates only the `RUN` that uses it, so
Docker reused the `COPY` layers and reran only the compile step, which
took 3 seconds. The push
uploaded two new blobs, among them the layer with the v2 binary; the
registry already had every other layer.

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
real    0m14.747s
deployment.apps/lab17-web annotated
```

Revision 1 is the first deployment and revision 2 the restart of Task 6.
When the traffic generator finishes:

```text
=== Summary: 309 requests in 45 s, 0 errors ===
By version:
   118 version=v1
   191 version=v2
By pod:
    33 host=lab17-web-65967f89fd-2gxfk
    58 host=lab17-web-65967f89fd-qdmtk
    27 host=lab17-web-65967f89fd-xv5zm
    80 host=lab17-web-7b885f5d4f-brbqx
    60 host=lab17-web-7b885f5d4f-wkq6n
    51 host=lab17-web-7b885f5d4f-z547k
```

Zero errors while every pod was replaced. For a few seconds both versions
answered at once: a rolling update means v1 and v2 must be able to run
side by side.

### Step 8.3: A broken release

Deploy `v3`, a tag that you never pushed, and give the rollout 30 seconds.
First start `./scripts/traffic.sh 50` in the second terminal, then run in
the first one:

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
lab17-web-5d5fdd6bf6-pmsdl   0/1     ErrImagePull   0          30s
lab17-web-7b885f5d4f-brbqx   1/1     Running        0          75s
lab17-web-7b885f5d4f-wkq6n   1/1     Running        0          65s
lab17-web-7b885f5d4f-z547k   1/1     Running        0          70s
NAME                   DESIRED   CURRENT   READY   AGE
lab17-web-5d5fdd6bf6   1         1         0       30s
lab17-web-65967f89fd   0         0         0       5m4s
lab17-web-75f757df57   0         0         0       7m25s
lab17-web-7b885f5d4f   3         3         3       75s
```

The rollout created one v3 pod (`maxSurge: 1`), which cannot pull its
image, and stopped there: with `maxUnavailable: 0` it may not remove a
v2 pod until a v3 pod is ready. The three v2 pods kept serving, and the
traffic generator reports **0 errors**:

```text
=== Summary: 349 requests in 50 s, 0 errors ===
By version:
   349 version=v2
```

The old ReplicaSets stay at 0 replicas: they are the revisions you can
roll back to.

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
real    0m0.125s
deployment.apps/lab17-web
REVISION  CHANGE-CAUSE
1         <none>
2         <none>
4         v3: image that was never pushed
5         v2: rolling update
```

The rollback took a fraction of a second: the v2 ReplicaSet still had its three
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
  t= 13s  sent=88    errors=0    last: version=v2 host=lab17-web-7b885f5d4f-wkq6n
  t= 14s  sent=93    errors=1    last: ERROR timeout (no answer within 1 s)
  t= 15s  sent=94    errors=2    last: ERROR timeout (no answer within 1 s)
  t= 17s  sent=95    errors=3    last: ERROR timeout (no answer within 1 s)
  t= 18s  sent=96    errors=4    last: ERROR timeout (no answer within 1 s)
  t= 19s  sent=97    errors=5    last: ERROR timeout (no answer within 1 s)
  t= 20s  sent=102   errors=5    last: version=v1 host=lab17-web-65967f89fd-n58pb
...
=== Summary: 236 requests in 40 s, 5 errors ===
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
Removed the Docker network kind.

Checking that nothing is left...
  nothing left

kubectl has no current context now that kind-lab17 is gone. To return to another cluster:
  kubectl config get-contexts
  kubectl config use-context <name>

Cleanup complete. The cluster, the containers, the lab images and the kind network are gone.
The pinned images stay in the local cache; remove them with './cleanup.sh --remove-images' if needed.
```

The script ends by checking that no `lab17` cluster, `lab17-*`
container or lab image is left; if it finds one, it lists it and exits
with an error. The pinned base images stay in the local cache, as in the
other labs, so a second run skips the downloads. To remove them too:

```bash
./cleanup.sh --remove-images
```

Docker refuses to remove an image that another container still uses (for
example `nginx` or `golang` from another lab); the script then shows
Docker's message, keeps that image and counts it in its last line.

Verify cleanup:

```bash
docker ps -a --filter name=lab17
docker images --format '{{.Repository}}:{{.Tag}}' | grep lab17 || echo "no lab17 images"
docker network ls --filter name=kind
kubectl config get-contexts kind-lab17
```

Expected output:

```text
CONTAINER ID   IMAGE     COMMAND   CREATED   STATUS    PORTS     NAMES
no lab17 images
NETWORK ID   NAME      DRIVER    SCOPE
CURRENT   NAME   CLUSTER   AUTHINFO   NAMESPACE
error: context kind-lab17 not found
```

No `lab17-*` container or image and no `kind` network
remain, and `kind delete cluster` also removed the `kind-lab17` context
from your kubeconfig. kubectl now has **no current context**, so its
commands fail until you choose one. If you work with another cluster,
list your contexts and switch back to it:

```bash
kubectl config get-contexts
kubectl config use-context <name>
```
