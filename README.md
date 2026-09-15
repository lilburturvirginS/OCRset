# 📚 ISD 2026 — OCR + LLM Q&A System

> **วิชา:** 06026240 Intelligent System Development · DSBA Coop
> **เป้าหมายโปรเจกต์:** สร้างระบบที่อ่านเล่มหลักสูตร PDF ด้วย OCR แล้วใช้ LLM ตอบคำถามภาษาไทยจากฐานข้อมูลที่สร้างขึ้น

---

## 🗺️ ภาพรวม Pipeline

```
PDF มคอ.2 (เล่มหลักสูตร)
       │
       ▼
  ┌─────────────┐
  │   Lab 4     │  OCR Baseline — ดึงข้อความ วัด Field Accuracy
  └─────────────┘
       │ evaluation_all_levels.json
       ▼
  ┌─────────────┐
  │   Lab 5     │  สร้าง Q&A Dataset (27 คู่ภาษาไทย)
  └─────────────┘
       │ lab5_qa_combined.csv
       ▼
  ┌─────────────┐
  │   Lab 6     │  Evaluation Framework — Precision / Recall / F1
  └─────────────┘
       │ run_lab6_evaluation.py
       ▼
  ┌─────────────┐
  │   Lab 7A    │  OCR บนภาพ Noisy (Synthetic Noise L0–L4)
  └─────────────┘
       │
       ▼
  ┌─────────────┐
  │   Lab 7B    │  Local LLM สกัด JSON วิชาจาก PDF (3 หลักสูตร)
  └─────────────┘
       │ output/lab7b_fixed/*.json
       ▼
  ┌─────────────┐
  │   Lab 8B    │  NL-to-SQL: ถามภาษาไทย → SQL → คำตอบ (97%)
  └─────────────┘
       │ app/data/dsba_coop.db
       ▼
  FastAPI Web App (app/main.py)
```

---

## 📦 ไฟล์สำคัญ

| ไฟล์/โฟลเดอร์ | Lab | บทบาท |
|---|:---:|---|
| `run_lab6_evaluation.py` | 4/6 | Evaluation framework รายฟิลด์ |
| `evaluation_all_levels.json` | 4/6 | ผลวัด OCR accuracy |
| `lab5_qa_combined.csv` | 5 | 27 Q&A pairs ภาษาไทย |
| `DSBA_academic_plan_coop.json` | 4–8 | Ground Truth หลักสูตร DSBA |
| `lab7_metrics.py` | 7A | วัด CER/WER บน Noisy images |
| `lab7b_curriculum.py` | 7B | Pipeline สกัดวิชา (5 Actions) |
| `output/lab7b_fixed/` | 7B | ผล extraction ทั้ง 3 หลักสูตร |
| `src/ocr_system/` | 7B–8B | Source code หลักของระบบ |
| `app/main.py` | 8B | FastAPI Backend (NL→SQL→Thai) |
| `app/data/dsba_coop.db` | 8B | SQLite DB ครบ (80c/37p/5pre) |
| `model_benchmark_results.json` | 8B | เปรียบเทียบ qwen3:4b vs qwen2.5-coder:7b |

---

## 🧪 Lab 4 — OCR Baseline & Field-Level Evaluation

**เป้าหมาย:** วัดความสามารถของ OCR ในการอ่านเล่มหลักสูตร PDF (มคอ.2) ของ DSBA

### สิ่งที่ทำ
- ใช้ `pymupdf` + `pdfplumber` ดึงข้อความจาก PDF
- เปรียบเทียบกับ Ground Truth (`DSBA_academic_plan_coop.json`)
- วัด **field-level accuracy** แยกรายฟิลด์

### ปัญหาที่พบ — MacThai PUA Font Bug
PDF ถูกสร้างด้วยฟอนต์ MacThai ที่เก็บสระและวรรณยุกต์ไว้ใน **Unicode Private Use Area** (`0xF700–0xF71A`) แทน Unicode ไทยมาตรฐาน (`0x0E00–0x0E7F`) → ข้อความภาษาไทยออกมาเป็นสัญลักษณ์ประหลาด

### ผลลัพธ์

| Field | Accuracy |
|---|:---:|
| name_en | 100% |
| credits | 100% |
| category | 100% |
| type | 100% |
| prerequisite | 97.5% |
| **Page Recall** | **98.75%** (79/80 วิชา) |

---

## 📝 Lab 5 — สร้าง Q&A Dataset

