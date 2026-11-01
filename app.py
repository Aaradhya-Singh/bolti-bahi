import os
import io
import json
import sqlite3
import re
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment
load_dotenv()
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")

# Initialize Sarvam SDK
client = None
if SARVAM_API_KEY:
    try:
        from sarvamai import SarvamAI
        client = SarvamAI(api_subscription_key=SARVAM_API_KEY)
    except Exception as e:
        print(f"Warning: could not initialize SarvamAI: {e}")

# Database Setup
DB_PATH = os.path.join(os.path.dirname(__file__), "bolti_bahi.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE COLLATE NOCASE,
        phone TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        customer_name TEXT NOT NULL,
        transaction_type TEXT NOT NULL, -- 'CREDIT' or 'REPAYMENT'
        amount REAL NOT NULL,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(customer_id) REFERENCES customers(id)
    )
    """)
    conn.commit()
    conn.close()

init_db()

app = FastAPI(title="Bolti Bahi — बोलती बही", description="Voice-first Rural FinTech Udhaar Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def calculate_customer_balances():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers ORDER BY name ASC")
    customers = cursor.fetchall()
    
    result = []
    total_shop_credit = 0.0
    
    for c in customers:
        cursor.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN transaction_type = 'CREDIT' THEN amount ELSE 0 END), 0) as total_credit,
                COALESCE(SUM(CASE WHEN transaction_type = 'REPAYMENT' THEN amount ELSE 0 END), 0) as total_repayment
            FROM transactions 
            WHERE customer_id = ?
        """, (c["id"],))
        row = cursor.fetchone()
        tot_credit = float(row["total_credit"])
        tot_repay = float(row["total_repayment"])
        balance = tot_credit - tot_repay
        total_shop_credit += balance
        
        result.append({
            "id": c["id"],
            "name": c["name"],
            "phone": c["phone"] or "",
            "total_credit": tot_credit,
            "total_repayment": tot_repay,
            "balance": balance,
            "created_at": c["created_at"]
        })
        
    conn.close()
    return result, total_shop_credit

def get_customer_balance_by_name(name: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, phone FROM customers WHERE name = ? COLLATE NOCASE", (name.strip(),))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None, 0.0
    
    cust_id = row["id"]
    cust_name = row["name"]
    cursor.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN transaction_type = 'CREDIT' THEN amount ELSE 0 END), 0) -
            COALESCE(SUM(CASE WHEN transaction_type = 'REPAYMENT' THEN amount ELSE 0 END), 0) as balance
        FROM transactions 
        WHERE customer_id = ?
    """, (cust_id,))
    bal_row = cursor.fetchone()
    balance = float(bal_row["balance"]) if bal_row else 0.0
    conn.close()
    return cust_name, balance

# Pydantic models
class IntentRequest(BaseModel):
    text: str
    language: Optional[str] = "hi-IN"

class CustomerCreate(BaseModel):
    name: str
    phone: Optional[str] = None

class TransactionConfirm(BaseModel):
    customer_name: str
    transaction_type: str # 'CREDIT' or 'REPAYMENT'
    amount: float
    notes: Optional[str] = ""
    phone: Optional[str] = None

class SpeakRequest(BaseModel):
    text: str
    language: Optional[str] = "hi-IN"

# ==================== API ENDPOINTS ====================

@app.get("/api/dashboard")
def get_dashboard():
    customers, total_credit = calculate_customer_balances()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.*, c.name as customer_name, c.phone as customer_phone
        FROM transactions t
        JOIN customers c ON t.customer_id = c.id
        ORDER BY t.created_at DESC
        LIMIT 10
    """)
    txns = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return {
        "total_credit": total_credit,
        "customer_count": len(customers),
        "customers": customers,
        "recent_transactions": txns
    }

@app.get("/api/customers")
def get_customers():
    customers, _ = calculate_customer_balances()
    return customers

@app.post("/api/customers")
def create_customer(data: CustomerCreate):
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Customer name cannot be empty")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO customers (name, phone) VALUES (?, ?)", (name, data.phone or ""))
        conn.commit()
        customer_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        cursor.execute("SELECT id FROM customers WHERE name = ? COLLATE NOCASE", (name,))
        customer_id = cursor.fetchone()["id"]
        if data.phone:
            cursor.execute("UPDATE customers SET phone = ? WHERE id = ?", (data.phone, customer_id))
            conn.commit()
    conn.close()
    
    return {"id": customer_id, "name": name, "phone": data.phone or "", "status": "success"}

