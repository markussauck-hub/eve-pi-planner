#!/usr/bin/env python3
"""
Baut die Daten für den EVE PI Planner (Planetary Interaction).

  pi.json        – Rezepte (Schematics) P0 -> P4, Stufen, Planetentypen -> P0,
                   Gebäude (CPU/PG), Steuer-Basiswerte. Quelle: Fuzzwork SDE
  universe.json  – alle Systeme mit Planetentypen, Sicherheitsstatus, Region und Gates
                   (für die Umkreissuche). Quelle: Fuzzwork SDE

    python build_data.py                                  # schreibt ./pi.json und ./universe.json
    python build_data.py --out site/pi.json --universe-out site/universe.json
    python build_data.py --local ./sde_csv                # SDE-CSVs lokal statt Download

Nur Standardbibliothek. Bricht mit klarer Meldung ab, wenn die SDE anders aussieht als erwartet.
"""

import argparse
import csv
import io
import json
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SDE_URL = "https://www.fuzzwork.co.uk/dump/latest/csv/"
USER_AGENT = "EVE-PI-Planner/1.0 (GitHub Pages build; github.com/markussauck-hub/eve-pi-planner)"

PLANET_GROUP = 7            # invGroups: "Planet"
WH_REGION_MIN = 11000000    # Wurmloch-Regionen (J-Space) ab hier
SKIP_REGION_MIN = 12000000  # Abyss, Void usw. – keine PI

# Feste Reihenfolge der Planetentypen in universe.json (Shattered hat keine PI)
PLANET_TYPES = ["Barren", "Gas", "Ice", "Lava", "Oceanic", "Plasma", "Storm", "Temperate"]

# Welche P0-Ressourcen es auf welchem Planetentyp gibt. Steht nicht sauber in der SDE,
# ist aber seit Jahren unverändert. Wird beim Build gegen die Typnamen geprüft.
PLANET_RESOURCES = {
    "Barren":    ["Aqueous Liquids", "Base Metals", "Carbon Compounds", "Micro Organisms", "Noble Metals"],
    "Gas":       ["Aqueous Liquids", "Base Metals", "Ionic Solutions", "Noble Gas", "Reactive Gas"],
    "Ice":       ["Aqueous Liquids", "Heavy Metals", "Micro Organisms", "Noble Gas", "Planktic Colonies"],
    "Lava":      ["Base Metals", "Felsic Magma", "Heavy Metals", "Non-CS Crystals", "Suspended Plasma"],
    "Oceanic":   ["Aqueous Liquids", "Carbon Compounds", "Complex Organisms", "Micro Organisms", "Planktic Colonies"],
    "Plasma":    ["Base Metals", "Heavy Metals", "Noble Metals", "Non-CS Crystals", "Suspended Plasma"],
    "Storm":     ["Aqueous Liquids", "Base Metals", "Ionic Solutions", "Noble Gas", "Suspended Plasma"],
    "Temperate": ["Aqueous Liquids", "Autotrophs", "Carbon Compounds", "Complex Organisms", "Micro Organisms"],
}

# Gebäude: CPU (tf) / PG (MW). Werte aus der SDE haben Vorrang (dgm-Attribute), das hier ist die Rückfallebene.
ATTR_CPU_LOAD, ATTR_PG_LOAD = 49, 15
BUILDINGS = {
    "basic":     {"name": "Basic Industry Facility",    "cpu": 200,  "pg": 800},
    "advanced":  {"name": "Advanced Industry Facility", "cpu": 500,  "pg": 700},
    "hightech":  {"name": "High-Tech Production Plant", "cpu": 1100, "pg": 400},
    "storage":   {"name": "Storage Facility",           "cpu": 500,  "pg": 700},
    "launchpad": {"name": "Launchpad",                  "cpu": 3600, "pg": 700},
    "ecu":       {"name": "Extractor Control Unit",     "cpu": 400,  "pg": 2600},
    "head":      {"name": "Extraktor-Kopf",             "cpu": 110,  "pg": 550},
}
# Command Center je Upgrade-Stufe (0–5): CPU / PG. Nicht in der SDE.
COMMAND_CENTER = [[1675, 6000], [7057, 9000], [12136, 12000], [17215, 15000], [21315, 17000], [25415, 19000]]

