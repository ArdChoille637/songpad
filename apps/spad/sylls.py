# Heuristic syllable counter (no dictionary needed).
_V = "aeiouy"


def word_syllables(w):
    w = "".join(c for c in w.lower() if c.isalpha())
    if not w:
        return 0
    n = 0
    prev = False
    for c in w:
        v = c in _V
        if v and not prev:
            n += 1
        prev = v
    if len(w) > 2 and w.endswith("e") and w[-2] not in _V:
        if not (w.endswith("le") and len(w) > 2 and w[-3] not in _V):
            n -= 1
    elif w.endswith("es") or w.endswith("ed"):
        if len(w) > 3 and w[-3] not in _V and not (w[-3] in "td" and w.endswith("ed")) \
                and not (w[-3] in "sxzc" and w.endswith("es")):
            n -= 1
    return n if n > 0 else 1


def line_syllables(text):
    return sum(word_syllables(w) for w in text.replace("-", " ").split())
