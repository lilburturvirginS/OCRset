# Thai-English OCR System

โปรเจกต์นี้เป็น OCR pipeline สำหรับเอกสารภาพเดี่ยวและหลายหน้า เช่น `.jpg`, `.png`, `.tif`, `.pdf` โดยรองรับเอกสารภาษาไทยและอังกฤษปนกัน

OCR engines ที่มีให้:

- PaddleOCR: เหมาะกับภาษาไทยและเอกสารทั่วไป
- Tesseract OCR: ใช้ `tha+eng` ได้ดีเมื่อมีภาษาไทย/อังกฤษปนกัน
- TrOCR: OCR แบบ Transformer เหมาะกับ printed English เป็นหลัก
- Ensemble: ใช้ PaddleOCR + Tesseract แล้วรวมผลแบบง่าย

---

## Project Structure

```text
ocr_system/
├── README.md
├── requirements.txt
├── pyproject.toml
├── data/
│   ├── input/                 # ใส่ไฟล์ภาพหรือ PDF ที่ต้องการ OCR
│   └── ground_truth/          # ไฟล์เฉลยสำหรับ evaluate
├── outputs/                   # ผลลัพธ์ OCR และ evaluation
└── src/
    └── ocr_system/
        ├── cli.py             # command line interface
        ├── config.py          # config หลักของระบบ
        ├── document_loader.py # โหลดภาพ / แปลง PDF เป็นภาพ
        ├── preprocessing.py   # resize, denoise, contrast, deskew, threshold
        ├── pipeline.py        # OCR pipeline หลัก
        ├── evaluation.py      # CER, WER, exact match
        ├── field_extraction.py# ดึง field เช่น email, date, id, phone
        ├── schemas.py         # dataclass ของผลลัพธ์
        ├── engine_factory.py  # เลือก OCR engine
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

## ใช้งานผ่าน VS Code 

แนะนำให้ใช้ **VS Code** เพราะเปิดดูโครงสร้างไฟล์ แก้โค้ด และรันคำสั่งใน Terminal ได้ในที่เดียว
---
## วิธีเปิดโปรเจกต์ใน VS Code
1. แตกไฟล์ `ocr_system.zip`
2. จะได้โฟลเดอร์ชื่อ `ocr_system`
3. เปิด VS Code
4. ไปที่เมนู
```text
File > Open Folder
```

5. เลือกโฟลเดอร์ `ocr_system`
6. เปิด Terminal ใน VS Code
```text
Terminal > New Terminal
```
หลังจากนี้ให้พิมพ์คำสั่งต่าง ๆ ใน Terminal ของ VS Code ได้เลย

---

## Installation
แนะนำใช้ Python 3.10 ขึ้นไป
เช็กเวอร์ชัน Python ก่อน:

```bash
python --version
```
หรือบางเครื่องอาจต้องใช้:
```bash
py --version
```
ถ้าเวอร์ชันเป็น Python 3.10, 3.11 หรือ 3.12 สามารถใช้ได้

---

## สร้าง Virtual Environment
Virtual Environment คือพื้นที่แยกสำหรับติดตั้ง package ของโปรเจกต์นี้โดยเฉพาะ เพื่อไม่ให้ชนกับโปรเจกต์อื่น
ให้เข้าไปในโฟลเดอร์โปรเจกต์ก่อน:
```bash
cd ocr_system
```
จากนั้นสร้าง environment:
```bash
python -m venv .venv
```

ถ้าใช้ Windows แล้วคำสั่ง `python` ไม่ได้ ให้ลองใช้:
```bash
py -m venv .venv
```

---

## เปิดใช้งาน Virtual Environment

### Windows CMD
```bash
.venv\Scripts\activate
```

### Windows PowerShell
```bash
.venv\Scripts\Activate.ps1
```

ถ้า PowerShell ขึ้น error เรื่อง policy ให้รัน:
```bash
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

แล้วลอง activate ใหม่อีกครั้ง

### macOS / Linux
```bash
source .venv/bin/activate
```
ถ้าสำเร็จ จะเห็นชื่อ environment ขึ้นต้นบรรทัดประมาณนี้:
```text
(.venv) C:\...\ocr_system>
```

---

## ติดตั้ง Python Packages
หลังจาก activate `.venv` แล้ว ให้ติดตั้ง package ทั้งหมด:
```bash
pip install -r requirements.txt
```

