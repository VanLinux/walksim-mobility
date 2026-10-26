"""Plano, flujos OD y mapas de celda sin interpolación espacial."""

from matplotlib import colormaps
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from matplotlib.figure import Figure
from matplotlib.patches import Polygon, Rectangle

from walksim.domain.plaza import NAMES, PORTS, PlazaInput, polygon, ports

VIEW_LABELS = dict(
    mean_density=("Densidad media", "peat/m²"),
    max_density=("Densidad máxima muestreada", "peat/m²"),
    person_seconds=("Ocupación acumulada", "peatón·s"),
    mean_stay_s=("Permanencia media por visitante", "s"),
)


def draw_plaza(figure, raw, result=None, dark=False, view="mean_density"):
    figure.clear()
    bg, ink, line = ("#292B2F", "#E7E8E9", "#60656B") if dark else ("#FFFFFF", "#30343B", "#C7CCD1")
    figure.set_facecolor(bg)
    ax = figure.add_subplot(111)
    ax.set_facecolor(bg)
    ax.tick_params(colors=ink, labelsize=8)
    for spine in ax.spines.values():
        spine.set_color(line)
    try:
        x = PlazaInput.parse(raw)
    except ValueError:
        ax.text(
            0.5,
            0.5,
            "Complete los datos para mostrar la plantilla",
            ha="center",
            transform=ax.transAxes,
            color=ink,
        )
        return
    poly = polygon(x)
    outline = Polygon(
        poly, closed=True, facecolor="#343A40" if dark else "#F1F3F4", edgecolor=line, linewidth=1.5
    )
    ax.add_patch(outline)
    if result:
        cells = [c for c in result["cells"] if c["area_m2"] > 1e-9]
        maximum = max((c[view] for c in cells), default=0)
        norm = Normalize(0, maximum if maximum else 1)
        cmap = colormaps["YlOrRd"]
        for c in cells:
            tile = Rectangle(
                (c["x_m"], c["y_m"]),
                c["width_m"],
                c["height_m"],
                facecolor=cmap(norm(c[view])),
                edgecolor="none",
            )
            tile.set_clip_path(outline)
            ax.add_patch(tile)
        scalar = ScalarMappable(norm=norm, cmap=cmap)
        cb = figure.colorbar(scalar, ax=ax, fraction=0.045, pad=0.07)
        cb.set_label(VIEW_LABELS[view][1], color=ink, fontsize=9)
        cb.ax.tick_params(colors=ink, labelsize=8)
        for i in result["critical_cells"][:3]:
            c = result["cells"][i]
            ax.plot(
                c["x_m"] + c["width_m"] / 2,
                c["y_m"] + c["height_m"] / 2,
                "+",
                color="#253B53",
                markersize=7,
            )
    positions = dict(
        N=(0, x.height_m / 2), S=(0, -x.height_m / 2), E=(x.length_m / 2, 0), W=(-x.length_m / 2, 0)
    )
    if not result:
        total = sum(map(sum, x.od))
        for i, p in enumerate(PORTS):
            for j, q in enumerate(PORTS):
                if x.od[i][j] > 0:
                    ax.annotate(
                        "",
                        xy=positions[q],
                        xytext=positions[p],
                        arrowprops=dict(
                            arrowstyle="->",
                            color="#7D96B3",
                            alpha=0.5,
                            linewidth=0.7 + 4 * x.od[i][j] / max(1, total),
                        ),
                    )
    for p in ports(x):
        px, py = positions[p]
        width = getattr(x, "width_" + p.lower() + "_m")
        if p in {"N", "S"}:
            ax.plot([px - width / 2, px + width / 2], [py, py], color="#7D96B3", linewidth=4)
        else:
            ax.plot([px, px], [py - width / 2, py + width / 2], color="#7D96B3", linewidth=4)
        ax.text(px * 1.12, py * 1.14, NAMES[p], ha="center", va="center", color=ink, fontsize=9)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-x.length_m * 0.66, x.length_m * 0.66)
    ax.set_ylim(-x.height_m * 0.68, x.height_m * 0.68)
    ax.set_xlabel("Este–Oeste (m)", color=ink, fontsize=9)
    ax.set_ylabel("Norte–Sur (m)", color=ink, fontsize=9)
    ax.set_title(
        VIEW_LABELS[view][0] if result else "Plantilla y demanda OD local",
        color=ink,
        fontsize=12,
        pad=16,
    )
    figure.subplots_adjust(left=0.13, right=0.9, bottom=0.14, top=0.88)


def report_plot(result, view="mean_density"):
    fig = Figure(figsize=(8, 5.8))
    draw_plaza(fig, result["inputs"], result, False, view)
    return fig
