"""Sentence-transformer embedding wrapper for the attack vault."""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import TYPE_CHECKING

from cosmac.exceptions import EmbedderError

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


class Embedder:
    """Thin wrapper around sentence-transformers with lazy model loading.

    The underlying ``SentenceTransformer`` is not instantiated until the first
    call to :meth:`encode` or :meth:`encode_batch`, keeping import time fast.

    Parameters
    ----------
    model_name:
        HuggingFace model identifier.  Defaults to ``"all-MiniLM-L6-v2"``.
    cache_dir:
        Optional local directory used as the model download / cache path.
    """

    _DIMENSION = 384
    _PRIMED_SIZE = 4096

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        cache_dir: str | None = None,
    ) -> None:
        self._model_name = model_name
        self._cache_dir = cache_dir
        self._model: SentenceTransformer | None = None
        # Embeddings computed ahead of time by prime(), read back by encode().
        self._primed: OrderedDict[str, list[float]] = OrderedDict()
        self._primed_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @property
    def model_name(self) -> str:
        """Return the model identifier string."""
        return self._model_name

    @property
    def dimension(self) -> int:
        """Return the embedding dimension (384 for all-MiniLM-L6-v2)."""
        return self._DIMENSION

    # ------------------------------------------------------------------
    # Encoding
    # ------------------------------------------------------------------

    def encode(self, text: str) -> list[float]:
        """Encode a single text string into a float vector.

        Raises
        ------
        EmbedderError
            If the model cannot be loaded or encoding fails.
        """
        with self._primed_lock:
            primed = self._primed.get(text)
        if primed is not None:
            return primed
        try:
            if self._model is None:
                self._load_model()
            embedding = self._model.encode(text, show_progress_bar=False)  # type: ignore[union-attr]
            return embedding.tolist()
        except EmbedderError:
            raise
        except Exception as exc:
            raise EmbedderError(f"Failed to encode text: {exc}") from exc

    def encode_batch(self, texts: list[str]) -> list[list[float]]:
        """Encode a batch of texts into float vectors.

        Raises
        ------
        EmbedderError
            If the model cannot be loaded or encoding fails.
        """
        try:
            if self._model is None:
                self._load_model()
            embeddings = self._model.encode(texts, show_progress_bar=False)  # type: ignore[union-attr]
            return [e.tolist() for e in embeddings]
        except EmbedderError:
            raise
        except Exception as exc:
            raise EmbedderError(f"Failed to encode batch: {exc}") from exc

    def prime(self, texts: list[str]) -> None:
        """Encode many texts in one batch so later :meth:`encode` calls are instant."""
        with self._primed_lock:
            pending = [t for t in dict.fromkeys(texts) if t and t not in self._primed]
        if len(pending) < 2:
            return
        vectors = self.encode_batch(pending)
        with self._primed_lock:
            for text, vector in zip(pending, vectors, strict=True):
                self._primed[text] = vector
            while len(self._primed) > self._PRIMED_SIZE:
                self._primed.popitem(last=False)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_model(self) -> None:
        """Lazily load the ``SentenceTransformer`` model.

        Raises
        ------
        EmbedderError
            If the model cannot be imported or instantiated.
        """
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                self._model_name,
                cache_folder=self._cache_dir,
            )
        except Exception as exc:
            raise EmbedderError(
                f"Failed to load SentenceTransformer model '{self._model_name}': {exc}"
            ) from exc
