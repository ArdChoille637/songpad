import os, sys, shutil, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps"))
from spad import theory, sylls, tabs, fmt
from spad.store import Store


class FakeStorage:
    """Minimal Storage stand-in rooted in a temp dir."""
    def __init__(self, root): self.r = root
    def p(self, path): return self.r + path
    def exists(self, path): return os.path.exists(self.p(path))
    def mkdir(self, path): os.mkdir(self.p(path)); return True
    def read(self, path):
        with open(self.p(path)) as f: return f.read()
    def write(self, path, data, mode="w"):
        with open(self.p(path), mode) as f: f.write(data)
        return True
    def listdir(self, path): return os.listdir(self.p(path)) if self.exists(path) else []
    def remove(self, path): os.remove(self.p(path)); return True
    def rmdir(self, path): os.rmdir(self.p(path)); return True


class Theory(unittest.TestCase):
    def test_diatonic(self):
        self.assertEqual(theory.diatonic("G"), ["G", "Am", "Bm", "C", "D", "Em", "F#dim"])
        self.assertEqual(theory.diatonic("F"), ["F", "Gm", "Am", "Bb", "C", "Dm", "Edim"])
        self.assertEqual(theory.diatonic("A", "minor"), ["Am", "Bdim", "C", "Dm", "Em", "F", "G"])
        self.assertEqual(theory.diatonic("C", sevenths=True)[4], "G7")

    def test_transpose(self):
        self.assertEqual(theory.transpose_chord("G", 2), "A")
        self.assertEqual(theory.transpose_chord("F#m7/C#", 1), "Gm7/D")
        self.assertEqual(theory.transpose_chord("Bb", 2, True), "C")
        self.assertEqual(theory.transpose_chord("C", -1), "B")

    def test_capo(self):
        self.assertEqual(theory.capo_shapes("A", 2), "G")
        self.assertEqual(theory.capo_shapes("Bb", 3), "G")
        self.assertEqual(theory.capo_shapes("Em", 0), "Em")

    def test_prog(self):
        self.assertEqual(theory.progression("G", "major", (0, 4, 5, 3)), ["G", "D", "Em", "C"])


class Sylls(unittest.TestCase):
    def test_words(self):
        for w, n in (("take", 1), ("northbound", 2), ("tonight", 2), ("beautiful", 3),
                     ("little", 2), ("the", 1), ("light", 1), ("porch", 1), ("walked", 1)):
            self.assertEqual(sylls.word_syllables(w), n, w)

    def test_line(self):
        self.assertEqual(sylls.line_syllables("Take the northbound line tonight"), 7)


class Tabs(unittest.TestCase):
    def test_guitar_ascii(self):
        t = tabs.new_tab("guitar", 1)
        tabs.set_cell(t, 0, 0, 5, "3")
        tabs.set_cell(t, 0, 2, 5, "5h7")
        self.assertEqual(tabs.get_cell(t, 0, 2, 5), "5h7")
        txt = tabs.to_ascii(t, 80).split("\n")
        self.assertEqual(len(txt), 6)
        self.assertTrue(txt[5].startswith("E |3-"))
        self.assertIn("5h7", txt[5])
        self.assertTrue(all(len(l) == len(txt[0]) for l in txt))
        tabs.set_cell(t, 0, 2, 5, "")
        self.assertEqual(tabs.get_cell(t, 0, 2, 5), "")

    def test_drums(self):
        t = tabs.new_tab("drums", 2)
        tabs.set_cell(t, 0, 4, 1, "o")
        tabs.set_cell(t, 0, 0, 2, "o")
        out = tabs.to_ascii(t, 80)
        self.assertIn("SD|----o-----------|", out)
        self.assertIn("BD|o---------------|", out)
        self.assertIn("legend" if False else "x=cymbal", out)
        self.assertEqual(out.count("HH|"), 1)  # two bars on one line
        tabs.add_drum_row(t, "CC")
        self.assertEqual(t["rows"][0], "CC")


class Chart(unittest.TestCase):
    def test_chord_row_and_inline(self):
        ln = {"t": "Take the northbound line tonight", "c": [[0, "G"], [9, "D"], [20, "Em"]]}
        row = fmt.chord_row(ln)
        self.assertEqual(row[0], "G")
        self.assertEqual(row[9], "D")
        self.assertEqual(row[20:22], "Em")
        self.assertEqual(fmt.inline_line(ln), "[G]Take the [D]northbound [Em]line tonight")
        self.assertEqual(fmt.chord_row(ln, 2).split()[0], "A")


