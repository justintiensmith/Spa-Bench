from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


SOURCE = Path("/Users/justintiensmith/Documents/MSc_Thesis_Bar_Charts.xlsx")
OUT = Path(__file__).resolve().parent / "chart_ooxml_summary.json"

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
}
REL_NS = {"pr": "http://schemas.openxmlformats.org/package/2006/relationships"}


def resolve(base: str, target: str) -> str:
    parts = base.split("/")[:-1]
    for part in target.split("/"):
        if part == "..":
            parts.pop()
        elif part != ".":
            parts.append(part)
    return "/".join(parts)


def rels_path(part: str) -> str:
    directory, filename = part.rsplit("/", 1)
    return f"{directory}/_rels/{filename}.rels"


with zipfile.ZipFile(SOURCE) as zf:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    workbook_rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rel_map = {r.attrib["Id"]: resolve("xl/workbook.xml", r.attrib["Target"]) for r in workbook_rels}
    sheets = {}
    for sheet in workbook.find("x:sheets", NS):
        sheets[sheet.attrib["name"]] = rel_map[sheet.attrib[f"{{{NS['r']}}}id"]]

    theme = ET.fromstring(zf.read("xl/theme/theme1.xml"))
    scheme = {}
    scheme_root = theme.find("a:themeElements/a:clrScheme", NS)
    if scheme_root is not None:
        for child in scheme_root:
            color = next(iter(child), None)
            if color is not None:
                scheme[child.tag.rsplit("}", 1)[-1]] = color.attrib.get("val") or color.attrib.get("lastClr")

    summary = {"theme": scheme, "sheets": {}}
    for sheet_name, sheet_part in sheets.items():
        sheet_root = ET.fromstring(zf.read(sheet_part))
        drawing = sheet_root.find("x:drawing", NS)
        if drawing is None:
            continue
        sheet_rels = ET.fromstring(zf.read(rels_path(sheet_part)))
        sheet_rel_map = {r.attrib["Id"]: resolve(sheet_part, r.attrib["Target"]) for r in sheet_rels}
        drawing_part = sheet_rel_map[drawing.attrib[f"{{{NS['r']}}}id"]]
        drawing_root = ET.fromstring(zf.read(drawing_part))
        drawing_rels = ET.fromstring(zf.read(rels_path(drawing_part)))
        drawing_rel_map = {r.attrib["Id"]: resolve(drawing_part, r.attrib["Target"]) for r in drawing_rels}
        charts = []
        for anchor in drawing_root:
            chart_ref = anchor.find(".//c:chart", NS)
            if chart_ref is None:
                continue
            chart_part = drawing_rel_map[chart_ref.attrib[f"{{{NS['r']}}}id"]]
            chart_root = ET.fromstring(zf.read(chart_part))
            series = []
            for ser in chart_root.findall(".//c:ser", NS):
                title = ser.find(".//c:tx//c:v", NS)
                solid = ser.find("c:spPr/a:solidFill", NS)
                color = None
                if solid is not None and len(solid):
                    node = solid[0]
                    kind = node.tag.rsplit("}", 1)[-1]
                    raw = node.attrib.get("val")
                    color = {"kind": kind, "raw": raw, "resolved": scheme.get(raw, raw)}
                series.append({"title": title.text if title is not None else None, "color": color})
            pos = {}
            for tag in ["from", "to"]:
                node = anchor.find(f"{{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}}{tag}")
                if node is not None:
                    pos[tag] = {re.sub(r"^.*}", "", child.tag): int(child.text) for child in node}
            charts.append({"part": chart_part, "position": pos, "series": series})
        summary["sheets"][sheet_name] = charts

OUT.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps({"pi_blue": summary["sheets"].get("Pi0.5 Robustness"), "theme": scheme}, indent=2))
