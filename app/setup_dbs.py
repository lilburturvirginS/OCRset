#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
setup_dbs.py — สร้างฐานข้อมูล SQLite สำหรับทุกสาขาที่มี
รันครั้งเดียว แล้วแอพจะใช้ไฟล์ .db ที่สร้างไว้

python app/setup_dbs.py
"""

import json
import re
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ─── DDL เหมือนกับ lab8b_curriculum_db.py ───────────────────────────────
DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS program (
    program_id    TEXT PRIMARY KEY,
    name_th       TEXT NOT NULL,
    name_en       TEXT,
    degree        TEXT,
    total_credits INTEGER NOT NULL,
    years         INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS course (
    code           TEXT PRIMARY KEY,
    name_th        TEXT NOT NULL,
    name_en        TEXT,
    credits        INTEGER NOT NULL,
    lecture_h      INTEGER,
    lab_h          INTEGER,
    self_h         INTEGER,
    description_th TEXT
);

CREATE TABLE IF NOT EXISTS plan_item (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id TEXT NOT NULL REFERENCES program(program_id),
    year       INTEGER NOT NULL,
    semester   INTEGER NOT NULL,
    code       TEXT NOT NULL,
    credits    INTEGER NOT NULL,
    alt_group  TEXT,
    note       TEXT
);

CREATE TABLE IF NOT EXISTS prerequisite (
    code     TEXT NOT NULL,
    requires TEXT NOT NULL,
    kind     TEXT NOT NULL DEFAULT 'pre',
    PRIMARY KEY (code, requires, kind)
);

CREATE INDEX IF NOT EXISTS ix_plan_sem ON plan_item(year, semester);
CREATE INDEX IF NOT EXISTS ix_plan_code ON plan_item(code);

CREATE VIEW IF NOT EXISTS v_plan AS
SELECT p.id, p.year, p.semester, p.code, c.name_th, c.name_en,
       p.credits, p.alt_group, p.note
FROM plan_item p
LEFT JOIN course c ON c.code = p.code;

CREATE VIEW IF NOT EXISTS v_semester_credits AS
SELECT year, semester, SUM(credits) AS credits, COUNT(*) AS n_courses
FROM (
    SELECT year, semester,
           COALESCE(alt_group, 'x' || id) AS grp,
           MIN(credits) AS credits
    FROM plan_item
    GROUP BY year, semester, COALESCE(alt_group, 'x' || id)
)
GROUP BY year, semester;
"""


def _credit_int(value) -> int:
    """แปลง '3(3-0-6)' หรือ '3' เป็น int"""
    text = str(value or "").strip()
    m = re.search(r"(\d+)\s*\(", text)
    if m:
        return int(m.group(1))
    m = re.search(r"\d+", text)
    return int(m.group()) if m else 0


def _credit_parts(value):
    """คืน (total, lecture, lab, self) หรือ None"""
    text = str(value or "").strip()
    m = re.search(r"(\d+)\s*\(\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)\s*\)", text)
    if m:
        return tuple(map(int, m.groups()))
    c = _credit_int(text)
    return c, None, None, None


def build_db_from_courses_json(
    json_path: Path,
    db_path: Path,
    program_id: str,
    name_th: str,
    name_en: str,
    total_credits: int,
    years: int,
):
    """สร้าง DB จาก courses JSON (รูปแบบ outputs/*.json ของโปรเจกต์)"""
    data = json.loads(json_path.read_text(encoding="utf-8"))
    courses_raw = data.get("courses", [])

    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    conn.executescript(DDL)

    conn.execute(
        "INSERT OR REPLACE INTO program VALUES (?,?,?,?,?,?)",
        (program_id, name_th, name_en, "ปริญญาตรี", total_credits, years),
    )

    code_re = re.compile(r"^\d{8}$")
    seen_codes: set[str] = set()
    plan_items = []
    prereqs = []

    for idx, src in enumerate(courses_raw):
        raw_code = str(src.get("code") or "").strip()
        if not code_re.match(raw_code):
            continue

        cr, lec, lab, self_h = _credit_parts(src.get("credits"))
        if cr == 0:
            continue

        name_th_c = str(src.get("name_th") or raw_code).strip()
        name_en_c = src.get("name_en")
        if name_en_c:
            name_en_c = str(name_en_c).replace("\n", " ").strip()

        if raw_code not in seen_codes:
            conn.execute(
                "INSERT OR IGNORE INTO course VALUES (?,?,?,?,?,?,?,?)",
                (raw_code, name_th_c, name_en_c, cr, lec, lab, self_h, None),
            )
            seen_codes.add(raw_code)

        try:
            year = int(src.get("year") or 0)
            semester = int(src.get("semester") or 0)
        except (TypeError, ValueError):
            year = semester = 0

        if 1 <= year <= 8 and 1 <= semester <= 3:
            notes = [
                str(x).strip()
                for x in (src.get("category"), src.get("type"), src.get("note"))
                if x
            ]
            note = " | ".join(notes) or None
            plan_items.append((program_id, year, semester, raw_code, cr, None, note))

        # prerequisite
        pre = str(src.get("prerequisite") or "").strip()
        pre_codes = re.findall(r"(?<!\d)\d{8}(?!\d)", pre)
        for req in pre_codes:
            if req != raw_code:
                prereqs.append((raw_code, req, "pre"))

    conn.executemany(
        "INSERT INTO plan_item (program_id,year,semester,code,credits,alt_group,note)"
        " VALUES (?,?,?,?,?,?,?)",
        plan_items,
    )
    for p in prereqs:
        try:
            conn.execute("INSERT OR IGNORE INTO prerequisite VALUES (?,?,?)", p)
        except sqlite3.IntegrityError:
            pass

    conn.commit()

    counts = {
        t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("program", "course", "plan_item", "prerequisite")
    }
    conn.close()
    print(f"  ✓ {db_path.name}")
    for t, c in counts.items():
        print(f"      {t:<14} {c:>4} แถว")
    return counts


