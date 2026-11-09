# Lab 18: Game Server Hosting

> For the lab overview, architecture diagram, and key concepts, see
> [README.md](README.md).

## How the Class Runs

This lab runs live over two class sessions, with the whole group connected to the same arena. Nothing
happens before class: you pull and start the client in the classroom.

### First Session: Architecture and Setup

1. The instructor presents the architecture of the arena, and the class discusses it.
2. The instructor confirms in class the **tag** of the **class image**, the client image built for the
   current deployment, which is also published in Canvas. Each deployment gets its own tag.
3. In class, every student pulls the class image, starts the game container on their laptop with one command
   and checks that the client starts (Task 1, then Task 2 up to the configuration check of Step 2.2).

### Second Session: Race and Design

1. The instructor confirms the tag in class. If it changed, use the new tag in the commands of Task 1 and
   Task 2 before the races.
2. The whole group searches for a match at the same time. Open Match groups **four players** with a similar
   latency into one race.
3. During the races, the instructor projects the cluster from the terminal, deletes a game server and scales
   a Fleet so that you can see the effect from both sides.
4. The class closes with the design questions of Task 5.

Work alone on your laptop, but talk to the classmates in your race: some observations compare what each
player saw.

The class image carries three things, all of them public: the CA certificate of the Open Match server, the
frontend address, and the static IP addresses of the accelerators. The CA certificate lets your client verify
that it talks to the matchmaker of this class. You receive no certificate of your own: the Frontend does not
ask for one, and Task 5 asks you what that means.

## Prerequisites

- **Docker Desktop** installed and running (macOS or Windows), or Docker Engine on Linux
- A modern web browser
- Free local port **8080**
- About 2 GB of free disk for the image
- The **image tag** of the class, published in Canvas
- A network that allows outbound TCP to port 50504 and outbound UDP. If the campus network blocks one of them,
  connect to a phone hotspot

You do not need an AWS account, kubectl or the SuperTuxKart game installed: the image includes the game and
shows it in your browser.

---

## Task 1: Prepare Your Laptop

Do this task in class during the first session, after the instructor confirms the tag.

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

### Step 1.2: Pull the class image

In class, replace `<tag>` with the tag that the instructor confirms (also published in Canvas):

```bash
docker pull joalgama32179/scalers-kart:<tag>
```

The image works on Apple silicon and on Intel or AMD laptops. It contains the matchmaking client, the
SuperTuxKart game and a small web interface, plus the public data of the current deployment: the CA certificate
of the Open Match server, the frontend address and the static IP addresses of the accelerators. It contains no
private key and no credential.

> **Question:** The class image is public on Docker Hub and contains the CA certificate and the addresses of
> the arena. Why is it safe to publish them, and why does every deployment get a new tag instead of reusing
> the same one?
>
> **Hint:** Think about what a CA certificate proves and who holds the matching private key, and about a
> laptop that still has last week's image in its cache.

---

## Task 2: Join the Arena

### Step 2.1: Start the container

Run the class image with the tag from Canvas. The same command works in macOS, Linux, WSL, Git Bash and
Windows PowerShell:

```bash
docker run --rm -p 127.0.0.1:8080:8080 joalgama32179/scalers-kart:<tag>
```

Each part of the command has a purpose:

| Part | Purpose |
| --- | --- |
| `--rm` | Deletes the container when it stops |
| `-p 127.0.0.1:8080:8080` | Publishes the web interface on your laptop only, never on the campus network |
| `joalgama32179/scalers-kart:<tag>` | The class image of the current deployment, with the frontend address and the CA certificate inside |

Leave this terminal open. Its log shows each step of the matchmaking; you stop the container with `Ctrl+C`.

### Step 2.2: Open the arena

Open <http://localhost:8080>. The page checks your configuration first: if you started a tag without class
data, it says **Falta configuración**.

> **First session:** stop here. If the page opens without **Falta configuración**, the client starts on your
> laptop. Stop the container with `Ctrl+C`; you search for a match in the second session.

Choose a nickname and your team (Scalers 1 to 8), keep **Valores de la clase** for the latency, then press
**Buscar partida**. With the class values every student sends the same latency, so the whole group lands in
one pool and races fill faster.

The game has sound. It starts with the **Buscar partida** click, because browsers play audio only after a
click; the **Sonido** button mutes it and turns it back on.

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
| ¡A correr! | The race runs; the game appears on the page. The player with the crown in the lobby presses **Empezar carrera** |

When the track appears, click it so that the keyboard goes to the game. Drive with the arrow keys; `Space`
uses an item, `N` fires the nitro and `V` drifts.

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

Play at least **one race** (more if there is time). Before each race, note the time when you press search,
and fill one row of the table when the race ends.

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
of the second session.

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
> **Question:** You joined the arena without any certificate of your own, and the Frontend still accepted
> your tickets: it uses server-only TLS, while the Director and the Agones allocators authenticate each other
> with mutual TLS. Anyone who reaches port 50504 can do what you did. What could an attacker on the internet
> do with that, and what would you put in front of the Frontend to authenticate players?
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

There is no written submission in Canvas: the activity is graded by attendance and participation in class.
Keep these as notes for the discussion of Task 5:

1. The **observation table** of Step 3.4, with at least one race.
2. A **screenshot of the matchmaking timeline** at the moment the assignment arrives, showing your ticket ID
   and the assignment.
3. A **screenshot of a race** in progress in your browser.
4. Your notes from **Task 4**: what you saw when the instructor deleted a game server, and how long the Fleet
   took to recover.
5. Your answers to the **design questions** of Task 5, three to six sentences each.

If your network did not let you play, write which step failed and the error the page showed, and follow
Tasks 4 and 5 from the projection and the discussion.

---

## Cleanup

Stop the container with `Ctrl+C` in its terminal. Because of `--rm`, Docker deletes it. Then remove every tag of
the image you downloaded (each session can use a different tag):

```bash
docker rmi $(docker images joalgama32179/scalers-kart -q | sort -u)
```

Verify that nothing remains:

```bash
docker ps -a --filter ancestor=joalgama32179/scalers-kart
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
deployed in two Regions.

> **Cost:** the arena bills by the hour even with no players (two EKS control planes, about 18 nodes, NAT
> gateways, three accelerators and load balancers), on the order of a few US dollars per hour. Deploy it the
> morning of each session that needs it and destroy it the same day; every new deployment needs its own class
> image and tag.

1. Deploy the clusters, the in-cluster components and the extra-cluster resources (VPC peering, ECR,
   Global Accelerator) with the three Terraform stages of the guidance README, in order.
2. Deploy the SuperTuxKart Fleets, the Match Function and the Director as the guidance describes in its
   SuperTuxKart section.
3. Build the class image for this deployment. The instructor builds it outside this repository, from the
   source of the game client: the build reads the CA certificate of the Open Match server from the cluster,
   and the frontend address and the static IP addresses of the three accelerators from the AWS API. It
   checks a TLS 1.3 connection to the Frontend without a client certificate, then pushes the image to Docker
   Hub for `amd64` and `arm64`. Use a new tag for every deployment, never `latest`, and never put a private
   key in the image.
4. Publish the tag in Canvas, and run four clients against the arena to confirm that a race starts. Students
   need only that tag.
5. After class, follow the **Clean Up Resources** section of the guidance to destroy both clusters, the
   accelerators and the VPC peering, and check that no load balancer or security group remains.

This repository never stores AWS account IDs, Global Accelerator addresses, certificates or keys. They change
in every deployment and reach students only inside the class image whose tag the instructor publishes in Canvas.
