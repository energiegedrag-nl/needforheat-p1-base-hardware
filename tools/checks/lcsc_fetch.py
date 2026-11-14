"""Fetch the LCSC/EasyEDA CAD data (symbol + footprint) of every part in the JLCPCB BOM and reduce it to
{lcsc: {name, fp, pins: {num: name}, pads: {num: [[x, y, w, h, rot, shape, drill], ...]}}} in mm, y down,
origin as easyeda2kicad uses it. This is the library JLCPCB places from.
Usage: python lcsc_fetch.py <BOM.csv> <cache dir> <out.json>   (needs: pip install easyeda2kicad)"""
import csv, json, os, sys
from easyeda2kicad.easyeda.easyeda_api import EasyedaApi
from easyeda2kicad.easyeda.easyeda_importer import EasyedaSymbolImporter, EasyedaFootprintImporter

bomf, cache, out = sys.argv[1:4]
os.makedirs(cache, exist_ok=True)
api = EasyedaApi()
res = {}
for row in csv.DictReader(open(bomf, encoding="utf8")):
    lc = row["LCSC"]
    p = os.path.join(cache, lc + ".json")
    if not os.path.exists(p):
        json.dump(api.get_cad_data_of_component(lcsc_id=lc), open(p, "w"))
    d = json.load(open(p))
    s, f = EasyedaSymbolImporter(d).get_symbol(), EasyedaFootprintImporter(d).get_footprint()
    pads = {}
    for q in f.pads:  # easyeda2kicad already converts to mm
        pads.setdefault(q.number, []).append([round(q.center_x - f.bbox.x, 3), round(q.center_y - f.bbox.y, 3),
                                              round(q.width, 3), round(q.height, 3), q.rotation, q.shape,
                                              round(2 * q.hole_radius, 3) if q.hole_radius else 0])
    res[lc] = dict(name=s.info.name, fp=f.info.name, pins={q.settings.spice_pin_number: q.name.text for q in s.pins},
                   pads=pads)
json.dump(res, open(out, "w"), indent=1)
print(len(res), "LCSC parts")
