# mychat_ultimate_pro_v42.0.py
import streamlit as st
import datetime
import json
import os
import requests
import hashlib
import re
import time
from io import BytesIO
from PIL import Image
import base64
import random

# === PAGE CONFIG ===
st.set_page_config(
    page_title="MyChatAI Pro",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# === API KEYS DARI STREAMLIT SECRETS ===
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    CLAUDE_API_KEY = st.secrets.get("CLAUDE_API_KEY", "")
    HUGGINGFACE_API_KEY = st.secrets.get("HUGGINGFACE_API_KEY", "")
    REPLICATE_API_KEY = st.secrets.get("REPLICATE_API_KEY", "")
    STABILITY_API_KEY = st.secrets.get("STABILITY_API_KEY", "")
    UNSPLASH_API_KEY = st.secrets.get("UNSPLASH_API_KEY", "")
    POLLINATIONS_API_KEY = st.secrets.get("POLLINATIONS_API_KEY", "")
    ELEVENLABS_API_KEY = st.secrets.get("ELEVENLABS_API_KEY", "")
    WEATHER_API_KEY = st.secrets.get("WEATHER_API_KEY", "")
    NEWS_API_KEY = st.secrets.get("NEWS_API_KEY", "")
    SEARCH_API_KEY = st.secrets.get("SEARCH_API_KEY", "")
    CRAZYROUTER_API_KEY = st.secrets.get("CRAZYROUTER_API_KEY", "")
    ADMIN_EMAIL = st.secrets.get("ADMIN_EMAIL", "joe.adie77711@gmail.com")
    MAX_FREE_REQUESTS = st.secrets.get("MAX_FREE_REQUESTS", 1000)
    DISCORD_WEBHOOK = st.secrets.get("DISCORD_WEBHOOK", "")
    TELEGRAM_BOT_TOKEN = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "")
except KeyError as e:
    st.error(f"Missing required secret: {e}")
    st.stop()

# === CONSTANTS ===
USER_DATA_FILE = "mychat_users.json"
CHAT_HISTORY_FILE = "mychat_chats.json"
USAGE_FILE = "mychat_usage.json"
DEFAULT_AVATAR = "https://ui-avatars.com/api/?name=User&background=4d6bfe&color=fff&size=40"

# === HASH ===
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# === DATA FUNCTIONS ===
def load_users():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, "r") as f:
            return json.load(f)
    default = {
        "admin": {
            "password": hash_password("777777"),
            "role": "admin",
            "email": ADMIN_EMAIL,
            "name": "Admin",
            "avatar": "https://ui-avatars.com/api/?name=Admin&background=4d6bfe&color=fff&size=40",
            "settings": {"language": "Malay", "dark_mode": True},
            "created_at": datetime.datetime.now().isoformat(),
            "premium_until": None,
            "total_requests": 0
        }
    }
    save_users(default)
    return default

