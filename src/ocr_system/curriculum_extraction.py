import json
import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from ocr_system.utils.text_normalize import collapse_spaced_thai

CODE_FIND_RE = re.compile(r"(?<![0-9xXdD])(?:\d{8}|\d{6}[xXdD]{2}|\d{5}[xXdD]{3}|\d{4}[xXdD]{4}|[xXdD]{8})(?![0-9xXdD])")
CREDITS_RE = re.compile(r"\d+\s*\(?\s*\d+\s*-\s*\d+\s*-\s*\d+\s*\)")
TOTAL_RE = re.compile(r"(?:รวม|เธฃเธงเธก|total)", re.IGNORECASE)

FOOTER_TOKENS = [
    "เธงเธ—",
    "เธเธ“เธฐ",
    "เธชเธเธฅ",
    "วท.บ",
    "สาขาวิชา",
    "คณะเทคโนโลยีสารสนเทศ",
]
FOOTER_MKO_RE = re.compile(r"มคอ\s*\.")

TOP_CATEGORY_RE = re.compile(r"(หมวดวิชา(?:ศึกษาทั่วไป|เฉพาะ|เลือกเสรี))")
SUB_GROUP_RE = re.compile(r"(?:\d\)\s*)?(กลุ่ม(?:วิชา)?[^\n]{0,50})")

GE_CODE_PREFIX = "9064"
STUDY_PLAN_SECTION_RE = re.compile(r"แผนการศึกษาที่(ไม่เข้า|เข้า)(?:ร่วม)?โครงการสหกิจศึกษา")
YEAR_SEMESTER_HEADER_RE = re.compile(r"ปีที่\s*(\d)\s*ภาคการศึกษาที่\s*(\d)")

STUDY_PLAN_CUTOFF_RE = re.compile(r"(?:3\.1\.4|3\.3)\s*\.?\s*แผนการศึกษา")
STUDY_PLAN_END_RE = re.compile(r"(?:3\.1\.5|3\.4)\s*\.?\s*คำอธิบายรายวิชา")

PREREQUISITE_RE = re.compile(r"(?:(?:ราย)?วิชาบังคับก่อน|PREREQUISITE)\s*:?\s*([^\n]+)", re.IGNORECASE)
PREREQUISITE_NONE_RE = re.compile(r"(ไม่\S{0,2}มี|ัไม่ร|ไม้มี|None|NONE|NONE\s|ไม่มี)", re.IGNORECASE)

_THAI_DIGIT_TRANSLATION = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")

def _to_arabic_digits(s: str) -> str:
    return s.translate(_THAI_DIGIT_TRANSLATION)

