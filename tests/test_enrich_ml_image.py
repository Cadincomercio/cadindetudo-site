from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPOSITORY_ROOT / "scripts" / "enrich_ml_image.py"
SPEC = importlib.util.spec_from_file_location("enrich_ml_image", SCRIPT)
resolver = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(resolver)

PUBLISH_SCRIPT = REPOSITORY_ROOT / "scripts" / "publish_gpt_job.py"
PUBLISH_SPEC = importlib.util.spec_from_file_location("publish_gpt_job", PUBLISH_SCRIPT)
publisher = importlib.util.module_from_spec(PUBLISH_SPEC)
assert PUBLISH_SPEC.loader is not None
PUBLISH_SPEC.loader.exec_module(publisher)

ITEM_ID = "MLB7273066334"
IMAGE = (
    "https://http2.mlstatic.com/"
    "D_Q_NP_2X_810823-MLB113931028108_072026-E--adubo.webp"
)


def _job() -> dict:
    return {
        "version": 1,
        "publish": False,
        "product": {
            "source_url": "https://www.mercadolivre.com.br/produto/up/MLBU4457612445",
            "title": "Adubo Fertilizante Npk 04-14-08 1 Kg Plantio Flores E Frutos",
            "item_id": ITEM_ID,
            "main_image_url": "",
            "gallery_images": [],
        },
        "research": {},
        "pages": [],
    }


class PersistentImageCacheTest(unittest.TestCase):
    def test_publish_false_validates_without_writing_pages(self) -> None:
        fixture = REPOSITORY_ROOT / "jobs" / "processed" / "teste-imagem-listagem-npk-3.json"
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory)
            with mock.patch.object(publisher, "ROOT", temporary_root):
                self.assertEqual(publisher.publish(fixture), [])
            self.assertEqual(list(temporary_root.iterdir()), [])

    def test_second_run_uses_cache_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache_path = root / "data" / "ml_images_cache.json"
            job_path = root / "job.json"
            job_path.write_text(json.dumps(_job()), encoding="utf-8")

            with (
                mock.patch.object(resolver, "images_from_items_api", return_value=[]),
                mock.patch.object(resolver, "images_from_public_product_ids", return_value=[]),
                mock.patch.object(resolver, "images_from_public_search", return_value=[]),
                mock.patch.object(resolver, "images_from_listing_search", return_value=[IMAGE]),
                mock.patch.object(resolver, "images_from_product_page", return_value=[]),
            ):
                self.assertTrue(resolver.enrich(job_path, cache_path))

            cached = json.loads(cache_path.read_text(encoding="utf-8"))[ITEM_ID]
            self.assertEqual(cached["source"], "listing")
            self.assertEqual(cached["mlbu"], "MLBU4457612445")
            self.assertEqual(cached["gallery_images"], [IMAGE])

            job_path.write_text(json.dumps(_job()), encoding="utf-8")
            with (
                mock.patch.object(resolver, "images_from_items_api", side_effect=AssertionError("network")),
                mock.patch.object(resolver, "images_from_public_product_ids", side_effect=AssertionError("network")),
                mock.patch.object(resolver, "images_from_public_search", side_effect=AssertionError("network")),
                mock.patch.object(resolver, "images_from_listing_search", side_effect=AssertionError("listing failed")),
                mock.patch.object(resolver, "images_from_product_page", side_effect=AssertionError("network")),
            ):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertTrue(resolver.enrich(job_path, cache_path))

            self.assertIn(f"Cache hit para {ITEM_ID}", output.getvalue())
            product = json.loads(job_path.read_text(encoding="utf-8"))["product"]
            self.assertEqual(product["main_image_url"], IMAGE)

    def test_job_image_is_cached_before_any_network_attempt(self) -> None:
        job = _job()
        job["product"].pop("item_id")
        job["product"]["source_url"] += "?wid=MLB7273066334"
        job["product"]["main_image_url"] = IMAGE
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache_path = root / "cache.json"
            job_path = root / "job.json"
            job_path.write_text(json.dumps(job), encoding="utf-8")
            with (
                mock.patch.object(resolver, "images_from_items_api", side_effect=AssertionError("network")),
                mock.patch.object(resolver, "images_from_public_product_ids", side_effect=AssertionError("network")),
                mock.patch.object(resolver, "images_from_public_search", side_effect=AssertionError("network")),
                mock.patch.object(resolver, "images_from_listing_search", side_effect=AssertionError("network")),
                mock.patch.object(resolver, "images_from_product_page", side_effect=AssertionError("network")),
            ):
                resolver.enrich(job_path, cache_path)
            cached = json.loads(cache_path.read_text(encoding="utf-8"))[ITEM_ID]
            self.assertEqual(cached["source"], "job")

    def test_supplied_gallery_order_wins_over_cache(self) -> None:
        job = _job()
        supplied = [IMAGE.replace("810823", str(value)) for value in ("111111", "222222", "333333")]
        job["product"]["main_image_url"] = IMAGE
        job["product"]["gallery_images"] = supplied
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache_path = root / "cache.json"
            cache_path.write_text(json.dumps({ITEM_ID: {"main_image_url": IMAGE, "gallery_images": [IMAGE]}}), encoding="utf-8")
            job_path = root / "job.json"
            job_path.write_text(json.dumps(job), encoding="utf-8")
            with mock.patch.object(resolver, "images_from_items_api", side_effect=AssertionError("network")):
                resolver.enrich(job_path, cache_path)
            product = json.loads(job_path.read_text(encoding="utf-8"))["product"]
            self.assertEqual(product["main_image_url"], supplied[0])
            self.assertEqual(product["gallery_images"], supplied)

    def test_smaller_resolution_does_not_replace_larger_gallery(self) -> None:
        images = [
            f"https://http2.mlstatic.com/D_NQ_NP_10{i}-MLB12345678901_012026-O.webp"
            for i in range(3)
        ]
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "cache.json"
            cache = {}
            product = _job()["product"]
            resolver._save_cache(cache, product, images, "listing", cache_path)
            resolver._save_cache(cache, product, images[:1], "items_api", cache_path)
            saved = json.loads(cache_path.read_text(encoding="utf-8"))[ITEM_ID]
            self.assertEqual(saved["gallery_images"], images)


