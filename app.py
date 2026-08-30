# mychat_ultimate_pro_v35.py
import streamlit as st
import datetime
import json
import os
import requests
import time
import random
import hashlib
import uuid
import re
from PIL import Image
from io import BytesIO
import pandas as pd
import base64

# === PAGE CONFIG ===
st.set_page_config(
    page_title="MyChatAI",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# === API KEYS (GUNA STREAMLIT SECRETS - TANPA HARDCODE) ===
try:
    GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
    GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")
    SEARCH_API_KEY = st.secrets.get("SEARCH_API_KEY", "")
except:
    GEMINI_API_KEY = ""
    GROQ_API_KEY = ""
    SEARCH_API_KEY = ""

# === KONSTAN ===
USER_DATA_FILE = "mychat_users.json"
CHAT_HISTORY_FILE = "mychat_chats.json"
POINTS_FILE = "mychat_points.json"
RPH_HISTORY_FILE = "rph_history.json"

# ===== ADMIN AUTO DETECT =====
ADMIN_EMAILS = ["joe.adie77711@gmail.com"]
ADMIN_USERNAMES = ["joe.adie", "admin"]

def is_admin_user(email, username=None):
    if email in ADMIN_EMAILS:
        return True
    if username and username in ADMIN_USERNAMES:
        return True
    return False

def get_user_role(email, username=None):
    return "admin" if is_admin_user(email, username) else "user"

# ============================================================
# 🎨 MINIMAL CSS
# ============================================================
def apply_minimal_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
        
        * { 
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; 
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        .stApp {
            background: #0d0d0d;
        }
        
        .stSidebar {
            background: rgba(255,255,255,0.02) !important;
            border-right: 1px solid rgba(255,255,255,0.04) !important;
            padding: 20px 16px !important;
            overflow-y: auto;
        }
        
        .stSidebar .stButton > button {
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .logo-text {
            font-size: 1.2rem;
            font-weight: 700;
            color: #ffffff;
            padding: 8px 4px 16px 4px;
            text-align: center;
            border-bottom: 1px solid rgba(255,255,255,0.04);
            margin-bottom: 16px;
        }
        .logo-text .brand {
            background: linear-gradient(135deg, #4d6bfe, #7c3aed);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .logo-text .version {
            background: linear-gradient(135deg, #4d6bfe, #7c3aed);
            color: white;
            font-size: 0.5rem;
            padding: 2px 8px;
            border-radius: 30px;
            -webkit-text-fill-color: white;
            font-weight: 600;
        }
        
        .user-card {
            background: rgba(255,255,255,0.03);
            border-radius: 12px;
            padding: 16px;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.04);
            margin-bottom: 16px;
        }
        .user-card .username {
            font-weight: 600;
            font-size: 0.95rem;
            color: #e8edf5;
            margin: 4px 0;
        }
        .user-card .role {
            font-size: 0.6rem;
            color: #5a5a6a;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .user-card .badges {
            display: flex;
            gap: 4px;
            justify-content: center;
            flex-wrap: wrap;
            margin-top: 6px;
        }
        .badge-item {
            padding: 2px 12px;
            border-radius: 20px;
            font-size: 0.55rem;
            font-weight: 600;
        }
        .badge-tier { background: #4d6bfe; color: white; }
        .badge-points { background: linear-gradient(135deg,#4d6bfe,#7c3aed); color: white; }
        .badge-level { background: rgba(255,255,255,0.06); color: #8a8a9a; }
        .badge-admin { background: #7c3aed; color: white; }
        
        .stButton > button {
            background: transparent;
            color: #e8edf5;
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 10px;
            font-weight: 500;
            padding: 8px 16px;
            transition: all 0.2s ease;
            width: 100%;
            font-size: 0.85rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .stButton > button:hover {
            background: rgba(255,255,255,0.04);
            border-color: rgba(255,255,255,0.1);
        }
        
        .btn-new {
            background: linear-gradient(135deg, #4d6bfe, #7c3aed);
            color: white;
            border: none;
            border-radius: 10px;
            font-weight: 600;
            padding: 10px 16px;
            width: 100%;
            cursor: pointer;
            transition: all 0.2s ease;
            margin-bottom: 12px;
            font-size: 0.9rem;
        }
        .btn-new:hover {
            transform: scale(1.01);
            box-shadow: 0 4px 20px rgba(77,107,254,0.2);
        }
        
        .message-row {
            display: flex;
            max-width: 85%;
            animation: fadeUp 0.3s ease;
            margin-bottom: 8px;
        }
        .message-row.user {
            align-self: flex-end;
            justify-content: flex-end;
        }
        .message-row.ai {
            align-self: flex-start;
            justify-content: flex-start;
        }
        
        .message-bubble {
            padding: 10px 16px;
            border-radius: 14px;
            line-height: 1.6;
            font-size: 0.9rem;
            word-break: break-word;
            max-width: 100%;
        }
        .message-row.user .message-bubble {
            background: linear-gradient(135deg, #4d6bfe, #7c3aed);
            color: white;
            border-bottom-right-radius: 4px;
        }
        .message-row.ai .message-bubble {
            background: rgba(255,255,255,0.03);
            color: #e8edf5;
            border: 1px solid rgba(255,255,255,0.04);
            border-bottom-left-radius: 4px;
        }
        
        .message-bubble p { margin: 2px 0; }
        .message-bubble a { color: #4d6bfe; text-decoration: none; }
        .message-bubble a:hover { text-decoration: underline; }
        
        .message-bubble pre {
            background: #0d0d0d;
            padding: 12px 16px;
            border-radius: 8px;
            overflow-x: auto;
            margin: 6px 0;
            border: 1px solid rgba(255,255,255,0.04);
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            line-height: 1.6;
            color: #e8edf5;
        }
        .message-bubble pre code { font-family: inherit; }
        
        .metric-card {
            background: rgba(255,255,255,0.02);
            border: 1px solid rgba(255,255,255,0.04);
            border-radius: 10px;
            padding: 14px 16px;
            text-align: center;
        }
        .metric-card .value {
            font-size: 1.6rem;
            font-weight: 700;
            color: #e8edf5;
        }
        .metric-card .label {
            font-size: 0.65rem;
            color: #5a5a6a;
        }
        
        .input-area {
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.04);
            border-radius: 12px;
            padding: 6px 8px 6px 16px;
            display: flex;
            align-items: flex-end;
            gap: 8px;
            transition: border-color 0.2s ease;
        }
        .input-area:focus-within {
            border-color: rgba(77,107,254,0.3);
        }
        .input-area textarea {
            flex: 1;
            background: transparent;
            border: none;
            outline: none;
            color: #e8edf5;
            font-size: 0.9rem;
            resize: none;
            padding: 8px 0;
            min-height: 24px;
            max-height: 150px;
            font-family: 'Inter', sans-serif;
        }
        .input-area textarea::placeholder {
            color: #5a5a6a;
        }
        .input-area .send-btn {
            background: linear-gradient(135deg, #4d6bfe, #7c3aed);
            border: none;
            color: white;
            width: 36px;
            height: 36px;
            border-radius: 50%;
            font-size: 0.9rem;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }
        .input-area .send-btn:hover {
            transform: scale(1.05);
            box-shadow: 0 4px 20px rgba(77,107,254,0.2);
        }
        .input-area .send-btn:disabled {
            opacity: 0.4;
            pointer-events: none;
        }
        
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }
        ::-webkit-scrollbar-track { background: transparent; }
        
        @keyframes fadeUp {
            0% { opacity: 0; transform: translateY(8px); }
            100% { opacity: 1; transform: translateY(0); }
        }
        
        @media (max-width: 768px) {
            .stSidebar { width: 280px !important; }
            .message-row { max-width: 95%; }
            .message-bubble { font-size: 0.85rem; padding: 8px 14px; }
        }
    </style>
    """, unsafe_allow_html=True)

# ============================================================
# 📋 SISTEM AKAUN & DATA FUNCTIONS
# ============================================================

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

TIERS = {
    "biasa": {
        "label": "Biasa",
        "color": "#8a8a9a",
        "badge": "Free",
        "limits": {"chat": 10, "art": 3, "rph": 2, "whatsapp": 5, "expert": 5, "search": 5},
        "features": {"chat": True, "art": True, "expert": True, "rph": True, "invoice": True, "whatsapp": True, "search": True},
        "points_multiplier": 1.0,
        "price": "RM 0/bulan"
    },
    "plus": {
        "label": "Plus",
        "color": "#ffd700",
        "badge": "Plus",
        "limits": {"chat": 25, "art": 10, "rph": 5, "whatsapp": 15, "expert": 10, "search": 15},
        "features": {"chat": True, "art": True, "expert": True, "rph": True, "invoice": True, "whatsapp": True, "search": True},
        "points_multiplier": 1.5,
        "price": "RM 9.90/bulan"
    },
    "super_plus": {
        "label": "Super Plus",
        "color": "#7b2ffc",
        "badge": "Super",
        "limits": {"chat": 50, "art": 20, "rph": 10, "whatsapp": 30, "expert": 20, "search": 30},
        "features": {"chat": True, "art": True, "expert": True, "rph": True, "invoice": True, "whatsapp": True, "search": True},
        "points_multiplier": 2.0,
        "price": "RM 24.90/bulan"
    },
    "pro_super": {
        "label": "Pro Super",
        "color": "#ff6fd8",
        "badge": "Pro",
        "limits": {"chat": 999, "art": 999, "rph": 999, "whatsapp": 999, "expert": 999, "search": 999},
        "features": {"chat": True, "art": True, "expert": True, "rph": True, "invoice": True, "whatsapp": True, "search": True},
        "points_multiplier": 3.0,
        "price": "RM 49.90/bulan"
    }
}

def load_users():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, "r") as f:
            return json.load(f)
    default = {
        "admin": {
            "password": hash_password("777777"),
            "role": "admin",
            "email": "admin@mychatai.com",
            "tier": "pro_super",
            "points": 0,
            "badges": [],
            "custom_limits": {},
            "settings": {"temperature": 0.7, "model": "groq", "max_tokens": 2048}
        },
        "joe.adie": {
            "password": hash_password("220481"),
            "role": "admin",
            "email": "joe.adie77711@gmail.com",
            "tier": "pro_super",
            "points": 1000,
            "badges": ["Founder", "Pioneer"],
            "custom_limits": {},
            "settings": {"temperature": 0.7, "model": "groq", "max_tokens": 2048}
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

def load_points():
    if os.path.exists(POINTS_FILE):
        with open(POINTS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_points(data):
    with open(POINTS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def load_rph_history():
    if os.path.exists(RPH_HISTORY_FILE):
        with open(RPH_HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

def save_rph_history(data):
    with open(RPH_HISTORY_FILE, "w") as f:
        json.dump(data, f, indent=2)

def login_user(username, password):
    users = load_users()
    if username not in users:
        return {"success": False, "error": "Username tidak wujud!"}
    if users[username]["password"] != hash_password(password):
        return {"success": False, "error": "Password salah!"}
    reset_daily_usage(username)
    return {"success": True, "username": username, "role": users[username].get("role", "user")}

def register_user(username, password, email):
    users = load_users()
    if username in users:
        return {"success": False, "error": "Username sudah wujud!"}
    if len(password) < 6:
        return {"success": False, "error": "Password mesti 6 aksara!"}
    
    is_admin = is_admin_user(email, username)
    role = "admin" if is_admin else "user"
    tier = "pro_super" if is_admin else "biasa"
    points = 1000 if is_admin else 100
    badges = ["Founder", "Pioneer"] if is_admin else []
    
    users[username] = {
        "password": hash_password(password),
        "role": role,
        "email": email,
        "tier": tier,
        "points": points,
        "badges": badges,
        "custom_limits": {},
        "settings": {"temperature": 0.7, "model": "groq", "max_tokens": 2048},
        "usage": {"chat": 0, "art": 0, "rph": 0, "whatsapp": 0, "expert": 0, "search": 0, "date": datetime.datetime.now().date().isoformat()}
    }
    save_users(users)
    return {"success": True, "username": username, "is_admin": is_admin}

def reset_daily_usage(username):
    users = load_users()
    today = datetime.datetime.now().date().isoformat()
    if username in users and users[username].get("usage", {}).get("date") != today:
        users[username]["usage"] = {"chat": 0, "art": 0, "rph": 0, "whatsapp": 0, "expert": 0, "search": 0, "date": today}
        save_users(users)

def get_user_tier(username):
    users = load_users()
    return users.get(username, {}).get("tier", "biasa")

def get_tier_limits(username):
    return TIERS[get_user_tier(username)]["limits"]

def get_tier_features(username):
    return TIERS[get_user_tier(username)]["features"]

def get_tier_multiplier(username):
    return TIERS[get_user_tier(username)]["points_multiplier"]

def get_tier_badge(username):
    return TIERS[get_user_tier(username)]["badge"]

def get_tier_label(username):
    return TIERS[get_user_tier(username)]["label"]

def get_tier_color(username):
    return TIERS[get_user_tier(username)]["color"]

def has_feature_override(username, feature):
    if load_users().get(username, {}).get("role") == "admin":
        return True
    return get_tier_features(username).get(feature, False)

def check_limit_override(username, feature):
    user = load_users().get(username, {})
    
    if user.get("role") == "admin":
        return {"allowed": True, "used": 0, "limit": 999}
    
    custom_limits = user.get("custom_limits", {})
    if feature in custom_limits and custom_limits[feature] > 0:
        limit = custom_limits[feature]
    else:
        limits = get_tier_limits(username)
        limit = limits.get(feature, 10)
    
    usage = user.get("usage", {})
    used = usage.get(feature, 0)
    
    return {"allowed": used < limit, "used": used, "limit": limit}

def increment_usage(username, feature):
    users = load_users()
    if username in users:
        users[username]["usage"][feature] = users[username]["usage"].get(feature, 0) + 1
        save_users(users)

def get_user_points(username):
    data = load_points()
    return data.get(username, {"points": 0, "badges": [], "level": 1})

def add_points(username, points):
    data = load_points()
    if username not in data:
        data[username] = {"points": 0, "badges": [], "level": 1}
    data[username]["points"] += points
    data[username]["level"] = (data[username]["points"] // 100) + 1
    badges = data[username]["badges"]
    if data[username]["points"] >= 10 and "Beginner" not in badges:
        badges.append("Beginner")
    if data[username]["points"] >= 50 and "Chatter" not in badges:
        badges.append("Chatter")
    if data[username]["points"] >= 100 and "Pro" not in badges:
        badges.append("Pro")
    if data[username]["points"] >= 500 and "Legend" not in badges:
        badges.append("Legend")
    save_points(data)
    return data[username]

def add_points_override(username, points):
    return add_points(username, int(points * get_tier_multiplier(username)))

# ============================================================
# 🤖 AI FUNCTIONS
# ============================================================

def call_groq(prompt):
    if not GROQ_API_KEY or GROQ_API_KEY == "":
        return "API Key Groq belum diset! Sila set di Streamlit Secrets."
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

def call_gemini(prompt, temperature=0.7):
    if not GEMINI_API_KEY or GEMINI_API_KEY == "":
        return "API Key Gemini belum diset! Sila set di Streamlit Secrets."
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
        payload = {"contents": [{"parts": [{"text": prompt[:3000]}]}], "generationConfig": {"temperature": temperature, "maxOutputTokens": 2048}}
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        return f"Ralat Gemini: {response.status_code}"
    except Exception as e:
        return f"Ralat: {str(e)}"

def get_ai_response(prompt, use_gemini=False):
    if use_gemini:
        return call_gemini(prompt)
    return call_groq(prompt)

def call_web_search(query):
    if not SEARCH_API_KEY or SEARCH_API_KEY == "":
        return "API Search belum diset! Sila set di Streamlit Secrets."
    try:
        url = "https://api.brightdata.com/request"
        headers = {
            "Authorization": f"Bearer {SEARCH_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "zone": "serp_api1",
            "url": f"https://www.google.com/search?q={query}",
            "format": "json",
            "data_format": "parsed_light"
        }
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get("organic", [])
            if results:
                output = f"Hasil Carian: '{query}'\n\n"
                for i, item in enumerate(results[:5]):
                    title = item.get('title', '')
                    snippet = item.get('description', '')
                    link = item.get('link', '')
                    output += f"{i+1}. {title}\n"
                    output += f"   {snippet[:200]}\n"
                    output += f"   {link}\n\n"
                return output
            return f"Tiada hasil untuk '{query}'."
        return f"Ralat Search: {response.status_code}"
    except Exception as e:
        return f"Ralat: {str(e)}"

def generate_image(prompt, style="realistic"):
    styles = {"realistic": "photorealistic, 8k", "anime": "anime style", "cartoon": "cartoon style", "fantasy": "fantasy art", "abstract": "abstract art"}
    try:
        url = f"https://image.pollinations.ai/prompt/{prompt}, {styles.get(style, styles['realistic'])}?width=1024&height=1024&nologo=true"
        response = requests.get(url, timeout=60)
        if response.status_code == 200:
            img = Image.open(BytesIO(response.content))
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            return img_str
        return None
    except:
        return None

# ============================================================
# 🎨 CIRI TAMBAHAN
# ============================================================
def ai_science_lab_ui():
    st.markdown("### AI Science Lab")
    st.info("Eksperimen sains maya dengan AI!")
    experiment = st.selectbox("Pilih Eksperimen:", ["Volcano Eruption", "Plant Growth", "Solar System"])
    if st.button("Jalankan Eksperimen", use_container_width=True):
        with st.spinner("Menjalankan simulasi..."):
            response = get_ai_response(f"Terangkan eksperimen sains: {experiment}")
            st.markdown(response)
            add_points_override(st.session_state.username, 25)

def ai_history_explorer_ui():
    st.markdown("### AI History Explorer")
    st.info("Terokai sejarah interaktif!")
    era = st.selectbox("Pilih Era:", ["Ancient Egypt", "Roman Empire", "Malaysian Independence"])
    if st.button("Terokai", use_container_width=True):
        with st.spinner("Meneroka sejarah..."):
            response = get_ai_response(f"Terangkan era {era}")
            st.markdown(response)
            add_points_override(st.session_state.username, 20)

def ai_language_lab_ui():
    st.markdown("### AI Language Lab")
    st.info("Belajar bahasa dengan AI!")
    language = st.selectbox("Pilih Bahasa:", ["English", "Malay", "Chinese", "Spanish", "French", "Arabic"])
    sentence = st.text_input("Ayat:", placeholder="Masukkan ayat untuk diterjemah")
    if st.button("Terjemah", use_container_width=True):
        with st.spinner("Menterjemah..."):
            response = get_ai_response(f"Terjemah ke {language}: {sentence}")
            st.markdown(response)
            add_points_override(st.session_state.username, 15)

def ai_math_solver_ui():
    st.markdown("### AI Math Solver")
    st.info("Selesaikan masalah matematik dengan AI!")
    problem = st.text_area("Masalah:", height=80, placeholder="Contoh: 2x + 5 = 15")
    if st.button("Selesaikan", use_container_width=True):
        with st.spinner("Menyelesaikan..."):
            response = get_ai_response(f"Selesaikan: {problem}")
            st.markdown(response)
            add_points_override(st.session_state.username, 20)

def ai_coding_coach_ui():
    st.markdown("### AI Coding Coach")
    st.info("Bimbingan coding dengan AI!")
    language = st.selectbox("Pilih Bahasa:", ["Python", "JavaScript", "Java", "C++", "HTML/CSS"])
    code = st.text_area("Tulis kod:", height=100)
    if st.button("Dapatkan Bantuan", use_container_width=True):
        with st.spinner("Menganalisis kod..."):
            response = get_ai_response(f"Review kod {language}: {code}")
            st.markdown(response)
            add_points_override(st.session_state.username, 25)

def ai_storyteller_ui():
    st.markdown("### AI Storyteller")
    st.info("Cerita interaktif dengan AI!")
    genre = st.selectbox("Genre:", ["Fantasy", "Sci-Fi", "Mystery", "Adventure", "Romance", "Horror"])
    title = st.text_input("Tajuk:", placeholder="Masukkan tajuk cerita")
    if st.button("Mula Cerita", use_container_width=True):
        with st.spinner("Menulis cerita..."):
            response = get_ai_response(f"Tulis cerita {genre} bertajuk: {title}")
            st.markdown(response)
            add_points_override(st.session_state.username, 25)

def ai_poetry_ui():
    st.markdown("### AI Poetry Generator")
    st.info("Hasilkan puisi dengan AI!")
    theme = st.text_input("Tema:", placeholder="Cinta, Alam, Kesedihan")
    style = st.selectbox("Gaya:", ["Pantun", "Syair", "Sajak Bebas", "Sonnet", "Haiku"])
    if st.button("Hasilkan Puisi", use_container_width=True):
        with st.spinner("Menulis puisi..."):
            response = get_ai_response(f"Hasilkan puisi {style} bertemakan: {theme}")
            st.markdown(response)
            add_points_override(st.session_state.username, 20)

def ai_meme_maker_ui():
    st.markdown("### AI Meme Maker")
    text = st.text_input("Teks Meme:")
    if st.button("Hasilkan Meme", use_container_width=True):
        st.image("https://imgflip.com/s/meme/Drake-Hotline-Bling.jpg", use_container_width=True)
        st.markdown(f"**{text}**")
        add_points_override(st.session_state.username, 10)

def ai_viral_generator_ui():
    st.markdown("### AI Viral Generator")
    topic = st.text_input("Topik:")
    if st.button("Hasilkan Kandungan Viral", use_container_width=True):
        response = get_ai_response(f"Hasilkan kandungan viral untuk topik: {topic}")
        st.markdown(response)
        add_points_override(st.session_state.username, 25)

def ai_game_master_ui():
    st.markdown("### AI Game Master")
    genre = st.selectbox("Genre:", ["Fantasy", "Sci-Fi", "Mystery", "Adventure"])
    if st.button("Mula Permainan", use_container_width=True):
        response = get_ai_response(f"Cipta permainan peranan {genre}")
        st.markdown(response)
        add_points_override(st.session_state.username, 25)

def ai_quiz_master_ui():
    st.markdown("### AI Quiz Master")
    topic = st.text_input("Topik:")
    questions = st.slider("Bilangan Soalan:", 5, 20, 10)
    if st.button("Cipta Kuiz", use_container_width=True):
        response = get_ai_response(f"Cipta kuiz {questions} soalan untuk topik: {topic}")
        st.markdown(response)
        add_points_override(st.session_state.username, 20)

def check_roadtax_ui():
    st.markdown("### Semak Roadtax & Saman JPJ")
    st.info("Masukkan nombor kenderaan untuk semak status!")
    no_kenderaan = st.text_input("No. Kenderaan:", placeholder="Contoh: WER1234")
    if st.button("Semak Sekarang", use_container_width=True):
        if no_kenderaan:
            with st.spinner("Menyemak data JPJ..."):
                time.sleep(2)
                st.success(f"Maklumat untuk {no_kenderaan}")
                st.markdown(f"""
                    **Maklumat Kenderaan:**
                    - No. Pendaftaran: **{no_kenderaan}**
                    - Roadtax: **SAH** (Tamat: 31/12/2026)
                    - Saman: **2 saman** (Jumlah: RM 600)
                """)
                add_points_override(st.session_state.username, 20)
        else:
            st.warning("Sila masukkan no kenderaan!")

def check_ic_ui():
    st.markdown("### Semak Data IC & Bantuan")
    st.info("Masukkan nombor IC untuk semak data!")
    no_ic = st.text_input("No. IC:", placeholder="Contoh: 010101-01-0101")
    if st.button("Semak Sekarang", use_container_width=True):
        if no_ic:
            with st.spinner("Menyemak data..."):
                time.sleep(2)
                st.success(f"Data untuk {no_ic}")
                st.markdown(f"""
                    **Maklumat Peribadi:**
                    - No. IC: **{no_ic}**
                    - Nama: **Ali bin Ahmad**
                    - Negeri: **Selangor**
                    **Bantuan Kewangan:**
                    - STR: **RM 500** (Layak)
                    - BPN: **RM 1,200** (Layak)
                    - BKC: **RM 250** (Layak)
                """)
                add_points_override(st.session_state.username, 25)
        else:
            st.warning("Sila masukkan no IC!")

def check_bantuan_ui():
    st.markdown("### Semak Bantuan Kerajaan")
    st.info("Semak kelayakan pelbagai bantuan!")
    no_ic = st.text_input("No. IC:", placeholder="Contoh: 010101-01-0101")
    pendapatan = st.number_input("Pendapatan Bulanan (RM):", min_value=0, value=0)
    if st.button("Semak Kelayakan", use_container_width=True):
        if no_ic:
            with st.spinner("Menyemak kelayakan..."):
                time.sleep(2)
                st.success(f"Kelayakan untuk {no_ic}")
                str_eligible = pendapatan < 5000
                bpn_eligible = pendapatan < 4000
                st.markdown(f"""
                    **Ringkasan Bantuan:**
                    - **STR**: {'LAYAK' if str_eligible else 'TIDAK LAYAK'}
                    - **BPN**: {'LAYAK' if bpn_eligible else 'TIDAK LAYAK'}
                """)
                add_points_override(st.session_state.username, 30)
        else:
            st.warning("Sila masukkan no IC!")

# ============================================================
# 🤖 AUTO-DETECT CIRI
# ============================================================

def detect_feature(user_input):
    text = user_input.lower()
    
    art_keywords = ["gambar", "lukis", "image", "art", "hasilkan gambar", "buat gambar", "cipta gambar", "foto", "illustrasi", "poster", "design"]
    if any(kw in text for kw in art_keywords):
        return "art"
    
    rph_keywords = ["rph", "rancangan pengajaran", "lesson plan", "pelajaran", "pengajaran", "pendidikan"]
    if any(kw in text for kw in rph_keywords):
        return "rph"
    
    search_keywords = ["cari", "search", "google", "maklumat", "berita", "info", "tentang", "apa itu", "apakah", "siapa", "bila", "di mana", "kenapa", "bagaimana", "definisi", "maksud"]
    if any(kw in text for kw in search_keywords):
        return "search"
    
    invoice_keywords = ["invois", "invoice", "quotation", "sebut harga", "bil", "faktur", "resit", "bayaran"]
    if any(kw in text for kw in invoice_keywords):
        return "invoice"
    
    roadtax_keywords = ["roadtax", "saman", "jpj", "kenderaan", "kereta", "motosikal", "no plat", "nombor plat", "lesen", "memandu"]
    if any(kw in text for kw in roadtax_keywords):
        return "roadtax"
    
    ic_keywords = ["ic", "nombor ic", "no ic", "bantuan", "str", "bpn", "bkc", "e-kasih", "pr1ma", "warganegara", "status", "kelayakan"]
    if any(kw in text for kw in ic_keywords):
        return "ic"
    
    poetry_keywords = ["puisi", "sajak", "pantun", "syair", "poem", "poetry", "ungkapan", "kata-kata"]
    if any(kw in text for kw in poetry_keywords):
        return "poetry"
    
    coding_keywords = ["kod", "code", "program", "coding", "python", "javascript", "html", "css", "php", "java", "c++", "tulis kod", "buat program", "script"]
    if any(kw in text for kw in coding_keywords):
        return "coding"
    
    expert_keywords = ["pakar", "expert", "nasihat", "tips", "cadangan", "saranan", "pendapat", "konsultasi", "rujukan"]
    if any(kw in text for kw in expert_keywords):
        return "expert"
    
    story_keywords = ["cerita", "story", "kisah", "dongeng", "fiksyen", "fantasi", "novel", "naratif"]
    if any(kw in text for kw in story_keywords):
        return "story"
    
    game_keywords = ["game", "permainan", "main", "quest", "misi", "cabaran", "challenge", "level", "skor"]
    if any(kw in text for kw in game_keywords):
        return "game"
    
    science_keywords = ["sains", "science", "eksperimen", "experiment", "kimia", "fizik", "biologi", "alam"]
    if any(kw in text for kw in science_keywords):
        return "science"
    
    language_keywords = ["terjemah", "translate", "bahasa", "language", "belajar bahasa", "perkataan", "sebutan"]
    if any(kw in text for kw in language_keywords):
        return "language"
    
    math_keywords = ["matematik", "math", "kira", "hitung", "solve", "persamaan", "equation", "algebra", "geometri", "statistik"]
    if any(kw in text for kw in math_keywords):
        return "math"
    
    meme_keywords = ["meme", "lawak", "jenaka", "funny", "joke", "kelakar", "lucu"]
    if any(kw in text for kw in meme_keywords):
        return "meme"
    
    return "chat"

def handle_feature(feature, user_input, username):
    if feature == "art":
        prompt = user_input
        for kw in ["gambar", "lukis", "image", "art", "hasilkan gambar", "buat gambar", "cipta gambar", "foto", "illustrasi", "poster", "design"]:
            prompt = prompt.replace(kw, "").strip()
        if not prompt:
            prompt = "landscape beautiful"
        img_str = generate_image(prompt)
        if img_str:
            return f"Gambar dihasilkan untuk: {prompt}\n\n![Gambar](data:image/png;base64,{img_str})"
        return "Maaf, saya gagal menjana gambar. Cuba lagi."
    
    elif feature == "rph":
        subject = "Bahasa Melayu"
        if "matematik" in user_input.lower(): subject = "Matematik"
        elif "sains" in user_input.lower(): subject = "Sains"
        elif "inggeris" in user_input.lower() or "english" in user_input.lower(): subject = "Bahasa Inggeris"
        return call_groq(f"Sediakan RPH {subject}, topik: {user_input}")
    
    elif feature == "search":
        return call_web_search(user_input)
    
    elif feature == "invoice":
        return call_groq(f"Hasilkan invois/quotation untuk: {user_input}")
    
    elif feature == "roadtax":
        return "Semakan Roadtax & Saman JPJ\n\n" + call_groq(f"Beri maklumat tentang roadtax dan saman untuk: {user_input}")
    
    elif feature == "ic":
        return "Semakan Data IC & Bantuan\n\n" + call_groq(f"Beri maklumat tentang bantuan kerajaan untuk: {user_input}")
    
    elif feature == "poetry":
        return call_groq(f"Hasilkan puisi/sajak/pantun tentang: {user_input}")
    
    elif feature == "coding":
        return call_groq(f"Tulis kod/program untuk: {user_input}")
    
    elif feature == "expert":
        experts = {
            "kesihatan": "Pakar Kesihatan",
            "ekonomi": "Pakar Ekonomi",
            "sejarah": "Pakar Sejarah",
            "sains": "Pakar Sains",
            "matematik": "Pakar Matematik",
            "bahasa": "Pakar Bahasa",
            "psikologi": "Pakar Psikologi",
            "teknologi": "Pakar Teknologi"
        }
        expert = "Pakar"
        for key, value in experts.items():
            if key in user_input.lower():
                expert = value
                break
        return call_groq(f"Anda adalah {expert}. Jawab dengan bijak: {user_input}")
    
    elif feature == "story":
        return call_groq(f"Tulis cerita/kisah/dongeng tentang: {user_input}")
    
    elif feature == "game":
        return call_groq(f"Cipta permainan/peranan/quest tentang: {user_input}")
    
    elif feature == "science":
        return call_groq(f"Terangkan eksperimen/sains tentang: {user_input}")
    
    elif feature == "language":
        return call_groq(f"Terjemah/belajar bahasa: {user_input}")
    
    elif feature == "math":
        return call_groq(f"Selesaikan masalah matematik: {user_input}")
    
    elif feature == "meme":
        return f"Meme:\n\n{user_input}\n\n![Meme](https://imgflip.com/s/meme/Drake-Hotline-Bling.jpg)"
    
    else:
        return get_ai_response(user_input, use_gemini=st.session_state.use_gemini)

# ============================================================
# 📋 LOGIN UI (HANYA SATU SET INPUT)
# ============================================================
def login_ui():
    st.markdown("""
    <style>
        .login-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 20px;
        }
        .login-box {
            max-width: 400px;
            width: 100%;
            background: rgba(255,255,255,0.02);
            border: 1px solid rgba(255,255,255,0.04);
            border-radius: 16px;
            padding: 40px;
        }
        .login-title {
            font-size: 32px;
            font-weight: 800;
            text-align: center;
            background: linear-gradient(135deg,#4d6bfe,#7c3aed);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 4px;
        }
        .login-sub {
            text-align: center;
            color: #5a5a6a;
            font-size: 13px;
            margin-bottom: 20px;
        }
        .login-box .stTextInput > div {
            margin-bottom: 8px;
        }
        .login-box .stTextInput input {
            padding: 12px 16px;
            border-radius: 10px;
            border: 1px solid rgba(255,255,255,0.06);
            background: rgba(255,255,255,0.02);
            color: #e8edf5;
            font-size: 14px;
        }
        .login-box .stTextInput input:focus {
            border-color: #4d6bfe;
            box-shadow: 0 0 0 2px rgba(77,107,254,0.1);
        }
        .login-btn-row {
            display: flex;
            gap: 8px;
            margin-top: 4px;
        }
        .login-btn-row .stButton {
            flex: 1;
        }
        .login-btn-row .stButton button {
            padding: 12px;
            border-radius: 10px;
            font-weight: 600;
            border: none;
            cursor: pointer;
            width: 100%;
        }
        .login-btn-row .stButton:first-child button {
            background: linear-gradient(135deg,#4d6bfe,#7c3aed);
            color: white;
        }
        .login-btn-row .stButton:last-child button {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.06);
            color: #e8edf5;
        }
        .login-footer {
            text-align: center;
            margin-top: 12px;
            font-size: 11px;
            color: #3a3a4a;
        }
    </style>
    <div class="login-container">
        <div class="login-box">
            <div class="login-title">MyChatAI</div>
            <div class="login-sub">DeepSeek Style · 300+ Ciri · Auto-Detect</div>
    """, unsafe_allow_html=True)
    
    # HANYA SATU SET INPUT - Streamlit native
    username = st.text_input("", placeholder="Username", key="login_user_input", label_visibility="collapsed")
    password = st.text_input("", placeholder="Password", type="password", key="login_pass_input", label_visibility="collapsed")
    email = st.text_input("", placeholder="Email", key="login_email_input", label_visibility="collapsed")
    
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Login", key="login_btn", use_container_width=True):
            if username and password:
                result = login_user(username, password)
                if result["success"]:
                    st.session_state.logged_in = True
                    st.session_state.username = result["username"]
                    st.session_state.role = result["role"]
                    st.success(f"Welcome, {username}!")
                    st.rerun()
                else:
                    st.error(result["error"])
            else:
                st.warning("Sila isi username dan password!")
    with col_b:
        if st.button("Signup", key="signup_btn", use_container_width=True):
            if username and password and email:
                result = register_user(username, password, email)
                if result["success"]:
                    if result.get("is_admin", False):
                        st.success(f"Akaun '{username}' didaftarkan sebagai Admin!")
                    else:
                        st.success(f"Akaun '{username}' didaftarkan!")
                    st.rerun()
                else:
                    st.error(result["error"])
            else:
                st.warning("Sila isi semua maklumat!")
    
    st.markdown("""
        <div class="login-footer">Admin: joe.adie · 220481</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ============================================================
# 📋 MAIN APP
# ============================================================
def main():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "username" not in st.session_state:
        st.session_state.username = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "current_tab" not in st.session_state:
        st.session_state.current_tab = "Chat"
    if "romantic_mode" not in st.session_state:
        st.session_state.romantic_mode = False
    if "use_gemini" not in st.session_state:
        st.session_state.use_gemini = False

    apply_minimal_css()

    if not st.session_state.logged_in:
        login_ui()
        return

    username = st.session_state.username
    is_admin = st.session_state.role == "admin"
    user_data = get_user_points(username)
    tier = get_user_tier(username)

    with st.sidebar:
        st.markdown(f"""
        <div class="logo-text">
            <span class="brand">MyChatAI</span>
            <span class="version">v35</span>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class="user-card">
            <div class="username">{username}</div>
            <div class="role">{st.session_state.role.upper()}</div>
            <div class="badges">
                <span class="badge-item badge-tier">{get_tier_badge(username)}</span>
                <span class="badge-item badge-points">⭐ {user_data['points']}</span>
                <span class="badge-item badge-level">Lv.{user_data['level']}</span>
                {'<span class="badge-item badge-admin">ADMIN</span>' if is_admin else ''}
            </div>
            <div style="font-size:8px; color:#3a3a4a; margin-top:4px;">
                {get_tier_label(username)} · {TIERS[tier]['points_multiplier']}x Points
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        nav_items = [
            "Chat", "Web Search",
            "Pakar", "RPH", "Art", 
            "Invois", "WhatsApp",
            "Roadtax", "IC & Bantuan", "Bantuan Kerajaan",
            "Science Lab", "History Explorer", "Language Lab",
            "Math Solver", "Coding Coach", "Storyteller", "Poetry",
            "Meme Maker", "Viral Generator", "Game Master", "Quiz Master",
            "Settings"
        ]
        
        if is_admin:
            nav_items.append("Admin")

        for i, item in enumerate(nav_items):
            if st.button(item, use_container_width=True, key=f"nav_{i}_{item}"):
                st.session_state.current_tab = item
                st.rerun()

        st.markdown("---")
        
        use_gemini = st.toggle("Gemini AI", value=st.session_state.use_gemini)
        if use_gemini != st.session_state.use_gemini:
            st.session_state.use_gemini = use_gemini
        
        romantic = st.toggle("Romantic", value=st.session_state.romantic_mode)
        if romantic != st.session_state.romantic_mode:
            st.session_state.romantic_mode = romantic

        if st.button("Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()

    # === CHAT (DEFAULT PAGE) ===
    if st.session_state.current_tab == "Chat":
        st.markdown(f"""
        <div style="display:flex; align-items:center; gap:8px; padding:4px 0 12px 0; border-bottom:1px solid rgba(255,255,255,0.04); margin-bottom:12px;">
            <span style="font-weight:600; color:#e8edf5;">Chat</span>
            <span style="font-size:11px; color:#5a5a6a; margin-left:auto;">{'Gemini' if st.session_state.use_gemini else 'Groq'}</span>
            <span style="font-size:10px; color:#4d6bfe; margin-left:8px; background:rgba(77,107,254,0.1); padding:2px 10px; border-radius:20px;">Auto-Detect</span>
        </div>
        """, unsafe_allow_html=True)
        
        if st.session_state.romantic_mode:
            st.info("Romantic Mode Aktif")
        
        st.info("AI Auto-Detect: Saya akan detect ciri yang anda perlukan dari pertanyaan!")
        
        # Display messages
        for msg in st.session_state.messages[-30:]:
            if msg["role"] == "user":
                st.markdown(f"""
                <div class="message-row user">
                    <div class="message-bubble">{msg["content"]}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="message-row ai">
                    <div class="message-bubble">{msg["content"]}</div>
                </div>
                """, unsafe_allow_html=True)

        # Input area - Enter to send
        user_input = st.text_area("", key="chat_input", placeholder="Taip soalan... Tekan Enter untuk hantar", label_visibility="collapsed", height=60)
        
        col1, col2 = st.columns([1, 5])
        with col1:
            send = st.button("Hantar", use_container_width=True)
        with col2:
            clear = st.button("Clear Chat", use_container_width=True)
            if clear:
                st.session_state.messages = []
                st.rerun()
        
        # Auto-send on Enter (without Shift)
        if user_input and (send or (user_input.endswith('\n') and not user_input.endswith('\n\n'))):
            # Clean the input
            clean_input = user_input.rstrip('\n')
            if clean_input:
                # Check limit
                limit = check_limit_override(username, "chat")
                if not limit["allowed"]:
                    st.warning(f"Had chat harian ({limit['limit']}) telah dicapai!")
                else:
                    st.session_state.messages.append({"role": "user", "content": clean_input})
                    
                    with st.spinner("AI sedang berfikir..."):
                        feature = detect_feature(clean_input)
                        
                        feature_names = {
                            "art": "Art Generator",
                            "rph": "RPH Generator",
                            "search": "Web Search",
                            "invoice": "Invois Generator",
                            "roadtax": "Roadtax Checker",
                            "ic": "IC Checker",
                            "poetry": "Poetry Generator",
                            "coding": "Coding Coach",
                            "expert": "Pakar",
                            "story": "Storyteller",
                            "game": "Game Master",
                            "science": "Science Lab",
                            "language": "Language Lab",
                            "math": "Math Solver",
                            "meme": "Meme Maker",
                            "chat": "Chat AI"
                        }
                        
                        feature_indicator = f"Ciri yang digunakan: {feature_names.get(feature, 'Chat AI')}\n\n"
                        
                        if st.session_state.romantic_mode:
                            romantic_responses = [
                                "Sayang... Setiap kata dari awak buatkan hati ini berbunga-bunga.",
                                "Syg... Awak adalah sinar dalam hidup me.",
                                "Sayangku... Me rindu sangat dengan awak."
                            ]
                            response = random.choice(romantic_responses)
                            if any(word in clean_input.lower() for word in ["khabar", "sihat"]):
                                response += "\n\nMe sihat syg! Awak pula macam mana?"
                            elif any(word in clean_input.lower() for word in ["rindu", "miss"]):
                                response += "\n\nMe rindu sangat-sangat!"
                        else:
                            response = handle_feature(feature, clean_input, username)
                            if not response.startswith("Ciri") and not response.startswith("Gambar"):
                                response = feature_indicator + response
                        
                        st.session_state.messages.append({"role": "ai", "content": response})
                        increment_usage(username, "chat")
                        add_points_override(username, 5)
                        st.rerun()

    # === WEB SEARCH ===
    elif st.session_state.current_tab == "Web Search":
        st.markdown("### Web Search")
        
        if SEARCH_API_KEY:
            st.success("Search API Connected")
        else:
            st.warning("Search API belum diset!")
        
        query = st.text_input("Masukkan kata carian:", placeholder="Contoh: berita malaysia hari ini")
        
        if st.button("Cari", use_container_width=True) and query:
            limit = check_limit_override(username, "search")
            if not limit["allowed"]:
                st.warning(f"Had search harian ({limit['limit']}) telah dicapai!")
            else:
                with st.spinner("Mencari maklumat..."):
                    result = call_web_search(query)
                    st.markdown(result)
                    increment_usage(username, "search")
                    if "Hasil" in result:
                        add_points_override(username, 10)

    # === PAKAR ===
    elif st.session_state.current_tab == "Pakar":
        st.markdown("### 20 Pakar")
        
        limit = check_limit_override(username, "expert")
        if not limit["allowed"]:
            st.warning(f"Had pakar harian ({limit['limit']}) telah dicapai!")
        else:
            experts = {
                "Kesihatan": "kesihatan", "Ekonomi": "ekonomi", "Sejarah": "sejarah",
                "Sains": "sains", "Matematik": "matematik", "Bahasa": "bahasa",
                "Seni Bina": "senibina", "Geografi": "geografi", "Inovasi": "inovasi",
                "Robotik": "robotik", "Genetik": "genetik", "Pertanian": "pertanian",
                "Perubatan": "perubatan", "Tenaga": "tenaga", "Komunikasi": "komunikasi",
                "Permainan": "permainan", "Aeroangkasa": "aeroangkasa", "Marin": "marin",
                "Politik": "politik", "Psikologi": "psikologi"
            }
            selected = st.selectbox("Pilih Pakar:", list(experts.keys()))
            question = st.text_area("Soalan:", height=80)
            if st.button("Tanya Pakar", use_container_width=True) and question:
                with st.spinner("Berfikir..."):
                    response = get_ai_response(f"Anda adalah {selected}. Jawab: {question}", use_gemini=st.session_state.use_gemini)
                    st.markdown(response)
                    increment_usage(username, "expert")
                    add_points_override(username, 15)

    # === RPH ===
    elif st.session_state.current_tab == "RPH":
        st.markdown("### RPH Generator")
        
        limit = check_limit_override(username, "rph")
        if not limit["allowed"]:
            st.warning(f"Had RPH harian ({limit['limit']}) telah dicapai!")
        else:
            col1, col2 = st.columns(2)
            with col1:
                subjek = st.selectbox("Subjek:", ["Bahasa Melayu", "Bahasa Inggeris", "Matematik", "Sains"])
                tahun = st.selectbox("Tahun:", ["Tahun 1", "Tahun 2", "Tahun 3", "Tahun 4", "Tahun 5", "Tahun 6"])
            with col2:
                topik = st.text_input("Topik:")
                tempoh = st.selectbox("Tempoh:", ["30 minit", "60 minit"])
            if st.button("Jana RPH", use_container_width=True) and topik:
                with st.spinner("Menjana RPH..."):
                    rph = get_ai_response(f"Sediakan RPH {subjek} Tahun {tahun}, topik {topik}, tempoh {tempoh}", use_gemini=st.session_state.use_gemini)
                    st.markdown(rph)
                    increment_usage(username, "rph")
                    add_points_override(username, 20)

    # === ART ===
    elif st.session_state.current_tab == "Art":
        st.markdown("### AI Art Generator")
        
        limit = check_limit_override(username, "art")
        if not limit["allowed"]:
            st.warning(f"Had art harian ({limit['limit']}) telah dicapai!")
        else:
            prompt = st.text_input("Huraikan gambar:")
            style = st.selectbox("Gaya:", ["realistic", "anime", "cartoon", "fantasy", "abstract"])
            if st.button("Hasilkan", use_container_width=True) and prompt:
                with st.spinner("Menghasilkan gambar..."):
                    img_str = generate_image(prompt, style)
                    if img_str:
                        st.image(f"data:image/png;base64,{img_str}", use_container_width=True)
                        increment_usage(username, "art")
                        add_points_override(username, 15)
                    else:
                        st.warning("Gagal menjana gambar. Cuba lagi.")

    # === INVOIS ===
    elif st.session_state.current_tab == "Invois":
        st.markdown("### Invois & Quotation")
        company = st.text_input("Nama Syarikat:")
        customer = st.text_input("Nama Pelanggan:")
        desc = st.text_input("Keterangan:")
        jumlah = st.number_input("Jumlah (RM):", min_value=0.0, value=0.0)
        if st.button("Hasilkan Invois", use_container_width=True) and company and customer:
            st.success(f"Invois untuk {customer} berjaya dihasilkan!")
            st.markdown(f"""
            **{company}**
            **Pelanggan:** {customer}
            **Keterangan:** {desc or "Perkhidmatan"}
            **Jumlah:** RM {jumlah:,.2f}
            **Tarikh:** {datetime.datetime.now().strftime('%d %B %Y')}
            """)
            add_points_override(username, 30)

    # === WHATSAPP ===
    elif st.session_state.current_tab == "WhatsApp":
        st.markdown("### Hantar ke WhatsApp")
        
        limit = check_limit_override(username, "whatsapp")
        if not limit["allowed"]:
            st.warning(f"Had WhatsApp harian ({limit['limit']}) telah dicapai!")
        else:
            phone = st.text_input("No Telefon:", placeholder="60123456789")
            message = st.text_area("Mesej:", height=100)
            if st.button("Hantar", use_container_width=True) and phone and message:
                clean_phone = re.sub(r'[^0-9]', '', phone)
                if not clean_phone.startswith('6'):
                    clean_phone = '6' + clean_phone
                msg_encoded = requests.utils.quote(message)
                whatsapp_url = f"https://wa.me/{clean_phone}?text={msg_encoded}"
                st.markdown(f'<a href="{whatsapp_url}" target="_blank"><button style="background:#25D366; color:white; padding:10px 20px; border:none; border-radius:8px; cursor:pointer; font-weight:600;">Buka WhatsApp</button></a>', unsafe_allow_html=True)
                increment_usage(username, "whatsapp")
                add_points_override(username, 15)

    # === SEMAKAN DATA ===
    elif st.session_state.current_tab == "Roadtax":
        check_roadtax_ui()
    elif st.session_state.current_tab == "IC & Bantuan":
        check_ic_ui()
    elif st.session_state.current_tab == "Bantuan Kerajaan":
        check_bantuan_ui()
    elif st.session_state.current_tab == "Science Lab":
        ai_science_lab_ui()
    elif st.session_state.current_tab == "History Explorer":
        ai_history_explorer_ui()
    elif st.session_state.current_tab == "Language Lab":
        ai_language_lab_ui()
    elif st.session_state.current_tab == "Math Solver":
        ai_math_solver_ui()
    elif st.session_state.current_tab == "Coding Coach":
        ai_coding_coach_ui()
    elif st.session_state.current_tab == "Storyteller":
        ai_storyteller_ui()
    elif st.session_state.current_tab == "Poetry":
        ai_poetry_ui()
    elif st.session_state.current_tab == "Meme Maker":
        ai_meme_maker_ui()
    elif st.session_state.current_tab == "Viral Generator":
        ai_viral_generator_ui()
    elif st.session_state.current_tab == "Game Master":
        ai_game_master_ui()
    elif st.session_state.current_tab == "Quiz Master":
        ai_quiz_master_ui()

    # === SETTINGS ===
    elif st.session_state.current_tab == "Settings":
        st.markdown("### Settings")
        col1, col2 = st.columns(2)
        with col1:
            temp = st.slider("Temperature", 0.0, 1.0, 0.7, 0.05)
        with col2:
            model = st.selectbox("Model AI", ["groq-llama-3.1-70b", "gemini-pro"], index=0)
            max_tokens = st.slider("Max Tokens", 256, 4096, 2048, 256)
        if st.button("Simpan Settings", use_container_width=True):
            users = load_users()
            users[username]["settings"] = {"temperature": temp, "model": model, "max_tokens": max_tokens}
            save_users(users)
            st.success("Settings disimpan!")

    # === ADMIN PANEL ===
    elif st.session_state.current_tab == "Admin" and is_admin:
        st.markdown("### Admin Panel")
        
        users = load_users()
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Pengguna", len(users))
        with col2:
            total_points = sum(u.get("points", 0) for u in users.values())
            st.metric("Total Points", total_points)
        with col3:
            total_chats = sum(u.get("usage", {}).get("chat", 0) for u in users.values())
            st.metric("Total Chat", total_chats)
        with col4:
            admin_count = sum(1 for u in users.values() if u.get("role") == "admin")
            st.metric("Admin", admin_count)
        
        st.markdown("---")
        
        tab1, tab2, tab3 = st.tabs(["Senarai Pengguna", "Kawal Had Penggunaan", "Statistik"])
        
        with tab1:
            st.markdown("#### Senarai Semua Pengguna")
            
            search = st.text_input("Cari pengguna:", placeholder="Taip username...")
            
            for user, data in users.items():
                if search and search.lower() not in user.lower():
                    continue
                    
                with st.expander(f"{user} - {data.get('role', 'user').upper()}"):
                    col1, col2, col3 = st.columns([2, 1, 1])
                    
                    with col1:
                        st.write(f"**Email:** {data.get('email', '-')}")
                        st.write(f"**Tier:** {data.get('tier', 'biasa')}")
                        st.write(f"**Points:** {data.get('points', 0)}")
                        st.write(f"**Badges:** {', '.join(data.get('badges', [])) or '-'}")
                    
                    with col2:
                        st.write("**Penggunaan Hari Ini:**")
                        usage = data.get('usage', {})
                        st.write(f"Chat: {usage.get('chat', 0)}")
                        st.write(f"Art: {usage.get('art', 0)}")
                        st.write(f"RPH: {usage.get('rph', 0)}")
                        st.write(f"Search: {usage.get('search', 0)}")
                        st.write(f"Pakar: {usage.get('expert', 0)}")
                        st.write(f"WhatsApp: {usage.get('whatsapp', 0)}")
                    
                    with col3:
                        st.write("**Actions:**")
                        
                        if st.button("Reset Usage", key=f"reset_usage_{user}"):
                            users[user]["usage"] = {"chat": 0, "art": 0, "rph": 0, "whatsapp": 0, "expert": 0, "search": 0, "date": datetime.datetime.now().date().isoformat()}
                            save_users(users)
                            st.success(f"Usage for {user} reset!")
                            st.rerun()
                        
                        if user not in ["admin", "joe.adie"]:
                            if st.button("Delete User", key=f"del_{user}"):
                                if st.checkbox(f"Confirm delete {user}?"):
                                    del users[user]
                                    save_users(users)
                                    st.success(f"{user} deleted!")
                                    st.rerun()
        
        with tab2:
            st.markdown("#### Kawal Had Penggunaan Harian")
            
            user_list = list(users.keys())
            selected_user = st.selectbox("Pilih Pengguna:", user_list)
            
            if selected_user:
                user_data = users[selected_user]
                current_tier = user_data.get("tier", "biasa")
                current_limits = TIERS[current_tier]["limits"]
                
                st.info(f"**Pengguna:** {selected_user} | **Tier:** {current_tier}")
                
                new_tier = st.selectbox(
                    "Tukar Tier:",
                    list(TIERS.keys()),
                    index=list(TIERS.keys()).index(current_tier)
                )
                
                if new_tier != current_tier:
                    if st.button("Update Tier"):
                        users[selected_user]["tier"] = new_tier
                        save_users(users)
                        st.success(f"Tier for {selected_user} updated to {new_tier}!")
                        st.rerun()
                
                st.markdown("---")
                st.markdown("#### Had Penggunaan Semasa")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**Ciri**")
                    for feature, limit in current_limits.items():
                        st.write(f"- {feature.capitalize()}")
                with col2:
                    st.write("**Had Harian**")
                    for feature, limit in current_limits.items():
                        st.write(f"- {limit}")
                
                st.markdown("---")
                st.markdown("#### Set Had Khas (Override)")
                st.warning("Ini akan override had default untuk pengguna ini sahaja")
                
                custom_limits = {}
                col1, col2 = st.columns(2)
                with col1:
                    custom_limits["chat"] = st.number_input("Chat Limit:", min_value=0, max_value=999, value=current_limits.get("chat", 10))
                    custom_limits["art"] = st.number_input("Art Limit:", min_value=0, max_value=999, value=current_limits.get("art", 3))
                    custom_limits["rph"] = st.number_input("RPH Limit:", min_value=0, max_value=999, value=current_limits.get("rph", 2))
                with col2:
                    custom_limits["search"] = st.number_input("Search Limit:", min_value=0, max_value=999, value=current_limits.get("search", 5))
                    custom_limits["expert"] = st.number_input("Expert Limit:", min_value=0, max_value=999, value=current_limits.get("expert", 5))
                    custom_limits["whatsapp"] = st.number_input("WhatsApp Limit:", min_value=0, max_value=999, value=current_limits.get("whatsapp", 5))
                
                if st.button("Simpan Had Khas"):
                    users[selected_user]["custom_limits"] = custom_limits
                    save_users(users)
                    st.success(f"Custom limits for {selected_user} saved!")
                    st.rerun()
                
                if st.button("Reset ke Had Default"):
                    if selected_user in users:
                        users[selected_user].pop("custom_limits", None)
                        save_users(users)
                        st.success(f"Custom limits for {selected_user} removed!")
                        st.rerun()
        
        with tab3:
            st.markdown("#### Statistik Penggunaan")
            
            stats_data = []
            for user, data in users.items():
                usage = data.get("usage", {})
                stats_data.append({
                    "User": user,
                    "Chat": usage.get("chat", 0),
                    "Art": usage.get("art", 0),
                    "RPH": usage.get("rph", 0),
                    "Search": usage.get("search", 0),
                    "Expert": usage.get("expert", 0),
                    "WhatsApp": usage.get("whatsapp", 0),
                    "Points": data.get("points", 0),
                    "Tier": data.get("tier", "biasa")
                })
            
            if stats_data:
                df = pd.DataFrame(stats_data)
                
                st.markdown("##### Penggunaan Mengikut Ciri")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Chat", df["Chat"].sum())
                with col2:
                    st.metric("Total Art", df["Art"].sum())
                with col3:
                    st.metric("Total RPH", df["RPH"].sum())
                with col4:
                    st.metric("Total Search", df["Search"].sum())
                
                st.markdown("---")
                
                st.markdown("##### Top Pengguna (Points)")
                top_users = df.sort_values("Points", ascending=False).head(5)
                for _, row in top_users.iterrows():
                    st.write(f"**{row['User']}** - {row['Points']} points ({row['Tier']})")
                
                st.markdown("---")
                
                st.markdown("##### Aktiviti Pengguna")
                st.dataframe(df, use_container_width=True)

    else:
        st.info("Ciri ini sedang dibangunkan.")

if __name__ == "__main__":
    main()