จากนั้นติดตั้งโปรเจกต์แบบ editable:
```bash
pip install -e .
```

คำสั่งนี้ทำให้สามารถเรียกใช้งานโปรเจกต์ด้วยรูปแบบนี้ได้:
```bash
python -m ocr_system.cli
```

---

## Install Tesseract Engine
ในโปรเจกต์นี้มี OCR หลายตัว เช่น PaddleOCR, Tesseract และ TrOCR
แต่สำหรับ Tesseract ต้องติดตั้งโปรแกรม Tesseract OCR แยกต่างหาก เพราะ `pytesseract` เป็นแค่ Python package ที่ใช้เรียกโปรแกรม Tesseract เท่านั้น

---

## ติดตั้ง Tesseract บน Windows
ให้ติดตั้ง Tesseract OCR จาก UB Mannheim build
ระหว่างติดตั้ง ให้เลือกภาษา:
```text
English
Thai
```

หลังติดตั้งเสร็จ ให้เปิด CMD หรือ VS Code Terminal ใหม่ แล้วตรวจสอบ:
```bash
tesseract --version
```

จากนั้นตรวจสอบภาษาที่ติดตั้ง:
```bash
tesseract --list-langs
```
ควรเห็นอย่างน้อย:
```text
eng
tha
```
ถ้าไม่เห็น `tha` แปลว่ายังไม่ได้ติดตั้งภาษาไทย

---

## ติดตั้ง Tesseract บน Ubuntu / Debian
```bash
sudo apt update
sudo apt install tesseract-ocr tesseract-ocr-tha poppler-utils
```
---

## ติดตั้ง Tesseract บน macOS
```bash
brew install tesseract poppler
brew install tesseract-lang
```
หมายเหตุ: `poppler` จำเป็นสำหรับแปลง PDF เป็นภาพผ่าน `pdf2image`

---

## เตรียมไฟล์สำหรับทดสอบ OCR
นำไฟล์เอกสารไปวางในโฟลเดอร์นี้:
```text
data/input/
```

ตัวอย่าง:
```text
data/input/sample.pdf
data/input/sample.jpg
data/input/sample.png
```

รองรับทั้ง:
```text
PDF หลายหน้า
JPG
PNG
TIFF
BMP
```

---

## Usage
### 1. OCR ด้วย Ensemble
Ensemble คือการใช้หลาย OCR engine ช่วยกัน แล้วเลือกผลลัพธ์ที่เหมาะสมที่สุด
เหมาะสำหรับเอกสารที่มีทั้งภาษาไทยและอังกฤษปนกัน

```bash
python -m ocr_system.cli ocr data/input/sample.pdf --engine ensemble
```

หลังรันเสร็จ ผลลัพธ์จะอยู่ในโฟลเดอร์:
```text
outputs/
```

จะได้ไฟล์ประมาณนี้:
```text
outputs/sample_ocr.json
outputs/sample_ocr.txt
outputs/sample_fields.json
outputs/pages/
```

ความหมายของไฟล์:
```text
sample_ocr.json     ผล OCR แบบละเอียด เช่น text, confidence, page
sample_ocr.txt      ข้อความ OCR รวมทั้งหมด อ่านง่าย
sample_fields.json  field ที่ระบบพยายาม extract เช่น วันที่ ชื่อ รหัส
outputs/pages/      ภาพแต่ละหน้าที่แปลงจาก PDF
```

---

## 2. OCR ด้วย PaddleOCR
เหมาะกับเอกสารทั่วไป โดยเฉพาะภาษาไทยและอังกฤษปนกัน
```bash
python -m ocr_system.cli ocr data/input/sample.jpg --engine paddle --paddle-lang th
```
ถ้าเอกสารเป็นอังกฤษล้วน อาจลองใช้:
```bash
python -m ocr_system.cli ocr data/input/sample.jpg --engine paddle --paddle-lang en
```
---
## 3. OCR ด้วย Tesseract ไทย + อังกฤษ
เหมาะกับเอกสาร scan ที่ตัวหนังสือชัด หรือเอกสารราชการ/ฟอร์มที่ layout ไม่ซับซ้อนมาก
```bash
python -m ocr_system.cli ocr data/input/sample.jpg --engine tesseract --languages tha+eng
```