# 1-TAP "पूरा हिसाब चुकता" (Full Settlement)
@app.post("/api/customers/{customer_id}/settle")
def settle_customer_balance(customer_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM customers WHERE id = ?", (customer_id,))
    cust = cursor.fetchone()
    if not cust:
        conn.close()
        raise HTTPException(status_code=404, detail="Customer not found")
    
    cust_name = cust["name"]
    cursor.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN transaction_type = 'CREDIT' THEN amount ELSE 0 END), 0) -
            COALESCE(SUM(CASE WHEN transaction_type = 'REPAYMENT' THEN amount ELSE 0 END), 0) as balance
        FROM transactions 
        WHERE customer_id = ?
    """, (customer_id,))
    current_balance = float(cursor.fetchone()["balance"])
    
    if current_balance <= 0:
        conn.close()
        return {
            "status": "already_settled",
            "customer_name": cust_name,
            "new_balance": 0.0,
            "spoken_text": f"{cust_name} का कोई उधार बाकी नहीं है।"
        }
    
    # Record repayment matching exact balance
    cursor.execute("""
        INSERT INTO transactions (customer_id, customer_name, transaction_type, amount, notes)
        VALUES (?, ?, 'REPAYMENT', ?, 'पूरा हिसाब चुकता')
    """, (customer_id, cust_name, current_balance))
    conn.commit()
    conn.close()
    
    spoken_text = f"{cust_name} का पूरा ₹{int(current_balance)} का हिसाब चुकता कर दिया गया है। अब बाकी उधार शून्य है।"
    
    audio_base64 = None
    if client:
        try:
            tts = client.text_to_speech.convert(
                text=spoken_text,
                language_code="hi-IN",
                speaker="ritu",
                model="bulbul:v3"
            )
            if tts.audios:
                audio_base64 = tts.audios[0]
        except Exception as e:
            print(f"TTS error on settle: {e}")
            
    return {
        "status": "settled",
        "customer_name": cust_name,
        "amount_settled": current_balance,
        "new_balance": 0.0,
        "spoken_text": spoken_text,
        "audio_base64": audio_base64
    }

@app.get("/api/transactions")
def get_transactions():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.*, c.name as customer_name, c.phone as customer_phone
        FROM transactions t
        JOIN customers c ON t.customer_id = c.id
        ORDER BY t.created_at DESC
    """)
    txns = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return txns

# VOICE INTENT EXTRACTION + BALANCE INQUIRY
@app.post("/api/extract-intent")
def extract_intent(req: IntentRequest):
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    prompt = f"""You are the core AI of Bolti Bahi (बोलती बही), an udhaar ledger assistant for Indian kirana shopkeepers.
Analyze the user's spoken or typed sentence in Hindi, Marathi, Hinglish, or English.
Input: "{text}"

Extract:
1. customer_name: Person's name (e.g. 'Ramesh', 'Suresh')
2. amount: Number in INR or null
3. transaction_type: 
   - 'CHECK_BALANCE' if user is asking how much udhaar/dues are pending (e.g. "Ramesh ka kitna udhaar baaki hai", "kitna baaki hai", "kitna paisa baki hai")
   - 'CREDIT' if user records credit/goods taken (e.g. "udhaar liya", "likh do", "500 ka udhaar")
   - 'REPAYMENT' if user records payment returned (e.g. "wapas kiye", "jama kar diye", "diye")
4. item: The item/goods purchased if mentioned (e.g. 'Samosa', 'Chawal'), or null
5. is_ambiguous: true if customer_name is missing, or if amount is missing when transaction_type is CREDIT/REPAYMENT
6. clarification_message: A friendly short sentence in Hindi.

Return ONLY valid JSON without markdown:
{{"customer_name": "Ramesh", "amount": 500, "transaction_type": "CREDIT", "item": null, "is_ambiguous": false, "clarification_message": "..."}}
"""
    parsed = None
    if client:
        try:
            response = client.chat.completions(
                model="sarvam-105b-conversations",
                messages=[{"role": "user", "content": prompt}]
            )
            content = response.choices[0].message.content.strip()
            if "```" in content:
                content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.MULTILINE)
                content = re.sub(r"\s*```$", "", content, flags=re.MULTILINE).strip()
            parsed = json.loads(content)
        except Exception as e:
            print(f"Sarvam LLM Error: {e}")

    if not parsed:
        parsed = fallback_parse_intent(text)
        
    parsed["original_text"] = text
    
    # Feature 1: Handle Voice Balance Inquiry right here!
    if parsed.get("transaction_type") == "CHECK_BALANCE":
        cust_name = parsed.get("customer_name")
        if cust_name:
            matched_name, balance = get_customer_balance_by_name(cust_name)
            if matched_name:
                if balance > 0:
                    spoken_text = f"{matched_name} के खाते में कुल ₹{int(balance)} का उधार बाकी है।"
                else:
                    spoken_text = f"{matched_name} का कोई भी उधार बाकी नहीं है।"
            else:
                spoken_text = f"{cust_name} नाम का कोई ग्राहक बहीखाते में नहीं मिला।"
        else:
            spoken_text = "कृपया बताएं कि किस ग्राहक का उधार जांचना है।"
            
        audio_b64 = None
        if client:
            try:
                tts = client.text_to_speech.convert(
                    text=spoken_text,
                    language_code="hi-IN",
                    speaker="ritu",
                    model="bulbul:v3"
                )
                if tts.audios:
                    audio_b64 = tts.audios[0]
            except Exception as e:
                print(f"TTS error: {e}")
                
        parsed["is_balance_inquiry"] = True
        parsed["current_balance"] = balance if cust_name and matched_name else 0.0
        parsed["spoken_text"] = spoken_text
        parsed["audio_base64"] = audio_b64
        
    return parsed

def fallback_parse_intent(text: str):
    text_lower = text.lower()
    
    tx_type = "UNKNOWN"
    if any(w in text_lower for w in ["kitna", "baki hai", "baaki hai", "check", "hisaab", "hisab"]):
        tx_type = "CHECK_BALANCE"
    elif any(w in text_lower for w in ["udhaar", "credit", "likh", "le gaya", "liya", "liye"]):
        tx_type = "CREDIT"
    elif any(w in text_lower for w in ["wapas", "jama", "chuka", "paid", "repaid", "diye", "return"]):
        tx_type = "REPAYMENT"
        
    amount = None
    amounts = re.findall(r"\b(\d+(?:\.\d+)?)\b", text)
    if amounts:
        amount = float(amounts[0])
        
    customer_name = None
    name_match = re.search(r"([A-Za-z\u0900-\u097F]+)\s+(?:ne|se|ko|ka|ke)", text, re.IGNORECASE)
    if name_match:
        customer_name = name_match.group(1).capitalize()
    elif "for " in text_lower:
        customer_name = text.split("for ")[-1].strip().split()[0].capitalize()

    item = None
    item_match = re.search(r"(?:ka|ki|ke)\s+([A-Za-z\u0900-\u097F]+)\s+(?:liya|kharida|diya)", text, re.IGNORECASE)
    if item_match:
        item = item_match.group(1).capitalize()
        
    is_ambiguous = (customer_name is None) if tx_type == "CHECK_BALANCE" else (customer_name is None or amount is None or tx_type == "UNKNOWN")
    
    msg = f"{customer_name} का हिसाब जांचें" if tx_type == "CHECK_BALANCE" else "लेन-देन विवरण"

    return {
        "customer_name": customer_name,
        "amount": amount,
        "transaction_type": tx_type,
        "item": item,
        "is_ambiguous": is_ambiguous,
        "clarification_message": msg,
        "original_text": text
    }

