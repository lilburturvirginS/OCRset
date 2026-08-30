import json

# Load all GT files and show note values for courses with notes
gt_files = {
    "IT_no_coop": "data/ground_truth/IT_academic_plan_no_coop.json",
    "IT_coop": "data/ground_truth/IT_academic_plan_coop.json",
    "DSBA_no_coop": "data/ground_truth/DSBA_academic_plan_no_coop.json",
    "DSBA_coop": "data/ground_truth/DSBA_academic_plan_coop.json",
    "AIT": "data/ground_truth/AIT_academic_plan.json",
}

out_files = {
    "IT_no_coop": "outputs/IT_curriculum_courses_no_coop.json",
    "IT_coop": "outputs/IT_curriculum_courses_coop.json",
    "DSBA_no_coop": "outputs/dsba_curriculum_courses_no_coop.json",
    "DSBA_coop": "outputs/dsba_curriculum_courses_coop.json",
    "AIT": "outputs/AIT_curriculum_courses_no_coop.json",
}

print("=== GT note values (all courses with notes) ===")
for key in gt_files:
    gt = json.load(open(gt_files[key], encoding="utf-8"))
    gt_courses = {c["code"]: c for c in gt.get("courses", []) if c.get("code")}
    gt_with_note = {code: c for code, c in gt_courses.items() if c.get("note")}
    print(f"\n[{key}] ({len(gt_with_note)} courses with note):")
    for code, c in gt_with_note.items():
        note_val = c["note"]
        print(f"  {code}: note={note_val}")

print("\n\n=== Output note values (all courses with notes or None) ===")
for key in out_files:
    out = json.load(open(out_files[key], encoding="utf-8"))
    out_courses = {c["code"]: c for c in out.get("courses", []) if c.get("code")}
    gt = json.load(open(gt_files[key], encoding="utf-8"))
    gt_courses = {c["code"]: c for c in gt.get("courses", []) if c.get("code")}
    gt_with_note = {code: c for code, c in gt_courses.items() if c.get("note")}
    
    print(f"\n[{key}] Checking {len(gt_with_note)} GT courses with notes:")
    for code, gt_c in gt_with_note.items():
        out_c = out_courses.get(code)
        gt_note = gt_c["note"]
        out_note = out_c.get("note") if out_c else "NOT FOUND"
        match = "OK" if gt_note == out_note else "MISMATCH"
        print(f"  {code}: [{match}] GT={gt_note!r} | OUT={out_note!r}")
