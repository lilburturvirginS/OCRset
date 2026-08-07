import re

# Tesseract sometimes inserts a single space between individual Thai
# characters (e.g. "ม ค อ" instead of "มคอ") because Thai script has no
# natural inter-word spaces and Tesseract has to guess word boundaries from
# its internal dictionary/language model. When that guess fails -- which
# happens unpredictably depending on scan quality, font, and noise -- it
# falls back to treating each character as its own "word". Thai text never
# legitimately contains a space between two Thai characters, so collapsing
# any space sandwiched between two Thai characters is always safe and never
# removes a real word boundary.
_THAI_CHAR_SPACED_RE = re.compile(r"(?<=[ก-๙])\s(?=[ก-๙])")


def collapse_spaced_thai(text: str) -> str:
    """Collapse OCR-introduced single spaces between individual Thai characters.

    Runs iteratively because removing one space can expose another
    previously non-adjacent pair of Thai characters (e.g. "ก า ร" needs two
    passes: "กา ร" -> "การ").
    """
    prev = None
    while prev != text:
        prev = text
        text = _THAI_CHAR_SPACED_RE.sub("", text)
    return text