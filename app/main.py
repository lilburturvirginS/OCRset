#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py — FastAPI backend สำหรับ Curriculum Q&A Application
รัน: uvicorn app.main:app --reload  (จาก root ของโปรเจกต์)
หรือ: python app/main.py
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ─── Paths ───────────────────────────────────────────────────────────────────
APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
ROOT = APP_DIR.parent
sys.path.insert(0, str(ROOT / "src"))

OLLAMA_URL = os.environ.get("LAB8_OLLAMA_URL", "http://127.0.0.1:11434")
MODEL_TEXT = os.environ.get("LAB8_MODEL_TEXT", "qwen3:4b")
MODEL_SQL = os.environ.get("LAB8_MODEL_SQL", "qwen2.5-coder:7b")
MODEL_ANSWER = os.environ.get("LAB8_MODEL_ANSWER", "qwen3:4b")
SQL_ROW_LIMIT = 200

# ── ค่า performance tuning (override ด้วย env var) ──────────────────────────
#
# ทำไมถึงใช้ num_ctx เดียวกันทั้งสอง step:
#   Ollama เก็บ KV-cache ตามขนาด context ที่กำหนด
#   ถ้าเปลี่ยน num_ctx ระหว่างสองการเรียก Ollama ต้อง re-initialize KV-cache
#   ทำให้เสียเวลา ~2s/call เพิ่มเติม → ใช้ค่าเดียวกัน 2048 ทั้งสองเพื่อหลีกปัญหานี้
#
NUM_CTX         = int(os.environ.get("LAB8_NUM_CTX",  "2048"))   # ใช้ทั้ง SQL และ Answer
SQL_NUM_CTX     = NUM_CTX   # alias เพื่อใช้ใน benchmark
ANS_NUM_CTX     = NUM_CTX
SQL_NUM_PREDICT = int(os.environ.get("LAB8_SQL_NUM_PREDICT", "128"))
ANS_NUM_PREDICT = int(os.environ.get("LAB8_ANS_NUM_PREDICT", "256"))
# keep_alive=-1 → Ollama ไม่ unload โมเดลออกจาก GPU ระหว่าง request
# ใช้ int ไม่ใช้ str เพราะ Ollama API รับ int เท่านั้น
KEEP_ALIVE: int = int(os.environ.get("LAB8_KEEP_ALIVE", "-1"))

# ── DB connection cache (เปิดครั้งเดียว ใช้ได้ตลอด process) ─────────────────
_DB_CACHE: dict[str, sqlite3.Connection] = {}

# ─── โปรแกรมที่รองรับ ─────────────────────────────────────────────────────
PROGRAMS: dict[str, dict] = {
    "dsba_coop": {
        "id": "dsba_coop",
        "name_th": "วิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ (สหกิจศึกษา)",
        "name_en": "DSBA Co-op",
        "short": "DSBA Coop",
        "icon": "📊",
        "field_accuracy": 100.0,
        "courses": 80,
        "db": DATA_DIR / "dsba_coop.db",
        "color": "#6366f1",
        "suggested": [
            "ปีที่ 1 เทอม 1 เรียนกี่หน่วยกิต",
            "วิชา 06026200 ชื่อว่าอะไร",
            "วิชา 06026201 ต้องเรียนวิชาอะไรมาก่อน",
            "หลักสูตรนี้มีกี่หน่วยกิตรวม",
            "เทอมไหนเรียนหนักที่สุด",
            "ปีที่ 3 เทอม 2 เรียนวิชาอะไรบ้าง",
        ],
    },
    "dsba_nocoop": {
        "id": "dsba_nocoop",
        "name_th": "วิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ",
        "name_en": "DSBA Regular",
        "short": "DSBA",
        "icon": "📈",
        "field_accuracy": 100.0,
        "courses": 80,
        "db": DATA_DIR / "dsba_nocoop.db",
        "color": "#8b5cf6",
        "suggested": [
            "ปีที่ 2 เทอม 1 เรียนกี่หน่วยกิต",
            "วิชา 06026202 คือวิชาอะไร",
            "หลักสูตรนี้มีกี่หน่วยกิตรวม",
            "ปีที่ 1 เทอม 1 เรียนกี่วิชา",
        ],
    },
    "ait": {
        "id": "ait",
        "name_th": "เทคโนโลยีสารสนเทศ (นานาชาติ)",
        "name_en": "Applied IT",
        "short": "AIT",
        "icon": "🌐",
        "field_accuracy": 100.0,
        "courses": 50,
        "db": DATA_DIR / "ait.db",
        "color": "#0ea5e9",
        "suggested": [
            "หลักสูตรนี้มีกี่หน่วยกิตรวม",
            "ปีที่ 1 เทอม 1 เรียนกี่วิชา",
            "วิชาบังคับมีกี่วิชา",
            "ปีที่ 4 เทอม 1 เรียนอะไรบ้าง",
        ],
    },
    "it_coop": {
        "id": "it_coop",
        "name_th": "เทคโนโลยีสารสนเทศ (สหกิจศึกษา)",
        "name_en": "IT Co-op",
        "short": "IT Coop",
        "icon": "💻",
        "field_accuracy": 99.0,
        "courses": 100,
        "db": DATA_DIR / "it_coop.db",
        "color": "#10b981",
        "suggested": [
            "หลักสูตรนี้มีกี่หน่วยกิตรวม",
            "ปีที่ 2 เทอม 2 เรียนกี่หน่วยกิต",
            "วิชา 06066303 ชื่อว่าอะไร",
            "เทอมไหนมีวิชาน้อยที่สุด",
        ],
    },
    "it_nocoop": {
        "id": "it_nocoop",
        "name_th": "เทคโนโลยีสารสนเทศ",
        "name_en": "IT Regular",
        "short": "IT",
        "icon": "🖥️",
        "field_accuracy": 99.0,
        "courses": 100,
        "db": DATA_DIR / "it_nocoop.db",
        "color": "#f59e0b",
        "suggested": [
            "หลักสูตรนี้มีกี่หน่วยกิตรวม",
            "ปีที่ 1 เทอม 1 เรียนอะไรบ้าง",
            "วิชาที่มีหน่วยกิตมากที่สุดคืออะไร",
        ],
    },
}

