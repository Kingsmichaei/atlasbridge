"""Fast, offline language identification for English, Hausa, Igbo and Yoruba.

Scores text on two signals:
  * characters that are distinctive to each orthography (e.g. Hausa hooked letters
    ɓ ɗ ƙ, Igbo dotted vowels ị ọ ụ, Yoruba tone-marked vowels and ẹ ọ ṣ), and
  * very common function words.
It is deliberately simple and transparent; the gateway can also ask N-ATLaS itself
(`method="model"`) when the heuristic is unsure.
"""

import re
import unicodedata

LANGS = ("en", "ha", "ig", "yo")
NAMES = {"en": "English", "ha": "Hausa", "ig": "Igbo", "yo": "Yoruba"}

_CHARS = {
    "ha": set("ɓɗƙƴʼ"),
    "ig": set("ịụṅ"),
    "yo": set("ẹṣ"),
}
# ọ is shared by Igbo and Yoruba; tone marks (acute/grave on vowels) are typical of Yoruba.
_SHARED_DOTTED_O = "ọ"

_WORDS = {
    "en": {"the", "and", "is", "are", "of", "to", "in", "what", "how", "please", "you", "my", "for", "with", "this", "that", "i", "it", "can", "why"},
    "ha": {"da", "ne", "na", "ce", "ba", "kuma", "wannan", "menene", "yaya", "ina", "shi", "ita", "su", "mu", "ku", "don", "amma", "akwai", "sannu", "zan", "yana", "tana", "ake", "nufi"},
    "ig": {"na", "nke", "bụ", "ka", "ndị", "kedu", "gị", "m", "ya", "anyị", "unu", "ha", "maka", "otu", "ihe", "ọ", "dị", "nwere", "ahụ", "mmadụ", "biko"},
    "yo": {"ni", "ti", "si", "ati", "kini", "bawo", "mo", "o", "a", "won", "wa", "fun", "pelu", "jowo", "eyi", "naa", "omi", "ara", "eniyan", "se", "ko", "mi", "re", "anfaani"},
}

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def _strip_tones(word: str) -> str:
    """Remove combining tone marks but keep under-dots (ẹ, ọ, ṣ, ị, ụ)."""
    decomposed = unicodedata.normalize("NFD", word)
    kept = "".join(ch for ch in decomposed if ch not in "̀́̂̄")
    return unicodedata.normalize("NFC", kept)


def detect(text: str) -> dict:
    """Return {"language", "name", "confidence", "scores"} for the given text."""
    text = unicodedata.normalize("NFC", text or "").lower()
    scores = {lang: 0.0 for lang in LANGS}
    if not text.strip():
        return {"language": "und", "name": "Unknown", "confidence": 0.0, "scores": scores}

    for lang, chars in _CHARS.items():
        scores[lang] += 3.0 * sum(text.count(c) for c in chars)

    dotted_o = text.count(_SHARED_DOTTED_O)
    scores["ig"] += 1.0 * dotted_o
    scores["yo"] += 1.0 * dotted_o

    decomposed = unicodedata.normalize("NFD", text)
    tone_marks = sum(decomposed.count(m) for m in ("̀", "́"))
    scores["yo"] += 0.75 * tone_marks
    scores["ig"] += 0.25 * tone_marks  # Igbo is sometimes written with tones too
    if "'" in text or "’" in text:
        scores["ha"] += 0.5  # Hausa often writes the glottal stop as an apostrophe

    words = [_strip_tones(w) for w in _WORD_RE.findall(text)]
    for w in words:
        for lang in LANGS:
            if w in _WORDS[lang]:
                scores[lang] += 1.0

    total = sum(scores.values())
    if total == 0:
        return {"language": "und", "name": "Unknown", "confidence": 0.0, "scores": scores}
    best = max(scores, key=scores.get)
    confidence = round(scores[best] / total, 3)
    return {
        "language": best,
        "name": NAMES[best],
        "confidence": confidence,
        "scores": {k: round(v, 2) for k, v in scores.items()},
    }