class PublisherStructureTest(unittest.TestCase):
    @staticmethod
    def _valid_job_with_pages(total: int) -> dict:
        fixture = REPOSITORY_ROOT / "jobs" / "processed" / "teste-imagem-listagem-npk-3.json"
        job = publisher.normalize(json.loads(fixture.read_text(encoding="utf-8")))
        original = job["pages"][0]
        job["pages"] = []
        for index in range(total):
            page = copy.deepcopy(original)
            page["slug"] = f"pagina-{index + 1}"
            job["pages"].append(page)
        return job

    def test_accepts_twenty_pages_and_rejects_twenty_one(self) -> None:
        publisher.validate(self._valid_job_with_pages(20))
        with self.assertRaisesRegex(ValueError, "Máximo de 20 páginas"):
            publisher.validate(self._valid_job_with_pages(21))

    def test_short_template_uses_gallery_in_supplied_order(self) -> None:
        template = (REPOSITORY_ROOT / "templates" / "landing.html").read_text(encoding="utf-8")
        job = self._valid_job_with_pages(1)
        product = job["product"]
        product["main_image_url"] = IMAGE
        product["gallery_images"] = [IMAGE, IMAGE.replace("810823", "999999")]
        job["pages"][0]["benefit_cards"] = ["Um", "Dois", "Três", "Quatro", "Cinco"]
        rendered = publisher.render(template, product, job["pages"][0])
        second = IMAGE.replace("810823", "999999")
        self.assertIn('class="product-card"', rendered)
        self.assertIn(f'data-gallery-main fetchpriority="high" src="{IMAGE}"', rendered)
        self.assertIn(f'class="context-background" src="{second}"', rendered)
        self.assertLess(rendered.index(f'data-src="{IMAGE}"'), rendered.index(f'data-src="{second}"'))
        self.assertEqual(rendered.count('<button class="thumb"'), 2)
        self.assertEqual(rendered.count('<li>'), 3)
        self.assertEqual(rendered.count('data-cadin-cta="mercado-livre"'), 2)
        self.assertNotIn("{{GALLERY_HTML}}", rendered)
        self.assertNotIn("Dúvidas frequentes", rendered)

    def test_gallery_does_not_prepend_a_different_main_when_job_supplies_images(self) -> None:
        template = (REPOSITORY_ROOT / "templates" / "landing.html").read_text(encoding="utf-8")
        job = self._valid_job_with_pages(1)
        product = job["product"]
        supplied = [IMAGE.replace("810823", str(value)) for value in ("111111", "222222", "333333")]
        product["main_image_url"] = IMAGE
        product["gallery_images"] = supplied
        rendered = publisher.render(template, product, job["pages"][0])
        self.assertIn(f'data-gallery-main fetchpriority="high" src="{supplied[0]}"', rendered)
        self.assertNotIn(IMAGE, rendered)

    def test_single_image_has_no_redundant_thumbnail(self) -> None:
        template = (REPOSITORY_ROOT / "templates" / "landing.html").read_text(encoding="utf-8")
        job = self._valid_job_with_pages(1)
        job["product"]["main_image_url"] = IMAGE
        job["product"]["gallery_images"] = [IMAGE]
        job["pages"][0]["context_image_url"] = ""
        rendered = publisher.render(template, job["product"], job["pages"][0])
        self.assertIn(f'data-gallery-main fetchpriority="high" src="{IMAGE}"', rendered)
        self.assertNotIn('<button class="thumb"', rendered)
        self.assertNotIn('<img class="context-background"', rendered)


if __name__ == "__main__":
    unittest.main()
