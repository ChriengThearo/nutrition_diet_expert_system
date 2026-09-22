"""Focused tests for scanner input validation and local CLIP result mapping."""

import io
import unittest
from unittest.mock import patch

import torch
from PIL import Image
from werkzeug.datastructures import FileStorage

from app.services.local_food_scanner import LocalFoodScanner, ScannerError


def image_file(content_type="image/jpeg"):
    image = Image.new("RGB", (128, 128), "white")
    for x in range(0, 128, 16):
        for y in range(0, 128, 16):
            if (x // 16 + y // 16) % 2:
                for dx in range(16):
                    for dy in range(16):
                        image.putpixel((x + dx, y + dy), (18, 87, 42))
    data = io.BytesIO()
    image.save(data, format="JPEG")
    data.seek(0)
    return FileStorage(stream=data, filename="food.jpg", content_type=content_type)


class _Inputs(dict):
    def to(self, _device):
        return self


class _Processor:
    def __call__(self, **_kwargs):
        return _Inputs()


class _Model:
    def get_image_features(self, **_kwargs):
        return torch.tensor([[1.0, 0.0]])


class LocalFoodScannerTests(unittest.TestCase):
    def test_rejects_unsupported_type(self):
        with self.assertRaisesRegex(ScannerError, "JPEG, PNG, or WebP"):
            LocalFoodScanner._image(image_file("application/pdf"))

    def test_rejects_malformed_and_oversize_files(self):
        malformed = FileStorage(stream=io.BytesIO(b"not an image"), filename="bad.jpg", content_type="image/jpeg")
        oversized = FileStorage(stream=io.BytesIO(b"x" * (LocalFoodScanner.MAX_BYTES + 1)), filename="large.jpg", content_type="image/jpeg")
        with self.assertRaisesRegex(ScannerError, "valid food image"):
            LocalFoodScanner._image(malformed)
        with self.assertRaisesRegex(ScannerError, "8 MB or smaller"):
            LocalFoodScanner._image(oversized)

    def test_mocked_clip_result_maps_to_seeded_food(self):
        catalog = ((101, "Apple, raw"), (102, "Banana, raw"))
        with patch.object(LocalFoodScanner, "_catalog", return_value=catalog), patch.object(LocalFoodScanner, "_load"):
            old = (LocalFoodScanner._processor, LocalFoodScanner._model, LocalFoodScanner._text_features, LocalFoodScanner._device)
            try:
                LocalFoodScanner._processor = _Processor()
                LocalFoodScanner._model = _Model()
                LocalFoodScanner._text_features = torch.tensor([[1.0, 0.0], [0.0, 1.0]])
                LocalFoodScanner._device = "cpu"
                matches = LocalFoodScanner.scan(image_file(), "instance")
            finally:
                LocalFoodScanner._processor, LocalFoodScanner._model, LocalFoodScanner._text_features, LocalFoodScanner._device = old
        self.assertEqual([match["fdc_id"] for match in matches], [101, 102])
        self.assertEqual(matches[0]["recognized_as"], "Apple, raw")
        self.assertEqual(matches[0]["score"], 100.0)


if __name__ == "__main__":
    unittest.main()
