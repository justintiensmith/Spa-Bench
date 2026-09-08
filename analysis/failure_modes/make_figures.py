from __future__ import annotations

import json
import os
import subprocess
import textwrap
from pathlib import Path

from reportlab.graphics import renderPDF, renderSVG
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib.colors import HexColor, white


ROOT = Path(__file__).resolve().parent
PAYLOAD = ROOT / "analysis_payload.json"
FIG_DIR = ROOT / "figures"

OBSERVED = "#B8DDAA"
WITHHELD = "#E6B0A5"
ABSENT = "#E7E7E7"
HEADER = "#F3F3F3"
INK = "#1F2933"
GRID = "#2D2D2D"

MODE_COLORS = {
    "Wrong target": "#3B6FB6",
    "No action": "#E1A43B",
    "Correct target, incorrect spatial outcome": "#5AAE61",
    "Grasp failure": "#9B6FB0",
    "Premature release or dropped object": "#E76F51",
    "Timeout or incomplete execution": "#6C757D",
    "Other execution failure": "#8C6D4F",
    "Unannotated or unclear": "#D9D9D9",
}


def wrap(value: str, width: int) -> list[str]:
    return textwrap.wrap(
        value.replace("\n", " "), width=width, break_long_words=False, break_on_hyphens=False
    ) or [""]


