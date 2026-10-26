"""Gráficas compartidas por la interfaz y el reporte, sin estado global pyplot."""

from __future__ import annotations

from matplotlib.figure import Figure


def draw_walkway(
    figure: Figure, result: dict | None, dark: bool = False, view: str = "overview"
) -> None:
    figure.clear()
    bg, text, grid = (
        ("#292B2F", "#E7E8E9", "#555960") if dark else ("#FFFFFF", "#30343B", "#DADDE0")
    )
    figure.set_facecolor(bg)
    if view == "speed":
        ax = figure.subplots()
        ax.set_facecolor(bg)
        ax.tick_params(colors=text)
        for spine in ax.spines.values():
            spine.set_color(grid)
        if result:
            series = [r for r in result["series"] if r["speed_mps"] is not None]
            ax.plot(
                [r["time_s"] / 60 for r in series],
                [r["speed_mps"] for r in series],
                color="#93A7C4",
                marker="o",
                markersize=3,
                linewidth=1.5,
            )
        ax.set(
            title="Velocidad media de recorridos finalizados por intervalo",
            xlabel="Tiempo observado (min)",
            ylabel="Velocidad (m/s)",
        )
        ax.title.set_color(text)
        ax.xaxis.label.set_color(text)
        ax.yaxis.label.set_color(text)
        ax.grid(color=grid, alpha=0.3)
        figure.subplots_adjust(left=0.12, right=0.97, bottom=0.16, top=0.87)
        return
    axes = figure.subplots(2, 2)
    for ax in axes.flat:
        ax.set_facecolor(bg)
        ax.tick_params(colors=text, labelsize=8)
        for spine in ax.spines.values():
            spine.set_color(grid)
        ax.xaxis.label.set_color(text)
        ax.yaxis.label.set_color(text)
        ax.title.set_color(text)
        ax.grid(alpha=0.28, color=grid, linewidth=0.6)
    if not result:
        for ax in axes.flat:
            ax.text(
                0.5,
                0.5,
                "Ejecute una microsimulación",
                ha="center",
                va="center",
                transform=ax.transAxes,
                color=text,
                fontsize=10,
            )
            ax.set_xticks([])
            ax.set_yticks([])
    else:
        series = result["series"]
        times = [r["time_s"] / 60 for r in series]
        for ax, key, title, ylabel, color in [
            (axes[0, 0], "occupancy", "Acumulación en el corredor", "Peatones", "#7BA899"),
            (axes[0, 1], "density", "Densidad media global", "peat/m²", "#93A7C4"),
            (axes[1, 0], "flow_pph", "Salidas por intervalo", "peat/h", "#BC9C78"),
        ]:
            values = [r[key] for r in series]
            ax.step(times, values, where="post", color=color, linewidth=1.8)
            ax.set(title=title, xlabel="Tiempo observado (min)", ylabel=ylabel)
        travel = result.get("travel_times_s", [])
        ax = axes[1, 1]
        if travel:
            ax.hist(
                travel,
                bins=min(20, max(1, int(len(travel) ** 0.5))),
                color="#93A7C4",
                edgecolor=bg,
                linewidth=0.8,
            )
        ax.set(
            title="Recorridos de la cohorte completada",
            xlabel="Tiempo de recorrido (s)",
            ylabel="Peatones",
        )
    figure.subplots_adjust(left=0.10, right=0.97, bottom=0.12, top=0.90, wspace=0.38, hspace=0.70)


def report_plot(result: dict) -> Figure:
    figure = Figure(figsize=(9, 5.8), dpi=120)
    draw_walkway(figure, result)
    return figure
