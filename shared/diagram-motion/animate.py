#!/usr/bin/env python3
"""Turn a draw.io diagram into an animated SVG that GitHub renders inline.

The draw.io desktop CLI exports the diagram to SVG. This script then adds a motion layer made only of CSS
keyframes, with no script and no external file, because GitHub serves repository images through an
<img> tag that runs CSS animation but blocks JavaScript. The diagram stays the same: every arrow of the
flow draws itself in step order while a glowing dot travels along it, the step badge pulses, the step
row of the legend lights up, and the box the arrow reaches glows. The loop holds the full diagram for a
few seconds before it starts again, and readers who ask for reduced motion get the static diagram.

Run it through render.sh, which exports the SVG first:
    shared/diagram-motion/render.sh 03-load-balancing-haproxy/diagrams/lab03-haproxy-load-balancing.drawio
    shared/diagram-motion/render.sh            # every diagram listed in flows.json

The step order of each diagram lives in flows.json next to this script. A diagram without an entry
animates its arrows in the order draw.io stores them.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLOWS = Path(__file__).with_name("flows.json")

INTRO = 0.8  # seconds before the first step
STEP = 1.7  # time between two steps
DRAW = 1.0  # time an arrow takes to draw
HOLD = 3.2  # full diagram on screen before the loop restarts
OUT = 0.8  # fade back to the starting state
DIM = 0.22  # opacity of an arrow that has not been drawn yet
REST = 0.45  # opacity of the legend rows that are not the current step
EASE = "cubic-bezier(.45,0,.25,1)"
ACCENT = "#FF9900"
BADGE = "#007CBD"
SIZE_LIMIT = 1000 * 1024

CELL = re.compile(r'<g data-cell-id="([^"]+)"')


def read_model(drawio: Path) -> dict[str, dict[str, str]]:
    """Return every mxCell of the .drawio as {id: attributes}, to know where each arrow points."""
    text = drawio.read_text(encoding="utf-8")
    if "<mxCell" not in text and "<diagram" in text:
        sys.exit(f"{drawio}: saved compressed; uncheck File > Properties > Compressed in draw.io and save again")
    model = {}
    for tag in re.findall(r"<mxCell\b[^>]*>", text):
        attrs = {k: html.unescape(v) for k, v in re.findall(r'(\w+)="([^"]*)"', tag)}
        if "id" in attrs:
            model[attrs["id"]] = attrs
    return model


def blocks(svg: str) -> dict[str, tuple[int, int]]:
    """Map each draw.io cell id to the slice of the SVG text that draws it.

    draw.io writes every cell as a flat sibling group, so a cell ends where the next one starts.
    """
    found = [(m.group(1), m.start()) for m in CELL.finditer(svg)]
    end = svg.rfind("</svg>")
    return {cid: (start, found[i + 1][1] if i + 1 < len(found) else end) for i, (cid, start) in enumerate(found)}


def polyline(d: str) -> list[tuple[float, float]]:
    """Points of an arrow path. draw.io arrows use M and L, Q for line-jump arcs, and C for curved edges."""
    nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", d)]
    pts, i = [], 0
    for c in re.findall(r"[MLQC]", d):
        if c in "ML":
            pts.append((nums[i], nums[i + 1]))
            i += 2
        elif c == "Q":  # control point, then end point; the arc is short, so a straight segment is close enough
            pts.append((nums[i + 2], nums[i + 3]))
            i += 4
        else:  # C: two control points, then end point
            pts.append((nums[i + 4], nums[i + 5]))
            i += 6
    return pts


def length(pts: list[tuple[float, float]]) -> float:
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:], strict=False))


def waypoints(pts: list[tuple[float, float]], n: int = 14) -> list[tuple[float, float]]:
    """Evenly spaced points along the arrow, for the dot to travel through."""
    total = length(pts) or 1.0
    out = []
    for k in range(n + 1):
        target, acc = total * k / n, 0.0
        for a, b in zip(pts, pts[1:], strict=False):
            seg = math.dist(a, b)
            if acc + seg >= target or (a, b) == (pts[-2], pts[-1]):
                f = 0.0 if seg == 0 else min(1.0, (target - acc) / seg)
                out.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
                break
            acc += seg
    return out


class Motion:
    """Builds one looping timeline per animated element, with one track per CSS property.

    Two effects on the same property of one element (a box that glows twice) are merged into a single
    keyframes rule, because a second animation on the same property would override the first.
    """

    def __init__(self, total: float) -> None:
        self.total = total
        self.tracks: dict[str, dict[str, tuple[str, list[tuple[float, str]]]]] = {}
        self.extra: dict[str, str] = {}

    def pct(self, t: float) -> str:
        return f"{max(0.0, min(100.0, 100 * t / self.total)):.2f}%"

    def cls(self, key: str) -> str:
        return f"k{list(self.tracks).index(key) + 1}" if key in self.tracks else ""

    def has(self, key: str, prop: str) -> bool:
        return prop in self.tracks.get(key, {})

    def add(self, key: str, prop: str, frames: list[tuple[float, str]], easing: str = EASE, extra: str = "") -> str:
        """Add (time, value) frames for one property of an element and return the element's class."""
        props = self.tracks.setdefault(key, {})
        if prop in props:
            ease, old = props[prop]
            inner = [f for f in frames if 0 < f[0] < self.total]
            props[prop] = (ease, sorted(old + inner, key=lambda f: f[0]))
        else:
            props[prop] = (easing, sorted(frames, key=lambda f: f[0]))
        if extra:
            self.extra[key] = extra
        return self.cls(key)

    def css(self) -> str:
        out = []
        for key, props in self.tracks.items():
            name, anims = self.cls(key), []
            for i, (prop, (easing, frames)) in enumerate(props.items()):
                body = "".join(f"{self.pct(t)}{{{prop}:{v}}}" for t, v in frames)
                out.append(f"@keyframes {name}{'abcdefgh'[i]}{{{body}}}")
                anims.append(f"{name}{'abcdefgh'[i]} {self.total:.2f}s {easing} infinite")
            extra = f";{self.extra[key]}" if key in self.extra else ""
            out.append(f".{name}{{animation:{','.join(anims)}{extra}}}")
        return "".join(out)


