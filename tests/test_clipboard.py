"""Run outside Houdini: python -m unittest discover -s tests -v."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "python"))
from motioncops.clipboard import classify_paths, node_name, paths_from_mime


class ClipboardPathsTests(unittest.TestCase):
    def test_batch_deduplicates_without_collapsing_numbered_images(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [str(Path(directory) / ("image.%04d.PNG" % n)) for n in range(10)]
            for path in paths:
                Path(path).touch()
            valid, skipped, recognized = classify_paths(paths + paths[:2])
            self.assertTrue(recognized)
            self.assertEqual(valid, [p.replace("\\", "/") for p in paths])
            self.assertEqual(skipped, [])

    def test_mixed_missing_unsupported_directory_and_unicode(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / name for name in (
                "image with spaces.png", "\u56fe\u7247.mov", "notes.txt", "missing.exr")]
            for path in paths[:3]:
                path.touch()
            valid, skipped, recognized = classify_paths([str(p) for p in paths] + [directory])
            self.assertTrue(recognized)
            self.assertEqual(len(valid), 2)
            self.assertEqual(len(skipped), 3)

    def test_empty_clipboard_falls_through(self):
        self.assertEqual(classify_paths([]), ([], [], False))
        self.assertEqual(paths_from_mime(None), [])

    def test_native_urls_take_precedence_over_text(self):
        class Url:
            def __init__(self, path):
                self.path = path
            def isLocalFile(self):
                return bool(self.path)
            def toLocalFile(self):
                return self.path
        class Mime:
            def hasUrls(self):
                return True
            def urls(self):
                return [Url("C:/some image.png"), Url(None)]
            def hasText(self):
                raise AssertionError("File URLs should take precedence")
        self.assertEqual(paths_from_mime(Mime()), ["C:/some image.png"])

    def test_node_names(self):
        self.assertEqual(node_name("C:/image 001.png"), "read_image_001")
        self.assertEqual(node_name("/tmp/\u56fe\u7247.exr"), "read_media")
        self.assertEqual(node_name("/tmp/a`$F`.exr"), "read_a_F")


if __name__ == "__main__":
    unittest.main()
