"""BM25 — лексический поиск по чанкам."""

from __future__ import annotations

import math
import re

from src.agent.rag.chunker import Chunk

_TOKEN_RE = re.compile(r"[а-яёa-z0-9]+")


def _tokenize(text: str) -> list[str]:
    """Разбить текст на токены: lower + regex по буквам и цифрам.

    Сохраняет кириллицу, латиницу, цифры. Пунктуация отбрасывается.
    """
    return _TOKEN_RE.findall(text.lower())


class BM25Index:
    """BM25-индекс по списку чанков.

    Args:
        chunks: чанки, по которым строится индекс.
        k1: параметр насыщения TF (по умолчанию 1.5).
        b: параметр нормализации длины документа (по умолчанию 0.75).
    """

    def __init__(
        self,
        chunks: list[Chunk],
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.chunks = chunks
        self.k1 = k1
        self.b = b

        self._doc_tokens: list[list[str]] = [
            _tokenize(self._chunk_text(c)) for c in chunks
        ]
        self._doc_lens: list[int] = [len(t) for t in self._doc_tokens]
        self._avgdl: float = (
            sum(self._doc_lens) / len(self._doc_lens)
            if self._doc_lens
            else 0.0
        )

        # term -> doc_idx -> tf
        self._tf: dict[str, dict[int, int]] = {}
        # term -> df
        self._df: dict[str, int] = {}
        for idx, tokens in enumerate(self._doc_tokens):
            counts: dict[str, int] = {}
            for tok in tokens:
                counts[tok] = counts.get(tok, 0) + 1
            for tok, count in counts.items():
                self._tf.setdefault(tok, {})[idx] = count
                self._df[tok] = self._df.get(tok, 0) + 1

        # IDF сглаженный: log((N - df + 0.5) / (df + 0.5) + 1)
        n = len(self.chunks)
        self._idf: dict[str, float] = {
            term: math.log((n - df + 0.5) / (df + 0.5) + 1.0)
            for term, df in self._df.items()
        }

    @staticmethod
    def _chunk_text(chunk: Chunk) -> str:
        """Текст чанка для токенизации: section + text.

        Заголовок раздела — часть лексического контекста. Это то же
        решение, что в build.py при эмбеддинге: префикс section.
        """
        if chunk.section:
            return f"{chunk.section}. {chunk.text}"
        return chunk.text

    def search(
        self, query: str, top_k: int = 5
    ) -> list[tuple[Chunk, float]]:
        """Найти top_k чанков по BM25.

        Возвращает список (chunk, score), отсортированный по убыванию score.
        Чанки с score == 0 не попадают в результат.
        """
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scores: list[float] = [0.0] * len(self.chunks)
        for term in set(query_tokens):
            if term not in self._idf:
                continue
            idf = self._idf[term]
            for doc_idx, tf in self._tf[term].items():
                dl = self._doc_lens[doc_idx]
                denom = tf + self.k1 * (
                    1 - self.b + self.b * dl / self._avgdl
                )
                scores[doc_idx] += idf * (tf * (self.k1 + 1)) / denom

        indexed = [
            (self.chunks[i], scores[i])
            for i in range(len(self.chunks))
            if scores[i] > 0
        ]
        indexed.sort(key=lambda x: x[1], reverse=True)
        return indexed[:top_k]