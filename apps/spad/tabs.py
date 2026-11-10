# Tab model + ASCII renderer for guitar, bass and drums. Pure logic.
GUITAR = ("e", "B", "G", "D", "A", "E")
BASS = ("G", "D", "A", "E")
DRUM_ROWS = ("CC", "HH", "Rd", "SD", "T1", "T2", "FT", "BD", "Hf")
DRUM_DEFAULT = ("HH", "SD", "BD")
DRUM_LEGEND = "x=cymbal o=hit X/O=accent g=ghost f=flam d=drag @=rim #=choke"
TECH = {"h": "h", "p": "p", "s": "/", "l": "\\", "b": "b", "r": "r", "v": "~", "x": "x"}


def new_tab(inst="guitar", bars=1):
    if inst == "drums":
        t = {"inst": "drums", "steps": 16, "rows": list(DRUM_DEFAULT), "bars": []}
    else:
        tun = BASS if inst == "bass" else GUITAR
        t = {"inst": inst, "strings": len(tun), "tuning": list(tun), "steps": 8, "bars": []}
    for _ in range(bars):
        add_bar(t)
    return t


def add_bar(t):
    if t["inst"] == "drums":
        t["bars"].append({r: "-" * t["steps"] for r in t["rows"]})
    else:
        t["bars"].append({"n": []})
    return len(t["bars"]) - 1


def n_steps(t):
    return t["steps"]


def n_rows(t):
    return len(t["rows"]) if t["inst"] == "drums" else t["strings"]


def get_cell(t, bar, step, row):
    """Token at (bar, step, row). Rows: string index (0=high) or drum row index."""
    b = t["bars"][bar]
    if t["inst"] == "drums":
        s = b[t["rows"][row]][step]
        return "" if s == "-" else s
    for n in b["n"]:
        if n[0] == step and n[1] == row:
            return n[2]
    return ""


def set_cell(t, bar, step, row, token):
    b = t["bars"][bar]
    if t["inst"] == "drums":
        name = t["rows"][row]
        line = b[name]
        b[name] = line[:step] + ((token or "-")[0]) + line[step + 1:]
        return
    notes = [n for n in b["n"] if not (n[0] == step and n[1] == row)]
    if token:
        notes.append([step, row, token])
    notes.sort()
    b["n"] = notes


def add_drum_row(t, name):
    if name in t["rows"]:
        return
    t["rows"].append(name)
    t["rows"].sort(key=lambda r: DRUM_ROWS.index(r) if r in DRUM_ROWS else 99)
    for b in t["bars"]:
        b[name] = "-" * t["steps"]


def _guitar_bar_cols(t, bar):
    """Per-step column widths and a row->cells grid for one bar."""
    steps = t["steps"]
    widths = [2] * steps
    for st, _sr, tok in t["bars"][bar]["n"]:
        if len(tok) > widths[st]:
            widths[st] = len(tok)
    rows = []
    for r in range(t["strings"]):
        cells = []
        for s in range(steps):
            tok = get_cell(t, bar, s, r)
            cells.append(tok + "-" * (widths[s] - len(tok)))
        rows.append("".join(cells))
    return rows


def bar_rows(t, bar):
    """Rendered text rows for one bar (without label/bar lines)."""
    if t["inst"] == "drums":
        return [t["bars"][bar][r] for r in t["rows"]]
    return _guitar_bar_cols(t, bar)


def row_labels(t):
    if t["inst"] == "drums":
        return [r.ljust(2) for r in t["rows"]]
    return [x.ljust(2) for x in t["tuning"]]


def to_ascii(t, max_cols=80):
    """Whole tab as text, wrapping bars to fit max_cols."""
    labels = row_labels(t)
    out = []
    i = 0
    nb = len(t["bars"])
    while i < nb:
        grids = []
        width = 3
        while i < nb:
            g = bar_rows(t, i)
            w = len(g[0]) + 1
            if grids and width + w > max_cols:
                break
            grids.append(g)
            width += w
            i += 1
        for r in range(len(labels)):
            out.append(labels[r] + "|" + "|".join(g[r] for g in grids) + "|")
        out.append("")
    if t["inst"] == "drums":
        out.append(DRUM_LEGEND)
    return "\n".join(out).rstrip("\n")
