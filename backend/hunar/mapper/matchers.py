"""Sentence-to-criterion similarity functions.

Every matcher returns a matrix S[i, j] = similarity between declaration unit i and performance
criterion j, in [0, 1]. The aggregation from criteria to NOS and packs is identical for all
matchers (see `mapper.py`), so the comparison isolates the similarity function.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from hunar.mapper.text import tokens


class Matcher:
    name: str = "base"
    # Similarity above which a sentence counts as evidence for a criterion (explanations only).
    evidence_threshold: float = 0.5

    def fit(self, criteria: list[str]) -> Matcher:
        self.criteria = criteria
        return self

    def similarity(self, sentences: list[str]) -> np.ndarray:
        raise NotImplementedError


class KeywordMatcher(Matcher):
    """Binary bag-of-words cosine: shared content words after stop-word removal."""

    name = "keyword"
    evidence_threshold = 0.3

    def fit(self, criteria: list[str]) -> KeywordMatcher:
        super().fit(criteria)
        self._crit = [set(tokens(c)) for c in criteria]
        return self

    def similarity(self, sentences: list[str]) -> np.ndarray:
        sims = np.zeros((len(sentences), len(self._crit)))
        for i, s in enumerate(sentences):
            st = set(tokens(s))
            if not st:
                continue
            for j, ct in enumerate(self._crit):
                if ct:
                    sims[i, j] = len(st & ct) / np.sqrt(len(st) * len(ct))
        return sims


class TfidfMatcher(Matcher):
    """TF-IDF (word unigrams and bigrams) with IDF fitted on all performance criteria."""

    name = "tfidf"
    evidence_threshold = 0.25

    def fit(self, criteria: list[str]) -> TfidfMatcher:
        super().fit(criteria)
        self._vec = TfidfVectorizer(tokenizer=tokens, lowercase=False, token_pattern=None,
                                    ngram_range=(1, 2), sublinear_tf=True)
        self._crit = self._vec.fit_transform(criteria)
        return self

    def similarity(self, sentences: list[str]) -> np.ndarray:
        return (self._vec.transform(sentences) @ self._crit.T).toarray()


@lru_cache(maxsize=4)
def _load_model(model_name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name, device="cpu")


class EmbeddingMatcher(Matcher):
    """Multilingual sentence embeddings (sentence-transformers), cosine similarity."""

    def __init__(self, model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                 short_name: str | None = None, evidence_threshold: float = 0.5):
        self.model_name = model_name
        self.name = short_name or model_name.split("/")[-1]
        self.evidence_threshold = evidence_threshold

    def _encode(self, texts: list[str]) -> np.ndarray:
        return _load_model(self.model_name).encode(texts, batch_size=64, normalize_embeddings=True,
                                                   show_progress_bar=False)

    def fit(self, criteria: list[str]) -> EmbeddingMatcher:
        super().fit(criteria)
        self._crit = self._encode(criteria)
        return self

    def similarity(self, sentences: list[str]) -> np.ndarray:
        return np.clip(self._encode(sentences) @ self._crit.T, 0.0, 1.0)


MINILM = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
LABSE = "sentence-transformers/LaBSE"


def build(name: str) -> Matcher:
    if name == "keyword":
        return KeywordMatcher()
    if name == "tfidf":
        return TfidfMatcher()
    if name == "minilm":
        return EmbeddingMatcher(MINILM, "minilm", evidence_threshold=0.5)
    if name == "labse":
        return EmbeddingMatcher(LABSE, "labse", evidence_threshold=0.5)
    raise ValueError(f"unknown matcher {name!r}")
