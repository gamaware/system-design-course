#!/usr/bin/env python3
"""Valida los puzzles "completa el diagrama" y arma el sitio estático (arch-builder, AUTHORING.md).

    python3 -I tools/build.py validate [puzzle.json | carpeta] ...    errores E-* y avisos W-*; exit 1 si hay errores
    python3 -I tools/build.py build [--out dist] [--published-only]   valida todo y escribe dist/

Texto base de cada puzzle en español (puzzles/<id>.json); traducción opcional al inglés en puzzles/en/<id>.json, con
los mismos ids. Cualquier error detiene el build y no se escribe nada. Los iconos ya deben estar en <out>/icons/
(scripts/fetch-icons.sh los descarga, verifica y extrae); este script solo los incrusta como <symbol> en
<out>/game-data.js para que dist/index.html funcione abierto desde el disco, sin servidor ni CDN.

Origen: motor del juego de arquitectura de studykit (GAME-SPEC.md), sin banco de preguntas, sin repetición espaciada
y con el selector de nube (AWS, Azure, Google Cloud, Oracle Cloud).
"""

from __future__ import annotations

import json
import math
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
SCHEMA_PATH = ROOT / "schema" / "puzzle.schema.json"
REGISTRY_PATH = ROOT / "icons" / "registry.json"
PACKAGES_PATH = ROOT / "icons" / "packages.tsv"
PUZZLES = ROOT / "puzzles"
APP_FILES = ["app.css", "core.js", "render.js", "app.js"]
CLOUDS = ("aws", "azure", "gcp", "oci")
OVERLAY_LANG = "en"

# Rejilla (debe coincidir con GEOM en app/render.js).
CW, CH = 120, 112
NODE_BOX = (-54, 0, 54, 104)
MARGIN_X, MARGIN_TOP, MARGIN_BOTTOM = 0.06, 0.22, 0.06
LABEL_H, LABEL_CHAR, LABEL_PAD = 26, 8.2, 34
# Grupos que pueden cruzar a sus hermanos: zonas dibujadas como columnas que atraviesan las subredes (ARCHITECTURES.md),
# grupos de autoescalado y de seguridad.
CROSSING = {"auto-scaling-group", "security-group", "az", "azure-zone", "gcp-zone", "oci-ad", "oci-fault-domain"}
STRADDLE = {"aws-internet-gateway", "aws-nat-gateway", "aws-vpc-endpoint"}
KIND_CLOUD = {
    "aws-cloud": "aws",
    "aws-account": "aws",
    "region": "aws",
    "az": "aws",
    "vpc": "aws",
    "public-subnet": "aws",
    "private-subnet": "aws",
    "security-group": "aws",
    "auto-scaling-group": "aws",
    "azure-subscription": "azure",
    "azure-resource-group": "azure",
    "azure-region": "azure",
    "azure-vnet": "azure",
    "azure-subnet": "azure",
    "azure-zone": "azure",
    "gcp-cloud": "gcp",
    "gcp-project": "gcp",
    "gcp-region": "gcp",
    "gcp-vpc": "gcp",
    "gcp-subnet": "gcp",
    "gcp-zone": "gcp",
    "oci-tenancy": "oci",
    "oci-compartment": "oci",
    "oci-region": "oci",
    "oci-ad": "oci",
    "oci-fault-domain": "oci",
    "oci-vcn": "oci",
    "oci-subnet": "oci",
}
LEVELS = [(3, "easy"), (6, "medium"), (99, "hard")]
BAND = {"easy": 0, "medium": 1, "hard": 2}
EM_DASH = "—"
TOKEN = re.compile(r"\{\{(s\d{1,2})\}\}")
ARTICLE_EN = re.compile(r"(?<![A-Za-z])(a|an|the)\s+\{\{s\d{1,2}\}\}", re.I)
ARTICLE_ES = re.compile(r"(?<![A-Za-zÁÉÍÓÚáéíóúñÑ])(el|la|los|las|un|una|unos|unas|del|al|lo)\s+\{\{s\d{1,2}\}\}", re.I)
CATEGORY_WORDS = {
    "compute": r"servidor|cómputo|instancia|copias|sistema operativo|ejecuta|server|compute|instance|operating system",
    "networking": r"tráfico|red|ruta|HTTPS|HTTP|balance|petici|URL|DNS|internet|traffic|network|route|request",
    "security": r"certificado|llave|cifr|secreto|identidad|token|certificate|key|encrypt|secret|identity",
    "management": r"métrica|alarma|avisa|alerta|registr|monitor|CPU|metric|alarm|alert|log",
    "database": r"base de datos|BD|tabla|consulta|réplica|database|table|query|replica",
    "storage": r"archivo|objeto|disco|almacen|file|object|disk|storage",
    "integration": r"cola|mensaje|evento|suscri|queue|message|event|subscri",
    "containers": r"contenedor|imagen|clúster|container|image|cluster",
}


class BuildError(Exception):
    pass


