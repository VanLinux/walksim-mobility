"""Gráficas de colas compartidas por interfaz y reporte."""

from matplotlib.figure import Figure


def draw_access(figure, result, dark=False):
    figure.clear()
    bg, ink, grid = ("#292B2F", "#E7E8E9", "#555960") if dark else ("#FFFFFF", "#30343B", "#DADDE0")
    figure.set_facecolor(bg)
    axes = figure.subplots(2, 2)
    for ax in axes.flat:
        ax.set_facecolor(bg)
        ax.tick_params(colors=ink, labelsize=8)
        for spine in ax.spines.values():
            spine.set_color(grid)
        ax.grid(alpha=0.25, color=grid)
    if result:
        rows = result["series"]
        times = [r["time_s"] / 60 for r in rows]
        for stage, color in zip(result["stages"], ["#8DA599", "#91A5C1"], strict=False):
            key = stage["key"]
            axes[0, 0].plot(
                times, [r[key + "_queue"] for r in rows], color=color, label=stage["label"]
            )
            axes[0, 1].plot(times, [r[key + "_density"] for r in rows], color=color)
        if result["stages"]:
            axes[0, 0].legend(fontsize=7, facecolor=bg, labelcolor=ink)
        axes[1, 0].plot(times, [r["mean_system"] for r in rows], color="#B5A182")
        hist = result["histogram"]
        axes[1, 1].bar(
            [h["start_s"] for h in hist],
            [h["count"] for h in hist],
            width=[h["end_s"] - h["start_s"] for h in hist],
            align="edge",
            color="#91A5C1",
            alpha=0.85,
        )
    titles = [
        ("Cola media por intervalo", "Tiempo observado (min)", "Peatones en espera"),
        ("Densidad del área de atención", "Tiempo observado (min)", "Peatones / m²"),
        ("Acumulación en el sistema", "Tiempo observado (min)", "Peatones"),
        ("Espera total · cohorte completada", "Espera (s)", "Peatones"),
    ]
    for ax, (title, xlabel, ylabel) in zip(axes.flat, titles, strict=True):
        ax.set_title(title, fontsize=10, color=ink, pad=10)
        ax.set_xlabel(xlabel, fontsize=8, color=ink)
        ax.set_ylabel(ylabel, fontsize=8, color=ink)
        if not result:
            ax.text(
                0.5,
                0.5,
                "Simule el escenario seleccionado",
                ha="center",
                va="center",
                transform=ax.transAxes,
                color=ink,
                fontsize=9,
            )
            ax.set_xticks([])
            ax.set_yticks([])
    figure.subplots_adjust(left=0.1, right=0.97, top=0.91, bottom=0.12, hspace=0.65, wspace=0.38)


def report_plot(result):
    figure = Figure(figsize=(9, 6))
    draw_access(figure, result)
    return figure
