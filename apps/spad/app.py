# SongPad UI: screens + input handling. Logic lives in theory/tabs/fmt/store.
from picoware.system.vector import Vector
from picoware.system.colors import (
    TFT_BLACK, TFT_WHITE, TFT_BLUE, TFT_CYAN, TFT_YELLOW, TFT_GREEN, TFT_RED, TFT_DARKGREY,
)
from picoware.system.buttons import (
    BUTTON_UP, BUTTON_DOWN, BUTTON_LEFT, BUTTON_RIGHT, BUTTON_CENTER, BUTTON_OK, BUTTON_ENTER,
    BUTTON_BACK, BUTTON_BACKSPACE, BUTTON_DELETE, BUTTON_SPACE,
    BUTTON_A, BUTTON_B, BUTTON_C, BUTTON_D, BUTTON_F, BUTTON_G, BUTTON_H, BUTTON_J, BUTTON_L, BUTTON_M,
    BUTTON_N, BUTTON_O, BUTTON_P, BUTTON_Q, BUTTON_R, BUTTON_S, BUTTON_T, BUTTON_V, BUTTON_X, BUTTON_Y,
    BUTTON_0, BUTTON_1, BUTTON_2, BUTTON_3, BUTTON_4, BUTTON_5, BUTTON_6, BUTTON_7, BUTTON_8, BUTTON_9,
    BUTTON_COMMA, BUTTON_PERIOD, BUTTON_PLUS, BUTTON_MINUS, BUTTON_EQUAL, BUTTON_AT, BUTTON_HASH,
    BUTTON_SLASH, BUTTON_BACKSLASH,
)
from spad import theory, tabs, fmt, sylls
from spad.store import Store

SELECT = (BUTTON_CENTER, BUTTON_OK, BUTTON_ENTER)
DIGITS = {BUTTON_0: 0, BUTTON_1: 1, BUTTON_2: 2, BUTTON_3: 3, BUTTON_4: 4,
          BUTTON_5: 5, BUTTON_6: 6, BUTTON_7: 7, BUTTON_8: 8, BUTTON_9: 9}
KEYS = ("C", "G", "D", "A", "E", "B", "F#", "F", "Bb", "Eb", "Ab", "Db")
FG, BG, HI, DIM = TFT_WHITE, TFT_BLACK, TFT_CYAN, TFT_DARKGREY
ABOUT = ("Offline songwriting notebook", "Lyrics, chords, guitar/bass/drum tab",
         "Files: /picoware/songpad/", "Plain JSON + ChordPro/TXT export")


def V(x, y):
    return Vector(x, y)


