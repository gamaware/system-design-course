# Animated diagrams

Each lab README shows its draw.io diagrams as animated SVGs. The arrows of the flow draw themselves
in step order while a glowing dot travels along them, the numbered badge of the step pulses, its row
in the legend lights up, and the box the arrow reaches glows. After the last step the full diagram
holds for a few seconds and the loop starts again.

The animation is plain CSS inside the SVG, with no script and no external file. GitHub shows
repository images through an `<img>` tag, which plays CSS animation and blocks scripts, so the
diagram animates on github.com and in any browser. Readers who turn on reduced motion in their
system settings see the static diagram.

## Render

```bash
shared/diagram-motion/render.sh                                   # every diagram in flows.json
shared/diagram-motion/render.sh 03-load-balancing-haproxy/diagrams/lab03-haproxy-load-balancing.drawio
```

`render.sh` exports the `.drawio` to SVG with the draw.io desktop CLI and then runs `animate.py`,
which adds the motion layer and writes `labNN-<name>.svg` next to the source. Run it again after
every change to a `.drawio`, together with the PNG export described in
[docs/DIAGRAMS.md](../../docs/DIAGRAMS.md).

Requirements: draw.io desktop and Python 3.13. `animate.py` uses only the standard library.

## Step order

`flows.json` lists the steps of each diagram, keyed by the path of its `.drawio`:

```json
{
  "03-load-balancing-haproxy/diagrams/lab03-haproxy-load-balancing.drawio": {
    "steps": [
      { "badge": "step-1", "edges": ["edge-client-haproxy"] },
      { "badge": "step-2", "edges": ["edge-haproxy-web1", "edge-haproxy-web2", "edge-haproxy-web3"] },
      { "badge": "step-6", "glow": ["grp-haproxy"] }
    ]
  }
}
```

| Field   | Meaning                                                                                      |
|---------|----------------------------------------------------------------------------------------------|
| `edges` | Ids of the draw.io arrows that draw in this step. Several ids draw at the same time.         |
| `badge` | Id of the numbered badge to pulse. Its legend row is the set of `step-N-…legend` cells.      |
| `glow`  | Ids of boxes to light up in a step that has no arrow.                                        |

Arrows that no step lists stay static. A diagram missing from `flows.json` animates its arrows one
by one in the order draw.io stores them.

## Size

Every text label in a draw.io SVG export carries a PNG copy for viewers that cannot render HTML
labels. `animate.py` drops those copies, which are about 90% of the file, so an animated diagram
weighs 60 to 200 KB, far below the 1024 KB limit of the pre-commit hook.
