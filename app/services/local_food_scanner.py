"""Local, in-memory CLIP matching for seeded USDA foods."""

import io
import hashlib
import os
import threading
from pathlib import Path

from PIL import Image, ImageFilter, UnidentifiedImageError
from sqlalchemy import text

from extensions import db


class ScannerError(RuntimeError):
    def __init__(self, message, status=422):
        super().__init__(message)
        self.status = status


class LocalFoodScanner:
    MAX_BYTES = 8 * 1024 * 1024
    ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
    _lock = threading.Lock()
    _preparation_lock = threading.Lock()
    _model = _processor = _text_features = _device = None
    _food_ids = ()
    _preparing = False
    _preparation_error = None

    @classmethod
    def _image(cls, file_storage):
        if file_storage is None:
            raise ScannerError("Choose an image before scanning.", 400)
        if file_storage.mimetype not in cls.ALLOWED_TYPES:
            raise ScannerError("Use a JPEG, PNG, or WebP image.", 415)
        data = file_storage.stream.read(cls.MAX_BYTES + 1)
        if not data:
            raise ScannerError("Choose an image before scanning.", 400)
        if len(data) > cls.MAX_BYTES:
            raise ScannerError("The image must be 8 MB or smaller.", 413)
        try:
            with Image.open(io.BytesIO(data)) as check:
                check.verify()
            with Image.open(io.BytesIO(data)) as image:
                image = image.convert("RGB")
                if min(image.size) < 96:
                    raise ScannerError("The image is too small to identify food.")
                image.thumbnail((1600, 1600))
                edges = list(image.convert("L").resize((128, 128)).filter(ImageFilter.FIND_EDGES).getdata())
                if sum(edges) / len(edges) < 7:
                    raise ScannerError("The image is too blurry or plain. Take a clearer photo of one food.")
                return image.copy()
        except ScannerError:
            raise
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ScannerError("The uploaded file is not a valid food image.") from exc

    @classmethod
    def _catalog(cls):
        with db.engine.connect() as connection:
            rows = connection.execute(text("SELECT fdc_id, name FROM usda_market_foods ORDER BY fdc_id")).mappings().all()
        if not rows:
            raise ScannerError("The local USDA market has not been seeded yet.", 503)
        return tuple((int(row["fdc_id"]), row["name"]) for row in rows)

    @classmethod
    def _load(cls, catalog, instance_path):
        food_ids = tuple(item[0] for item in catalog)
        catalog_signature = hashlib.sha256("\n".join(f"{fdc_id}:{name}" for fdc_id, name in catalog).encode("utf-8")).hexdigest()
        if cls._model is not None and cls._food_ids == food_ids:
            return
        with cls._lock:
            if cls._model is not None and cls._food_ids == food_ids:
                return
            try:
                import torch
                from transformers import CLIPModel, CLIPProcessor
            except ImportError as exc:
                raise ScannerError("Local scanner dependencies are missing. Install the project requirements.", 503) from exc
            cls._device = "cuda" if torch.cuda.is_available() else "cpu"
            model_name = os.getenv("USDA_LOCAL_MODEL", "openai/clip-vit-base-patch32")
            index_path = Path(os.getenv("USDA_LOCAL_INDEX", str(Path(instance_path) / "usda_scanner" / "clip_food_index.pt")))
            try:
                processor = CLIPProcessor.from_pretrained(model_name)
                model = CLIPModel.from_pretrained(model_name).to(cls._device).eval()
                features = None
                if index_path.exists():
                    cached = torch.load(index_path, map_location=cls._device, weights_only=True)
                    if cached.get("model_name") == model_name and cached.get("catalog_signature") == catalog_signature:
                        features = cached["text_features"]
                if features is None:
                    batches = []
                    with torch.inference_mode():
                        for start in range(0, len(catalog), 256):
                            labels = [f"a photo of fresh {name}" for _, name in catalog[start:start + 256]]
                            inputs = processor(text=labels, padding=True, truncation=True, return_tensors="pt").to(cls._device)
                            values = getattr(model.get_text_features(**inputs), "pooler_output", None)
                            if values is None:
                                values = model.get_text_features(**inputs)
                            batches.append(values / values.norm(dim=-1, keepdim=True))
                    features = torch.cat(batches)
                    index_path.parent.mkdir(parents=True, exist_ok=True)
                    torch.save({"model_name": model_name, "catalog_signature": catalog_signature, "text_features": features.cpu()}, index_path)
                cls._model, cls._processor = model, processor
                cls._text_features, cls._food_ids = features.to(cls._device), food_ids
            except ScannerError:
                raise
            except Exception as exc:
                raise ScannerError("The local food model is unavailable. Keep this computer online while its public model downloads for the first time.", 503) from exc

    @classmethod
    def prepare(cls, instance_path):
        """Start the expensive one-time CLIP/index setup without holding an HTTP request open."""
        catalog = cls._catalog()
        food_ids = tuple(item[0] for item in catalog)
        with cls._preparation_lock:
            if cls._model is not None and cls._food_ids == food_ids:
                return {"ready": True, "preparing": False, "error": None}
            if cls._preparing:
                return {"ready": False, "preparing": True, "error": None}
            cls._preparing = True
            cls._preparation_error = None

        def load_in_background():
            try:
                cls._load(catalog, instance_path)
            except ScannerError as exc:
                with cls._preparation_lock:
                    cls._preparation_error = str(exc)
            except Exception:
                with cls._preparation_lock:
                    cls._preparation_error = "The local food model could not be prepared. Try scanning again."
            finally:
                with cls._preparation_lock:
                    cls._preparing = False

        threading.Thread(target=load_in_background, name="usda-clip-preparation", daemon=True).start()
        return {"ready": False, "preparing": True, "error": None}

    @classmethod
    def preparation_status(cls):
        with cls._preparation_lock:
            return {
                "ready": cls._model is not None and not cls._preparing,
                "preparing": cls._preparing,
                "error": cls._preparation_error,
            }

    @classmethod
    def scan(cls, file_storage, instance_path):
        image, catalog = cls._image(file_storage), cls._catalog()
        cls._load(catalog, instance_path)
        try:
            import torch
            with torch.inference_mode():
                inputs = cls._processor(images=image, return_tensors="pt").to(cls._device)
                values = cls._model.get_image_features(**inputs)
                values = getattr(values, "pooler_output", values)
                values = values / values.norm(dim=-1, keepdim=True)
                scores, indexes = torch.topk((values @ cls._text_features.T).squeeze(0), k=min(5, len(catalog)))
        finally:
            image.close()
        return [{"fdc_id": catalog[index][0], "recognized_as": catalog[index][1], "score": round(max(0, min(100, float(score) * 100)), 1)} for score, index in zip(scores.cpu().tolist(), indexes.cpu().tolist())]
