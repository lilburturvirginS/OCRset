# แนวทางสกัด Lab 7B ใหม่ แล้วต่อ Lab 8B

---

## ข้อเท็จจริงก่อน — pred_text.json ของเราดีแค่ไหน?

ก่อนเริ่มสกัดใหม่ ควรรู้ว่าปัญหาจริง ๆ คืออะไร:

```
pred_text.json ปัจจุบัน:
  มี year/semester ชัดเจน:  50 วิชา  ✅
  ไม่มี (wildcard/flexible): 49 วิชา  ⚠️ (แต่เป็นแบบนั้นจริงในเล่ม)
```

**วิชา 49 ตัวที่ไม่มี year/semester แบ่งเป็น 2 กลุ่ม:**
- **วิชา wildcard** (`90644xxx`, `xxxxxxxx`) → เป็นวิชาเลือกที่ยังไม่กำหนดรหัสจริงในเล่ม → ไม่มีทางสกัดได้
- **วิชาเลือก flexible** (เช่น `06026226`) → มีรหัสจริง แต่เลือกเรียนได้หลายเทอม (`3/1, 3/2, 4/1`) → สกัดได้

**สรุป:** ถ้าจะสกัดใหม่ จุดที่แก้ได้จริงคือ **วิชา flexible** ให้ระบุ year/semester ให้ครบ

---

## Format ที่ Lab 8B ต้องการจาก pred_text.json

ไฟล์ต้องเป็น JSON มีโครงสร้างดังนี้:

```json
{
  "program": {
    "program_id": "DSBA-coop",
    "name_th": "วิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ (สหกิจศึกษา)",
    "total_credits": 135,
    "years": 4
  },
  "courses": [
    {
      "code": "06026200",
      "name_th": "แคลคูลัส 1",
      "name_en": "CALCULUS 1",
      "credits": "3(3-0-6)",
      "year": 1,
      "semester": 1,
      "prerequisite": "ไม่มี",
      "flexible_year_semester": null,
      "category": "หมวดวิชาเฉพาะ",
      "type": "บังคับ"
    },
    ...
  ]
}
```

> **Field ที่สำคัญที่สุด:** `code` (8 หลัก), `year`, `semester`, `credits`

---

## สิ่งที่ต้องระวังเมื่อสกัดใหม่

### ✅ สกัดให้ได้ครบ

| Field | ตัวอย่าง | หมายเหตุ |
|-------|---------|---------|
| `code` | `06026200` | ต้องเป็นตัวเลข 8 หลักเท่านั้น |
| `year` | `1`, `2`, `3`, `4` | ปีที่ในแผนการเรียน |
| `semester` | `1`, `2` | เทอมที่ |
| `credits` | `3(3-0-6)` | หน่วยกิต รูปแบบ `n(l-b-s)` |
| `prerequisite` | `06026200` หรือ `ไม่มี` | รหัสวิชาที่ต้องเรียนก่อน |
| `flexible_year_semester` | `"3/1, 3/2"` | กรณีวิชาเลือกระบุตัวเลือกที่นี่ |

### ⚠️ กรณีพิเศษที่ต้องจัดการ

1. **วิชา wildcard** → ปล่อยให้ `year=0, semester=0` ได้ ระบบจะข้ามให้เอง
2. **วิชามีหลายรหัส** เช่น `06026259 หรือ 06026260` → สกัดเป็น 2 entry แยกกัน
3. **วิชา flexible** ที่เลือกเทอมได้ → ใส่ `year=0, semester=0` แล้วระบุใน `flexible_year_semester`

---

## ขั้นตอน Lab 7B → Lab 8B แบบเต็ม

### Step 1: สกัดใหม่จาก Lab 7B

แก้ prompt หรือรัน pipeline ของ Lab 7B ให้ได้ output ที่สมบูรณ์:

```bash
# รัน Lab 7B pipeline ของคุณ
# ตรวจสอบว่า output มี year/semester ครบ
python -c "
import json
data = json.load(open('output/merged_coop/pred_text.json', encoding='utf-8'))
courses = data['courses']
has = [c for c in courses if c.get('year') and int(str(c.get('year',0))) > 0]
print(f'วิชาที่มี year/semester: {len(has)}/{len(courses)}')
"
```