**เป้าหมาย:** สร้างชุดคำถาม-คำตอบภาษาไทยจากเนื้อหาเล่มหลักสูตร เพื่อใช้เป็น benchmark

### Dataset: `lab5_qa_combined.csv`
รวม **27 คู่ Q&A** ครอบคลุมหลายประเภท:
- คำถามเกี่ยวกับหน่วยกิตและปี/ภาค
- คำถามเกี่ยวกับรหัสและชื่อวิชา
- คำถามเกี่ยวกับ prerequisite
- คำถามเกี่ยวกับหมวดวิชาและประเภท (บังคับ/เลือก)
- คำถามเปรียบเทียบหลายวิชา

```
Schema: question, answer, course_codes, page_ref, clause_ref, note
```

---

## 📊 Lab 6 — Evaluation Framework & Metrics Design

**เป้าหมาย:** ออกแบบระบบวัดผลที่เหมาะสมกับงาน OCR + LLM Information Extraction

### Script: `run_lab6_evaluation.py`
```python
# 1. โหลด OCR output และ Ground Truth
# 2. จับคู่วิชาด้วย code matching
# 3. วัด field-level accuracy แยกราย attribute
# 4. คำนวณ Precision, Recall, F1
# 5. แยก category_level
# 6. บันทึกผลเป็น evaluation_all_levels.json
```

### สิ่งที่เรียนรู้
- ต้องแยก **Precision/Recall** ไม่ใช่ดูแค่ accuracy รวม
- **Field-level > Document-level**: ดูรายฟิลด์จะรู้ว่าปัญหาอยู่ที่ field ไหน
- ต้องแยก error: (ก) โมเดลสกัดผิด vs (ข) Ground Truth ผิดเอง

---

## 🖼️ Lab 7A — OCR บนภาพเอกสาร Noisy

**เป้าหมาย:** ทดสอบว่า OCR ยังทำงานได้ดีแค่ไหนเมื่อเอกสารมีคุณภาพต่ำลง

### Pipeline
```
PDF (L0) → Synthetic Noise (L1–L4) → OpenCV Pre-processing → typhoon-ocr1.5-3b → CER/WER
```

### 5 ระดับ Noise

| Level | สภาพ | มุมเอียง |
|---|---|:---:|
| L0_clean | ต้นฉบับดิจิทัล | 0° |
| L1_light | สแกนคุณภาพดี | 0.4° |
| L2_watermark | มือถือ + ลายน้ำ | 1.1° |
| L3_tilted_copy | ถ่ายเอกสารซ้ำ | 2.3° |
| L4_rescan | เครื่องถ่ายเก่า | 3.8° |

### สิ่งที่เรียนรู้
- **Breaking Point** = L3–L4 คือจุดที่ accuracy ดิ่งลงชัดเจน
- ลำดับ OpenCV **ห้ามสลับ**: `Deskew → Background Division → Denoising → Binarization`
- เครื่องมือที่ทันสมัยที่สุด ≠ ดีที่สุดเสมอ

---

## 🤖 Lab 7B — สกัดข้อมูลหลักสูตรจาก PDF ด้วย Local LLM

**เป้าหมาย:** PDF มคอ.2 (DSBA, IT, AIT) → JSON รายวิชาตาม Schema

### ปัญหาเริ่มต้น (Baseline)

| หลักสูตร | GT วิชา | Recall |
|---|:---:|:---:|
| DSBA Coop | 90 | **37.8%** ❌ |
| IT Coop | 106 | **39.6%** ❌ |
| AIT | 57 | **45.6%** ❌ |

### 5 Actions ที่แก้ใน `lab7b_curriculum.py`

1. **MacThai PUA Decoder** — แปลงสระ/วรรณยุกต์จาก PUA → Unicode มาตรฐาน
2. **Multi-Semester Chunking** — ผ่าหน้าที่มีหลายภาค ส่ง LLM ทีละภาค
3. **Concrete 1-Shot Prompt** — ตัวอย่างจริงในแต่ละ prompt
4. **Self-Correction Loop** — Ollama refinement สูงสุด 3 รอบ
5. **Adaptive Deduplication** — รวมวิชาเลือก + แผน, code ซ้ำ → ตารางแผนชนะ

### ผลหลัง Fix