ถ้าเป็นอังกฤษอย่างเดียว:
```bash
python -m ocr_system.cli ocr data/input/sample.jpg --engine tesseract --languages eng
```

ถ้าเป็นไทยอย่างเดียว:
```bash
python -m ocr_system.cli ocr data/input/sample.jpg --engine tesseract --languages tha
```

---

## 4. OCR ด้วย TrOCR
TrOCR เป็นโมเดล OCR จาก Transformer
ในโปรเจกต์นี้ใช้เป็น fallback สำหรับข้อความสั้น ๆ หรือภาพที่ crop เป็นบรรทัดแล้ว
```bash
python -m ocr_system.cli ocr data/input/sample.jpg --engine trocr --device cpu
```
ถ้ามี GPU และติดตั้ง PyTorch แบบ CUDA แล้ว สามารถใช้:
```bash
python -m ocr_system.cli ocr data/input/sample.jpg --engine trocr --device cuda
```
หมายเหตุ: TrOCR ในโปรเจกต์นี้ยังไม่เหมาะกับเอกสารยาวทั้งหน้า แนะนำใช้ PaddleOCR หรือ Tesseract เป็นหลัก

---
## Evaluation
Evaluation คือการวัดว่า OCR อ่านถูกแค่ไหน โดยเทียบกับข้อความจริง หรือ Ground Truth
สร้างไฟล์ ground truth เช่น:
```text
data/ground_truth/example_ground_truth.json
```

ตัวอย่างเนื้อหา:
```json
{
  "sample.pdf": "ข้อความจริงทั้งหมดในเอกสาร sample.pdf",
  "sample.jpg": "ข้อความจริงในเอกสาร sample.jpg"
}
```

จากนั้นรัน OCR ก่อน:
```bash
python -m ocr_system.cli ocr data/input/sample.pdf --engine ensemble
```
แล้ว evaluate:
```bash
python -m ocr_system.cli evaluate data/ground_truth/example_ground_truth.json outputs/sample_ocr.json
```

Metric ที่ได้:

```text
cer           Character Error Rate ยิ่งต่ำยิ่งดี
wer           Word Error Rate ยิ่งต่ำยิ่งดี
exact_match   ข้อความตรงทั้งหมดหรือไม่
```

ตัวอย่างการอ่านผล:
```text
CER = 0.05 หมายถึงผิดประมาณ 5% ระดับตัวอักษร
WER = 0.12 หมายถึงผิดประมาณ 12% ระดับคำ
exact_match = false หมายถึงยังไม่ตรง 100%
```
---

## คำสั่งที่ใช้บ่อย
OCR ไฟล์ PDF ด้วยระบบรวม:
```bash
python -m ocr_system.cli ocr data/input/sample.pdf --engine ensemble
```

OCR รูปภาพด้วย PaddleOCR:
```bash
python -m ocr_system.cli ocr data/input/sample.jpg --engine paddle --paddle-lang th
```

OCR รูปภาพด้วย Tesseract:
```bash
python -m ocr_system.cli ocr data/input/sample.jpg --engine tesseract --languages tha+eng
```

Evaluate ผล OCR:
```bash
python -m ocr_system.cli evaluate data/ground_truth/example_ground_truth.json outputs/sample_ocr.json
```

---

## Recommended Engine

สำหรับเอกสารไทย+อังกฤษปนกัน แนะนำเริ่มจาก:
```bash
python -m ocr_system.cli ocr data/input/sample.pdf --engine ensemble --languages tha+eng --paddle-lang th --save-debug-images
```

ถ้าเอกสารเป็นอังกฤษเกือบทั้งหมด:
```bash
python -m ocr_system.cli ocr data/input/sample.pdf --engine paddle --paddle-lang en
```

ถ้า Tesseract อ่านไทยเพี้ยน ให้ลอง OCR แบบไม่ preprocess:
```bash
python -m ocr_system.cli ocr data/input/sample.jpg --engine tesseract --no-preprocess
```

---

## Output JSON Format
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

---

# Lab 4 — OCR Baseline & Field-Level Evaluation

Lab 4 คือการทดสอบว่า OCR อ่านเล่มหลักสูตร PDF (มคอ.2) ของ DSBA ได้ถูกต้องแค่ไหน โดยวัดระดับ field (ชื่อวิชา, หน่วยกิต, หมวดวิชา ฯลฯ) ไม่ใช่แค่ดูข้อความรวม

