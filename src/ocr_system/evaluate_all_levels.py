"""
Lab 6 — Run the OCR dataset from all previous labs and evaluate results at
multiple levels against ground truth:

  1. FIELD LEVEL    -- per-field accuracy (name_en, credits, category, type,
                        prerequisite) averaged across all matched courses.
  2. PAGE LEVEL      -- of all ground-truth courses, what fraction were
                        successfully located to a specific page in the OCR'd
                        curriculum book. Distinguishes courses found by exact
                        code match vs found only via a name-based fallback
                        (code missing/misread but the course name matched
                        something extracted elsewhere) vs not found at all.
  3. CATEGORY LEVEL  -- field-level accuracy AND recall broken down separately
                        for each course category (หมวดวิชาศึกษาทั่วไป /
                        หมวดวิชาเฉพาะ), so accuracy differences between course
                        groups are visible rather than averaged away.
  4. TYPE LEVEL       -- same breakdown as category level, but grouped by
                        course type (บังคับ / เลือก) instead.
  5. QA CITATION CHECK -- cross-checks the Lab5 question/answer pairs: for
                        each QA row that cites specific course codes and page
                        numbers, verifies the page(s) actually match where
                        this extraction run found those courses. Ties Lab5
                        and Lab6 together instead of evaluating them in
                        isolation.

Usage:
    python -m ocr_system.evaluate_all_levels <ocr_json> <ground_truth_json> [<ground_truth_json> ...] [--qa <qa_csv>] [--output-dir <dir>]

Outputs a human-readable report to stdout and a machine-readable
`evaluation_all_levels.json` file (written to --output-dir, default "outputs").
"""

import csv
import json
import re
import sys
from pathlib import Path

from ocr_system.curriculum_extraction import extract_curriculum_from_file
from ocr_system.evaluate_curriculum import _normalize_credits, _normalize_name

FIELDS_TO_CHECK = ["name_en", "credits", "category", "type", "prerequisite"]


def _fields_match(field: str, expected, got) -> bool:
    if field == "name_en":
        return _normalize_name(expected) == _normalize_name(got)
    if field == "credits":
        return _normalize_credits(expected) == _normalize_credits(got)
    return expected == got


def _normalize_lookup_name(name: str) -> str:
    return re.sub(r"\s+", "", name or "").lower()


def _best_occurrence_by_code(courses: list[dict]) -> dict[str, dict]:
    best: dict[str, dict] = {}
    for c in courses:
        code = c.get("code")
        if not isinstance(code, str) or not code.isdigit():
            continue
        is_good = bool(c.get("name_en")) and bool(c.get("credits"))
        if code not in best:
            best[code] = c
            continue
        existing = best[code]
        existing_good = bool(existing.get("name_en")) and bool(existing.get("credits"))
        if is_good and not existing_good:
            best[code] = c
    return best


def _build_name_lookup(courses: list[dict]) -> dict[str, dict]:
    lookup: dict[str, dict] = {}
    for c in courses:
        if c.get("page") is None:
            continue
        for field in ("name_th", "name_en"):
            name = c.get(field)
            if not name:
                continue
            key = _normalize_lookup_name(name)
            if key not in lookup:
                lookup[key] = c
    return lookup


def evaluate_field_level(gt_courses: list[dict], best_by_code: dict[str, dict]) -> dict:
    totals = {f: 0 for f in FIELDS_TO_CHECK}
    matches = {f: 0 for f in FIELDS_TO_CHECK}
    matched_courses = 0

    for gt_course in gt_courses:
        code = gt_course.get("code")
        if not isinstance(code, str) or not code.isdigit():
            continue
        extracted = best_by_code.get(code)
        if not extracted:
            continue
        matched_courses += 1
        for field in FIELDS_TO_CHECK:
            expected = gt_course.get(field)
            if expected is None:
                continue
            totals[field] += 1
            if _fields_match(field, expected, extracted.get(field)):
                matches[field] += 1

    return {
        "matched_courses": matched_courses,
        "per_field": {
            field: {
                "checked": totals[field],
                "correct": matches[field],
                "accuracy": round(matches[field] / totals[field], 4) if totals[field] else None,
            }
            for field in FIELDS_TO_CHECK
        },
    }