# ---------------------------------------------------------------- JSON Schema (subconjunto draft 2020-12)
def schema_errors(obj, schema: dict) -> list[str]:
    """Valida obj contra el subconjunto de JSON Schema que usa puzzle.schema.json. Devuelve 'ruta: mensaje'."""
    root = schema
    out: list[str] = []

    def resolve(s):
        while "$ref" in s:
            ref = s["$ref"]
            if not ref.startswith("#/"):
                raise BuildError(f"referencia de esquema no soportada: {ref}")
            node = root
            for part in ref[2:].split("/"):
                node = node[part]
            s = node
        return s

    def type_ok(v, t):
        if isinstance(t, list):
            return any(type_ok(v, x) for x in t)
        return {
            "object": isinstance(v, dict),
            "array": isinstance(v, list),
            "string": isinstance(v, str),
            "integer": isinstance(v, int) and not isinstance(v, bool),
            "number": isinstance(v, (int, float)) and not isinstance(v, bool),
            "boolean": isinstance(v, bool),
            "null": v is None,
        }[t]

    def collect(v, s, path):
        e: list[str] = []
        check(v, s, path, e)
        return e

    def check(v, s, path, errs):
        s = resolve(s)
        if "oneOf" in s:
            ok = [sub for sub in s["oneOf"] if not collect(v, sub, path)]
            if len(ok) != 1:
                errs.append(f"{path}: debe coincidir con exactamente una forma permitida")
            return
        if "type" in s and not type_ok(v, s["type"]):
            errs.append(f"{path}: se esperaba {s['type']}")
            return
        if "const" in s and v != s["const"]:
            errs.append(f"{path}: debe ser {s['const']!r}")
        if "enum" in s and v not in s["enum"]:
            errs.append(f"{path}: {v!r} no está en {s['enum']}")
        if isinstance(v, str):
            if "minLength" in s and len(v) < s["minLength"]:
                errs.append(f"{path}: más corto que {s['minLength']}")
            if "maxLength" in s and len(v) > s["maxLength"]:
                errs.append(f"{path}: más largo que {s['maxLength']} caracteres")
            if "pattern" in s and not re.search(s["pattern"], v):
                errs.append(f"{path}: {v!r} no cumple {s['pattern']}")
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            if "minimum" in s and v < s["minimum"]:
                errs.append(f"{path}: menor que {s['minimum']}")
            if "maximum" in s and v > s["maximum"]:
                errs.append(f"{path}: mayor que {s['maximum']}")
            if "exclusiveMinimum" in s and v <= s["exclusiveMinimum"]:
                errs.append(f"{path}: debe ser mayor que {s['exclusiveMinimum']}")
        if isinstance(v, list):
            if "minItems" in s and len(v) < s["minItems"]:
                errs.append(f"{path}: menos de {s['minItems']} elementos")
            if "maxItems" in s and len(v) > s["maxItems"]:
                errs.append(f"{path}: más de {s['maxItems']} elementos")
            if s.get("uniqueItems") and len({json.dumps(x, sort_keys=True) for x in v}) != len(v):
                errs.append(f"{path}: elementos repetidos")
            if "items" in s:
                for i, x in enumerate(v):
                    check(x, s["items"], f"{path}[{i}]", errs)
        if isinstance(v, dict):
            for k in s.get("required", []):
                if k not in v:
                    errs.append(f"{path}: falta '{k}'")
            props = s.get("properties", {})
            for k, x in v.items():
                if "propertyNames" in s:
                    check(k, s["propertyNames"], f"{path}.{k} (llave)", errs)
                if k in props:
                    check(x, props[k], f"{path}.{k}", errs)
                elif s.get("additionalProperties") is False:
                    errs.append(f"{path}: propiedad inesperada '{k}'")
                elif isinstance(s.get("additionalProperties"), dict):
                    check(x, s["additionalProperties"], f"{path}.{k}", errs)

    check(obj, schema, "$", out)
    return out


# ---------------------------------------------------------------- contexto y reporte
@dataclass
class Context:
    registry: dict
    schema: dict

    @classmethod
    def load(cls) -> Context:
        return cls(
            registry=json.loads(REGISTRY_PATH.read_text(encoding="utf-8")),
            schema=json.loads(SCHEMA_PATH.read_text(encoding="utf-8")),
        )

    @property
    def services(self) -> dict:
        return self.registry["services"]


@dataclass
class Report:
    errors: list[tuple[str, str]] = field(default_factory=list)
    warnings: list[tuple[str, str]] = field(default_factory=list)

    def err(self, code: str, msg: str) -> None:
        self.errors.append((code, msg))

    def warn(self, code: str, msg: str) -> None:
        self.warnings.append((code, msg))


# ---------------------------------------------------------------- geometría (unidades SVG)
def node_box(cell: dict) -> tuple[float, float, float, float]:
    cx, top = (cell["c"] + 0.5) * CW, cell["r"] * CH
    return (cx + NODE_BOX[0], top + NODE_BOX[1], cx + NODE_BOX[2], top + NODE_BOX[3])


def group_rect(cell: dict) -> tuple[float, float, float, float]:
    return (cell["c"] * CW, cell["r"] * CH, (cell["c"] + cell["w"]) * CW, (cell["r"] + cell["h"]) * CH)


def label_box(g: dict) -> tuple[float, float, float, float]:
    x0, y0, x1, _ = group_rect(g["cell"])
    if g["kind"] in CROSSING:  # zone labels are centred
        half = (LABEL_CHAR * len(g["label"])) / 2
        mid = (x0 + x1) / 2
        return (mid - half, y0, mid + half, y0 + LABEL_H)
    return (x0, y0, min(x1, x0 + LABEL_PAD + LABEL_CHAR * len(g["label"])), y0 + LABEL_H)


def inside(a, b, eps=0.5) -> bool:
    return a[0] >= b[0] - eps and a[1] >= b[1] - eps and a[2] <= b[2] + eps and a[3] <= b[3] + eps


def overlap(a, b, eps=0.5) -> bool:
    return a[0] < b[2] - eps and b[0] < a[2] - eps and a[1] < b[3] - eps and b[1] < a[3] - eps


