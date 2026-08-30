"""
Evaluation for curriculum extraction results against ground truth.

Unlike evaluation.py (which measures CER/WER on plain OCR text), this module
evaluates *structured* extraction quality: given a list of extracted courses
(code, name_th, name_en, credits, ...) and a ground truth course list, it
reports:

  - recall: how many GT courses were found at all (matched by course code)
  - field accuracy: for matched courses, how often name_en / credits agree

This is necessary because the curriculum ground truth
(data/ground_truth/DSBA_academic_plan_coop.json) is a list of course records,
not a single block of text, so CER/WER does not apply directly.
"""

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass
class CurriculumEvaluationResult:
    gt_total: int
    matched: int
    missing: int
    recall: float
    name_en_agreement: float | None
    credits_agreement: float | None
    category_agreement: float | None
    type_agreement: float | None
    prerequisite_agreement: float | None
    missing_codes: list[str]
    mismatched_name_en: list[dict[str, Any]]
    mismatched_credits: list[dict[str, Any]]
    mismatched_category: list[dict[str, Any]]
    mismatched_type: list[dict[str, Any]]
    mismatched_prerequisite: list[dict[str, Any]]


def evaluate_curriculum(extracted: dict[str, Any], ground_truth: dict[str, Any]) -> CurriculumEvaluationResult:
    # Deduplicate GT courses (same logic as extracted) so that a course code
    # appearing multiple times in GT (e.g. 06016418 in two module groups)
    # is merged into one record and compared only once.
    gt_by_code = _merge_duplicate_courses(
        [c for c in ground_truth.get("courses", []) if _is_valid_code(c.get("code"))]
    )
    gt_courses = list(gt_by_code.values())
    extracted_by_code = _merge_duplicate_courses(extracted.get("courses", []))

    matched_courses = []
    missing_codes = []

    for gt_course in gt_courses:
        code = gt_course["code"]
        if code in extracted_by_code:
            matched_courses.append((gt_course, extracted_by_code[code]))
        else:
            missing_codes.append(code)

    name_en_matches = 0
    credits_matches = 0
    category_matches = 0
    type_matches = 0
    prerequisite_matches = 0
    mismatched_name_en = []
    mismatched_credits = []
    mismatched_category = []
    mismatched_type = []
    mismatched_prerequisite = []

    for gt_course, extracted_course in matched_courses:
        if gt_course.get("name_en") is not None:
            if _normalize_name(gt_course.get("name_en")) == _normalize_name(extracted_course.get("name_en")):
                name_en_matches += 1
            else:
                mismatched_name_en.append({
                    "code": gt_course["code"],
                    "expected": gt_course.get("name_en"),
                    "got": extracted_course.get("name_en"),
                })

        if gt_course.get("credits") is not None:
            if _normalize_credits(gt_course.get("credits")) == _normalize_credits(extracted_course.get("credits")):
                credits_matches += 1
            else:
                mismatched_credits.append({
                    "code": gt_course["code"],
                    "expected": gt_course.get("credits"),
                    "got": extracted_course.get("credits"),
                })

        if gt_course.get("category") is not None:
            if gt_course.get("category") == extracted_course.get("category"):
                category_matches += 1
            else:
                mismatched_category.append({
                    "code": gt_course["code"],
                    "expected": gt_course.get("category"),
                    "got": extracted_course.get("category"),
                })

        if gt_course.get("type") is not None:
            if gt_course.get("type") == extracted_course.get("type"):
                type_matches += 1
            else:
                mismatched_type.append({
                    "code": gt_course["code"],
                    "expected": gt_course.get("type"),
                    "got": extracted_course.get("type"),
                })

        if gt_course.get("prerequisite") is not None:
            if gt_course.get("prerequisite") == extracted_course.get("prerequisite"):
                prerequisite_matches += 1
            else:
                mismatched_prerequisite.append({
                    "code": gt_course["code"],
                    "expected": gt_course.get("prerequisite"),
                    "got": extracted_course.get("prerequisite"),
                })

    name_en_checked = sum(1 for gt_course, _ in matched_courses if gt_course.get("name_en") is not None)
    credits_checked = sum(1 for gt_course, _ in matched_courses if gt_course.get("credits") is not None)
    category_checked = sum(1 for gt_course, _ in matched_courses if gt_course.get("category") is not None)
    type_checked = sum(1 for gt_course, _ in matched_courses if gt_course.get("type") is not None)
    prerequisite_checked = sum(1 for gt_course, _ in matched_courses if gt_course.get("prerequisite") is not None)

    gt_total = len(gt_courses)
    matched = len(matched_courses)

    return CurriculumEvaluationResult(
        gt_total=gt_total,
        matched=matched,
        missing=len(missing_codes),
        recall=round(matched / gt_total, 4) if gt_total else 0.0,
        name_en_agreement=round(name_en_matches / name_en_checked, 4) if name_en_checked else None,
        credits_agreement=round(credits_matches / credits_checked, 4) if credits_checked else None,
        category_agreement=round(category_matches / category_checked, 4) if category_checked else None,
        type_agreement=round(type_matches / type_checked, 4) if type_checked else None,
        prerequisite_agreement=round(prerequisite_matches / prerequisite_checked, 4) if prerequisite_checked else None,
        missing_codes=missing_codes,
        mismatched_name_en=mismatched_name_en,
        mismatched_credits=mismatched_credits,
        mismatched_category=mismatched_category,
        mismatched_type=mismatched_type,
        mismatched_prerequisite=mismatched_prerequisite,
    )


