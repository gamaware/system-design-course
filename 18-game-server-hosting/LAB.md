# Lab 18: Game Server Hosting

> For the lab overview, architecture diagram, and key concepts, see
> [README.md](README.md).

## How the Class Runs

This lab runs live, with the whole group connected to the same arena:

1. The instructor presents the architecture and shows the two EKS clusters running.
2. The instructor publishes two things in Canvas: the **frontend address** (a Global Accelerator host name)
   and a **certificate bundle** for the game client.
3. Every student starts the game container on their laptop and searches for a match. Open Match groups
   **four players** with a similar latency into one race.
4. During the races, the instructor projects the cluster from the terminal, deletes a game server and scales
   a Fleet so that you can see the effect from both sides.
5. The class closes with the design questions of Task 5.

Work alone on your laptop, but talk to the classmates in your race: some observations compare what each
player saw.

The certificate bundle lets your client verify that it is talking to the matchmaker of this class (the CA
certificate). Your client also sends its own key pair, but the Frontend does not check it: Task 5 asks you
what that means. Do not share the bundle outside the class or upload it anywhere.

## Prerequisites

- **Docker Desktop** installed and running (macOS or Windows), or Docker Engine on Linux
- A modern web browser
- Free local port **8080**
- About 2 GB of free disk for the image
- A network that allows outbound TCP to port 50504 and outbound UDP. If the campus network blocks one of them,
  connect to a phone hotspot

You do not need an AWS account, kubectl or the SuperTuxKart game installed: the image includes the game and
shows it in your browser.

---

## Task 1: Prepare Your Laptop

Do this task before the class, or at the start of it, so that the image download does not compete with the
rest of the group.

### Step 1.1: Check Docker and the port

```bash
docker version --format '{{.Server.Version}}'
docker run --rm hello-world | head -2
```

Expected output (your version may differ):

```text
29.9.2

Hello from Docker!
```

Check that nothing listens on port 8080. On macOS or Linux:

```bash
lsof -nP -iTCP:8080 -sTCP:LISTEN || echo "port 8080 is free"
```

On Windows (PowerShell):

```powershell
Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue
```

