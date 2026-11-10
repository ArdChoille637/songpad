# Chord chart rendering and export (ChordPro / plain text). Pure logic.
from spad import theory, tabs

SECTION_TYPES = ("verse", "chorus", "bridge", "pre-chorus", "intro", "outro")
_ABBR = {"verse": "V", "chorus": "C", "bridge": "B", "pre-chorus": "P", "intro": "I", "outro": "O"}


def sec_label(sec, n=0):
    t = sec.get("type", "verse")
    return sec.get("label") or (t[:1].upper() + t[1:])


def sec_short(sec):
    return _ABBR.get(sec.get("type", "verse"), "?")


def chord_row(line, semis=0, flats=False):
    """(chord_row_text) aligned over line['t'] using offsets; collisions shift right."""
    row = ""
    for off, ch in sorted(line.get("c", [])):
        ch = theory.transpose_chord(ch, semis, flats) if semis else ch
        if len(row) < off:
            row += " " * (off - len(row))
        elif row:
            row += " "
        row += ch
    return row


def chart_lines(sec, semis=0, flats=False, width=38):
    """Yield (kind, text) tuples: 'c' chord row, 't' lyric row; wraps lyrics."""
    out = []
    for ln in sec.get("lines", []):
        txt = ln.get("t", "")
        crow = chord_row(ln, semis, flats)
        if len(txt) <= width and len(crow) <= width:
            if crow:
                out.append(("c", crow))
            out.append(("t", txt))
            continue
        pos = 0
        while pos < max(len(txt), len(crow), 1):
            seg_t = txt[pos:pos + width]
            seg_c = crow[pos:pos + width]
            if seg_c.strip():
                out.append(("c", seg_c.rstrip()))
            out.append(("t", seg_t))
            pos += width
    return out


def inline_line(line, semis=0, flats=False):
    """ChordPro line: chords inline in [brackets]."""
    txt = line.get("t", "")
    cs = sorted(line.get("c", []))
    res = ""
    last = 0
    for off, ch in cs:
        off = min(off, len(txt))
        res += txt[last:off]
        ch = theory.transpose_chord(ch, semis, flats) if semis else ch
        res += "[" + ch + "]"
        last = off
    return res + txt[last:]


def to_chordpro(song, sections, tabs_by_id, semis=0):
    flats = theory.uses_flats(song.get("key", "C"))
    key = theory.transpose_chord(song.get("key", "C"), semis, flats) if semis else song.get("key", "C")
    o = ["{title: %s}" % song.get("title", "Untitled")]
    o.append("{key: %s}" % key)
    if song.get("tempo"):
        o.append("{tempo: %d}" % song["tempo"])
    if song.get("capo"):
        o.append("{capo: %d}" % song["capo"])
    for sid in song.get("order", []):
        sec = sections.get(sid)
        if not sec:
            continue
        typ = sec.get("type", "verse")
        d = typ if typ in ("verse", "chorus", "bridge") else "verse"
        o.append("")
        o.append("{start_of_%s: %s}" % (d, sec_label(sec)))
        for ln in sec.get("lines", []):
            o.append(inline_line(ln, semis, flats))
        o.append("{end_of_%s}" % d)
    for tid in song.get("tabs", []):
        t = tabs_by_id.get(tid)
        if not t:
            continue
        o.append("")
        o.append("{start_of_tab: %s}" % t.get("name", t["inst"]))
        o.append(tabs.to_ascii(t, 80))
        o.append("{end_of_tab}")
    return "\n".join(o) + "\n"


def to_text(song, sections, tabs_by_id, semis=0):
    flats = theory.uses_flats(song.get("key", "C"))
    o = [song.get("title", "Untitled"), "Key: " + song.get("key", "C")]
    if song.get("tempo"):
        o.append("Tempo: %d bpm" % song["tempo"])
    for sid in song.get("order", []):
        sec = sections.get(sid)
        if not sec:
            continue
        o.append("")
        o.append("[%s]" % sec_label(sec))
        for kind, text in chart_lines(sec, semis, flats, 78):
            o.append(text)
    for tid in song.get("tabs", []):
        t = tabs_by_id.get(tid)
        if not t:
            continue
        o.append("")
        o.append("-- %s --" % t.get("name", t["inst"]))
        o.append(tabs.to_ascii(t, 80))
    return "\n".join(o) + "\n"
