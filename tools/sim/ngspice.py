"""Tiny wrapper around the ngspice shared library that ships with KiCad.

Usage: run(netlist_text) -> dict of vector name -> numpy array (last analysis).
"""
import ctypes as C
import os

import numpy as np

KICAD_BIN = os.environ.get("KICAD_BIN", os.path.expandvars(r"%LOCALAPPDATA%\Programs\KiCad\10.0\bin"))


class VecInfo(C.Structure):
    _fields_ = [("name", C.c_char_p), ("type", C.c_int), ("flags", C.c_short),
                ("realdata", C.POINTER(C.c_double)), ("compdata", C.c_void_p), ("length", C.c_int)]


_PRINT = C.CFUNCTYPE(C.c_int, C.c_char_p, C.c_int, C.c_void_p)
_STAT = C.CFUNCTYPE(C.c_int, C.c_char_p, C.c_int, C.c_void_p)
_EXIT = C.CFUNCTYPE(C.c_int, C.c_int, C.c_bool, C.c_bool, C.c_int, C.c_void_p)
_lib = None
_log = []


def _load():
    global _lib, _cbs
    if _lib:
        return _lib
    os.add_dll_directory(KICAD_BIN)
    _lib = C.CDLL(os.path.join(KICAD_BIN, "ngspice.dll"))
    _cbs = (_PRINT(lambda s, i, p: _log.append(s.decode(errors="replace")) or 0),
            _STAT(lambda s, i, p: 0), _EXIT(lambda *a: 0))
    _lib.ngSpice_Init(_cbs[0], _cbs[1], _cbs[2], None, None, None, None)
    _lib.ngGet_Vec_Info.restype = C.POINTER(VecInfo)
    _lib.ngSpice_CurPlot.restype = C.c_char_p
    _lib.ngSpice_AllVecs.restype = C.POINTER(C.c_char_p)
    return _lib


def run(netlist, analysis):
    lib = _load()
    _log.clear()
    lines = [l for l in netlist.strip().splitlines()] + [".end"]
    arr = (C.c_char_p * (len(lines) + 1))(*[l.encode() for l in lines], None)
    lib.ngSpice_Circ(arr)
    lib.ngSpice_Command(analysis.encode())
    plot = lib.ngSpice_CurPlot()
    names = []
    vp = lib.ngSpice_AllVecs(plot)
    i = 0
    while vp[i]:
        names.append(vp[i].decode())
        i += 1
    out = {}
    for n in names:
        v = lib.ngGet_Vec_Info(f"{plot.decode()}.{n}".encode())
        if v and v.contents.realdata:
            out[n.lower()] = np.ctypeslib.as_array(v.contents.realdata, shape=(v.contents.length,)).copy()
    lib.ngSpice_Command(b"remcirc")
    errs = [l for l in _log if "error" in l.lower()]
    if errs:
        print("\n".join(errs[:10]))
    return out