def decimals_ok(x: float) -> bool:
    return abs(round(x * 100) - x * 100) < 1e-6


# ---------------------------------------------------------------- nombres (leak check)
PREFIXES = ("Amazon ", "AWS ", "Azure ", "Microsoft ", "Google Cloud ", "Google ", "Oracle ", "OCI ")


def service_names(svc: dict) -> list[str]:
    names = {svc["label"], svc["short"], *svc.get("aliases", [])}
    m = re.match(r"^(.*?)\s*\((.+)\)$", svc["label"])
    if m:
        names |= {m.group(1), m.group(2)}
    for n in list(names):
        for pre in PREFIXES:
            if n.startswith(pre) and len(n) > len(pre) + 2:
                names.add(n[len(pre) :])
    return sorted((n for n in names if len(n) >= 2), key=len, reverse=True)


def name_regex(name: str) -> re.Pattern:
    body = re.escape(name).replace(r"\ ", r"[\s-]+")
    flags = 0 if (" " not in name and name[:1].isupper() and name[1:].islower()) else re.I
    return re.compile(rf"(?<![A-Za-z0-9ÁÉÍÓÚáéíóúñÑ]){body}(?![A-Za-z0-9ÁÉÍÓÚáéíóúñÑ])", flags)


def strip_tokens(text: str) -> str:
    return TOKEN.sub(" ", text)


def leaks(p: dict, ctx: Context, texts: list[tuple[str, str]], rep: Report, lang: str) -> None:
    allow = {a["id"] for a in p.get("allow_mention", [])}
    # Un servicio puede responder varios slots (uses > 1): cada uno puede nombrarlo en su propia etiqueta.
    answers: dict[str, set[str]] = {}
    for s in p["slots"]:
        answers.setdefault(s["accept"][0], set()).add(s["id"])
    for sid, slot_ids in answers.items():
        if sid in allow or sid not in ctx.services:
            continue
        for nm in service_names(ctx.services[sid]):
            rx = name_regex(nm)
            for where, text in texts:
                if where in {f"slot {slot_id} label" for slot_id in slot_ids}:
                    continue
                if text and rx.search(text):
                    rep.err("E-LEAK", f"{lang}: {where} nombra la respuesta {sid} ({nm!r})")


