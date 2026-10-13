#!/usr/bin/env python3
"""
Erzeugt eine kleine Test-SDE im Fuzzwork-CSV-Format, damit build_data.py und die Seite
ohne Internet getestet werden können:

    python tests/make_fixture.py /tmp/sde
    python build_data.py --local /tmp/sde
    python -m http.server 8000

Die PI-Rezepte entsprechen dem Spiel, die TypeIDs und das Universum sind ausgedacht
(1200 Testsysteme in einem Gitter). Für echte Daten build_data.py ohne --local laufen lassen.
"""

import csv
import random
import sys
from pathlib import Path

P0_TO_P1 = {
    "Aqueous Liquids": "Water", "Autotrophs": "Industrial Fibers", "Base Metals": "Reactive Metals",
    "Carbon Compounds": "Biofuels", "Complex Organisms": "Proteins", "Felsic Magma": "Silicon",
    "Heavy Metals": "Toxic Metals", "Ionic Solutions": "Electrolytes", "Micro Organisms": "Bacteria",
    "Noble Gas": "Oxygen", "Noble Metals": "Precious Metals", "Non-CS Crystals": "Chiral Structures",
    "Planktic Colonies": "Biomass", "Reactive Gas": "Oxidizing Compound", "Suspended Plasma": "Plasmoids",
}
P2 = {
    "Biocells": ["Biofuels", "Precious Metals"],
    "Construction Blocks": ["Reactive Metals", "Toxic Metals"],
    "Consumer Electronics": ["Toxic Metals", "Chiral Structures"],
    "Coolant": ["Electrolytes", "Water"],
    "Enriched Uranium": ["Precious Metals", "Toxic Metals"],
    "Fertilizer": ["Bacteria", "Proteins"],
    "Genetically Enhanced Livestock": ["Proteins", "Biomass"],
    "Livestock": ["Proteins", "Biofuels"],
    "Mechanical Parts": ["Reactive Metals", "Precious Metals"],
    "Microfiber Shielding": ["Industrial Fibers", "Silicon"],
    "Miniature Electronics": ["Chiral Structures", "Silicon"],
    "Nanites": ["Bacteria", "Reactive Metals"],
    "Oxides": ["Oxidizing Compound", "Oxygen"],
    "Polyaramids": ["Oxidizing Compound", "Industrial Fibers"],
    "Polytextiles": ["Biofuels", "Industrial Fibers"],
    "Rocket Fuel": ["Plasmoids", "Electrolytes"],
    "Silicate Glass": ["Oxidizing Compound", "Silicon"],
    "Superconductors": ["Plasmoids", "Water"],
    "Supertensile Plastics": ["Oxygen", "Biomass"],
    "Synthetic Oil": ["Electrolytes", "Oxygen"],
    "Test Cultures": ["Bacteria", "Water"],
    "Transmitter": ["Plasmoids", "Chiral Structures"],
    "Viral Agent": ["Bacteria", "Biomass"],
    "Water-Cooled CPU": ["Reactive Metals", "Water"],
}
P3 = {
    "Biotech Research Reports": ["Nanites", "Livestock", "Construction Blocks"],
    "Camera Drones": ["Silicate Glass", "Rocket Fuel"],
    "Condensates": ["Oxides", "Coolant"],
    "Cryoprotectant Solution": ["Test Cultures", "Synthetic Oil", "Fertilizer"],
    "Data Chips": ["Supertensile Plastics", "Microfiber Shielding"],
    "Gel-Matrix Biopaste": ["Oxides", "Biocells", "Superconductors"],
    "Guidance Systems": ["Water-Cooled CPU", "Transmitter"],
    "Hazmat Detection Systems": ["Polytextiles", "Viral Agent", "Transmitter"],
    "Hermetic Membranes": ["Polyaramids", "Genetically Enhanced Livestock"],
    "High-Tech Transmitters": ["Polyaramids", "Transmitter"],
    "Industrial Explosives": ["Fertilizer", "Polytextiles"],
    "Neocoms": ["Biocells", "Silicate Glass"],
    "Nuclear Reactors": ["Microfiber Shielding", "Enriched Uranium"],
    "Planetary Vehicles": ["Supertensile Plastics", "Mechanical Parts", "Miniature Electronics"],
    "Robotics": ["Mechanical Parts", "Consumer Electronics"],
    "Smartfab Units": ["Construction Blocks", "Miniature Electronics"],
    "Supercomputers": ["Water-Cooled CPU", "Coolant", "Consumer Electronics"],
    "Synthetic Synapses": ["Supertensile Plastics", "Test Cultures"],
    "Transcranial Microcontrollers": ["Biocells", "Nanites"],
    "Ukomi Superconductors": ["Synthetic Oil", "Superconductors"],
    "Vaccines": ["Livestock", "Viral Agent"],
}
P4 = {
    "Broadcast Node": ["Neocoms", "Data Chips", "High-Tech Transmitters"],
    "Integrity Response Drones": ["Gel-Matrix Biopaste", "Hazmat Detection Systems", "Planetary Vehicles"],
    "Nano-Factory": ["Industrial Explosives", "Ukomi Superconductors", "Reactive Metals"],
    "Organic Mortar Applicators": ["Condensates", "Robotics", "Bacteria"],
    "Recursive Computing Module": ["Synthetic Synapses", "Guidance Systems", "Transcranial Microcontrollers"],
    "Self-Harmonizing Power Core": ["Camera Drones", "Nuclear Reactors", "Hermetic Membranes"],
    "Sterile Conduits": ["Smartfab Units", "Vaccines", "Water"],
    "Wetware Mainframe": ["Supercomputers", "Biotech Research Reports", "Cryoprotectant Solution"],
}
PLANETS = ["Barren", "Gas", "Ice", "Lava", "Oceanic", "Plasma", "Storm", "Temperate"]
BASE = {0: 5, 1: 400, 2: 7200, 3: 60000, 4: 1200000}
VOL = {0: 0.01, 1: 0.38, 2: 1.5, 3: 6, 4: 100}


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    ids, types, tier = {}, [], {}

    def add(name, group, lv=None, base=0, vol=0):
        tid = 900000 + len(ids)
        ids[name] = tid
        types.append([tid, group, name, base, vol])
        if lv is not None:
            tier[name] = lv
        return tid

    for n in P0_TO_P1:
        add(n, 1032, 0, BASE[0], VOL[0])
    for lv, table in ((1, P0_TO_P1.values()), (2, P2), (3, P3), (4, P4)):
        for n in table:
            add(n, 1040 + lv, lv, BASE[lv], VOL[lv])
    for p in PLANETS:
        add(f"Planet ({p})", 7)
    for p in PLANETS:
        for b in ("Basic Industry Facility", "Advanced Industry Facility"):
            add(f"{p} {b}", 1028)
    for p in ("Barren", "Temperate"):
        add(f"{p} High-Tech Production Plant", 1028)

    schem, tmap, pmap = [], [], []

    def recipe(product, inputs, qty_in, qty_out, cycle, pin_kind, planets):
        sid = 100 + len(schem)
        schem.append([sid, product, cycle])
        tmap.append([sid, ids[product], qty_out, 0])
        for i in inputs:
            q = 40 if tier[i] == 1 and tier[product] == 4 else qty_in
            tmap.append([sid, ids[i], q, 1])
        for p in planets:
            pmap.append([sid, ids[f"{p} {pin_kind}"]])

    for p0, p1 in P0_TO_P1.items():
        recipe(p1, [p0], 3000, 20, 1800, "Basic Industry Facility", PLANETS)
    for n, ins in P2.items():
        recipe(n, ins, 40, 5, 3600, "Advanced Industry Facility", PLANETS)
    for n, ins in P3.items():
        recipe(n, ins, 10, 3, 3600, "Advanced Industry Facility", PLANETS)
    for n, ins in P4.items():
        recipe(n, ins, 6, 1, 3600, "High-Tech Production Plant", ["Barren", "Temperate"])

    def write(name, header, data):
        with open(out / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(data)

    write("invTypes", ["typeID", "groupID", "typeName", "basePrice", "volume", "published"],
          [t + [1] for t in types])
    write("planetSchematics", ["schematicID", "schematicName", "cycleTime"], schem)
    write("planetSchematicsTypeMap", ["schematicID", "typeID", "quantity", "isInput"], tmap)
    write("planetSchematicsPinMap", ["schematicID", "pinTypeID"], pmap)
    write("dgmTypeAttributes", ["typeID", "attributeID", "valueInt", "valueFloat"], [])

    # Universum: 3 Regionen + 1 Wurmloch-Region, 1200 Systeme im Gitter 40 x 30
    rnd = random.Random(7)
    write("mapRegions", ["regionID", "regionName"],
          [[10000001, "Testregion Nord"], [10000002, "Testregion Mitte"], [10000003, "Testregion Süd"], [11000001, "Testwurmloch"]])
    systems, planets, jumps = [], [], []
    W, H = 40, 30
    for y in range(H):
        for x in range(W):
            sid = 30000000 + y * W + x
            region = 10000001 + min(2, y // 10)
            sec = round(max(-1.0, min(1.0, 1.0 - y / 15 + rnd.uniform(-.15, .15))), 4)
            systems.append([sid, f"Testsystem {y * W + x + 1:04d}", region, sec])
            for k in range(rnd.randint(3, 10)):
                planets.append([40000000 + len(planets), ids[f"Planet ({rnd.choice(PLANETS)})"], 7, sid])
            if x + 1 < W and rnd.random() < .8:
                jumps.append([sid, sid + 1])
            if y + 1 < H and rnd.random() < .6:
                jumps.append([sid, sid + W])
    for i in range(30):
        sid = 31000000 + i
        systems.append([sid, f"J10{i:04d}", 11000001, -0.99])
        for k in range(rnd.randint(2, 8)):
            planets.append([40000000 + len(planets), ids[f"Planet ({rnd.choice(PLANETS)})"], 7, sid])
    write("mapSolarSystems", ["regionID", "solarSystemID", "solarSystemName", "security"],
          [[s[2], s[0], s[1], s[3]] for s in systems])
    write("mapDenormalize", ["itemID", "typeID", "groupID", "solarSystemID"], planets)
    write("mapSolarSystemJumps", ["fromSolarSystemID", "toSolarSystemID"],
          jumps + [[b, a] for a, b in jumps])
    print(f"Test-SDE geschrieben nach {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "sde_fixture")