---

## สิ่งที่ต้องเตรียม

- ไฟล์ PDF หลักสูตร ใส่ไว้ที่ `data/`
- ไฟล์ Ground Truth (ข้อมูลเฉลย): `DSBA_academic_plan_coop.json`
- ติดตั้ง package แล้ว (ทำตามขั้นตอน Lab 3)

---

## รัน Evaluation

```bash
python run_lab6_evaluation.py
```

ระบบจะ:
1. โหลด OCR output และ Ground Truth
2. จับคู่วิชาด้วยรหัสวิชา
3. วัด field-level accuracy แยกรายฟิลด์
4. คำนวณ Precision, Recall, F1
5. บันทึกผลเป็น `evaluation_all_levels.json`

---

## ดูผลลัพธ์

ผลจะอยู่ในไฟล์ `evaluation_all_levels.json`

```bash
python -c "import json; d=json.load(open('evaluation_all_levels.json')); print(json.dumps(d, indent=2, ensure_ascii=False))"
```

ตัวอย่างผลที่ได้:

```text
name_en      100%
credits      100%
category     100%
type         100%
prerequisite 97.5%
Page Recall  98.75%  (79/80 วิชา)
```

---

## ปัญหาที่พบ — MacThai PUA Font Bug

ถ้าข้อความภาษาไทยใน output ออกมาเป็นสัญลักษณ์แปลก ๆ เช่น `ï¿½` หรือเป็นกล่องสี่เหลี่ยม นั่นคือ **MacThai PUA Font Bug**

PDF ถูกสร้างด้วยฟอนต์ MacThai ที่เก็บสระและวรรณยุกต์ไว้ใน Private Use Area (`0xF700–0xF71A`) แทน Unicode ไทยมาตรฐาน (`0x0E00–0x0E7F`)

วิธีแก้ด้วย Python:
```python
THAI_PUA_MAP = {
    0xF700: "\u0E11", 0xF701: "\u0E12", 0xF702: "\u0E24",
    0xF705: "\u0E31", 0xF706: "\u0E34", 0xF707: "\u0E35",
    0xF70A: "\u0E48", 0xF70B: "\u0E49", 0xF70E: "\u0E4C",
}
def fix_thai_pua(text: str) -> str:
    return "".join(THAI_PUA_MAP.get(ord(c), c) for c in text)
```

---

## ความหมายของ Metric

```text
Precision    จากที่สกัดมาทั้งหมด มีกี่ % ที่ถูก
Recall       จากที่ควรสกัดได้ทั้งหมด สกัดได้กี่ %   (ยิ่งต่ำ = ตกหล่นเยอะ)
F1           ค่าเฉลี่ยระหว่าง Precision และ Recall
```

---

# Lab 5 — สร้าง Q&A Dataset

Lab 5 คือการสร้างชุดคำถาม-คำตอบภาษาไทยจากเนื้อหาเล่มหลักสูตร เพื่อใช้เป็น benchmark ทดสอบระบบตอบคำถามใน Lab 8B

---

## ไฟล์ที่ได้

```text
lab5_qa_combined.csv
```

มี **27 คู่ Q&A** ครอบคลุม 5 ประเภทคำถาม:

```text
ประเภทที่ 1  คำถามเกี่ยวกับหน่วยกิตและปี/ภาค
ประเภทที่ 2  คำถามเกี่ยวกับรหัสวิชาและชื่อ
ประเภทที่ 3  คำถามเกี่ยวกับ prerequisite (วิชาบังคับก่อน)
ประเภทที่ 4  คำถามเกี่ยวกับหมวดวิชาและประเภท (บังคับ/เลือก)
ประเภทที่ 5  คำถามเปรียบเทียบหลายวิชา
```

---

## โครงสร้าง CSV

```text
question     คำถามภาษาไทย
answer       คำตอบที่ถูกต้อง
course_codes รหัสวิชาที่เกี่ยวข้อง
page_ref     เลขหน้าในเล่มหลักสูตร
clause_ref   ข้อที่ในมคอ.2
note         หมายเหตุเพิ่มเติม
```

ตัวอย่าง:

