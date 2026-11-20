"""Minimal S-expression reader/writer for KiCad files (kept small on purpose)."""
import re

BS = chr(92)  # backslash
_tok = re.compile(r'\s*(?:(\()|(\))|("(?:[^"\\]|\\.)*")|([^\s()"]+))')
_unesc = re.compile(r'\\(.)')


class Sym(str):
    """An unquoted atom."""


def parse(text):
    stack, cur = [], []
    pos = 0
    n = len(text)
    while pos < n:
        m = _tok.match(text, pos)
        if not m or m.end() == pos:
            break
        pos = m.end()
        lp, rp, s, a = m.groups()
        if lp:
            stack.append(cur)
            cur = []
        elif rp:
            done = cur
            cur = stack.pop()
            cur.append(done)
        elif s is not None:
            cur.append(_unesc.sub(r'\1', s[1:-1]))
        elif a is not None:
            cur.append(Sym(a))
    return cur[0]


def q(s):
    return '"' + s.replace(BS, BS + BS).replace('"', BS + '"').replace("\n", BS + "n") + '"'


def dump(x, ind=0):
    if isinstance(x, list):
        if not x:
            return "()"
        simple = all(not isinstance(e, list) for e in x)
        if simple and len(x) < 8:
            return "(" + " ".join(dump(e) for e in x) + ")"
        out = "(" + dump(x[0])
        for e in x[1:]:
            if isinstance(e, list):
                out += "\n" + "\t" * (ind + 1) + dump(e, ind + 1)
            else:
                out += " " + dump(e)
        return out + ")"
    if isinstance(x, Sym):
        return str(x)
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, float):
        s = ("%.4f" % x).rstrip("0").rstrip(".")
        return "0" if s in ("-0", "") else s
    if isinstance(x, int):
        return str(x)
    return q(x)


def find(node, key):
    return [e for e in node if isinstance(e, list) and e and e[0] == key]


def first(node, key):
    r = find(node, key)
    return r[0] if r else None
