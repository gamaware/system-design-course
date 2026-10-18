#!/usr/bin/env python3
"""Extrae a dist/ solo los iconos oficiales que usan los puzzles (arch-builder, ICONS.md).

    python3 -I tools/icons.py --cache DIR --out dist/icons [--puzzles puzzles] [--registry icons/registry.json]

Lee los paquetes ya descargados y verificados por scripts/fetch-icons.sh (zip de AWS, Azure y Google Cloud; librería
draw.io de Oracle) sin descomprimirlos completos: abre cada zip y copia únicamente los miembros que el registro
(icons/registry.json) asigna a un servicio o grupo que aparece en algún puzzle, más el icono de cada nube (selector
de la portada). Escribe <out>/<id>.svg y
<out>/manifest.json (id -> paquete y archivo de origen) para que tools/build.py arme el sprite.

Oracle no publica archivos SVG: su paquete oficial es una librería de draw.io cuyas figuras son plantillas vectoriales
("stencils"). Para cada figura usada se traduce esa geometría a SVG tal cual (mismos trazos, mismos colores, misma
proporción); no se redibuja ni se recolorea nada.

Los paquetes son datos no confiables: no se ejecuta nada de ellos, solo se leen miembros por nombre, se comprueba que
sean SVG y se escriben con nombres generados aquí (nunca se usa una ruta que venga del zip).
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import re
import sys
import urllib.parse
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_ICON_BYTES = 2_000_000
OCI_MEMBER = "OCI Style Guide for Drawio/OCI Library.xml"

# Iconos genéricos (personas, internet): trazo neutro propio, no son marcas de ningún proveedor.
BUILTIN = {
    "users": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><g fill="none" stroke="#232F3E" '
        'stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><circle cx="24" cy="22" r="8"/>'
        '<path d="M10 50c0-9 6-15 14-15s14 6 14 15"/><circle cx="43" cy="19" r="6.5"/>'
        '<path d="M40 31c1-.3 2-.4 3-.4 7 0 12 5 12 13"/></g></svg>'
    ),
    "internet": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><g fill="none" stroke="#232F3E" '
        'stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><circle cx="32" cy="32" r="22"/>'
        '<path d="M10 32h44M32 10c-7 6-10 14-10 22s3 16 10 22M32 10c7 6 10 14 10 22s-3 16-10 22"/>'
        '<path d="M14 20h36M14 44h36"/></g></svg>'
    ),
    "team": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><g fill="none" stroke="#232F3E" '
        'stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><circle cx="22" cy="24" r="7"/>'
        '<path d="M9 50c0-8 6-13 13-13s13 5 13 13"/><path d="M42 18a8 8 0 0 1 8 8v7l3 5H39l3-5v-7a8 8 0 0 1 8-8z" '
        'transform="translate(-4 4)"/><path d="M43 47a3.5 3.5 0 0 0 6 0"/></g></svg>'
    ),
}


class IconError(Exception):
    pass


def load_packages(tsv: Path) -> dict[str, str]:
    """id -> nombre del archivo del paquete (icons/packages.tsv)."""
    out = {}
    for line in tsv.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) != 4:
            raise IconError(f"{tsv.name}: línea mal formada: {line!r}")
        out[cols[0]] = cols[1]
    return out


def used_ids(puzzle_dir: Path, registry: dict) -> tuple[set[str], set[str]]:
    services: set[str] = set()
    kinds: set[str] = set()
    for f in sorted(puzzle_dir.glob("*.json")):
        p = json.loads(f.read_text(encoding="utf-8"))
        services |= {n["icon"] for n in p.get("nodes", [])}
        services |= {t["service"] for t in p.get("palette", [])}
        services |= {s["accept"][0] for s in p.get("slots", []) if s.get("accept")}
        kinds |= {g["kind"] for g in p.get("groups", []) if g["kind"] in registry["groups"]}
    unknown = sorted(s for s in services if s not in registry["services"])
    if unknown:
        raise IconError(f"servicios sin entrada en icons/registry.json: {unknown}")
    return services, kinds


def read_svg(zf: zipfile.ZipFile, member: str) -> str:
    try:
        info = zf.getinfo(member)
    except KeyError as e:
        raise IconError(f"{zf.filename}: no contiene {member!r}") from e
    if info.file_size > MAX_ICON_BYTES:
        raise IconError(f"{member}: {info.file_size} bytes, demasiado grande para un icono")
    text = zf.read(info).decode("utf-8")
    if "<svg" not in text:
        raise IconError(f"{member}: no es un SVG")
    return text


# ---------------------------------------------------------------- Oracle: draw.io stencil -> SVG
TAG = re.compile(r"<(/?)([A-Za-z-]+)((?:\s+[A-Za-z_:][A-Za-z0-9_:.-]*=\"[^\"]*\")*)\s*(/?)>")
ATTR = re.compile(r"([A-Za-z_:][A-Za-z0-9_:.-]*)=\"([^\"]*)\"")


def _attrs(s: str) -> dict[str, str]:
    return {k: html.unescape(v) for k, v in ATTR.findall(s)}


def _inflate(data: str) -> str:
    raw = zlib.decompress(base64.b64decode(data), -15).decode("utf-8")
    return urllib.parse.unquote(raw)


def oci_library(zf: zipfile.ZipFile) -> dict[str, dict]:
    text = zf.read(OCI_MEMBER).decode("utf-8")
    m = re.search(r"<mxlibrary>(.*)</mxlibrary>", text, re.S)
    if not m:
        raise IconError(f"{OCI_MEMBER}: no es una librería de draw.io")
    out: dict[str, dict] = {}
    for entry in json.loads(m.group(1)):
        title = html.unescape(html.unescape(str(entry.get("title") or ""))).replace("\xa0", " ").strip()
        if title and title not in out:
            out[title] = entry
    return out


def _style(s: str) -> dict[str, str]:
    out = {}
    for part in s.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k] = v
    return out


def _cells(model: str) -> list[dict]:
    cells = []
    for m in re.finditer(r"<mxCell\b([^>]*?)(/>|>(.*?)</mxCell>)", model, re.S):
        a = _attrs(m.group(1))
        geo = re.search(r"<mxGeometry\b([^>]*)", m.group(3) or "")
        g = _attrs(geo.group(1)) if geo else {}
        cells.append(
            {
                "id": a.get("id"),
                "parent": a.get("parent"),
                "value": a.get("value", ""),
                "style": a.get("style", ""),
                "x": float(g.get("x", 0)),
                "y": float(g.get("y", 0)),
                "w": float(g.get("width", 0)),
                "h": float(g.get("height", 0)),
            }
        )
    return cells


def _num(v: str) -> str:
    x = round(float(v), 3)
    return str(int(x)) if x == int(x) else f"{x:g}"


def stencil_svg(stencil: str, x: float, y: float, w: float, h: float, fill: str, stroke: str, sw: float) -> list[str]:
    """One stencil (draw.io mxStencil XML) placed at x, y, w, h -> SVG elements (paths drawn by its fill ops)."""
    head = re.search(r"<shape\b([^>]*)>", stencil)
    sa = _attrs(head.group(1)) if head else {}
    w0, h0 = float(sa.get("w") or 100), float(sa.get("h") or 100)
    sx, sy = w / w0, h / h0

    def px(v: str) -> str:
        return _num(str(x + float(v) * sx))

    def py(v: str) -> str:
        return _num(str(y + float(v) * sy))

    out: list[str] = []
    d: list[str] = []
    cur = {"fill": fill, "stroke": stroke, "sw": sw}
    for close, tag, attrs, _ in TAG.findall(stencil):
        if close:
            continue
        a = _attrs(attrs)
        if tag == "move":
            d.append(f"M{px(a['x'])} {py(a['y'])}")
        elif tag == "line":
            d.append(f"L{px(a['x'])} {py(a['y'])}")
        elif tag == "curve":
            d.append(f"C{px(a['x1'])} {py(a['y1'])} {px(a['x2'])} {py(a['y2'])} {px(a['x3'])} {py(a['y3'])}")
        elif tag == "quad":
            d.append(f"Q{px(a['x1'])} {py(a['y1'])} {px(a['x2'])} {py(a['y2'])}")
        elif tag == "arc":
            rx, ry = _num(str(float(a["rx"]) * sx)), _num(str(float(a["ry"]) * sy))
            flags = f"{a.get('x-axis-rotation', '0')} {a.get('large-arc-flag', '0')} {a.get('sweep-flag', '0')}"
            d.append(f"A{rx} {ry} {flags} {px(a['x'])} {py(a['y'])}")
        elif tag == "close":
            d.append("Z")
        elif tag in ("rect", "roundrect"):
            w1, h1 = float(a.get("w", 0)) * sx, float(a.get("h", 0)) * sy
            x0, y0 = px(a["x"]), py(a["y"])
            r = min(w1, h1) * float(a.get("arcsize", 0)) / 100 if tag == "roundrect" else 0
            if r:
                q, wi, hi = _num(str(r)), _num(str(w1 - 2 * r)), _num(str(h1 - 2 * r))
                corner = f"a{q} {q} 0 0 1"
                d.append(
                    f"M{_num(str(float(x0) + r))} {y0}h{wi}{corner} {q} {q}v{hi}{corner} -{q} {q}"
                    f"h-{wi}{corner} -{q} -{q}v-{hi}{corner} {q} -{q}Z"
                )
            else:
                d.append(f"M{x0} {y0}h{_num(str(w1))}v{_num(str(h1))}h-{_num(str(w1))}Z")
        elif tag == "ellipse":
            erx, ery = float(a["w"]) * sx / 2, float(a["h"]) * sy / 2
            cx, cy = float(px(a["x"])) + erx, float(py(a["y"])) + ery
            arc = f"a{_num(str(erx))} {_num(str(ery))} 0 1 0"
            d.append(
                f"M{_num(str(cx - erx))} {_num(str(cy))}{arc} {_num(str(2 * erx))} 0{arc} -{_num(str(2 * erx))} 0Z"
            )
        elif tag == "fillcolor":
            cur["fill"] = a.get("color", cur["fill"])
        elif tag == "strokecolor":
            cur["stroke"] = a.get("color", cur["stroke"])
        elif tag == "strokewidth":
            cur["sw"] = float(a.get("width", cur["sw"]))
        elif tag in ("fill", "stroke", "fillstroke"):
            if d:
                f = cur["fill"] if tag in ("fill", "fillstroke") and cur["fill"] not in ("none", "") else "none"
                s = cur["stroke"] if tag in ("stroke", "fillstroke") and cur["stroke"] not in ("none", "") else None
                if f != "none" or s:
                    stroke_attr = f' stroke="{s}" stroke-width="{_num(str(cur["sw"]))}"' if s else ""
                    out.append(f'<path d="{"".join(d)}" fill="{f}"{stroke_attr}/>')
            d = []
    return out


def oci_svg(entry: dict) -> str:
    """Library entry (compressed mxGraphModel) -> standalone SVG of the icon (the text label cell is left out)."""
    cells = _cells(_inflate(entry["xml"]))
    by_id = {c["id"]: c for c in cells}

    def origin(c: dict) -> tuple[float, float]:
        ox, oy, cur, guard = 0.0, 0.0, by_id.get(c["parent"]), 0
        while cur is not None and guard < 50:
            ox, oy = ox + cur["x"], oy + cur["y"]
            cur = by_id.get(cur["parent"])
            guard += 1
        return ox, oy

    parts: list[str] = []
    xs: list[float] = []
    ys: list[float] = []
    for c in cells:
        st = _style(c["style"])
        m = re.search(r"shape=stencil\(([^)]*)\)", c["style"])
        if not m or c["value"].strip():
            continue
        fill, stroke = st.get("fillColor", "none"), st.get("strokeColor", "none")
        if fill == "none" and stroke == "none":
            continue
        ox, oy = origin(c)
        x, y = ox + c["x"], oy + c["y"]
        drawn = stencil_svg(_inflate(m.group(1)), x, y, c["w"], c["h"], fill, stroke, float(st.get("strokeWidth", 1)))
        if drawn:
            parts += drawn
            xs += [x, x + c["w"]]
            ys += [y, y + c["h"]]
    if not parts:
        raise IconError(f"figura OCI sin trazos: {entry.get('title')!r}")
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    vb = f"{_num(str(x0))} {_num(str(y0))} {_num(str(x1 - x0))} {_num(str(y1 - y0))}"
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}">{"".join(parts)}</svg>'


# ---------------------------------------------------------------- main
def extract(cache: Path, out: Path, puzzle_dir: Path, registry_path: Path, packages_path: Path) -> dict:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    packages = load_packages(packages_path)
    services, kinds = used_ids(puzzle_dir, registry)
    wanted = [(sid, registry["services"][sid]["icon"]) for sid in sorted(services)]
    wanted += [(f"group-{k}", registry["groups"][k]["icon"]) for k in sorted(kinds)]
    wanted += [(f"cloud-{c}", v["logo"]) for c, v in sorted(registry["clouds"].items()) if "logo" in v]
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.svg"):
        old.unlink()
    zips: dict[str, zipfile.ZipFile] = {}
    oci: dict[str, dict] | None = None
    manifest: dict[str, dict] = {}
    try:
        for ident, icon in wanted:
            if "builtin" in icon:
                svg, source = BUILTIN[icon["builtin"]], {"package": "builtin", "name": icon["builtin"]}
            else:
                pkg = icon["package"]
                if pkg not in packages:
                    raise IconError(f"{ident}: paquete desconocido {pkg!r}")
                if pkg not in zips:
                    path = cache / packages[pkg]
                    if not path.is_file():
                        raise IconError(f"falta {path} (corre scripts/fetch-icons.sh)")
                    zips[pkg] = zipfile.ZipFile(path)
                if "shape" in icon:
                    if oci is None:
                        oci = oci_library(zips[pkg])
                    if icon["shape"] not in oci:
                        raise IconError(f"{ident}: la librería OCI no tiene la figura {icon['shape']!r}")
                    svg = oci_svg(oci[icon["shape"]])
                    source = {"package": pkg, "shape": icon["shape"]}
                else:
                    svg = read_svg(zips[pkg], icon["file"])
                    source = {"package": pkg, "file": icon["file"]}
            name = f"{ident}.svg"
            (out / name).write_text(svg, encoding="utf-8")
            manifest[ident] = dict(source, file=name)
    finally:
        for z in zips.values():
            z.close()
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--puzzles", type=Path, default=ROOT / "puzzles")
    ap.add_argument("--registry", type=Path, default=ROOT / "icons" / "registry.json")
    ap.add_argument("--packages", type=Path, default=ROOT / "icons" / "packages.tsv")
    a = ap.parse_args(argv)
    try:
        manifest = extract(a.cache, a.out, a.puzzles, a.registry, a.packages)
    except (IconError, OSError, ValueError, zipfile.BadZipFile) as e:
        print(f"icons: {e}", file=sys.stderr)
        return 1
    by_pkg: dict[str, int] = {}
    for m in manifest.values():
        by_pkg[m["package"]] = by_pkg.get(m["package"], 0) + 1
    print(f"icons: {len(manifest)} iconos en {a.out} {by_pkg}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