class Figure:
    """Small top-left-coordinate wrapper around a ReportLab vector Drawing."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.drawing = Drawing(width, height)
        self.rect(0, 0, width, height, "#FFFFFF", "#FFFFFF", 0)

    def rect(self, x: float, y: float, w: float, h: float, fill: str, stroke: str = GRID, stroke_width: float = 1) -> None:
        self.drawing.add(
            Rect(
                x,
                self.height - y - h,
                w,
                h,
                rx=0,
                ry=0,
                fillColor=HexColor(fill),
                strokeColor=HexColor(stroke),
                strokeWidth=stroke_width,
            )
        )

    def line(self, x1: float, y1: float, x2: float, y2: float, color: str, width: float = 1) -> None:
        self.drawing.add(
            Line(
                x1,
                self.height - y1,
                x2,
                self.height - y2,
                strokeColor=HexColor(color),
                strokeWidth=width,
            )
        )

    def text(
        self,
        x: float,
        y: float,
        value: str,
        size: float = 18,
        anchor: str = "middle",
        bold: bool = False,
        fill: str = INK,
        lines: list[str] | None = None,
        line_height: float | None = None,
    ) -> None:
        use_lines = lines if lines is not None else [value]
        lh = line_height or size * 1.16
        first_center_y = y - (len(use_lines) - 1) * lh / 2
        for idx, line in enumerate(use_lines):
            center_y = first_center_y + idx * lh
            self.drawing.add(
                String(
                    x,
                    self.height - center_y - size * 0.34,
                    line,
                    fontName="Helvetica-Bold" if bold else "Helvetica",
                    fontSize=size,
                    fillColor=HexColor(fill),
                    textAnchor=anchor,
                )
            )

    def save(self, stem: Path) -> None:
        renderSVG.drawToFile(self.drawing, str(stem.with_suffix(".svg")))
        renderPDF.drawToFile(self.drawing, str(stem.with_suffix(".pdf")))
        font_cache = Path("/private/tmp/spa-bench-font-cache")
        font_cache.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["FONTCONFIG_FILE"] = "/opt/homebrew/etc/fonts/fonts.conf"
        env["XDG_CACHE_HOME"] = str(font_cache)
        subprocess.run(
            [
                "pdftoppm",
                "-png",
                "-r",
                "120",
                "-singlefile",
                str(stem.with_suffix(".pdf")),
                str(stem),
            ],
            check=True,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def matrix_group(fig: Figure, matrix: dict, x: float, y: float, width: float, height: float) -> None:
    rows = matrix["rows"]
    cols = matrix["columns"]
    values = matrix["values"]
    title_h = 42
    header_h = 64
    row_label_w = max(102, min(165, width * 0.22))
    cell_w = (width - row_label_w) / len(cols)
    cell_h = (height - title_h - header_h) / len(rows)
    context = f" — {matrix['context']}" if matrix["context"] else ""
    fig.text(x + width / 2, y + 22, f"{matrix['task']}{context}", 21, bold=True)

    table_y = y + title_h
    fig.rect(x, table_y, row_label_w, header_h, HEADER, GRID, 1.4)
    fig.text(x + row_label_w / 2, table_y + header_h / 2, "", 14, bold=True, lines=["Concept /", "argument"])
    for j, col in enumerate(cols):
        cx = x + row_label_w + j * cell_w
        fig.rect(cx, table_y, cell_w, header_h, HEADER, GRID, 1.4)
        fig.text(cx + cell_w / 2, table_y + header_h / 2, "", 13, bold=True, lines=wrap(col, max(9, int(cell_w / 9))))
    for i, row in enumerate(rows):
        cy = table_y + header_h + i * cell_h
        fig.rect(x, cy, row_label_w, cell_h, HEADER, GRID, 1.4)
        fig.text(x + row_label_w / 2, cy + cell_h / 2, row, 15, bold=True)
        for j, status in enumerate(values[i]):
            cx = x + row_label_w + j * cell_w
            fill = OBSERVED if status == "Observed" else WITHHELD if status == "Withheld" else ABSENT
            display = "Absent" if status == "Absent" else "—" if status == "N/A" else status
            fig.rect(cx, cy, cell_w, cell_h, fill, GRID, 1.4)
            fig.text(cx + cell_w / 2, cy + cell_h / 2, display, 14)


def make_matrix_overview(payload: dict) -> None:
    matrices = payload["matrices"]
    by_key = {(m["task"], m["context"]): m for m in matrices}
    fig = Figure(1800, 1800)
    fig.text(900, 40, "Spa-Bench training exposure and held-out spatial bindings", 30, bold=True)
    matrix_group(fig, by_key[("Physical State", "")], 55, 70, 820, 320)
    matrix_group(fig, by_key[("Ordinal Position", "2-object sequences")], 925, 70, 820, 285)
    matrix_group(fig, by_key[("Relative Size", "")], 55, 410, 820, 245)
    matrix_group(fig, by_key[("Ordinal Position", "3-object sequences")], 925, 375, 820, 325)
    matrix_group(fig, by_key[("Referential Description", "")], 55, 690, 820, 285)
    matrix_group(fig, by_key[("Ordinal Position", "4-object sequences")], 925, 725, 820, 370)
    matrix_group(fig, by_key[("Counting", "")], 55, 1015, 640, 325)

    legend_x, legend_y = 760, 1135
    for i, (label, color) in enumerate(
        [("Observed binding", OBSERVED), ("Withheld binding", WITHHELD), ("Absent / N.A.", ABSENT)]
    ):
        yy = legend_y + i * 45
        fig.rect(legend_x, yy - 16, 30, 30, color, GRID, 1)
        fig.text(legend_x + 45, yy, label, 18, anchor="start")
    note = wrap(
        "A withheld cell retains physical trajectory coverage under a direct or familiar instruction; only the spatial concept–argument binding is absent.",
        72,
    )
    fig.text(1220, 1282, "", 16, lines=note)
    matrix_group(fig, by_key[("Relational Placement", "")], 55, 1390, 1690, 350)
    fig.save(FIG_DIR / "missing_cell_matrices")

    for i, matrix in enumerate(matrices, start=1):
        w = 1500 if matrix["task"] == "Relational Placement" else 980
        h = 430 if len(matrix["rows"]) <= 2 else 520 if len(matrix["rows"]) == 3 else 600
        task_fig = Figure(w, h)
        matrix_group(task_fig, matrix, 40, 30, w - 80, h - 70)
        slug = matrix["task"].lower().replace(" ", "_")
        if matrix["context"]:
            slug += "_" + matrix["context"].split("-")[0]
        task_fig.save(FIG_DIR / f"matrix_{i:02d}_{slug}")


def stacked_bar_figure(labels: list[str], counts: list[dict], modes: list[str], title: str, width: int, height: int) -> Figure:
    fig = Figure(width, height)
    left_margin, right_margin, top_margin, bottom_margin = 320, 120, 95, 205
    plot_x, plot_y = left_margin, top_margin
    plot_w, plot_h = width - left_margin - right_margin, height - top_margin - bottom_margin
    row_h = plot_h / len(labels)
    bar_h = min(56, row_h * 0.58)
    fig.text(width / 2, 45, title, 28, bold=True)
    for tick in range(0, 101, 20):
        x = plot_x + plot_w * tick / 100
        fig.line(x, plot_y, x, plot_y + plot_h, "#D8D8D8", 1.2)
        fig.text(x, plot_y + plot_h + 32, f"{tick}%", 15)
    for i, (label, row) in enumerate(zip(labels, counts)):
        total = sum(int(row.get(mode, 0)) for mode in modes)
        y = plot_y + i * row_h + row_h / 2
        fig.text(plot_x - 18, y, label, 17, anchor="end", bold=True)
        x = plot_x
        for mode in modes:
            count = int(row.get(mode, 0))
            pct = count / total * 100 if total else 0
            seg_w = plot_w * pct / 100
            if seg_w > 0:
                fig.rect(x, y - bar_h / 2, seg_w, bar_h, MODE_COLORS[mode], "#FFFFFF", 1)
                if seg_w >= 54:
                    text_fill = "#FFFFFF" if mode in {"Wrong target", "Other execution failure", "Timeout or incomplete execution"} else INK
                    fig.text(x + seg_w / 2, y, str(count), 15, bold=True, fill=text_fill)
            x += seg_w
        fig.text(plot_x + plot_w + 18, y, f"n={total}", 15, anchor="start")
    fig.text(plot_x + plot_w / 2, plot_y + plot_h + 63, "Share of failed novel-spatial-grounding rollouts", 18, bold=True)

    legend_y = height - 112
    legend_item_w = (width - 100) / 4
    for i, mode in enumerate(modes):
        row, col = divmod(i, 4)
        x = 55 + col * legend_item_w
        y = legend_y + row * 42
        fig.rect(x, y - 14, 25, 25, MODE_COLORS[mode], MODE_COLORS[mode], 0)
        fig.text(x + 36, y, mode, 14, anchor="start")
    return fig


def make_failure_figures(payload: dict) -> None:
    modes = payload["mode_order"]
    tasks = payload["task_order"]
    task_counts = [payload["task_counts"][task] for task in tasks]
    task_fig = stacked_bar_figure(tasks, task_counts, modes, "Failure modes are strongly task-dependent", 1750, 900)
    task_fig.save(FIG_DIR / "failure_modes_by_task")

    models = payload["complete_models"]
    model_counts = [payload["model_counts"][model] for model in models]
    model_fig = stacked_bar_figure(models, model_counts, modes, "Failure-mode composition by model", 1650, 650)
    model_fig.save(FIG_DIR / "failure_modes_by_model")


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.loads(PAYLOAD.read_text(encoding="utf-8"))
    make_matrix_overview(payload)
    make_failure_figures(payload)
    print(f"Wrote figures to {FIG_DIR}")


if __name__ == "__main__":
    main()
