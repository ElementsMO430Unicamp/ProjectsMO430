"""Gera assets/images/modelo-logico-grafos.png — modelo lógico de grafos do projeto P3."""

from __future__ import annotations

from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "images" / "modelo-logico-grafos.png"

# Paleta alinhada ao tema bioinformática / medallion
COLORS = {
    "gene": ("#E8F4FD", "#1565C0"),
    "disease": ("#FCE4EC", "#AD1457"),
    "pathway": ("#E8F5E9", "#2E7D32"),
    "ppi": "#546E7A",
    "pathway_edge": "#388E3C",
    "assoc_edge": "#C62828",
    "title_bg": "#263238",
    "layer": "#FFF8E1",
    "layer_border": "#F9A825",
}


def draw_node_box(
    ax,
    x: float,
    y: float,
    width: float,
    height: float,
    title: str,
    attrs: list[str],
    face: str,
    edge: str,
) -> None:
    box = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=2,
        edgecolor=edge,
        facecolor=face,
        zorder=2,
    )
    ax.add_patch(box)

    ax.text(
        x + width / 2,
        y + height - 0.35,
        title,
        ha="center",
        va="top",
        fontsize=11,
        fontweight="bold",
        color=edge,
        zorder=3,
    )
    ax.text(
        x + 0.15,
        y + height - 0.75,
        "Atributos:",
        ha="left",
        va="top",
        fontsize=8,
        fontstyle="italic",
        color="#455A64",
        zorder=3,
    )
    for i, attr in enumerate(attrs):
        ax.text(
            x + 0.2,
            y + height - 1.05 - i * 0.32,
            f"• {attr}",
            ha="left",
            va="top",
            fontsize=8.5,
            family="monospace",
            color="#37474F",
            zorder=3,
        )


def draw_edge_label(ax, x: float, y: float, text: str, color: str, rotation: float = 0) -> None:
    ax.text(
        x,
        y,
        text,
        ha="center",
        va="center",
        fontsize=7.5,
        color=color,
        fontweight="bold",
        rotation=rotation,
        bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor=color, alpha=0.95),
        zorder=4,
    )


