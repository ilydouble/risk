"""Render manuscript illustrations and existing-result plots; no model execution."""

import json
import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path

import fitz
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
INK, MUTED = "#172B40", "#526579"
BLUE, TEAL, PURPLE, ORANGE = "#2563eb", "#087F8C", "#7354AD", "#B86A22"


class Diagram:
    def __init__(self, width, height):
        self.width, self.height = width, height
        self.lines = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="white"/>',
        ]

    def text(self, x, y, value, size=18, color=INK, bold=False, anchor="start"):
        weight = "bold" if bold else "normal"
        self.lines.append(
            f'<text x="{x}" y="{y}" font-family="Helvetica, Arial, sans-serif" '
            f'font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" '
            f'fill="{color}">{escape(value)}</text>'
        )

    def rect(self, x, y, w, h, fill="#F6F8FB", stroke="#CFD8E3", radius=10):
        self.lines.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        )

    def box(self, x, y, w, h, title, subtitle="", color=BLUE, fill="#F0F5FF"):
        self.rect(x, y, w, h, fill, color)
        self.text(x + w / 2, y + 30, title, 19, color, True, "middle")
        if subtitle:
            self.text(x + w / 2, y + 56, subtitle, 15, MUTED, anchor="middle")

    def path(self, points, color=MUTED, dashed=False, arrow=True):
        points = list(points)
        coords = " ".join(f"{x},{y}" for x, y in points)
        dash = 'stroke-dasharray="7 5"' if dashed else ""
        self.lines.append(
            f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="2" {dash}/>'
        )
        if arrow:
            x, y = points[-1]
            px, py = points[-2]
            dx, dy = x - px, y - py
            length = (dx * dx + dy * dy) ** 0.5
            ux, uy = dx / length, dy / length
            verts = [
                (x, y),
                (x - 10 * ux + 4 * uy, y - 10 * uy - 4 * ux),
                (x - 10 * ux - 4 * uy, y - 10 * uy + 4 * ux),
            ]
            coords = " ".join(f"{a},{b}" for a, b in verts)
            self.lines.append(f'<polygon points="{coords}" fill="{color}"/>')

    def circle(self, x, y, r, label, color=BLUE):
        self.lines.append(
            f'<circle cx="{x}" cy="{y}" r="{r}" fill="white" stroke="{color}" stroke-width="2"/>'
        )
        self.text(x, y + 6, label, 18, color, True, "middle")

    def save(self, name):
        svg = ROOT / f"{name}.svg"
        svg.write_text("\n".join(self.lines + ["</svg>"]) + "\n")
        ET.parse(svg)
        with fitz.open(svg) as source:
            pdf = source.convert_to_pdf()
        with fitz.open("pdf", pdf) as document:
            document.save(ROOT / f"{name}.pdf")
            document[0].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False).save(ROOT / f"{name}.png")


def problem():
    d = Diagram(1440, 650)
    d.text(
        40, 45, "Relational evidence: predicting status and deciding what to review", 27, bold=True
    )
    for x, title in [
        (40, "(a) Public records"),
        (510, "(b) Corporate graph"),
        (980, "(c) Two distinct decisions"),
    ]:
        d.rect(x, 80, 420, 500)
        d.text(x + 22, 115, title, 22, bold=True)
    d.box(70, 155, 360, 80, "Companies House", "Registry records and director attributes")
    d.box(70, 260, 360, 80, "GLEIF", "Legal-entity records and relationships")
    d.text(70, 385, "233,251 firms", 27, BLUE, True)
    d.text(70, 425, "412,348 directed edges", 25, BLUE, True)
    d.text(70, 475, "Address-group split", 20, bold=True)
    d.text(70, 505, "Train / validation / test snapshots", 17, MUTED)
    d.text(70, 545, "Labels: contemporaneous registry status", 16, MUTED)
    d.path([(460, 305), (510, 305)], BLUE)
    # Schematic topology: connections illustrate relation semantics, not observations.
    d.path([(720, 257), (614, 205)], BLUE, True, False)
    d.path([(720, 257), (832, 205)], TEAL, False, False)
    d.path([(720, 297), (620, 355)], BLUE, True, False)
    d.path([(720, 297), (825, 355)], PURPLE, True, False)
    for x, y, label, c in [
        (720, 277, "Firm", INK),
        (595, 195, "A", BLUE),
        (850, 195, "B", TEAL),
        (600, 367, "C", BLUE),
        (845, 367, "D", PURPLE),
    ]:
        d.circle(x, y, 32 if label == "Firm" else 24, label, c)
    for y, c, dash, label in [
        (427, BLUE, True, "Shared address"),
        (462, TEAL, False, "Registered ownership"),
        (497, PURPLE, True, "Name-based association"),
    ]:
        d.path([(540, y - 6), (582, y - 6)], c, dash, False)
        d.text(595, y, label, 17)
    d.text(540, 545, "A recorded link need not imply similar risk.", 16, MUTED)
    d.path([(930, 305), (980, 305)], BLUE)
    d.box(
        1010,
        155,
        360,
        100,
        "Predict corporate status",
        "Rank firms by distress probability",
        TEAL,
        "#EDF8F7",
    )
    d.text(1030, 285, "Evaluate: average precision", 18, TEAL)
    d.box(
        1010,
        335,
        360,
        100,
        "Prioritize review",
        "Rank predictions by need for scrutiny",
        PURPLE,
        "#F5F1FB",
    )
    d.text(1030, 465, "Evaluate: retained error vs coverage", 17, PURPLE)
    d.text(1010, 530, "Research question:", 18, bold=True)
    d.text(1010, 556, "Does conflict add error information?", 17)
    d.text(
        40,
        618,
        "Conceptual graph only. Dataset counts are observed; the "
        "additional value of conflict is the hypothesis under study.",
        17,
        MUTED,
    )
    d.save("figure-1-problem")