def save_users(data):
    with open(USER_DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def load_chats():
    if os.path.exists(CHAT_HISTORY_FILE):
        with open(CHAT_HISTORY_FILE, "r") as f:
            return json.load(f)
    return {}

def save_chats(data):
    with open(CHAT_HISTORY_FILE, "w") as f:
        json.dump(data, f, indent=2)

def load_usage(username):
    if os.path.exists(USAGE_FILE):
        with open(USAGE_FILE, "r") as f:
            data = json.load(f)
        return data.get(username, {"count": 0, "month": datetime.datetime.now().month, "year": datetime.datetime.now().year})
    return {"count": 0, "month": datetime.datetime.now().month, "year": datetime.datetime.now().year}

def save_usage(username, data):
    all_data = {}
    if os.path.exists(USAGE_FILE):
        with open(USAGE_FILE, "r") as f:
            all_data = json.load(f)
    all_data[username] = data
    with open(USAGE_FILE, "w") as f:
        json.dump(all_data, f, indent=2)

def check_usage_limit(username):
    user_data = load_users().get(username, {})
    if user_data.get("role") == "admin" or is_premium(username):
        return {"allowed": True, "used": 0, "limit": 999999}
    usage = load_usage(username)
    now = datetime.datetime.now()
    if usage["month"] != now.month or usage["year"] != now.year:
        usage = {"count": 0, "month": now.month, "year": now.year}
        save_usage(username, usage)
    if usage["count"] >= MAX_FREE_REQUESTS:
        return {"allowed": False, "used": usage["count"], "limit": MAX_FREE_REQUESTS}
    return {"allowed": True, "used": usage["count"], "limit": MAX_FREE_REQUESTS}

def increment_usage(username):
    usage = load_usage(username)
    now = datetime.datetime.now()
    if usage["month"] != now.month or usage["year"] != now.year:
        usage = {"count": 0, "month": now.month, "year": now.year}
    usage["count"] += 1
    save_usage(username, usage)
    users = load_users()
    if username in users:
        users[username]["total_requests"] = users[username].get("total_requests", 0) + 1
        save_users(users)
    return usage["count"]

def get_usage_status(username):
    usage = load_usage(username)
    now = datetime.datetime.now()
    if usage["month"] != now.month or usage["year"] != now.year:
        usage = {"count": 0, "month": now.month, "year": now.year}
        save_usage(username, usage)
    remaining = max(0, MAX_FREE_REQUESTS - usage["count"])
    return {
        "used": usage["count"],
        "limit": MAX_FREE_REQUESTS,
        "remaining": remaining,
        "percentage": round((usage["count"] / MAX_FREE_REQUESTS) * 100, 1)
    }

def is_premium(username):
    user_data = load_users().get(username, {})
    premium_until = user_data.get("premium_until")
    if premium_until:
        try:
            expiry = datetime.datetime.fromisoformat(premium_until)
            return expiry > datetime.datetime.now()
        except:
            return False
    return False

# === AUTH FUNCTIONS ===
def login_user(username, password):
    users = load_users()
    if username not in users:
        return {"success": False, "error": "Username tidak wujud"}
    if users[username]["password"] != hash_password(password):
        return {"success": False, "error": "Password salah"}
    return {"success": True, "username": username, "role": users[username].get("role", "user")}

def register_user(username, password, email, name=""):
    users = load_users()
    if username in users:
        return {"success": False, "error": "Username sudah wujud"}
    if len(password) < 6:
        return {"success": False, "error": "Password mesti 6 aksara"}
    users[username] = {
        "password": hash_password(password),
        "role": "user",
        "email": email,
        "name": name or username,
        "avatar": f"https://ui-avatars.com/api/?name={name or username}&background=4d6bfe&color=fff&size=40",
        "settings": {"language": "Malay", "dark_mode": True},
        "created_at": datetime.datetime.now().isoformat(),
        "premium_until": None,
        "total_requests": 0
    }
    save_users(users)
    return {"success": True, "username": username}

def get_user_data(username):
    users = load_users()
    return users.get(username, {})

def update_user(username, data):
    users = load_users()
    if username in users:
        users[username].update(data)
        save_users(users)
        return True
    return False

# === AI FUNCTIONS ===
def call_groq(prompt):
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        payload = {"model": "llama-3.1-70b-versatile", "messages": [{"role": "user", "content": prompt}], "temperature": 0.7, "max_tokens": 2048}
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        return f"Ralat Groq: {response.status_code}"
    except Exception as e:
        return f"Ralat: {str(e)}"

def call_deepseek_r1(prompt):
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://mychatai.com",
            "X-Title": "MyChatAI Pro"
        }
        payload = {"model": "deepseek/deepseek-r1", "messages": [{"role": "user", "content": prompt}], "temperature": 0.7, "max_tokens": 4096}
        response = requests.post(url, json=payload, headers=headers, timeout=90)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        return f"Ralat DeepSeek: {response.status_code}"
    except Exception as e:
        return f"Ralat: {str(e)}"

def call_gemini(prompt):
    if not GEMINI_API_KEY:
        return None
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data['candidates'][0]['content']['parts'][0]['text']
        return None
    except:
        return None

def call_claude(prompt):
    if not CLAUDE_API_KEY:
        return None
    try:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": CLAUDE_API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "claude-3-haiku-20240307",
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}]
        }
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.json()['content'][0]['text']
        return None
    except:
        return None

def call_huggingface(prompt):
    if not HUGGINGFACE_API_KEY:
        return None
    try:
        url = "https://api-inference.huggingface.co/models/microsoft/DialoGPT-medium"
        headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
        payload = {"inputs": prompt}
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.json()[0]['generated_text']
        return None
    except:
        return None

def call_replicate(prompt):
    if not REPLICATE_API_KEY:
        return None
    try:
        url = "https://api.replicate.com/v1/predictions"
        headers = {"Authorization": f"Bearer {REPLICATE_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "version": "02e509c789964a7ea8736978a43525956ef40397be9033abf9fd2badfe68c9e3",
            "input": {"prompt": prompt}
        }
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code == 201:
            prediction_id = response.json()['id']
            for _ in range(30):
                status_response = requests.get(f"https://api.replicate.com/v1/predictions/{prediction_id}", headers=headers)
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    if status_data['status'] == 'succeeded':
                        return status_data['output']
                    elif status_data['status'] == 'failed':
                        return None
                time.sleep(1)
            return None
        return None
    except:
        return None

# ============================================================
# SMART AI DENGAN AUTO-FALLBACK
# ============================================================
def smart_ai_with_fallback(prompt):
    models = [
        ("Groq", call_groq),
        ("DeepSeek", call_deepseek_r1),
        ("Gemini", call_gemini),
        ("Claude", call_claude),
        ("HuggingFace", call_huggingface),
        ("Replicate", call_replicate)
    ]
    for model_name, model_func in models:
        try:
            response = model_func(prompt)
            if response and not response.startswith("Ralat") and not response.startswith("❌"):
                return response
        except:
            continue
    return "Maaf, semua model AI tidak dapat diakses. Sila cuba lagi nanti."