# ─── SQL Guard ────────────────────────────────────────────────────────────────
FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|"
    r"pragma|vacuum|reindex|truncate)\b", re.I)

# DDL สั้นที่สุดที่ยังให้ LLM เขียน SQL ถูก (ลด token ~40%)
DDL_CONTEXT = (
    "program(program_id,name_th,total_credits,years)\n"
    "course(code,name_th,name_en,credits)\n"
    "plan_item(id,program_id,year,semester,code,credits,alt_group,note)\n"
    "prerequisite(code,requires,kind)  -- kind='pre'\n"
    "VIEW v_plan(year,semester,code,name_th,name_en,credits)\n"
    "VIEW v_semester_credits(year,semester,credits,n_courses)"
)

# SQL prompt prefix คงที่ — ไม่ต้อง format ใหม่ทุก request
_SQL_PROMPT_PREFIX = (
    "แปลงคำถามภาษาไทยเป็น SQLite SQL คำสั่งเดียว (SELECT หรือ WITH เท่านั้น)\n\n"
    f"Schema:\n{DDL_CONTEXT}\n\n"
    "ตัวอย่าง:\n"
    "Q: ปี 2 เทอม 1 กี่หน่วยกิต → SELECT credits FROM v_semester_credits WHERE year=2 AND semester=1\n"
    "Q: วิชา 06026240 ชื่อว่าอะไร → SELECT name_th FROM course WHERE code='06026240'\n"
    "Q: วิชาไหนต้องเรียน X มาก่อน → SELECT code FROM prerequisite WHERE requires='X' AND kind='pre'\n"
    "Q: วิชา X ต้องเรียนวิชาอะไรมาก่อน / ต้องผ่านอะไรมาก่อนถึงจะลง X ได้ → SELECT requires FROM prerequisite WHERE code='X' AND kind='pre'\n"
    "Q: เรียนวิชาอะไรบ้างปี 3 เทอม 1 → SELECT code,name_th FROM v_plan WHERE year=3 AND semester=1\n"
    "Q: หลักสูตรมีกี่หน่วยกิต → SELECT total_credits FROM program\n"
    "Q: เทอมไหนหนักสุด → SELECT year,semester,credits FROM v_semester_credits ORDER BY credits DESC LIMIT 1\n\n"
    "กติกา: ถามหน่วยกิตต่อเทอมใช้ v_semester_credits, ถามวิชาใช้ v_plan\n\n"
    "Q: {question}\nSQL:"
)

# Answer prompt — ชัดเจน ไม่สั้นเกินไป เพื่อป้องกัน hallucination
ANSWER_PROMPT = (
    "ตอบคำถามเป็นภาษาไทย โดยใช้เฉพาะข้อมูลจากผลลัพธ์ด้านล่างเท่านั้น\n\n"
    "คำถาม: {question}\n\n"
    "ผลลัพธ์: {rows}\n\n"
    "กติกา:\n"
    "- ตอบสั้น ตรงประเด็น ใช้ตัวเลขและชื่อจากผลลัพธ์เท่านั้น ห้ามเพิ่มเติม\n"
    "- ถ้าผลลัพธ์ว่าง ตอบว่า ไม่พบข้อมูลนี้ในเล่มหลักสูตร\n"
    "- ถ้าคำถามเกี่ยวกับหน่วยกิต (เช่น total_credits, credits) ให้ใช้คำว่า 'หน่วยกิต' เสมอ\n"
    '- ตอบเป็น JSON {{"answer": "คำตอบภาษาไทย"}} เท่านั้น'
)


