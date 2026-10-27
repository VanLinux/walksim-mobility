"""Mediciones del paso: entrada/salida y detenciones previas en FCD a 0.5 s."""

import xml.etree.ElementTree as ET


def summarize(x, entries, fcd_path, crossings):
    people = {
        ident: dict(group=ident[:2], inserted=False, entered=False, completed=False, wait_s=0.0)
        for _t, ident in entries
        if ident[:2] in {"AB", "BA"}
    }
    series = [
        dict(time_s=i * 0.5, queue_ab=0, queue_ba=0)
        for i in range(int((x.duration_s + 2 * x.cycle_s) * 2))
    ]
    for _event, step in ET.iterparse(fcd_path, events=("end",)):
        if step.tag != "timestep":
            continue
        t = float(step.get("time"))
        index = round(t * 2)
        if not 0 <= index < len(series):
            step.clear()
            continue
        for p in step.findall("person"):
            ident = p.get("id")
            if ident not in people:
                continue
            rec = people[ident]
            rec["inserted"] = True
            edge = p.get("edge", p.get("lane", ""))
            in_crossing = edge in crossings or edge.removesuffix("_0") in crossings
            if in_crossing:
                rec["entered"] = True
            elif rec["entered"]:
                rec["completed"] = True
            elif float(p.get("speed", "0")) < 0.1:
                rec["wait_s"] += 0.5
                series[index]["queue_" + rec["group"].lower()] += 1
        step.clear()

    def stats(records):
        generated = len(records)
        inserted = sum(r["inserted"] for r in records)
        entered = sum(r["entered"] for r in records)
        completed = sum(r["completed"] for r in records)
        wait = sum(r["wait_s"] for r in records if r["entered"])
        return dict(
            generated=generated,
            inserted=inserted,
            entered=entered,
            completed=completed,
            pending=generated - completed,
            not_inserted=generated - inserted,
            waiting=inserted - entered,
            crossing=entered - completed,
            mean_wait_s=wait / entered if entered else None,
            max_queue_ab=0,
            max_queue_ba=0,
            completed_pct=100 * completed / generated if generated else None,
        )

    directions = {d: stats([r for r in people.values() if r["group"] == d]) for d in ("AB", "BA")}
    summary = stats(list(people.values()))
    for d in directions:
        k = "max_queue_" + d.lower()
        summary[k] = directions[d][k] = max(r["queue_" + d.lower()] for r in series)
    return dict(summary=summary, directions=directions, series=series)