# Customs-Basiswert je Stufe (ISK pro Einheit), fest im Spiel, nicht in der SDE.
# Exportsteuer = Basiswert × Steuersatz, Import = 50 % davon.
BASE_VALUE = {0: 5, 1: 400, 2: 7200, 3: 60000, 4: 1200000}

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


# ---------------------------------------------------------------------------
# CSV laden
# ---------------------------------------------------------------------------
def rows(name, local_dir=None, need=()):
    if local_dir:
        text = (Path(local_dir) / f"{name}.csv").read_text(encoding="utf-8-sig")
    else:
        url = f"{SDE_URL}{name}.csv"
        print(f"Lade {url}", flush=True)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=300) as resp:
            text = resp.read().decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text, newline=""))
    header = [h.strip().lower() for h in next(reader)]
    missing = [c for c in need if c not in header]
    if missing:
        sys.exit(f"{name}.csv: Spalten fehlen {missing} – vorhanden: {header}")
    for row in reader:
        yield dict(zip(header, row))


def to_int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# PI-Daten
# ---------------------------------------------------------------------------
def build_pi(local):
    names, group_of, base_price, volume = {}, {}, {}, {}
    for r in rows("invTypes", local, need=("typeid", "groupid", "typename")):
        tid = to_int(r["typeid"])
        if tid is None:
            continue
        names[tid] = r["typename"].strip()
        group_of[tid] = to_int(r["groupid"])
        base_price[tid] = to_float(r.get("baseprice"))
        volume[tid] = to_float(r.get("volume"))
    by_name = {}
    for tid, n in names.items():
        by_name.setdefault(n, tid)

    schem = {}
    for r in rows("planetSchematics", local, need=("schematicid", "cycletime")):
        sid = to_int(r["schematicid"])
        if sid is not None:
            schem[sid] = {"cycle": to_int(r["cycletime"]), "name": r.get("schematicname", "").strip(), "in": [], "out": None}

    for r in rows("planetSchematicsTypeMap", local, need=("schematicid", "typeid", "quantity", "isinput")):
        sid, tid, qty = to_int(r["schematicid"]), to_int(r["typeid"]), to_int(r["quantity"])
        if sid not in schem or None in (tid, qty):
            continue
        if str(r["isinput"]).strip().lower() in ("1", "true"):
            schem[sid]["in"].append([tid, qty])
        else:
            schem[sid]["out"] = [tid, qty]

    pins_of = defaultdict(set)
    for r in rows("planetSchematicsPinMap", local, need=("schematicid", "pintypeid")):
        sid, pin = to_int(r["schematicid"]), to_int(r["pintypeid"])
        if sid in schem and pin is not None:
            pins_of[sid].add(pin)

    # Rezept je Produkt
    recipes = {}
    for sid, s in schem.items():
        if not s["out"] or not s["in"] or not s["cycle"]:
            continue
        out_id, out_qty = s["out"]
        recipes[out_id] = {"q": out_qty, "c": s["cycle"], "in": sorted(s["in"], key=lambda m: names.get(m[0], "")), "sid": sid}
    if len(recipes) < 60:
        sys.exit(f"Nur {len(recipes)} PI-Rezepte gefunden – Datenquelle prüfen.")

    # Stufe aus dem Rezeptgraphen: P0 = kommt in keinem Rezept als Produkt vor
    tier = {}

    def tier_of(t, depth=0):
        if t in tier:
            return tier[t]
        if depth > 10:
            sys.exit(f"Zyklus im Rezeptgraphen bei {names.get(t, t)}")
        r = recipes.get(t)
        tier[t] = 0 if r is None else 1 + max(tier_of(i, depth + 1) for i, _ in r["in"])
        return tier[t]

    for t in list(recipes):
        tier_of(t)
    counts = defaultdict(int)
    for t in tier:
        counts[tier[t]] += 1
    print("  Rezepte je Stufe:", dict(sorted(counts.items())), flush=True)
    if set(counts) != {0, 1, 2, 3, 4}:
        sys.exit(f"Unerwartete Stufen {dict(counts)} – Datenquelle prüfen.")

    # Planetentypen: Typname "Planet (Barren)" -> "Barren"
    # Mehrere TypeIDs können denselben Namen tragen ("Planet (Barren)") – alle merken
    planet_type_ids = defaultdict(list)
    for tid, n in names.items():
        if group_of.get(tid) == PLANET_GROUP and n.startswith("Planet (") and n.endswith(")"):
            planet_type_ids[n[8:-1]].append(tid)

    # P0 je Planetentyp, gegen die SDE-Namen geprüft
    p0_ids = {t for t, lv in tier.items() if lv == 0}
    # Namen tolerant vergleichen: "Micro Organisms" == "Microorganisms", Groß-/Kleinschreibung egal
    norm = lambda s: "".join(ch for ch in s.lower() if ch.isalnum())
    p0_by_norm = {norm(names.get(t, "")): t for t in p0_ids}
    resources = {}
    for ptype, res in PLANET_RESOURCES.items():
        ids = []
        for n in res:
            t = p0_by_norm.get(norm(n))
            if t is None:
                sys.exit(f"P0-Rohstoff '{n}' ({ptype}) nicht in den Rezepten gefunden – Tabelle prüfen. "
                         f"P0 laut SDE: {sorted(names.get(x, x) for x in p0_ids)}")
            ids.append(t)
        resources[ptype] = ids
    covered = {t for ids in resources.values() for t in ids}
    if covered != p0_ids:
        sys.exit(f"P0 ohne Planetentyp: {[names.get(t) for t in p0_ids - covered]}")

    # Auf welchen Planeten darf ein Rezept laufen? Aus den Gebäude-Namen ("Barren High-Tech Production Plant")
    def planets_for(sid):
        out = set()
        for pin in pins_of.get(sid, ()):
            n = names.get(pin, "")
            for p in PLANET_TYPES:
                if n.startswith(p + " "):
                    out.add(p)
        return sorted(out)

    p4_planets = set()
    for t, r in recipes.items():
        if tier[t] == 4:
            pl = planets_for(r["sid"])
            if pl:
                p4_planets.update(pl)
    p4_planets = sorted(p4_planets) or ["Barren", "Temperate"]

    # Gebäudewerte aus der SDE (falls vorhanden), Rückfall auf die Konstanten
    building_ids = defaultdict(list)
    for tid, n in names.items():
        for key, b in BUILDINGS.items():
            if key != "head" and n.endswith(" " + b["name"]) and n.split(" ")[0] in PLANET_TYPES:
                building_ids[key].append(tid)
    wanted = {t for ids in building_ids.values() for t in ids}
    attrs = defaultdict(dict)
    if wanted:
        for r in rows("dgmTypeAttributes", local, need=("typeid", "attributeid")):
            tid = to_int(r["typeid"])
            if tid not in wanted:
                continue
            aid = to_int(r["attributeid"])
            if aid in (ATTR_CPU_LOAD, ATTR_PG_LOAD):
                v = to_float(r.get("valuefloat")) or to_float(r.get("valueint"))
                if v:
                    attrs[tid][aid] = v
    buildings = {}
    for key, b in BUILDINGS.items():
        cpu, pg, src = b["cpu"], b["pg"], "Konstante"
        for tid in building_ids.get(key, []):
            a = attrs.get(tid, {})
            if ATTR_CPU_LOAD in a and ATTR_PG_LOAD in a:
                cpu, pg, src = round(a[ATTR_CPU_LOAD]), round(a[ATTR_PG_LOAD]), "SDE"
                break
        buildings[key] = {"name": b["name"], "cpu": cpu, "pg": pg}
        print(f"  {b['name']}: CPU {cpu} / PG {pg} ({src})", flush=True)

    # Items: id -> [Name, Stufe, Steuer-Basiswert, Volumen]
    items = {}
    for t, lv in tier.items():
        # invTypes.basePrice ist NICHT der Customs-Basiswert (schwankt je Item) – im Spiel gilt ein Wert je Stufe
        items[str(t)] = [names.get(t, f"#{t}"), lv, BASE_VALUE[lv], volume.get(t) or 0]

    return {
        "source": "Fuzzwork SDE dump (fuzzwork.co.uk/dump/latest/csv/)",
        "items": items,
        # Produkt -> [Menge pro Zyklus, Zykluszeit s, [[Input, Menge], …]]
        "recipes": {str(t): [r["q"], r["c"], r["in"]] for t, r in sorted(recipes.items())},
        # Schematic-ID -> Produkt (für die Fabriken eigener Kolonien aus ESI)
        "schematics": {str(r["sid"]): t for t, r in sorted(recipes.items())},
        "planetTypes": PLANET_TYPES,
        "planetTypeIds": {p: sorted(planet_type_ids.get(p, [])) for p in PLANET_TYPES},
        "resources": resources,
        "p4Planets": p4_planets,
        "buildings": buildings,
        "commandCenter": COMMAND_CENTER,
    }, planet_type_ids


