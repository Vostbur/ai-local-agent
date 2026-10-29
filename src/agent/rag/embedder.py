import logging
from typing import List

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger("agent")


class Embedder:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None

    def _ensure_loaded(self) -> None:
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
            logger.info("Embedder model loaded: %s", self.model_name)

    def embed(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)
        self._ensure_loaded()
        vectors = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=32,
        )
        return np.asarray(vectors, dtype=np.float32)

    def embed_one(self, text: str) -> np.ndarray:
        return self.embed([text])[0]
