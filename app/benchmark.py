#!/usr/bin/env python3
import time, sys
sys.path.insert(0, 'src')
from ocr_system.lab8b_curriculum_db import ask, open_db

db = 'app/data/it_coop.db'
conn = open_db(db)

questions = [
    'ปีที่ 1 เทอม 1 เรียนกี่หน่วยกิต',
    'วิชา 06066303 ชื่อว่าอะไร',
    'เทอมไหนเรียนหนักที่สุด',
]

print('=== Baseline timing (qwen3:4b, default params) ===')
total = 0
for q in questions:
    t0 = time.time()
    r = ask(conn, q, verbose=False)
    elapsed = time.time() - t0
    total += elapsed
    ans = r['answer']
    sql = r['sql']
    print(f'  {elapsed:.1f}s | Q: {q}')
    print(f'         A: {ans}')
    print(f'         SQL: {sql}')

print(f'\n  รวม: {total:.1f}s  เฉลี่ย: {total/len(questions):.1f}s/คำถาม')
conn.close()
