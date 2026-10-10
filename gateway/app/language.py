"""Fast, offline language identification for English, Hausa, Igbo and Yoruba.

Works on text written with or without diacritics (most Nigerians type without them).
Three signals are combined:
  1. orthography: letters distinctive to each language (Hausa ɓ ɗ ƙ ƴ, Igbo ị ụ ṅ,
     Yoruba ẹ ṣ and tone marks);
  2. vocabulary: common words per language, matched with diacritics stripped. A word
     listed for several languages counts 1/n towards each, so shared words like
     "na" (Hausa and Igbo) don't decide the result on their own;
  3. spelling patterns: letter clusters typical of each language (Igbo "kw", "nw", "gh",
     Hausa "ts", "'y", Yoruba "gb" at word start, ...).
The gateway can also ask N-ATLaS itself (`method="model"`).
"""

import re
import unicodedata
from collections import Counter

LANGS = ("en", "ha", "ig", "yo")
NAMES = {"en": "English", "ha": "Hausa", "ig": "Igbo", "yo": "Yoruba"}

_VOCAB = {
    "en": """the a an and or but is are was were be been am i you he she it we they me my your his her its our their
        this that these those what which who whom why how when where there here of to in on at for with from by about
        as into than then so if not no yes do does did have has had can could will would should may might must
        please hello hi thanks thank good morning evening night today tomorrow yesterday name help want need know
        tell explain write give make get go come see say said like just also very more most some any all every
        one two three water food money work school market people person family health price buy sell""",
    "ha": """da ne ce na ba kuma wannan wadannan menene mene me yaya ina shi ita su mu ku ni kai ke don domin amma akwai
        babu sannu zan zai zata za yana tana suna muna kuna ake nufi mun sun kun yi yin ya ta wani wata cikin daga
        zuwa game gida ruwa abinci lafiya barka yau gobe jiya aiki kudi mutum mutane yaro yara mata maza sosai kawai
        saboda idan lokacin lokaci inda abin abu nan can kowa mai masu ga har tun sai dole kwana nagode godiya
        sunana sunanka sunanki kake kike kasuwa safiya rana dare karatu koyon koya son ina so ci sha je tafi zo
        dai fa kam haka wace wane wanne nawa yaushe ina me yasa saboda gari kasa jiki dan adam amfanin amfani
        kamar wajen yawa sosai tare ko kada kar""",
    "ig": """na nke bu bụ ka ndi ndị kedu gi gị m ya anyi anyị unu ha maka otu ihe dị di nwere ahu ahụ mmadu mmadụ biko
        ebee gini gịnị olee ole aha achoro achọrọ choro chọrọ iri nri daalu ukwu nno ndewo ututu ụtụtụ oma ọma
        chukwu nne nna ulo ụlọ akwukwo akwụkwọ oru ọrụ ego mmiri obi ezi nwa umu ụmụ ga ana eme ime adi nyere aka
        abuo abụọ ato atọ ugbu ebe mgbe gwa kwuo ma mana kwa oge ubochi ụbọchị mere bi esi aga ahia ahịa uru
        isi onye ndụ ndu ihunanya ịhụnanya kwesiri kwesịrị ezigbo nke ọma ka i mere bia bịa nọ no""",
    "yo": """ni ti si ati kini bawo mo o a won wọn wa fun pelu pẹlu jowo jọwọ eyi naa omi ara eniyan ẹniyan se ṣe ko kò
        mi re rẹ anfaani e ẹ ku kú aaro aarọ kaaro kaarọ ale alẹ osan ọsan daadaa dupe dupẹ oluwa ile owo ise iṣẹ
        ounje ounjẹ omo ọmọ iya baba nibo nigba ohun gbogbo kan meji lati sugbon ṣugbọn tabi nitori yen yi ojo ọjọ
        oni ola ọla ana lo je jẹ fe fẹ ri gbo gbọ so sọ sise ṣiṣe ba bi nkan oruko orukọ pupo pupọ jeun jẹun oja ọja
        n kilode kilọde nisinsinyi bayi ẹ jọ jo dara dáradára ọrẹ ore iwe ìwé""",
}

_PATTERNS = {
    "ig": [r"kw", r"gw", r"nw", r"gh", r"\bnd", r"\bmm", r"ch", r"\bnn"],
    "ha": [r"ts", r"'y", r"ʼy", r"\bsh", r"aw\b", r"ai\b"],
    "yo": [r"\bgb", r"\bkp", r"\bẹ", r"\bọ", r"\bn\s"],
}

_CHARS = {"ha": "ɓɗƙƴ", "ig": "ịụṅ", "yo": "ẹṣ"}

_WORD_RE = re.compile(r"[^\W\d_]+(?:['ʼ’][^\W\d_]+)?", re.UNICODE)


def _plain(s: str) -> str:
    """Lowercase and strip all diacritics (ọ→o, ị→i, à→a, ɗ stays as-is)."""
    s = unicodedata.normalize("NFD", s.lower())
    return unicodedata.normalize("NFC", "".join(c for c in s if not unicodedata.combining(c)))


def _build_vocab() -> dict[str, dict[str, float]]:
    owners: dict[str, set] = {}
    for lang, words in _VOCAB.items():
        for w in words.split():
            owners.setdefault(_plain(w), set()).add(lang)
    return {w: {l: 1.0 / len(ls) for l in ls} for w, ls in owners.items()}


_WEIGHTS = _build_vocab()


def detect(text: str) -> dict:
    """Return {"language", "name", "confidence", "scores"} for the given text."""
    raw = unicodedata.normalize("NFC", text or "").lower()
    scores = {lang: 0.0 for lang in LANGS}
    if not raw.strip():
        return {"language": "und", "name": "Unknown", "confidence": 0.0, "scores": scores}

    # 1. orthography
    for lang, chars in _CHARS.items():
        scores[lang] += 2.0 * sum(raw.count(c) for c in chars)
    dotted_o = raw.count("ọ")
    scores["ig"] += 0.75 * dotted_o
    scores["yo"] += 0.75 * dotted_o
    decomposed = unicodedata.normalize("NFD", raw)
    tones = decomposed.count("̀") + decomposed.count("́")
    scores["yo"] += 0.5 * tones
    scores["ig"] += 0.15 * tones

    # 2. vocabulary (diacritics stripped)
    words = [_plain(w) for w in _WORD_RE.findall(raw)]
    for w in words:
        for lang, wt in _WEIGHTS.get(w, {}).items():
            scores[lang] += 1.5 * wt
    # Igbo writes verb prefixes with hyphens: "na-arụ", "ga-esi"
    scores["ig"] += 1.0 * len(re.findall(r"\b(?:na|ga|a)-[a-zọụị]", raw))

    # 3. spelling patterns
    plain_text = _plain(raw)
    for lang, pats in _PATTERNS.items():
        for p in pats:
            scores[lang] += 0.4 * len(re.findall(p, plain_text if lang != "yo" else raw))

    total = sum(scores.values())
    if total == 0:
        return {"language": "und", "name": "Unknown", "confidence": 0.0, "scores": scores}
    ranked = sorted(scores, key=scores.get, reverse=True)
    best = ranked[0]
    confidence = round(scores[best] / total, 3)
    return {
        "language": best,
        "name": NAMES[best],
        "confidence": confidence,
        "scores": {k: round(v, 2) for k, v in scores.items()},
    }