def architecture():
    d = Diagram(1500, 850)
    d.text(
        40, 45, "RiskGNN++: classification, evidence learning, and selective review", 27, bold=True
    )
    d.rect(40, 80, 1420, 175, "#F1F8F8", "#D0E4E4")
    d.rect(40, 280, 1420, 255, "#F7F3FB", "#E1D6EE")
    d.rect(40, 560, 1420, 170, "#FCF7F0", "#EBD9C4")
    d.text(60, 111, "A  PRIMARY PREDICTION", 16, TEAL, True)
    d.text(415, 311, "B  EVIDENTIAL OPINIONS AND REVIEW", 16, PURPLE, True)
    d.text(60, 591, "C  AUXILIARY FUSION", 16, ORANGE, True)
    # Arrows laid out before boxes; each lane uses a separate horizontal corridor.
    d.path([(300, 185), (380, 185)], TEAL)
    d.path([(665, 185), (750, 185)], TEAL)
    d.path([(1000, 185), (1090, 185)], TEAL)
    d.path([(1270, 220), (1270, 345)], TEAL)
    d.text(1285, 273, "calibrated p", 15, TEAL)
    d.path([(180, 225), (180, 355)], PURPLE)
    d.path([(345, 400), (415, 400)], PURPLE)
    d.path([(700, 400), (755, 400)], PURPLE)
    d.path([(1000, 400), (1090, 400)], PURPLE)
    d.text(1020, 388, "C", 17, PURPLE, True)
    # Branch of opinion bundle to fusion; no inference feedback into primary head.
    d.path([(530, 445), (530, 625)], ORANGE)
    d.text(544, 549, "opinions + degree", 15, ORANGE)
    d.path([(700, 665), (755, 665)], ORANGE)
    d.path([(1000, 665), (1090, 665)], ORANGE)
    d.box(75, 145, 225, 80, "Shared backbone", "Intrinsic + graph + hypergraph", TEAL, "#FFFFFF")
    d.box(
        380,
        145,
        285,
        80,
        "Learned representation mix",
        "Node and graph representations",
        TEAL,
        "#FFFFFF",
    )
    d.box(750, 145, 250, 80, "Primary softmax head", "Discriminative prediction", TEAL, "#FFFFFF")
    d.box(
        1090,
        145,
        320,
        80,
        "Probability calibration",
        "UK: isotonic / SMEsD: Platt",
        TEAL,
        "#FFFFFF",
    )
    d.box(75, 355, 270, 90, "Evidential heads", "Node + relation-conditioned", PURPLE, "#FFFFFF")
    d.box(415, 355, 285, 90, "Opinion bundle", "Node and relation opinions", PURPLE, "#FFFFFF")
    d.box(
        755, 355, 245, 90, "Composite conflict C", "Computed before discounting", PURPLE, "#FFFFFF"
    )
    d.box(1090, 345, 320, 110, "Review score", "ambiguity(p) + gamma * C", PURPLE, "#FFFFFF")
    d.text(1250, 428, "Defer the highest scores", 16, PURPLE, anchor="middle")
    d.text(85, 488, "Relation pooling includes self;", 16, MUTED)
    d.text(85, 514, "missing relations still yield opinions.", 16, MUTED)
    d.text(755, 488, "Shared representations:", 16, MUTED)
    d.text(755, 514, "opinions are not independent sources.", 16, MUTED)
    d.text(1108, 500, "Evaluate at matched review budgets", 16, PURPLE)
    d.box(
        415,
        625,
        285,
        85,
        "Conflict / degree discount",
        "Applied to relation opinions",
        ORANGE,
        "#FFFFFF",
    )
    d.box(755, 625, 245, 85, "Dempster fusion", "Then degree-based scaling", ORANGE, "#FFFFFF")
    d.box(
        1090,
        625,
        320,
        85,
        "Auxiliary objective",
        "Fused evidence + KL regularization",
        ORANGE,
        "#FFFFFF",
    )
    d.text(75, 630, "Training coupling", 19, ORANGE, True)
    d.text(75, 662, "Auxiliary losses update", 17, MUTED)
    d.text(75, 689, "shared model parameters.", 17, MUTED)
    for x, c, label in [
        (40, TEAL, "Primary probabilities"),
        (415, PURPLE, "Opinion / conflict features"),
        (855, ORANGE, "Auxiliary evidence pathway"),
    ]:
        d.path([(x, 775), (x + 40, 775)], c)
        d.text(x + 52, 781, label, 17, c)
    d.text(
        40,
        823,
        "Implemented paths. The primary head does not consume fused "
        "probabilities; scalar fused uncertainty is a separate review "
        "baseline.",
        17,
        MUTED,
    )
    d.save("figure-2-architecture")