def evaluate_curriculum_from_files(
    extracted_path: str | Path,
    ground_truth_path: str | Path,
    output_path: str | Path | None = None,
) -> CurriculumEvaluationResult:
    with Path(extracted_path).open("r", encoding="utf-8") as f:
        extracted = json.load(f)
    with Path(ground_truth_path).open("r", encoding="utf-8") as f:
        ground_truth = json.load(f)

    result = evaluate_curriculum(extracted, ground_truth)

    if output_path:
        with Path(output_path).open("w", encoding="utf-8") as f:
            json.dump(asdict(result), f, ensure_ascii=False, indent=2)

    return result


def _merge_duplicate_courses(courses: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Merge multiple occurrences of the same course code into one record.

    The same course code can legitimately appear more than once across a
    403-page institution-wide catalog (main curriculum table, elective
    listings, instructor teaching-load pages, index pages, ...). Some of
    those occurrences carry full data (name, credits) and some don't (e.g.
    a bare code in an index). Naively keeping "the last occurrence found"
    can silently overwrite a good record with an empty one. Instead, for
    each field we keep the first non-empty value we encounter across all
    occurrences of that code.
    """
    merged: dict[str, dict[str, Any]] = {}
    fields = ("name_th", "name_en", "credits", "year", "semester", "category", "type", "prerequisite")

    for course in courses:
        code = course.get("code")
        if not _is_valid_code(code):
            continue
        if code not in merged:
            merged[code] = dict(course)
            continue
        existing = merged[code]
        for field in fields:
            if not existing.get(field) and course.get(field):
                existing[field] = course[field]

    return merged


def _is_valid_code(code: Any) -> bool:
    return isinstance(code, str) and code.isdigit()


def _normalize_name(name: str | None) -> str:
    if not name:
        return ""
    return re.sub(r"\s+", " ", name).strip().upper()


def _normalize_credits(credits: str | None) -> str:
    if not credits:
        return ""
    return re.sub(r"\s+", "", credits)


def _fmt_pct(value: float | None) -> str:
    return f"{value * 100:.1f}%" if value is not None else "n/a (GT has no value for this field)"


def _print_summary(result: CurriculumEvaluationResult) -> None:
    print(f"GT courses (valid):     {result.gt_total}")
    print(f"Matched (found):        {result.matched} ({result.recall * 100:.1f}%)")
    print(f"Missing:                {result.missing}")
    print(f"name_en agreement:      {_fmt_pct(result.name_en_agreement)} (of matched)")
    print(f"credits agreement:      {_fmt_pct(result.credits_agreement)} (of matched)")
    print(f"category agreement:     {_fmt_pct(result.category_agreement)} (of matched)")
    print(f"type agreement:         {_fmt_pct(result.type_agreement)} (of matched)")
    print(f"prerequisite agreement: {_fmt_pct(result.prerequisite_agreement)} (of matched)")
    if result.missing_codes:
        print(f"Missing codes:          {result.missing_codes}")
    if result.mismatched_name_en:
        print(f"\nSample name_en mismatches:")
        for item in result.mismatched_name_en[:5]:
            print(f"  {item['code']}: expected={item['expected']!r} got={item['got']!r}")
    if result.mismatched_credits:
        print(f"\nSample credits mismatches:")
        for item in result.mismatched_credits[:5]:
            print(f"  {item['code']}: expected={item['expected']!r} got={item['got']!r}")
    if result.mismatched_category:
        print(f"\nSample category mismatches:")
        for item in result.mismatched_category[:5]:
            print(f"  {item['code']}: expected={item['expected']!r} got={item['got']!r}")
    if result.mismatched_type:
        print(f"\nSample type mismatches:")
        for item in result.mismatched_type[:5]:
            print(f"  {item['code']}: expected={item['expected']!r} got={item['got']!r}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate curriculum extraction against ground truth")
    parser.add_argument("extracted", help="Path to extracted courses JSON (from curriculum_extraction.py)")
    parser.add_argument("ground_truth", help="Path to ground truth JSON (e.g. DSBA_academic_plan_coop.json)")
    parser.add_argument("--output", default="outputs/curriculum_evaluation_result.json", help="Where to save the result JSON")
    args = parser.parse_args()

    result = evaluate_curriculum_from_files(args.extracted, args.ground_truth, args.output)
    _print_summary(result)
    print(f"\nSaved result to {args.output}")