@app.post("/api/transcribe")
async def transcribe_audio(audio: UploadFile = File(...), language_code: str = Form("hi-IN")):
    if not client:
        return {"transcript": "", "error": "Sarvam API client not available"}
        
    try:
        audio_bytes = await audio.read()
        res = client.speech_to_text.transcribe(
            file=(audio.filename or "audio.webm", audio_bytes, audio.content_type or "audio/webm"),
            model="saaras:v3",
            language_code=language_code
        )
        return {"transcript": res.transcript, "language": res.language_code}
    except Exception as e:
        print(f"STT Error: {e}")
        return {"transcript": "", "error": str(e)}

@app.post("/api/speak")
def generate_speech(req: SpeakRequest):
    if not client:
        return {"audio_base64": None}
    try:
        tts = client.text_to_speech.convert(
            text=req.text,
            language_code="hi-IN",
            speaker="ritu",
            model="bulbul:v3"
        )
        if tts.audios and len(tts.audios) > 0:
            return {"audio_base64": tts.audios[0]}
        return {"audio_base64": None}
    except Exception as e:
        print(f"TTS Error: {e}")
        return {"audio_base64": None, "error": str(e)}

@app.post("/api/transactions/confirm")
def confirm_transaction(data: TransactionConfirm):
    cust_name = data.customer_name.strip()
    if not cust_name:
        raise HTTPException(status_code=400, detail="Customer name missing")
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than zero")
    if data.transaction_type not in ["CREDIT", "REPAYMENT"]:
        raise HTTPException(status_code=400, detail="Invalid transaction type")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, phone FROM customers WHERE name = ? COLLATE NOCASE", (cust_name,))
    row = cursor.fetchone()
    if row:
        customer_id = row["id"]
        if data.phone and not row["phone"]:
            cursor.execute("UPDATE customers SET phone = ? WHERE id = ?", (data.phone.strip(), customer_id))
            conn.commit()
    else:
        cursor.execute("INSERT INTO customers (name, phone) VALUES (?, ?)", (cust_name, data.phone or ""))
        conn.commit()
        customer_id = cursor.lastrowid
        
    cursor.execute("""
        INSERT INTO transactions (customer_id, customer_name, transaction_type, amount, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (customer_id, cust_name, data.transaction_type, data.amount, data.notes or ""))
    conn.commit()
    tx_id = cursor.lastrowid
    
    cursor.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN transaction_type = 'CREDIT' THEN amount ELSE 0 END), 0) -
            COALESCE(SUM(CASE WHEN transaction_type = 'REPAYMENT' THEN amount ELSE 0 END), 0) as balance
        FROM transactions 
        WHERE customer_id = ?
    """, (customer_id,))
    new_balance = float(cursor.fetchone()["balance"])
    
    cursor.execute("SELECT phone FROM customers WHERE id = ?", (customer_id,))
    final_phone = cursor.fetchone()["phone"] or ""
    conn.close()
    
    item_clause = f" ({data.notes})" if data.notes else ""
    if data.transaction_type == "CREDIT":
        spoken_text = f"{cust_name} के खाते में ₹{data.amount:.0f}{item_clause} का उधार जोड़ दिया गया है। अब कुल उधार ₹{new_balance:.0f} है।"
    else:
        spoken_text = f"{cust_name} से ₹{data.amount:.0f} की वापसी दर्ज कर ली गई है। अब बाकी उधार ₹{new_balance:.0f} है।"

    audio_base64 = None
    if client:
        try:
            tts = client.text_to_speech.convert(
                text=spoken_text,
                language_code="hi-IN",
                speaker="ritu",
                model="bulbul:v3"
            )
            if tts.audios:
                audio_base64 = tts.audios[0]
        except Exception as e:
            print(f"TTS generation error on confirm: {e}")
            
    return {
        "status": "success",
        "transaction_id": tx_id,
        "customer_name": cust_name,
        "customer_phone": final_phone,
        "transaction_type": data.transaction_type,
        "amount": data.amount,
        "notes": data.notes or "",
        "new_balance": new_balance,
        "spoken_text": spoken_text,
        "audio_base64": audio_base64
    }

@app.post("/api/reset-demo")
@app.get("/api/reset-demo")
def reset_demo():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions")
    cursor.execute("DELETE FROM customers")
    conn.commit()
    conn.close()
    return {"status": "reset", "message": "Demo data wiped clean."}

# ==================== FRONTEND UI ====================

@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_CONTENT

