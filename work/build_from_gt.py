#!/usr/bin/env python3
"""
build_from_gt.py — สร้าง curriculum.json ที่สมบูรณ์จาก ground truth
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent


def credit_parts(value):
    text = str(value or "").strip()
    # ถ้ามีหลายแบบ (เช่น "3(3-0-6) หรือ 3(2-2-5)") ใช้อันแรก
    m = re.search(r"(\d+)\s*\(\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)\s*\)", text)
    if m:
        return tuple(map(int, m.groups()))
    m = re.search(r"\d+", text)
    if not m:
        return (0, None, None, None)
    return int(m.group()), None, None, None


gt_path = ROOT / "data" / "ground_truth_C" / "DSBA_academic_plan_coop.json"
gt = json.loads(gt_path.read_text(encoding="utf-8"))

courses = {}
plan = []
prerequisites = []
seen_plan = set()
alt_counter = 0

for i, c in enumerate(gt["courses"]):
    raw_code = str(c.get("code", "")).strip()
    # แตกรหัสที่มีตัวเลข 8 หลักออก (handle "06026259 หรือ 06026260")
    codes = re.findall(r"(?<!\d)\d{8}(?!\d)", raw_code)

    if not codes:
        # wildcard เช่น 06026xxx, xxxxxxxx — ข้ามได้
        print(f"  ข้าม wildcard [{i}]: {raw_code!r}")
        continue

    cr, lh, labh, selfh = credit_parts(c.get("credits"))

    # สร้าง course entries
    for code in codes:
        if code not in courses:
            courses[code] = {
                "code": code,
                "name_th": str(c.get("name_th") or code).strip(),
                "name_en": (str(c["name_en"]).replace("\n", " ").strip()
                            if c.get("name_en") else None),
                "credits": cr,
                "lecture_h": lh,
                "lab_h": labh,
                "self_h": selfh,
                "description_th": None
            }

    # สร้าง plan items
    try:
        year = int(c.get("year") or 0)
        semester = int(c.get("semester") or 0)
    except (TypeError, ValueError):
        year = semester = 0

    if 1 <= year <= 8 and 1 <= semester <= 3:
        # ถ้ามีหลายรหัส ใช้ alt_group
        alt_group = None
        if len(codes) > 1:
            alt_counter += 1
            alt_group = f"alt_y{year}s{semester}_{alt_counter}"

        notes = [x for x in [c.get("category"), c.get("type"), c.get("note")] if x]
        note = " | ".join(str(x) for x in notes) or None

        for code in codes:
            key = (year, semester, code, alt_group)
            if key not in seen_plan:
                plan.append({
                    "year": year,
                    "semester": semester,
                    "code": code,
                    "credits": cr,
                    "alt_group": alt_group,
                    "note": note
                })
                seen_plan.add(key)
    else:
        print(f"  ข้าม flexible [{i}]: {raw_code!r} y={year} s={semester}")

    # prerequisite
    prereq = str(c.get("prerequisite") or "").strip()
    pre_codes = re.findall(r"(?<!\d)\d{8}(?!\d)", prereq)
    for code in codes:
        for req in pre_codes:
            if req != code:
                prerequisites.append({"code": code, "requires": req, "kind": "pre"})

# สรุป
print(f"\ncourses: {len(courses)}")
print(f"plan: {len(plan)}")
print(f"prerequisites: {len(prerequisites)}")

total = 0
sem_credits = {}
for p in plan:
    k = (p["year"], p["semester"])
    if k not in sem_credits:
        sem_credits[k] = 0
    if p.get("alt_group") is None:
        sem_credits[k] += p["credits"]
        total += p["credits"]

# นับ alt_group ครั้งเดียว
from collections import defaultdict
alt_groups = defaultdict(list)
for p in plan:
    if p.get("alt_group"):
        alt_groups[(p["year"], p["semester"], p["alt_group"])].append(p["credits"])
for (y, s, ag), crs in alt_groups.items():
    min_cr = min(crs)
    sem_credits[(y, s)] = sem_credits.get((y, s), 0) + min_cr
    total += min_cr

for k in sorted(sem_credits):
    print(f"  ปี {k[0]}/เทอม {k[1]}: {sem_credits[k]} หน่วยกิต")
print(f"รวม credits: {total}")

result = {
    "program": {
        "program_id": "DSBA-coop",
        "name_th": "วิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ (สหกิจศึกษา)",
        "name_en": "Data Science and Business Analytics (Cooperative Education)",
        "degree": "วิทยาศาสตรบัณฑิต",
        "total_credits": 135,
        "years": 4
    },
    "courses": list(courses.values()),
    "plan": plan,
    "prerequisites": prerequisites
}

out = ROOT / "work" / "lab8b_run" / "curriculum.json"
out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nเขียน {out}")
