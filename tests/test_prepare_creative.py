import importlib.util
import sys
import tempfile
import unittest
import json
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import prepare_creative as pipeline

class CreativePreparationTest(unittest.TestCase):
    def test_two_links_create_pending_manifest_and_two_briefs(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(pipeline, "ROOT", Path(directory)):
            path = pipeline.prepare("https://www.mercadolivre.com.br/controle-remoto/up/MLBU123", "https://http2.mlstatic.com/product.webp")
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["product"]["creative_assets"]["status"], "pending")
            self.assertTrue((path.parent / "desktop-prompt.txt").is_file())
            self.assertTrue((path.parent / "mobile-prompt.txt").is_file())
            self.assertFalse(list(Path(directory).rglob("index.html")))
            with self.assertRaisesRegex(ValueError, "Artes pendentes"):
                pipeline.publish_manifest(path)

    def test_invalid_listing_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(pipeline, "ROOT", Path(directory)):
            with self.assertRaises(ValueError):
                pipeline.prepare("https://mercadolivre.com.br.evil.example/product", "https://example.com/photo.png")
            self.assertEqual(list(Path(directory).iterdir()), [])
