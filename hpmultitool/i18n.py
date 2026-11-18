"""Minimal translation layer.

Source texts in the code are English. ``tr("Text {x}", x=1)`` translates
into the active language and formats. ``N_("Text")`` only marks a text for
translation where it is stored in data tables; such texts are translated
with ``tr(text)`` when shown. Catalogues: ``i18n_de.py`` (German).
``tests/test_i18n.py`` checks that every marked text has a translation.

Adding a language: create ``i18n_<code>.py`` with a dict named like the
upper-case code (e.g. ``FR``), and add it to ``LANGUAGES`` below.
"""

from __future__ import annotations

import importlib
import locale
import os

LANGUAGES = {"en": "English", "de": "Deutsch"}
_language = "en"
_catalogue: dict[str, str] = {}


def system_language() -> str:
    """Language of the operating system if supported, otherwise English."""
    candidates = [os.environ.get(name, "") for name in ("LANGUAGE", "LC_ALL", "LC_MESSAGES",
                                                         "LANG")]
    try:
        candidates.append(locale.getlocale()[0] or "")
    except ValueError:
        pass
    for value in candidates:
        code = value.split(":")[0][:2].lower()
        if code in LANGUAGES:
            return code
    return "en"


def set_language(code: str | None) -> None:
    global _language, _catalogue
    _language = code if code in LANGUAGES else system_language()
    if _language == "en":
        _catalogue = {}
    else:
        module = importlib.import_module(f"{__package__}.i18n_{_language}")
        _catalogue = getattr(module, _language.upper())


def language() -> str:
    return _language


def tr(text: str, /, **values) -> str:
    text = _catalogue.get(text, text)
    return text.format(**values) if values else text


def N_(text: str) -> str:  # noqa: N802 - gettext convention
    return text


def decimal_sep() -> str:
    return "," if _language == "de" else "."


def localize_number(text: str) -> str:
    """Use the language's decimal separator in an already formatted number."""
    return text.replace(".", ",") if _language == "de" else text