```text
"วิชาแคลคูลัส 1 มีกี่หน่วยกิต เรียนปี/เทอมใด"  →  "3(3-0-6) ปี 1 เทอม 1"
"วิชา 06026216 เป็นบังคับหรือเลือก"              →  "วิชาเลือก"
```

---

## ดูไฟล์ CSV

```bash
python -c "import csv; [print(r) for r in csv.DictReader(open('lab5_qa_combined.csv', encoding='utf-8'))]"
```

---

# Lab 6 — Evaluation Framework & Metrics Design

Lab 6 คือการออกแบบระบบวัดผลที่เหมาะสม ใช้ Script เดียวกันกับ Lab 4 แต่ขยายให้ครอบคลุมมากขึ้น

---

## รัน Evaluation (เหมือน Lab 4)

```bash
python run_lab6_evaluation.py
```

---

## ความแตกต่างจาก Lab 4

Lab 6 เพิ่ม:
- แยก category_level (หมวดวิชาเฉพาะ vs หมวดศึกษาทั่วไป)
- ระบุว่า error มาจาก (ก) โมเดลสกัดผิด หรือ (ข) Ground Truth ผิดเอง
- วัด Precision/Recall แยก ไม่ใช่แค่ accuracy รวม

---

## อ่านผล

```bash
python -c "
import json
d = json.load(open('evaluation_all_levels.json'))
for k, v in d.items():
    print(k, ':', v)
"
```

---

# Lab 7A — OCR บนภาพเอกสาร Noisy

Lab 7A คือการทดสอบว่า OCR ทำงานได้ดีแค่ไหนเมื่อเอกสารมีคุณภาพต่ำลง โดยเพิ่ม Synthetic Noise 4 ระดับลงบนภาพต้นฉบับ

---

## สิ่งที่ต้องเตรียม

- โมเดล `scb10x/typhoon-ocr1.5-3b` (VLM สำหรับ OCR)
- Ollama ติดตั้งแล้วและรันอยู่:

```bash
ollama pull scb10x/typhoon-ocr1.5-3b
ollama serve
```

---

## 5 ระดับ Noise ที่ทดสอบ

```text
L0_clean      ต้นฉบับดิจิทัล ไม่มี noise             0°
L1_light      สแกนคุณภาพดี                          0.4°
L2_watermark  ถ่ายด้วยมือถือ มีลายน้ำ                 1.1°
L3_tilted     ถ่ายเอกสารซ้ำจากสำเนา                 2.3°
L4_rescan     เครื่องถ่ายเก่า คุณภาพต่ำ               3.8°
```

---

## Pipeline ที่รัน

```
ภาพ L0–L4
   ↓
OpenCV Pre-processing:
   1. Deskew          ← ต้องทำก่อนเสมอ ห้ามสลับลำดับ
   2. Background Division
   3. Denoising
   4. Binarization
   ↓
typhoon-ocr1.5-3b
   ↓
CER / WER เทียบ Ground Truth
```

---

## รัน Metrics

```bash
python lab7_metrics.py
```

ผลจะแสดง CER/WER แยกแต่ละระดับ Noise

---

## ตีความผล

```text
CER (Character Error Rate)   ยิ่งต่ำยิ่งดี
WER (Word Error Rate)        ยิ่งต่ำยิ่งดี

Breaking Point = ระดับที่ค่าพุ่งสูงชัดเจน (โดยทั่วไปคือ L3–L4)
```

---

## ข้อควรรู้

ถ้า PDF มีข้อความฝังอยู่แล้ว (text-based PDF) ให้ใช้ `pdfplumber` ดึงข้อความตรง ๆ แทน OCR เพราะ:
- เร็วกว่ามาก
- แม่นยำกว่าเสมอ (ข้อความที่ฝังไม่มีทางผิด)

ตรวจก่อนด้วย:
```python
import pdfplumber
with pdfplumber.open("data/DSBA.pdf") as pdf:
    for i in range(min(3, len(pdf.pages))):
        text = pdf.pages[i].extract_text()
        print(f"หน้า {i+1}: {len(text or '')} ตัวอักษร")
        if text:
            print(text[:200])
```

ถ้าได้ข้อความออกมา → ใช้ pdfplumber ไม่ต้อง OCR

---

