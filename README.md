# Bolti Bahi — बोलती बही 🎙️📖
> **Voice-First Rural FinTech & Udhaar Management Assistant for Indian Kirana Shopkeepers**  
> Powered by [Sarvam AI](https://sarvam.ai) (Saaras STT, 105B Conversations, Bulbul TTS)

---

## 🌟 Overview

**Bolti Bahi** is an intuitive, voice-first business and customer credit (*udhaar*) management assistant tailored for small kirana store owners and rural retailers across India.

Instead of writing in paper notebooks or struggling with complex accounting software, shopkeepers simply tap a large microphone button and speak naturally in Hindi, Hinglish, or English.

---

## ⚡ Key Features

- **🎙️ Voice-First Input (Sarvam Saaras STT)**:
  - Speak transactions naturally: *"Ramesh ne 500 rupaye ka udhaar liya."*
  - Instant text-input fallback for loud or quiet environments.

- **🧠 AI Intent & Entity Extraction (Sarvam 105B Conversations)**:
  - Understands customer names, transaction types (`CREDIT` vs `REPAYMENT`), amounts, and item descriptions (*"500 rupees ka Samosa"*).

- **🔍 Voice Balance Inquiry (*बकाया जांचें*)**:
  - Ask: *"Ramesh ka kitna udhaar baaki hai?"*
  - The app inspects the database and **speaks the answer back** instantly.

- **🔊 Spoken Confirmations (Sarvam Bulbul TTS)**:
  - High-fidelity natural voice output confirming every transaction and balance check in Hindi.

- **✅ 1-Tap "पूरा हिसाब चुकता" (Full Settlement)**:
  - Single button to record a full repayment matching the exact outstanding balance.

- **🛡️ Mandatory Confirmation Safeguard**:
  - Never commits financial records without explicit review. Editable inputs for customer name, item, and amount.

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+
- A [Sarvam AI API Key](https://dashboard.sarvam.ai)

### 2. Setup

```bash
# Clone the repository
git clone https://github.com/your-username/bolti-bahi.git
cd bolti-bahi

# Install dependencies
pip install -r requirements.txt

# Configure your API key
cp .env.example .env
# Edit .env and paste your SARVAM_API_KEY
```

### 3. Run the App

```bash
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

Open **`http://localhost:8000`** in your browser (mobile or desktop).

---

## 📁 Project Structure

```
bolti-bahi/
├── app.py                # Single-file FastAPI server & embedded mobile-first UI
├── requirements.txt      # Python dependencies
├── .env.example          # Environment template (keys kept safe)
├── .gitignore            # Git exclusion rules (.env, *.db, __pycache__)
└── README.md             # Project documentation
```

---

## 🛡️ Security & Privacy
- API keys are read strictly from environment variables and never exposed to client-side code.
- SQLite database (`*.db`) and `.env` files are excluded from version control via `.gitignore`.

---

## 📜 License
MIT License. Built with ❤️ for Bharat.
