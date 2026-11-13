"""Start HPMulti-Tool:  python -m hpmultitool [--simulate] [--lang de|en]"""

from __future__ import annotations

import argparse
import sys


def main(argv=None) -> int:
    from .i18n import LANGUAGES

    parser = argparse.ArgumentParser(prog="hpmultitool",
                                     description="Data acquisition for HP 34401A multimeters")
    parser.add_argument("--simulate", action="store_true",
                        help="use two simulated multimeters instead of real hardware")
    parser.add_argument("--lang", choices=sorted(LANGUAGES),
                        help="user interface language (default: last used, else system language)")
    args = parser.parse_args(argv)

    from PySide6.QtCore import QLibraryInfo, QSettings, QTranslator
    from PySide6.QtWidgets import QApplication

    from . import APP_NAME
    from .i18n import language, set_language

    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setDesktopFileName("hpmultitool")
    app.setStyle("Fusion")
    from .gui.widgets import WheelGuard
    app.installEventFilter(WheelGuard(app))  # mouse wheel scrolls, never changes values
    settings = QSettings(APP_NAME, APP_NAME)
    set_language(args.lang or settings.value("ui/language") or None)

    state = {"translator": None, "window": None}

    def install_qt_translation():
        """Translate Qt's own texts (Yes/No, Close, file dialogs)."""
        if state["translator"] is not None:
            app.removeTranslator(state["translator"])
            state["translator"] = None
        if language() != "en":
            translator = QTranslator(app)
            path = QLibraryInfo.path(QLibraryInfo.TranslationsPath)
            if translator.load(f"qtbase_{language()}", path):
                app.installTranslator(translator)
                state["translator"] = translator

    from .gui.main_window import MainWindow

    def open_window(devices=None):
        window = MainWindow(simulate=args.simulate, devices=devices)
        window.language_change_requested.connect(switch_language)
        window.show()
        state["window"] = window

    def switch_language(code):
        old = state["window"]
        if not old.shutdown():
            return
        set_language(code)
        install_qt_translation()
        open_window(list(old.devices))
        old.hide()
        old.deleteLater()

    install_qt_translation()
    open_window()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
