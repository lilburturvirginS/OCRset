"""Map ground-truth course codes to the page number where they were found in
an OCR'd curriculum book, and export the result as CSV.

This answers the Lab5 deliverable: "ไฟล์ csv บอกว่า ground truth ชื่ออะไร
หลักสูตรไหน เอาข้อมูลมาจากเล่มหลักสูตรหน้าไหนบ้าง" -- for each ground truth
file, which program/plan it belongs to, and which page(s) of the OCR'd
curriculum book its data actually came from.

Only works for ground-truth files that key courses by `code` (an exact,
unambiguous join key). Rule/regulation ground truth (values without a course
code) needs a different, text-matching based approach -- see
rules_page_mapping.py (not implemented here).
"""

import csv
import json
from pathlib import Path
from typing import Any

from .curriculum_extraction import extract_curriculum_from_file


def build_code_page_index(ocr_json_path: str | Path, program: str = "DSBA", plan: str = "coop") -> dict[str, dict[str, Any]]:
    """Extract every course occurrence from the OCR JSON and, for each code,
    keep the "best" occurrence: the first one that has both name_en and
    credits populated (falling back to the first occurrence found at all if
    none are fully populated), along with the page it was found on.
    """
    extracted = extract_curriculum_from_file(ocr_json_path, program=program, plan=plan)

    best_by_code: dict[str, dict[str, Any]] = {}
    for course in extracted["courses"]:
        code = course.get("code")
        if not isinstance(code, str) or not code.isdigit():
            continue
        is_good = bool(course.get("name_en")) and bool(course.get("credits"))
        if code not in best_by_code:
            best_by_code[code] = course
            continue
        existing = best_by_code[code]
        existing_good = bool(existing.get("name_en")) and bool(existing.get("credits"))
        if is_good and not existing_good:
            best_by_code[code] = course

    return best_by_code


def map_ground_truth_files_to_pages(
    ocr_json_path: str | Path,
    ground_truth_paths: list[str | Path],
    output_dir: str | Path,
    program: str = "DSBA",
    plan: str = "coop",
) -> tuple[Path, Path]:
    """Map every course-code-based ground truth file against the OCR JSON and
    write two CSVs to output_dir:
      - page_mapping.csv          (one row per ground-truth course)
      - page_mapping_summary.csv  (one row per ground-truth file)
    Returns (detail_csv_path, summary_csv_path).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    code_page_index = build_code_page_index(ocr_json_path, program=program, plan=plan)

    detail_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for gt_path in ground_truth_paths:
        gt_path = Path(gt_path)
        with gt_path.open("r", encoding="utf-8") as f:
            gt = json.load(f)

        gt_program = gt.get("program", "ALL (General Education)")
        gt_plan = gt.get("plan", "-")
        total = 0
        matched = 0
        pages_hit: set[int] = set()

        for course in gt.get("courses", []):
            code = course.get("code")
            if not isinstance(code, str) or not code.isdigit():
                continue
            total += 1
            match = code_page_index.get(code)
            page = match["page"] if match else None
            if page is not None:
                matched += 1
                pages_hit.add(page)
            detail_rows.append(
                {
                    "ground_truth_file": gt_path.name,
                    "program": gt_program,
                    "plan": gt_plan,
                    "code": code,
                    "name_th": course.get("name_th"),
                    "page_found": page,
                    "matched": page is not None,
                }
            )

        summary_rows.append(
            {
                "ground_truth_file": gt_path.name,
                "program": gt_program,
                "plan": gt_plan,
                "total_courses": total,
                "matched_courses": matched,
                "match_rate": f"{matched / total * 100:.1f}%" if total else "-",
                "page_range_in_book": f"{min(pages_hit)}-{max(pages_hit)}" if pages_hit else "-",
            }
        )

    detail_path = output_dir / "page_mapping.csv"
    summary_path = output_dir / "page_mapping_summary.csv"

    with detail_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["ground_truth_file", "program", "plan", "code", "name_th", "page_found", "matched"]
        )
        writer.writeheader()
        writer.writerows(detail_rows)

    with summary_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "ground_truth_file",
                "program",
                "plan",
                "total_courses",
                "matched_courses",
                "match_rate",
                "page_range_in_book",
            ],
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    return detail_path, summary_path