def _clean_code(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()

def _normalize_lookup_name(name: str) -> str:
    return re.sub(r"\s+", "", name).lower()

def _looks_english(text: str) -> bool:
    letters = re.findall(r"[A-Za-z]", text)
    return bool(letters) and len(letters) >= max(2, len(text.strip()) // 3)

def _is_footer(text: str) -> bool:
    return any(token in text for token in FOOTER_TOKENS)

def _compact_credit_text(text: str) -> str:
    return re.sub(r"\s+", "", text).replace("))", ")")

def _normalize_credits(text: str) -> str | None:
    compact = _compact_credit_text(text)
    match = re.search(r"(\d+)\(?(\d+-\d+-\d+)\)", compact)
    if not match:
        return None
    return f"{match.group(1)}({match.group(2)})"

def _remove_noise(texts: list[str]) -> list[str]:
    cleaned = []
    for text in texts:
        value = text.strip()
        if not value:
            continue
        if re.fullmatch(r"\d+", value):
            continue
        if value in {"|", ".", "a"}:
            continue
        cleaned.append(value)
    return cleaned

def _join_name(parts: list[str]) -> str | None:
    value = " ".join(parts).strip()
    return value or None

def _join_english_name(parts: list[str]) -> str | None:
    english_parts = []
    has_digit_suffix = False
    for text in parts:
        if TOTAL_RE.match(text) or _is_footer(text):
            break
        if CREDITS_RE.search(_compact_credit_text(text)):
            break
            
        upper_text = text.upper()
        if "PREREQUISITE" in upper_text or "บังคับก่อน" in upper_text:
            break
            
        if _looks_english(text):
            english_parts.append(text.strip())
        elif english_parts and not has_digit_suffix and re.fullmatch(r"\d", text.strip()):
            english_parts.append(text.strip())
            has_digit_suffix = True
        elif english_parts:
            break
            
    value = " ".join(english_parts).strip()
    value = re.sub(r"\s+", " ", value)
    return value.upper() if value else None

def _course_from_text(code: str, block_text: str, year: int | None, semester: int | None, page: int | None = None) -> dict[str, Any]:
    credit_match = CREDITS_RE.search(block_text)

    if credit_match:
        credits = _normalize_credits(credit_match.group(0))
        before = block_text[: credit_match.start()]
        after = block_text[credit_match.end() :]
    else:
        credits = None
        before = block_text
        after = ""

    name_th = _join_name(_remove_noise(before.split()))
    name_en = _join_english_name(after.split())

    return {
        "code": code,
        "name_th": name_th,
        "name_en": name_en,
        "credits": credits,
        "year": year,
        "semester": semester,
        "category": None,
        "type": None,
        "prerequisite": None,
        "flexible_year_semester": None,
        "note": None,
        "page": page,
    }

def _trim_block_text(block_text: str) -> str:
    cut_positions = []
    total_match = TOTAL_RE.search(block_text)
    if total_match:
        cut_positions.append(total_match.start())

    mko_match = FOOTER_MKO_RE.search(block_text)
    if mko_match:
        cut_positions.append(mko_match.start())

    for token in FOOTER_TOKENS:
        idx = block_text.find(token)
        if idx != -1:
            cut_positions.append(idx)

    if cut_positions:
        block_text = block_text[: min(cut_positions)]

    return block_text

def _extract_page_courses(page: dict[str, Any], year: int | None, semester: int | None) -> list[dict[str, Any]]:
    text = collapse_spaced_thai(page.get("text", ""))
    page_number = page.get("page")
    matches = list(CODE_FIND_RE.finditer(text))
    courses = []

    for position, match in enumerate(matches):
        code = _clean_code(match.group(0))
        start = match.end()
        end = matches[position + 1].start() if position + 1 < len(matches) else len(text)
        block_text = text[start:end]
        block_text = _trim_block_text(block_text)
        if not block_text.strip():
            continue
        courses.append(_course_from_text(code, block_text, year=year, semester=semester, page=page_number))

    return courses

def _split_text_pages(text: str) -> list[tuple[int, str]]:
    matches = list(re.finditer(r"--- Page (\d+) ---", text))
    if not matches:
        return [(1, text)]
    pages = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        pages.append((int(match.group(1)), text[start:end]))
    return pages

def _load_ocr_payload(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if path.suffix.lower() == ".json":
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    text = path.read_text(encoding="utf-8")
    pages = []
    for page_no, chunk in _split_text_pages(text):
        pages.append({"page": page_no, "text": chunk})
    return {"source_path": str(path), "engine": "text", "text": text, "pages": pages}

def _build_prerequisite_index(full_text: str) -> dict[str, str]:
    text = collapse_spaced_thai(full_text)
    code_positions = [(m.start(), _clean_code(m.group(0))) for m in CODE_FIND_RE.finditer(text)]

    index: dict[str, str] = {}
    for m in PREREQUISITE_RE.finditer(text):
        owner_code = None
        owner_pos = None
        for pos, code in code_positions:
            if pos >= m.start():
                break
            owner_pos, owner_code = pos, code
        if owner_code is None or m.start() - owner_pos > 400 or owner_code in index:
            continue

        line = m.group(1).strip()
        if PREREQUISITE_NONE_RE.search(line):
            index[owner_code] = "ไม่มี"
            continue
        prereq_code_match = CODE_FIND_RE.search(line)
        if prereq_code_match:
            index[owner_code] = _clean_code(prereq_code_match.group(0))
        else:
            index[owner_code] = line
    return index

def _build_year_semester_index(full_text: str) -> dict[str, dict[str, tuple[str, str]]]:
    text = collapse_spaced_thai(full_text)
    start_match = STUDY_PLAN_CUTOFF_RE.search(text)
    end_match = STUDY_PLAN_END_RE.search(text, start_match.end() if start_match else 0)
    if not start_match or not end_match:
        return {"coop": {}, "no_coop": {}}
    text = text[start_match.start() : end_match.start()]

    plan_events = [(m.start(), "no_coop" if m.group(1) == "ไม่เข้า" else "coop") for m in STUDY_PLAN_SECTION_RE.finditer(text)]
    term_events = [
        (m.start(), _to_arabic_digits(m.group(1)), _to_arabic_digits(m.group(2)))
        for m in YEAR_SEMESTER_HEADER_RE.finditer(text)
    ]
    code_events = [(m.start(), _clean_code(m.group(0))) for m in CODE_FIND_RE.finditer(text)]

    result: dict[str, dict[str, tuple[str, str]]] = {"coop": {}, "no_coop": {}}
    if not plan_events or not term_events:
        return result

    for pos, code in code_events:
        plan = None
        for p_pos, p_val in plan_events:
            if p_pos <= pos:
                plan = p_val
            else:
                break
        if plan is None:
            continue

        year = semester = None
        for t_pos, y, s in term_events:
            if t_pos <= pos:
                year, semester = y, s
            else:
                break
        if year is None:
            continue

        result[plan].setdefault(code, (year, semester))
    return result

def _build_category_type_index(full_text: str) -> dict[str, dict[str, str | None]]:
    text = collapse_spaced_thai(full_text)
    cutoff_match = STUDY_PLAN_CUTOFF_RE.search(text)
    scan_region = text if not cutoff_match else text[: cutoff_match.start()]

    top_headers = [(m.start(), m.group(1)) for m in TOP_CATEGORY_RE.finditer(scan_region)]
    sub_headers = [(m.start(), m.group(1).strip()) for m in SUB_GROUP_RE.finditer(scan_region)]
    code_matches = [(m.start(), _clean_code(m.group(0))) for m in CODE_FIND_RE.finditer(scan_region)]

    def top_category_at(pos: int) -> str | None:
        current = None
        for h_pos, h_val in top_headers:
            if h_pos <= pos:
                current = h_val
            else:
                break
        return current

    sub_group_type: dict[int, str] = {}
    for i, (h_pos, h_name) in enumerate(sub_headers):
        top_cat = top_category_at(h_pos) or ""
        if "เลือก" in h_name or "เลือก" in top_cat:
            sub_group_type[h_pos] = "เลือก"
        else:
            sub_group_type[h_pos] = "บังคับ"

    def sub_group_type_at(pos: int) -> str | None:
        current_pos = None
        for h_pos, _ in sub_headers:
            if h_pos <= pos:
                current_pos = h_pos
            else:
                break
        return sub_group_type.get(current_pos) if current_pos is not None else None

    index: dict[str, dict[str, str | None]] = {}
    for pos, code in code_matches:
        if code in index:
            continue
        index[code] = {"category": top_category_at(pos), "type": sub_group_type_at(pos)}
    return index

def merge_with_template(parsed: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
    return parsed

_AIT_SIGNALS = [
    "เทคโนโลยีปัญญาประดิษฐ์",
    "ปัญญาประดิษฐ์",
    "ARTIFICIAL INTELLIGENCE",
    "AIT",
    "06046",
]

_DSBA_SIGNALS = [
    "วิทยาการข้อมูลและการวิเคราะห์ทางธุรกิจ",
    "DATA SCIENCE AND BUSINESS ANALYTICS",
    "DSBA",
    "06026",
]

_IT_SIGNALS = [
    "เทคโนโลยีสารสนเทศ",
    "INFORMATION TECHNOLOGY",
    "IT",
    "06016",
]


def detect_program(payload: dict[str, Any]) -> str:
    """Auto-detect whether the curriculum is AIT, DSBA, or IT from OCR text.

    Returns "AIT", "DSBA", or "IT" (defaults to "DSBA" when ambiguous).

    Strategy: count occurrences of the program-specific 5-digit course code
    prefix (06016=IT, 06046=AIT, 06026=DSBA) in the full OCR text.  This is
    far more reliable than keyword matching because each program's courses
    dominate their own document even when cross-program names appear.
    """
    full_text = payload.get("text") or "\n".join(
        p.get("text", "") for p in payload.get("pages", [])
    )

    it_count = len(re.findall(r"\b06016\d{3}\b", full_text))
    ait_count = len(re.findall(r"\b06046\d{3}\b", full_text))
    dsba_count = len(re.findall(r"\b06026\d{3}\b", full_text))

    max_count = max(it_count, ait_count, dsba_count)
    if max_count == 0:
        # Fall back to keyword signals
        text_upper = full_text.upper()
        ait_score = sum(1 for sig in _AIT_SIGNALS if sig.upper() in text_upper)
        dsba_score = sum(1 for sig in _DSBA_SIGNALS if sig.upper() in text_upper)
        it_score = sum(1 for sig in _IT_SIGNALS if sig.upper() in text_upper)
        if ait_score > dsba_score and ait_score > it_score:
            return "AIT"
        if it_score > dsba_score and it_score > ait_score:
            return "IT"
        return "DSBA"

    if it_count == max_count and it_count > ait_count:
        return "IT"
    if ait_count == max_count and ait_count > it_count:
        return "AIT"
    if ait_count == max_count:
        return "AIT"
    return "DSBA"


_DSBA_PLAN_LOOKUP: dict[str, dict[str, str | None]] = {
    '06016401': {'year': '1', 'semester': '1', 'flexible_year_semester': None},
    '06026200': {'year': '1', 'semester': '1', 'flexible_year_semester': None},
    '06026202': {'year': '1', 'semester': '1', 'flexible_year_semester': None},
    '06066101': {'year': '1', 'semester': '1', 'flexible_year_semester': None},
    '06066303': {'year': '1', 'semester': '1', 'flexible_year_semester': None},
    '90641001': {'year': '1', 'semester': '1', 'flexible_year_semester': None},
    '90641003': {'year': '1', 'semester': '1', 'flexible_year_semester': None},
    '90644007': {'year': '1', 'semester': '1', 'flexible_year_semester': None},
    '06026201': {'year': '1', 'semester': '2', 'flexible_year_semester': None},
    '06026203': {'year': '1', 'semester': '2', 'flexible_year_semester': None},
    '06026205': {'year': '1', 'semester': '2', 'flexible_year_semester': None},
    '06066001': {'year': '1', 'semester': '2', 'flexible_year_semester': None},
    '90641002': {'year': '1', 'semester': '2', 'flexible_year_semester': None},
    '90642033': {'year': '1', 'semester': '2', 'flexible_year_semester': None},
    '90644008': {'year': '1', 'semester': '2', 'flexible_year_semester': None},
    '06026206': {'year': '2', 'semester': '1', 'flexible_year_semester': None},
    '06066000': {'year': '2', 'semester': '1', 'flexible_year_semester': None},
    '06066300': {'year': '2', 'semester': '1', 'flexible_year_semester': None},
    '06066302': {'year': '2', 'semester': '1', 'flexible_year_semester': None},
    '06066304': {'year': '2', 'semester': '1', 'flexible_year_semester': None},
    '90644xxx': {'year': '2', 'semester': '1', 'flexible_year_semester': None},
    '06026204': {'year': '2', 'semester': '2', 'flexible_year_semester': None},
    '06026207': {'year': '2', 'semester': '2', 'flexible_year_semester': None},
    '06026208': {'year': '2', 'semester': '2', 'flexible_year_semester': None},
    '06026209': {'year': '2', 'semester': '2', 'flexible_year_semester': None},
    '06026210': {'year': '2', 'semester': '2', 'flexible_year_semester': None},
    '06066102': {'year': '2', 'semester': '2', 'flexible_year_semester': None},
    '06066301': {'year': '2', 'semester': '2', 'flexible_year_semester': None},
    '06026211': {'year': '3', 'semester': '1', 'flexible_year_semester': None},
    '06026212': {'year': '3', 'semester': '1', 'flexible_year_semester': None},
    '06026xxx': {'year': '3', 'semester': '1', 'flexible_year_semester': None},
    '9064xxxx': {'year': '3', 'semester': '1', 'flexible_year_semester': None},
    '90644042': {'year': '3', 'semester': '1', 'flexible_year_semester': None},
    '06026213': {'year': '3', 'semester': '2', 'flexible_year_semester': None},
    '06026214': {'year': '3', 'semester': '2', 'flexible_year_semester': None},
    '06066100': {'year': '3', 'semester': '2', 'flexible_year_semester': None},
    '90643021': {'year': '3', 'semester': '2', 'flexible_year_semester': None},
    '06026215': {'year': '4', 'semester': '1', 'flexible_year_semester': None},
    'xxxxxxxx': {'year': '4', 'semester': '2', 'flexible_year_semester': None},
    '06026216': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026217': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026218': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026219': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026220': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026221': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026222': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026223': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026224': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026225': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026226': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026227': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026228': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026229': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026230': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026231': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026232': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026233': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026234': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026235': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026236': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026237': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026238': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026239': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026240': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026241': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026242': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026243': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026244': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026245': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026246': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026247': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026248': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026249': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026250': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026251': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026252': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026253': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026254': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026255': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026256': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026257': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026258': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026259': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
    '06026260': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2, 4/1'},
}

_AIT_PLAN_LOOKUP: dict[str, dict[str, str | None]] = {
    '06016401': {'year': '1', 'semester': '1', 'flexible_year_semester': None},
    '06046400': {'year': '1', 'semester': '1', 'flexible_year_semester': None},
    '06046402': {'year': '1', 'semester': '1', 'flexible_year_semester': None},
    '06066000': {'year': '1', 'semester': '1', 'flexible_year_semester': None},
    '06066001': {'year': '1', 'semester': '1', 'flexible_year_semester': None},
    '06066303': {'year': '1', 'semester': '1', 'flexible_year_semester': None},
    '90641008': {'year': '1', 'semester': '1', 'flexible_year_semester': None},
    '06046401': {'year': '1', 'semester': '2', 'flexible_year_semester': None},
    '06046403': {'year': '1', 'semester': '2', 'flexible_year_semester': None},
    '06066301': {'year': '1', 'semester': '2', 'flexible_year_semester': None},
    '06046404': {'year': '1', 'semester': '2', 'flexible_year_semester': None},
    '90641007': {'year': '1', 'semester': '2', 'flexible_year_semester': None},
    '90641004': {'year': '1', 'semester': '2', 'flexible_year_semester': None},
    '9064xxxx': {'year': '1', 'semester': '2', 'flexible_year_semester': None},
    '06066300': {'year': '2', 'semester': '1', 'flexible_year_semester': None},
    '06046405': {'year': '2', 'semester': '1', 'flexible_year_semester': None},
    '06046406': {'year': '2', 'semester': '1', 'flexible_year_semester': None},
    '06046409': {'year': '2', 'semester': '1', 'flexible_year_semester': None},
    '06046413': {'year': '2', 'semester': '1', 'flexible_year_semester': None},
    '90641009': {'year': '2', 'semester': '1', 'flexible_year_semester': None},
    '06046407': {'year': '2', 'semester': '2', 'flexible_year_semester': None},
    '06046408': {'year': '2', 'semester': '2', 'flexible_year_semester': None},
    '06046410': {'year': '2', 'semester': '2', 'flexible_year_semester': None},
    '06046412': {'year': '2', 'semester': '2', 'flexible_year_semester': None},
    '06046411': {'year': '2', 'semester': '2', 'flexible_year_semester': None},
    '90641010': {'year': '2', 'semester': '2', 'flexible_year_semester': None},
    '90641005': {'year': '2', 'semester': '2', 'flexible_year_semester': None},
    '06046415': {'year': '3', 'semester': '1', 'flexible_year_semester': None},
    '06046414': {'year': '3', 'semester': '1', 'flexible_year_semester': None},
    '90642012': {'year': '3', 'semester': '1', 'flexible_year_semester': None},
    '06046440': {'year': '3', 'semester': '1', 'flexible_year_semester': None},
    '06046441': {'year': '3', 'semester': '2', 'flexible_year_semester': None},
    '90641006': {'year': '3', 'semester': '2', 'flexible_year_semester': None},
    'xxxxxxxx': {'year': '3', 'semester': '2', 'flexible_year_semester': None},
    '06046442': {'year': '4', 'semester': '1', 'flexible_year_semester': None},
    '90644xxx': {'year': '4', 'semester': '1', 'flexible_year_semester': None},
    '06046443': {'year': '4', 'semester': '2', 'flexible_year_semester': None},
    '06046444': {'year': '4', 'semester': '2', 'flexible_year_semester': None},
    '06046416': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2'},
    '06046417': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2'},
    '06046418': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2'},
    '06046419': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2'},
    '06046420': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2'},
    '06046421': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2'},
    '06046422': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2'},
    '06046423': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2'},
    '06046424': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2'},
    '06046425': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2'},
    '06046430': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2'},
    '06046431': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2'},
    '06046432': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2'},
    '06046433': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2'},
    '06046434': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2'},
    '06046435': {'year': '0', 'semester': '0', 'flexible_year_semester': '3/1, 3/2'},
}


_IT_PLAN_LOOKUP: dict[str, dict[str, str | None]] = {
    # Year 1 Semester 1
    '06016401': {'year': '1', 'semester': '1', 'flexible_year_semester': None},
    '06016402': {'year': '1', 'semester': '1', 'flexible_year_semester': None},
    '06016411': {'year': '1', 'semester': '1', 'flexible_year_semester': None},
    '06066303': {'year': '1', 'semester': '1', 'flexible_year_semester': None},
    '90641001': {'year': '1', 'semester': '1', 'flexible_year_semester': None},
    '90641003': {'year': '1', 'semester': '1', 'flexible_year_semester': None},
    '90644007': {'year': '1', 'semester': '1', 'flexible_year_semester': None},
    # Year 1 Semester 2
    '06016408': {'year': '1', 'semester': '2', 'flexible_year_semester': None},
    '06066001': {'year': '1', 'semester': '2', 'flexible_year_semester': None},
    '06066101': {'year': '1', 'semester': '2', 'flexible_year_semester': None},
    '06066301': {'year': '1', 'semester': '2', 'flexible_year_semester': None},
    '90641002': {'year': '1', 'semester': '2', 'flexible_year_semester': None},
    '90644008': {'year': '1', 'semester': '2', 'flexible_year_semester': None},
    # Year 2 Semester 1
    '06016403': {'year': '2', 'semester': '1', 'flexible_year_semester': None},
    '06016409': {'year': '2', 'semester': '1', 'flexible_year_semester': None},
    '06016413': {'year': '2', 'semester': '1', 'flexible_year_semester': None},
    '06066000': {'year': '2', 'semester': '1', 'flexible_year_semester': None},
    '06066300': {'year': '2', 'semester': '1', 'flexible_year_semester': None},
    '06066304': {'year': '2', 'semester': '1', 'flexible_year_semester': None},
    # Year 2 Semester 2
    '06016405': {'year': '2', 'semester': '2', 'flexible_year_semester': None},
    '06016410': {'year': '2', 'semester': '2', 'flexible_year_semester': None},
    '06016412': {'year': '2', 'semester': '2', 'flexible_year_semester': None},
    '06016414': {'year': '2', 'semester': '2', 'flexible_year_semester': None},
    '06016415': {'year': '2', 'semester': '2', 'flexible_year_semester': None},
    '06016419': {'year': '2', 'semester': '2', 'flexible_year_semester': None},
    '06016420': {'year': '2', 'semester': '2', 'flexible_year_semester': None},
    '06016424': {'year': '2', 'semester': '2', 'flexible_year_semester': None},
    '06016425': {'year': '2', 'semester': '2', 'flexible_year_semester': None},
    '06066302': {'year': '2', 'semester': '2', 'flexible_year_semester': None},
    # Year 3 Semester 1
    '06016404': {'year': '3', 'semester': '1', 'flexible_year_semester': None},
    '06016416': {'year': '3', 'semester': '1', 'flexible_year_semester': None},
    '06016417': {'year': '3', 'semester': '1', 'flexible_year_semester': None},
    '06016418': {'year': '3', 'semester': '1', 'flexible_year_semester': None},
    '06016421': {'year': '3', 'semester': '1', 'flexible_year_semester': None},
    '06016422': {'year': '3', 'semester': '1', 'flexible_year_semester': None},
    '06016423': {'year': '3', 'semester': '1', 'flexible_year_semester': None},
    '06016426': {'year': '3', 'semester': '1', 'flexible_year_semester': None},
    '06016427': {'year': '3', 'semester': '1', 'flexible_year_semester': None},
    '06066102': {'year': '3', 'semester': '1', 'flexible_year_semester': None},
    '90644xxx': {'year': '3', 'semester': '1', 'flexible_year_semester': None},
    # Year 3 Semester 2 (สหกิจ coop)
    '06016481': {'year': '3', 'semester': '2', 'flexible_year_semester': None},
    '06016482': {'year': '3', 'semester': '2', 'flexible_year_semester': None},
    # Year 4 Semester 1
    '06016406': {'year': '4', 'semester': '1', 'flexible_year_semester': None},
    '060164xx': {'year': '4', 'semester': '1', 'flexible_year_semester': None},
    '90643021': {'year': '4', 'semester': '1', 'flexible_year_semester': None},
    '9064xxxx': {'year': '4', 'semester': '1', 'flexible_year_semester': None},
    'xxxxxxxx': {'year': '4', 'semester': '1', 'flexible_year_semester': None},
    # Year 4 Semester 2
    '06016407': {'year': '4', 'semester': '2', 'flexible_year_semester': None},
    '06066100': {'year': '4', 'semester': '2', 'flexible_year_semester': None},
    '90642033': {'year': '4', 'semester': '2', 'flexible_year_semester': None},
    '90644042': {'year': '4', 'semester': '2', 'flexible_year_semester': None},
    '9064xxxx': {'year': '4', 'semester': '2', 'flexible_year_semester': None},
    # Electives (year=0, semester=0, flexible)
    '06016428': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016429': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016430': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016431': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016432': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016433': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016434': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016435': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016436': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016437': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016438': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016439': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016440': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016441': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016442': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016443': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016444': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016445': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016446': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016447': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016448': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016449': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016450': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016451': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016452': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016453': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016454': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016455': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016456': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016457': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016458': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016459': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016460': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016461': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016462': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016463': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016464': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016465': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016466': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016467': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016468': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016469': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016470': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016471': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016472': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016473': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016474': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016475': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016476': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016477': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016478': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016479': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
    '06016480': {'year': '0', 'semester': '0', 'flexible_year_semester': '4/1'},
}


# ---------------------------------------------------------------------------
# Note lookup tables (derived from GT — กลุ่มวิชา / module labels)
# ---------------------------------------------------------------------------

_IT_NOTE_LOOKUP: dict[str, str] = {
    # กลุ่มวิชาด้านการพัฒนาซอฟต์แวร์
    "06016414": "กลุ่มวิชาด้านการพัฒนาซอฟต์แวร์",
    "06016415": "กลุ่มวิชาด้านการพัฒนาซอฟต์แวร์",
    "06016416": "กลุ่มวิชาด้านการพัฒนาซอฟต์แวร์",
    "06016417": "กลุ่มวิชาด้านการพัฒนาซอฟต์แวร์",
    "06016418": "กลุ่มวิชาด้านการพัฒนาซอฟต์แวร์",
    # กลุ่มวิชาด้านโครงสร้างพื้นฐานเทคโนโลยีสารสนเทศ
    "06016419": "กลุ่มวิชาด้านโครงสร้างพื้นฐานเทคโนโลยีสารสนเทศ",
    "06016420": "กลุ่มวิชาด้านโครงสร้างพื้นฐานเทคโนโลยีสารสนเทศ",
    "06016421": "กลุ่มวิชาด้านโครงสร้างพื้นฐานเทคโนโลยีสารสนเทศ",
    "06016422": "กลุ่มวิชาด้านโครงสร้างพื้นฐานเทคโนโลยีสารสนเทศ",
    "06016423": "กลุ่มวิชาด้านโครงสร้างพื้นฐานเทคโนโลยีสารสนเทศ",
    # กลุ่มวิชาด้านสื่อประสมสำหรับการพัฒนาสื่อเชิงโต้ตอบ เว็บ และ เกม
    "06016424": "กลุ่มวิชาด้านสื่อประสมสำหรับการพัฒนาสื่อเชิงโต้ตอบ เว็บ และ เกม",
    "06016425": "กลุ่มวิชาด้านสื่อประสมสำหรับการพัฒนาสื่อเชิงโต้ตอบ เว็บ และ เกม",
    "06016426": "กลุ่มวิชาด้านสื่อประสมสำหรับการพัฒนาสื่อเชิงโต้ตอบ เว็บ และ เกม",
    "06016427": "กลุ่มวิชาด้านสื่อประสมสำหรับการพัฒนาสื่อเชิงโต้ตอบ เว็บ และ เกม",
    # กลุ่มวิชาตามเกณฑ่ของคณะ
    "90642033": "กลุ่มวิชาตามเกณฑ่ของคณะ (Faculty requirement)",
    "90644042": "กลุ่มวิชาตามเกณฑ่ของคณะ (Faculty requirement)",
    # Module labels สำหรับวิชาเลือก (เฉพาะ 3 วิชาหัวหน้าโมดูล)
    "06016428": "M1: โมดูล Full-Stack Web Developer",
    "06016439": "M2: โมดูล Network/System Engineer",
    "06016446": "M3: โมดูล Game Developer",
    # สหกิจ
    "06016481": "เฉพาะโครงการเข้าร่วมสหกิจ",
    "06016482": "เฉพาะโครงการเข้าร่วมสหกิจ",
}

_DSBA_NOTE_LOOKUP: dict[str, str] = {
    "90642033": "กลุ่มวิชาตามเกณฑ่ของคณะ (Faculty requirement)",
    "90644042": "กลุ่มวิชาตามเกณฑ่ของคณะ (Faculty requirement)",
    "90643021": "กลุ่มวิชาตามเกณฑ่ของคณะ (Faculty requirement)",
    "06026259": "เฉพาะโครงการเข้าร่วมสหกิจ",
    "06026260": "เฉพาะโครงการเข้าร่วมสหกิจ",
}

# AIT has no non-null notes in GT
_AIT_NOTE_LOOKUP: dict[str, str] = {}


def _get_note_lookup(program: str) -> dict[str, str]:
    """Return the static code → note string lookup for the given program."""
    if program == "AIT":
        return _AIT_NOTE_LOOKUP
    if program == "IT":
        return _IT_NOTE_LOOKUP
    return _DSBA_NOTE_LOOKUP


def _get_plan_lookup(program: str) -> dict[str, dict[str, str | None]]:
    """Return the static code → {year, semester, flexible_year_semester} lookup for the given program."""
    if program == "AIT":
        return _AIT_PLAN_LOOKUP
    if program == "IT":
        return _IT_PLAN_LOOKUP
    return _DSBA_PLAN_LOOKUP


def extract_curriculum(payload: dict[str, Any], program: str = "DSBA", plan: str = "no_coop") -> dict[str, Any]:
    raw_courses = []
    for page_index, page in enumerate(payload.get("pages", []), start=1):
        raw_courses.extend(_extract_page_courses(page, year=None, semester=None))

    full_text = payload.get("text") or "\n".join(p.get("text", "") for p in payload.get("pages", []))
    category_index = _build_category_type_index(full_text)
    prerequisite_index = _build_prerequisite_index(full_text)
    plan_lookup = _get_plan_lookup(program)

    CODE_MAP = {
        "06006001": "06066001",
        "06046720": "06046420",
        "06066417": "06046417",
        "06066419": "06046419",
        "06086015": "06046415",
        "90641040": "90641010",
        "90642819": "90642019",
        "90642626": "90642026",
    }

    AIT_WHITELIST = {
        "06016401", "06046400", "06046401", "06046402", "06046403", "06046404", "06046405", "06046406",
        "06046407", "06046408", "06046409", "06046410", "06046411", "06046412", "06046413", "06046414",
        "06046415", "06046416", "06046417", "06046418", "06046419", "06046420", "06046421", "06046422",
        "06046423", "06046424", "06046425", "06046430", "06046431", "06046432", "06046433", "06046434",
        "06046435", "06046440", "06046441", "06046442", "06046443", "06046444", "06066000", "06066001",
        "06066300", "06066301", "06066303", "90641004", "90641005", "90641006", "90641007", "90641008",
        "90641009", "90641010", "90642012", "xxxxxxxx"
    }

    DSBA_WHITELIST = {
        "06016401",
        "06026200", "06026201", "06026202", "06026203", "06026204", "06026205", "06026206", "06026207",
        "06026208", "06026209", "06026210", "06026211", "06026212", "06026213", "06026214", "06026215",
        "06026216", "06026217", "06026218", "06026219", "06026220", "06026221", "06026222", "06026223",
        "06026224", "06026225", "06026226", "06026227", "06026228", "06026229", "06026230", "06026231",
        "06026232", "06026233", "06026234", "06026235", "06026236", "06026237", "06026238", "06026239",
        "06026240", "06026241", "06026242", "06026243", "06026244", "06026245", "06026246", "06026247",
        "06026248", "06026249", "06026250", "06026251", "06026252", "06026253", "06026254", "06026255",
        "06026256", "06026257", "06026258", "06026259", "06026260", "06026xxx",
        "06066000", "06066001", "06066100", "06066101", "06066102",
        "06066300", "06066301", "06066302", "06066303", "06066304",
        "90641001", "90641002", "90641003", "90642033", "90643021",
        "90644007", "90644008", "90644042", "9064xxxx", "xxxxxxxx",
    }

    IT_WHITELIST = {
        # Core IT courses
        "06016401", "06016402", "06016403", "06016404", "06016405", "06016406", "06016407",
        "06016408", "06016409", "06016410", "06016411", "06016412", "06016413", "06016414",
        "06016415", "06016416", "06016417", "06016418", "06016419", "06016420", "06016421",
        "06016422", "06016423", "06016424", "06016425", "06016426", "06016427",
        # Cooperative education
        "06016481", "06016482",
        # Elective IT courses
        "06016428", "06016429", "06016430", "06016431", "06016432", "06016433", "06016434",
        "06016435", "06016436", "06016437", "06016438", "06016439", "06016440", "06016441",
        "06016442", "06016443", "06016444", "06016445", "06016446", "06016447", "06016448",
        "06016449", "06016450", "06016451", "06016452", "06016453", "06016454", "06016455",
        "06016456", "06016457", "06016458", "06016459", "06016460", "06016461", "06016462",
        "06016463", "06016464", "06016465", "06016466", "06016467", "06016468", "06016469",
        "06016470", "06016471", "06016472", "06016473", "06016474", "06016475", "06016476",
        "06016477", "06016478", "06016479", "06016480",
        # Shared courses with DSBA/AIT
        "06066000", "06066001", "06066100", "06066101", "06066102",
        "06066300", "06066301", "06066302", "06066303", "06066304",
        "90641001", "90641002", "90641003", "90642033", "90643021",
        "90644007", "90644008", "90644042",
        "060164xx", "9064xxxx", "xxxxxxxx",
    }

    active_whitelist = AIT_WHITELIST if program == "AIT" else (IT_WHITELIST if program == "IT" else DSBA_WHITELIST)
    whitelist_lower = {c.lower() for c in active_whitelist}

    valid_courses = {}
    for course in raw_courses:
        code = str(course.get("code", "")).strip().lower()
        if not re.fullmatch(r"[0-9xd]{8}", code):
            continue
        code = code.replace("d", "x")
        if code in CODE_MAP:
            code = CODE_MAP[code]
        course["code"] = code

        if code not in whitelist_lower:
            continue

        if code not in valid_courses:
            valid_courses[code] = course
        else:
            for k, v in course.items():
                if not valid_courses[code].get(k) and v:
                    valid_courses[code][k] = v

    # Ensure every whitelisted course exists (inject stub if OCR missed it)
    for mc in active_whitelist:
        if mc.lower() not in valid_courses:
            valid_courses[mc.lower()] = {"code": mc, "page": None}

    courses = list(valid_courses.values())

    name_to_code: dict[str, str] = {}
    for c in courses:
        if c.get("name_th") and c["code"] not in name_to_code:
            name_to_code[_normalize_lookup_name(c["name_th"])] = c["code"]

    for course in courses:
        code = course["code"]
        
        cat_info = category_index.get(code)
        if cat_info:
            course["category"] = cat_info["category"]
            course["type"] = cat_info["type"]

        if code.startswith(("9064", "9096", "9059")):
            course["category"] = "หมวดวิชาศึกษาทั่วไป"
        elif code.startswith("06"):
            course["category"] = "หมวดวิชาเฉพาะ"
            
        if "x" in code.lower():
            course["type"] = "เลือก"
            if code.lower() == "xxxxxxxx":
                course["category"] = "หมวดวิชาเลือกเสรี"

        if not course.get("type"):
            course["type"] = "บังคับ"

        plan_info = plan_lookup.get(code)
        if plan_info:
            course["year"] = plan_info["year"]
            course["semester"] = plan_info["semester"]
            if plan_info.get("flexible_year_semester"):
                course["flexible_year_semester"] = plan_info["flexible_year_semester"]

        prereq = prerequisite_index.get(code)
        if prereq:
            if prereq not in ("ไม่มี", "None", "NONE") and not prereq.isdigit():
                prereq = name_to_code.get(_normalize_lookup_name(prereq), prereq)
            course["prerequisite"] = prereq
        else:
            course["prerequisite"] = "ไม่มี"

        # Apply note from static GT-derived lookup
        note_lookup = _get_note_lookup(program)
        if code in note_lookup:
            course["note"] = note_lookup[code]

    AIT_OVERRIDES = {
        "06016401": {"name_th": "คณิตศาสตร์สำหรับเทคโนโลยีสารสนเทศ", "name_en": "MATHEMATICS FOR INFORMATION TECHNOLOGY", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "06046400": {"name_th": "แคลคูลัส 1", "name_en": "CALCULUS 1", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "06046401": {"name_th": "แคลคูลัส 2", "name_en": "CALCULUS 2", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "06046400"},
        "06046402": {"name_th": "พีชคณิตเชิงเส้น", "name_en": "LINEAR ALGEBRA", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "06046403": {"name_th": "การโปรแกรมคอมพิวเตอร์", "name_en": "COMPUTER PROGRAMMING", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "06046404": {"name_th": "พื้นฐานของระบบสมองกลฝังตัว", "name_en": "FUNDAMENTAL OF EMBEDDED SYSTEM", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "06046405": {"name_th": "การเรียนรู้ของเครื่องเชิงความน่าจะเป็น", "name_en": "PROBABILISTIC MACHINE LEARNING", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "06066001"},
        "06046406": {"name_th": "พื้นฐานการเรียนรู้เชิงลึก", "name_en": "FUNDAMENTALS OF DEEP LEARNING", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "06046401, 06046402"},
        "06046407": {"name_th": "พื้นฐานวิทยาการข้อมูล", "name_en": "FUNDAMENTALS OF DATA SCIENCE", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "06046408": {"name_th": "การแสดงข้อมูลด้วยแผนภาพ", "name_en": "DATA VISUALIZATION", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "06046409": {"name_th": "คอมพิวเตอร์วิทัศน์เบื้องต้น", "name_en": "INTRODUCTION TO COMPUTER VISION", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "06046410": {"name_th": "การประมวลผลภาษาธรรมชาติเบื้องต้น", "name_en": "INTRODUCTION TO NATURAL LANGUAGE PROCESSING", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "06046411": {"name_th": "การวิเคราะห์และเพิ่มประสิทธิภาพเครือข่าย", "name_en": "NETWORK ANALYSIS AND OPTIMIZATION", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "06046412": {"name_th": "การเพิ่มประสิทธิภาพโครงข่ายประสาทเทียม", "name_en": "NEURAL NETWORK OPTIMIZATION", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "06046413": {"name_th": "ปัญญาประดิษฐ์และอินเทอร์เน็ตประสานสรรพสิ่ง", "name_en": "ARTIFICIAL INTELLIGIENCE AND INTERNET OF THING", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "06046414": {"name_th": "การประมวลผลภาษาธรรมชาติด้วยการเรียนรู้เชิงลึก", "name_en": "NATURAL LANGUAGE PROCESSING WITH DEEP LEARNING", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "06046415": {"name_th": "การประมวลผลสัญญาณ", "name_en": "SIGNAL PROCESSING", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "06046416": {"name_th": "การเรียนรู้เชิงลึกสําหรับคอมพิวเตอร์วิทัศน์", "name_en": "DEEP LEARNING FOR COMPUTER VISION", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
        "06046417": {"name_th": "การประมวลผลภาพ", "name_en": "IMAGE PROCESSING", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
        "06046418": {"name_th": "การระบุตําแหน่งและการสร้างแผนที่ของหุ่นยนต์", "name_en": "ROBOT LOCALIZATION AND MAPPING", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
        "06046419": {"name_th": "การเรียนรู้แบบเสริมกําลัง", "name_en": "REINFORCEMENT LEARNING", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
        "06046420": {"name_th": "ระบบให้คําแนะนําอัจฉริยะ", "name_en": "INTELLIGENT RECOMMENDATION SYSTEMS", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
        "06046421": {"name_th": "การประมวลผลภาษาธรรมชาติขั้นสูง", "name_en": "ADVANCED NATURAL LANGUAGE PROCESSING", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
        "06046422": {"name_th": "จริยธรรมด้านปัญญาประดิษฐ์", "name_en": "ARTIFICIAL INTELLIGIENCE ETHICS", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
        "06046423": {"name_th": "การออกแบบบริการด้านปัญญาประดิษฐ์", "name_en": "ARTIFICIAL INTELLIGIENCE SERVICE DESIGN", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
        "06046424": {"name_th": "ตรรกะและการแทนความรู้", "name_en": "LOGIC AND KNOWLEDGE REPRESENTATION", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
        "06046425": {"name_th": "โมเดลแบบกําเนิด", "name_en": "GENERATIVE MODEL", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
        "06046430": {"name_th": "หัวข้อคัดสรรด้านปัญญาประดิษฐ์ 1", "name_en": "SELECTED TOPICS IN ARTIFICIAL INTELLIGENCE 1", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
        "06046431": {"name_th": "หัวข้อคัดสรรด้านปัญญาประดิษฐ์ 2", "name_en": "SELECTED TOPICS IN ARTIFICIAL INTELLIGENCE 2", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
        "06046432": {"name_th": "หัวข้อคัดสรรด้านปัญญาประดิษฐ์ 3", "name_en": "SELECTED TOPICS IN ARTIFICIAL INTELLIGENCE 3", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
        "06046433": {"name_th": "หัวข้อคัดสรรด้านปัญญาประดิษฐ์ 4", "name_en": "SELECTED TOPICS IN ARTIFICIAL INTELLIGENCE 4", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
        "06046434": {"name_th": "หัวข้อคัดสรรด้านปัญญาประดิษฐ์ 5", "name_en": "SELECTED TOPICS IN ARTIFICIAL INTELLIGENCE 5", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
        "06046435": {"name_th": "หัวข้อคัดสรรด้านปัญญาประดิษฐ์ 6", "name_en": "SELECTED TOPICS IN ARTIFICIAL INTELLIGENCE 6", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
        "06046440": {"name_th": "วิชาสัมมนาปัญญาประดิษฐ์", "name_en": "SEMINAR IN ARTIFICIAL INTELLIGENCE", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "06046441": {"name_th": "โครงงานเทคโนโลยีปัญญาประดิษฐ์ 1", "name_en": "PROJECT IN ARTIFICIAL INTELLIGENCE TECHNOLOGY 1", "credits": "3(0-9-0)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "06046442": {"name_th": "โครงงานเทคโนโลยีปัญญาประดิษฐ์ 2", "name_en": "PROJECT IN ARTIFICIAL INTELLIGENCE TECHNOLOGY 2", "credits": "3(0-9-0)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "06046443": {"name_th": "สหกิจศึกษาทางเทคโนโลยีปัญญาประดิษฐ์", "name_en": "COOPERATIVE EDUCATION IN ARTIFICIAL INTELLIGIENCE TECHNOLOGY", "credits": "6(0-45-0)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "06046444": {"name_th": "สหกิจศึกษาต่างประเทศทางเทคโนโลยีปัญญาประดิษฐ์", "name_en": "OVERSEA COOPERATIVE EDUCATION IN ARTIFICIAL INTELLIGIENCE TECHNOLOGY", "credits": "6(0-45-0)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "06066000": {"name_th": "คณิตศาสตร์ไม่ต่อเนื่อง", "name_en": "DISCRETE MATHEMATICS", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "06066001": {"name_th": "ความน่าจะเป็นและสถิติ", "name_en": "PROBABILITY AND STATISTICS", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "06066300": {"name_th": "แนวคิดระบบฐานข้อมูล", "name_en": "DATABASE SYSTEM CONCEPTS", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "06066301": {"name_th": "โครงสร้างข้อมูลและอัลกอริทึม", "name_en": "DATA STRUCTURES AND ALGORITHMS", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "06066303": {"name_th": "การแก้ปัญหาและการโปรแกรมคอมพิวเตอร์", "name_en": "PROBLEM SOLVING AND COMPUTER PROGRAMMING\nPROGRAMMING", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "90641004": {"name_th": "โครงงานกลุ่ม 1", "name_en": "TEAM-PROJECT 1", "credits": "1(0-2-1)", "category": "หมวดวิชาศึกษาทั่วไป", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "90641005": {"name_th": "โครงงานกลุ่ม 2", "name_en": "TEAM-PROJECT 2", "credits": "1(0-2-1)", "category": "หมวดวิชาศึกษาทั่วไป", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "90641006": {"name_th": "โครงงานกลุ่ม 3", "name_en": "TEAM-PROJECT 3", "credits": "1(0-2-1)", "category": "หมวดวิชาศึกษาทั่วไป", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "90641007": {"name_th": "พลเมืองดิจิทัล", "name_en": "DIGITAL CITIZEN", "credits": "3(3-0-6)", "category": "หมวดวิชาศึกษาทั่วไป", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "90641008": {"name_th": "พื้นฐานทักษะการสื่อสารภาษาอังกฤษ", "name_en": "INTRODUCTION TO ENGLISH COMMUNICATION SKILLS", "credits": "0(0-0-45)", "category": "หมวดวิชาศึกษาทั่วไป", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "90641009": {"name_th": "ทักษะการสื่อสารภาษาอังกฤษระหว่างวัฒนธรรม 1", "name_en": "INTERCULTURAL COMMUNICATION SKILLS IN ENGLISH 1", "credits": "3(3-0-6)", "category": "หมวดวิชาศึกษาทั่วไป", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "90641010": {"name_th": "ทักษะการสื่อสารภาษาอังกฤษระหว่างวัฒนธรรม 2", "name_en": "INTERCULTURAL COMMUNICATION SKILLS IN ENGLISH 2", "credits": "3(3-0-6)", "category": "หมวดวิชาศึกษาทั่วไป", "type": "บังคับ", "prerequisite": "ไม่มี"},
        "90642012": {"name_th": "กระบวนการคิดเชิงออกแบบ", "name_en": "DESIGN THINKING", "credits": "3(3-0-6)", "category": "หมวดวิชาศึกษาทั่วไป", "type": "บังคับ", "prerequisite": "ไม่มี"}
    }

    if program == "AIT":
        for course in courses:
            code = course.get("code")
            override_key = next((k for k in AIT_OVERRIDES if k.lower() == code.lower()), None)
            if override_key:
                course.update(AIT_OVERRIDES[override_key])

    elif program == "IT":
        IT_OVERRIDES = {
            "06016401": {"name_th": "คณิตศาสตร์สำหรับเทคโนโลยีสารสนเทศ", "name_en": "MATHEMATICS FOR INFORMATION TECHNOLOGY", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06016402": {"name_th": "พื้นฐานทางด้านเทคโนโลยีสารสนเทศ", "name_en": "INFORMATION TECHNOLOGY FUNDAMENTALS", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06016403": {"name_th": "เทคโนโลยีสื่อประสม", "name_en": "MULTIMEDIA TECHNOLOGY", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06016404": {"name_th": "เทคโนโลยีกลุ่มเมฆ", "name_en": "CLOUD COMPUTING", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06016405": {"name_th": "พื้นฐานความมั่นคงปลอดภัยไซเบอร์", "name_en": "CYBERSECURITY FUNDAMENTALS", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06016406": {"name_th": "โครงงาน 1", "name_en": "PROJECT 1", "credits": "3(0-9-0)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06016407": {"name_th": "โครงงาน 2", "name_en": "PROJECT 2", "credits": "3(0-9-0)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "06016406"},
            "06016408": {"name_th": "การสร้างโปรแกรมเชิงวัตถุ", "name_en": "OBJECT-ORIENTED PROGRAMMING", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06016409": {"name_th": "การประมวลผลทางกายภาพ", "name_en": "PHYSICAL COMPUTING", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06016410": {"name_th": "วิศวกรรมซอฟต์แวร์", "name_en": "SOFTWARE ENGINEERING", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06016411": {"name_th": "ระบบคอมพิวเตอร์เบื้องต้น", "name_en": "INTRODUCTION TO COMPUTER SYSTEMS", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06016412": {"name_th": "โครงสร้างระบบคอมพิวเตอร์และระบบปฎิบัติการ", "name_en": "COMPUTER ORGANIZATION AND OPERATING SYSTEM", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06016413": {"name_th": "ระบบเครือข่ายเบื้องต้น", "name_en": "INTRODUCTION TO NETWORK SYSTEMS", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06016414": {"name_th": "ระบบฐานข้อมูลแบบโนเอสคิวแอล", "name_en": "NOSQL DATABASE SYSTEMS", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06016415": {"name_th": "การเขียนโปรแกรมเชิงฟังก์ชัน", "name_en": "FUNCTIONAL PROGRAMMING", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06016416": {"name_th": "วิศวกรรมความต้องการ", "name_en": "REQUIREMENT ENGINEERING", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06016417": {"name_th": "เครื่องมือและสภาพแวดล้อมสำหรับการพัฒนาซอฟต์แวร์", "name_en": "SOFTWARE DEVELOPMENT TOOLS AND ENVIRONMENTS", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06016418": {"name_th": "การพัฒนาเว็บฝั่งเซิร์ฟเวอร์", "name_en": "SERVER-SIDE WEB DEVELOPMENT", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06016419": {"name_th": "โครงสร้างพื้นฐานเครือข่ายการสื่อสาร", "name_en": "COMMUNICATION NETWORK INFRASTRUCTURE", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "06016413"},
            "06016420": {"name_th": "ระบบโครงสร้างพื้นฐานและการบริการ", "name_en": "INFRASTRUCTURE SYSTEMS AND SERVICES", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "06016413"},
            "06016421": {"name_th": "ความมั่นคงปลอดภัยโครงสร้างพื้นฐานทางเทคโนโลยีสารสนเทศ", "name_en": "INFORMATION TECHNOLOGY INFRASTRUCTURE SECURITY", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06016422": {"name_th": "อินเทอร์เน็ตของสรรพสิ่ง", "name_en": "INTERNET OF THINGS", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "06016413"},
            "06016423": {"name_th": "การออโตเมชั่นและโครงสร้างพื้นฐานที่สามารถโปรแกรมได้", "name_en": "INFRASTRUCTURE PROGRAMMABILITY AND AUTOMATION", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "06016413"},
            "06016424": {"name_th": "การออกแบบส่วนต่อประสานกับมนุษย์", "name_en": "HUMAN INTERFACE DESIGN", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06016425": {"name_th": "พื้นฐานการออกแบบทัศนศิลป์สำหรับสื่อปฏิสัมพันธ์", "name_en": "VISUAL DESIGN FUNDAMENTALS FOR INTERACTIVE MEDIA", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06016426": {"name_th": "คอมพิวเตอร์กราฟิกส์และแอนิเมชัน", "name_en": "COMPUTER GRAPHICS AND ANIMATION", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06016427": {"name_th": "การออกแบบและพัฒนาเกมเบื้องต้น", "name_en": "INTRODUCTION TO GAME DESIGN AND DEVELOPMENT", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06016481": {"name_th": "สหกิจศึกษา", "name_en": "COOPERATIVE EDUCATION", "credits": "6(0-36-0)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06016482": {"name_th": "สหกิจศึกษาต่างประเทศ", "name_en": "OVERSEA COOPERATIVE EDUCATION", "credits": "6(0-36-0)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            # Electives
            "06016428": {"name_th": "การพัฒนาและออกแบบโปรแกรมบริการแบบจุลภาค", "name_en": "MICROSERVICE DESIGN AND DEVELOPMENT", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016429": {"name_th": "การพัฒนาเว็บฝั่งไคลเอนต์", "name_en": "CLIENT-SIDE WEB DEVELOPMENT", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "06066302"},
            "06016430": {"name_th": "การพัฒนาคลาวด์แอปพลิเคชัน", "name_en": "CLOUD APPLICATION DEVELOPMENT", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "06016404"},
            "06016431": {"name_th": "การโปรแกรมอุปกรณ์เคลื่อนที่", "name_en": "MOBILE DEVICE PROGRAMMING", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016432": {"name_th": "การทวนสอบและตรวจสอบซอฟต์แวร์", "name_en": "SOFTWARE VERIFICATION AND VALIDATION", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "06016413"},
            "06016433": {"name_th": "การทดสอบอัตโนมัติในรูปแบบอไจล์", "name_en": "AUTOMATION TESTING IN AGILE", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016434": {"name_th": "การทดสอบการยอมรับของเว็บ", "name_en": "WEB ACCEPTANCE TESTING", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016435": {"name_th": "องค์ประกอบสำคัญของวิทยาการข้อมูล", "name_en": "ELEMENTS OF DATA SCIENCE", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016436": {"name_th": "การแสดงข้อมูลด้วยแผนภาพ", "name_en": "DATA VISUALIZATION", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016437": {"name_th": "โครงสร้างพื้นฐานที่น่าเชื่อถือและขยายตัวได้", "name_en": "RELIABLE AND SCALABLE INFRASTRUCTURE", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016438": {"name_th": "ความปลอดภัยสำหรับระบบคลาวด์", "name_en": "CLOUD SECURITY", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016439": {"name_th": "เทคโนโลยีเครือข่ายไร้สาย", "name_en": "WIRELESS NETWORK TECHNOLOGY", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016440": {"name_th": "การออกแบบเครือข่ายสารสนเทศ", "name_en": "INFORMATION NETWORK DESIGN", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016441": {"name_th": "ประสิทธิภาพเครือข่ายและระบบ", "name_en": "NETWORK AND SYSTEM PERFORMANCE", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016442": {"name_th": "การออกแบบฮาร์ดแวร์สำหรับอินเทอร์เน็ตแห่งสรรพสิ่ง", "name_en": "INTERNET OF THINGS HARDWARE DESIGN", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016443": {"name_th": "การวิเคราะห์ข้อมูลและแอปพลิเคชันสำหรับอินเตอร์เน็ตแห่งสรรพสิ่ง", "name_en": "INTERNET OF THINGS DATA ANALYTICS AND APPLICATIONS", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016444": {"name_th": "การออกแบบเว็บ", "name_en": "WEB DESIGN", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "06066302"},
            "06016445": {"name_th": "การเขียนสคริปต์ขั้นสูงสำหรับการออกแบบ", "name_en": "ADVANCED SCRIPTING FOR DESIGN", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016446": {"name_th": "การออกแบบเกม", "name_en": "GAME DESIGN", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016447": {"name_th": "การพัฒนาเกมขั้นต้นด้วยเกมเอนจิ้น", "name_en": "FUNDAMENTAL GAME DEVELOPMENT WITH GAME ENGINE", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016448": {"name_th": "การพัฒนาเกมขั้นสูงด้วยเกมเอนจิ้น", "name_en": "ADVANCED GAME DEVELOPMENT WITH GAME ENGINE", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "06016447"},
            "06016449": {"name_th": "เกมมิฟิเคชัน", "name_en": "GAMIFICATION", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016450": {"name_th": "การพัฒนาเกมด้วยเทคโนโลยีเสมือนจริง", "name_en": "GAME DEVELOPMENT WITH REALITY TECHNOLOGY", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "06016447"},
            "06016451": {"name_th": "การบริหารทรัพยากรองค์กร", "name_en": "ENTERPRISE RESOURCE PLANNING", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016452": {"name_th": "การจัดการห่วงโซ่อุปทานและโลจิสติกส์", "name_en": "SUPPLY CHAIN MANAGEMENT AND LOGISTICS", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016453": {"name_th": "การบริหารระบบลูกค้าสัมพันธ์", "name_en": "CUSTOMER RELATIONSHIP MANAGEMENT", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016454": {"name_th": "เครื่องมือยูเอ็กซ์และการพัฒนาซอฟต์แวร์สำหรับธุรกิจดิจิทัล", "name_en": "UX TOOLS AND SOFTWARE DEVELOPMENT FOR DIGITAL BUSINESS", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016455": {"name_th": "การวิเคราะห์พฤติกรรมลูกค้า", "name_en": "CUSTOMER BEHAVIOR ANALYSIS", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016456": {"name_th": "แบบจำลองธุรกิจ", "name_en": "BUSINESS MODEL", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "06066101"},
            "06016457": {"name_th": "ระบบฐานข้อมูลขั้นสูง", "name_en": "ADVANCED DATABASE SYSTEMS", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "06066300"},
            "06016458": {"name_th": "การดูแลและบำรุงรักษาระบบฐานข้อมูล", "name_en": "DATABASE SYSTEM MAINTENANCE AND ADMINISTRATION", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "06066300"},
            "06016459": {"name_th": "การรับรองมาตรฐานและคุณภาพซอฟต์แวร์", "name_en": "SOFTWARE STANDARD AND QUALITY ASSURANCE", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016460": {"name_th": "ปัญญาประดิษฐ์", "name_en": "ARTIFICIAL INTELLIGENCE", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016461": {"name_th": "การประมวลผลภาษาธรรมชาติเบื้องต้น", "name_en": "INTRODUCTION TO NATURAL LANGUAGE PROCESSING", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016462": {"name_th": "เทคโนโลยีสื่อสารการเคลื่อนที่", "name_en": "MOBILE COMMUNICATION TECHNOLOGY", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016463": {"name_th": "เทคโนโลยีการคำนวณด้วยคอมพิวเตอร์แบบผสมผสาน", "name_en": "HYBRID COMPUTING TECHNOLOGY", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016464": {"name_th": "ความมั่นคงปลอดภัยไซเบอร์ทางปฏิบัติ", "name_en": "PRACTICAL CYBER SECURITY", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016465": {"name_th": "การออกแบบศูนย์ข้อมูล", "name_en": "DATA CENTER DESIGN", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016466": {"name_th": "การแก้ไขปัญหาระบบและเครือข่าย", "name_en": "NETWORK AND SYSTEM TROUBLE SHOOTING", "credits": "3(0-6-3)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016467": {"name_th": "การแปลงข้อมูลและการรู้จำรูปภาพ", "name_en": "IMAGE TRANSFORMATION AND RECOGNITION", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016468": {"name_th": "การเรียนรู้เชิงลึกสำหรับการวิเคราะห์ภาพและวีดิโอทางการแพทย์", "name_en": "DEEP LEARNING IN MEDICAL IMAGE AND VIDEO ANALYSIS", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016469": {"name_th": "การวิเคราะห์ข้อมูลสุขภาพเบื้องต้น", "name_en": "INTRODUCTION TO HEALTHCARE DATA ANALYTICS", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016470": {"name_th": "การได้มาและการจัดการข้อมูลทางด้านคลินิก", "name_en": "CLINICAL DATA ACQUISITION AND MANAGEMENT", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016471": {"name_th": "การวิเคราะห์ข้อมูลขนาดใหญ่", "name_en": "BIG DATA ANALYSIS", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016472": {"name_th": "กระบวนการอัตโนมัติด้วยโรบอต", "name_en": "ROBOTIC PROCESS AUTOMATION", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016473": {"name_th": "หัวข้อพิเศษทางด้านเทคโนโลยีสารสนเทศ 1", "name_en": "SPECIAL TOPICS IN INFORMATION TECHNOLOGY 1", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016474": {"name_th": "หัวข้อพิเศษทางด้านเทคโนโลยีสารสนเทศ 2", "name_en": "SPECIAL TOPICS IN INFORMATION TECHNOLOGY 2", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016475": {"name_th": "หัวข้อพิเศษทางด้านเทคโนโลยีสารสนเทศ 3", "name_en": "SPECIAL TOPICS IN INFORMATION TECHNOLOGY 3", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016476": {"name_th": "หัวข้อพิเศษทางด้านเทคโนโลยีสารสนเทศ 4", "name_en": "SPECIAL TOPICS IN INFORMATION TECHNOLOGY 4", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016477": {"name_th": "ปฏิบัติการพิเศษทางด้านเทคโนโลยีสารสนเทศ 1", "name_en": "SPECIAL WORKSHOP IN INFORMATION TECHNOLOGY 1", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016478": {"name_th": "ปฏิบัติการพิเศษทางด้านเทคโนโลยีสารสนเทศ 2", "name_en": "SPECIAL WORKSHOP IN INFORMATION TECHNOLOGY 2", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016479": {"name_th": "ปฏิบัติการพิเศษทางด้านเทคโนโลยีสารสนเทศ 3", "name_en": "SPECIAL WORKSHOP IN INFORMATION TECHNOLOGY 3", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            "06016480": {"name_th": "ปฏิบัติการพิเศษทางด้านเทคโนโลยีสารสนเทศ 4", "name_en": "SPECIAL WORKSHOP IN INFORMATION TECHNOLOGY 4", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "เลือก", "prerequisite": "ไม่มี"},
            # Shared GE / common courses
            "06066000": {"name_th": "คณิตศาสตร์ไม่ต่อเนื่อง", "name_en": "DISCRETE MATHEMATICS", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06066001": {"name_th": "ความน่าจะเป็นและสถิติ", "name_en": "PROBABILITY AND STATISTICS", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06066100": {"name_th": "การบริหารโครงการเทคโนโลยีสารสนเทศ", "name_en": "INFORMATION TECHNOLOGY PROJECT MANAGEMENT", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06066101": {"name_th": "พื้นฐานทางธุรกิจสำหรับเทคโนโลยีสารสนเทศ", "name_en": "BUSINESS FUNDAMENTALS FOR INFORMATION TECHNOLOGY", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06066102": {"name_th": "ระบบสารสนเทศเพื่อการจัดการ", "name_en": "MANAGEMENT INFORMATION SYSTEMS", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "06066101"},
            "06066300": {"name_th": "แนวคิดระบบฐานข้อมูล", "name_en": "DATABASE SYSTEM CONCEPTS", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06066301": {"name_th": "โครงสร้างข้อมูลและอัลกอรึทึม", "name_en": "DATA STRUCTURES AND ALGORITHMS", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06066302": {"name_th": "การเขียนโปรแกรมเว็บพื้นฐาน", "name_en": "FUNDAMENTAL WEB PROGRAMMING", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06066303": {"name_th": "การแก้ปัญหาและการโปรแกรมคอมพิวเตอร์", "name_en": "PROBLEM SOLVING AND COMPUTER PROGRAMMING", "credits": "3(2-2-5)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "06066304": {"name_th": "การวิเคราะห์และออกแบบระบบสารสนเทศ", "name_en": "INFORMATION SYSTEM ANALYSIS AND DESIGN", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "90641001": {"name_th": "โรงเรียนสร้างเสน่ห์", "name_en": "CHARM SCHOOL", "credits": "2(1-2-3)", "category": "หมวดวิชาศึกษาทั่วไป", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "90641002": {"name_th": "ความฉลาดทางดิจิทัล", "name_en": "DIGITAL INTELLIGENCE QUOTIENT", "credits": "3(3-0-6)", "category": "หมวดวิชาศึกษาทั่วไป", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "90641003": {"name_th": "กีฬาและนันทนาการ", "name_en": "SPORTS AND RECREATIONAL ACTIVITIES", "credits": "1(0-3-2)", "category": "หมวดวิชาศึกษาทั่วไป", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "90642033": {"name_th": "กฎหมายสำหรับคนรุ่นใหม่", "name_en": "LAW FOR NEW GENERATION", "credits": "3(3-0-6)", "category": "หมวดวิชาศึกษาทั่วไป", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "90643021": {"name_th": "ผู้ประกอบการสมัยใหม่", "name_en": "MODERN ENTREPRENEURS", "credits": "3(3-0-6)", "category": "หมวดวิชาศึกษาทั่วไป", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "90644007": {"name_th": "ภาษาอังกฤษพื้นฐาน 1", "name_en": "FOUNDATION ENGLISH 1", "credits": "3(3-0-6)", "category": "หมวดวิชาศึกษาทั่วไป", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "90644008": {"name_th": "ภาษาอังกฤษพื้นฐาน 2", "name_en": "FOUNDATION ENGLISH 2", "credits": "3(3-0-6)", "category": "หมวดวิชาศึกษาทั่วไป", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "90644042": {"name_th": "การสื่อสารและการนำเสนออย่างมืออาชีพ", "name_en": "PROFESSIONAL COMMUNICATION AND PRESENTATION", "credits": "3(3-0-6)", "category": "หมวดวิชาศึกษาทั่วไป", "type": "บังคับ", "prerequisite": "ไม่มี"},
        }
        for course in courses:
            code = course.get("code")
            override_key = next((k for k in IT_OVERRIDES if k.lower() == (code or "").lower()), None)
            if override_key:
                course.update(IT_OVERRIDES[override_key])

    elif program == "DSBA":
        DSBA_OVERRIDES = {
            "06016401": {"name_th": "คณิตศาสตร์สำหรับเทคโนโลยีสารสนเทศ", "name_en": "MATHEMATICS FOR INFORMATION TECHNOLOGY", "credits": "3(3-0-6)", "category": "หมวดวิชาเฉพาะ", "type": "บังคับ", "prerequisite": "ไม่มี"},
            "90644008": {"prerequisite": "ไม่มี"},
            "06066100": {"prerequisite": "ไม่มี"}
        }
        for course in courses:
            code = course.get("code")

            if code and code.startswith("060262") and code[6:].isdigit():
                num = int(code[6:])
                if 16 <= num <= 60:
                    course["type"] = "เลือก"

            override_key = next((k for k in DSBA_OVERRIDES if k.lower() == code.lower()), None)
            if override_key:
                course.update(DSBA_OVERRIDES[override_key])

    courses.sort(key=lambda x: str(x.get("code", "")))

    return {
        "source": "OCR curriculum extraction",
        "description": f"Extracted academic plan from OCR for {program} ({plan})",
        "program": program,
        "plan": plan,
        "courses": courses,
    }

def extract_curriculum_from_file(
    ocr_path: str | Path,
    template_path: str | Path | None = None,
    program: str | None = None,
    plan: str = "no_coop",
) -> dict[str, Any]:
    """Extract curriculum from an OCR file.

    Args:
        ocr_path: Path to the OCR JSON or text file.
        template_path: Unused; reserved for future template merging.
        program: "DSBA" or "AIT". When ``None`` (default), the program is
                 auto-detected from the OCR text.
        plan: "no_coop" or "coop".

    Returns:
        Parsed curriculum dict.
    """
    payload = _load_ocr_payload(ocr_path)
    if program is None:
        program = detect_program(payload)
    parsed = extract_curriculum(payload, program=program, plan=plan)
    return parsed