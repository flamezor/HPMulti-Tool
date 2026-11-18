"""Every text marked with tr()/N_() must have a German translation with the same placeholders."""

import ast
import re
import unittest
from pathlib import Path

from hpmultitool.i18n_de import DE

PACKAGE = Path(__file__).resolve().parent.parent / "hpmultitool"
PLACEHOLDER = re.compile(r"\{[^{}]*\}")


def marked_texts():
    texts = {}
    for path in sorted(PACKAGE.rglob("*.py")):
        if path.name.startswith("i18n"):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in ("tr", "N_") and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                texts.setdefault(node.args[0].value, f"{path.name}:{node.lineno}")
    return texts


class TranslationTests(unittest.TestCase):
    def test_all_texts_translated(self):
        missing = {text: where for text, where in marked_texts().items() if text not in DE}
        self.assertEqual(missing, {}, "Missing German translations")

    def test_placeholders_match(self):
        wrong = [en for en, de in DE.items()
                 if sorted(PLACEHOLDER.findall(en)) != sorted(PLACEHOLDER.findall(de))]
        self.assertEqual(wrong, [])

    def test_placeholder_named_text(self):
        # "text" is also the name of tr()'s first parameter: must not collide
        from hpmultitool.i18n import tr
        self.assertEqual(tr("{text!r} shown", text="test1"), "'test1' shown")

    def test_no_unused_entries(self):
        unused = sorted(set(DE) - set(marked_texts()))
        self.assertEqual(unused, [], "Unused catalogue entries")


if __name__ == "__main__":
    unittest.main()