# ---------------------------------------------------------------- validación
def validate(p: dict, ctx: Context, stem: str | None = None) -> Report:
    rep = Report()
    for e in schema_errors(p, ctx.schema):
        rep.err("E-SCHEMA", e)
    if rep.errors:
        return rep
    reg = ctx.services
    groups = {g["id"]: g for g in p["groups"]}
    nodes = {n["id"]: n for n in p["nodes"]}
    slots = {s["id"]: s for s in p["slots"]}

    # 1. ids
    if p["id"] != f"{p['scenario']}-{p['cloud']}":
        rep.err("E-ID", f"id {p['id']!r} debe ser {p['scenario']}-{p['cloud']}")
    if stem is not None and stem != p["id"]:
        rep.err("E-ID", f"el archivo se llama {stem}.json pero el id es {p['id']!r}")
    seen: dict[str, int] = {}
    for coll in (p["groups"], p["nodes"], p["slots"], p["edges"]):
        for x in coll:
            seen[x["id"]] = seen.get(x["id"], 0) + 1
    for i, n in seen.items():
        if n > 1:
            rep.err("E-ID", f"el id {i!r} se usa {n} veces")

    # 2. huecos {{sN}}
    token_owner: dict[str, list[int]] = {}
    for r in p["requirements"]:
        toks = TOKEN.findall(r["text"])
        if len(toks) > 1:
            rep.err("E-TOKEN", f"el requisito {r['n']} tiene {len(toks)} huecos (máximo uno)")
        for t in toks:
            token_owner.setdefault(t, []).append(r["n"])
            if t not in slots:
                rep.err("E-TOKEN", f"el requisito {r['n']} nombra el slot inexistente {t}")
        if r["slot"] is not None:
            if r["slot"] not in slots:
                rep.err("E-TOKEN", f"el requisito {r['n']} apunta al slot inexistente {r['slot']!r}")
            elif toks != [r["slot"]]:
                rep.err("E-TOKEN", f"el requisito {r['n']} es de {r['slot']} pero sus huecos son {toks}")
            elif slots[r["slot"]]["number"] != r["n"]:
                rep.err(
                    "E-NUMBER", f"el requisito {r['n']} es de {r['slot']}, cuyo número es {slots[r['slot']]['number']}"
                )
        elif toks:
            rep.err("E-TOKEN", f"el requisito {r['n']} tiene un hueco pero slot es null")
    for sid in slots:
        n = len(token_owner.get(sid, []))
        if n != 1:
            rep.err("E-TOKEN", f"el slot {sid} aparece {n} veces en los requisitos (exactamente una)")

    # 3. respuestas, paleta, iconos, nube
    pal: dict[str, dict] = {}
    for t in p["palette"]:
        if t["service"] in pal:
            rep.err("E-PALETTE", f"{t['service']} aparece dos veces en la paleta")
        pal[t["service"]] = t
    need: dict[str, int] = {}
    for s in p["slots"]:
        need[s["accept"][0]] = need.get(s["accept"][0], 0) + 1
    for sid, n in need.items():
        if sid not in pal:
            rep.err("E-PALETTE", f"la respuesta {sid} no está en la paleta")
        elif pal[sid].get("uses", 1) != n:
            rep.err("E-PALETTE", f"{sid} responde {n} slot(s) pero la paleta le da uses={pal[sid].get('uses', 1)}")
        elif pal[sid].get("role", "answer") != "answer":
            rep.err("E-PALETTE", f"{sid} es respuesta pero tiene role {pal[sid]['role']!r}")
    for sid, t in pal.items():
        if sid not in need and "role" not in t:
            rep.err("E-PALETTE", f"{sid} no es respuesta: dale role near-miss, distractor o filler")
        if sid not in need and t.get("uses", 1) != 1:
            rep.err("E-PALETTE", f"{sid} no es respuesta y no puede tener uses > 1")
    refs = [("nodo", n["icon"]) for n in p["nodes"]] + [("paleta", t["service"]) for t in p["palette"]]
    for where, ident in refs:
        if ident not in reg:
            rep.err("E-ICON", f"icono de {where} {ident!r} no está en icons/registry.json")
            continue
        cloud = reg[ident].get("cloud")
        if cloud not in (None, p["cloud"]):
            rep.err("E-CLOUD", f"{ident} es de {cloud} y el puzzle es de {p['cloud']}")
    for n in p["nodes"]:
        if n["icon"] in reg and reg[n["icon"]].get("cloud") is None and not n.get("label"):
            rep.err("E-LABEL", f"el nodo {n['id']} usa un icono genérico y necesita label")
    for g in p["groups"]:
        kc = KIND_CLOUD.get(g["kind"])
        if kc and kc != p["cloud"]:
            rep.warn("W-CLOUD", f"el grupo {g['id']} es de tipo {g['kind']} ({kc}) en un puzzle de {p['cloud']}")

    # 4. números
    nums = [x["number"] for x in p["nodes"] if x.get("number") is not None] + [s["number"] for s in p["slots"]]
    for n in sorted({x for x in nums if nums.count(x) > 1}):
        rep.err("E-NUMBER", f"el número {n} se usa más de una vez")
    req_n = [r["n"] for r in p["requirements"]]
    if len(set(req_n)) != len(req_n):
        rep.err("E-NUMBER", "se repiten números de requisito")
    if set(nums) != set(req_n):
        rep.err(
            "E-NUMBER", f"números del diagrama {sorted(set(nums))} distintos de los requisitos {sorted(set(req_n))}"
        )

    # 5. geometría
    check_geometry(p, groups, rep)

    # 6. flechas y pasos
    ends = set(nodes) | set(slots)
    for e in p["edges"]:
        for end in ("from", "to"):
            if e[end] not in ends:
                rep.err("E-EDGE", f"la flecha {e['id']} {end} {e[end]!r} no es nodo ni slot")
        if e["from"] == e["to"]:
            rep.err("E-EDGE", f"la flecha {e['id']} sale y llega al mismo lugar")
        if e.get("route") == "points" and not e.get("points"):
            rep.err("E-EDGE", f"la flecha {e['id']} tiene route=points sin points")
    steps = [e["step"] for e in p["edges"] if e["step"] is not None]
    if len(set(steps)) != len(steps):
        rep.err("E-STEP", "se repiten pasos")
    if sorted(set(steps)) != list(range(1, len(set(steps)) + 1)):
        rep.err("E-STEP", f"los pasos deben ser 1..k sin huecos; hay {sorted(steps)}")

    # 7. distractores
    distract = [t for s, t in pal.items() if s not in need]
    minimum = math.ceil(0.75 * len(p["slots"]))
    if len(distract) < minimum:
        rep.err("E-DISTRACT", f"{len(distract)} distractores para {len(p['slots'])} slots (mínimo {minimum})")
    fillers = [t for t in distract if t.get("role") == "filler"]
    if distract and len(fillers) > max(1, len(distract) // 4):
        rep.warn("W-DISTRACT", f"{len(fillers)} de relleno de {len(distract)} distractores (máximo 25 %)")
    if len(p["palette"]) > 20:
        rep.warn("W-DISTRACT", f"{len(p['palette'])} fichas en la paleta (más de 20)")
    for t in distract:
        if t.get("role") in ("near-miss", "distractor") and not t.get("why_not"):
            rep.err("E-NEARMISS", f"{t['service']} ({t['role']}) necesita why_not para los slots donde parece válido")
        for key in t.get("why_not", {}):
            if key != "*" and key not in slots:
                rep.err("E-NEARMISS", f"why_not de {t['service']} nombra el slot inexistente {key}")
    for s in p["slots"]:
        nm = s["near_miss"]
        if nm is None:
            continue
        t = pal.get(nm)
        if t is None or nm in need:
            rep.err("E-NEARMISS", f"near_miss {nm!r} del slot {s['id']} debe ser una ficha que no sea respuesta")
        elif t.get("role") != "near-miss":
            rep.err("E-NEARMISS", f"near_miss {nm!r} del slot {s['id']} debe tener role near-miss")
        elif s["id"] not in t.get("why_not", {}) and "*" not in t.get("why_not", {}):
            rep.err("E-NEARMISS", f"el near-miss {nm} necesita why_not para {s['id']}")

    # 8. fugas de la respuesta (texto base en español)
    texts = [("title", p["title"]), ("summary", p["summary"])]
    texts += [(f"requisito {r['n']}", strip_tokens(r["text"])) for r in p["requirements"]]
    texts += [(f"nodo {n['id']} label", n.get("label", "")) for n in p["nodes"]]
    texts += [(f"slot {s['id']} label", s.get("label", "")) for s in p["slots"]]
    texts += [(f"flecha {e['id']} label", e.get("label", "")) for e in p["edges"]]
    texts += [(f"grupo {g['id']} label", g["label"]) for g in p["groups"]]
    leaks(p, ctx, texts, rep, "es")

    # 9. artículos antes del hueco
    for r in p["requirements"]:
        if ARTICLE_ES.search(r["text"]):  # "a" es preposición en español; el inglés se revisa en la traducción
            rep.err(
                "E-ARTICLE",
                f"requisito {r['n']}: un artículo antes del hueco delata el género o el sonido de la respuesta",
            )

    # 10. explicaciones, pistas, fuentes, rayas
    urls = {ref["url"] for ref in p["source_refs"]}
    for s in p["slots"]:
        req = next((r for r in p["requirements"] if r["slot"] == s["id"]), None)
        if req and s["hint_cue"] not in req["text"]:
            rep.err(
                "E-CUE", f"hint_cue {s['hint_cue']!r} del slot {s['id']} no es parte exacta del requisito {req['n']}"
            )
        for u in s["refs"]:
            if u not in urls:
                rep.err("E-SRC", f"el slot {s['id']} cita {u}, que no está en source_refs")
    texts_dash = [("title", p["title"]), ("summary", p["summary"])]
    texts_dash += [(f"requisito {r['n']}", r["text"]) for r in p["requirements"]]
    texts_dash += [(f"slot {s['id']} explanation", s["explanation"]) for s in p["slots"]]
    texts_dash += [(f"why_not {t['service']} {k}", v) for t in p["palette"] for k, v in t.get("why_not", {}).items()]
    for where, text in texts_dash:
        if EM_DASH in text:
            rep.err("E-EXPL", f"{where} tiene raya larga")
    for r in p["requirements"]:
        if len(r["text"]) > 220:
            rep.warn("W-LENGTH", f"el requisito {r['n']} pasa de 220 caracteres")

    if p.get("difficulty_override"):
        score, level = difficulty(p, ctx)
        if abs(BAND[level] - BAND[p["difficulty_override"]["level"]]) > 1:
            rep.warn(
                "W-DIFF", f"dificultad calculada {level} ({score}) contra la fijada {p['difficulty_override']['level']}"
            )
    return rep


def check_geometry(p: dict, groups: dict, rep: Report) -> None:
    cols, rows = p["layout"]["cols"], p["layout"]["rows"]
    grid = (0, 0, cols * CW, rows * CH)
    for g in p["groups"]:
        c = g["cell"]
        if not all(decimals_ok(c[k]) for k in "crwh"):
            rep.err("E-GEOM", f"el grupo {g['id']} usa más de 2 decimales")
        if not inside(group_rect(c), grid):
            rep.err("E-GEOM", f"el grupo {g['id']} sale de la rejilla {cols}x{rows}")
        if g["parent"] is not None and g["parent"] not in groups:
            rep.err("E-GEOM", f"el grupo {g['id']} tiene un padre inexistente {g['parent']!r}")

    def chain(gid):
        out, cur, guard = [], gid, 0
        while cur is not None and cur in groups and guard < 50:
            out.append(cur)
            cur = groups[cur]["parent"]
            guard += 1
        return out

    for g in p["groups"]:
        if len(chain(g["id"])) >= 50:
            rep.err("E-GEOM", f"el grupo {g['id']} forma un ciclo de padres")
        par = groups.get(g["parent"]) if g["parent"] else None
        if par:
            a, b = g["cell"], par["cell"]
            if (
                a["c"] < b["c"] + MARGIN_X - 1e-6
                or a["c"] + a["w"] > b["c"] + b["w"] - MARGIN_X + 1e-6
                or a["r"] < b["r"] + MARGIN_TOP - 1e-6
                or a["r"] + a["h"] > b["r"] + b["h"] - MARGIN_BOTTOM + 1e-6
            ):
                rep.err(
                    "E-GEOM",
                    f"el grupo {g['id']} no cabe en {par['id']} con los márgenes ({MARGIN_X} lados, "
                    f"{MARGIN_TOP} arriba para la etiqueta, {MARGIN_BOTTOM} abajo)",
                )
    for i, g in enumerate(p["groups"]):
        for h in p["groups"][i + 1 :]:
            if (
                g["parent"] == h["parent"]
                and g["kind"] not in CROSSING
                and h["kind"] not in CROSSING
                and overlap(group_rect(g["cell"]), group_rect(h["cell"]))
            ):
                rep.err("E-GEOM", f"los grupos hermanos {g['id']} y {h['id']} se enciman")
    items = [("nodo", n) for n in p["nodes"]] + [("slot", s) for s in p["slots"]]
    for kind, x in items:
        c = x["cell"]
        if not (decimals_ok(c["c"]) and decimals_ok(c["r"])):
            rep.err("E-GEOM", f"{kind} {x['id']} usa más de 2 decimales")
        if not (0 <= c["c"] <= cols - 1 and 0 <= c["r"] <= rows - 1):
            rep.err("E-GEOM", f"{kind} {x['id']} ({c['c']}, {c['r']}) sale de la rejilla {cols}x{rows}")
            continue
        box = node_box(c)
        gid = x["group"]
        if gid is not None and gid not in groups:
            rep.err("E-GEOM", f"{kind} {x['id']} declara el grupo inexistente {gid!r}")
            continue
        allowed = set(chain(gid)) if gid else set()
        icon = x.get("icon") or x["accept"][0]
        for g in p["groups"]:
            r = group_rect(g["cell"])
            if g["id"] in allowed:
                if not inside(box, r):
                    rep.err("E-GEOM", f"{kind} {x['id']} no queda dentro de su grupo {g['id']}")
            elif g["kind"] in CROSSING:
                pass
            elif inside(box, r):
                rep.err("E-GEOM", f"{kind} {x['id']} queda dentro de {g['id']}, que no es su grupo ni un ancestro")
            elif overlap(box, r) and icon not in STRADDLE:
                rep.warn("W-GEOM", f"{kind} {x['id']} cruza el borde de {g['id']}")
            if overlap(box, label_box(g)):
                rep.warn("W-LABEL", f"{kind} {x['id']} puede tapar la etiqueta del grupo {g['id']}")
    for i, (_, a) in enumerate(items):
        for _, b in items[i + 1 :]:
            if overlap(node_box(a["cell"]), node_box(b["cell"]), eps=2):
                rep.err("E-GEOM", f"{a['id']} y {b['id']} se enciman")


OVERLAY_KEYS = {"id", "title", "summary", "requirements", "slots", "nodes", "edges", "groups", "why_not"}


def validate_overlay(p: dict, tr: dict, ctx: Context, rep: Report) -> None:
    """Traducción al inglés: mismas llaves que el puzzle, mismos huecos, sin artículo delator, sin fugas."""
    for k in tr:
        if k not in OVERLAY_KEYS:
            rep.err("E-OVERLAY", f"en: llave desconocida {k!r}")
    if tr.get("id") != p["id"]:
        rep.err("E-OVERLAY", f"en: id {tr.get('id')!r} distinto de {p['id']!r}")
    by_n = {str(r["n"]): r for r in p["requirements"]}
    ids = {
        "slots": {s["id"] for s in p["slots"]},
        "nodes": {n["id"] for n in p["nodes"]},
        "edges": {e["id"] for e in p["edges"]},
        "groups": {g["id"] for g in p["groups"]},
    }
    for n, text in (tr.get("requirements") or {}).items():
        if n not in by_n:
            rep.err("E-OVERLAY", f"en: el requisito {n} no existe")
            continue
        if TOKEN.findall(text) != TOKEN.findall(by_n[n]["text"]):
            rep.err("E-TOKEN", f"en: el requisito {n} debe conservar los huecos {TOKEN.findall(by_n[n]['text'])}")
        if ARTICLE_EN.search(text):
            rep.err("E-ARTICLE", f"en: requisito {n}: 'a', 'an' o 'the' antes del hueco delata la respuesta")
    for coll in ("slots", "nodes", "edges", "groups"):
        for k in tr.get(coll) or {}:
            if k not in ids[coll]:
                rep.err("E-OVERLAY", f"en: {coll}.{k} no existe en el puzzle")
    pal = {t["service"] for t in p["palette"]}
    for svc, m in (tr.get("why_not") or {}).items():
        if svc not in pal:
            rep.err("E-OVERLAY", f"en: why_not de {svc}, que no está en la paleta")
        for k, text in m.items():
            if k != "*" and k not in ids["slots"]:
                rep.err("E-OVERLAY", f"en: why_not {svc}.{k} nombra un slot inexistente")
            if not 15 <= len(text) <= 300:
                rep.err("E-EXPL", f"en: why_not {svc}.{k} debe tener de 15 a 300 caracteres")
    for sid, f in (tr.get("slots") or {}).items():
        unknown = set(f) - {"explanation", "hint_cue", "label"}
        if unknown:
            rep.err("E-OVERLAY", f"en: slots.{sid} con llaves desconocidas {sorted(unknown)}")
        if "explanation" in f and not 20 <= len(f["explanation"]) <= 300:
            rep.err("E-EXPL", f"en: la explicación de {sid} debe tener de 20 a 300 caracteres")
        cue = f.get("hint_cue")
        req = next((r for r in p["requirements"] if r["slot"] == sid), None)
        if cue and req and cue not in (tr.get("requirements") or {}).get(str(req["n"]), ""):
            rep.err("E-CUE", f"en: hint_cue de {sid} no es parte exacta del requisito en inglés")
    for where, text in overlay_texts(tr):
        if EM_DASH in text:
            rep.err("E-EXPL", f"en: {where} tiene raya larga")
    texts = [(k, tr[k]) for k in ("title", "summary") if tr.get(k)]
    texts += [(f"requisito {n}", strip_tokens(t)) for n, t in (tr.get("requirements") or {}).items()]
    texts += [(f"nodo {k} label", v) for k, v in (tr.get("nodes") or {}).items()]
    texts += [(f"flecha {k} label", v) for k, v in (tr.get("edges") or {}).items()]
    texts += [(f"grupo {k} label", v) for k, v in (tr.get("groups") or {}).items()]
    texts += [(f"slot {k} label", f.get("label", "")) for k, f in (tr.get("slots") or {}).items()]
    leaks(p, ctx, texts, rep, "en")


def overlay_texts(tr: dict):
    for k in ("title", "summary"):
        if tr.get(k):
            yield k, tr[k]
    for n, t in (tr.get("requirements") or {}).items():
        yield f"requisito {n}", t
    for sid, f in (tr.get("slots") or {}).items():
        for k, t in f.items():
            yield f"slot {sid} {k}", t
    for svc, m in (tr.get("why_not") or {}).items():
        for k, t in m.items():
            yield f"why_not {svc} {k}", t
    for coll in ("nodes", "edges", "groups"):
        for k, t in (tr.get(coll) or {}).items():
            yield f"{coll} {k}", t


# ---------------------------------------------------------------- dificultad (GAME-SPEC 1.8 de studykit)
def difficulty(p: dict, ctx: Context) -> tuple[int, str]:
    reg = ctx.services

    def cat(sid):
        return reg.get(sid, {}).get("category")

    slots = p["slots"]
    n = len(slots)
    score = 2 if n >= 7 else 1 if n >= 5 else 0
    answers = {s["accept"][0] for s in slots}
    distract = [t for t in p["palette"] if t["service"] not in answers]
    ratio = len(distract) / n if n else 0
    score += 2 if ratio >= 2 else 1 if ratio >= 1.5 else 0
    score += min(3, sum(1 for s in slots if s.get("near_miss") and cat(s["near_miss"]) == cat(s["accept"][0])))
    score += 1 if len(p["nodes"]) < 2 else 0
    score += 1 if any(not e.get("label") for e in p["edges"]) else 0
    named = 0
    for s in slots:
        req = next((r["text"] for r in p["requirements"] if r["slot"] == s["id"]), "")
        words = CATEGORY_WORDS.get(s.get("category") or cat(s["accept"][0]) or "", "")
        if words and re.search(words, strip_tokens(req), re.I):
            named += 1
    score += 1 if named * 2 < n else 0
    score += 1 if any(s.get("niche") for s in slots) else 0
    level = next(lvl for top, lvl in LEVELS if score <= top)
    return score, level


# ---------------------------------------------------------------- salida
def normalize(p: dict, ctx: Context, tr: dict | None) -> dict:
    reg = ctx.services
    score, level = difficulty(p, ctx)
    out = json.loads(json.dumps(p))
    for k in ("$schema", "review_notes", "allow_mention"):
        out.pop(k, None)
    out["difficulty_score"] = score
    out["difficulty"] = p["difficulty_override"]["level"] if p.get("difficulty_override") else level
    for s in out["slots"]:
        s.setdefault("category", reg[s["accept"][0]]["category"])
        s.setdefault("label", "")
    answers = {s["accept"][0] for s in out["slots"]}
    for t in out["palette"]:
        t.setdefault("uses", 1)
        t.setdefault("role", "answer" if t["service"] in answers else "distractor")
        t.setdefault("why_not", {})
    for e in out["edges"]:
        e.setdefault("route", "auto")
        e.setdefault("label", "")
    for n in out["nodes"]:
        n.setdefault("label", "")
        n.setdefault("number", None)
    out.setdefault("topics", [])
    if tr:
        out[OVERLAY_LANG] = {k: v for k, v in tr.items() if k != "id"}
    return out


def svg_symbol(raw: str, sym_id: str) -> str:
    """SVG oficial -> <symbol id=... viewBox=...>. El dibujo no cambia: se quitan el prólogo, comentarios, <title> y
    los id sin uso; los id referenciados y las clases de <style> se prefijan para que no choquen en la página."""
    s = re.sub(r"<\?xml[^>]*\?>", "", raw)
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"<title>.*?</title>", "", s, flags=re.S)
    m = re.search(r"<svg\b([^>]*)>", s)
    if not m:
        raise BuildError(f"{sym_id}: no es un SVG")
    vb = re.search(r'viewBox="([^"]+)"', m.group(1))
    if not vb:
        w = re.search(r'\bwidth="([\d.]+)', m.group(1))
        h = re.search(r'\bheight="([\d.]+)', m.group(1))
        view = f"0 0 {w.group(1)} {h.group(1)}" if w and h else "0 0 64 64"
    else:
        view = vb.group(1)
    body = s[m.end() : s.rindex("</svg>")]
    refs = set(re.findall(r"url\(#([^)]+)\)", body)) | set(re.findall(r'href="#([^"]+)"', body))
    body = re.sub(r'\sid="([^"]*)"', lambda mm: f' id="{sym_id}-{mm.group(1)}"' if mm.group(1) in refs else "", body)
    for r in refs:
        body = body.replace(f"url(#{r})", f"url(#{sym_id}-{r})").replace(f'href="#{r}"', f'href="#{sym_id}-{r}"')
    classes = set()
    for attr in re.findall(r'\sclass="([^"]*)"', body):
        classes |= set(attr.split())
    for c in sorted(classes, key=len, reverse=True):
        body = re.sub(rf"\.{re.escape(c)}(?![\w-])", f".{sym_id}-{c}", body)
    body = re.sub(
        r'\sclass="([^"]*)"', lambda mm: ' class="' + " ".join(f"{sym_id}-{c}" for c in mm.group(1).split()) + '"', body
    )
    body = re.sub(r">\s+<", "><", body).strip()
    return f'<symbol id="{sym_id}" viewBox="{view}">{body}</symbol>'