def ollama_generate(prompt: str, fmt: Any = None,
                    model: str | None = None,
                    num_ctx: int = SQL_NUM_CTX,
                    num_predict: int = SQL_NUM_PREDICT) -> str:
    import requests
    target_model = model or MODEL_TEXT
    content = prompt + ("\n/no_think" if "qwen3" in target_model.lower() else "")
    payload: dict[str, Any] = {
        "model": target_model,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "think": False,
        "keep_alive": KEEP_ALIVE,   # ← คงโมเดลไว้ใน GPU ระหว่าง requests
        "options": {
            "temperature": 0.0,
            "num_ctx": num_ctx,
            "num_predict": num_predict,
            "stop": ["```", "<think>"],  # ← หยุดก่อนสร้าง reasoning หรือ markdown
        },
    }
    if fmt:
        payload["format"] = fmt
    r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=60)
    r.raise_for_status()
    return (r.json().get("message") or {}).get("content", "")


def parse_json_loose(s: str) -> dict:
    s = re.sub(r"<think>.*?</think>", "", s, flags=re.S)
    s = re.sub(r"^```(?:json)?|```$", "", s.strip(), flags=re.M).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    start = s.find("{")
    if start < 0:
        return {}
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(s[start:i + 1])
                except json.JSONDecodeError:
                    return {}
    return {}


def clean_sql(s: str) -> str:
    """ตัด <think> และ fence ออกจาก SQL รองรับทั้ง query บรรทัดเดียวและหลายบรรทัด"""
    s = re.sub(r"<think>.*?</think>", "", s, flags=re.S)
    s = re.sub(r"```(?:sql)?", "", s).strip()
    m = re.search(r"(?is)\b(select|with)\b.*", s)
    if not m:
        return s.strip()
    sql = m.group(0).strip()
    if ";" in sql:
        sql = sql.split(";")[0].strip()
    lines = []
    for line in sql.splitlines():
        if re.search(r"[\u0e00-\u0e7f]", line) and not re.search(r"['\"][^'\"]*[\u0e00-\u0e7f][^'\"]*['\"]", line):
            break
        lines.append(line)
    sql = " ".join(lines).strip()
    sql = re.sub(r"\s+", " ", sql).strip()
    return sql


def guard_sql(sql: str) -> str:
    s = sql.strip().rstrip(";").strip()
    if not s:
        raise ValueError("SQL ว่างเปล่า")
    if ";" in s:
        raise ValueError("ห้ามมีหลายคำสั่งใน query เดียว")
    if not re.match(r"^\s*(select|with)\b", s, re.I):
        raise ValueError("อนุญาตเฉพาะ SELECT หรือ WITH เท่านั้น")
    if FORBIDDEN_SQL.search(s):
        raise ValueError("พบคำสั่งที่ไม่อนุญาตใน SQL")
    if not re.search(r"\blimit\b", s, re.I):
        s += f" LIMIT {SQL_ROW_LIMIT}"
    return s


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def get_cached_db(program_id: str, db_path: Path) -> sqlite3.Connection:
    """คืน DB connection ที่เปิดไว้แล้ว (สร้างใหม่ถ้า closed หรือยังไม่มี)"""
    conn = _DB_CACHE.get(program_id)
    if conn is None:
        conn = open_db(db_path)
        _DB_CACHE[program_id] = conn
    else:
        try:
            conn.execute("SELECT 1")  # ตรวจว่ายัง alive
        except Exception:
            conn = open_db(db_path)
            _DB_CACHE[program_id] = conn
    return conn


