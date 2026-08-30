#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import json
import re
import csv
from pathlib import Path

# Setup paths relative to script location
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR / "src"))

from ocr_system.evaluate_all_levels import run, print_report

EVAL_CONFIGS = [
    {
        "name": "DSBA - Cooperative Education (Coop)",
        "ocr_json": "outputs/dsba_curriculum_ocr.json",
        "gt_files": ["data/ground_truth/DSBA_academic_plan_coop.json"],
        "page_mapping": "data/ground_truth/dsba_coop_course_page_mapping.csv",
        "program": "DSBA",
        "plan": "coop"
    },
    {
        "name": "DSBA - Regular Plan (No Coop)",
        "ocr_json": "outputs/dsba_curriculum_ocr.json",
        "gt_files": ["data/ground_truth/DSBA_academic_plan_no_coop.json"],
        "page_mapping": "data/ground_truth/dsba_no_coop_course_page_mapping.csv",
        "program": "DSBA",
        "plan": "no_coop"
    },
    {
        "name": "AIT - Regular Plan (No Coop)",
        "ocr_json": "outputs/AIT_curriculum_ocr.json",
        "gt_files": ["data/ground_truth/AIT_academic_plan.json"],
        "page_mapping": "data/ground_truth/ait_course_page_mapping.csv",
        "program": "AIT",
        "plan": "no_coop"
    },
    {
        "name": "IT - Cooperative Education (Coop)",
        "ocr_json": "outputs/IT_curriculum_ocr.json",
        "gt_files": ["data/ground_truth/IT_academic_plan_coop.json"],
        "page_mapping": "data/ground_truth/it_coop_course_page_mapping.csv",
        "program": "IT",
        "plan": "coop"
    },
    {
        "name": "IT - Regular Plan (No Coop)",
        "ocr_json": "outputs/IT_curriculum_ocr.json",
        "gt_files": ["data/ground_truth/IT_academic_plan_no_coop.json"],
        "page_mapping": "data/ground_truth/it_no_coop_course_page_mapping.csv",
        "program": "IT",
        "plan": "no_coop"
    }
]

def main():
    print("=" * 80)
    print("                    STARTING LAB 6 COMPREHENSIVE EVALUATION")
    print("=" * 80)
    
    reports = []
    
    for cfg in EVAL_CONFIGS:
        print("\n" + "#" * 80)
        print(f" RUNNING EVALUATION FOR: {cfg['name']}")
        print("#" * 80)
        
        ocr_path = BASE_DIR / cfg["ocr_json"]
        if not ocr_path.exists():
            print(f"Error: OCR file not found: {ocr_path}")
            continue
            
        gts = [str(BASE_DIR / p) for p in cfg["gt_files"] if (BASE_DIR / p).exists()]
        if not gts:
            print(f"Error: No Ground Truth files found from list: {cfg['gt_files']}")
            continue
            
        map_path = cfg["page_mapping"]
        if map_path and (BASE_DIR / map_path).exists():
            map_path = str(BASE_DIR / map_path)
        else:
            print(f"Warning: Page mapping CSV not found: {map_path}. Using OCR fallback.")
            map_path = None
            
        try:
            report = run(
                ocr_json_path=str(ocr_path),
                ground_truth_paths=gts,
                qa_csv_path=str(BASE_DIR / "data/ground_truth/qa_pairs.csv") if (BASE_DIR / "data/ground_truth/qa_pairs.csv").exists() else None,
                page_mapping_path=map_path,
                program=cfg["program"],
                plan=cfg["plan"]
            )
            print_report(report)
            reports.append((cfg["name"], report))
        except Exception as e:
            print(f"Failed to evaluate {cfg['name']}: {e}")
            import traceback
            traceback.print_exc()

    # Save summary report
    output_report_path = BASE_DIR / "outputs" / "lab6_final_report.txt"
    output_report_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_report_path, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("                 LAB 6 FINAL EVALUATION REPORT SUMMARY\n")
        f.write("=" * 80 + "\n\n")
        
        for name, r in reports:
            f.write(f"Scenarios: {name}\n")
            for gt_file, levels in r["ground_truth_files"].items():
                f.write(f"  Ground Truth File: {gt_file}\n")
                f.write(f"  Field Accuracy Summary:\n")
                for field, stats in levels["field_level"]["per_field"].items():
                    acc = f"{stats['accuracy']*100:.2f}%" if stats['accuracy'] is not None else "N/A"
                    f.write(f"    - {field:12s}: {acc:>8s} ({stats['correct']}/{stats['checked']})\n")
                
                pl = levels["page_level"]
                rate = f"{pl['page_localization_rate']*100:.2f}%" if pl['page_localization_rate'] is not None else "N/A"
                f.write(f"  Page Localization Rate: {rate} ({pl['found_by_code'] + pl['found_by_name_only']}/{pl['total_gt_courses']})\n")
                f.write(f"  Distinct Pages Used   : {pl['distinct_pages_used']}\n\n")
            f.write("-" * 80 + "\n\n")
            
    print("\n" + "=" * 80)
    print(f"LAB 6 RUN COMPLETED. Summary saved to: {output_report_path.resolve()}")
    print("=" * 80)

if __name__ == "__main__":
    main()