def load_strings() -> dict:
    out = {}
    for lang in ("es", "en"):
        f = APP / "i18n" / f"{lang}.json"
        out[lang] = json.loads(f.read_text(encoding="utf-8"))
    missing = set(out["es"]) ^ set(out["en"])
    if missing:
        raise BuildError(f"las llaves de app/i18n/es.json y en.json no coinciden: {sorted(missing)}")
    return out


def load_packages() -> list[dict]:
    out = []
    for line in PACKAGES_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            pid, name, sha, url = line.split("\t")
            out.append({"id": pid, "file": name, "sha256": sha, "url": url})
    return out


def expand(paths: list[str]) -> list[Path]:
    out: list[Path] = []
    for a in paths:
        p = Path(a)
        out += sorted(p.glob("*.json")) if p.is_dir() else [p]
    return out


def check_file(f: Path, ctx: Context) -> tuple[dict | None, dict | None, Report]:
    rep = Report()
    try:
        p = json.loads(f.read_text(encoding="utf-8"))
    except ValueError as e:
        rep.err("E-JSON", str(e))
        return None, None, rep
    rep = validate(p, ctx, f.stem)
    tr = None
    trf = f.parent / OVERLAY_LANG / f.name
    if trf.exists():
        try:
            tr = json.loads(trf.read_text(encoding="utf-8"))
        except ValueError as e:
            rep.err("E-JSON", f"en: {e}")
        if tr is not None and not rep.errors:
            validate_overlay(p, tr, ctx, rep)
    return p, tr, rep