def ask_question(program_id: str, db_path: Path, question: str) -> dict:
    result: dict[str, Any] = {
        "question": question, "sql": None, "rows": [],
        "answer": None, "error": None, "elapsed_ms": 0,
    }
    t0 = time.time()

    # ── ใช้ cached connection แทนเปิดใหม่ทุก request ────────────────────────
    conn = get_cached_db(program_id, db_path)

    # ── Step 1: Thai → SQL (num_ctx=1024, num_predict=128) ──────────────────
    sql_prompt = _SQL_PROMPT_PREFIX.format(question=question)
    t_sql = time.time()

    for attempt in range(2):
        try:
            raw_sql = ollama_generate(
                sql_prompt + '\nตอบเป็น JSON {"sql": "SELECT ..."}',
                fmt={
                    "type": "object",
                    "properties": {"sql": {"type": "string"}},
                    "required": ["sql"],
                    "additionalProperties": False,
                },
                model=MODEL_SQL,
                num_ctx=SQL_NUM_CTX,
                num_predict=SQL_NUM_PREDICT,
            )
            parsed_sql = parse_json_loose(raw_sql)
            sql_raw = str(parsed_sql.get("sql", "")) if isinstance(parsed_sql, dict) else raw_sql
            sql = guard_sql(clean_sql(sql_raw))
            result["sql"] = sql
            rows = [dict(r) for r in conn.execute(sql).fetchall()]
            result["rows"] = rows
            result["error"] = None
            break
        except Exception as e:
            result["error"] = f"{type(e).__name__}: {e}"
            if attempt == 1:
                result["answer"] = "ไม่สามารถตอบคำถามนี้ได้ กรุณาลองใหม่หรือปรับคำถาม"
                result["elapsed_ms"] = int((time.time() - t0) * 1000)
                return result
            # retry with error context
            sql_prompt = (
                _SQL_PROMPT_PREFIX.format(question=question)
                + f"\nSQL ก่อนหน้าผิด: {e}\nเขียนใหม่:"
            )

    result["_sql_ms"] = int((time.time() - t_sql) * 1000)

    if not result["rows"]:
        result["answer"] = "ไม่พบข้อมูลนี้ในเล่มหลักสูตร"
        result["elapsed_ms"] = int((time.time() - t0) * 1000)
        return result

    # ── Step 2: rows → Thai answer (num_ctx=2048 — เพิ่ม num_predict เพื่อโมเดลตอบให้ครบถ้ามีวิชาหลายราย) ──
    t_ans = time.time()
    rows_json = json.dumps(result["rows"][:20], ensure_ascii=False)  # จำกัด 20 แถว
    raw_ans = ollama_generate(
        ANSWER_PROMPT.format(question=question, rows=rows_json),
        fmt={
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
            "additionalProperties": False,
        },
        model=MODEL_ANSWER,
        num_ctx=NUM_CTX,         # ← เดียวกันกับ SQL step — ไม่ต้อง re-init KV-cache
        num_predict=ANS_NUM_PREDICT,
    )
    parsed_ans = parse_json_loose(raw_ans)
    answer = str(parsed_ans.get("answer", "")).strip() if isinstance(parsed_ans, dict) else raw_ans
    answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.S).strip()
    result["answer"] = answer or "ไม่สามารถสรุปคำตอบได้"
    result["_ans_ms"] = int((time.time() - t_ans) * 1000)

    result["elapsed_ms"] = int((time.time() - t0) * 1000)
    return result


# ─── FastAPI App ──────────────────────────────────────────────────────────────
app = FastAPI(title="Curriculum Q&A", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# serve static files
app.mount("/static", StaticFiles(directory=str(APP_DIR)), name="static")


class AskRequest(BaseModel):
    program_id: str
    question: str


class AskResponse(BaseModel):
    question: str
    answer: str
    sql: str | None
    rows: list[dict]
    error: str | None
    elapsed_ms: int


@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = APP_DIR / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>index.html not found</h1>")


@app.get("/api/programs")
async def get_programs():
    return [
        {
            "id": p["id"],
            "name_th": p["name_th"],
            "name_en": p["name_en"],
            "short": p["short"],
            "icon": p["icon"],
            "field_accuracy": p["field_accuracy"],
            "courses": p["courses"],
            "color": p["color"],
            "suggested": p["suggested"],
            "available": p["db"].exists(),
        }
        for p in PROGRAMS.values()
    ]


@app.post("/api/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    prog = PROGRAMS.get(req.program_id)
    if not prog:
        raise HTTPException(status_code=404, detail=f"ไม่พบสาขา: {req.program_id}")
    if not prog["db"].exists():
        raise HTTPException(status_code=503, detail="ฐานข้อมูลยังไม่พร้อม รัน setup_dbs.py ก่อน")
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="กรุณาพิมพ์คำถาม")

    result = ask_question(req.program_id, prog["db"], req.question.strip())
    # strip internal timing keys ก่อนส่งออก
    result.pop("_sql_ms", None)
    result.pop("_ans_ms", None)
    return AskResponse(**result)


@app.get("/health")
async def health():
    import requests as req_lib
    try:
        r = req_lib.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        models = [m["name"] for m in r.json().get("models", [])]
        ollama_ok = any(m.startswith(MODEL_TEXT.split(":")[0]) for m in models)
    except Exception:
        ollama_ok = False

    return {
        "status": "ok" if ollama_ok else "degraded",
        "ollama": ollama_ok,
        "model_sql": MODEL_SQL,
        "model_answer": MODEL_ANSWER,
        "programs": {pid: p["db"].exists() for pid, p in PROGRAMS.items()},
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True,
                app_dir=str(APP_DIR))
