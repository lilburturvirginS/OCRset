# วิธีพุชไฟล์ขึ้น GitHub (กรณีไม่มี .git)

---

## ครั้งแรก — ตั้งค่า git ในโฟลเดอร์

เปิด PowerShell ในโฟลเดอร์ `isd-2026-OCR-LLM-QNA` แล้วรันตามลำดับ:

```powershell
git init
git remote add group https://github.com/maplecodingfrez/isd-2026-OCR-LLM-QNA.git
git fetch group
git checkout -b lab006x group/lab006x
```

> คำสั่งนี้จะดึง branch `lab006x` จาก repo กลุ่มมาไว้ในเครื่อง พร้อมใช้งานได้เลย

---

## เพิ่ม / แก้ไขไฟล์ แล้วพุชขึ้น

```powershell
git add -A
git commit -m "ใส่ข้อความอธิบายการเปลี่ยนแปลง"
git push group lab006x
```

---

## ดูสถานะไฟล์ที่เปลี่ยนแปลง

```powershell
git status
```

---

## หมายเหตุ

- **ครั้งแรก** ต้องรัน `git init` และ `git remote add` ก่อนเท่านั้น ครั้งต่อไปข้ามไปรัน `git add / commit / push` ได้เลย
- ถ้า GitHub ขอ password ให้ใส่ **Personal Access Token (PAT)** แทนรหัสผ่านปกติ
- PAT สร้างได้ที่: `GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)`