# Lab 7B — สกัดข้อมูลหลักสูตรจาก PDF ด้วย Local LLM

Lab 7B คือการใช้ LLM ที่รันบนเครื่องเอง (ผ่าน Ollama) สกัดข้อมูลรายวิชาจาก PDF มคอ.2 ออกมาเป็น JSON

---

## สิ่งที่ต้องเตรียม

ติดตั้ง Ollama และดึงโมเดล:

```bash
ollama pull qwen3:4b
ollama pull scb10x/typhoon-ocr1.5-3b
ollama serve
```

ตรวจสอบว่า Ollama รันอยู่:
```bash
curl http://localhost:11434/api/tags
```

---

## เช็กสเปกเครื่องก่อนรัน

| RAM | GPU | ความเร็วโดยประมาณ |
|-----|-----|------------------|
| 8 GB, ไม่มี GPU | — | 5–10 นาที/หน้า |
| 16 GB, ไม่มี GPU | — | 1–3 นาที/หน้า |
| GPU 8 GB VRAM+ | — | 10–30 วินาที/หน้า |
| Mac Apple Silicon 16 GB | — | 20–60 วินาที/หน้า |

> **คำนวณก่อนรัน:** ถ้าหลักสูตรมี 120 หน้า และเครื่องใช้ 2 นาที/หน้า = **4 ชั่วโมง**  
> ดังนั้นให้ใช้ `--pages` เลือกเฉพาะหน้าตารางแผนการศึกษา (โดยทั่วไปประมาณ 10–20 หน้า)

---

## รัน Extraction

```bash
# สกัด DSBA เฉพาะหน้า 5-18 (ตารางแผนการศึกษา)
python lab7b_curriculum.py --curriculum dsba_coop --pages 5-18

# สกัด IT Coop
python lab7b_curriculum.py --curriculum it_coop --pages 5-20

# สกัด AIT
python lab7b_curriculum.py --curriculum ait --pages 4-15
```

---

## ผลลัพธ์

ไฟล์จะถูกสร้างที่:
```text
output/lab7b_fixed/
    dsba_coop/
        pred_text.json      ← JSON รายวิชาทั้งหมด
        evaluation.json     ← ผลเทียบ Ground Truth รายฟิลด์
        comparison.csv      ← ตาราง diff แสดงสิ่งที่สกัดผิด/ถูก
    it_coop/
        (เช่นเดียวกัน)
    ait/
        (เช่นเดียวกัน)
```

---

## ดูผล Evaluation

```bash
python -c "
import json
d = json.load(open('output/lab7b_fixed/dsba_coop/evaluation.json'))
print(f'Recall:    {d[\"recall\"]:.1%}')
print(f'Precision: {d[\"precision\"]:.1%}')
print(f'F1:        {d[\"f1\"]:.3f}')
"
```

---

## ปัญหาที่พบบ่อยและวิธีแก้

**ปัญหา: ภาษาไทยในผลเป็นสัญลักษณ์แปลก**
→ MacThai PUA Font Bug (ดูวิธีแก้ใน Lab 4)

**ปัญหา: LLM สกัดวิชาปนกันระหว่างภาคเรียน**
→ ระบบแก้ด้วย Multi-Semester Chunking: ผ่าหน้าที่มีหลายภาคออก แล้วส่ง LLM ทีละภาค

**ปัญหา: Recall ต่ำกว่า 70%**
→ ตรวจสอบ `--pages` ว่าครอบคลุมหน้าที่มีตารางแผนครบหรือไม่

---

# Lab 8B — NL-to-SQL: ถามภาษาไทย ตอบจากฐานข้อมูล

Lab 8B คือการสร้างระบบให้คนถามคำถามภาษาไทยธรรมดา แล้วระบบแปลงเป็น SQL ค้นหาข้อมูลจากฐานข้อมูลหลักสูตร และตอบกลับเป็นภาษาไทย

ตัวอย่าง:
```text
ถาม:  "ปีที่ 2 เทอม 1 นักศึกษาต้องเรียนกี่หน่วยกิต"
ตอบ:  "15 หน่วยกิต"
```

---

## สิ่งที่ต้องเตรียม

ติดตั้ง Ollama และดึงโมเดล 2 ตัว:

```bash
ollama pull qwen2.5-coder:7b
ollama pull qwen3:4b
ollama serve
```

