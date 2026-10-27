"""Una gráfica de colas y una banda del ciclo para interfaz y reporte."""

from matplotlib.figure import Figure


def draw_crossing(figure, inputs, result=None, dark=False):
    from walksim.domain.crossing import CrossingInput

    figure.clear()
    bg, ink, grid = ("#292B2F", "#E7E8E9", "#555960") if dark else ("#FFFFFF", "#30343B", "#DADDE0")
    figure.set_facecolor(bg)
    axes = figure.subplots(2, 1, gridspec_kw={"height_ratios": [3, 1]})
    for ax in axes:
        ax.set_facecolor(bg)
        ax.tick_params(colors=ink, labelsize=8)
        for spine in ax.spines.values():
            spine.set_color(grid)
    ax = axes[0]
    if result:
        rows = result["series"]
        for key, label, color in [
            ("queue_ab", "Acera A", "#7299A9"),
            ("queue_ba", "Acera B", "#B09470"),
        ]:
            ax.step(
                [r["time_s"] / 60 for r in rows],
                [r[key] for r in rows],
                where="post",
                label=label,
                color=color,
            )
        ax.axvline(
            result["inputs"]["duration_s"] / 60, color=ink, ls="--", lw=0.8, label="Fin de llegadas"
        )
        ax.legend(fontsize=8, facecolor=bg, labelcolor=ink)
    else:
        ax.text(
            0.5,
            0.5,
            "Simule sus datos para ver las colas",
            ha="center",
            va="center",
            color=ink,
            transform=ax.transAxes,
        )
    ax.set(
        title="Peatones detenidos antes de iniciar el cruce",
        xlabel="Tiempo desde inicio (min)",
        ylabel="Peatones",
    )
    ax.grid(alpha=0.2, color=grid)
    for name in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        name.set_color(ink)
    try:
        x = CrossingInput.parse(inputs)
    except ValueError:
        x = None
    ax = axes[1]
    if x:
        start = 0
        phases = [
            (x.cycle_s - x.walk_s - x.clearance_s - 3, "Vehículos", "#7299A9"),
            (3, "Amarillo", "#C8B176"),
            (x.walk_s, "Iniciar", "#8DA599"),
            (x.clearance_s, "Despeje", "#AF9299"),
        ]
        for duration, label, color in phases:
            ax.barh([0], [duration], left=start, height=0.7, color=color, label=label)
            start += duration
        ax.set_xlim(0, x.cycle_s)
        ax.legend(
            fontsize=7,
            ncol=2,
            facecolor=bg,
            labelcolor=ink,
            loc="upper center",
            bbox_to_anchor=(0.5, -0.55),
        )
    ax.set_yticks([])
    ax.set_xlabel("Un ciclo de señalización (s)", color=ink, fontsize=8)
    figure.subplots_adjust(left=0.13, right=0.96, top=0.93, bottom=0.21, hspace=0.6)


def report_plot(result):
    figure = Figure(figsize=(9, 6))
    draw_crossing(figure, result["inputs"], result)
    return figure