# ---------------------------------------------------------------------------
# Universum: Systeme, Planetentypen, Gates
# ---------------------------------------------------------------------------
def build_universe(local, planet_type_ids):
    type_idx = {tid: PLANET_TYPES.index(p) for p, ids in planet_type_ids.items() if p in PLANET_TYPES for tid in ids}

    regions = {}
    for r in rows("mapRegions", local, need=("regionid", "regionname")):
        rid = to_int(r["regionid"])
        if rid is not None and rid < SKIP_REGION_MIN:
            regions[rid] = r["regionname"].strip()

    systems = {}
    for r in rows("mapSolarSystems", local, need=("solarsystemid", "solarsystemname", "regionid", "security")):
        sid, rid = to_int(r["solarsystemid"]), to_int(r["regionid"])
        if sid is None or rid not in regions:
            continue
        systems[sid] = {"name": r["solarsystemname"].strip(), "region": rid,
                        "sec": to_float(r["security"]) or 0.0, "pl": [0] * len(PLANET_TYPES)}

    n_planets = 0
    for r in rows("mapDenormalize", local, need=("groupid", "typeid", "solarsystemid")):
        if to_int(r["groupid"]) != PLANET_GROUP:
            continue
        s = systems.get(to_int(r["solarsystemid"]))
        i = type_idx.get(to_int(r["typeid"]))
        if s is not None and i is not None:
            s["pl"][i] += 1
            n_planets += 1

    systems = {sid: s for sid, s in systems.items() if any(s["pl"])}
    order = sorted(systems, key=lambda sid: systems[sid]["name"].lower())
    index = {sid: i for i, sid in enumerate(order)}
    region_ids = sorted({systems[sid]["region"] for sid in order}, key=lambda rid: regions[rid].lower())
    region_idx = {rid: i for i, rid in enumerate(region_ids)}

    edges = set()
    for r in rows("mapSolarSystemJumps", local, need=("fromsolarsystemid", "tosolarsystemid")):
        a, b = index.get(to_int(r["fromsolarsystemid"])), index.get(to_int(r["tosolarsystemid"]))
        if a is not None and b is not None and a != b:
            edges.add((min(a, b), max(a, b)))

    print(f"  {len(order)} Systeme mit PI-Planeten, {n_planets} Planeten, {len(edges)} Gate-Verbindungen", flush=True)
    jita = next((s for s in systems.values() if s["name"] == "Jita"), None)
    if jita:
        print(f"  Kontrolle Jita: {dict(zip(PLANET_TYPES, jita['pl']))}", flush=True)
    if len(order) < 1000 or len(edges) < 1000 or n_planets < 30000 * (len(order) > 5000):
        sys.exit("Zu wenige Systeme oder Gates – Datenquelle prüfen.")

    def sec(v):          # exakter Wert, die Seite rundet wie im Spiel
        return round(v, 3)

    return {
        "planetTypes": PLANET_TYPES,
        "regions": [[rid, regions[rid], 1 if rid >= WH_REGION_MIN else 0] for rid in region_ids],
        # System: [ID, Name, Sicherheit, Region-Index, "Anzahl je Planetentyp" (8 Ziffern, max 9)]
        "systems": [[sid, systems[sid]["name"], sec(systems[sid]["sec"]), region_idx[systems[sid]["region"]],
                     "".join(str(min(9, n)) for n in systems[sid]["pl"])] for sid in order],
        "jumps": sorted(edges),
    }


def write(path, data):
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Geschrieben: {out} ({out.stat().st_size / 1024:.0f} KB)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="pi.json")
    ap.add_argument("--universe-out", default="universe.json")
    ap.add_argument("--local", help="Ordner mit lokalen SDE-CSVs statt Download")
    args = ap.parse_args()

    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    pi, planet_type_ids = build_pi(args.local)
    write(args.out, {"generated": generated, **pi})
    write(args.universe_out, {"generated": generated, **build_universe(args.local, planet_type_ids)})


if __name__ == "__main__":
    main()
