"""Load (and flatten) symbols from KiCad symbol libraries."""
import copy, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from sexpr import parse, Sym, find, first

KICAD = os.environ.get("KICAD_DIR", os.path.expandvars(r"%LOCALAPPDATA%\Programs\KiCad\10.0"))
SYMDIR = os.path.join(KICAD, "share", "kicad", "symbols")
_cache = {}


def _lib(path):
    if path not in _cache:
        with open(path, encoding="utf8") as f:
            _cache[path] = parse(f.read())
    return _cache[path]


def _libpath(libname, extra):
    if libname in extra:
        return extra[libname]
    return os.path.join(SYMDIR, libname + ".kicad_sym")


def load_symbol(lib_id, extra=None):
    """Return a flattened symbol s-expr named lib_id (e.g. 'Device:R')."""
    extra = extra or {}
    libname, name = lib_id.split(":", 1)
    lib = _lib(_libpath(libname, extra))
    syms = {s[1]: s for s in find(lib, "symbol")}
    s = copy.deepcopy(syms[name])
    ext = first(s, "extends")
    if ext:
        parent = copy.deepcopy(syms[ext[1]])
        pname = ext[1]
        # child properties override parent's
        props = {p[1]: p for p in find(s, "property")}
        out = [Sym("symbol"), name]
        for e in parent[2:]:
            if isinstance(e, list) and e and e[0] == "property" and e[1] in props:
                out.append(props.pop(e[1]))
            elif isinstance(e, list) and e and e[0] == "symbol":
                e[1] = e[1].replace(pname + "_", name + "_", 1)
                out.append(e)
            else:
                out.append(e)
        for p in props.values():
            out.insert(2, p)
        s = out
    s[1] = lib_id
    return s


def pins(sym):
    """List of dicts: number, name, x, y, angle, unit, type."""
    res = []
    for u in find(sym, "symbol"):
        uname = u[1]
        unit = int(uname.rsplit("_", 2)[-2])
        for p in find(u, "pin"):
            at = first(p, "at")
            num = first(p, "number")[1]
            nm = first(p, "name")[1]
            res.append(dict(number=num, name=nm, x=float(at[1]), y=float(at[2]),
                            angle=int(float(at[3])) if len(at) > 3 else 0, unit=unit, type=str(p[1])))
    return res


if __name__ == "__main__":
    for lid in sys.argv[1:]:
        s = load_symbol(lid)
        print(lid, [(p["number"], p["name"], p["unit"], p["type"], p["x"], p["y"], p["angle"]) for p in pins(s)])
