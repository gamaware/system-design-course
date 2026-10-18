"""Pruebas del validador y de la extracción de iconos (tools/build.py, tools/icons.py).

python3 -m unittest discover -s tests
"""

from __future__ import annotations

import base64
import copy
import json
import sys
import unittest
import urllib.parse
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build as bld  # noqa: E402
import icons as icn  # noqa: E402

CTX = bld.Context.load()


def load(cloud: str) -> tuple[dict, dict]:
    p = json.loads((ROOT / "puzzles" / f"e02-{cloud}.json").read_text(encoding="utf-8"))
    tr = json.loads((ROOT / "puzzles" / "en" / f"e02-{cloud}.json").read_text(encoding="utf-8"))
    return p, tr


def codes(p: dict, tr: dict | None = None) -> set[str]:
    rep = bld.validate(p, CTX, p.get("id"))
    if tr is not None and not rep.errors:
        bld.validate_overlay(p, tr, CTX, rep)
    return {c for c, _ in rep.errors}


class PilotTest(unittest.TestCase):
    def test_four_pilots_are_clean(self):
        for cloud in bld.CLOUDS:
            p, tr = load(cloud)
            rep = bld.validate(p, CTX, p["id"])
            bld.validate_overlay(p, tr, CTX, rep)
            self.assertEqual(rep.errors, [], cloud)
            self.assertEqual(rep.warnings, [], cloud)
            self.assertEqual(bld.difficulty(p, CTX)[1], "medium")

    def test_every_registry_icon_has_a_source(self):
        for sid, svc in CTX.services.items():
            icon = svc["icon"]
            self.assertTrue({"builtin", "file", "shape"} & set(icon), sid)
            if "builtin" not in icon:
                self.assertIn(icon["package"], {"aws", "azure", "gcp-core", "gcp-category", "oci"}, sid)


class RuleTest(unittest.TestCase):
    def setUp(self):
        self.p, self.tr = load("aws")

    def test_leak_in_requirement(self):
        q = copy.deepcopy(self.p)
        q["requirements"][0]["text"] = "{{s1}} son instancias EC2 con sistema operativo que el equipo parcha."
        q["slots"][0]["hint_cue"] = "sistema operativo"
        self.assertIn("E-LEAK", codes(q))

    def test_leak_in_edge_and_group_label(self):
        q = copy.deepcopy(self.p)
        q["edges"][1]["label"] = "al ALB"
        self.assertIn("E-LEAK", codes(q))
        q = copy.deepcopy(self.p)
        q["groups"][1]["label"] = "Grupo de Auto Scaling"
        self.assertIn("E-LEAK", codes(q))

    def test_spanish_and_english_articles(self):
        q = copy.deepcopy(self.p)
        q["requirements"][1]["text"] = "Un {{s2}} mantiene de 2 a 20 copias y reemplaza las que fallan."
        self.assertIn("E-ARTICLE", codes(q))
        t = copy.deepcopy(self.tr)
        t["requirements"]["2"] = "A {{s2}} keeps 2 to 20 copies and replaces the ones that fail."
        t["slots"]["s2"]["hint_cue"] = "replaces the ones that fail"
        self.assertIn("E-ARTICLE", codes(self.p, t))

    def test_english_overlay_leak_and_tokens(self):
        t = copy.deepcopy(self.tr)
        t["requirements"]["3"] = (
            "{{s3}} is an Application Load Balancer that sends /api to one group and /tienda to another."
        )
        self.assertIn("E-LEAK", codes(self.p, t))
        t = copy.deepcopy(self.tr)
        t["requirements"]["4"] = "Issues and renews on its own the public certificate for tienda.mx."
        self.assertIn("E-TOKEN", codes(self.p, t))

    def test_service_from_another_cloud(self):
        q = copy.deepcopy(self.p)
        q["palette"].append({"service": "azure-functions", "role": "filler"})
        self.assertIn("E-CLOUD", codes(q))

    def test_slot_refs_must_be_in_source_refs(self):
        q = copy.deepcopy(self.p)
        q["slots"][0]["refs"] = ["https://example.com/doc"]
        self.assertIn("E-SRC", codes(q))

    def test_geometry_overlap_and_steps(self):
        q = copy.deepcopy(self.p)
        q["nodes"][2]["cell"] = {"c": 3.3, "r": 2.5}
        self.assertIn("E-GEOM", codes(q))
        q = copy.deepcopy(self.p)
        q["edges"][0]["step"] = 9
        self.assertIn("E-STEP", codes(q))

    def test_cue_tokens_palette_and_near_miss(self):
        q = copy.deepcopy(self.p)
        q["slots"][0]["hint_cue"] = "no aparece en el requisito"
        self.assertIn("E-CUE", codes(q))
        q = copy.deepcopy(self.p)
        q["requirements"][0]["text"] = "Servidores con sistema operativo que el equipo parcha."
        self.assertIn("E-TOKEN", codes(q))
        q = copy.deepcopy(self.p)
        q["palette"] = [t for t in q["palette"] if t["service"] != "aws-nlb"]
        self.assertIn("E-NEARMISS", codes(q))

    def test_id_must_match_scenario_cloud_and_file(self):
        q = copy.deepcopy(self.p)
        q["cloud"] = "gcp"
        self.assertIn("E-ID", codes(q))
        rep = bld.validate(self.p, CTX, "otro-nombre")
        self.assertIn("E-ID", {c for c, _ in rep.errors})

    def test_schema_rejects_unknown_fields(self):
        q = copy.deepcopy(self.p)
        q["source_qids"] = ["123"]
        self.assertEqual(codes(q), {"E-SCHEMA"})

    def test_em_dash(self):
        q = copy.deepcopy(self.p)
        q["slots"][0]["explanation"] = q["slots"][0]["explanation"] + " — fin."
        self.assertIn("E-EXPL", codes(q))


