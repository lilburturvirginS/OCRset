#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_model_benchmark.py — เปรียบเทียบประสิทธิภาพระหว่างโมเดล (qwen3:4b vs qwen2.5-coder:7b)
1. ทดสอบ Text-to-SQL บนชุดคำถาม 30 ข้อ (Lab 8B)
2. ทดสอบ Information Extraction บนหน้าตารางหลักสูตรจริง (Lab 7B)
3. วัดความเร็ว (Latency), VRAM, และความแม่นยำ (Accuracy)
"""

import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
DB_PATH = ROOT / "work" / "lab8b_run" / "curriculum.db"
GOLD_QUESTIONS_PATH = ROOT / "work" / "lab8b_run" / "gold_questions.json"


def check_gpu_vram() -> str:
    """อ่านปริมาณ VRAM ที่ใช้ปัจจุบันจาก nvidia-smi"""
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, check=True
        )
        used, total = res.stdout.strip().split(",")
        return f"{used.strip()} / {total.strip()} MB"
    except Exception:
        return "N/A"


def run_text_to_sql_benchmark(model_name: str) -> dict:
    """รันคำถาม 30 ข้อด้วยโมเดลที่กำหนด"""
    print(f"\n==========================================================================")
    print(f"  [1/2] เริ่มทดสอบ Text-to-SQL ด้วยโมเดล: {model_name}")
    print(f"==========================================================================")

    # Import functions จาก lab8b_curriculum_db
    from ocr_system.lab8b_curriculum_db import open_db, ask, score_one

    conn = open_db(str(DB_PATH), readonly=True)
    questions = json.loads(GOLD_QUESTIONS_PATH.read_text(encoding="utf-8"))

    # ตั้งค่าโมเดลผ่าน environment หรือ monkeypatch
    import ocr_system.lab8b_curriculum_db as lab8b_mod
    lab8b_mod.MODEL_TEXT = model_name

    n_ok = 0
    n_sql_ok = 0
    times = []
    results = []

    for i, q in enumerate(questions, 1):
        t0 = time.time()
        got = ask(conn, q["question"], verbose=False)
        dur = round(time.time() - t0, 2)
        times.append(dur)

        ok, why = score_one(q["expect"], got)
        sql_ok = got["error"] is None
        n_ok += int(ok)
        n_sql_ok += int(sql_ok)

        status_str = "ถูก" if ok else "ผิด"
        print(f"  {i:>2}. [{status_str}] {q['question'][:40]:<42} ({dur:.1f}s) -> {why[:25]}")
        results.append({
            "id": q["id"],
            "question": q["question"],
            "sql": got["sql"],
            "answer": got["answer"],
            "correct": ok,
            "sql_ok": sql_ok,
            "seconds": dur
        })

    conn.close()

    total_q = len(questions)
    avg_time = round(sum(times) / len(times), 2)
    sql_rate = round(n_sql_ok / total_q * 100, 1)
    ans_acc = round(n_ok / total_q * 100, 1)

    print("-" * 74)
    print(f"  โมเดล {model_name}:")
    print(f"    SQL Syntax ผ่าน:  {n_sql_ok}/{total_q} ({sql_rate}%)")
    print(f"    คำตอบถูกต้อง:     {n_ok}/{total_q} ({ans_acc}%)")
    print(f"    เวลาเฉลี่ย/ข้อ:    {avg_time} วินาที")
    print(f"    VRAM ใช้งาน:       {check_gpu_vram()}")
    print("-" * 74)

    return {
        "model": model_name,
        "total_questions": total_q,
        "sql_pass_count": n_sql_ok,
        "sql_pass_rate": sql_rate,
        "answer_correct_count": n_ok,
        "answer_accuracy": ans_acc,
        "avg_seconds_per_query": avg_time,
        "total_seconds": round(sum(times), 1),
        "vram": check_gpu_vram(),
        "details": results
    }


def run_extraction_benchmark(model_name: str) -> dict:
    """ทดสอบการสกัดตารางหลักสูตร 1 หน้า (DSBA หน้า 30)"""
    print(f"\n==========================================================================")
    print(f"  [2/2] เริ่มทดสอบ Information Extraction ด้วยโมเดล: {model_name}")
    print(f"==========================================================================")

    from ocr_system.lab7b_curriculum import (
        ollama_chat, EXTRACT_PROMPT, SYSTEM_PROMPT, COURSE_SCHEMA, parse_json
    )

    sample_page_text = """
ปีที่ 1 ภาคการศึกษาที่ 1
รหัสวิชา ชื่อวิชา หน่วยกิต (บรรยาย-ปฏิบัติ-ศึกษาด้วยตนเอง)
06026200 แคลคูลัส 1
CALCULUS 1
3 (3-0-6)
06026202 พีชคณิตเชิงเส้น
LINEAR ALGEBRA
3 (3-0-6)
06066101 พื้นฐานทางธุรกิจสำหรับเทคโนโลยีสารสนเทศ
BUSINESS FUNDAMENTALS FOR INFORMATION TECHNOLOGY
3 (3-0-6)
06066303 การแก้ปัญหาและการโปรแกรมคอมพิวเตอร์
PROBLEM SOLVING AND COMPUTER PROGRAMMING
3 (2-2-5)
90641001 โรงเรียนสร้างเสน่ห์
CHARM SCHOOL
3 (3-0-6)
90644007 การฟังและการพูดภาษาอังกฤษเพื่อการสื่อสาร
ENGLISH LISTENING AND SPEAKING FOR COMMUNICATION
3 (3-0-6)
จำนวนหน่วยกิตรวม 18
"""

    t0 = time.time()
    try:
        raw = ollama_chat(
            model_name,
            [{"role": "system", "content": SYSTEM_PROMPT},
             {"role": "user", "content": EXTRACT_PROMPT.format(document_text=sample_page_text)}],
            fmt=COURSE_SCHEMA,
            think=False,
            num_ctx=8192,
            num_predict=2048,
        )
        d = parse_json(raw)
        courses = d.get("courses") or []
        dur = round(time.time() - t0, 2)
        n_courses = len(courses)
        print(f"  สกัดได้: {n_courses} รายวิชา (ใช้เวลา {dur:.2f} วินาที)")
        for c in courses:
            print(f"    - {c.get('code')}: {c.get('name_th')} | {c.get('credits')} | {c.get('name_en')}")
        return {
            "model": model_name,
            "success": True,
            "courses_extracted": n_courses,
            "seconds": dur,
            "courses": courses
        }
    except Exception as e:
        dur = round(time.time() - t0, 2)
        print(f"  เกิดข้อผิดพลาด: {e}")
        return {
            "model": model_name,
            "success": False,
            "error": str(e),
            "seconds": dur
        }


def main():
    models = ["qwen3:4b", "qwen2.5-coder:7b"]
    summary = {}

    for model in models:
        # ตรวจสอบว่าโมเดลพร้อมรันหรือไม่
        print(f"\n>>> กำลังเตรียมทดสอบ: {model} <<<")
        sql_res = run_text_to_sql_benchmark(model)
        ext_res = run_extraction_benchmark(model)
        summary[model] = {
            "text_to_sql": sql_res,
            "extraction": ext_res
        }

    # บันทึกผลลัพธ์ลง JSON
    out_json = ROOT / "model_benchmark_results.json"
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nบันทึกผลลัพธ์ฉบับเต็ม: {out_json}")


if __name__ == "__main__":
    main()
