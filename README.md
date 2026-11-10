# SongPad

Offline songwriting notebook for Picoware (PicoCalc): lyrics, chord charts, guitar/bass/drum tab,
metronome, idea log. Plain JSON on the SD card, ChordPro and TXT export. Autosave every ~3 s of
edits, plus a revision history (up to 20 snapshots per song, restore is undoable).

- `apps/SongPad.py` - Picoware entry point (copy to `/sd/picoware/apps/`)
- `apps/spad/` - helper modules (copy to `/sd/picoware/apps/spad/`)
- `tests/` - `python3 -I -m unittest discover -s tests`
- Simulator: `bash picoware/tools/run-micropython-desktop.sh --apps-source <repo>/apps --app SongPad`
