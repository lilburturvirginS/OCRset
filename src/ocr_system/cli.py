import argparse
import json
from dataclasses import asdict
from pathlib import Path
from rich import print
from .config import OCRConfig
from .pipeline import run_ocr
from .evaluation import evaluate_from_files
from .field_extraction import extract_common_fields
from .curriculum_extraction import extract_curriculum_from_file
from .evaluate_curriculum import evaluate_curriculum_from_files
from .page_mapping import map_ground_truth_files_to_pages
from .utils.io import save_json


def parse_args():
    parser = argparse.ArgumentParser(description="Thai-English OCR system")
    sub = parser.add_subparsers(dest="command", required=True)

    ocr = sub.add_parser("ocr", help="Run OCR on image or PDF")
    ocr.add_argument("input_path")
    ocr.add_argument("--output-dir", default="outputs")
    ocr.add_argument("--engine", choices=["paddle", "tesseract", "trocr", "ensemble"], default="ensemble")
    ocr.add_argument("--languages", default="tha+eng", help="Tesseract languages, e.g. tha+eng")
    ocr.add_argument("--paddle-lang", default="th", help="PaddleOCR language, e.g. th or en")
    ocr.add_argument("--dpi", type=int, default=300)
    ocr.add_argument("--no-preprocess", action="store_true")
    ocr.add_argument("--no-deskew", action="store_true")
    ocr.add_argument("--save-debug-images", action="store_true")
    ocr.add_argument("--min-confidence", type=float, default=0.0)
    ocr.add_argument("--device", default="cpu")

    ev = sub.add_parser("evaluate", help="Evaluate OCR JSON against ground truth JSON (CER/WER)")
    ev.add_argument("ground_truth_json")
    ev.add_argument("prediction_json")
    ev.add_argument("--output", default="outputs/evaluation_result.json")

    curr = sub.add_parser(
        "curriculum",
        help="Extract structured course data from an OCR JSON, optionally evaluate against curriculum ground truth",
    )
    curr.add_argument("ocr_json", help="Path to *_ocr.json produced by the 'ocr' command")
    curr.add_argument("--ground-truth", default=None, help="Path to curriculum ground truth JSON (e.g. DSBA_academic_plan_coop.json). If omitted, only extraction runs.")
    curr.add_argument("--output-dir", default="outputs")
    curr.add_argument("--program", default=None, help="Program name: IT, DSBA, or AIT. If omitted, auto-detected from OCR text.")
    curr.add_argument("--plan", default="no_coop")

    mp = sub.add_parser(
        "map-pages",
        help="Map one or more course-based ground truth JSON files to the OCR page each course was found on, output as CSV",
    )
    mp.add_argument("ocr_json", help="Path to *_ocr.json produced by the 'ocr' command")
    mp.add_argument(
        "--ground-truth",
        nargs="+",
        required=True,
        help="One or more ground truth JSON files (e.g. DSBA_academic_plan_coop.json DSBA_academic_plan_no_coop.json general_education_ground_truth.json)",
    )
    mp.add_argument("--output-dir", default="outputs")
    mp.add_argument("--program", default="DSBA")
    mp.add_argument("--plan", default="coop")

    return parser.parse_args()


def main():
    args = parse_args()

    if args.command == "ocr":
        output_dir = Path(args.output_dir)
        config = OCRConfig(
            input_path=Path(args.input_path),
            output_dir=output_dir,
            page_image_dir=output_dir / "pages",
            engine=args.engine,
            languages=args.languages,
            paddle_lang=args.paddle_lang,
            dpi=args.dpi,
            preprocess=not args.no_preprocess,
            deskew=not args.no_deskew,
            save_debug_images=args.save_debug_images,
            min_confidence=args.min_confidence,
            device=args.device,
        )
        result = run_ocr(config)
        fields = extract_common_fields(result.text)
        field_path = output_dir / f"{Path(args.input_path).stem}_fields.json"
        save_json(fields, field_path)
        print(f"[green]OCR done[/green]: {output_dir}")
        print(f"Extracted fields: {json.dumps(fields, ensure_ascii=False, indent=2)}")

    elif args.command == "evaluate":
        result = evaluate_from_files(args.ground_truth_json, args.prediction_json)
        save_json(result, args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "curriculum":
        output_dir = Path(args.output_dir)
        stem = Path(args.ocr_json).stem.replace("_ocr", "")
        plan_suffix = f"_{args.plan}"  # _coop or _no_coop

        # Step 1: extract structured courses from the OCR JSON.
        extracted = extract_curriculum_from_file(
            args.ocr_json,
            program=args.program,
            plan=args.plan,
        )
        courses_path = output_dir / f"{stem}_courses{plan_suffix}.json"
        save_json(extracted, courses_path)
        print(f"[green]Extraction done[/green]: {len(extracted['courses'])} courses -> {courses_path}")

        # Step 2 (optional): evaluate against curriculum ground truth.
        if args.ground_truth:
            eval_path = output_dir / f"{stem}_curriculum_evaluation{plan_suffix}.json"
            result = evaluate_curriculum_from_files(courses_path, args.ground_truth, eval_path)
            print(f"[green]Evaluation done[/green]: {eval_path}")
            print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
        else:
            print("[yellow]No --ground-truth given, skipping evaluation.[/yellow]")

    elif args.command == "map-pages":
        detail_path, summary_path = map_ground_truth_files_to_pages(
            args.ocr_json,
            args.ground_truth,
            args.output_dir,
            program=args.program,
            plan=args.plan,
        )
        print(f"[green]Page mapping done[/green]")
        print(f"Detail CSV:  {detail_path}")
        print(f"Summary CSV: {summary_path}")


if __name__ == "__main__":
    main()