def main() -> None:
    fig, ax = plt.subplots(figsize=(14, 9), dpi=150)
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 9)
    ax.axis("off")
    fig.patch.set_facecolor("#FAFAFA")

    # Título
    ax.add_patch(
        FancyBboxPatch(
            (0.3, 8.15),
            13.4,
            0.7,
            boxstyle="round,pad=0.02",
            facecolor=COLORS["title_bg"],
            edgecolor="none",
            zorder=1,
        )
    )
    ax.text(
        7,
        8.5,
        "Modelo Lógico de Grafos — Integração Multi-ômica Long COVID (P3 MO430)",
        ha="center",
        va="center",
        fontsize=13,
        fontweight="bold",
        color="white",
        zorder=2,
    )
    ax.text(
        7,
        7.85,
        "Nós tipados · Arestas ponderadas · Fontes: GEO · EBI · STRING-DB · KEGG · NIH · OpenTargets",
        ha="center",
        va="center",
        fontsize=8.5,
        color="#607D8B",
        zorder=2,
    )

    # Nós
    draw_node_box(
        ax, 0.5, 3.8, 3.6, 3.2,
        "Gene / Proteína",
        ["symbol", "geneid", "log2foldchange", "pvalue", "padj", "description", "string_id"],
        *COLORS["gene"],
    )
    draw_node_box(
        ax, 5.2, 5.5, 3.4, 2.4,
        "Gene / Proteína (par)",
        ["node1, node2", "preferredName", "9606.ENSP…"],
        *COLORS["gene"],
    )
    draw_node_box(
        ax, 9.8, 5.5, 3.5, 2.5,
        "Área KEGG / Pathway",
        ["idarea", "title (K#####)", "map05171", "log2FC agregado"],
        *COLORS["pathway"],
    )
    draw_node_box(
        ax, 9.8, 1.8, 3.5, 2.8,
        "Doença / Fenótipo",
        ["pasc_status", "symptom_cluster", "severity_score", "target_id (OpenTargets)"],
        *COLORS["disease"],
    )

    # Camada medallion (contexto)
    layer = FancyBboxPatch(
        (0.4, 0.35),
        8.8,
        1.2,
        boxstyle="round,pad=0.02",
        linewidth=1.5,
        edgecolor=COLORS["layer_border"],
        facecolor=COLORS["layer"],
        linestyle="--",
        zorder=1,
    )
    ax.add_patch(layer)
    ax.text(
        4.8,
        1.25,
        "Pipeline Medallion (Airflow)",
        ha="center",
        fontsize=9,
        fontweight="bold",
        color="#E65100",
    )
    ax.text(
        4.8,
        0.75,
        "Bronze → Silver → Gold  |  silver_geo_nodes · gold_geo_nodes · gold_edge_ppi",
        ha="center",
        fontsize=8,
        color="#795548",
    )

    # Arestas PPI (Gene ↔ Gene par)
    ax.add_patch(
        FancyArrowPatch(
            (4.1, 5.4),
            (5.2, 6.2),
            arrowstyle="-|>",
            mutation_scale=14,
            linewidth=2,
            color=COLORS["ppi"],
            connectionstyle="arc3,rad=0.1",
            zorder=2,
        )
    )
    draw_edge_label(ax, 4.55, 6.0, "INTERAÇÃO_PPI", COLORS["ppi"], rotation=18)

    # Self-loop PPI hint on gene box
    ax.add_patch(
        FancyArrowPatch(
            (1.5, 3.8),
            (3.0, 3.8),
            arrowstyle="-|>",
            mutation_scale=12,
            linewidth=1.8,
            color=COLORS["ppi"],
            connectionstyle="arc3,rad=-0.6",
            zorder=2,
        )
    )

    # Gene → Pathway area
    ax.add_patch(
        FancyArrowPatch(
            (4.1, 6.5),
            (9.8, 6.7),
            arrowstyle="-|>",
            mutation_scale=14,
            linewidth=2,
            color=COLORS["pathway_edge"],
            connectionstyle="arc3,rad=-0.15",
            zorder=2,
        )
    )
    draw_edge_label(
        ax, 7.0, 7.15,
        "CORRELAÇÃO_EXPRESSÃO_PATHWAY\nidarea · title · log2FC",
        COLORS["pathway_edge"],
    )

    # Gene → Disease
    ax.add_patch(
        FancyArrowPatch(
            (3.2, 4.2),
            (9.8, 3.2),
            arrowstyle="-|>",
            mutation_scale=14,
            linewidth=2,
            color=COLORS["assoc_edge"],
            connectionstyle="arc3,rad=0.2",
            zorder=2,
        )
    )
    draw_edge_label(
        ax, 6.5, 3.35,
        "ASSOCIAÇÃO_GENE_DOENÇA\n(NIH · OpenTargets)",
        COLORS["assoc_edge"],
    )

    # Legenda arestas PPI (atributos)
    legend_ppi = FancyBboxPatch(
        (0.5, 0.35),
        3.6,
        1.2,
        boxstyle="round,pad=0.02",
        linewidth=1,
        edgecolor=COLORS["ppi"],
        facecolor="white",
        zorder=2,
    )
    ax.add_patch(legend_ppi)
    ax.text(0.7, 1.35, "PPI (STRING-DB):", fontsize=8, fontweight="bold", color=COLORS["ppi"])
    for i, line in enumerate([
        "combined_score",
        "experimentally_determined",
        "database_annotated",
        "automated_textmining",
    ]):
        ax.text(0.75, 1.05 - i * 0.22, f"  {line}", fontsize=7, family="monospace", color="#455A64")

    # Nota identificadores
    ax.text(
        7,
        0.25,
        "Harmonização de IDs: Entrez (geneid) · HGNC (symbol) · Ensembl/STRING · KEGG (K#####)",
        ha="center",
        fontsize=7.5,
        color="#78909C",
        style="italic",
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT, bbox_inches="tight", facecolor=fig.get_facecolor(), pad_inches=0.15)
    plt.close(fig)
    print(f"Gerado: {OUTPUT} ({OUTPUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