def copy_existing_db(src: Path, dst: Path):
    shutil.copy2(src, dst)
    conn = sqlite3.connect(str(dst))
    counts = {
        t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("program", "course", "plan_item", "prerequisite")
    }
    conn.close()
    print(f"  ✓ {dst.name}  (copied from {src.name})")
    for t, c in counts.items():
        print(f"      {t:<14} {c:>4} แถว")
    return counts


PROGRAMS = [
    {
        "id": "dsba_coop",
        "name_th": "วิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ (สหกิจศึกษา)",
        "name_en": "Data Science and Business Analytics (Co-op)",
        "total_credits": 135,
        "years": 4,
        "source": "existing_db",  # ใช้ DB ที่มีอยู่แล้ว
        "existing_db": ROOT / "work" / "lab8b_run" / "curriculum.db",
        "db_file": "dsba_coop.db",
    },
    {
        "id": "dsba_nocoop",
        "name_th": "วิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ",
        "name_en": "Data Science and Business Analytics",
        "total_credits": 135,
        "years": 4,
        "source": "json",
        "json": ROOT / "outputs" / "dsba_curriculum_courses_no_coop.json",
        "db_file": "dsba_nocoop.db",
    },
    {
        "id": "ait",
        "name_th": "เทคโนโลยีสารสนเทศ (นานาชาติ)",
        "name_en": "Applied Information Technology",
        "total_credits": 120,
        "years": 4,
        "source": "json",
        "json": ROOT / "outputs" / "AIT_curriculum_courses_no_coop.json",
        "db_file": "ait.db",
    },
    {
        "id": "it_coop",
        "name_th": "เทคโนโลยีสารสนเทศ (สหกิจศึกษา)",
        "name_en": "Information Technology (Co-op)",
        "total_credits": 133,
        "years": 4,
        "source": "json",
        "json": ROOT / "outputs" / "IT_curriculum_courses_coop.json",
        "db_file": "it_coop.db",
    },
    {
        "id": "it_nocoop",
        "name_th": "เทคโนโลยีสารสนเทศ",
        "name_en": "Information Technology",
        "total_credits": 133,
        "years": 4,
        "source": "json",
        "json": ROOT / "outputs" / "IT_curriculum_courses_no_coop.json",
        "db_file": "it_nocoop.db",
    },
]


def main():
    print("=" * 60)
    print("  สร้างฐานข้อมูลสำหรับทุกสาขา")
    print("=" * 60)

    all_ok = True
    for prog in PROGRAMS:
        print(f"\n→ {prog['name_th']} ({prog['id']})")
        db_path = DATA_DIR / prog["db_file"]

        try:
            if prog["source"] == "existing_db":
                src = prog["existing_db"]
                if not src.exists():
                    print(f"  ✗ ไม่พบ DB ต้นทาง: {src}")
                    all_ok = False
                    continue
                copy_existing_db(src, db_path)
            else:
                json_path = prog["json"]
                if not json_path.exists():
                    print(f"  ✗ ไม่พบ JSON: {json_path}")
                    all_ok = False
                    continue
                build_db_from_courses_json(
                    json_path, db_path,
                    prog["id"], prog["name_th"], prog["name_en"],
                    prog["total_credits"], prog["years"],
                )
        except Exception as e:
            print(f"  ✗ ล้มเหลว: {e}")
            import traceback; traceback.print_exc()
            all_ok = False

    print("\n" + "=" * 60)
    if all_ok:
        print("  ✅ สร้างฐานข้อมูลครบทุกสาขาแล้ว")
        print(f"  ไฟล์ .db อยู่ที่: {DATA_DIR}")
    else:
        print("  ⚠ มีบางสาขาที่สร้างไม่สำเร็จ ดูข้อผิดพลาดข้างต้น")
    print("=" * 60)


if __name__ == "__main__":
    main()
