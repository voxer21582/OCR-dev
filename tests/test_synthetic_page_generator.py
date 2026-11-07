import runpy
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
GENERATOR = runpy.run_path(str(ROOT / "tools" / "generate_synthetic_ocr_pages.py"))


class SyntheticPageGeneratorTests(unittest.TestCase):
    def test_uses_embedded_sized_font_without_os_font_path(self):
        calls = []

        class FontStub:
            @staticmethod
            def load_default(*, size):
                calls.append(size)
                return "embedded-font"

            @staticmethod
            def truetype(*args, **kwargs):
                raise AssertionError("OS font paths are forbidden")

        self.assertEqual(GENERATOR["_load_synthetic_font"](FontStub), "embedded-font")
        self.assertEqual(calls, [44])

    def test_rejects_pillow_without_sized_default_font_api(self):
        class OldFontStub:
            @staticmethod
            def load_default():
                return "tiny-font"

        with self.assertRaisesRegex(RuntimeError, "Pillow 10.1 or newer"):
            GENERATOR["_load_synthetic_font"](OldFontStub)

    def test_seven_synthetic_cases_are_unique_and_bilingual(self):
        pages = GENERATOR["SYNTHETIC_PAGES"]
        self.assertEqual(len(pages), 7)
        self.assertEqual(len({case for case, _ in pages}), 7)
        all_text = " ".join(text for _, lines in pages for text in lines)
        self.assertIn("FATTURA", all_text)
        self.assertIn("HOTEL INVOICE", all_text)
        self.assertIn("RICEVUTA PARCHEGGIO", all_text)
        self.assertIn("PAYMENT APPROVED", all_text)

    def test_generation_refuses_to_overwrite_nonempty_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "pages"
            directory.mkdir()
            sentinel = directory / "keep.txt"
            sentinel.write_text("synthetic sentinel", encoding="utf-8")
            with self.assertRaisesRegex(FileExistsError, "must be empty"):
                GENERATOR["generate_pages"](directory)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "synthetic sentinel")

    def test_generated_pages_are_repeatable_with_portable_font(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is installed only in the temporary Windows runner")

        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = GENERATOR["generate_pages"](Path(first_dir))
            second = GENERATOR["generate_pages"](Path(second_dir))
            self.assertEqual(tuple(path.stem for path in first), tuple(path.stem for path in second))
            self.assertEqual([p.read_bytes() for p in first], [p.read_bytes() for p in second])
            with Image.open(first[0]) as page:
                self.assertEqual(page.size, (1275, 1650))


if __name__ == "__main__":
    unittest.main()