def print_report(f: Path, p: dict | None, rep: Report, ctx: Context) -> None:
    level = ""
    if p is not None and not rep.errors:
        score, lvl = difficulty(p, ctx)
        level = f", dificultad {lvl} ({score})"
    print(f"{f.name}: {'ok' if not rep.errors else f'{len(rep.errors)} error(es)'}{level}")
    for c, m in rep.errors + rep.warnings:
        print(f"  {c} {m}")


def cmd_validate(paths: list[str]) -> int:
    ctx = Context.load()
    files = expand(paths or [str(PUZZLES)])
    if not files:
        print("no hay puzzles que validar", file=sys.stderr)
        return 1
    bad = 0
    for f in files:
        p, _, rep = check_file(f, ctx)
        print_report(f, p, rep, ctx)
        bad += bool(rep.errors)
    return 1 if bad else 0


def build(out: Path, published_only: bool = False) -> dict:
    ctx = Context.load()
    strings = load_strings()
    files = sorted(PUZZLES.glob("*.json"))
    if not files:
        raise BuildError("no hay puzzles en puzzles/")
    errors: list[str] = []
    loaded = []
    for f in files:
        p, tr, rep = check_file(f, ctx)
        errors += [f"{f.name}: {c} {m}" for c, m in rep.errors]
        for c, m in rep.warnings:
            print(f"aviso {f.name}: {c} {m}", file=sys.stderr)
        if p is not None:
            loaded.append((p, tr))
    if errors:
        raise BuildError("la validación falló:\n  " + "\n  ".join(errors))
    puzzles = [normalize(p, ctx, tr) for p, tr in loaded if not published_only or p["status"] == "published"]
    reg = ctx.services
    used = sorted(
        {n["icon"] for p in puzzles for n in p["nodes"]} | {t["service"] for p in puzzles for t in p["palette"]}
    )
    kinds = sorted({g["kind"] for p in puzzles for g in p["groups"] if g["kind"] in ctx.registry["groups"]})
    icon_dir = out / "icons"
    manifest_path = icon_dir / "manifest.json"
    if not manifest_path.exists():
        raise BuildError(f"falta {manifest_path}: corre scripts/fetch-icons.sh antes del build")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    # Nubes del selector: nombre, paquete y, si el registro lo define, el símbolo de su icono (gi-cloud-<id>)
    # y si ese icono ya es el nombre escrito (wordmark).
    clouds = {}
    for k, v in ctx.registry["clouds"].items():
        if k in CLOUDS:
            clouds[k] = {f: v[f] for f in ("label", "name", "package")}
            if "logo" in v:
                clouds[k]["logo"] = f"gi-cloud-{k}"
                if v.get("logo_wordmark"):
                    clouds[k]["wordmark"] = True
    logos = [f"cloud-{k}" for k, v in clouds.items() if "logo" in v]
    sprite = []
    for ident in [*used, *(f"group-{k}" for k in kinds), *logos]:
        if ident not in manifest:
            raise BuildError(f"el icono {ident} no se extrajo (vuelve a correr scripts/fetch-icons.sh)")
        sprite.append(svg_symbol((icon_dir / manifest[ident]["file"]).read_text(encoding="utf-8"), f"gi-{ident}"))
    data = {
        "version": 1,
        "built": date.today().isoformat(),
        "store_key": "dse_arch_v1",
        "clouds": clouds,
        "packages": [{k: pk[k] for k in ("id", "file", "url")} for pk in load_packages()],
        "categories": ctx.registry["categories"],
        "icons": {
            i: {k: reg[i][k] for k in ("label", "short", "category", "role", "cloud") if k in reg[i]}
            | ({"mode": reg[i]["mode"]} if "mode" in reg[i] else {})
            for i in used
        },
        "groupIcons": kinds,
        "sprite": "".join(sprite),
        "strings": strings,
        "puzzles": puzzles,
    }
    assets = out / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for name in APP_FILES:
        shutil.copyfile(APP / name, assets / name)
    (out / "game-data.js").write_text(
        "/* Generado por tools/build.py: no editar. */\nwindow.GAME = " + json.dumps(data, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )
    shutil.copyfile(APP / "index.html", out / "index.html")
    return data


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv else 2
    if argv[0] == "validate":
        return cmd_validate(argv[1:])
    if argv[0] == "build":
        out = ROOT / "dist"
        if "--out" in argv:
            i = argv.index("--out")
            if i + 1 >= len(argv):
                print("--out necesita una carpeta", file=sys.stderr)
                return 2
            out = Path(argv[i + 1]).resolve()
        try:
            data = build(out, published_only="--published-only" in argv)
        except BuildError as e:
            print(str(e), file=sys.stderr)
            return 1
        by_cloud: dict[str, int] = {}
        for p in data["puzzles"]:
            by_cloud[p["cloud"]] = by_cloud.get(p["cloud"], 0) + 1
        print(f"build: {len(data['puzzles'])} puzzles {by_cloud}, {len(data['icons'])} iconos -> {out}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