class StoreRoundTrip(unittest.TestCase):
    def setUp(self): self.d = tempfile.mkdtemp(); self.s = Store(FakeStorage(self.d))
    def tearDown(self): shutil.rmtree(self.d)

    def test_full_song(self):
        st = self.s
        song = st.new_song("Northbound", "G")
        sec = st.new_section(song, "chorus")
        sec["lines"] = [{"t": "Take the northbound line", "c": [[0, "G"], [9, "D"]]}]
        st.save_section(song["id"], sec)
        tab = st.new_tab(song, tabs.new_tab("guitar"))
        tabs.set_cell(tab, 0, 0, 5, "3")
        st.save_tab(song["id"], tab)
        st.save_song(song)
        self.assertEqual([e["t"] for e in st.index()], ["Northbound"])
        loaded = st.load_song(song["id"])
        secs, tbs = st.load_sections(loaded), st.load_tabs(loaded)
        cho = fmt.to_chordpro(loaded, secs, tbs)
        self.assertIn("{title: Northbound}", cho)
        self.assertIn("{start_of_chorus: Chorus}", cho)
        self.assertIn("[G]Take the [D]northbound line", cho)
        self.assertIn("{start_of_tab: Guitar}", cho)
        txt = fmt.to_text(loaded, secs, tbs)
        self.assertIn("[Chorus]", txt)
        st.delete_song(song["id"])
        self.assertEqual(st.index(), [])

    def _song(self):
        st = self.s
        song = st.new_song("Rev", "C")
        sec = st.new_section(song, "verse")
        sec["lines"] = [{"t": "one", "c": []}]
        st.save_section(song["id"], sec)
        st.save_song(song)
        return song, {sec["id"]: sec}, sec

    def test_revisions_dedupe_prune_restore(self):
        st = self.s
        song, secs, sec = self._song()
        self.assertEqual(st.snapshot(song, secs, {}, 100, "a"), 1)
        self.assertEqual(st.snapshot(song, secs, {}, 101, "same"), 0)  # unchanged -> no new revision
        sec["lines"][0]["t"] = "two"
        st.save_section(song["id"], sec)
        self.assertEqual(st.snapshot(song, secs, {}, 200, "b"), 2)
        self.assertEqual([r["seq"] for r in st.revisions(song["id"])], [2, 1])
        sec["lines"][0]["t"] = "unsaved"  # live edit not yet snapshotted
        song2, secs2, _ = st.restore(song, secs, {}, 1, 300)
        self.assertEqual(list(secs2.values())[0]["lines"][0]["t"], "one")
        on_disk = st.load_section(song["id"], sec["id"])
        self.assertEqual(on_disk["lines"][0]["t"], "one")
        revs = st.revisions(song["id"])
        self.assertEqual(revs[0]["why"], "before restore")  # restore is itself undoable
        undo = st.restore(song2, secs2, {}, revs[0]["seq"], 400)  # undo the restore
        self.assertEqual(list(undo[1].values())[0]["lines"][0]["t"], "unsaved")

    def test_revision_cap(self):
        st = self.s
        song, secs, sec = self._song()
        for i in range(st.MAX_REV + 5):
            sec["lines"][0]["t"] = "v%d" % i
            st.snapshot(song, secs, {}, i, "x")
        revs = st.revisions(song["id"])
        self.assertEqual(len(revs), st.MAX_REV)
        self.assertEqual(revs[0]["seq"], st.MAX_REV + 5)
        files = [f for f in os.listdir(self.d + "/picoware/songpad/songs/%s/history" % song["id"]) if f != "index.json"]
        self.assertEqual(len(files), st.MAX_REV)

    def test_write_skips_identical(self):
        st = self.s
        st.write_json("/picoware/songpad/x.json", {"a": 1})
        p = self.d + "/picoware/songpad/x.json"
        os.remove(p)
        st.write_json("/picoware/songpad/x.json", {"a": 1})  # identical: not rewritten
        self.assertFalse(os.path.exists(p))
        st.write_json("/picoware/songpad/x.json", {"a": 2})
        self.assertTrue(os.path.exists(p))

    def test_delete_song_removes_history(self):
        st = self.s
        song, secs, _ = self._song()
        st.snapshot(song, secs, {}, 1, "a")
        st.delete_song(song["id"])
        self.assertFalse(os.path.exists(self.d + "/picoware/songpad/songs/" + song["id"]))

    def test_ideas(self):
        self.s.add_idea("hook: porch light", 1, "2026-11")
        self.s.add_idea("second", 2, "2026-12")
        self.assertEqual([i["text"] for i in self.s.list_ideas()], ["second", "hook: porch light"])


if __name__ == "__main__":
    unittest.main()
