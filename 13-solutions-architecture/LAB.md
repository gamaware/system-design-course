# Lab 13: Solutions Architecture

> For the lab overview, architecture diagram, and key concepts, see [README.md](README.md).

## Choose Your Environment

This lab runs in a web browser. The default option needs no installation.

| Environment | What You Need | Setup |
| --- | --- | --- |
| **Option A: Published site** | A modern web browser | Open [Complete the diagram](https://hallowed-denim-9pax.here.now/) |
| **Option B: Local build** | bash, `curl`, Python 3.10+, internet for the first build | `./build.sh` in `arch-builder/` |

Both options serve the same site with the same 36 puzzles. The browser you play in keeps your
progress, so finish the deliverable in a single browser.

## How Scoring Works

Read this before Task 2, because the deliverable is a score.

| Event | Points per slot |
| --- | --- |
| Correct on the first submit | 10 |
| Correct on the second submit | 5 |
| Correct on the third submit or later | 2 |
| Each hint used on that slot | Halves the slot's points (never below 2) |
| Answer shown with **Show answers** | 0 |

The maximum is 10 points per slot (70 for Scenario 9, which has 7 slots). A **perfect** attempt
(every slot right on the first submit, no hints, no answers shown) adds a 20 % bonus. In Challenge
mode, finishing before the timer runs out adds another 10 %.

---

## Task 1: Open the Exercise

Open the site, switch it to English, and learn the controls before playing a graded scenario.

### Step 1.1: Open the site (Option A)

Open the published exercise:

```text
https://hallowed-denim-9pax.here.now/
```

The start screen shows the title, a **Cloud** picker, a **Mode** picker, and the list of scenarios
for the selected cloud.

### Step 1.2: Build the site locally (Option B)

Skip this step if you use the published site. From the repository root:

```bash
cd 13-solutions-architecture/arch-builder
./build.sh
```

The script validates the 36 puzzles, downloads the official icon packages (about 23 MB, only the
first time), verifies their SHA-256 checksums, and writes the site to `dist/`. Its messages are in
Spanish. Expected output (abbreviated):

```text
e01-aws.json: ok, dificultad medium (4)
...
e09-oci.json: ok, dificultad hard (7)
icons: descargando aws de https://d1.awsstatic.com/...
...
icons: <N> iconos en /path/to/13-solutions-architecture/arch-builder/dist/icons {...}
build: 36 puzzles {'aws': 9, 'azure': 9, 'gcp': 9, 'oci': 9}, <N> iconos -> /path/to/.../dist
build: listo, abre /path/to/13-solutions-architecture/arch-builder/dist/index.html
```

Open the site directly from disk, without a web server:

```bash
open dist/index.html        # macOS
xdg-open dist/index.html    # Linux
start dist/index.html       # Windows (Git Bash or PowerShell)
```

### Step 1.3: Switch to English

The site opens in Spanish. Click **English** in the top bar. The button changes to **Español**,
and every label in this guide now matches the screen. The browser remembers the choice.

### Step 1.4: Tour the start screen

On the start screen:

1. Under **Cloud**, pick **AWS**. Each cloud shows `9 scenarios`.
2. Under **Mode**, keep **Practice** ("With hints and retries"). **Challenge** adds a timer,
   removes hints, and allows a single submit.
3. Scroll to **Scenarios on AWS**. Each row shows the scenario number and title, its level,
   the number of slots, and your status (**New**, **Best: N of M**, or **Perfect**).
4. Click **How to play** to see the keyboard shortcuts, then close the dialog.

> **Question:** The site keeps your progress without an account or a server. Where is it stored,
> and what happens if you open the site in another browser?
>
> **Hint:** Look at the Architecture section of the README and at the Cleanup section.

---

## Task 2: Scenario 9 on AWS

Scenario 9 is the multi-Region pattern from the last class diagram of
[Lab 04](../04-dns-dig-bind9/README.md): DNS picks the Region, and the load balancer picks the
virtual machine. This is the graded scenario: play it on AWS first.

### Step 2.1: Open Scenario 9 on AWS

In **Scenarios on AWS**, click **Scenario 9 · DNS picks the region and the balancer picks the VM**,
or open it directly:

```text
https://hallowed-denim-9pax.here.now/#p=e09-aws
```

The line above the title reads `Scenario 9 · AWS`. The row on the start screen showed
`Hard · 7 slots`.

### Step 2.2: Read the scenario before touching the palette

Read, in this order:

1. The summary: a store sells to Mexico and Spain under a single domain from two Regions.
2. The **Requirements** list. Each numbered requirement describes one gap (slot) of the diagram.
3. The diagram and the numbered steps below it, which follow a request from the shopper to the
   virtual machines.

Click **Enlarge diagram** (or press `Z`) to see the diagram at full size. **Text description of
the diagram** describes the same diagram as a list, for screen readers.

### Step 2.3: Place the services

The **Services** palette holds every answer plus near-miss services that look right but fail one
word of a requirement. Place one service per slot in any of three ways:

- Drag a service tile onto a slot.
- Tap a tile, then tap a slot (or tap a slot, then a tile).
- With the keyboard: arrows move in the palette, `Enter` picks a tile, and a digit `1`-`9` drops it
  in that slot.

The status line at the bottom confirms each move, for example:

```text
You picked <service>. Now tap a slot.
```

To take a service back, tap its slot and then the palette, or focus the slot and press `Delete`.
**Clear** empties every slot that is not solved yet (after a confirmation), and **Undo** restores
them for 5 seconds.

### Step 2.4: Submit and read the verdict

Click **Submit** (or press `S`). If some slots are still empty, a dialog asks whether to
**Submit anyway** or **Keep playing**; empty slots count as wrong.

The status line shows the verdict. Expected output after a first submit with two mistakes:

```text
5 of 7 slots right, 50 of 70 points. First try.
```

Correct slots lock with their points. The side panel opens on the first wrong slot
(`Slot N: Wrong`) and explains **Why not** the service you picked. Then choose:

- **Try again** clears the wrong slots for another submit, which pays 5 points per slot (then 2).
- **Show answers** fills the remaining slots with 0 points and ends the attempt.

### Step 2.5: Use hints only when stuck

Before submitting, focus a slot and click **Hint for slot N** (or press `H`). Hints have three
levels:

1. Highlights the deciding words of the requirement and names the service category.
2. Fades half of the wrong services in the palette.
3. Leaves only two candidates.

Each level halves the points of that slot and rules out the perfect bonus. Hints exist only in
Practice mode.

### Step 2.6: Capture your score

The attempt ends when you solve every slot or click **Show answers**. Take the screenshot described
in the [Deliverable](#deliverable) section now, while the status line still shows your score.

### Step 2.7: Review the architecture

1. Click any slot to read **Why** its service is right, **The deciding words:** of the requirement,
   and the **Official documentation** links.
2. Click **Review the architecture**, then **Walk through the steps** and **Next step** to follow a
   purchase through the finished diagram. During the review the status line shows each step
   instead of the score. Click **Close the review** when you finish.

> **Question:** Slot 2 and the load balancers both run health checks. Who probes whom in each case,
> and from where? Which failure does each one detect?
>
> **Hint:** Compare a whole Region going down with a single virtual machine failing behind its
> balancer. Lab 04's "DNS round robin vs load balancer" diagram shows the second case.
>
> **Question:** Requirement 1 asks for a 60 s TTL. If Region A fails, will every shopper reach
> Region B within 60 seconds?
>
> **Hint:** Add up the time to detect the failure, the TTL, the DNS caches of resolvers and
> browsers, and the time to reconnect.

---

## Task 3: Scenario 9 on Another Cloud

The four clouds share the same topology for every scenario: same slots, nodes, and arrows. In this
task you solve Scenario 9 again on a second provider and compare.

### Step 3.1: Switch clouds from the scenario

In the top bar of Scenario 9, the cloud links (**AWS**, **Azure**, **Google Cloud**,
**Oracle Cloud**) open the same scenario on another provider. Pick one. The heading changes to,
for example, `Scenario 9 · Azure`.

Read the requirements again instead of assuming they are identical: a cloud can word a
requirement differently so that its answer stays unique and documented.

### Step 3.2: Solve it

Play the scenario as in Task 2. This attempt is not graded, so use hints freely if you need them.

### Step 3.3: Compare the two solutions

Copy this table into your notes and fill it in from the finished diagrams:

| Slot | What the requirement asks for | AWS service | Second cloud service |
| --- | --- | --- | --- |
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |
| 5 | | | |
| 6 | | | |
| 7 | | | |

> **Question:** On your second cloud, is every slot a separate service, or is one of them a feature
> of another service? How would that change the way you operate it?
>
> **Hint:** Read the **Why** panel of slots 1 and 2 on both clouds.
>
> **Question:** The two Regions are different on each cloud (for example, Mexico and Spain). Why
> does the scenario name concrete Regions instead of "Region A" and "Region B" only?
>
> **Hint:** A design must use services and features that exist in the Regions it runs in.

---

## Task 4: Scenarios by Topic

Every scenario reviews topics from earlier modules. Pick scenarios that match labs you have done,
and try Challenge mode on at least one.

### Step 4.1: Choose your scenarios

| Scenario | Title | Topics | Related modules |
| --- | --- | --- | --- |
| 1 | A private network with controlled egress | Private subnets, NAT, egress filtering, bastion access, flow logs | 07, 08 |
| 2 | A store that survives Buen Fin | Compute, auto scaling, L7 load balancing, TLS, monitoring | 02, 03 |
| 3 | Video courses for 300,000 students | CDN, caching, storage classes, public DNS, web firewall | 04, 09, 11 |
| 4 | An animation studio that renders at night | NFS vs object storage, backup vs replica, interruptible compute, VPN | 09 |
| 5 | Scholarship payments | OAuth 2.0 and OIDC, JWT, encryption keys, threat detection, audit | 06 |
| 6 | Reservations in two countries | Relational HA, read replicas, multi-Region NoSQL and CAP, secrets | 10 |
| 7 | World Cup 2026 betting pool | L7 load balancing, serverless containers, cache, queue, NoSQL | 03, 11, 17 |
| 8 | A parcel service that never loses an order | Publish/subscribe, queues, at-least-once delivery, DLQ, streaming | 14 |
| 9 | DNS picks the region and the balancer picks the VM | DNS, load balancing, auto scaling, multi-Region HA | 03, 04 |

Play at least two scenarios besides Scenario 9, on any cloud. Use **Scenarios** in the top bar to
jump between them, or press `N` and `P` for the next and previous scenario.

### Step 4.2: Play one scenario in Challenge mode

Go back with **All scenarios**, select **Challenge** under **Mode**, and open a scenario. You can
also add `&mode=challenge` to a scenario link:

```text
https://hallowed-denim-9pax.here.now/#p=e02-aws&mode=challenge
```

The top bar shows a **Challenge** tag and a countdown. The budget is 30 seconds of reading plus 40
seconds per slot. For a 5-slot scenario:

```text
3:50 left
```

Challenge mode has no hints and a single submit: the site reveals unsolved slots with 0 points.
When time runs out, it submits the services already in place. Finishing in time adds 10 % to the score, and
the verdict line includes the time, for example `Time 2:41 of 3:50. +5 for time.`

To practice against the clock with hints, check **Show a timer in practice** on the start screen
instead.

> **Question:** In the scenario you played, which slot had the most convincing near miss? Which
> words of the requirement ruled it out?
>
> **Hint:** After the attempt ends, each slot's panel shows **The deciding words:** highlighted.

---

## Task 5: Cross-Cloud Equivalences

Reflect on what "the same architecture on another cloud" really means. Use
[ARCHITECTURES.md](ARCHITECTURES.md), the design document of the exercise. The document is in
Spanish and lists every answer, so open it only after playing.

### Step 5.1: Complete the equivalence table for Scenario 9

Extend your table from Task 3 to the four clouds. Play the two remaining clouds of Scenario 9, or
read the Scenario 9 table in `ARCHITECTURES.md` ("Escenario 9"), whose columns are the requirement
(*requisito*), the service per cloud, the distractor per cloud (*distractor por nube*), and the
sources (*fuentes*).

### Step 5.2: Read the notes on equivalences

Each scenario in `ARCHITECTURES.md` ends with an **Equivalencias** list that explains where a cloud
differs. The last section, **Equivalencias dudosas** (questionable equivalences), groups the hard
cases:

| Section | Meaning |
| --- | --- |
| Sin equivalente limpio | No clean equivalent: the cloud needs another service, extra code, or a different design |
| No verificado | Not verified: a detail the official documentation does not state, so the puzzles do not claim it |
| Evitados por retiro | Avoided because the provider is retiring the service |

### Step 5.3: Reflect

Answer these questions in a few sentences each.

> **Question:** Pick one entry from "Sin equivalente limpio". What does the design lose or gain on
> that cloud, and would you still choose that cloud for the scenario?
>
> **Hint:** Consider operational effort (extra functions or glue code), cost, and whether the
> requirement is still met exactly.
>
> **Question:** Some services exist on a cloud but not in its Mexico Region. Why is regional
> availability a requirement and not a detail?
>
> **Hint:** Think about data residency, latency to users, and what happens to the design if the
> service runs in a Region far from the rest of the system.
>
> **Question:** A one-to-one service mapping between clouds is a common shortcut during a
> migration. Based on Scenario 9 and one other scenario, when is that shortcut safe and when is it
> misleading?
>
> **Hint:** Compare a slot where the four answers behave the same with one where a service lives
> inside another, or needs extra pieces.

---

## Deliverable

Submit one screenshot of **Scenario 9 on AWS** after the attempt ends (every slot solved, or the
answers shown). The screenshot must show:

1. The line `Scenario 9 · AWS` and the scenario title above the requirements.
2. The finished diagram with every slot filled.
3. The status line at the bottom with your score, for example:

```text
7 of 7 slots right, 60 of 70 points.
```

A perfect attempt reads `7 of 7 slots right, 70 of 70 points. Perfect: +14 bonus.` The top bar
also shows your best score for the scenario (`Best: N of 70`).

Take the screenshot before you click **Play again**, **Next scenario**, or **All scenarios**: a new
attempt replaces the status line. Close **Review the architecture** first if it is open, because
the review shows its steps in the status line instead of the score.

---

## Cleanup

This lab creates no cloud resources or containers. If you built the site locally (Option B):

```bash
cd 13-solutions-architecture/arch-builder
rm -rf dist .cache
```

To reset your progress, clear the site data for the exercise in your browser settings.
