"""Light text processing shared by all matchers: sentence splitting and tokenisation.

Handles English, Hindi in Devanagari and Hinglish (Hindi in Roman script).
"""
from __future__ import annotations

import re

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

# Function words that carry no skill information in Hindi / Hinglish declarations.
HINDI_STOP = {
    "मैं", "मै", "मेरे", "मेरा", "मेरी", "हूँ", "हूं", "है", "हैं", "था", "थे", "थी", "और", "का", "की", "के",
    "को", "से", "में", "पर", "भी", "ने", "यह", "वह", "जो", "तो", "कर", "करता", "करती", "करते", "हम", "साल",
    "main", "mai", "mein", "me", "mera", "meri", "mere", "hoon", "hu", "hun", "hai", "hain", "tha", "the",
    "thi", "aur", "ka", "ki", "ke", "ko", "se", "par", "pe", "bhi", "ne", "yeh", "ye", "woh", "wo", "jo",
    "to", "kar", "karta", "karti", "karte", "kiya", "hum", "saal", "sal", "liye", "lie", "bhai", "ji",
}
STOP = set(ENGLISH_STOP_WORDS) | HINDI_STOP
TOKEN_RE = re.compile(r"[a-z0-9]+|[ऀ-ॿ]+")
SENT_SPLIT = re.compile(r"[.!?।;\n]+")


def split_sentences(text: str, max_tokens: int = 20) -> list[str]:
    """Split a declaration into short units. Long run-on sentences are split again on commas."""
    out: list[str] = []
    for part in SENT_SPLIT.split(text):
        part = part.strip(" ,-–")
        if not part:
            continue
        pieces = [p.strip() for p in part.split(",")] if len(part.split()) > max_tokens else [part]
        out.extend(p for p in pieces if len(p.split()) >= 2)
    return out or [text.strip()]


def _stem(tok: str) -> str:
    if not tok.isascii() or len(tok) <= 4:
        return tok
    for suf in ("ing", "ed", "es", "s"):
        if tok.endswith(suf) and len(tok) - len(suf) >= 3:
            return tok[: -len(suf)]
    return tok


def tokens(text: str) -> list[str]:
    return [_stem(t) for t in TOKEN_RE.findall(text.lower()) if t not in STOP and len(t) > 1]