# ============================================================
# DETECT SOALAN "SIAPA ANDA" - VERSI DIPERBAHARUI (DIUBAH)
# ============================================================
def is_identity_question(prompt):
    identity_keywords = [
        "siapa anda", "siapa kamu", "siapa awak", "awak siapa", "anda siapa",
        "kamu siapa", "siapa kau", "kau siapa", "who are you", "who are u",
        "tell me about yourself", "introduce yourself", "perkenalkan diri",
        "siapakah anda", "siapakah kamu", "siapakah awak", "kenal diri",
        "perkenalan", "kenalkan diri", "apa nama awak", "nama awak siapa",
        "nama kamu siapa", "nama anda siapa", "what is your name",
        "your name", "siapa nama awak", "siapa nama kamu", "siapa nama anda"
    ]
    prompt_lower = prompt.lower().strip()
    for keyword in identity_keywords:
        if keyword in prompt_lower:
            return True
    return False

def get_identity_response():  # DIUBAH: ayat lebih menarik, kurang simbol
    return """Helo! Nama saya Joe, dan saya adalah AI assistant peribadi anda dari MyChatAI Pro.

Saya direka khas untuk membantu anda dengan pelbagai tugasan harian secara pantas dan efektif. Saya menggunakan gabungan model AI terbaik seperti Groq, DeepSeek-R1, Gemini, Claude, HuggingFace dan Replicate untuk memberikan jawapan yang tepat dan berkualiti.

Antara kelebihan saya:
- 1000 soalan percuma setiap bulan
- Boleh menjana gambar, video, muzik, RPH, invois, business plan dan banyak lagi
- Sokongan multi-bahasa (Melayu, Inggeris, Cina)

Ciri-ciri utama saya termasuklah chat pintar, generator RPH, art dan video, music generator (TTS dan Suno), invois dan quotation, integrasi WhatsApp, business tools, fitness tracker, meditation guide, research assistant, game master dan banyak lagi.

Ada apa-apa yang boleh saya bantu? Saya sedia membantu anda pada bila-bila masa."""

# ============================================================
# SMART AI - UTAMA
# ============================================================
def smart_ai(username, prompt, think_mode=False, search_mode=False):
    limit_check = check_usage_limit(username)
    if not limit_check["allowed"]:
        return f"Had Penggunaan Bulanan Telah Dicapai\nPenggunaan: {limit_check['used']}/{limit_check['limit']}"

    if is_identity_question(prompt):
        return get_identity_response()

    if think_mode:
        response = call_deepseek_r1(prompt)
    else:
        response = call_groq(prompt)

    if response.startswith("Ralat") or response.startswith("❌"):
        response = smart_ai_with_fallback(prompt)

    increment_usage(username)
    return response