No output on Windows, or `port 8080 is free` on macOS and Linux, means you can use the port. If another
program uses it, see [Troubleshooting](README.md#troubleshooting).

### Step 1.2: Pull the image

```bash
docker pull joalgama32179/scalers-kart:1.0
```

The image works on Apple silicon and on Intel or AMD laptops. It contains the matchmaking client, the
SuperTuxKart game and a small web interface. It contains no certificates and no addresses: you provide both
when you start it.

> **Question:** Why is it a good idea that the public image contains no certificate or address, even though
> that makes the `docker run` command longer?
>
> **Hint:** Think about who can download a public image, and what happens next semester when the arena runs
> in a new account with new certificates.

### Step 1.3: Place the certificate bundle

Create a working folder, then download the bundle from Canvas and extract **every file** into a subfolder
named `certs`:

```bash
mkdir -p ~/scalers-kart/certs
cd ~/scalers-kart
ls certs
```

The `ls` command must list the certificate files of the bundle: a CA certificate (`ca.crt` or
`publicCA.cert`) and a client certificate with its key. Keep the original file names.

---

## Task 2: Join the Arena

### Step 2.1: Start the container

From the folder that contains `certs`, run the container with the frontend address from Canvas. Replace
`<frontend-address>` with that host name and keep `:50504` at the end.

macOS, Linux, WSL or Git Bash:

```bash
docker run --rm -p 127.0.0.1:8080:8080 -v "$PWD/certs:/certs:ro" \
  -e FRONTEND=<frontend-address>:50504 joalgama32179/scalers-kart:1.0
```

Windows PowerShell:

```powershell
docker run --rm -p 127.0.0.1:8080:8080 -v "${PWD}/certs:/certs:ro" `
  -e FRONTEND=<frontend-address>:50504 joalgama32179/scalers-kart:1.0
```

Each part of the command has a purpose:

| Part | Purpose |
| --- | --- |
| `--rm` | Deletes the container when it stops |
| `-p 127.0.0.1:8080:8080` | Publishes the web interface on your laptop only, never on the campus network |
| `-v "$PWD/certs:/certs:ro"` | Mounts the bundle read-only inside the container |
| `-e FRONTEND=...` | Tells the client where the Open Match Frontend is |

Leave this terminal open. Its log shows each step of the matchmaking; you stop the container with `Ctrl+C`.

### Step 2.2: Open the arena

Open <http://localhost:8080>. The page checks your configuration first: if a certificate or the address is
missing, it says which one. Choose a nickname and your team (Scalers 1 to 8), keep **Valores de la clase**
for the latency, then start the search. With the class values every student sends the same latency, so the
whole group lands in one pool and races fill faster.

### Step 2.3: Read the matchmaking timeline

The page shows a timeline with one row per stage (the labels are the ones on screen), and each row turns
active and then done:

| Stage | What happens in the architecture |
| --- | --- |
| Ticket creado | Your client attached its latency to each Region and created a ticket in the Open Match Frontend |
| En el pool | The ticket waits in a pool until the Match Function finds three more players with a similar latency |
| Match formado | The Director fetched a match that contains your ticket |
| Servidor asignado por Agones | Agones allocated a game server and the Director wrote its address in your ticket |
| Conectando | SuperTuxKart connects over UDP to that server through Global Accelerator |
| ¡A correr! | The race runs; the game appears on the page. The player with the crown in the lobby presses **Start race** |

Write down three values that the page shows: your **ticket ID**, the **assignment** (the address and port
of your game server) once it arrives, and your **measured latency** to `us-east-1` and to `us-east-2`
(switch the latency control to **Mi medición** to see it; the ticket itself carries the class preset).

> **Question:** Your client sends its own latency in the ticket. What could a dishonest player gain by
> sending a false latency, and where in the architecture would you check it?
>
> **Hint:** Compare the reported value with what a server in each Region could measure itself, for example
> with the Agones latency ping service.

---

## Task 3: Race and Measure

Play at least **two races**. Before each race, note the time when you press search, and fill one row of the
table when the race ends.

### Step 3.1: Time the matchmaking

Use the timestamps of the timeline, or a stopwatch, to measure:

- **Ticket to match**: from the moment the client creates the ticket to the moment the assignment arrives
- **Match to race**: from the assignment to the start of the race

### Step 3.2: Find your Region and server

The assignment shows the custom routing address and port of your server, not its private IP. Ask the other
three players of your race for their assignment: all four must be identical. The instructor projects the
allocated GameServers of each cluster; find yours by the time of the allocation and note its **Region** and
**GameServer name**.

### Step 3.3: Feel the lag

While racing, watch for delays between your input and the kart, karts that jump, or a game that freezes.
Rate the lag from 1 (none) to 5 (unplayable), and compare with your measured latency to the Region of your server.

### Step 3.4: Fill the observation table

Copy this table into your report and fill one row per race:

| Race | Ticket to match (s) | Match to race (s) | Measured latency us-east-1 (ms) | Measured latency us-east-2 (ms) | Region of your server | GameServer name | Lag (1-5) | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | | | | | | | | |
| 2 | | | | | | | | |
| 3 | | | | | | | | |

> **Question:** Did the matchmaker send your race to the Region with the lowest latency for you? If not,
> why could that still be the right decision for the group?
>
> **Hint:** The Match Function builds a match for four players at once, and the Director asks for a server
> in the Region of the latency band that formed the match.
>
> **Question:** Ticket to match took longer when fewer students were searching. Which two parameters of
> the Match Function would you change to shorten the wait, and what would the players lose?
>
> **Hint:** Look at the number of players per match and the width of the latency ranges.

---

## Task 4: Failure and Scale

The instructor runs these steps on cluster 1 and projects the terminal. You observe from your laptop and
from the projection.

### Step 4.1: Watch the GameServers

The instructor leaves this command running in a visible terminal:

```bash
kubectl get gameservers -n gameservers -w
```

Illustrative output (names, addresses and ages change in every deployment):

```text
NAME                       STATE       ADDRESS       PORT   NODE                          AGE
supertuxkart-x7k2p-4fz9q   Allocated   10.1.x.x      7012   ip-10-1-x-x.ec2.internal      6m
supertuxkart-x7k2p-9ldwn   Ready       10.1.x.x      7020   ip-10-1-x-x.ec2.internal      6m
supertuxkart-pool2-b8cm5   Ready       10.1.x.x      7003   ip-10-1-x-x.ec2.internal      6m
```

Every new race turns one `Ready` server into `Allocated`. When the last player of a race disconnects, the
server calls the Agones SDK `Shutdown()` and you see a new server go through `Scheduled`, `RequestReady` and
`Ready`. Players who stay in the lobby keep their server `Allocated`.

### Step 4.2: Delete a game server in the middle of a race

During a race, the instructor deletes the Pod of one `Allocated` GameServer:

```bash
kubectl delete pod -n gameservers <allocated-gameserver-pod>
```

If you were in that race, write down what you saw and how long it took you to notice. Everyone writes down
what the projection showed: the state of the deleted GameServer and how long the Fleet took to have a new
`Ready` server.

> **Question:** The platform replaced the server in seconds, yet the four players lost their race. Why
> does Kubernetes self-healing not save the match?
>
> **Hint:** Where does the state of the race live: in a database, in the client, or in the memory of the
> server process?
>
> **Question:** What would the system need so that a race survives the loss of its server?
>
> **Hint:** Think about checkpoints of the game state, reconnection to a new server and the cost of both for
> a race of a few minutes.

### Step 4.3: Scale a Fleet

The guidance runs each Fleet with a fixed number of replicas. The instructor scales one Fleet by hand, and
shows the Agones resource that does it automatically, a `FleetAutoscaler` with a buffer policy:

```bash
kubectl get fleets -n gameservers
kubectl scale fleet supertuxkart -n gameservers --replicas=6
```

```yaml
apiVersion: autoscaling.agones.dev/v1
kind: FleetAutoscaler
metadata:
  name: supertuxkart-autoscaler
  namespace: gameservers
spec:
  fleetName: supertuxkart
  policy:
    type: Buffer
    buffer:
      bufferSize: 2      # always keep 2 Ready servers waiting for the next matches
      minReplicas: 2
      maxReplicas: 10
```

Write down how many seconds the new servers took to reach `Ready`.

> **Question:** A HorizontalPodAutoscaler in Lab 17 scaled on CPU. Why does a game Fleet scale on the number
> of `Ready` servers instead?
>
> **Hint:** A `Ready` server uses almost no CPU, and a player who finds no `Ready` server waits for the whole
> start time of a new one.

---

## Task 5: Design Questions

Answer each question in three to six sentences, using what you observed. The class discusses them at the end
of the session.

### Step 5.1: Load balancing and proxies

> **Question:** The matchmaking calls go through a Network Load Balancer, while the game traffic goes
> through custom routing to one exact server. Why can the second path not use a load balancer that picks any
> healthy target, as HAProxy did in Lab 03?
>
> **Hint:** Compare a stateless HTTP request with a UDP race whose state lives in one process.
>
> **Question:** The client talks directly to the Open Match Frontend. Production games put a **game
> frontend** in front of it. Which responsibilities of the proxies and gateways of Lab 12 would that service
> take?
>
> **Hint:** Authentication, rate limiting, hiding internal services, and one place to change the protocol.

### Step 5.2: DNS, Global Accelerator and multi-Region

> **Question:** Lab 04 routed users to a Region with DNS. What does Global Accelerator add for a game, given
> that resolvers cache DNS answers and the game needs a stable low-latency path?
>
> **Hint:** Static anycast IP addresses, the AWS backbone after the nearest edge location, and failover that
> does not wait for a DNS TTL.
>
> **Question:** Cluster 2 can host races, but Open Match and the Director run only in cluster 1. What
> happens to running races and to new matches if `us-east-1` fails? How would you remove that single point
> of failure?
>
> **Hint:** Separate the data plane (the races) from the control plane (matchmaking and allocation).

### Step 5.3: Containers, Kubernetes and horizontal scaling

> **Question:** Lab 17 used a Deployment. Why does Agones define its own `GameServer` and `Fleet` resources
> instead of running SuperTuxKart in a Deployment?
>
> **Hint:** Think about a rolling update or a scale-down that picks a Pod with a race in progress.
>
> **Question:** Each SuperTuxKart server here requests 20m of CPU and 64 MiB of memory. Estimate how many
> races one node with 2 vCPU and 8 GiB could host, and name the resource that limits you first.
>
> **Hint:** Kubernetes schedules on requests, and the node also runs system Pods.

### Step 5.4: Queues, caching and state

> **Question:** In what ways does an Open Match ticket behave like a message in the queues of Lab 14, and in
> what ways does it not?
>
> **Hint:** Who consumes it, in what order, and what happens to a ticket that nobody matches.
>
> **Question:** Open Match keeps the tickets in Redis, the cache of Lab 11. Why does in-memory storage fit
> tickets, and what would players notice if Redis restarted?
>
> **Hint:** How long a ticket lives, and whether losing one costs more than asking the player to search again.

### Step 5.5: Observability, security and cost

> **Question:** Name three metrics you would put on a dashboard for this arena, and the alarm you would set
> on each.
>
> **Hint:** Time from ticket to match, number of `Ready` servers per Region, and failed allocations.
>
> **Question:** The Director and the Agones allocators authenticate each other with mutual TLS, but the
> Open Match Frontend accepts any client that reaches port 50504, certificate or not. What could an
> attacker on the internet do with that, and what would you put in front of the Frontend to stop it?
>
> **Hint:** Flooding the pools with fake tickets delays every real match. Think of the game frontend and
> API gateway pattern from the proxies lab, and of the authentication you used in the Keycloak lab.
>
> **Question:** Two EKS control planes, the node groups, three accelerators and the load balancers cost money
> every hour, even with no players. Which parts would you turn off between classes, and which managed
> service would you evaluate instead for a small game?
>
> **Hint:** Compare the fixed hourly cost with the cost per player hour, and look at Amazon GameLift.

---

## Deliverable

Submit one PDF named `ApellidoPaterno_ApellidoMaterno_Lab18.pdf` with:

1. The **observation table** of Step 3.4, with at least two races.
2. A **screenshot of the matchmaking timeline** at the moment the assignment arrives, showing your ticket ID
   and the assignment.
3. A **screenshot of a race** in progress in your browser.
4. Your notes from **Task 4**: what you saw when the instructor deleted a game server, and how long the Fleet
   took to recover.
5. Your answers to the **design questions** of Task 5, three to six sentences each.

If your network did not let you play, write which step failed and the error the page showed, and answer
Tasks 4 and 5 from the projection and the discussion.

---

## Cleanup

Stop the container with `Ctrl+C` in its terminal. Because of `--rm`, Docker deletes it. Then remove the image
and the certificate bundle:

```bash
docker rmi joalgama32179/scalers-kart:1.0
rm -rf ~/scalers-kart
```

Verify that nothing remains:

```bash
docker ps -a --filter ancestor=joalgama32179/scalers-kart:1.0
docker images joalgama32179/scalers-kart
```

Expected output: both commands print only their header line.

```text
CONTAINER ID   IMAGE     COMMAND   CREATED   STATUS    PORTS     NAMES
REPOSITORY   TAG       IMAGE ID   CREATED   SIZE
```

---

## Instructor Notes

The arena is the AWS guidance
[Game Server Hosting on Amazon EKS with Agones and Open Match](https://github.com/aws-solutions-library-samples/guidance-for-game-server-hosting-using-agones-and-open-match-on-amazon-eks),
deployed in two Regions:

1. Deploy the clusters, the in-cluster components and the extra-cluster resources (VPC peering, ECR,
   Global Accelerator) with the three Terraform stages of the guidance README, in order.
2. Deploy the SuperTuxKart Fleets, the Match Function and the Director as the guidance describes in its
   SuperTuxKart section.
3. Issue a client certificate for the game client from the cluster's cert-manager CA, and share in Canvas
   only that client certificate, its key and the CA certificate. Never share the private key of the
   Frontend server certificate.
4. Share the `global_accelerator_address` output in Canvas as the frontend address.
5. After class, follow the **Clean Up Resources** section of the guidance to destroy both clusters, the
   accelerators and the VPC peering, and check that no load balancer or security group remains.

This repository never stores AWS account IDs, Global Accelerator addresses, certificates or keys. They change
in every deployment and belong in Canvas for the day of the class only.
