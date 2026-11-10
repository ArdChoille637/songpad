# Plain-JSON song storage on the SD card. `st` is picoware's Storage (or a fake in tests).
ROOT = "/picoware/songpad"


def _js():
    try:
        import ujson as js
    except ImportError:
        import json as js
    return js


def _rid(n=3):
    try:
        from os import urandom
        return "".join("%02x" % b for b in urandom(n))
    except Exception:
        import random
        return "".join("%02x" % random.randint(0, 255) for _ in range(n))


def _sig(text):
    import hashlib
    h = hashlib.sha256(text.encode()).digest()
    return "".join("%02x" % b for b in h[:8])


class Store:
    def __init__(self, st, root=ROOT):
        self.st = st
        self.root = root
        self._last = {}  # path -> last JSON written (skip identical writes, saves SD wear)
        self._mk(root)
        self._mk(root + "/songs")
        self._mk(root + "/ideas")
        self._mk(root + "/exports")

    def _mk(self, path):
        if not self.st.exists(path):
            parts = path.strip("/").split("/")
            cur = ""
            for p in parts:
                cur += "/" + p
                if not self.st.exists(cur):
                    self.st.mkdir(cur)

    def read_json(self, path, default=None):
        try:
            if not self.st.exists(path):
                return default
            raw = self.st.read(path)
            if isinstance(raw, bytes):
                raw = raw.decode()
            if not raw:
                return default
            return _js().loads(raw)
        except Exception:
            return default

    def write_json(self, path, obj):
        s = _js().dumps(obj)
        if self._last.get(path) == s:
            return True
        ok = bool(self.st.write(path, s))
        if ok:
            self._last[path] = s
        return ok

    def write_text(self, path, text):
        return bool(self.st.write(path, text))

    # ---- songs -------------------------------------------------------
    def _sd(self, sid):
        return "%s/songs/%s" % (self.root, sid)

    def index(self):
        return self.read_json(self.root + "/index.json", [])

    def _save_index(self, idx):
        self.write_json(self.root + "/index.json", idx)

    def new_song(self, title, key="C", mode="major"):
        idx = self.index()
        sid = "s" + _rid()
        while any(e["id"] == sid for e in idx):
            sid = "s" + _rid()
        song = {"v": 1, "id": sid, "title": title or "Untitled", "key": key, "mode": mode,
                "tempo": 100, "time": "4/4", "capo": 0, "order": [], "tabs": [],
                "tags": [], "rev": 1}
        d = self._sd(sid)
        self._mk(d)
        self._mk(d + "/sections")
        self._mk(d + "/tabs")
        self.write_json(d + "/song.json", song)
        idx.append({"id": sid, "t": song["title"]})
        self._save_index(idx)
        return song

    def load_song(self, sid):
        return self.read_json(self._sd(sid) + "/song.json")

    def save_song(self, song):
        song["rev"] = song.get("rev", 0) + 1
        ok = self.write_json(self._sd(song["id"]) + "/song.json", song)
        idx = self.index()
        for e in idx:
            if e["id"] == song["id"] and e["t"] != song["title"]:
                e["t"] = song["title"]
                self._save_index(idx)
        return ok

    def save_song_quiet(self, song):
        """Autosave path: same as save_song but only bumps rev when content changed."""
        return self.write_json(self._sd(song["id"]) + "/song.json", song)

    def delete_song(self, sid):
        d = self._sd(sid)
        for sub in ("sections", "tabs", "history"):
            if not self.st.exists(d + "/" + sub):
                continue
            for f in self.st.listdir(d + "/" + sub):
                self.st.remove("%s/%s/%s" % (d, sub, f))
                self._last.pop("%s/%s/%s" % (d, sub, f), None)
            self.st.rmdir(d + "/" + sub)
        self.st.remove(d + "/song.json")
        self.st.rmdir(d)
        self._save_index([e for e in self.index() if e["id"] != sid])

    # ---- sections / tabs --------------------------------------------
    def new_section(self, song, typ="verse"):
        sid = "c" + _rid(2)
        sec = {"id": sid, "type": typ, "label": typ[:1].upper() + typ[1:], "lines": [{"t": "", "c": []}]}
        self.save_section(song["id"], sec)
        song["order"].append(sid)
        return sec

    def load_section(self, song_id, sec_id):
        return self.read_json("%s/sections/%s.json" % (self._sd(song_id), sec_id))

    def save_section(self, song_id, sec):
        return self.write_json("%s/sections/%s.json" % (self._sd(song_id), sec["id"]), sec)

    def delete_section(self, song, sec_id):
        self.st.remove("%s/sections/%s.json" % (self._sd(song["id"]), sec_id))
        song["order"] = [s for s in song["order"] if s != sec_id]

    def load_sections(self, song):
        out = {}
        for sid in song["order"]:
            if sid not in out:
                s = self.load_section(song["id"], sid)
                if s:
                    out[sid] = s
        return out

    def new_tab(self, song, tab):
        tid = "t" + _rid(2)
        tab["id"] = tid
        tab.setdefault("name", tab["inst"][:1].upper() + tab["inst"][1:])
        self.save_tab(song["id"], tab)
        song["tabs"].append(tid)
        return tab

    def load_tab(self, song_id, tid):
        return self.read_json("%s/tabs/%s.json" % (self._sd(song_id), tid))

    def save_tab(self, song_id, tab):
        return self.write_json("%s/tabs/%s.json" % (self._sd(song_id), tab["id"]), tab)

    def load_tabs(self, song):
        out = {}
        for tid in song["tabs"]:
            t = self.load_tab(song["id"], tid)
            if t:
                out[tid] = t
        return out

    # ---- revision history ---------------------------------------------
    MAX_REV = 20

    def _hd(self, sid):
        return self._sd(sid) + "/history"

    def revisions(self, sid):
        """Newest first: [{'seq','ts','why','ns','nt'}]."""
        return list(reversed(self.read_json(self._hd(sid) + "/index.json", [])))

    def snapshot(self, song, secs, tabs_by_id, ts=0, why="auto"):
        """Save the whole song as a revision. Returns the seq, or 0 if nothing changed."""
        sid = song["id"]
        body = {"song": song, "secs": secs, "tabs": tabs_by_id}
        # compare ignoring the bumping rev counter
        probe = dict(song)
        probe.pop("rev", None)
        sig = _js().dumps({"song": probe, "secs": secs, "tabs": tabs_by_id})
        hd = self._hd(sid)
        self._mk(hd)
        idx = self.read_json(hd + "/index.json", [])
        if idx and idx[-1].get("sig") == _sig(sig):
            return 0
        seq = (idx[-1]["seq"] + 1) if idx else 1
        self.write_json("%s/r%d.json" % (hd, seq), body)
        idx.append({"seq": seq, "ts": ts, "why": why, "ns": len(secs), "nt": len(tabs_by_id),
                    "sig": _sig(sig)})
        while len(idx) > self.MAX_REV:
            old = idx.pop(0)
            try:
                self.st.remove("%s/r%d.json" % (hd, old["seq"]))
            except Exception:
                pass
        self.write_json(hd + "/index.json", idx)
        return seq

    def restore(self, song, secs, tabs_by_id, seq, ts=0):
        """Roll the song back to revision `seq`. The current state is snapshotted first."""
        sid = song["id"]
        body = self.read_json("%s/r%d.json" % (self._hd(sid), seq))
        if not body:
            return None
        self.snapshot(song, secs, tabs_by_id, ts, "before restore")
        new = body["song"]
        for sub in ("sections", "tabs"):
            d = "%s/%s" % (self._sd(sid), sub)
            for f in self.st.listdir(d):
                self.st.remove(d + "/" + f)
                self._last.pop(d + "/" + f, None)
        self.write_json(self._sd(sid) + "/song.json", new)
        for s in body["secs"].values():
            self.save_section(sid, s)
        for t in body["tabs"].values():
            self.save_tab(sid, t)
        idx = self.index()
        for e in idx:
            if e["id"] == sid and e["t"] != new["title"]:
                e["t"] = new["title"]
                self._save_index(idx)
        return new, body["secs"], body["tabs"]

    # ---- ideas -------------------------------------------------------
    def _idea_file(self, ym):
        return "%s/ideas/ideas-%s.json" % (self.root, ym)

    def add_idea(self, text, ts, ym):
        f = self._idea_file(ym)
        items = self.read_json(f, [])
        items.append({"id": "i" + _rid(2), "ts": ts, "text": text})
        self.write_json(f, items)

    def list_ideas(self):
        """Newest first across all month files."""
        names = sorted(n for n in self.st.listdir(self.root + "/ideas") if n.startswith("ideas-"))
        out = []
        for n in reversed(names):
            out.extend(reversed(self.read_json("%s/ideas/%s" % (self.root, n), [])))
        return out
