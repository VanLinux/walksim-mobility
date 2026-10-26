"""Etiquetas compartidas de entradas y procedencia, sin dependencias gráficas."""

INPUT_LABELS = dict(
    mode="Tarea de ingeniería",
    flow_type="Tipo de flujo",
    demand_basis="Base de demanda",
    length_m="Longitud (m)",
    width_m="Ancho total (m)",
    obstacles_m="Descuento por obstáculos (m)",
    edges_m="Descuento por bordes (m)",
    flow_ab_pph="Demanda A → B (peat/h)",
    flow_ba_pph="Demanda B → A (peat/h)",
    count_ab="Conteo A → B (peat)",
    count_ba="Conteo B → A (peat)",
    phf="Factor de hora pico (PHF)",
    speed_mps="Velocidad representativa (m/s)",
    slope_pct="Pendiente (%)",
    target_los="LOS objetivo",
    margin_pct="Margen de diseño (%)",
    share_ab_pct="Reparto A → B (%)",
    duration_s="Periodo observado (s)",
    warmup_s="Calentamiento (s)",
    bin_s="Intervalo de gráfica (s)",
    seed="Semilla",
    platoon_cycle_s="Intervalo entre pelotones (s)",
    platoon_release_s="Duración de descarga (s)",
)
ORIGIN_LABELS = dict(
    default="Predeterminado", entered="Introducido", observed="Observado", csv="CSV"
)