> **เป้าหมาย:** วิชาที่มี year/semester ควรมากกว่า 35 รายการ (ปัจจุบันเราได้ 50)

---

### Step 2: copy ไปที่ work/lab7b_run/

```bash
# สร้าง folder และ copy
mkdir -p work/lab7b_run
cp output/merged_coop/pred_text.json work/lab7b_run/pred_markdown.json
```

> `run_lab8b.py` จะหาไฟล์ที่ `work/lab7b_run/pred_markdown.json`

---

### Step 3: รัน Lab 8B ทั้งหมด

```bash
# เปิด Ollama ก่อน (Terminal แยก)
ollama serve

# รัน Lab 8B โดย skip Lab 7B (เพราะเราเตรียม pred_markdown.json ไว้แล้ว)
python run_lab8b.py --skip-lab7
```

ถ้าต้องการรันทีละ step เพื่อ debug:

```bash
# 1) สร้าง schema
python src/ocr_system/lab8b_curriculum_db.py schema -o work/lab8b_run/schema

# 2) แปลง Lab 7B JSON → Lab 8B format
python src/ocr_system/lab8b_curriculum_db.py import-lab7b \
  -i work/lab7b_run/pred_markdown.json \
  -o work/lab8b_run/curriculum.json \
  --program-id "DSBA-coop" \
  --program-name "วิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ (สหกิจศึกษา)" \
  --total-credits 135 \
  --years 4

# 3) โหลดเข้า SQLite
python src/ocr_system/lab8b_curriculum_db.py load \
  -i work/lab8b_run/curriculum.json \
  -d work/lab8b_run/curriculum.db --replace

# 4) ตรวจ 7 กฎ
python src/ocr_system/lab8b_curriculum_db.py verify \
  -d work/lab8b_run/curriculum.db \
  -o work/lab8b_run/verify.json

# 5) รัน evaluation
python src/ocr_system/lab8b_curriculum_db.py eval \
  -d work/lab8b_run/curriculum.db \
  -q work/lab8b_run/gold_questions.json \
  -o work/lab8b_run/eval_result.json
```

---

### Step 4: ตรวจ verify.json และเพิ่ม classification

หลังรัน verify แล้ว เปิด `work/lab8b_run/verify.json` และเพิ่ม field ด้วยมือสำหรับข้อที่ไม่ผ่าน:

```json
{
  "id": "CHK1",
  "ok": false,
  "detail": "...",
  "classification": "(ข)",
  "classification_detail": "อธิบายว่าทำไมถึงเป็นแบบนี้..."
}
```

ตัวเลือก:
- `"(ก)"` — สกัดผิด ต้องกลับไปแก้ prompt
- `"(ข)"` — เอกสารต้นทางเป็นแบบนั้น ต้องแก้กฎ

---

### Step 5: ตรวจผล evaluation

```bash
python -c "
import json
res = json.load(open('work/lab8b_run/eval_result.json', encoding='utf-8'))
ok = sum(1 for r in res if r['correct'])
sql_ok = sum(1 for r in res if r.get('error') is None)
print(f'SQL รันผ่าน: {sql_ok}/{len(res)}')
print(f'ตอบถูก: {ok}/{len(res)}')
wrong = [r for r in res if not r['correct']]
for r in wrong:
    print(f'  [{r[\"id\"]}] {r[\"question\"][:40]} → {r[\"why\"]}')
"
```

---

## เป้าหมายที่ควรได้

| ตัวชี้วัด | เป้าหมาย |
|----------|---------|
| วิชาในแผน (plan_item) | ≥ 35 รายการ |
| verify ผ่าน | ≥ 5/7 |
| SQL รันผ่าน | 100% |
| ตอบถูก | ≥ 80% |

---

## หมายเหตุ: ทำไม 37 วิชาในแผนถึงพอ

เล่มหลักสูตร DSBA สหกิจมีวิชาบังคับในแผน 35 วิชา + วิชาสหกิจ 2 วิชา = 37 รายการ ส่วนที่เหลือเป็นวิชาเลือก (flexible) ที่นักศึกษาเลือกเองตามเงื่อนไข ซึ่งไม่กำหนดในแผนตายตัว ดังนั้น **37 plan_item ที่เราได้คือถูกต้องแล้ว**
