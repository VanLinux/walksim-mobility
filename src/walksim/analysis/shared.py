"""Cohortes y eventos geométricos a partir de FCD de peatones y bicicletas reales."""

from __future__ import annotations

import bisect
import math
import xml.etree.ElementTree as ET
from collections import Counter
from statistics import fmean

from walksim.analysis.walkway import percentile
from walksim.domain.shared import GROUP_LABELS

EVENTS = ["meetings_pb", "passes_bp", "meetings_bb", "passes_bb"]


def crossings(previous, current, seen):
    """Sólo pares que pueden invertir orden en un paso; evita comparar todos contra todos."""
    common = previous.keys() & current.keys()
    if not common:
        return []
    max_move = max(abs(current[p] - previous[p]) for p in common)
    ordered = sorted(common, key=previous.get)
    positions = [previous[p] for p in ordered]
    out = []
    for i, p in enumerate(ordered):
        limit = bisect.bisect_right(positions, positions[i] + 2 * max_move + 1e-8)
        for q in ordered[i + 1 : limit]:
            before = previous[p] - previous[q]
            after = current[p] - current[q]
            if before == after or before * after > 0 or (before == 0 and after == 0):
                continue
            pair = tuple(sorted((p, q)))
            if pair in seen:
                continue
            mode_p, dir_p = p.split(".")[:2]
            mode_q, dir_q = q.split(".")[:2]
            if mode_p == mode_q == "P":
                continue
            if dir_p != dir_q:
                kind = "meetings_bb" if mode_p == mode_q == "B" else "meetings_pb"
                actor = p if mode_p == "B" else q
                target = q if actor == p else p
            else:
                direction = 1 if dir_p == "AB" else -1
                gain = (current[p] - previous[p] - current[q] + previous[q]) * direction
                actor, target = (p, q) if gain > 0 else (q, p)
                if actor.startswith("P"):
                    continue
                kind = "passes_bb" if target.startswith("B") else "passes_bp"
            fraction = abs(before) / (abs(before) + abs(after)) if before != after else 0.5
            seen.add(pair)
            out.append((kind, actor, target, fraction))
    return out


def summarize(trips_path, persons_path, fcd_path, x, entries):
    start, stop = x.warmup_s, x.warmup_s + x.duration_s
    final = stop + x.clearance_s
    planned = {ident: t for t, ident, _speed in entries}
    counts = Counter(".".join(p.split(".")[:2]) for p in planned)
    completed = Counter()
    values = {g: [] for g in GROUP_LABELS}
    started = 0
    finish_times = []
    for path, tag in [(trips_path, "tripinfo"), (persons_path, "personinfo")]:
        for _event, node in ET.iterparse(path, events=("end",)):
            if node.tag != tag:
                continue
            ident = node.get("id")
            group = ".".join((ident or "").split(".")[:2])
            if ident not in planned:
                node.clear()
                continue
            row = node if tag == "tripinfo" else node.find("walk")
            if row is not None:
                depart = float(row.get("depart", "-1"))
                arrival = float(row.get("arrival", "-1"))
                if depart >= 0:
                    started += 1
                if 0 <= arrival < final:
                    completed[group] += 1
                    finish_times.append(arrival)
                    if start <= planned[ident] < stop:
                        values[group].append(
                            (
                                arrival - planned[ident],
                                float(row.get("routeLength", "0")),
                                max(0.0, float(row.get("timeLoss", "0"))),
                            )
                        )
            node.clear()
    groups = {}
    for g in GROUP_LABELS:
        v = values[g]
        groups[g] = dict(
            generated=counts[g],
            completed=completed[g],
            cohort_completed=len(v),
            mean_trip_s=fmean(r[0] for r in v) if v else None,
            p95_trip_s=percentile([r[0] for r in v], 0.95),
            speed_mps=sum(r[1] for r in v) / sum(r[0] for r in v) if v else None,
            mean_loss_s=fmean(r[2] for r in v) if v else None,
        )
    bins = math.ceil(x.duration_s / x.bin_s)
    series = [
        dict(
            time_s=i * x.bin_s,
            interval_s=min(x.bin_s, x.duration_s - i * x.bin_s),
            ped_occupancy=0.0,
            bike_occupancy=0.0,
            **{e: 0 for e in EVENTS},
        )
        for i in range(bins)
    ]
    incidence = {g: dict(exposure_s=0.0, meetings=0, passes=0) for g in GROUP_LABELS}
    previous = {}
    previous_t = None
    seen = set()
    totals = Counter()
    context = ET.iterparse(fcd_path, events=("start", "end"))
    _, root = next(context)
    for event, frame in context:
        if event != "end" or frame.tag != "timestep":
            continue
        t = float(frame.get("time"))
        current = {}
        modes = Counter()
        for node in frame:
            ident = node.get("id")
            if ident not in planned:
                continue
            group = ".".join(ident.split(".")[:2])
            px = float(node.get("x"))
            if ident.startswith("B"):
                px -= 0.8 * (1 if ".AB." in ident else -1)
            current[ident] = px
            modes[group] += 1
        left, right = max(start, t), min(stop, t + 0.5)
        if right > left:
            for g, n in modes.items():
                incidence[g]["exposure_s"] += n * (right - left)
            lo = left
            while lo < right - 1e-9:
                k = min(bins - 1, int((lo - start + 1e-9) // x.bin_s))
                hi = min(right, start + (k + 1) * x.bin_s)
                series[k]["ped_occupancy"] += (modes["P.AB"] + modes["P.BA"]) * (hi - lo)
                series[k]["bike_occupancy"] += (modes["B.AB"] + modes["B.BA"]) * (hi - lo)
                lo = hi
        if previous_t is not None:
            for kind, actor, target, f in crossings(previous, current, seen):
                time = previous_t + f * (t - previous_t)
                if start <= time < stop:
                    totals[kind] += 1
                    k = min(bins - 1, int((time - start) // x.bin_s))
                    series[k][kind] += 1
                    a, b = ".".join(actor.split(".")[:2]), ".".join(target.split(".")[:2])
                    if kind.startswith("meetings"):
                        incidence[a]["meetings"] += 1
                        incidence[b]["meetings"] += 1
                    else:
                        incidence[a]["passes"] += 1
                        if target.startswith("P"):
                            incidence[b]["passes"] += 1
        previous, previous_t = current, t
        root.clear()
    for row in series:
        row["ped_occupancy"] /= row["interval_s"]
        row["bike_occupancy"] /= row["interval_s"]
    for g, v in incidence.items():
        unit = 3600 if g.startswith("P") else 60
        v["meeting_rate"] = v["meetings"] * unit / v["exposure_s"] if v["exposure_s"] else None
        v["passing_rate"] = v["passes"] * unit / v["exposure_s"] if v["exposure_s"] else None
        v["weighted_rate"] = (
            (
                v["passing_rate"] + 0.5 * v["meeting_rate"]
                if g.startswith("P")
                else v["meeting_rate"] + 10 * v["passing_rate"]
            )
            if v["exposure_s"]
            else None
        )
    done = sum(completed.values())
    summary = dict(
        generated=len(entries),
        started=started,
        completed=done,
        pending=len(entries) - done,
        cohort_generated=sum(start <= t < stop for t in planned.values()),
        cohort_completed=sum(len(v) for v in values.values()),
        **{e: totals[e] for e in EVENTS},
        clearance_s=max(0.0, max(finish_times, default=stop) - stop)
        if done == len(entries)
        else None,
    )
    return dict(summary=summary, groups=groups, series=series, incidence=incidence)
