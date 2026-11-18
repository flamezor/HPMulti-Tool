"""Object list of the measurement series: free text input and own templates."""

import json
import os
import tempfile
import unittest
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="hpmulti-test-")
os.environ["XDG_DATA_HOME"] = _TMP
os.environ["APPDATA"] = _TMP
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox  # noqa: E402

from hpmultitool import i18n  # noqa: E402
from hpmultitool.series import LOOP_TEMPLATES, TemplateStore, parse_objects  # noqa: E402


class TemplateStoreTests(unittest.TestCase):
    def setUp(self):
        i18n.set_language("en")

    def test_parse_objects(self):
        self.assertEqual(parse_objects(" red \n\nyellow\n  \nblack, white\n"),
                         ["red", "yellow", "black, white"])

    def test_own_template_saved_replaced_and_deleted(self):
        store = TemplateStore()
        store.save("My cable", ["a", "b"])
        store.save("my cable", ["c"])                      # same name, other case: replaced
        self.assertEqual(store.find("MY CABLE").objects, ["c"])
        self.assertEqual(len(store.templates()), len(LOOP_TEMPLATES) + 1)
        store.delete("My cable")
        self.assertIsNone(store.find("My cable"))

    def test_built_in_template_overridden_hidden_and_restored(self):
        store = TemplateStore()
        store.save("Numbered 1 … 8", ["x", "y"])           # own version replaces the built-in
        names = [t.name for t in store.templates()]
        self.assertEqual(names.count("Numbered 1 … 8"), 1)
        self.assertEqual(store.find("Numbered 1 … 8").objects, ["x", "y"])
        store.delete("Numbered 1 … 8")                     # deleting it brings the built-in back
        self.assertEqual(store.find("Numbered 1 … 8").objects[0], "1")
        store.delete("Numbered 1 … 8")                     # deleting the built-in hides it
        self.assertIsNone(store.find("Numbered 1 … 8"))
        store.restore()
        self.assertIsNotNone(store.find("Numbered 1 … 8"))

    def test_round_trip_and_bad_data(self):
        store = TemplateStore()
        store.save("Own", ["1", "2"])
        store.delete("Sensor cable, 6 cores")
        again = TemplateStore.from_dict(json.loads(json.dumps(store.to_dict())))
        self.assertEqual(again.find("Own").objects, ["1", "2"])
        self.assertIsNone(again.find("Sensor cable, 6 cores"))
        broken = TemplateStore.from_dict({"custom": [["", []], "x", [1, 2, 3]], "hidden": [5]})
        self.assertEqual(len(broken.templates()), len(LOOP_TEMPLATES))
        self.assertEqual(len(TemplateStore.from_dict(None).templates()), len(LOOP_TEMPLATES))


class PlanCardTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        i18n.set_language("en")
        cls.ini = str(Path(_TMP) / "templates.ini")
        cls.originals = (QInputDialog.getText, QMessageBox.question, QMessageBox.information)
        QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
        QMessageBox.information = staticmethod(lambda *a, **k: 0)

    @classmethod
    def tearDownClass(cls):
        QInputDialog.getText, QMessageBox.question, QMessageBox.information = (
            staticmethod(cls.originals[0]), staticmethod(cls.originals[1]),
            staticmethod(cls.originals[2]))

    def card(self):
        from hpmultitool.gui.plan_card import PlanCard
        return PlanCard(QSettings(self.ini, QSettings.IniFormat))

    def test_type_objects_and_keep_own_template(self):
        card = self.card()
        card.set_objects([])
        card.object_text.setFocus()
        QTest.keyClicks(card.object_text, "red")
        QTest.keyClick(card.object_text, Qt.Key_Return)
        QTest.keyClicks(card.object_text, "blue")
        self.assertEqual(card.objects(), ["red", "blue"])

        QInputDialog.getText = staticmethod(lambda *a, **k: ("Probe A", True))
        card._save_template()
        self.assertEqual(card.template.currentData(), "Probe A")
        self.assertTrue(card.delete_template_button.isEnabled())

        # A new card (= next program start) offers the saved template.
        card2 = self.card()
        card2.set_objects([])
        card2.template.select_data("Probe A")
        self.assertEqual(card2.objects(), ["red", "blue"])

        # Edit: change the list and save under the same name.
        card2.set_objects(["red", "blue", "green"])
        QInputDialog.getText = staticmethod(lambda *a, **k: (k.get("text", ""), True))
        card2._save_template()
        card3 = self.card()
        card3.template.select_data("Probe A")
        self.assertEqual(card3.objects(), ["red", "blue", "green"])

        card3._delete_template()
        self.assertIsNone(card3.template.currentData())
        self.assertEqual(card3.objects(), ["red", "blue", "green"])   # list is kept
        self.assertIsNone(self.card().templates.find("Probe A"))

    def test_empty_list_is_not_saved(self):
        card = self.card()
        card.set_objects([])
        QInputDialog.getText = staticmethod(lambda *a, **k: ("Empty", True))
        card._save_template()
        self.assertIsNone(card.templates.find("Empty"))

    def test_deleted_standard_template_can_be_restored(self):
        card = self.card()
        card.template.select_data("4 cores (DIN 47100)")
        self.assertEqual(card.objects(), ["white", "brown", "green", "yellow"])
        self.assertTrue(card.restore_templates_button.isHidden())
        card._delete_template()
        self.assertIsNone(card.templates.find("4 cores (DIN 47100)"))
        self.assertFalse(card.restore_templates_button.isHidden())
        card._restore_templates()
        self.assertIsNotNone(card.templates.find("4 cores (DIN 47100)"))
        self.assertTrue(card.restore_templates_button.isHidden())

    def test_own_list_per_instrument(self):
        card = self.card()
        card.set_devices([])
        card.set_objects(["1", "2"])                       # default list
        card.set_devices(["T034", "T049"])
        self.assertFalse(card.list_for_row.isHidden())
        self.assertEqual(card.list_for.currentData(), "T034")
        card.set_objects(["red", "yellow", "black"])
        card.list_for.select_data("T049")
        self.assertEqual(card.objects(), ["1", "2"])       # still the default list
        card.template.select_data("4 cores (DIN 47100)")
        self.assertEqual(card.object_lists(),
                         {"T034": ["red", "yellow", "black"],
                          "T049": ["white", "brown", "green", "yellow"]})
        card.mode.select_data("loop")
        card.update_info([])
        self.assertIn("T034: 3, T049: 4 → 4 steps", card.info.text())

        # Stored and restored, also in a test profile.
        card.store(card._settings)
        again = self.card()
        again.set_devices(["T034", "T049"])
        self.assertEqual(again.object_lists(), card.object_lists())
        profile = card.profile_data()
        again.apply_profile({"objects": ["a", "b"]})       # old profile: one shared list
        self.assertEqual(again.object_lists(), {"T034": ["a", "b"], "T049": ["a", "b"]})
        again.apply_profile(profile)
        self.assertEqual(again.object_lists(), card.object_lists())

        card.set_devices(["T034"])                         # one instrument: no choice shown
        self.assertTrue(card.list_for_row.isHidden())
        self.assertEqual(card.objects(), ["red", "yellow", "black"])


if __name__ == "__main__":
    unittest.main()