HTML_CONTENT = """<!DOCTYPE html>
<html lang="hi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>बोलती बही — Bolti Bahi</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/lucide@latest"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Mukta:wght@400;600;700;800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Mukta', 'Inter', -apple-system, sans-serif;
            background-color: #F8F9FA;
            -webkit-tap-highlight-color: transparent;
        }
        .mic-pulse {
            animation: pulse-ring 2s infinite;
        }
        @keyframes pulse-ring {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(234, 88, 12, 0.7); }
            70% { transform: scale(1.05); box-shadow: 0 0 0 20px rgba(234, 88, 12, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(234, 88, 12, 0); }
        }
        .recording-wave {
            animation: wave 1.2s infinite ease-in-out;
        }
        @keyframes wave {
            0%, 100% { height: 8px; }
            50% { height: 32px; }
        }
    </style>
</head>
<body class="text-gray-800 antialiased min-h-screen pb-20">

    <!-- Top App Bar -->
    <header class="bg-gradient-to-r from-orange-600 to-amber-600 text-white shadow-md sticky top-0 z-30 px-4 py-3">
        <div class="max-w-md mx-auto flex items-center justify-between">
            <div class="flex items-center space-x-2">
                <div class="bg-white/20 p-2 rounded-xl backdrop-blur-sm">
                    <i data-lucide="book-open-check" class="w-6 h-6 text-white"></i>
                </div>
                <div>
                    <h1 class="text-2xl font-extrabold tracking-tight leading-none">बोलती बही</h1>
                    <p class="text-xs text-orange-100 font-medium">Bolti Bahi • Voice Udhaar Register</p>
                </div>
            </div>
            
            <button onclick="resetDemo()" title="Reset Demo Data" class="text-xs bg-white/20 hover:bg-white/30 text-white px-3 py-1.5 rounded-full flex items-center space-x-1 font-semibold transition">
                <i data-lucide="rotate-ccw" class="w-3.5 h-3.5"></i>
                <span>Reset</span>
            </button>
        </div>
    </header>

    <main class="max-w-md mx-auto px-4 pt-4 space-y-4">

        <!-- Sarvam AI Powered Badge -->
        <div class="flex items-center justify-between text-xs bg-orange-50 border border-orange-200 text-orange-800 px-3 py-1.5 rounded-lg">
            <span class="flex items-center space-x-1.5">
                <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                <span class="font-bold">Sarvam AI:</span>
                <span>Saaras (STT) + Bulbul (TTS)</span>
            </span>
            <span class="font-semibold text-orange-600">Voice Inquiry Active</span>
        </div>

        <!-- Metric Cards -->
        <div class="grid grid-cols-2 gap-3">
            <div class="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
                <div class="flex items-center space-x-2 text-rose-600 mb-1">
                    <i data-lucide="arrow-up-right" class="w-4 h-4"></i>
                    <span class="text-xs font-bold uppercase tracking-wider">कुल बाकी उधार</span>
                </div>
                <div class="text-2xl font-black text-gray-900" id="totalCredit">₹0</div>
                <div class="text-xs text-gray-500 mt-0.5">Total Outstanding</div>
            </div>

            <div class="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
                <div class="flex items-center space-x-2 text-blue-600 mb-1">
                    <i data-lucide="users" class="w-4 h-4"></i>
                    <span class="text-xs font-bold uppercase tracking-wider">कुल ग्राहक</span>
                </div>
                <div class="text-2xl font-black text-gray-900" id="customerCount">0</div>
                <div class="text-xs text-gray-500 mt-0.5">Active Customers</div>
            </div>
        </div>

        <!-- Voice Action Center (The Hero Component) -->
        <div class="bg-white rounded-3xl p-5 shadow-sm border border-orange-100 text-center relative overflow-hidden">
            <div class="absolute -top-12 -right-12 w-32 h-32 bg-orange-100 rounded-full blur-2xl opacity-50"></div>
            
            <p class="text-sm font-semibold text-gray-500 mb-3" id="voiceStatus">
                बटन दबाएं और बोलें <span class="text-gray-400">• Press & Speak</span>
            </p>

            <!-- Big Mic Button -->
            <div class="flex justify-center items-center my-2">
                <button id="micBtn" onclick="toggleRecording()" 
                    class="w-24 h-24 rounded-full bg-gradient-to-tr from-orange-500 to-amber-500 hover:from-orange-600 hover:to-amber-600 text-white shadow-lg shadow-orange-500/30 flex flex-col items-center justify-center transition-all duration-300 transform active:scale-95">
                    <i id="micIcon" data-lucide="mic" class="w-10 h-10"></i>
                    <span id="micLabel" class="text-xs font-extrabold mt-1">बोलिए</span>
                </button>
            </div>

            <!-- Waveform Animation -->
            <div id="recordingWaveform" class="hidden flex justify-center items-center space-x-1.5 h-8 my-2">
                <span class="w-1.5 bg-rose-500 rounded-full recording-wave" style="animation-delay: 0.1s"></span>
                <span class="w-1.5 bg-rose-500 rounded-full recording-wave" style="animation-delay: 0.2s"></span>
                <span class="w-1.5 bg-rose-500 rounded-full recording-wave" style="animation-delay: 0.3s"></span>
                <span class="w-1.5 bg-rose-500 rounded-full recording-wave" style="animation-delay: 0.4s"></span>
                <span class="w-1.5 bg-rose-500 rounded-full recording-wave" style="animation-delay: 0.5s"></span>
            </div>

            <!-- Live Transcript Display -->
            <div id="transcriptBox" class="mt-3 p-3 bg-orange-50/70 border border-orange-100 rounded-xl text-left hidden">
                <div class="text-[11px] font-bold text-orange-600 uppercase tracking-wider mb-1 flex items-center space-x-1">
                    <i data-lucide="sparkles" class="w-3 h-3"></i>
                    <span>सुनी गई बात (Transcribed text)</span>
                </div>
                <p id="transcriptText" class="text-sm font-medium text-gray-900"></p>
            </div>

            <!-- Text Input Fallback -->
            <div class="mt-4 pt-3 border-t border-gray-100">
                <p class="text-xs text-gray-500 mb-2 font-medium">या यहाँ लिखकर बोलें / पूछें:</p>
                <div class="flex space-x-2">
                    <input type="text" id="manualText" 
                        placeholder="जैसे: Ramesh ka kitna udhaar baaki hai?" 
                        class="flex-1 text-sm bg-gray-50 border border-gray-200 rounded-xl px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:bg-white transition"
                        onkeydown="if(event.key==='Enter') processTextQuery()"
                    >
                    <button onclick="processTextQuery()" 
                        class="bg-orange-600 hover:bg-orange-700 text-white px-4 py-2.5 rounded-xl font-bold text-sm shadow-sm transition flex items-center justify-center">
                        <i data-lucide="arrow-right" class="w-4 h-4"></i>
                    </button>
                </div>

                <!-- Quick Preset Chips for Easy Evaluation -->
                <div class="flex flex-wrap gap-1.5 mt-2.5 justify-center">
                    <button onclick="setSample('Ramesh ka kitna udhaar baaki hai?')" 
                        class="text-xs bg-purple-50 hover:bg-purple-100 text-purple-800 px-2.5 py-1 rounded-full transition border border-purple-200 font-bold">
                        🔍 रमेश का कितना बाकी है?
                    </button>
                    <button onclick="setSample('Ramesh ne 500 rupaye ka udhaar liya.')" 
                        class="text-xs bg-orange-50 hover:bg-orange-100 text-orange-800 px-2.5 py-1 rounded-full transition border border-orange-200 font-medium">
                        ⚡ रमेश उधार ₹500
                    </button>
                    <button onclick="setSample('Ramesh ne 200 rupaye wapas kar diye.')" 
                        class="text-xs bg-emerald-50 hover:bg-emerald-100 text-emerald-800 px-2.5 py-1 rounded-full transition border border-emerald-200 font-medium">
                        ⚡ रमेश वापसी ₹200
                    </button>
                </div>
            </div>
        </div>

        <!-- Confirmation Card / Safety Modal -->
        <div id="confirmCard" class="hidden bg-amber-50 border-2 border-amber-300 rounded-3xl p-5 shadow-lg relative animate-fade-in">
            <div class="flex items-center space-x-2 text-amber-800 mb-2 font-bold">
                <i data-lucide="shield-alert" class="w-5 h-5 text-amber-600"></i>
                <span class="text-base">पुष्टि करें (Confirm Transaction)</span>
            </div>
            
            <p class="text-xs text-amber-700 mb-3">
                कृपया जांचें कि क्या यह लेन-देन सही है:
            </p>

            <div class="bg-white rounded-2xl p-4 space-y-2.5 border border-amber-200 shadow-sm mb-4">
                <div class="flex justify-between items-center text-sm">
                    <span class="text-gray-500">ग्राहक (Customer):</span>
                    <input type="text" id="confirmCustName" class="font-bold text-gray-900 text-right bg-amber-50/50 px-2 py-0.5 rounded border border-amber-200">
                </div>
                
                <div class="flex justify-between items-center text-sm">
                    <span class="text-gray-500">फ़ोन नंबर (Phone):</span>
                    <input type="text" id="confirmCustPhone" placeholder="वैकल्पिक" class="text-sm text-right bg-amber-50/50 px-2 py-0.5 rounded border border-amber-200 text-gray-800">
                </div>

                <div class="flex justify-between items-center text-sm">
                    <span class="text-gray-500">प्रकार (Type):</span>
                    <select id="confirmTxType" class="font-bold text-right bg-amber-50/50 px-2 py-0.5 rounded border border-amber-200">
                        <option value="CREDIT">उधार (CREDIT)</option>
                        <option value="REPAYMENT">वापसी (REPAYMENT)</option>
                    </select>
                </div>

                <div class="flex justify-between items-center text-sm">
                    <span class="text-gray-500">सामान/विवरण (Item):</span>
                    <input type="text" id="confirmNotes" placeholder="वैकल्पिक (e.g. समोसा)" class="font-semibold text-right bg-amber-50/50 px-2 py-0.5 rounded border border-amber-200 text-gray-800">
                </div>

                <div class="flex justify-between items-center text-sm pt-1 border-t border-gray-100">
                    <span class="text-gray-500 font-bold">रकम (Amount):</span>
                    <div class="flex items-center space-x-1">
                        <span class="font-bold text-gray-600">₹</span>
                        <input type="number" id="confirmAmount" class="font-black text-lg text-right text-gray-900 w-28 bg-amber-50/50 px-2 py-0.5 rounded border border-amber-200">
                    </div>
                </div>
            </div>

            <div class="flex space-x-2">
                <button onclick="cancelConfirmation()" 
                    class="flex-1 bg-white hover:bg-gray-100 text-gray-700 font-bold py-3 rounded-xl border border-gray-300 transition text-sm">
                    रद्द करें (Cancel)
                </button>
                <button onclick="executeConfirmedTransaction()" 
                    class="flex-1 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white font-bold py-3 rounded-xl shadow-md transition text-sm flex items-center justify-center space-x-1.5">
                    <i data-lucide="check-circle-2" class="w-4 h-4"></i>
                    <span>पुष्टि करें (Confirm)</span>
                </button>
            </div>
        </div>

        <!-- Audio Feedback Player -->
        <audio id="audioPlayer" class="hidden"></audio>

        <!-- Voice Confirmation Toast -->
        <div id="voiceFeedbackToast" class="hidden bg-emerald-700 text-white p-3.5 rounded-2xl shadow-lg flex items-center justify-between text-sm">
            <div class="flex items-center space-x-2.5">
                <div class="bg-white/20 p-2 rounded-xl">
                    <i data-lucide="volume-2" class="w-5 h-5 text-white"></i>
                </div>
                <span id="toastMessage" class="font-medium text-xs leading-snug"></span>
            </div>
            <button onclick="replayAudio()" id="replayBtn" class="bg-white/20 hover:bg-white/30 p-1.5 rounded-lg ml-2">
                <i data-lucide="rotate-cw" class="w-4 h-4"></i>
            </button>
        </div>

        <!-- Section 1: Customer Udhaar Register -->
        <div class="bg-white rounded-3xl p-4 shadow-sm border border-gray-100">
            <div class="flex items-center justify-between mb-3">
                <div class="flex items-center space-x-2">
                    <i data-lucide="book-marked" class="w-5 h-5 text-orange-600"></i>
                    <h2 class="text-base font-extrabold text-gray-900">ग्राहक बहीखाता (Udhaar Register)</h2>
                </div>
                <button onclick="openAddCustomerModal()" class="text-xs bg-orange-100 hover:bg-orange-200 text-orange-800 font-bold px-2.5 py-1 rounded-lg flex items-center space-x-1 transition">
                    <i data-lucide="plus" class="w-3.5 h-3.5"></i>
                    <span>नया ग्राहक</span>
                </button>
            </div>

            <!-- Customer List Container with 1-Tap Settle Buttons -->
            <div id="customerList" class="space-y-2">
                <p class="text-xs text-gray-400 py-3 text-center">लोड हो रहा है...</p>
            </div>
        </div>

        <!-- Section 2: Recent Transactions Log -->
        <div class="bg-white rounded-3xl p-4 shadow-sm border border-gray-100">
            <div class="flex items-center justify-between mb-3">
                <div class="flex items-center space-x-2">
                    <i data-lucide="history" class="w-5 h-5 text-blue-600"></i>
                    <h2 class="text-base font-extrabold text-gray-900">हालिया लेन-देन (History)</h2>
                </div>
            </div>

            <div id="transactionList" class="space-y-2">
                <p class="text-xs text-gray-400 py-3 text-center">कोई लेन-देन नहीं मिला</p>
            </div>
        </div>

    </main>

    <!-- Add Customer Modal -->
    <div id="customerModal" class="fixed inset-0 bg-black/40 backdrop-blur-xs z-50 hidden flex items-center justify-center p-4">
        <div class="bg-white w-full max-w-sm rounded-3xl p-5 shadow-2xl space-y-4">
            <div class="flex justify-between items-center">
                <h3 class="font-extrabold text-lg text-gray-900">नया ग्राहक जोड़ें</h3>
                <button onclick="closeAddCustomerModal()" class="text-gray-400 hover:text-gray-600">
                    <i data-lucide="x" class="w-5 h-5"></i>
                </button>
            </div>
            <div>
                <label class="block text-xs font-semibold text-gray-500 mb-1">ग्राहक का नाम (Customer Name)*</label>
                <input type="text" id="newCustName" placeholder="जैसे: Ramesh" class="w-full text-sm bg-gray-50 border border-gray-200 rounded-xl px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:bg-white">
            </div>
            <div>
                <label class="block text-xs font-semibold text-gray-500 mb-1">फ़ोन नंबर (वैकल्पिक)</label>
                <input type="tel" id="newCustPhone" placeholder="जैसे: 9876543210" class="w-full text-sm bg-gray-50 border border-gray-200 rounded-xl px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:bg-white">
            </div>
            <div class="flex space-x-2 pt-2">
                <button onclick="closeAddCustomerModal()" class="flex-1 bg-gray-100 hover:bg-gray-200 text-gray-700 font-bold py-2.5 rounded-xl text-sm transition">
                    रद्द करें
                </button>
                <button onclick="saveNewCustomer()" class="flex-1 bg-orange-600 hover:bg-orange-700 text-white font-bold py-2.5 rounded-xl text-sm shadow transition">
                    ग्राहक जोड़ें
                </button>
            </div>
        </div>
    </div>

    <script>
        let isRecording = false;
        let mediaRecorder = null;
        let audioChunks = [];
        let lastAudioBase64 = null;

        document.addEventListener('DOMContentLoaded', () => {
            lucide.createIcons();
            fetchDashboard();
        });

        function setSample(text) {
            document.getElementById('manualText').value = text;
            processTextQuery();
        }

        async function fetchDashboard() {
            try {
                const res = await fetch('/api/dashboard');
                const data = await res.json();
                
                document.getElementById('totalCredit').innerText = `₹${Math.round(data.total_credit).toLocaleString('en-IN')}`;
                document.getElementById('customerCount').innerText = data.customer_count;

                renderCustomers(data.customers);
                renderTransactions(data.recent_transactions);
            } catch (err) {
                console.error("Dashboard error:", err);
            }
        }

        function renderCustomers(customers) {
            const container = document.getElementById('customerList');
            if (!customers || customers.length === 0) {
                container.innerHTML = `<p class="text-xs text-gray-400 py-3 text-center">अभी कोई ग्राहक नहीं है। ऊपर दिए गए बटन से जोड़ें।</p>`;
                return;
            }

            container.innerHTML = customers.map(c => {
                const isDebt = c.balance > 0;
                const balanceClass = isDebt ? 'text-rose-600 bg-rose-50 border-rose-200' : 'text-emerald-700 bg-emerald-50 border-emerald-200';
                
                // 1-Tap "पूरा हिसाब चुकता" Button
                const settleBtn = isDebt ? `
                    <button onclick="settleCustomer(${c.id}, '${c.name}', ${Math.round(c.balance)})" 
                        class="text-[11px] bg-emerald-600 hover:bg-emerald-700 text-white font-extrabold px-2.5 py-1 rounded-lg transition shadow-xs flex items-center space-x-1 mt-1">
                        <i data-lucide="check" class="w-3 h-3"></i>
                        <span>हिसाब चुकता</span>
                    </button>
                ` : '';

                return `
                <div class="p-3 rounded-2xl bg-gray-50 hover:bg-gray-100/80 transition border border-gray-100">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center space-x-3">
                            <div class="w-10 h-10 rounded-full bg-orange-100 text-orange-700 font-black text-sm flex items-center justify-center">
                                ${c.name.charAt(0).toUpperCase()}
                            </div>
                            <div>
                                <h4 class="font-extrabold text-sm text-gray-900">${c.name}</h4>
                                <div class="flex items-center space-x-1.5 text-[11px] text-gray-400">
                                    <i data-lucide="phone" class="w-2.5 h-2.5"></i>
                                    <span>${c.phone || '<span class="italic text-gray-300">फ़ोन नहीं है</span>'}</span>
                                </div>
                            </div>
                        </div>
                        <div class="text-right flex flex-col items-end">
                            <span class="inline-block px-2.5 py-0.5 rounded-full text-xs font-black border ${balanceClass}">
                                ₹${Math.round(c.balance).toLocaleString('en-IN')}
                            </span>
                            <div class="text-[10px] text-gray-400">बाकी उधार</div>
                            ${settleBtn}
                        </div>
                    </div>
                </div>
                `;
            }).join('');
            lucide.createIcons();
        }

        // 1-Tap Settle Function
        async function settleCustomer(id, name, amount) {
            if (!confirm(`${name} का पूरा हिसाब ₹${amount} चुकता करें?`)) return;

            try {
                const res = await fetch(`/api/customers/${id}/settle`, { method: 'POST' });
                const data = await res.json();
                showVoiceFeedback(data.spoken_text, data.audio_base64);
                fetchDashboard();
            } catch (err) {
                console.error("Settle error:", err);
                alert("हिसाब चुकता करने में त्रुटि हुई!");
            }
        }

        function renderTransactions(txns) {
            const container = document.getElementById('transactionList');
            if (!txns || txns.length === 0) {
                container.innerHTML = `<p class="text-xs text-gray-400 py-3 text-center">कोई लेन-देन नहीं हुआ है।</p>`;
                return;
            }

            container.innerHTML = txns.map(t => {
                const isCredit = t.transaction_type === 'CREDIT';
                const badgeColor = isCredit ? 'bg-rose-100 text-rose-700' : 'bg-emerald-100 text-emerald-800';
                const typeLabel = isCredit ? 'उधार (Credit)' : 'वापसी (Repayment)';
                const dateStr = new Date(t.created_at).toLocaleTimeString('hi-IN', { hour: '2-digit', minute: '2-digit' });
                const noteBadge = t.notes ? `<span class="bg-amber-100 text-amber-800 px-1.5 py-0.2 text-[10px] rounded font-semibold ml-1">📦 ${t.notes}</span>` : '';

                return `
                <div class="p-2.5 rounded-xl bg-gray-50 border border-gray-100 text-xs">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center space-x-1.5">
                            <span class="px-2 py-0.5 rounded font-extrabold text-[10px] ${badgeColor}">
                                ${typeLabel}
                            </span>
                            <span class="font-bold text-gray-800">${t.customer_name}</span>
                            ${noteBadge}
                        </div>
                        <div class="flex items-center space-x-2">
                            <span class="font-black text-sm ${isCredit ? 'text-rose-600' : 'text-emerald-700'}">
                                ${isCredit ? '+' : '-'}₹${Math.round(t.amount)}
                            </span>
                            <span class="text-[10px] text-gray-400">${dateStr}</span>
                        </div>
                    </div>
                </div>
                `;
            }).join('');
        }

        // Web Audio Recording
        async function toggleRecording() {
            if (!isRecording) {
                startRecording();
            } else {
                stopRecording();
            }
        }

        async function startRecording() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                audioChunks = [];

                mediaRecorder.ondataavailable = (event) => {
                    audioChunks.push(event.data);
                };

                mediaRecorder.onstop = async () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    await handleAudioUpload(audioBlob);
                };

                mediaRecorder.start();
                isRecording = true;

                document.getElementById('micBtn').classList.add('mic-pulse', 'from-rose-500', 'to-red-600');
                document.getElementById('micLabel').innerText = "रोकें";
                document.getElementById('voiceStatus').innerText = "सुन रहे हैं... (Listening...)";
                document.getElementById('recordingWaveform').classList.remove('hidden');
            } catch (err) {
                console.error("Microphone access error:", err);
                alert("माइक्रोफ़ोन की अनुमति नहीं मिली। कृपया नीचे लिखकर दर्ज करें।");
            }
        }

        function stopRecording() {
            if (mediaRecorder && isRecording) {
                mediaRecorder.stop();
                isRecording = false;

                document.getElementById('micBtn').classList.remove('mic-pulse', 'from-rose-500', 'to-red-600');
                document.getElementById('micLabel').innerText = "बोलिए";
                document.getElementById('voiceStatus').innerText = "सरवम AI समझ रहा है...";
                document.getElementById('recordingWaveform').classList.add('hidden');
            }
        }

        async function handleAudioUpload(blob) {
            const formData = new FormData();
            formData.append("audio", blob, "recording.webm");
            formData.append("language_code", "hi-IN");

            try {
                const res = await fetch('/api/transcribe', {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();
                if (data.transcript && data.transcript.trim()) {
                    showTranscript(data.transcript);
                    await parseIntent(data.transcript);
                } else {
                    document.getElementById('voiceStatus').innerText = "आवाज समझ नहीं आई। कृपया दोबारा बोलें या नीचे लिखें।";
                }
            } catch (err) {
                console.error("Transcribe error:", err);
                document.getElementById('voiceStatus').innerText = "त्रुटि हुई। कृपया नीचे लिखकर प्रयास करें।";
            }
        }

        async function processTextQuery() {
            const input = document.getElementById('manualText');
            const text = input.value.trim();
            if (!text) return;

            showTranscript(text);
            input.value = "";
            await parseIntent(text);
        }

        function showTranscript(text) {
            document.getElementById('transcriptBox').classList.remove('hidden');
            document.getElementById('transcriptText').innerText = `"${text}"`;
        }

        // Voice Intent Processing
        async function parseIntent(text) {
            document.getElementById('voiceStatus').innerText = "सरवम AI समझ रहा है...";
            try {
                const res = await fetch('/api/extract-intent', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: text })
                });
                const data = await res.json();
                document.getElementById('voiceStatus').innerText = "बटन दबाएं और बोलें";

                // Voice Balance Inquiry Result
                if (data.is_balance_inquiry) {
                    showVoiceFeedback(data.spoken_text, data.audio_base64);
                    return;
                }

                if (data.is_ambiguous) {
                    alert(data.clarification_message || "कृपया ग्राहक का नाम और सही रकम बताएं।");
                    return;
                }

                showConfirmation(data.customer_name, data.transaction_type, data.amount, data.item);
            } catch (err) {
                console.error("Intent extraction error:", err);
                document.getElementById('voiceStatus').innerText = "त्रुटि हुई। कृपया दोबारा प्रयास करें।";
            }
        }

        function showConfirmation(customer, type, amount, item) {
            document.getElementById('confirmCustName').value = customer || "";
            document.getElementById('confirmTxType').value = (type === 'REPAYMENT') ? 'REPAYMENT' : 'CREDIT';
            document.getElementById('confirmAmount').value = amount || "";
            document.getElementById('confirmNotes').value = item || "";
            document.getElementById('confirmCustPhone').value = "";
            document.getElementById('confirmCard').classList.remove('hidden');
            document.getElementById('confirmCard').scrollIntoView({ behavior: 'smooth' });
            lucide.createIcons();
        }

        function cancelConfirmation() {
            document.getElementById('confirmCard').classList.add('hidden');
        }

        async function executeConfirmedTransaction() {
            const customer_name = document.getElementById('confirmCustName').value.trim();
            const transaction_type = document.getElementById('confirmTxType').value;
            const amount = parseFloat(document.getElementById('confirmAmount').value);
            const notes = document.getElementById('confirmNotes').value.trim();
            const phone = document.getElementById('confirmCustPhone').value.trim();

            if (!customer_name || isNaN(amount) || amount <= 0) {
                alert("कृपया सही ग्राहक और रकम भरें।");
                return;
            }

            try {
                const res = await fetch('/api/transactions/confirm', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        customer_name: customer_name,
                        transaction_type: transaction_type,
                        amount: amount,
                        notes: notes,
                        phone: phone
                    })
                });
                const data = await res.json();
                cancelConfirmation();
                
                showVoiceFeedback(data.spoken_text, data.audio_base64);
                fetchDashboard();
            } catch (err) {
                console.error("Transaction save error:", err);
                alert("लेन-देन दर्ज करने में विफल!");
            }
        }

        function showVoiceFeedback(text, audioB64) {
            const toast = document.getElementById('voiceFeedbackToast');
            document.getElementById('toastMessage').innerText = text;
            toast.classList.remove('hidden');
            lastAudioBase64 = audioB64;

            if (audioB64) {
                playAudioB64(audioB64);
            } else if ('speechSynthesis' in window) {
                const utter = new SpeechSynthesisUtterance(text);
                utter.lang = 'hi-IN';
                window.speechSynthesis.speak(utter);
            }

            setTimeout(() => {
                toast.classList.add('hidden');
            }, 8000);
        }

        function playAudioB64(b64) {
            const audio = document.getElementById('audioPlayer');
            audio.src = `data:audio/wav;base64,${b64}`;
            audio.play().catch(e => console.log("Audio autoplay restricted:", e));
        }

        function replayAudio() {
            if (lastAudioBase64) {
                playAudioB64(lastAudioBase64);
            }
        }

        function openAddCustomerModal() {
            document.getElementById('newCustName').value = "";
            document.getElementById('newCustPhone').value = "";
            document.getElementById('customerModal').classList.remove('hidden');
        }

        function closeAddCustomerModal() {
            document.getElementById('customerModal').classList.add('hidden');
        }

        async function saveNewCustomer() {
            const name = document.getElementById('newCustName').value.trim();
            const phone = document.getElementById('newCustPhone').value.trim();
            if (!name) {
                alert("ग्राहक का नाम अनिवार्य है");
                return;
            }

            try {
                await fetch('/api/customers', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: name, phone: phone })
                });
                closeAddCustomerModal();
                fetchDashboard();
            } catch (err) {
                alert("ग्राहक जोड़ने में त्रुटि!");
            }
        }

        async function resetDemo() {
            if (confirm("क्या आप डेमो डेटा रीसेट करना चाहते हैं?")) {
                await fetch('/api/reset-demo', { method: 'POST' });
                fetchDashboard();
            }
        }
    </script>
</body>
</html>
"""
