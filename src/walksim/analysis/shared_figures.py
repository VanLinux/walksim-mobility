"""Series mixtas y comparación de tasas analíticas con exposición simulada."""

from matplotlib.figure import Figure


def draw_shared(figure, analytical=None, result=None, dark=False):
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
    colors = ["#8DA599", "#91A5C1"]
    if result:
        rows = result["series"]
        times = [r["time_s"] / 60 for r in rows]
        for key, label, color in [
            ("ped_occupancy", "Peatones", colors[0]),
            ("bike_occupancy", "Bicicletas", colors[1]),
        ]:
            axes[0, 0].plot(times, [r[key] for r in rows], color=color, label=label)
        for key, label, color in [
            ("meetings_pb", "Encuentros P–B", colors[0]),
            ("passes_bp", "Rebases B→P", colors[1]),
        ]:
            axes[0, 1].plot(times, [r[key] for r in rows], color=color, label=label)
        for ax in axes[0]:
            ax.legend(fontsize=7, facecolor=bg, labelcolor=ink)
    for index, (mode, key) in enumerate(
        [("pedestrian", "weighted_h"), ("bicycle", "weighted_min")]
    ):
        ax = axes[1, index]
        for j, direction in enumerate(["AB", "BA"]):
            row = (
                next(
                    (r[mode] for r in analytical["directions"] if r["direction"] == direction), None
                )
                if analytical
                else None
            )
            if row:
                ax.bar(
                    j - 0.17,
                    row[key],
                    width=0.33,
                    color=colors[0],
                    label="Analítico" if j == 0 else None,
                )
            measured = (
                result["incidence"][("P." if index == 0 else "B.") + direction]["weighted_rate"]
                if result
                else None
            )
            if measured is not None:
                ax.bar(
                    j + 0.17,
                    measured,
                    width=0.33,
                    color=colors[1],
                    label="Simulado" if j == 0 else None,
                )
        ax.set_xticks([0, 1], ["A → B", "B → A"])
        handles, labels = ax.get_legend_handles_labels()
        if handles:
            ax.legend(handles, labels, fontsize=7, facecolor=bg, labelcolor=ink)
    titles = [
        ("Ocupación media por intervalo", "Tiempo observado (min)", "Usuarios"),
        ("Eventos geométricos peatón–bicicleta", "Tiempo observado (min)", "Eventos / intervalo"),
        ("Eventos ponderados por peatón", "Sentido", "Eventos por peatón·h"),
        ("Eventos ponderados por ciclista", "Sentido", "Eventos por ciclista·min"),
    ]
    for ax, (title, xlabel, ylabel) in zip(axes.flat, titles, strict=True):
        ax.set_title(title, color=ink, fontsize=10, pad=12)
        ax.set_xlabel(xlabel, color=ink, fontsize=8)
        ax.set_ylabel(ylabel, color=ink, fontsize=8)
    figure.subplots_adjust(left=0.11, right=0.97, top=0.91, bottom=0.13, hspace=0.65, wspace=0.4)


def report_plot(result):
    fig = Figure(figsize=(9, 6))
    draw_shared(fig, result["analytical"], result)
    return fig
