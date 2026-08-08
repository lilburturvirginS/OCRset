# Thai-English OCR System — Curriculum Extraction & QA Pipeline

ระบบ OCR Pipeline สำหรับเอกสารภาษาไทยและอังกฤษ รองรับ PDF หลายร้อยหน้า  
มีฟีเจอร์หลักครบ 3 ส่วน: **OCR** → **Course Extraction** → **Multi-Level Evaluation**

ครอบคลุม **3 สาขาวิชา** คณะเทคโนโลยีสารสนเทศ มหาวิทยาลัยเกษตรศาสตร์ วิทยาเขตศรีราชา:

| สาขา | ชื่อเต็ม | แผน |
|------|----------|-----|
| **IT** | เทคโนโลยีสารสนเทศ | Coop / No Coop |
| **DSBA** | วิทยาการข้อมูลและการวิเคราะห์ทางธุรกิจ | Coop / No Coop |
| **AIT** | เทคโนโลยีปัญญาประดิษฐ์ | No Coop |

---

## สารบัญ

- [Project Structure](#project-structure)
- [Installation](#installation)
- [OCR Usage](#ocr-usage)
- [Curriculum Pipeline (Lab 4–6)](#curriculum-pipeline-lab-46)
- [Multi-Level Evaluation](#multi-level-evaluation)
- [ผลลัพธ์ล่าสุด](#ผลลัพธ์ล่าสุด)
- [ไฟล์และโค้ดที่สำคัญ](#ไฟล์และโค้ดที่สำคัญ)

---

## Project Structure

```text
isd-2026-OCR-LLM-QNA/
├── README.md
├── pyproject.toml
├── run_lab6_evaluation.py       # รัน Multi-Level Evaluation ครบทุก scenario ครั้งเดียว
├── check_notes.py               # สคริปต์ตรวจสอบค่า note ระหว่าง OCR output กับ GT
├── note_mismatch_only.csv       # รายการ note ที่ไม่ตรงกัน (CSV)
├── note_mismatch_only.json      # รายการ note ที่ไม่ตรงกัน (JSON)
│
├── data/
│   └── ground_truth/
│       ├── IT_academic_plan_coop.json
│       ├── IT_academic_plan_no_coop.json
│       ├── DSBA_academic_plan_coop.json
│       ├── DSBA_academic_plan_no_coop.json
│       ├── AIT_academic_plan.json
│       ├── general_education_ground_truth.json
│       ├── rules_ground_truth.json
│       ├── qa_pairs.csv
│       ├── it_coop_course_page_mapping.csv
│       ├── it_no_coop_course_page_mapping.csv
│       ├── dsba_coop_course_page_mapping.csv
│       ├── dsba_no_coop_course_page_mapping.csv
│       └── ait_course_page_mapping.csv
│
├── outputs/
│   ├── IT_curriculum_ocr.json                  # ผล OCR ดิบ (IT)
│   ├── IT_curriculum_courses_coop.json         # รายวิชาที่สกัดได้ (IT coop)
│   ├── IT_curriculum_courses_no_coop.json      # รายวิชาที่สกัดได้ (IT no_coop)
│   ├── IT_curriculum_curriculum_evaluation_coop.json
│   ├── IT_curriculum_curriculum_evaluation_no_coop.json
│   ├── dsba_curriculum_ocr.json                # ผล OCR ดิบ (DSBA)
│   ├── dsba_curriculum_courses_coop.json
│   ├── dsba_curriculum_courses_no_coop.json
│   ├── dsba_curriculum_curriculum_evaluation_coop.json
│   ├── dsba_curriculum_curriculum_evaluation_no_coop.json
│   ├── AIT_curriculum_ocr.json                 # ผล OCR ดิบ (AIT)
│   ├── AIT_curriculum_courses_no_coop.json
│   ├── AIT_curriculum_curriculum_evaluation_no_coop.json
│   ├── *_evaluation_all_levels.json            # ผล Multi-Level Evaluation ทุก scenario
│   └── lab6_final_report.txt                   # รายงานสรุปผลการประเมิน Lab 6
│
└── src/
    └── ocr_system/
        ├── cli.py                    # Command Line Interface
        ├── config.py                 # Config หลักของระบบ
        ├── document_loader.py        # โหลดภาพ / แปลง PDF เป็นภาพ
        ├── preprocessing.py          # resize, denoise, contrast, deskew, threshold
        ├── pipeline.py               # OCR pipeline หลัก
        ├── evaluation.py             # CER, WER, exact match
        ├── field_extraction.py       # ดึง field เช่น email, date, id, phone
        ├── curriculum_extraction.py  # สกัดรายวิชาจากเอกสารหลักสูตร (Lab 4)
        ├── evaluate_curriculum.py    # วัดผล recall + field-level agreement (Lab 4)
        ├── evaluate_all_levels.py    # Multi-Level Evaluation (Lab 5, 6)
        ├── page_mapping.py           # จับคู่รายวิชากับหน้าเอกสาร
        ├── schemas.py                # Dataclass ของผลลัพธ์
        ├── engine_factory.py         # เลือก OCR engine
        ├── engines/
        │   ├── base.py
        │   ├── paddle_engine.py
        │   ├── tesseract_engine.py
        │   ├── trocr_engine.py
        │   └── ensemble_engine.py
        └── utils/
            └── io.py
```

---

## Installation

> แนะนำใช้ **Python 3.10** ขึ้นไป

### 1. ตรวจสอบ Python version

```bash
python --version
# หรือ
py --version
```

### 2. สร้าง Virtual Environment

```bash
python -m venv .venv
```

### 3. เปิดใช้งาน Virtual Environment

**Windows PowerShell:**
```powershell
.venv\Scripts\Activate.ps1
```

> ถ้า error เรื่อง policy:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

**Windows CMD:**
```cmd
.venv\Scripts\activate
```

**macOS / Linux:**
```bash
source .venv/bin/activate
```

### 4. ติดตั้ง Packages

```bash
pip install -r requirements.txt
pip install -e .
```

### 5. ติดตั้ง Tesseract OCR (ถ้าต้องการใช้ engine Tesseract)

**Windows:** ติดตั้งจาก [UB Mannheim build](https://github.com/UB-Mannheim/tesseract/wiki) → เลือก language: English + Thai

**Ubuntu / Debian:**
```bash
sudo apt update
sudo apt install tesseract-ocr tesseract-ocr-tha poppler-utils
```

**macOS:**
```bash
brew install tesseract tesseract-lang poppler
```

ตรวจสอบหลังติดตั้ง:
```bash
tesseract --version
tesseract --list-langs   # ควรเห็น tha และ eng
```

---

## OCR Usage

### OCR ด้วย Ensemble (แนะนำสำหรับเอกสารไทย+อังกฤษ)

```bash
python -m ocr_system.cli ocr data/input/sample.pdf --engine ensemble --languages tha+eng --paddle-lang th
```

### OCR ด้วย PaddleOCR

```bash
python -m ocr_system.cli ocr data/input/sample.pdf --engine paddle --paddle-lang th
```

### OCR ด้วย Tesseract

```bash
python -m ocr_system.cli ocr data/input/sample.pdf --engine tesseract --languages tha+eng
```

### OCR ด้วย TrOCR (สำหรับข้อความ printed English)

```bash
python -m ocr_system.cli ocr data/input/sample.jpg --engine trocr --device cpu
```

### ผลลัพธ์ OCR

หลังรัน จะได้ไฟล์ใน `outputs/`:

| ไฟล์ | ความหมาย |
|------|----------|
| `sample_ocr.json` | ผล OCR แบบละเอียด (text, confidence, page, box) |
| `sample_ocr.txt` | ข้อความ OCR รวมทุกหน้า อ่านง่าย |
| `sample_fields.json` | Field ที่ extract ได้ เช่น วันที่ รหัส โทรศัพท์ |
| `outputs/pages/` | ภาพแต่ละหน้าที่แปลงจาก PDF |

### Output JSON Format

```json
{
  "source_path": "data/input/sample.pdf",
  "engine": "ensemble",
  "text": "--- Page 1 ---\n...",
  "pages": [
    {
      "page": 1,
      "text": "...",
      "lines": [
        {
          "text": "ข้อความที่ OCR อ่านได้",
          "confidence": 0.95,
          "box": [[0, 0], [100, 0], [100, 30], [0, 30]],
          "engine": "paddle",
          "page": 1
        }
      ],
      "image_path": "outputs/pages/sample_page_001.jpg"
    }
  ]
}
```

---

## Curriculum Pipeline (Lab 4–6)

Pipeline สำหรับสกัดและประเมินข้อมูลรายวิชาจากหลักสูตรฉบับ PDF:

```text
หลักสูตร PDF (400+ หน้า)
     │
     ▼  [OCR Engine: Tesseract tha+eng]
 ข้อความดิบ (Raw OCR JSON)
     │
     ▼  [curriculum_extraction.py]
        - Auto-detect สาขา (IT / DSBA / AIT) จากรหัสวิชา
        - Parse รายวิชา: code, name_th, name_en, credits, year, semester,
          category, type, prerequisite, note, page
        - Whitelist กรองวิชาที่ถูกต้อง
        - Overrides แก้ไขค่าที่ OCR อ่านผิด
     │
     ▼  [evaluate_curriculum.py / evaluate_all_levels.py]
        ประเมินผลเทียบ Ground Truth ทุกมิติ
```

### ขั้นตอนที่ 1: OCR ไฟล์หลักสูตร

```bash
# IT
python -m ocr_system.cli ocr data/input/IT_curriculum.pdf --engine tesseract --output-dir outputs

# DSBA
python -m ocr_system.cli ocr data/input/DSBA_curriculum.pdf --engine tesseract --output-dir outputs

# AIT
python -m ocr_system.cli ocr data/input/AIT_curriculum.pdf --engine tesseract --output-dir outputs
```

### ขั้นตอนที่ 2: สกัดรายวิชาและประเมินผลเบื้องต้น

```powershell
# IT — แผนปกติ (no_coop)
python -m ocr_system.cli curriculum outputs/IT_curriculum_ocr.json --ground-truth data/ground_truth/IT_academic_plan_no_coop.json --plan no_coop

# IT — แผนสหกิจ (coop)
python -m ocr_system.cli curriculum outputs/IT_curriculum_ocr.json --ground-truth data/ground_truth/IT_academic_plan_coop.json --plan coop

# DSBA — แผนปกติ (no_coop)
python -m ocr_system.cli curriculum outputs/dsba_curriculum_ocr.json --ground-truth data/ground_truth/DSBA_academic_plan_no_coop.json --plan no_coop

# DSBA — แผนสหกิจ (coop)
python -m ocr_system.cli curriculum outputs/dsba_curriculum_ocr.json --ground-truth data/ground_truth/DSBA_academic_plan_coop.json --plan coop

# AIT
python -m ocr_system.cli curriculum outputs/AIT_curriculum_ocr.json --ground-truth data/ground_truth/AIT_academic_plan.json --plan no_coop
```

ผลลัพธ์จากขั้นตอนนี้:
- `outputs/*_courses_{plan}.json` — รายวิชาที่สกัดได้ พร้อม field ครบถ้วน
- `outputs/*_curriculum_evaluation_{plan}.json` — ผลประเมินเบื้องต้น (recall, field agreement)

### ขั้นตอนที่ 3: Multi-Level Evaluation ครบทุก scenario (แนะนำ)

```bash
py run_lab6_evaluation.py
```

หรือรันแยก scenario ผ่าน module:

```powershell
# IT coop
python -m ocr_system.evaluate_all_levels outputs/IT_curriculum_ocr.json data/ground_truth/IT_academic_plan_coop.json --program IT --plan coop --page-mapping data/ground_truth/it_coop_course_page_mapping.csv --output-dir outputs

# IT no_coop
python -m ocr_system.evaluate_all_levels outputs/IT_curriculum_ocr.json data/ground_truth/IT_academic_plan_no_coop.json --program IT --plan no_coop --page-mapping data/ground_truth/it_no_coop_course_page_mapping.csv --output-dir outputs

# DSBA coop
python -m ocr_system.evaluate_all_levels outputs/dsba_curriculum_ocr.json data/ground_truth/DSBA_academic_plan_coop.json --program DSBA --plan coop --page-mapping data/ground_truth/dsba_coop_course_page_mapping.csv --output-dir outputs

# DSBA no_coop
python -m ocr_system.evaluate_all_levels outputs/dsba_curriculum_ocr.json data/ground_truth/DSBA_academic_plan_no_coop.json --program DSBA --plan no_coop --page-mapping data/ground_truth/dsba_no_coop_course_page_mapping.csv --output-dir outputs

# AIT
python -m ocr_system.evaluate_all_levels outputs/AIT_curriculum_ocr.json data/ground_truth/AIT_academic_plan.json --program AIT --plan no_coop --page-mapping data/ground_truth/ait_course_page_mapping.csv --output-dir outputs
```

---

## Multi-Level Evaluation

ระบบประเมินผลใน **4 ระดับ**:

| ระดับ | คำอธิบาย | Metric |
|-------|----------|--------|
| **FIELD LEVEL** | ความถูกต้องรายฟิลด์ของวิชาที่จับคู่ได้ (`name_en`, `credits`, `category`, `type`, `prerequisite`) | Accuracy per field |
| **PAGE LEVEL** | อัตราระบุหน้าเอกสารถูกต้อง (Page Localization Rate) | Found / Total GT |
| **CATEGORY LEVEL** | Recall แยกตามหมวดวิชา (หมวดวิชาเฉพาะ, หมวดวิชาศึกษาทั่วไป) | Recall per category |
| **TYPE LEVEL** | Recall แยกตามประเภทวิชา (บังคับ, เลือก) | Recall per type |

---

## ผลลัพธ์ล่าสุด

> **อัปเดตล่าสุด:** 2026-08-08 | รัน `run_lab6_evaluation.py`

### Field Level + Page Level

| หลักสูตร / แผน | Recall (วิชา) | name_en | credits | category | type | prerequisite | Page Rate |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **DSBA Coop** | 100% (80/80) | 100% | 100% | 100% | 100% | 100% | 100% |
| **DSBA No Coop** | 100% (80/80) | 100% | 100% | 100% | 100% | 100% | 100% |
| **AIT No Coop** | 100% (49/49) | 100% | 100% | 100% | 100% | 100% | 100% |
| **IT Coop** | 100% (99/99) | 100% | 100% | 100% | 100% | 98.99% | 100% |
| **IT No Coop** | 100% (99/99) | 100% | 100% | 100% | 100% | 98.99% | 100% |

> **หมายเหตุ IT:** prerequisite ที่พลาด 1/99 วิชาเกิดจากรูปแบบการอ้างอิงวิชาบังคับก่อน (prerequisite chain) ที่ซับซ้อนในบางวิชา

### หน้าเอกสารที่ครอบคลุม

| หลักสูตร | ช่วงหน้า | จำนวนหน้าที่ใช้ (distinct) |
|----------|----------|--------------------------|
| DSBA Coop / No Coop | 16–356 | 71 หน้า |
| AIT No Coop | 18–303 | 37 หน้า |
| IT Coop / No Coop | 21–378 | 67 หน้า |

รายงานฉบับเต็ม: [`outputs/lab6_final_report.txt`](outputs/lab6_final_report.txt)

---

## ไฟล์และโค้ดที่สำคัญ

| ไฟล์ | บทบาท |
|------|--------|
| [`src/ocr_system/curriculum_extraction.py`](src/ocr_system/curriculum_extraction.py) | สกัดรายวิชาจาก OCR text รองรับ auto-detect สาขา, whitelist, overrides |
| [`src/ocr_system/evaluate_all_levels.py`](src/ocr_system/evaluate_all_levels.py) | Multi-Level Evaluation: Field, Page, Category, Type |
| [`src/ocr_system/evaluate_curriculum.py`](src/ocr_system/evaluate_curriculum.py) | ประเมินผลเบื้องต้น recall + field agreement |
| [`src/ocr_system/page_mapping.py`](src/ocr_system/page_mapping.py) | จับคู่รายวิชากับหน้าเอกสารจาก page mapping CSV |
| [`src/ocr_system/cli.py`](src/ocr_system/cli.py) | CLI interface รองรับ subcommand `ocr`, `evaluate`, `curriculum` |
| [`run_lab6_evaluation.py`](run_lab6_evaluation.py) | รัน evaluation ทุก scenario ครั้งเดียว พร้อมบันทึก summary |
| [`check_notes.py`](check_notes.py) | ตรวจสอบค่า `note` ระหว่าง OCR output กับ Ground Truth |
| [`note_mismatch_only.json`](note_mismatch_only.json) | บันทึกรายการ note ที่ไม่ตรงกัน (ใช้ตรวจสอบและแก้ไข) |

### Ground Truth Files

| ไฟล์ | รายละเอียด |
|------|-----------|
| `data/ground_truth/IT_academic_plan_{plan}.json` | เฉลยรายวิชา IT (coop / no_coop) |
| `data/ground_truth/DSBA_academic_plan_{plan}.json` | เฉลยรายวิชา DSBA (coop / no_coop) |
| `data/ground_truth/AIT_academic_plan.json` | เฉลยรายวิชา AIT |
| `data/ground_truth/general_education_ground_truth.json` | เฉลยหมวดวิชาศึกษาทั่วไป |
| `data/ground_truth/rules_ground_truth.json` | กฎและเงื่อนไขหลักสูตร |
| `data/ground_truth/qa_pairs.csv` | ชุด QA สำหรับ cross-check Lab 5 |
| `data/ground_truth/*_course_page_mapping.csv` | mapping รหัสวิชา ↔ หน้าเอกสาร |

---

## Evaluation สำหรับ OCR ทั่วไป (CER/WER)

```bash
# รัน OCR ก่อน
python -m ocr_system.cli ocr data/input/sample.pdf --engine ensemble

# จากนั้น evaluate เทียบ Ground Truth
python -m ocr_system.cli evaluate data/ground_truth/example_ground_truth.json outputs/sample_ocr.json
```

| Metric | ความหมาย |
|--------|----------|
| `cer` | Character Error Rate — ยิ่งต่ำยิ่งดี |
| `wer` | Word Error Rate — ยิ่งต่ำยิ่งดี |
| `exact_match` | ข้อความตรงทั้งหมดหรือไม่ |

---

## Git Branch

โปรเจกต์นี้ทำงานอยู่บน branch **`lab006`**

```bash
git checkout lab006
git pull origin lab006
```