def load_page_mapping(page_mapping_path: str) -> dict[str, dict]:
    """Load course_page_mapping.csv into a dict keyed by course code."""
    mapping: dict[str, dict] = {}
    with open(page_mapping_path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            code = (row.get("code") or "").strip()
            if code:
                mapping[code] = row
    return mapping


def evaluate_page_level(
    gt_courses: list[dict],
    best_by_code: dict[str, dict],
    name_lookup: dict[str, dict],
    page_mapping: dict[str, dict] | None = None,
) -> dict:
    total = 0
    found_by_code = 0
    found_by_name_only = 0
    pages_used: set[str] = set()
    missing_codes = []

    for gt_course in gt_courses:
        code = gt_course.get("code")
        if not isinstance(code, str) or not code.isdigit():
            continue
        total += 1

        # Use course_page_mapping.csv as ground truth when available
        if page_mapping and code in page_mapping:
            row = page_mapping[code]
            status = row.get("status", "")
            primary = [p.strip() for p in (row.get("primary_pages") or "").split(";") if p.strip()]
            if status == "found" and primary:
                found_by_code += 1
                pages_used.update(primary)
                continue
            elif status == "found_by_name_only":
                found_by_name_only += 1
                pages_used.update(primary)
                continue
            else:
                missing_codes.append(code)
                continue

        # Fallback: infer from OCR output
        extracted = best_by_code.get(code)
        page = extracted.get("page") if extracted else None
        if page is not None:
            found_by_code += 1
            pages_used.add(str(page))
            continue

        name = gt_course.get("name_th") or gt_course.get("name_en")
        alt = name_lookup.get(_normalize_lookup_name(name)) if name else None
        if alt and alt.get("page") is not None:
            found_by_name_only += 1
            pages_used.add(str(alt["page"]))
            continue

        missing_codes.append(code)

    found = found_by_code + found_by_name_only
    page_nums = sorted(int(p) for p in pages_used if p.isdigit())
    return {
        "total_gt_courses": total,
        "found_by_code": found_by_code,
        "found_by_name_only": found_by_name_only,
        "not_found": len(missing_codes),
        "page_localization_rate": round(found / total, 4) if total else None,
        "distinct_pages_used": len(pages_used),
        "page_range": f"{min(page_nums)}-{max(page_nums)}" if page_nums else None,
        "missing_codes": missing_codes,
    }


def _grouped_level(gt_courses: list[dict], best_by_code: dict[str, dict], group_field: str) -> dict:
    groups: dict[str, dict] = {}
    for gt_course in gt_courses:
        code = gt_course.get("code")
        if not isinstance(code, str) or not code.isdigit():
            continue
        key = gt_course.get(group_field) or f"(ไม่ระบุ {group_field})"
        g = groups.setdefault(
            key,
            {"gt_total": 0, "matched": 0, "totals": {f: 0 for f in FIELDS_TO_CHECK}, "matches": {f: 0 for f in FIELDS_TO_CHECK}},
        )
        g["gt_total"] += 1
        extracted = best_by_code.get(code)
        if not extracted:
            continue
        g["matched"] += 1
        for field in FIELDS_TO_CHECK:
            expected = gt_course.get(field)
            if expected is None:
                continue
            g["totals"][field] += 1
            if _fields_match(field, expected, extracted.get(field)):
                g["matches"][field] += 1

    result = {}
    for key, g in groups.items():
        result[key] = {
            "gt_total": g["gt_total"],
            "matched": g["matched"],
            "recall": round(g["matched"] / g["gt_total"], 4) if g["gt_total"] else None,
            "per_field": {
                field: {
                    "checked": g["totals"][field],
                    "correct": g["matches"][field],
                    "accuracy": round(g["matches"][field] / g["totals"][field], 4) if g["totals"][field] else None,
                }
                for field in FIELDS_TO_CHECK
            },
        }
    return result


def evaluate_qa_citations(qa_csv_path: str, best_by_code: dict[str, dict], program: str | None = None) -> dict:
    checked = 0
    ok = 0
    mismatches = []

    with open(qa_csv_path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            # filter by program if specified
            if program and row.get("program") and row["program"].upper() != program.upper():
                continue
            # extract 8-digit codes from the 'note' column
            codes = re.findall(r"\d{8}", row.get("note") or "")
            # cited_pages uses ';' as delimiter
            cited_pages = {p.strip() for p in (row.get("cited_pages") or "").split(";") if p.strip()}
            if not codes or not cited_pages:
                continue
            checked += 1

            actual_pages = {
                str(best_by_code[c]["page"])
                for c in codes
                if c in best_by_code and best_by_code[c].get("page") is not None
            }
            if actual_pages and actual_pages & cited_pages:
                ok += 1
            else:
                mismatches.append({
                    "question": row.get("question"),
                    "program": row.get("program"),
                    "cited_pages": sorted(cited_pages),
                    "actual_pages": sorted(actual_pages),
                })

    return {"qa_pairs_checked": checked, "qa_pairs_citation_ok": ok, "qa_pairs_citation_mismatches": mismatches}


def run(
    ocr_json_path: str,
    ground_truth_paths: list[str],
    qa_csv_path: str | None = None,
    page_mapping_path: str | None = None,
    program: str = "DSBA",
    plan: str = "no_coop",
) -> dict:
    extracted = extract_curriculum_from_file(ocr_json_path, program=program, plan=plan)
    best_by_code = _best_occurrence_by_code(extracted["courses"])
    name_lookup = _build_name_lookup(extracted["courses"])
    page_mapping = load_page_mapping(page_mapping_path) if page_mapping_path else None

    report: dict = {"ocr_source": ocr_json_path, "ground_truth_files": {}}

    for gt_path in ground_truth_paths:
        gt = json.loads(Path(gt_path).read_text(encoding="utf-8"))
        gt_courses = gt.get("courses", [])
        report["ground_truth_files"][Path(gt_path).name] = {
            "field_level": evaluate_field_level(gt_courses, best_by_code),
            "page_level": evaluate_page_level(gt_courses, best_by_code, name_lookup, page_mapping),
            "category_level": _grouped_level(gt_courses, best_by_code, "category"),
            "type_level": _grouped_level(gt_courses, best_by_code, "type"),
        }

    if qa_csv_path:
        report["qa_citation_check"] = evaluate_qa_citations(qa_csv_path, best_by_code, program=program)

    return report


def _print_field_block(title: str, per_field: dict) -> None:
    print(f"\n--- {title} ---")
    for field, stats in per_field.items():
        acc = f"{stats['accuracy'] * 100:.1f}%" if stats["accuracy"] is not None else "n/a"
        print(f"  {field:15s}: {acc:>7s}  ({stats['correct']}/{stats['checked']})")


def print_report(report: dict) -> None:
    for gt_name, levels in report["ground_truth_files"].items():
        print(f"\n{'=' * 70}")
        print(f"GROUND TRUTH: {gt_name}")
        print(f"{'=' * 70}")

        _print_field_block(f"FIELD LEVEL ({levels['field_level']['matched_courses']} courses matched)", levels["field_level"]["per_field"])

        pl = levels["page_level"]
        print(f"\n--- PAGE LEVEL ---")
        rate = f"{pl['page_localization_rate'] * 100:.1f}%" if pl["page_localization_rate"] is not None else "n/a"
        print(f"  Found by code:      {pl['found_by_code']}/{pl['total_gt_courses']}")
        print(f"  Found by name only: {pl['found_by_name_only']}/{pl['total_gt_courses']}")
        print(f"  Not found:          {pl['not_found']}/{pl['total_gt_courses']}")
        print(f"  Page localization rate: {rate}")
        print(f"  Pages spanned:      {pl['page_range']} ({pl['distinct_pages_used']} distinct pages)")
        if pl["missing_codes"]:
            print(f"  Missing codes:      {pl['missing_codes']}")

        print(f"\n--- CATEGORY LEVEL ---")
        for category, stats in levels["category_level"].items():
            recall = f"{stats['recall'] * 100:.1f}%" if stats["recall"] is not None else "n/a"
            print(f"  [{category}] gt_total={stats['gt_total']} matched={stats['matched']} recall={recall}")
            _print_field_block("fields", stats["per_field"])

        print(f"\n--- TYPE LEVEL ---")
        for type_name, stats in levels["type_level"].items():
            recall = f"{stats['recall'] * 100:.1f}%" if stats["recall"] is not None else "n/a"
            print(f"  [{type_name}] gt_total={stats['gt_total']} matched={stats['matched']} recall={recall}")
            _print_field_block("fields", stats["per_field"])

    if "qa_citation_check" in report:
        qa = report["qa_citation_check"]
        print(f"\n{'=' * 70}")
        print("QA CITATION CHECK (Lab5 cross-check)")
        print(f"{'=' * 70}")
        print(f"  Checked: {qa['qa_pairs_checked']}, OK: {qa['qa_pairs_citation_ok']}")
        if qa["qa_pairs_citation_mismatches"]:
            print("  Mismatches:")
            for m in qa["qa_pairs_citation_mismatches"]:
                print(f"    - {m['question']}: cited={m['cited_pages']} actual={m['actual_pages']}")


if __name__ == "__main__":
    args = sys.argv[1:]
    qa_csv_path = None
    page_mapping_path = None
    output_dir = "outputs"
    program = "DSBA"
    plan = "no_coop"

    for flag, attr in [("--qa", "qa_csv_path"), ("--page-mapping", "page_mapping_path"), ("--output-dir", "output_dir"), ("--program", "program"), ("--plan", "plan")]:
        if flag in args:
            i = args.index(flag)
            val = args[i + 1]
            del args[i : i + 2]
            if attr == "qa_csv_path":       qa_csv_path = val
            elif attr == "page_mapping_path": page_mapping_path = val
            elif attr == "output_dir":      output_dir = val
            elif attr == "program":         program = val
            elif attr == "plan":            plan = val

    if len(args) < 2:
        print("Usage: python -m ocr_system.evaluate_all_levels <ocr_json> <ground_truth_json> [...] "
              "[--qa <qa_csv>] [--page-mapping <csv>] [--program DSBA|AIT] [--plan no_coop|coop] [--output-dir <dir>]")
        sys.exit(1)

    ocr_json_path = args[0]
    ground_truth_paths = args[1:]

    report = run(ocr_json_path, ground_truth_paths, qa_csv_path, page_mapping_path, program, plan)
    print_report(report)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{program.lower()}_{plan}_evaluation_all_levels.json" if plan else f"{program.lower()}_evaluation_all_levels.json"
    out_path = out_dir / filename
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nFull report saved to: {out_path.resolve()}")