- `qwen2.5-coder:7b` — ใช้แปลงคำถามภาษาไทยเป็น SQL (Tier 1)
- `qwen3:4b` — ใช้แปลงผลลัพธ์จาก DB กลับเป็นคำตอบภาษาไทย (Tier 2)

---

## ขั้นตอนที่ 1 — สร้าง Schema ฐานข้อมูล

```bash
python src/ocr_system/lab8b_curriculum_db.py schema
```

จะได้ไฟล์:
```text
work/lab8b_run/schema/schema.sql              ← DDL สร้างตาราง 4 ตาราง + 2 Views
work/lab8b_run/schema/curriculum.schema.json  ← JSON Schema สำหรับ validate ข้อมูล
```

โครงสร้างตารางที่สร้าง:
```sql
program      (program_id, name_th, name_en, degree, total_credits, years)
course       (code, name_th, name_en, credits, lecture_h, lab_h, self_h)
plan_item    (id, program_id, year, semester, code, credits, alt_group, note)
prerequisite (code, requires, kind)
```

---

## ขั้นตอนที่ 2 — โหลดข้อมูลเข้า Database

```bash
python src/ocr_system/lab8b_curriculum_db.py load
```

ผลลัพธ์:
```text
program        1 แถว
course        80 แถว
plan_item     37 แถว
prerequisite   5 แถว
```

ไฟล์ Database อยู่ที่: `app/data/dsba_coop.db`

---

## ขั้นตอนที่ 3 — ตรวจความถูกต้อง 7 กฎ

```bash
python src/ocr_system/lab8b_curriculum_db.py verify
```

ผลจะอยู่ที่ `work/lab8b_run/verify.json`

กฎที่ตรวจ:
```text
CHK1  ผลรวมหน่วยกิตแผน = ที่ประกาศไว้
CHK2  ทุก code ในแผนมีคำอธิบาย
CHK3  รหัสวิชา = ตัวเลข 8 หลัก
CHK4  หน่วยกิตในแผน = ในคำอธิบาย
CHK5  prerequisite อยู่ภาคก่อนวิชาที่อ้างถึง
CHK6  ไม่มีวิชาซ้ำในเทอมเดียวกัน
CHK7  หน่วยกิตต่อเทอม อยู่ระหว่าง 9–22
```

---

## ขั้นตอนที่ 4 — ถามคำถามภาษาไทย

ถามคำถามเดี่ยว:
```bash
python src/ocr_system/lab8b_curriculum_db.py ask -q "ปีที่ 2 เทอม 1 เรียนกี่หน่วยกิต"
python src/ocr_system/lab8b_curriculum_db.py ask -q "วิชา 06026200 ชื่อว่าอะไร"
python src/ocr_system/lab8b_curriculum_db.py ask -q "วิชา 06026201 ต้องเรียนวิชาอะไรก่อน"
```

---

## ขั้นตอนที่ 5 — รัน Evaluation ครบ 30 ข้อ

```bash
python src/ocr_system/lab8b_curriculum_db.py eval
```

ผลจะอยู่ที่ `work/lab8b_run/eval_result.json`

---

## ขั้นตอนที่ 6 — รัน Web App

```bash
uvicorn app.main:app --reload
```

เปิดเบราว์เซอร์:
```text
http://localhost:8000
```

พิมพ์คำถามภาษาไทยในช่องค้นหา แล้วรอรับคำตอบ

---

## ไฟล์สำคัญทั้งหมดของ Lab 8B

```text
work/lab8b_run/
    schema/schema.sql           DDL สร้างตาราง + VIEW
    curriculum.json             ข้อมูลหลักสูตรที่โหลดเข้า DB
    verify.json                 ผล 7 กฎ
    gold_questions.json         30 คำถามทดสอบ + คำตอบ
    eval_result.json            ผลการรัน (SQL 100%, ตอบถูก 97%)

app/
    main.py                     FastAPI Backend
    index.html                  หน้าเว็บสำหรับถามคำถาม
    data/dsba_coop.db           SQLite Database
```

---

## ผลสุดท้าย

```text
SQL รันผ่าน   30/30   100%
ตอบถูก        29/30    97%
เวลาเฉลี่ย    ~0.6 วินาที/คำถาม (โมเดลโหลดอยู่แล้ว)
```

---
