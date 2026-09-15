#!/usr/bin/env python3
"""
benchmark_optimized.py — วัดเวลาหลัง optimize
Baseline: Q1=40.7s(cold) / Q2=0.8s / Q3=0.9s → เฉลี่ย 14.1s (incl. cold-start)
"""
import sys, os, time, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

os.environ["LAB8_SQL_NUM_CTX"]     = "1024"
os.environ["LAB8_SQL_NUM_PREDICT"] = "128"
os.environ["LAB8_ANS_NUM_CTX"]     = "2048"
os.environ["LAB8_ANS_NUM_PREDICT"] = "200"
os.environ["LAB8_KEEP_ALIVE"]      = "-1"

import importlib.util
spec = importlib.util.spec_from_file_location("m", Path(__file__).parent / "main.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# ── warm-up ───────────────────────────────────────────────────────────────
print("=== Warm-up (โหลด model + ตั้ง num_ctx=2048) ===")
t_warm = time.time()
# ต้อง warm-up ด้วย num_ctx เดียวกับ main calls เพื่อให้ Ollama จอง KV-cache
# ขนาด 2048 ไว้ล่วงหน้า ป้องกัน resize penalty ในคำถามแรก
m.ollama_generate("hi /no_think", num_ctx=m.NUM_CTX, num_predict=5)
print(f"  warm-up: {time.time()-t_warm:.1f}s\n")

print(f"  SQL: num_ctx={m.SQL_NUM_CTX}, num_predict={m.SQL_NUM_PREDICT}")
print(f"  ANS: num_ctx={m.ANS_NUM_CTX}, num_predict={m.ANS_NUM_PREDICT}")
print(f"  keep_alive={m.KEEP_ALIVE}")
print()

# ── test questions (IT Coop + AIT) ───────────────────────────────────────
QUESTIONS = [
    ("it_coop", Path("app/data/it_coop.db"), "ปีที่ 1 เทอม 1 เรียนกี่หน่วยกิต"),
    ("it_coop", Path("app/data/it_coop.db"), "วิชา 06066303 ชื่อว่าอะไร"),
    ("it_coop", Path("app/data/it_coop.db"), "เทอมไหนเรียนหนักที่สุด"),
    ("ait",     Path("app/data/ait.db"),     "หลักสูตรนี้มีกี่หน่วยกิตรวม"),
    ("ait",     Path("app/data/ait.db"),     "ปีที่ 2 เทอม 1 เรียนวิชาอะไรบ้าง"),
]

print("=== Optimized timing ===")
total = 0
for prog_id, db_path, q in QUESTIONS:
    t0 = time.time()
    r = m.ask_question(prog_id, db_path, q)
    elapsed = time.time() - t0
    total += elapsed
    sql_ms = r.get("_sql_ms", "?")
    ans_ms = r.get("_ans_ms", "?")
    ans = r["answer"]
    sql = r["sql"] or "(none)"
    print(f"  [{prog_id}] {elapsed:.2f}s  (SQL:{sql_ms}ms  ANS:{ans_ms}ms)")
    print(f"    Q: {q}")
    print(f"    A: {ans}")
    print(f"    SQL: {sql}")
    print()

avg = total / len(QUESTIONS)
baseline_warm = 0.85  # จาก Q2+Q3 ก่อน optimize
improvement = (baseline_warm - avg) / baseline_warm * 100 if avg < baseline_warm else 0

print("=" * 60)
print(f"  รวม     : {total:.2f}s")
print(f"  เฉลี่ย  : {avg:.2f}s/คำถาม")
print(f"  Baseline warm : ~{baseline_warm:.2f}s/คำถาม")
if improvement > 0:
    print(f"  เร็วขึ้น: {improvement:.0f}%")
else:
    print(f"  เปรียบเทียบ: avg {avg:.2f}s vs baseline {baseline_warm:.2f}s")
print("=" * 60)