class App:
    def __init__(self, vm):
        self.vm = vm
        self.d = vm.draw
        self.W = self.d.size.x
        self.H = self.d.size.y
        fs = self.d.font_size
        self.cw = max(fs.x, 5)
        self.lh = fs.y + 3
        self.cols = self.W // self.cw
        self.store = Store(vm.storage)
        self.mode = "home"
        self.stack = []
        self.sel = 0
        self.scroll = 0
        self.msg = ""
        self.dirty = True
        self.song = None
        self.secs = {}
        self.sec = None
        self.line = 0
        self.col = 0
        self.sevenths = False
        self.semis = 0
        self.tab = None
        self.tbar = self.tstep = self.trow = 0
        self.last_digit_at = -1
        self.ask_cb = None
        self.ask_text = ""
        self.confirm = None
        self.kb_done = None
        self.edited = False
        self.last_flush = 0
        self.last_snap = 0
        self.last_snap_edit = False
        self.revs = []
        # metronome
        self.bpm = 100
        self.beat = 0
        self.beat_at = 0
        self.running = False
        self.taps = []
        # chord helper
        self.ck = 0
        self.cminor = False
        self.ccapo = 0

    # ---------------------------------------------------------- drawing
    def begin(self, title, hint=""):
        d = self.d
        d.erase()
        d.fill_rectangle(V(0, 0), V(self.W, self.lh + 4), TFT_BLUE)
        d.text(V(4, 3), title[: self.cols - 1], FG)
        if hint:
            y = self.H - self.lh - 2
            d.fill_rectangle(V(0, y), V(self.W, self.lh + 2), DIM)
            d.text(V(4, y + 2), hint[: self.cols - 1], HI)
        if self.msg:
            d.text(V(4, self.H - 2 * self.lh - 4), self.msg[: self.cols - 1], TFT_YELLOW)

    def end(self):
        self.d.swap()
        self.dirty = False

    def body_rows(self):
        return (self.H - 3 * self.lh - 10) // self.lh

    def list_view(self, items, top=None):
        """Draw a scrolling selectable list; returns nothing."""
        top = self.lh + 10 if top is None else top
        rows = self.body_rows()
        if self.sel < self.scroll:
            self.scroll = self.sel
        elif self.sel >= self.scroll + rows:
            self.scroll = self.sel - rows + 1
        for i in range(self.scroll, min(len(items), self.scroll + rows)):
            y = top + (i - self.scroll) * self.lh
            if i == self.sel:
                self.d.fill_rectangle(V(0, y - 1), V(self.W, self.lh), TFT_BLUE)
            self.d.text(V(8, y), items[i][: self.cols - 2], FG)

    def flash(self, text):
        self.msg = text
        self.dirty = True

    # ---------------------------------------------------------- navigation
    def go(self, mode, push=True):
        if push:
            self.stack.append((self.mode, self.sel, self.scroll))
        self.mode = mode
        self.sel = self.scroll = 0
        self.msg = ""
        self.dirty = True

    def back(self):
        self.msg = ""
        self.dirty = True
        if self.stack:
            self.mode, self.sel, self.scroll = self.stack.pop()
            return True
        return False

    # ---------------------------------------------------------- text entry
    def ask(self, title, initial, cb, max_chars=0):
        kb = self.vm.keyboard
        kb.reset()
        kb.title = title
        kb.response = initial
        self.ask_cb = cb
        self.ask_max = max_chars
        self.prev_mode = self.mode
        self.mode = "ask"
        self.vm.input_manager.reset()
        kb.run(force=True)

    def run_ask(self, button):
        kb = self.vm.keyboard
        if button == BUTTON_BACK:
            self.finish_ask(None)
            return
        running = kb.run(max_characters=self.ask_max)
        if kb.is_finished:
            self.finish_ask(kb.response)
        elif not running:
            self.finish_ask(None)

    def finish_ask(self, text):
        self.vm.keyboard.reset()
        self.mode = self.prev_mode
        cb, self.ask_cb = self.ask_cb, None
        self.vm.input_manager.reset()
        self.dirty = True
        if text is not None and cb:
            cb(text)
            self.touch()

    # ---------------------------------------------------------- persistence
    def save_song(self):
        if self.song:
            self.store.save_song(self.song)

    def open_song(self, sid):
        s = self.store.load_song(sid)
        if not s:
            self.flash("Could not open song")
            return
        self.song = s
        self.sec = self.tab = None
        self.edited = False
        self.last_snap = self.now()
        self.secs = self.store.load_sections(s)
        self.bpm = s.get("tempo", 100)
        self.go("song")

    # ---------------------------------------------------------- run loop
    AUTOSAVE_MS = 3000       # flush edits to the SD card this soon after the last change
    CHECKPOINT_MS = 120000   # also keep a revision at least this often while editing

    def touch(self):
        """Mark the open song as changed; autosave picks it up."""
        if not self.edited:
            self.edited = True
            self.edit_at = self.now()

    def now(self):
        from time import ticks_ms
        return ticks_ms()

    def wall(self):
        from time import time
        try:
            return int(time())
        except Exception:
            return 0

    def flush(self, snap=False, why="auto"):
        """Write everything dirty (current section, tab, song). Optionally keep a revision."""
        if not self.song:
            return
        try:
            if self.sec is not None and self.sec["id"] in self.secs:
                self.store.save_section(self.song["id"], self.sec)
            if self.tab is not None:
                self.store.save_tab(self.song["id"], self.tab)
            self.store.save_song_quiet(self.song)
            if snap:
                tbs = self.store.load_tabs(self.song)
                if self.tab is not None:
                    tbs[self.tab["id"]] = self.tab
                if self.store.snapshot(self.song, self.secs, tbs, self.wall(), why):
                    self.last_snap = self.now()
            self.edited = False
            self.last_flush = self.now()
        except Exception as e:
            self.flash("Autosave failed: " + str(e)[:24])

    def autosave_tick(self):
        if not self.edited:
            return
        from time import ticks_diff
        n = self.now()
        if ticks_diff(n, self.edit_at) >= self.AUTOSAVE_MS:
            snap = ticks_diff(n, self.last_snap) >= self.CHECKPOINT_MS
            self.flush(snap, "autosave")

    def tick(self):
        b = self.vm.button
        if self.song and self.mode in ("lines", "tab", "sections", "info", "song"):
            self.autosave_tick()
        if self.mode == "ask":
            self.run_ask(b)
            return
        if self.mode == "metro":
            self.metro_tick()
        if b == -1:
            if self.dirty:
                getattr(self, "draw_" + self.mode)()
            return
        self.vm.input_manager.reset()
        if self.confirm:
            self.do_confirm(b)
        else:
            getattr(self, "key_" + self.mode)(b)
            if self.mode in ("lines", "tab", "sections", "info") and b not in (
                    BUTTON_UP, BUTTON_DOWN, BUTTON_LEFT, BUTTON_RIGHT, BUTTON_BACK):
                self.touch()
        if self.mode != "ask":
            getattr(self, "draw_" + self.mode)()

    def do_confirm(self, b):
        cb, self.confirm = self.confirm, None
        self.msg = ""
        if b == BUTTON_Y:
            cb()
        self.dirty = True

    def ask_confirm(self, text, cb):
        self.confirm = cb
        self.flash(text + " Y/N")

    # ================================================================ HOME
    HOME = ("Songs", "Chord helper", "Metronome", "Ideas", "About")

    def draw_home(self):
        self.begin("SongPad", "Up/Down + Enter   Back=exit")
        self.list_view(self.HOME)
        self.end()

    def key_home(self, b):
        if b == BUTTON_UP:
            self.sel = (self.sel - 1) % len(self.HOME)
        elif b == BUTTON_DOWN:
            self.sel = (self.sel + 1) % len(self.HOME)
        elif b in SELECT:
            self.go(("songs", "chords", "metro", "ideas", "about")[self.sel])
        elif b == BUTTON_BACK:
            self.vm.back()

    def draw_about(self):
        self.begin("About", "Back")
        for i, t in enumerate(ABOUT):
            self.d.text(V(8, self.lh + 14 + i * self.lh), t, FG)
        self.end()

    def key_about(self, b):
        if b == BUTTON_BACK or b in SELECT:
            self.back()

    # ================================================================ SONGS
    def draw_songs(self):
        idx = self.store.index()
        self.begin("Songs (%d)" % len(idx), "Enter open  N new  D delete")
        if idx:
            self.list_view([e["t"] for e in idx])
        else:
            self.d.text(V(8, self.lh + 14), "No songs yet - press N", FG)
        self.end()

    def key_songs(self, b):
        idx = self.store.index()
        n = len(idx)
        if b == BUTTON_UP and n:
            self.sel = (self.sel - 1) % n
        elif b == BUTTON_DOWN and n:
            self.sel = (self.sel + 1) % n
        elif b in SELECT and n:
            self.open_song(idx[self.sel]["id"])
        elif b == BUTTON_N:
            def made(t):
                s = self.store.new_song(t.strip() or "Untitled")
                self.open_song(s["id"])
            self.ask("Song title", "", made, 40)
        elif b == BUTTON_D and n:
            sid = idx[self.sel]["id"]
            self.ask_confirm("Delete %s?" % idx[self.sel]["t"][:20], lambda: self.del_song(sid))
        elif b == BUTTON_BACK:
            self.back()

    def del_song(self, sid):
        self.store.delete_song(sid)
        self.sel = max(0, self.sel - 1)

    # ================================================================ SONG
    SONG = ("Lyrics & chords", "Chord chart", "Tabs", "Song info", "History", "Export")

    def draw_song(self):
        s = self.song
        self.begin(s["title"], "Enter open   Back")
        self.d.text(V(8, self.lh + 8), "Key %s %s  %d bpm  capo %d" % (
            s["key"], s["mode"], s["tempo"], s["capo"]), HI)
        self.list_view(self.SONG, top=self.lh * 2 + 14)
        self.end()

    def key_song(self, b):
        if b == BUTTON_UP:
            self.sel = (self.sel - 1) % len(self.SONG)
        elif b == BUTTON_DOWN:
            self.sel = (self.sel + 1) % len(self.SONG)
        elif b in SELECT:
            if self.sel == 5:
                self.do_export()
                return
            self.semis = 0
            if self.sel == 4:
                self.flush(True, "checkpoint")
                self.revs = self.store.revisions(self.song["id"])
            self.go(("sections", "chart", "tabs", "info", "history")[self.sel])
        elif b == BUTTON_BACK:
            self.flush(True, "closed song")
            self.back()

    def do_export(self):
        s = self.song
        tbs = self.store.load_tabs(s)
        base = "%s/exports/%s" % (self.store.root, "".join(
            c if c.isalpha() or c.isdigit() else "_" for c in s["title"])[:24] or s["id"])
        self.store.write_text(base + ".cho", fmt.to_chordpro(s, self.secs, tbs))
        self.store.write_text(base + ".txt", fmt.to_text(s, self.secs, tbs))
        self.flash("Saved " + base.split("/")[-1] + ".cho/.txt")

    # ================================================================ INFO
    def draw_info(self):
        s = self.song
        self.begin("Song info", "Up/Dn field  L/R change  Enter rename")
        rows = ("Title: " + s["title"], "Key: %s" % s["key"], "Mode: " + s["mode"],
                "Tempo: %d bpm" % s["tempo"], "Capo: %d" % s["capo"],
                "Play shapes in: " + theory.capo_shapes(s["key"], s["capo"]))
        self.list_view(rows)
        self.end()

    def key_info(self, b):
        s = self.song
        if b == BUTTON_UP:
            self.sel = (self.sel - 1) % 5
        elif b == BUTTON_DOWN:
            self.sel = (self.sel + 1) % 5
        elif b in (BUTTON_LEFT, BUTTON_RIGHT):
            d = 1 if b == BUTTON_RIGHT else -1
            if self.sel == 1:
                i = KEYS.index(s["key"]) if s["key"] in KEYS else 0
                s["key"] = KEYS[(i + d) % len(KEYS)]
            elif self.sel == 2:
                s["mode"] = "minor" if s["mode"] == "major" else "major"
            elif self.sel == 3:
                s["tempo"] = max(30, min(260, s["tempo"] + d * 2))
            elif self.sel == 4:
                s["capo"] = max(0, min(12, s["capo"] + d))
        elif b in SELECT and self.sel == 0:
            def ren(t):
                s["title"] = t.strip() or s["title"]
            self.ask("Song title", s["title"], ren, 40)
        elif b == BUTTON_BACK:
            self.save_song()
            self.back()

    # ================================================================ SECTIONS
    def sec_items(self):
        out = []
        for sid in self.song["order"]:
            sc = self.secs.get(sid)
            n = len(sc["lines"]) if sc else 0
            out.append("%d. %s (%d lines)" % (len(out) + 1, sc["label"] if sc else "?", n))
        return out

    def draw_sections(self):
        self.begin("Sections", "Enter edit N new T type Q/A move R repeat D del")
        items = self.sec_items()
        if items:
            self.list_view(items)
        else:
            self.d.text(V(8, self.lh + 14), "Empty - press N to add a verse", FG)
        self.end()

    def key_sections(self, b):
        order = self.song["order"]
        n = len(order)
        if b == BUTTON_UP and n:
            self.sel = (self.sel - 1) % n
        elif b == BUTTON_DOWN and n:
            self.sel = (self.sel + 1) % n
        elif b in SELECT and n:
            self.sec = self.secs[order[self.sel]]
            self.line = self.col = 0
            self.go("lines")
        elif b == BUTTON_N:
            typ = "verse" if n == 0 else ("chorus" if self.secs[order[-1]]["type"] == "verse" else "verse")
            sc = self.store.new_section(self.song, typ)
            self.secs[sc["id"]] = sc
            self.save_song()
            self.sel = len(order) - 1
        elif b == BUTTON_T and n:
            sc = self.secs[order[self.sel]]
            ts = fmt.SECTION_TYPES
            sc["type"] = ts[(ts.index(sc["type"]) + 1) % len(ts)]
            sc["label"] = sc["type"][:1].upper() + sc["type"][1:]
            self.store.save_section(self.song["id"], sc)
        elif b == BUTTON_Q and n and self.sel > 0:
            order[self.sel - 1], order[self.sel] = order[self.sel], order[self.sel - 1]
            self.sel -= 1
            self.save_song()
        elif b == BUTTON_A and n and self.sel < n - 1:
            order[self.sel + 1], order[self.sel] = order[self.sel], order[self.sel + 1]
            self.sel += 1
            self.save_song()
        elif b == BUTTON_R and n:
            order.append(order[self.sel])
            self.save_song()
            self.flash("Added a repeat at the end")
        elif b == BUTTON_D and n:
            self.ask_confirm("Remove section?", self.del_section)
        elif b == BUTTON_BACK:
            self.save_song()
            self.back()

    def del_section(self):
        order = self.song["order"]
        sid = order.pop(self.sel)
        self.sec = None
        if sid not in order:
            self.store.delete_section(self.song, sid)
            self.secs.pop(sid, None)
        self.sel = max(0, min(self.sel, len(order) - 1))
        self.save_song()

    # ================================================================ LINES (lyrics + chords)
    def chords_now(self):
        s = self.song
        return theory.diatonic(s["key"], s["mode"], self.sevenths)

    def draw_lines(self):
        sc, d = self.sec, self.d
        self.begin("%s  key %s" % (sc["label"], self.song["key"]),
                   "1-7 chord 0 clr Ent text N new D del S 7th")
        ch = self.chords_now()
        d.text(V(4, self.lh + 8), " ".join("%d:%s" % (i + 1, c) for i, c in enumerate(ch))[: self.cols - 1], HI)
        y = self.lh * 2 + 12
        rows = (self.H - y - self.lh * 3) // (self.lh * 2)
        first = max(0, min(self.line - rows // 2, len(sc["lines"]) - rows))
        for i in range(first, min(len(sc["lines"]), first + rows)):
            ln = sc["lines"][i]
            sel = i == self.line
            if sel:
                d.fill_rectangle(V(0, y - 1), V(self.W, self.lh * 2), TFT_BLUE)
            d.text(V(4, y), fmt.chord_row(ln)[: self.cols - 8], TFT_YELLOW)
            d.text(V(4, y + self.lh), ln["t"][: self.cols - 8], FG)
            d.text(V(self.W - 6 * self.cw, y + self.lh), "%ds" % sylls.line_syllables(ln["t"]), DIM)
            if sel:
                cx = 4 + min(self.col, self.cols - 9) * self.cw
                d.fill_rectangle(V(cx, y + self.lh * 2 - 3), V(self.cw, 2), TFT_GREEN)
            y += self.lh * 2 + 2
        self.end()

    def key_lines(self, b):
        sc = self.sec
        lines = sc["lines"]
        ln = lines[self.line]
        if b == BUTTON_UP and self.line > 0:
            self.line -= 1
        elif b == BUTTON_DOWN and self.line < len(lines) - 1:
            self.line += 1
        elif b == BUTTON_LEFT:
            self.col = max(0, self.col - 1)
        elif b == BUTTON_RIGHT:
            self.col = min(len(ln["t"]), self.col + 1)
        elif b in DIGITS:
            k = DIGITS[b]
            ln["c"] = [c for c in ln["c"] if c[0] != self.col]
            if 1 <= k <= 7:
                ln["c"].append([self.col, self.chords_now()[k - 1]])
                ln["c"].sort()
        elif b == BUTTON_S:
            self.sevenths = not self.sevenths
        elif b in SELECT:
            def edit(t):
                ln["t"] = t
                ln["c"] = [c for c in ln["c"] if c[0] <= len(t)]
                self.col = min(self.col, len(t))
            self.ask("Lyric line", ln["t"], edit, 80)
        elif b == BUTTON_N:
            lines.insert(self.line + 1, {"t": "", "c": []})
            self.line += 1
            self.col = 0
        elif b == BUTTON_D and len(lines) > 1:
            lines.pop(self.line)
            self.line = min(self.line, len(lines) - 1)
        elif b == BUTTON_BACK:
            self.flush(True, "edited lyrics")
            self.back()
        self.col = min(self.col, len(lines[self.line]["t"]))

    # ================================================================ CHART
    def chart_rows(self):
        rows = []
        flats = theory.uses_flats(self.song["key"])
        for sid in self.song["order"]:
            sc = self.secs.get(sid)
            if not sc:
                continue
            rows.append(("h", "[%s]" % sc["label"]))
            rows.extend(fmt.chart_lines(sc, self.semis, flats, self.cols - 2))
            rows.append(("t", ""))
        return rows

    def draw_chart(self):
        s = self.song
        key = theory.transpose_chord(s["key"], self.semis, theory.uses_flats(s["key"])) if self.semis else s["key"]
        self.begin("%s - key %s" % (s["title"][:18], key), "L/R transpose  Up/Dn scroll")
        rows = self.chart_rows()
        n = (self.H - 3 * self.lh - 10) // self.lh
        self.sel = max(0, min(self.sel, max(0, len(rows) - n)))
        y = self.lh + 10
        colr = {"h": HI, "c": TFT_YELLOW, "t": FG}
        for kind, text in rows[self.sel: self.sel + n]:
            self.d.text(V(4, y), text, colr[kind])
            y += self.lh
        self.end()

    def key_chart(self, b):
        if b == BUTTON_UP:
            self.sel = max(0, self.sel - 3)
        elif b == BUTTON_DOWN:
            self.sel += 3
        elif b in (BUTTON_LEFT, BUTTON_RIGHT):
            self.semis = (self.semis + (1 if b == BUTTON_RIGHT else -1) + 6) % 12 - 6
        elif b == BUTTON_BACK:
            self.semis = 0
            self.back()

    # ================================================================ TABS
    def draw_tabs(self):
        self.begin("Tabs", "Enter edit  G guitar B bass D drums  X del")
        items = []
        for tid in self.song["tabs"]:
            t = self.store.load_tab(self.song["id"], tid)
            items.append("%s (%d bars)" % (t.get("name", "?"), len(t["bars"])) if t else "?")
        if items:
            self.list_view(items)
        else:
            self.d.text(V(8, self.lh + 14), "None - G, B or D adds a tab", FG)
        self.end()

    def key_tabs(self, b):
        ids = self.song["tabs"]
        n = len(ids)
        if b == BUTTON_UP and n:
            self.sel = (self.sel - 1) % n
        elif b == BUTTON_DOWN and n:
            self.sel = (self.sel + 1) % n
        elif b in SELECT and n:
            self.tab = self.store.load_tab(self.song["id"], ids[self.sel])
            self.tbar = self.tstep = self.trow = 0
            self.go("tab")
        elif b in (BUTTON_G, BUTTON_B, BUTTON_D):
            inst = {BUTTON_G: "guitar", BUTTON_B: "bass", BUTTON_D: "drums"}[b]
            self.store.new_tab(self.song, tabs.new_tab(inst, 1))
            self.save_song()
            self.sel = len(ids) - 1
        elif b == BUTTON_X and n:
            self.ask_confirm("Delete tab?", self.del_tab)
        elif b == BUTTON_BACK:
            self.back()

    def del_tab(self):
        tid = self.song["tabs"].pop(self.sel)
        self.tab = None
        self.store.st.remove("%s/songs/%s/tabs/%s.json" % (self.store.root, self.song["id"], tid))
        self.sel = max(0, self.sel - 1)
        self.save_song()

    # ================================================================ TAB EDITOR
    def draw_tab(self):
        t, d = self.tab, self.d
        drums = t["inst"] == "drums"
        self.begin("%s  bar %d/%d" % (t["name"], self.tbar + 1, len(t["bars"])),
                   "arrows move 0-9 fret hpslbrvx  Bksp clr N bar ,/. bar")
        steps = t["steps"]
        cw = self.cw * (2 if drums else 4)
        x0 = 4 + self.cw * 3
        y0 = self.lh + 14
        labels = tabs.row_labels(t)
        rh = self.lh + 3
        for r in range(tabs.n_rows(t)):
            y = y0 + r * rh
            d.text(V(4, y), labels[r], HI)
            for s in range(steps):
                x = x0 + s * cw
                tok = tabs.get_cell(t, self.tbar, s, r)
                cur = s == self.tstep and r == self.trow
                if cur:
                    d.fill_rectangle(V(x, y - 1), V(cw, rh), TFT_BLUE)
                d.text(V(x + 2, y), tok if tok else ("-" if not drums else "."), FG if tok else DIM)
            d.fill_rectangle(V(x0 - 3, y - 1), V(1, rh), DIM)
        if not drums:
            cell = tabs.get_cell(t, self.tbar, self.tstep, self.trow)
            d.text(V(4, y0 + tabs.n_rows(t) * rh + 6), "step %d  string %s  [%s]" % (
                self.tstep + 1, labels[self.trow].strip(), cell), TFT_YELLOW)
        else:
            d.text(V(4, y0 + tabs.n_rows(t) * rh + 6),
                   "x o X g f d @ #  Space=hit  +=row", TFT_YELLOW)
        self.end()

    def tab_set(self, token):
        tabs.set_cell(self.tab, self.tbar, self.tstep, self.trow, token)

    def key_tab(self, b):
        t = self.tab
        drums = t["inst"] == "drums"
        steps, rows = t["steps"], tabs.n_rows(t)
        if b == BUTTON_LEFT:
            self.tstep = (self.tstep - 1) % steps
        elif b == BUTTON_RIGHT:
            self.tstep = (self.tstep + 1) % steps
        elif b == BUTTON_UP:
            self.trow = (self.trow - 1) % rows
        elif b == BUTTON_DOWN:
            self.trow = (self.trow + 1) % rows
        elif b in (BUTTON_BACKSPACE, BUTTON_DELETE):
            self.tab_set("")
        elif b == BUTTON_N:
            if self.tbar == len(t["bars"]) - 1:
                tabs.add_bar(t)
            self.tbar += 1
        elif b == BUTTON_COMMA:
            self.tbar = max(0, self.tbar - 1)
        elif b == BUTTON_PERIOD:
            self.tbar = min(len(t["bars"]) - 1, self.tbar + 1)
        elif b == BUTTON_BACK:
            self.flush(True, "edited tab")
            self.back()
        elif drums:
            self.key_drum(b)
        elif b in DIGITS:
            cur = tabs.get_cell(t, self.tbar, self.tstep, self.trow)
            k = str(DIGITS[b])
            from time import ticks_ms
            now = ticks_ms()
            if cur.isdigit() and len(cur) == 1 and now - self.last_digit_at < 900 and int(cur + k) <= 24:
                k = cur + k
            self.last_digit_at = now
            self.tab_set(k)
        else:
            tech = {BUTTON_H: "h", BUTTON_P: "p", BUTTON_S: "/", BUTTON_L: "\\",
                    BUTTON_B: "b", BUTTON_R: "r", BUTTON_V: "~", BUTTON_X: "x"}.get(b)
            if tech:
                cur = tabs.get_cell(t, self.tbar, self.tstep, self.trow)
                self.tab_set("x" if tech == "x" else (cur + tech if cur else cur))
        self.last_digit_at = self.last_digit_at if b in DIGITS else -1

    def key_drum(self, b):
        t = self.tab
        name = t["rows"][self.trow]
        if b in (BUTTON_SPACE,) + SELECT:
            cur = tabs.get_cell(t, self.tbar, self.tstep, self.trow)
            self.tab_set("" if cur else ("x" if name in ("CC", "HH", "Rd", "Hf") else "o"))
            return
        ch = {BUTTON_X: "x", BUTTON_O: "o", BUTTON_G: "g", BUTTON_F: "f", BUTTON_D: "d",
              BUTTON_AT: "@", BUTTON_HASH: "#"}.get(b)
        if ch:
            self.tab_set(ch)
        elif b == BUTTON_PLUS or b == BUTTON_EQUAL:
            for r in tabs.DRUM_ROWS:
                if r not in t["rows"]:
                    tabs.add_drum_row(t, r)
                    break
        elif b == BUTTON_C:
            self.tab_set("X")

    # ================================================================ METRONOME
    def metro_tick(self):
        from time import ticks_ms, ticks_diff
        now = ticks_ms()
        if self.running and ticks_diff(now, self.beat_at) >= 60000 // self.bpm:
            self.beat_at = now
            self.beat = (self.beat + 1) % 4
            self.dirty = True
        elif self.running and ticks_diff(now, self.beat_at) > 90 and self.flashing:
            self.dirty = True
        self.flashing = self.running and ticks_diff(now, self.beat_at) < 90

    flashing = False

    def draw_metro(self):
        d = self.d
        self.begin("Metronome", "Space start/stop  L/R +-5  Up/Dn +-1  T tap")
        if self.running and self.flashing:
            col = TFT_RED if self.beat == 0 else TFT_GREEN
            d.fill_rectangle(V(0, self.lh + 4), V(self.W, self.H - 2 * self.lh - 10), col)
        d.text(V(self.W // 2 - 4 * self.cw, self.H // 2 - 10), "%3d BPM" % self.bpm, FG if not self.flashing else BG)
        d.text(V(self.W // 2 - 3 * self.cw, self.H // 2 + 10), "beat %d" % (self.beat + 1) if self.running else "stopped", DIM if not self.flashing else BG)
        self.end()

    def key_metro(self, b):
        if b == BUTTON_SPACE or b in SELECT:
            self.running = not self.running
            self.beat = 3
            from time import ticks_ms
            self.beat_at = ticks_ms() - 60000 // self.bpm
        elif b == BUTTON_LEFT:
            self.bpm = max(30, self.bpm - 5)
        elif b == BUTTON_RIGHT:
            self.bpm = min(260, self.bpm + 5)
        elif b == BUTTON_UP:
            self.bpm = min(260, self.bpm + 1)
        elif b == BUTTON_DOWN:
            self.bpm = max(30, self.bpm - 1)
        elif b == BUTTON_T:
            from time import ticks_ms, ticks_diff
            now = ticks_ms()
            if self.taps and ticks_diff(now, self.taps[-1]) > 2000:
                self.taps = []
            self.taps.append(now)
            self.taps = self.taps[-6:]
            if len(self.taps) >= 2:
                avg = ticks_diff(self.taps[-1], self.taps[0]) / (len(self.taps) - 1)
                self.bpm = max(30, min(260, int(60000 / avg)))
        elif b == BUTTON_BACK:
            self.running = False
            if self.song:
                self.song["tempo"] = self.bpm
                self.save_song()
            self.back()

    # ================================================================ CHORD HELPER
    def draw_chords(self):
        key = KEYS[self.ck]
        mode = "minor" if self.cminor else "major"
        ch = theory.diatonic(key, mode, self.sevenths)
        self.begin("Chords: %s %s" % (key, mode), "L/R key Up/Dn mode S 7ths +/- capo")
        y = self.lh + 10
        romans = theory.ROMAN
        for i, c in enumerate(ch):
            r = romans[i] if not self.cminor else romans[i].lower() if i in (0, 3, 4) else romans[i]
            self.d.text(V(8, y), "%s  %s" % (r.ljust(4), c), FG)
            y += self.lh
        y += 4
        for name, degs in theory.PROGRESSIONS[:4]:
            self.d.text(V(8, y), (name + ": " + " ".join(theory.progression(key, mode, degs, self.sevenths)))[: self.cols - 2], TFT_YELLOW)
            y += self.lh
        self.d.text(V(8, y + 4), "Capo %d -> play %s shapes" % (self.ccapo, theory.capo_shapes(key, self.ccapo)), HI)
        self.end()

    def key_chords(self, b):
        if b == BUTTON_LEFT:
            self.ck = (self.ck - 1) % len(KEYS)
        elif b == BUTTON_RIGHT:
            self.ck = (self.ck + 1) % len(KEYS)
        elif b in (BUTTON_UP, BUTTON_DOWN):
            self.cminor = not self.cminor
        elif b == BUTTON_S:
            self.sevenths = not self.sevenths
        elif b in (BUTTON_PLUS, BUTTON_EQUAL):
            self.ccapo = min(12, self.ccapo + 1)
        elif b == BUTTON_MINUS:
            self.ccapo = max(0, self.ccapo - 1)
        elif b == BUTTON_BACK:
            self.back()

    # ================================================================ HISTORY
    def rev_label(self, r):
        ts = r.get("ts", 0)
        if ts > 1700000000:
            from time import gmtime
            g = gmtime(ts)
            when = "%02d-%02d %02d:%02d" % (g[1], g[2], g[3], g[4])
        else:
            when = "no clock"
        return "#%d %s %s %dsec/%dtab" % (r["seq"], when, r.get("why", "")[:12], r.get("ns", 0), r.get("nt", 0))

    def draw_history(self):
        self.begin("History: " + self.song["title"][:20], "Enter restore  N save checkpoint  Back")
        if self.revs:
            self.list_view([self.rev_label(r) for r in self.revs])
        else:
            self.d.text(V(8, self.lh + 14), "No revisions yet", FG)
        self.end()

    def key_history(self, b):
        n = len(self.revs)
        if b == BUTTON_UP and n:
            self.sel = (self.sel - 1) % n
        elif b == BUTTON_DOWN and n:
            self.sel = (self.sel + 1) % n
        elif b == BUTTON_N:
            self.flush(True, "manual")
            self.revs = self.store.revisions(self.song["id"])
            self.sel = 0
            self.flash("Checkpoint saved")
        elif b in SELECT and n:
            seq = self.revs[self.sel]["seq"]
            self.ask_confirm("Restore #%d?" % seq, lambda: self.do_restore(seq))
        elif b == BUTTON_BACK:
            self.back()

    def do_restore(self, seq):
        tbs = self.store.load_tabs(self.song)
        got = self.store.restore(self.song, self.secs, tbs, seq, self.wall())
        if not got:
            self.flash("Revision missing")
            return
        self.song, self.secs = got[0], got[1]
        self.sec = self.tab = None
        self.edited = False
        self.revs = self.store.revisions(self.song["id"])
        self.sel = 0
        self.flash("Restored #%d (undo = newest)" % seq)

    # ================================================================ IDEAS
    def draw_ideas(self):
        self.begin("Ideas", "N new idea   Up/Dn scroll   Back")
        items = [i["text"] for i in self.store.list_ideas()]
        if items:
            self.list_view(items)
        else:
            self.d.text(V(8, self.lh + 14), "No ideas yet - press N", FG)
        self.end()

    def key_ideas(self, b):
        n = len(self.store.list_ideas())
        if b == BUTTON_UP and n:
            self.sel = (self.sel - 1) % n
        elif b == BUTTON_DOWN and n:
            self.sel = (self.sel + 1) % n
        elif b == BUTTON_N:
            def add(t):
                if t.strip():
                    from time import time, gmtime
                    g = gmtime(time())
                    self.store.add_idea(t.strip(), int(time()), "%04d-%02d" % (g[0], g[1]))
            self.ask("New idea", "", add, 120)
        elif b == BUTTON_BACK:
            self.back()
