#!/usr/bin/env python3
"""Build a simulator key script: one key per frame, optional start wait.
DSL on stdin/argv file: tokens separated by whitespace; 'text:Some words' types text;
'name*3' repeats a key; everything else is a key name (enter, down, n, 1 ...)."""
import sys
SAVE = ["down"] * 4 + ["right", "enter"]  # on-screen keyboard: go to SAVE


def build(src, start_wait=60):
    out = ["wait %d" % start_wait]
    for tok in src.split("\n"):
        tok = tok.strip()
        if not tok or tok.startswith("#"):
            continue
        for part in tok.split("  "):
            part = part.strip()
            if part == "SAVE":
                keys = SAVE
            elif part.startswith("text:"):
                keys = list(part[5:])  # no spaces: the sim has no key name for space
            elif "*" in part:
                k, n = part.rsplit("*", 1)
                keys = [k] * int(n)
            else:
                keys = part.split()
            for k in keys:
                out.append("keys " + k)
                out.append("wait 4")  # the on-screen keyboard drops keys faster than ~1 per 5 frames
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    sys.stdout.write(build(open(sys.argv[1]).read()))