# === CSS ===
def apply_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
    * { font-family: 'Inter', sans-serif; }
    .stApp { background: #0d0d0d; }
    .stSidebar { background: rgba(255,255,255,0.02) !important; border-right: 1px solid rgba(255,255,255,0.04) !important; }

    .chat-bubble-user {
        background: linear-gradient(135deg, #4d6bfe, #7c3aed);
        color: white;
        padding: 12px 18px;
        border-radius: 18px 18px 4px 18px;
        max-width: 80%;
        margin-left: auto;
        margin-bottom: 12px;
    }
    .chat-bubble-ai {
        background: rgba(255,255,255,0.05);
        color: #e8edf5;
        padding: 12px 18px;
        border-radius: 18px 18px 18px 4px;
        max-width: 80%;
        margin-right: auto;
        margin-bottom: 12px;
        border: 1px solid rgba(255,255,255,0.06);
    }

    .input-container {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: rgba(13,13,13,0.95);
        padding: 16px 20px;
        border-top: 1px solid rgba(255,255,255,0.06);
        backdrop-filter: blur(20px);
        z-index: 100;
    }
    .input-wrapper {
        max-width: 900px;
        margin: 0 auto;
        display: flex;
        align-items: center;
        gap: 8px;
        background: rgba(255,255,255,0.05);
        border-radius: 14px;
        padding: 6px 6px 6px 16px;
        border: 1px solid rgba(255,255,255,0.08);
    }
    .input-wrapper:focus-within {
        border-color: #4d6bfe;
    }
    .input-wrapper input {
        flex: 1;
        background: transparent;
        border: none;
        outline: none;
        color: #e8edf5;
        font-size: 16px;
        padding: 12px 0;
        min-height: 52px;
    }
    .input-wrapper input::placeholder {
        color: #5a5a6a;
        font-size: 15px;
    }

    .input-btn {
        background: transparent;
        border: none;
        color: #8a8a9a;
        padding: 8px 14px;
        border-radius: 10px;
        cursor: pointer;
        font-size: 14px;
        font-weight: 500;
        transition: all 0.2s;
        white-space: nowrap;
        height: 40px;
    }
    .input-btn:hover {
        background: rgba(255,255,255,0.06);
        color: #e8edf5;
    }
    .input-btn.active {
        color: #4d6bfe;
        background: rgba(77,107,254,0.15);
    }
    .input-btn.send-btn {
        background: linear-gradient(135deg, #4d6bfe, #7c3aed);
        color: white;
        padding: 8px 20px;
        border-radius: 10px;
        font-weight: 600;
        height: 40px;
        min-width: 80px;
    }
    .input-btn.send-btn:hover {
        transform: scale(1.02);
        box-shadow: 0 4px 20px rgba(77,107,254,0.3);
    }

    .profile-section {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px 16px;
        border-top: 1px solid rgba(255,255,255,0.04);
        margin-top: auto;
    }
    .profile-avatar {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        object-fit: cover;
    }
    .profile-name {
        flex: 1;
        font-size: 14px;
        font-weight: 600;
        color: #e8edf5;
    }
    .profile-email {
        font-size: 11px;
        color: #5a5a6a;
    }

    .settings-btn {
        background: transparent;
        border: none;
        color: #5a5a6a;
        cursor: pointer;
        font-size: 18px;
        padding: 4px 8px;
        border-radius: 6px;
    }
    .settings-btn:hover {
        background: rgba(255,255,255,0.05);
        color: #e8edf5;
    }

    .new-chat-btn {
        background: linear-gradient(135deg, #4d6bfe, #7c3aed);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 10px 16px;
        font-weight: 600;
        width: 100%;
        cursor: pointer;
        margin-bottom: 12px;
    }

    .history-item {
        padding: 8px 12px;
        border-radius: 8px;
        margin-bottom: 4px;
        cursor: pointer;
        font-size: 13px;
        color: #8a8a9a;
        transition: all 0.2s;
    }
    .history-item:hover {
        background: rgba(255,255,255,0.04);
        color: #e8edf5;
    }

    .brand-title {
        text-align: center;
        padding: 16px 0 10px 0;
        border-bottom: 1px solid rgba(255,255,255,0.04);
        margin-bottom: 12px;
    }
    .brand-title .main {
        font-size: 26px;
        font-weight: 800;
        background: linear-gradient(135deg, #4d6bfe, #7c3aed);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -0.5px;
    }
    .brand-title .version {
        font-size: 10px;
        color: #5a5a6a;
        letter-spacing: 1px;
        margin-top: 2px;
    }
    .brand-title .tagline {
        font-size: 11px;
        color: #4a4a5a;
        margin-top: 2px;
        letter-spacing: 0.5px;
    }

    .premium-badge {
        background: linear-gradient(135deg, #f59e0b, #d97706);
        padding: 2px 12px;
        border-radius: 12px;
        font-size: 10px;
        font-weight: 700;
        color: white;
        display: inline-block;
    }
    .status-online {
        color: #10b981;
        font-size: 10px;
    }

    .footer-credit {
        text-align: center;
        padding: 12px 0 8px 0;
        color: #3a3a4a;
        font-size: 10px;
        border-top: 1px solid rgba(255,255,255,0.03);
        margin-top: 10px;
    }

    @media (max-width: 768px) {
        .stSidebar { width: 280px !important; }
        .input-wrapper { padding: 4px 4px 4px 12px; }
        .input-btn { padding: 6px 10px; font-size: 12px; }
        .input-btn.send-btn { min-width: 60px; padding: 6px 14px; }
    }
    </style>
    """, unsafe_allow_html=True)

# === LOGIN UI ===
def login_ui():
    apply_css()
    st.markdown("""
    <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; min-height:100vh; padding:20px;">
        <div style="max-width:420px; width:100%; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.06); border-radius:20px; padding:40px 32px;">
            <div style="text-align:center; margin-bottom:30px;">
                <div style="font-size:48px; margin-bottom:8px;">💬</div>
                <h1 style="font-size:32px; font-weight:800; background:linear-gradient(135deg,#4d6bfe,#7c3aed); -webkit-background-clip:text; -webkit-text-fill-color:transparent;">MyChatAI Pro</h1>
                <p style="color:#8a8a9a; font-size:14px;">Groq · DeepSeek-R1 · Gemini · Claude</p>
                <p style="color:#5a5a6a; font-size:12px;">1000 Request Percuma · Premium Available</p>
            </div>
            <div style="display:flex; flex-direction:column; gap:12px;">
                <input type="text" placeholder="Username" id="login_user" style="width:100%; padding:14px 18px; border-radius:12px; border:1px solid rgba(255,255,255,0.06); background:rgba(255,255,255,0.02); color:#e8edf5; font-size:15px; outline:none;">
                <input type="password" placeholder="Password" id="login_pass" style="width:100%; padding:14px 18px; border-radius:12px; border:1px solid rgba(255,255,255,0.06); background:rgba(255,255,255,0.02); color:#e8edf5; font-size:15px; outline:none;">
                <input type="email" placeholder="Email (untuk daftar)" id="login_email" style="width:100%; padding:14px 18px; border-radius:12px; border:1px solid rgba(255,255,255,0.06); background:rgba(255,255,255,0.02); color:#e8edf5; font-size:15px; outline:none;">
                <button style="width:100%; padding:14px; background:linear-gradient(135deg,#4d6bfe,#7c3aed); border:none; border-radius:12px; font-weight:700; color:white; font-size:16px; cursor:pointer; margin-top:4px;" onclick="document.getElementById('login_btn').click();">🔓 Login</button>
                <div style="text-align:center; margin-top:8px; font-size:14px; color:#5a5a6a;">Tiada akaun? <a href="#" style="color:#4d6bfe; text-decoration:none;" onclick="document.getElementById('signup_btn').click();">Daftar Sekarang</a></div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input("Username", key="login_user_input", placeholder="", label_visibility="collapsed")
        password = st.text_input("Password", type="password", key="login_pass_input", placeholder="", label_visibility="collapsed")
        email = st.text_input("Email", key="login_email_input", placeholder="", label_visibility="collapsed")

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🔓 Login", key="login_btn", use_container_width=True):
                if username and password:
                    result = login_user(username, password)
                    if result["success"]:
                        st.session_state.logged_in = True
                        st.session_state.username = result["username"]
                        st.session_state.role = result["role"]
                        st.session_state.messages = []
                        st.rerun()
                    else:
                        st.error(result["error"])
                else:
                    st.warning("Sila isi username dan password")
        with col_b:
            if st.button("📝 Daftar", key="signup_btn", use_container_width=True):
                if username and password and email:
                    result = register_user(username, password, email)
                    if result["success"]:
                        st.success(f"Akaun '{username}' didaftarkan! Sila login.")
                    else:
                        st.error(result["error"])
                else:
                    st.warning("Sila isi semua maklumat")

# === SETTINGS MODAL ===
def settings_modal():
    username = st.session_state.username
    user_data = get_user_data(username)

    with st.sidebar:
        st.markdown("---")
        st.markdown("### Settings")

        lang = st.selectbox("🌐 Bahasa", ["Malay", "English", "Chinese"], index=0)
        dark_mode = st.toggle("Dark Mode", value=True)

        st.markdown("#### Tukar Password")
        old_pass = st.text_input("Password Lama", type="password", key="old_pass")
        new_pass = st.text_input("Password Baru", type="password", key="new_pass")
        confirm_pass = st.text_input("Confirm Password", type="password", key="confirm_pass")

        if st.button("Tukar Password", use_container_width=True):
            users = load_users()
            if username in users:
                if users[username]["password"] == hash_password(old_pass):
                    if new_pass == confirm_pass and len(new_pass) >= 6:
                        users[username]["password"] = hash_password(new_pass)
                        save_users(users)
                        st.success("✅ Password berjaya ditukar!")
                    else:
                        st.error("Password baru tidak sama atau kurang 6 aksara")
                else:
                    st.error("Password lama salah")

        st.markdown("---")
        st.markdown("### Usage Status")
        usage = get_usage_status(username)
        st.progress(usage["percentage"] / 100)
        st.caption(f"Digunakan: {usage['used']} / {usage['limit']} (Bulanan)")
        st.caption(f"Baki: {usage['remaining']} request")

        st.markdown("---")
        st.markdown("### Help & Feedback")
        feedback = st.text_area("Hantar feedback atau laporkan isu:", height=80)
        if st.button("📤 Hantar Feedback", use_container_width=True):
            if DISCORD_WEBHOOK:
                try:
                    data = {"content": f"Feedback dari {username}: {feedback}"}
                    requests.post(DISCORD_WEBHOOK, json=data, timeout=10)
                except:
                    pass
            st.success("✅ Terima kasih! Feedback anda akan diproses.")

        st.markdown("---")
        st.caption("MyChatAI Pro v42.0")
        st.caption(f"{username} | {st.session_state.role}")

# === CHAT UI ===
def chat_ui():
    username = st.session_state.username
    user_data = get_user_data(username)

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "think_mode" not in st.session_state:
        st.session_state.think_mode = False
    if "search_mode" not in st.session_state:
        st.session_state.search_mode = False
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = load_chats().get(username, [])
    if "show_settings" not in st.session_state:
        st.session_state.show_settings = False

    apply_css()

    with st.sidebar:
        st.markdown("""
        <div class="brand-title">
            <div class="main">💬 MyChatAI Pro</div>
            <div class="version">v42.0</div>
            <div class="tagline">✨ Smart AI Assistant</div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("➕ New Chat", key="new_chat_btn", use_container_width=True):
            if st.session_state.messages:
                history = load_chats()
                if username not in history:
                    history[username] = []
                chat_title = st.session_state.messages[0]["content"][:50] if st.session_state.messages else "New Chat"
                history[username].append({
                    "title": chat_title,
                    "messages": st.session_state.messages,
                    "time": datetime.datetime.now().isoformat()
                })
                save_chats(history)
                st.session_state.chat_history = history.get(username, [])
            st.session_state.messages = []
            st.rerun()

        search_query = st.text_input("🔍 Cari sejarah...", key="search_history", placeholder="Taip untuk cari...", label_visibility="collapsed")

        features = [
            "RPH", "Art", "Video", "Music",
            "Invois", "WhatsApp", "Neural", "Roadtax",
            "IC", "Kontraktor", "Business", "Fitness",
            "Meditation", "Research", "Comic", "Game",
            "Analytics"
        ]
        selected = st.selectbox("📂 Ciri-ciri", ["-- Pilih --"] + features, key="feature_select", label_visibility="collapsed")
        if selected != "-- Pilih --":
            st.session_state.current_tab = selected
            st.rerun()

        st.markdown("---")
        st.markdown("### history chat")

        history = load_chats().get(username, [])
        if search_query:
            history = [h for h in history if search_query.lower() in h.get("title", "").lower()]

        today = datetime.datetime.now().date()
        this_week = today - datetime.timedelta(days=7)

        for chat in reversed(history[-50:]):
            chat_time = datetime.datetime.fromisoformat(chat.get("time", datetime.datetime.now().isoformat()))
            title = chat.get("title", "Chat")[:40]
            if st.button(f"💬 {title}", key=f"hist_{chat.get('time', '')}", use_container_width=True):
                st.session_state.messages = chat.get("messages", [])
                st.rerun()

        st.markdown("---")

        if is_premium(username):
            st.markdown('<span class="premium-badge">PREMIUM</span>', unsafe_allow_html=True)

        st.markdown(f"""
        <div class="profile-section">
            <img src="{user_data.get('avatar', DEFAULT_AVATAR)}" class="profile-avatar">
            <div>
                <div class="profile-name">{user_data.get('name', username)} <span class="status-online">● Online</span></div>
                <div class="profile-email">{user_data.get('email', '')}</div>
            </div>
            <button class="settings-btn" onclick="document.getElementById('settings_btn').click();">⚙️</button>
        </div>
        """, unsafe_allow_html=True)

        if st.button("⚙️", key="settings_btn", help="Settings"):
            st.session_state.show_settings = not st.session_state.get("show_settings", False)
            st.rerun()

        if st.session_state.get("show_settings", False):
            settings_modal()

        st.markdown("""
        <div class="footer-credit">
            © 2026 <span style="color:#ec4899;">❤</span> MyChatAI Pro
        </div>
        """, unsafe_allow_html=True)

    # === MAIN CHAT ===
    if not st.session_state.messages:
        st.markdown(f"""
        <div style="text-align:center; padding:60px 20px;">
            <div style="font-size:48px; margin-bottom:16px;">💬</div>
            <h2 style="color:#e8edf5; font-weight:600;">Selamat datang, {user_data.get('name', username)}!</h2>
            <p style="color:#8a8a9a; font-size:16px;">Tanya apa-apa atau mula chat dengan AI.</p>
            <p style="color:#5a5a6a; font-size:13px; margin-top:8px;">💡 Tekan Enter untuk hantar</p>
            <p style="color:#4a4a5a; font-size:11px; margin-top:4px;">Groq · DeepSeek · Gemini · Claude · HuggingFace · Replicate</p>
        </div>
        """, unsafe_allow_html=True)

    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f'<div class="chat-bubble-user">{msg["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-bubble-ai">{msg["content"]}</div>', unsafe_allow_html=True)

    # === INPUT ===
    st.markdown("""
    <div class="input-container">
        <div class="input-wrapper">
    """, unsafe_allow_html=True)

    col_input, col_think, col_search, col_send = st.columns([4, 1.2, 1.2, 1.5])

    with col_input:
        user_input = st.text_input("", key="chat_input", placeholder="Taip mesej... (Enter untuk hantar)", label_visibility="collapsed")

    with col_think:
        think_label = "Think ✓" if st.session_state.think_mode else "Think"
        if st.button(think_label, key="think_btn", use_container_width=True):
            st.session_state.think_mode = not st.session_state.think_mode
            st.rerun()

    with col_search:
        search_label = "🔍 Search ✓" if st.session_state.search_mode else "🔍 Search"
        if st.button(search_label, key="search_btn", use_container_width=True):
            st.session_state.search_mode = not st.session_state.search_mode
            st.rerun()

    with col_send:
        if st.button("➤ Send", key="send_btn", use_container_width=True):
            if user_input.strip():
                st.session_state.messages.append({"role": "user", "content": user_input})
                with st.spinner("Menghasilkan..."):
                    response = smart_ai(username, user_input, st.session_state.think_mode, st.session_state.search_mode)
                st.session_state.messages.append({"role": "ai", "content": response})
                st.rerun()

    st.markdown("""
        </div>
    </div>
    """, unsafe_allow_html=True)

    # JavaScript untuk Enter key
    st.markdown("""
    <script>
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            var input = document.querySelector('input[data-testid="stTextInput"]');
            if (input && document.activeElement === input) {
                e.preventDefault();
                var btns = document.querySelectorAll('button');
                for (var btn of btns) {
                    if (btn.textContent.includes('Send') || btn.textContent.includes('➤')) {
                        btn.click();
                        setTimeout(function() {
                            input.value = '';
                            input.dispatchEvent(new Event('input', { bubbles: true }));
                        }, 100);
                        break;
                    }
                }
            }
        }
    });
    </script>
    """, unsafe_allow_html=True)

# === FEATURE UI ===
def feature_ui(feature):
    username = st.session_state.username

    st.markdown(f"### {feature}")

    if feature == "RPH":
        col1, col2 = st.columns(2)
        with col1:
            subjek = st.selectbox("Subjek", ["Bahasa Melayu", "Bahasa Inggeris", "Matematik", "Sains", "Sejarah"])
            tahun = st.selectbox("Tahun", ["Tahun 1", "Tahun 2", "Tahun 3", "Tahun 4", "Tahun 5", "Tahun 6"])
        with col2:
            topik = st.text_input("Topik")
            tempoh = st.selectbox("Tempoh", ["30 minit", "60 minit"])
        if st.button("Jana RPH", use_container_width=True) and topik:
            rph = call_deepseek_r1(f"Sediakan RPH {subjek} Tahun {tahun}, topik {topik}, tempoh {tempoh}")
            st.markdown(rph)

    elif feature == "Art":
        prompt = st.text_input("Huraikan gambar")
        if st.button("Hasilkan", use_container_width=True) and prompt:
            try:
                url = f"https://image.pollinations.ai/prompt/{prompt}?width=1024&height=1024&nologo=true"
                response = requests.get(url, timeout=60)
                if response.status_code == 200:
                    img = Image.open(BytesIO(response.content))
                    st.image(img, use_container_width=True)
                else:
                    st.error("Gagal menghasilkan gambar")
            except:
                st.error("Ralat")

    elif feature == "🎬 Video":
        prompt = st.text_area("Huraikan video", height=80)
        duration = st.slider("Durasi (saat)", 3, 15, 5)
        if st.button("Hasilkan Video", use_container_width=True) and prompt:
            with st.spinner("Menghasilkan video..."):
                try:
                    url = f"https://image.pollinations.ai/video?prompt={prompt}&duration={duration}"
                    response = requests.get(url, timeout=120)
                    if response.status_code == 200:
                        st.video(response.content)
                    else:
                        st.error("Gagal menghasilkan video")
                except:
                    st.error("Ralat")

    elif feature == "🎵 Music":
        st.info("🎵 Music Generator - Hasilkan lagu dengan TTS atau Suno")
        mode = st.radio("Pilih Mod:", ["TTS (Percuma)", "Suno (Lagu Sebenar)"], horizontal=True)
        prompt = st.text_area("Huraikan lagu:", height=80)
        style = st.selectbox("Gaya:", ["pop", "rock", "jazz", "classical", "hip-hop", "rnb", "electronic", "acoustic"])
        if st.button("Hasilkan Lagu", use_container_width=True) and prompt:
            if mode == "TTS (Percuma)":
                try:
                    tts_url = f"https://api.pollinations.ai/tts?text={prompt[:500]}&voice=alloy"
                    response = requests.get(tts_url, timeout=60)
                    if response.status_code == 200:
                        st.audio(response.content, format="audio/mp3")
                    else:
                        st.error("Gagal menghasilkan audio")
                except:
                    st.error("Ralat")
            else:
                st.warning("Suno API memerlukan setup tambahan. Guna TTS dahulu.")

    elif feature == "Invois":
        company = st.text_input("Nama Syarikat")
        customer = st.text_input("Nama Pelanggan")
        desc = st.text_input("Keterangan")
        jumlah = st.number_input("Jumlah (RM)", min_value=0.0, value=0.0)
        if st.button("Hasilkan Invois", use_container_width=True) and company and customer:
            st.success(f"Invois untuk {customer} berjaya dihasilkan")
            st.markdown(f"""
            **{company}**
            Pelanggan: {customer}
            Keterangan: {desc or "Perkhidmatan"}
            Jumlah: RM {jumlah:,.2f}
            Tarikh: {datetime.datetime.now().strftime('%d %B %Y')}
            """)

    elif feature == "WhatsApp":
        phone = st.text_input("No Telefon", placeholder="60123456789")
        message = st.text_area("Mesej", height=100)
        if st.button("Hantar", use_container_width=True) and phone and message:
            clean_phone = re.sub(r'[^0-9]', '', phone)
            if not clean_phone.startswith('6'):
                clean_phone = '6' + clean_phone
            msg_encoded = requests.utils.quote(message)
            whatsapp_url = f"https://wa.me/{clean_phone}?text={msg_encoded}"
            st.markdown(f'<a href="{whatsapp_url}" target="_blank"><button style="background:#25D366; color:white; padding:8px 16px; border:none; border-radius:8px; font-weight:600; cursor:pointer;">Buka WhatsApp</button></a>', unsafe_allow_html=True)

    elif feature == "Neural":
        st.markdown("""
        Neural Networks adalah sistem komputasi yang terinspirasi dari otak manusia.
        **Komponen Utama:**
        - Input Layer
        - Hidden Layers
        - Output Layer
        - Weights & Biases
        **Jenis-Jenis:**
        1. CNN - Untuk imej & video
        2. RNN - Untuk data berurutan
        3. LSTM - RNN dengan ingatan
        4. Transformers - Asas ChatGPT
        5. GANs - Menghasilkan data baru
        """)

    elif feature == "Roadtax":
        st.info("Untuk semakan sebenar, gunakan aplikasi MyJPJ")
        st.markdown("""
        **Simulasi:**
        - Roadtax: SAH (Tamat: 31/12/2026)
        - Saman: 2 saman (RM 600)
        - Insurans: AKTIF
        """)

    elif feature == "IC":
        st.info("Untuk semakan sebenar, gunakan portal rasmi")
        st.markdown("""
        **Simulasi:**
        - STR: LAYAK (RM 500)
        - BPN: LAYAK (RM 1,200)
        - BKC: LAYAK (RM 250)
        """)

    elif feature == "Kontraktor":
        tender_name = st.text_input("Nama Projek")
        tender_budget = st.number_input("Bajet (RM)", min_value=0.0, value=0.0)
        if st.button("Buka Tender", use_container_width=True) and tender_name and tender_budget > 0:
            st.success(f"Tender '{tender_name}' berjaya dibuka")

    elif feature == " Business":
        st.markdown("""
        - Business Plan
        - Market Analysis
        - SWOT Analysis
        - Pricing Strategy
        - Pitch Deck
        """)
        if st.button("Jana Business Plan", use_container_width=True):
            response = call_deepseek_r1("Hasilkan business plan untuk startup teknologi")
            st.markdown(response)

    elif feature == " Fitness":
        goal = st.selectbox("Matlamat", ["Turun Berat", "Bina Otot", "Kekal Sihat"])
        days = st.slider("Hari seminggu", 1, 7, 3)
        if st.button("Jana Rancangan", use_container_width=True):
            response = call_deepseek_r1(f"Hasilkan rancangan senaman untuk matlamat {goal} ({days} hari seminggu)")
            st.markdown(response)

    elif feature == " Meditation":
        duration = st.slider("Durasi (minit)", 1, 30, 10)
        if st.button("Mula Meditasi", use_container_width=True):
            response = call_deepseek_r1(f"Panduan meditasi selama {duration} minit")
            st.markdown(response)

    elif feature == "Research":
        topic = st.text_input("Topik Penyelidikan")
        if st.button("Mulakan Penyelidikan", use_container_width=True) and topic:
            response = call_deepseek_r1(f"Buat literature review untuk topik: {topic}")
            st.markdown(response)

    elif feature == "Comic":
        title = st.text_input("Tajuk Komik")
        if st.button("Hasilkan Komik", use_container_width=True) and title:
            response = call_deepseek_r1(f"Hasilkan komik bertajuk: {title}")
            st.markdown(response)

    elif feature == "Game":
        game_type = st.selectbox("Jenis", ["Escape Room", "Murder Mystery", "Treasure Hunt", "Adventure"])
        if st.button("Mula Permainan", use_container_width=True):
            response = call_deepseek_r1(f"Cipta {game_type} yang menarik")
            st.markdown(response)

    elif feature == "Analytics":
        users = load_users()
        chats = load_chats()
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Pengguna", len(users))
        with col2:
            st.metric("Chat Total", sum(len(c) for c in chats.values()))
        with col3:
            st.metric("Request", "1000/bulan")
        with col4:
            st.metric("Status", "✅ Aktif")

    else:
        st.info("Ciri ini sedang dibangunkan.")

# === MAIN ===
def main():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "username" not in st.session_state:
        st.session_state.username = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "current_tab" not in st.session_state:
        st.session_state.current_tab = "Chat"
    if "show_settings" not in st.session_state:
        st.session_state.show_settings = False
    if "think_mode" not in st.session_state:
        st.session_state.think_mode = False
    if "search_mode" not in st.session_state:
        st.session_state.search_mode = False

    if not st.session_state.logged_in:
        login_ui()
        return

    if st.session_state.current_tab == "Chat":
        chat_ui()
    else:
        feature_ui(st.session_state.current_tab)

if __name__ == "__main__":
    main()