| หลักสูตร | Recall เดิม | Recall ใหม่ | F1 |
|---|:---:|:---:|:---:|
| DSBA Coop | 37.8% | **92.22%** | 0.892 |
| IT Coop | 39.6% | **92.45%** | 0.933 |
| AIT | 45.6% | **92.98%** | 0.914 |

---

## 🗃️ Lab 8B — NL-to-SQL: ถามภาษาไทย ตอบจากฐานข้อมูล

**เป้าหมาย:** JSON จาก Lab 7B → SQLite → รับคำถามภาษาไทย ตอบอัตโนมัติ

### Two-Tier Pipeline

```
คำถามภาษาไทย
      ↓ [Tier 1] qwen2.5-coder:7b
      SQL + guard_sql() (ป้องกัน DROP/DELETE)
      ↓ SQLite (read-only)
      ↓ [Tier 2] qwen3:4b
      คำตอบภาษาไทย
```

### Database Schema

```sql
program      (program_id, name_th, name_en, degree, total_credits, years)
course       (code, name_th, name_en, credits, lecture_h, lab_h, self_h)
plan_item    (id, program_id, year, semester, code, credits, alt_group, note)
prerequisite (code, requires, kind)
-- Views
v_plan             -- plan_item JOIN course
v_semester_credits -- SUM(credits) per year/semester
```

### ผลสุดท้าย

```
SQL รันผ่าน   30/30  (100%)
ตอบถูก        29/30  ( 97%)
Avg Latency   ~0.6s/คำถาม
```

### คำสั่งรัน

```bash
python src/ocr_system/lab8b_curriculum_db.py schema
python src/ocr_system/lab8b_curriculum_db.py load
python src/ocr_system/lab8b_curriculum_db.py verify
python src/ocr_system/lab8b_curriculum_db.py ask -q "ปีที่ 2 เทอม 1 เรียนกี่หน่วยกิต"
python src/ocr_system/lab8b_curriculum_db.py eval

# รัน Web App
uvicorn app.main:app --reload
# → http://localhost:8000
```

---

## 🚀 วิธีติดตั้งและรัน

### Requirements
- Python 3.10+
- [Ollama](https://ollama.ai) พร้อมโมเดล: `qwen3:4b`, `qwen2.5-coder:7b`, `typhoon-ocr1.5-3b`

```bash
git clone https://github.com/lilburturvirginS/OCRset.git
cd OCRset
pip install -e .
```

---

## 📈 ตัวเลขสำคัญสรุป

| งาน | Metric | ผล |
|---|---|:---:|
| Lab 4 — OCR Field Accuracy | Page Recall | **98.75%** |
| Lab 7B — Extraction | DSBA Recall (ก่อน → หลัง) | 37.8% → **92.2%** |
| Lab 7B — F1 Score | IT Coop | **0.933** |
| Lab 8B — NL-to-SQL | SQL Pass Rate | **100%** (30/30) |
| Lab 8B — NL-to-SQL | Answer Accuracy | **97%** (29/30) |
| Lab 8B — Latency | เวลาเฉลี่ย/คำถาม | **~0.6s** |

---

## 📁 โครงสร้างโปรเจกต์

```
isd-2026-OCR-LLM-QNA/
├── README.md
├── DSBA_academic_plan_coop.json       ← Ground Truth หลักสูตร DSBA
├── run_lab6_evaluation.py             ← Evaluation framework (Lab 4/6)
├── lab5_qa_combined.csv               ← 27 Q&A pairs (Lab 5)
├── lab7_metrics.py                    ← CER/WER metrics (Lab 7A)
├── lab7b_curriculum.py                ← Pipeline สกัดวิชา (Lab 7B)
├── evaluation_all_levels.json
├── model_benchmark_results.json
├── src/
│   └── ocr_system/
│       └── lab8b_curriculum_db.py     ← Engine ครบวงจร (Lab 8B)
├── app/
│   ├── main.py                        ← FastAPI Backend
│   ├── index.html
│   ├── style.css
│   └── data/dsba_coop.db              ← SQLite Database
├── output/lab7b_fixed/                ← ผล extraction ทั้ง 3 หลักสูตร
├── work/
│   ├── build_from_gt.py
│   └── lab8b_run/                     ← schema, curriculum, eval results
├── data/                              ← PDF ต้นฉบับ
└── gt/                                ← Ground Truth
```

---

*โปรเจกต์นี้เป็นส่วนหนึ่งของวิชา Intelligent System Development (ISD) ปีการศึกษา 2026 หลักสูตร DSBA Coop*
