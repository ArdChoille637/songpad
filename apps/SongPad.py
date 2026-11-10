# picoware/apps/SongPad.py - offline songwriting notebook (thin entry point).
# Helper modules live in picoware/apps/spad/.
_app = None


def start(view_manager) -> bool:
    global _app
    try:
        from spad.app import App
        _app = App(view_manager)
        _app.draw_home()
        return True
    except Exception as e:
        print("[SongPad] start failed:", type(e).__name__, e)
        _app = None
        return False


def run(view_manager) -> None:
    if _app is None:
        view_manager.back()
        return
    _app.tick()


def stop(view_manager) -> None:
    global _app
    from gc import collect
    try:
        if _app is not None:
            _app.flush(True, "closed app")
    except Exception:
        pass
    _app = None
    collect()
