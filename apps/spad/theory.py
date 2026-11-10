# Chord math: keys, diatonic chords, transpose, capo. Pure logic, no hardware.
SHARP = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
FLAT = ("C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B")
_IDX = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
FLAT_KEYS = ("F", "Bb", "Eb", "Ab", "Db", "Gb")
MAJOR = (0, 2, 4, 5, 7, 9, 11)
MINOR = (0, 2, 3, 5, 7, 8, 10)
TRIADS = {
    "major": ("", "m", "m", "", "", "m", "dim"),
    "minor": ("m", "dim", "", "m", "m", "", ""),
}
SEVENTHS = {
    "major": ("maj7", "m7", "m7", "maj7", "7", "m7", "m7b5"),
    "minor": ("m7", "m7b5", "maj7", "m7", "m7", "maj7", "7"),
}
ROMAN = ("I", "II", "III", "IV", "V", "VI", "VII")
PROGRESSIONS = (
    ("I-V-vi-IV", (0, 4, 5, 3)),
    ("vi-IV-I-V", (5, 3, 0, 4)),
    ("I-IV-V", (0, 3, 4)),
    ("ii-V-I", (1, 4, 0)),
    ("I-vi-IV-V", (0, 5, 3, 4)),
    ("12-bar blues", (0, 0, 0, 0, 3, 3, 0, 0, 4, 3, 0, 4)),
)


def note_index(name):
    """'F#' / 'Bb' / 'c' -> 0..11, or -1 if not a note."""
    if not name:
        return -1
    base = _IDX.get(name[0].upper())
    if base is None:
        return -1
    for ch in name[1:]:
        if ch == "#":
            base += 1
        elif ch == "b":
            base -= 1
        else:
            return -1
    return base % 12


def note_name(idx, flats=False):
    return (FLAT if flats else SHARP)[idx % 12]


def split_chord(chord):
    """'F#m7/C#' -> ('F#', 'm7', 'C#'). Bass is '' when absent."""
    bass = ""
    if "/" in chord:
        chord, bass = chord.split("/", 1)
    n = 1
    if len(chord) > 1 and chord[1] in "#b":
        n = 2
    return chord[:n], chord[n:], bass


def uses_flats(key):
    root = key[:-1] if key.endswith("m") else key
    return root in FLAT_KEYS


def transpose_chord(chord, semis, flats=False):
    if not chord:
        return chord
    root, qual, bass = split_chord(chord)
    ri = note_index(root)
    if ri < 0:
        return chord
    out = note_name(ri + semis, flats) + qual
    if bass:
        bi = note_index(bass)
        out += "/" + (note_name(bi + semis, flats) if bi >= 0 else bass)
    return out


def scale(key, mode="major"):
    r = note_index(key)
    fl = uses_flats(key) or (mode == "minor" and key in ("D", "G", "C", "F", "Bb", "Eb"))
    return [note_name(r + i, fl) for i in (MAJOR if mode == "major" else MINOR)]


def diatonic(key, mode="major", sevenths=False):
    """Seven chords built on the scale of `key`."""
    names = scale(key, mode)
    quals = (SEVENTHS if sevenths else TRIADS)[mode]
    return [names[i] + quals[i] for i in range(7)]


def progression(key, mode, degrees, sevenths=False):
    ch = diatonic(key, mode, sevenths)
    return [ch[d] for d in degrees]


def capo_shapes(key, capo):
    """Key to play in (shapes) when a capo is on `capo` fret."""
    if capo <= 0:
        return key
    minor = key.endswith("m")
    root = key[:-1] if minor else key
    ri = note_index(root)
    if ri < 0:
        return key
    shape = note_name(ri - capo, uses_flats(root) or (ri - capo) % 12 in (5, 10, 3, 8, 1))
    return shape + ("m" if minor else "")