def add_class(svg: str, span: tuple[int, int], cls: str) -> tuple[str, int]:
    """Give the cell's outer group a class; return the new text and how much it grew."""
    start = span[0]
    tag_end = svg.index(">", start)
    head = svg[start:tag_end]
    new = head.replace('class="', f'class="{cls} ', 1) if 'class="' in head else f'{head} class="{cls}"'
    return svg[:start] + new + svg[tag_end:], len(new) - len(head)


def outline(text: str) -> tuple[float, float, float, float, float] | None:
    """Box of a cell for its glow ring: its first rectangle, or the bounds of its first filled path.

    AWS group shapes (VPC, subnet, region) are drawn as paths rather than rectangles.
    """
    r = re.search(r'<rect x="([\d.-]+)" y="([\d.-]+)" width="([\d.]+)" height="([\d.]+)"(?: rx="([\d.]+)")?', text)
    if r:
        x, y, w, h = map(float, r.groups()[:4])
        return x, y, w, h, float(r.group(5) or 0)
    p = re.search(r'<path d="([MLCQZ\d.\s-]+)" fill="(?!none)', text)
    if not p:
        return None
    nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", p.group(1))]
    xs, ys = nums[0::2], nums[1::2]
    return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys), 0.0


def center(text: str) -> str:
    """Pivot of a badge in px. Its label is a 100%-sized foreignObject, so the fill box would sit far away."""
    r = re.search(r'<rect x="([\d.-]+)" y="([\d.-]+)" width="([\d.]+)" height="([\d.]+)"', text)
    if r:
        x, y, w, h = map(float, r.groups())
        return f"{x + w / 2:g}px {y + h / 2:g}px"
    e = re.search(r'<ellipse cx="([\d.-]+)" cy="([\d.-]+)"', text)
    return f"{float(e.group(1)):g}px {float(e.group(2)):g}px" if e else "center"