class SymbolTest(unittest.TestCase):
    def test_ids_and_classes_are_prefixed(self):
        raw = (
            '<?xml version="1.0"?><svg viewBox="0 0 512 512"><defs><style>.st0{fill:none}.st1{fill:#4285f4}'
            '</style><linearGradient id="g"/></defs><title>x</title><path class="st1" fill="url(#g)" id="unused"/>'
            '<rect class="st0"/></svg>'
        )
        sym = bld.svg_symbol(raw, "gi-x")
        self.assertIn('<symbol id="gi-x" viewBox="0 0 512 512">', sym)
        self.assertIn(".gi-x-st1{fill:#4285f4}", sym)
        self.assertIn('class="gi-x-st1"', sym)
        self.assertIn("url(#gi-x-g)", sym)
        self.assertNotIn('id="unused"', sym)
        self.assertNotIn("<title>", sym)

    def test_viewbox_from_size(self):
        self.assertIn('viewBox="0 0 18 18"', bld.svg_symbol('<svg width="18" height="18"><path/></svg>', "gi-a"))


class OciStencilTest(unittest.TestCase):
    @staticmethod
    def pack(text: str) -> str:
        comp = zlib.compressobj(9, zlib.DEFLATED, -15)
        raw = comp.compress(urllib.parse.quote(text).encode()) + comp.flush()
        return base64.b64encode(raw).decode()

    def test_stencil_geometry_is_scaled_to_the_cell(self):
        stencil = (
            '<shape strokewidth="inherit"><foreground><path><move x="0" y="0"/><line x="100" y="0"/>'
            '<curve x1="100" y1="50" x2="50" y2="100" x3="0" y3="100"/><close/></path><fillstroke/>'
            "</foreground></shape>"
        )
        model = (
            '<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
            '<mxCell id="2" style="group" parent="1"><mxGeometry x="10" y="0" width="84" height="84" as="geometry"/>'
            '</mxCell><mxCell id="3" style="fillColor=#2d5967;strokeColor=none;shape=stencil('
            + self.pack(stencil)
            + ');" parent="2"><mxGeometry x="2" y="2" width="80" height="40" as="geometry"/></mxCell>'
            '<mxCell id="4" value="Etiqueta" style="fillColor=none;shape=stencil('
            + self.pack(stencil)
            + ');" parent="2"><mxGeometry y="90" width="84" height="20" as="geometry"/></mxCell></root></mxGraphModel>'
        )
        svg = icn.oci_svg({"title": "prueba", "xml": self.pack(model)})
        self.assertIn('viewBox="12 2 80 40"', svg)
        self.assertIn('d="M12 2L92 2C92 22 52 42 12 42Z" fill="#2d5967"', svg)
        self.assertEqual(svg.count("<path"), 1)


if __name__ == "__main__":
    unittest.main()