def results():
    data = json.loads((ROOT / "existing-results.json").read_text())
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
        }
    )
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.6), gridspec_kw={"width_ratios": [1.1, 1, 1]})
    names = data["uk_ap"]["models"]
    means = data["uk_ap"]["mean"]
    sd = data["uk_ap"]["sample_sd"]
    ax = axes[0]
    ax.barh(
        names,
        means,
        xerr=sd,
        color=["#97A8B8", "#BAC5D0", "#9EB6D4", TEAL],
        height=0.58,
        error_kw={"ecolor": INK, "capsize": 3, "linewidth": 1.2},
    )
    ax.invert_yaxis()
    ax.set_xlim(0, 42)
    ax.set_xlabel("Average precision (%)")
    ax.set_title("(a) UK discrimination", loc="left", weight="bold", pad=18)
    for i, (m, e) in enumerate(zip(means, sd, strict=True)):
        ax.text(m + e + 0.7, i, f"{m:.2f}", va="center", fontsize=10)
    for ax, key, title, limit in [
        (axes[1], "uk_aurc", "(b) UK selective review", 0.06),
        (axes[2], "smesd_aurc", "(c) SMEsD selective review", 0.25),
    ]:
        vals = data[key]["mean"]
        ax.barh(
            ["Probability\nambiguity", "Scalar\nuncertainty", "Conflict-guided\nranking"],
            vals,
            color=["#97A8B8", "#C7B9D9", TEAL],
            height=0.55,
        )
        ax.invert_yaxis()
        ax.set_xlim(0, limit)
        ax.set_xlabel("AURC (lower is better)")
        ax.set_title(title, loc="left", weight="bold", pad=18)
        for i, v in enumerate(vals):
            ax.text(v + limit * 0.025, i, f"{v:.4f}", va="center", fontsize=10)
    for ax in axes:
        ax.set_axisbelow(True)
        ax.grid(axis="x", color="#E5EAF0", linewidth=0.8)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
    fig.subplots_adjust(left=0.09, right=0.98, top=0.77, bottom=0.34, wspace=0.62)
    fig.text(
        0.04,
        0.94,
        "Existing results: discrimination and review gains are different claims",
        fontsize=17,
        weight="bold",
        color=INK,
    )
    fig.text(
        0.04,
        0.88,
        "Completed ten-seed runs on fixed splits. No hypothetical results are plotted.",
        fontsize=11,
        color=MUTED,
    )
    fig.text(
        0.04,
        0.18,
        "UK AP: +3.88 pp vs ComRisk (p = 0.027); +0.08 pp vs RiskGNN+ (p "
        "= 0.965). Error bars: sample SD across seeds.",
        fontsize=10,
        color=MUTED,
    )
    fig.text(
        0.04,
        0.12,
        "UK AURC: conflict vs ambiguity p = 0.0023. At 70% automatic "
        "coverage: p = 0.2765 (no significant gain).",
        fontsize=10,
        color=MUTED,
    )
    fig.text(
        0.04,
        0.06,
        "SMEsD AURC: conflict vs ambiguity p = 0.063 (no benefit). AURC "
        "bars show means only. All p values: paired t tests.",
        fontsize=10,
        color=MUTED,
    )
    for ext in ["svg", "pdf", "png"]:
        fig.savefig(ROOT / f"figure-3-existing-results.{ext}", dpi=240, facecolor="white")
    svg = ROOT / "figure-3-existing-results.svg"
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
    plt.close(fig)


if __name__ == "__main__":
    problem()
    architecture()
    results()
    print("Rendered three figures in SVG, PDF and PNG.")