def outermost(cells: list[str], model: dict[str, dict[str, str]]) -> list[str]:
    """Keep only the cells with no ancestor in the list: an SVG child group already inherits the opacity."""
    chosen = set(cells)

    def covered(cid: str) -> bool:
        seen, parent = set(), model.get(cid, {}).get("parent")
        while parent and parent not in seen:
            if parent in chosen:
                return True
            seen.add(parent)
            parent = model.get(parent, {}).get("parent")
        return False

    return [c for c in cells if not covered(c)]


def load_flows(path: Path = FLOWS) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def default_steps(svg: str, spans: dict[str, tuple[int, int]], model: dict) -> list[dict]:
    return [{"edges": [cid]} for cid in spans if model.get(cid, {}).get("edge") == "1"]


def related(cid: str, spans: dict[str, tuple[int, int]]) -> list[str]:
    """A box in these diagrams is a group cell plus its icon cell (grp-x and svc-x): glow both."""
    base = cid.split("-", 1)[1] if cid.startswith(("grp-", "svc-")) else cid
    return [c for c in (cid, f"grp-{base}", f"svc-{base}") if c in spans] or []


def animate(drawio: Path, flows: dict) -> Path:
    drawio = drawio.resolve()
    rel = drawio.resolve().relative_to(ROOT).as_posix()
    out = drawio.with_suffix(".svg")
    if not out.exists():
        sys.exit(f"{out}: export it first with render.sh")
    svg = out.read_text(encoding="utf-8")
    if 'class="mo-fx"' in svg:
        sys.exit(f"{out}: already animated; export it again with render.sh")
    model = read_model(drawio)

    # The text labels come with a PNG copy for viewers without foreignObject support. Every browser that
    # renders GitHub images supports it, and those copies are 90% of the file, so they go.
    svg = re.sub(r"(</foreignObject>)\s*<image\b[^>]*/>(\s*</switch>)", r"\1\2", svg)
    # Same look as the PNG export: light palette on white.
    svg = svg.replace("color-scheme: light dark;", "color-scheme: light;", 1)
    svg = re.sub(r"background: transparent; background-color: transparent;", "background: #FFFFFF;", svg, count=1)

    spans = blocks(svg)
    steps = flows.get(rel, {}).get("steps") or default_steps(svg, spans, model)
    total = INTRO + len(steps) * STEP + DRAW + HOLD + OUT
    mo = Motion(total)
    end_run = INTRO + (len(steps) - 1) * STEP + DRAW + 0.3
    back = total - OUT

    defs, overlay = [], []
    animated_edges = {e for s in steps for e in s.get("edges", [])}
    shine = f"drop-shadow(0 0 10px {ACCENT}) drop-shadow(0 0 3px {ACCENT})"

    rings: dict[str, str] = {}

    def glow(node: str, at: float) -> None:
        """Light up a box with an orange ring traced over its border.

        A drop shadow would tint the whole fill of a large see-through container, so the ring follows the
        box's own rectangle. A box drawn without one (a bare icon) gets the drop shadow instead.
        """
        cells = related(node, spans)
        frames = [(0, "0"), (at - 0.1, "0"), (at + 0.15, "1"), (at + 0.9, "0"), (total, "0")]
        for cid in cells:
            box = outline(svg[slice(*spans[cid])])
            if not box:
                continue
            x, y, w, h, rx = box
            key = f"ring-{cid}"
            cls = mo.add(key, "opacity", frames, easing="ease-out")
            if key not in rings:
                shape = f'x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="{rx:g}" fill="none" stroke="{ACCENT}"'
                rings[key] = (
                    f'<g class="{cls}" style="opacity:0"><rect {shape} stroke-width="8" filter="url(#mo-blur)"/>'
                    f'<rect {shape} stroke-width="2.5"/></g>'
                )
            return
        for cid in cells:
            mo.add(
                cid,
                "filter",
                [(0, "none"), (at - 0.1, "none"), (at + 0.15, shine), (at + 0.9, "none"), (total, "none")],
                easing="ease-out",
            )

    for k, step in enumerate(steps):
        t0 = INTRO + k * STEP
        t1 = t0 + DRAW
        for eid in step.get("edges", []):
            if eid not in spans:
                print(f"  ! {rel}: edge {eid} not found", file=sys.stderr)
                continue
            text = svg[slice(*spans[eid])]
            m = re.search(r'<path d="([^"]+)" fill="none" stroke="([^"]+)"([^>]*)/>', text)
            if not m:
                continue
            d, stroke, rest = m.groups()
            dash = re.search(r'stroke-dasharray="([^"]+)"', rest)
            width = re.search(r'stroke-width="([^"]+)"', rest)
            # 1. The arrow stays faint until its step, then shows in full until the loop fades it back.
            #    An arrow listed in two steps keeps the timing of the first one.
            if not mo.has(eid, "opacity"):
                fade = [(0, f"{DIM}"), (t1 - 0.05, f"{DIM}"), (t1 + 0.1, "1"), (back, "1"), (total, f"{DIM}")]
                cells = [c for c in (eid, f"{eid}-label", f"{eid}-lbl", *step.get("labels", [])) if c in spans]
                for cid in outermost(cells, model):
                    mo.add(cid, "opacity", fade)
            # 2. A copy of the line draws itself from source to target, revealed by a growing mask.
            mid = f"mk{len(defs)}"
            reveal = mo.add(
                f"{mid}-r",
                "stroke-dashoffset",
                [(0, "1"), (t0, "1"), (t0 + 0.02, "1"), (t1, "0"), (total, "0")],
                easing="linear",
            )
            defs.append(
                f'<mask id="{mid}" maskUnits="userSpaceOnUse" x="-10000" y="-10000" width="40000" '
                f'height="40000"><path d="{d}" fill="none" stroke="#fff" stroke-width="16" '
                f'pathLength="1" stroke-dasharray="1 1" class="{reveal}"/></mask>'
            )
            show = mo.add(
                f"{mid}-l",
                "opacity",
                [(0, "0"), (t0, "0"), (t0 + 0.05, "1"), (t1 + 0.1, "1"), (t1 + 0.35, "0"), (total, "0")],
                easing="linear",
            )
            sw = float(width.group(1)) + 1 if width else 3
            dash_attr = f' stroke-dasharray="{dash.group(1)}"' if dash else ""
            overlay.append(
                f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{sw:g}"{dash_attr} '
                f'mask="url(#{mid})" class="{show}"/>'
            )
            # 3. A glowing dot rides the front of the line.
            way = waypoints(polyline(d))
            if len(way) < 2:
                print(f"  ! {rel}: edge {eid} has no usable path for the dot", file=sys.stderr)
                continue
            start = f"translate({way[0][0]:.1f}px,{way[0][1]:.1f}px)"
            moves = [(0, start), (t0, start)]
            for i, (x, y) in enumerate(way):
                moves.append((t0 + 0.02 + (DRAW - 0.02) * i / (len(way) - 1), f"translate({x:.1f}px,{y:.1f}px)"))
            moves.append((total, f"translate({way[-1][0]:.1f}px,{way[-1][1]:.1f}px)"))
            mo.add(f"{mid}-d", "transform", moves, easing="linear")
            dot = mo.add(
                f"{mid}-d",
                "opacity",
                [(0, "0"), (t0, "0"), (t0 + 0.04, "1"), (t1 - 0.04, "1"), (t1 + 0.02, "0"), (total, "0")],
                easing="linear",
            )
            overlay.append(
                f'<g class="{dot}"><circle r="20" fill="url(#mo-halo)"/>'
                f'<circle r="6.5" fill="{ACCENT}" stroke="#FFFFFF" stroke-width="2"/></g>'
            )
            # 4. The box the arrow reaches glows when the dot arrives.
            target = model.get(eid, {}).get("target")
            if target and related(target, spans):
                glow(target, t1)
        for node in step.get("glow", []):
            if related(node, spans):
                glow(node, t0 + 0.4)
        # 5. The step badge pulses and its legend row lights up while the others rest.
        badge = step.get("badge")
        if badge and badge in spans:
            mo.add(
                badge,
                "transform",
                [
                    (0, "scale(1)"),
                    (t0, "scale(1)"),
                    (t0 + 0.18, "scale(1.3)"),
                    (t0 + 0.6, "scale(1)"),
                    (total, "scale(1)"),
                ],
                extra=f"transform-box:view-box;transform-origin:{center(svg[slice(*spans[badge])])}",
            )
            mo.add(
                badge,
                "filter",
                [
                    (0, "none"),
                    (t0, "none"),
                    (t0 + 0.18, f"drop-shadow(0 0 8px {BADGE})"),
                    (t0 + 0.6, "none"),
                    (total, "none"),
                ],
            )
        digits = re.search(r"\d+", badge) if badge else None
        num = digits.group(0) if digits else None
        rows = step.get("legend") or (
            [
                c
                for c in spans
                if ("legend" in c and re.search(rf"(^|-){num}(-|$)", c)) or re.fullmatch(rf"s{num}-(badge|desc)", c)
            ]
            if num
            else []
        )
        if rows:
            last = k == len(steps) - 1
            frames = [(0, "1"), (INTRO - 0.2, "1"), (INTRO, f"{REST}")]
            if t0 > INTRO:
                frames.append((t0 - 0.05, f"{REST}"))
            frames.append((t0 + 0.15, "1"))
            if not last:
                frames += [(t0 + STEP - 0.05, "1"), (t0 + STEP + 0.1, f"{REST}"), (end_run, f"{REST}")]
            frames += [(end_run + 0.3, "1"), (total, "1")]
            for c in outermost([c for c in rows if c in spans], model):
                mo.add(c, "opacity", frames, easing="linear")

    classes = {key: mo.cls(key) for key in mo.tracks if key in spans}
    # Apply the classes from the end of the file backwards so earlier offsets stay valid.
    for cid in sorted(classes, key=lambda c: spans[c][0], reverse=True):
        svg, _ = add_class(svg, spans[cid], classes[cid])

    unanimated = [c for c in spans if model.get(c, {}).get("edge") == "1" and c not in animated_edges]
    css = mo.css() + "@media (prefers-reduced-motion:reduce){*{animation:none!important}.mo-fx{display:none}}"
    halo = (
        '<radialGradient id="mo-halo"><stop offset="0" stop-color="#FF9900" stop-opacity=".9"/>'
        '<stop offset=".45" stop-color="#FF9900" stop-opacity=".35"/>'
        '<stop offset="1" stop-color="#FF9900" stop-opacity="0"/></radialGradient>'
    )
    blur = (
        '<filter id="mo-blur" filterUnits="userSpaceOnUse" x="-10000" y="-10000" width="40000" height="40000">'
        '<feGaussianBlur stdDeviation="4"/></filter>'
    )
    layer = (
        f"<defs>{halo}{blur}{''.join(defs)}</defs><style>{css}</style>"
        f'<g class="mo-fx" pointer-events="none">{"".join(rings.values())}{"".join(overlay)}</g>'
    )
    svg = svg[: svg.rfind("</svg>")] + layer + "</svg>\n"

    out.write_text(svg, encoding="utf-8")
    size = out.stat().st_size
    note = f", {len(unanimated)} arrow(s) outside the flow stay static" if unanimated else ""
    print(f"{out.relative_to(ROOT)}: {len(steps)} steps, {total:.1f}s loop, {size // 1024} KB{note}")
    if size > SIZE_LIMIT:
        sys.exit(f"{out}: {size // 1024} KB is over the 1000 KB budget")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("drawio", nargs="*", type=Path, help=".drawio files to animate")
    ap.add_argument("--all", action="store_true", help="animate every diagram listed in flows.json")
    ap.add_argument("--list", action="store_true", help="print the diagrams listed in flows.json and exit")
    ap.add_argument("--flows", type=Path, default=FLOWS, help="step order file (default: flows.json)")
    args = ap.parse_args()
    flows = load_flows(args.flows)
    if args.list:
        print("\n".join(flows))
        return
    files = [ROOT / p for p in flows] if args.all else args.drawio
    if not files:
        ap.error("pass .drawio files or --all")
    for f in files:
        animate(f, flows)


if __name__ == "__main__":
    main()
