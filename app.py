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

# === API KEYS ===
try:
    GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
    GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")
    SEARCH_API_KEY = st.secrets.get("SEARCH_API_KEY", "")
except:
    GEMINI_API_KEY = ""
    GROQ_API_KEY = ""
    SEARCH_API_KEY = ""

# === CONSTANTS ===
USER_DATA_FILE = "mychat_users.json"
CHAT_HISTORY_FILE = "mychat_chats.json"
POINTS_FILE = "mychat_points.json"
RPH_HISTORY_FILE = "rph_history.json"

# === ADMIN ===
ADMIN_EMAILS = ["joe.adie77711@gmail.com"]
ADMIN_USERNAMES = ["joe.adie"]

def is_admin_user(email, username=None):
    if email in ADMIN_EMAILS:
        return True
    if username and username in ADMIN_USERNAMES:
        return True
    return False

def get_user_role(email, username=None):
    return "admin" if is_admin_user(email, username) else "user"

# ============================================================
# 🎨 CSS
# ============================================================
def apply_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
        * { font-family: 'Inter', sans-serif; margin: 0; padding: 0; box-sizing: border-box; }
        .stApp { background: #0d0d0d; }
        
        .stSidebar {
            background: rgba(255,255,255,0.02) !important;
            border-right: 1px solid rgba(255,255,255,0.04) !important;
            padding: 20px 16px !important;
            overflow-y: auto;
        }
        
        .logo-text {
            font-size: 1.3rem;
            font-weight: 800;
            text-align: center;
            padding: 8px 4px 16px 4px;
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
            margin-left: 4px;
        }
        
        .user-card {
            background: rgba(255,255,255,0.03);
            border-radius: 12px;
            padding: 14px;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.04);
            margin-bottom: 12px;
        }
        .user-card .username {
            font-weight: 600;
            font-size: 0.95rem;
            color: #e8edf5;
            margin: 2px 0;
        }
        .user-card .role {
            font-size: 0.55rem;
            color: #5a5a6a;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .user-card .badges {
            display: flex;
            gap: 4px;
            justify-content: center;
            flex-wrap: wrap;
            margin-top: 4px;
        }
        .badge-item {
            padding: 2px 10px;
            border-radius: 20px;
            font-size: 0.5rem;
            font-weight: 600;
        }
        .badge-tier { background: #4d6bfe; color: white; }
        .badge-points { background: linear-gradient(135deg,#4d6bfe,#7c3aed); color: white; }
        .badge-level { background: rgba(255,255,255,0.06); color: #8a8a9a; }
        .badge-admin { background: #7c3aed; color: white; }
        .badge-romantic { background: #ff6fb0; color: white; }
        
        .btn-new-chat {
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
        .btn-new-chat:hover {
            transform: scale(1.01);
            box-shadow: 0 4px 20px rgba(77,107,254,0.2);
        }
        
        .history-label {
            font-size: 0.6rem;
            color: #5a5a6a;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            padding: 8px 4px 4px 4px;
            font-weight: 700;
        }
        
        .history-item {
            padding: 6px 10px;
            border-radius: 8px;
            cursor: pointer;
            transition: 0.2s;
            font-size: 0.75rem;
            color: #8a8a9a;
            margin-bottom: 2px;
            border: 1px solid transparent;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .history-item:hover {
            background: rgba(255,255,255,0.04);
            color: #e8edf5;
        }
        .history-item.active {
            background: rgba(255,255,255,0.04);
            color: #e8edf5;
            border-color: rgba(255,255,255,0.04);
        }
        .history-item .del {
            color: #5a5a6a;
            cursor: pointer;
            font-size: 0.6rem;
            padding: 2px 6px;
            border-radius: 30px;
        }
        .history-item .del:hover {
            background: #ff6fd8;
            color: white;
        }
        
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
        }
        .stButton > button:hover {
            background: rgba(255,255,255,0.04);
            border-color: rgba(255,255,255,0.1);
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
        .message-row.ai.romantic .message-bubble {
            border-color: #ff6fb0;
            background: linear-gradient(135deg, #1a0a1a, #2a1a2a);
        }
        .message-row.ai.romantic .message-bubble p {
            color: #ffb0d0;
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
        
        .input-container {
            position: relative;
            margin-top: 8px;
        }
        .input-container textarea {
            width: 100%;
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 12px;
            color: #e8edf5;
            font-size: 0.9rem;
            padding: 12px 16px;
            padding-right: 140px;
            resize: none;
            min-height: 52px;
            max-height: 150px;
            font-family: 'Inter', sans-serif;
            outline: none;
            transition: border-color 0.2s ease;
        }
        .input-container textarea:focus {
            border-color: rgba(77,107,254,0.3);
        }
        .input-container textarea::placeholder {
            color: #5a5a6a;
        }
        
        .input-actions {
            position: absolute;
            right: 8px;
            bottom: 8px;
            display: flex;
            gap: 4px;
            align-items: center;
        }
        .input-actions .icon-btn {
            background: transparent;
            border: none;
            color: #5a5a6a;
            cursor: pointer;
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 0.9rem;
            transition: all 0.2s ease;
        }
        .input-actions .icon-btn:hover {
            color: #e8edf5;
            background: rgba(255,255,255,0.04);
        }
        .input-actions .send-btn {
            background: linear-gradient(135deg, #4d6bfe, #7c3aed);
            border: none;
            color: white;
            padding: 6px 14px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 0.8rem;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .input-actions .send-btn:hover {
            transform: scale(1.02);
            box-shadow: 0 2px 12px rgba(77,107,254,0.2);
        }
        
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }
        ::-webkit-scrollbar-track { background: transparent; }
        
        @keyframes fadeUp {
            0% { opacity: 0; transform: translateY(8px); }
            100% { opacity: 1; transform: translateY(0); }
        }
        
        .login-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 20px;
        }
        .login-box {
            max-width: 380px;
            width: 100%;
            background: rgba(255,255,255,0.02);
            border: 1px solid rgba(255,255,255,0.04);
            border-radius: 16px;
            padding: 40px 32px;
        }
        .login-title {
            font-size: 28px;
            font-weight: 800;
            text-align: center;
            background: linear-gradient(135deg, #4d6bfe, #7c3aed);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 24px;
        }
        .login-box .stTextInput > div {
            margin-bottom: 10px;
        }
        .login-box .stTextInput input {
            width: 100%;
            padding: 12px 16px;
            border-radius: 10px;
            border: 1px solid rgba(255,255,255,0.06);
            background: rgba(255,255,255,0.02);
            color: #e8edf5;
            font-size: 14px;
            outline: none;
        }
        .login-box .stTextInput input:focus {
            border-color: #4d6bfe;
            box-shadow: 0 0 0 2px rgba(77,107,254,0.1);
        }
        .login-btn-row {
            display: flex;
            gap: 10px;
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
            font-size: 14px;
        }
        .login-btn-row .stButton:first-child button {
            background: linear-gradient(135deg, #4d6bfe, #7c3aed);
            color: white;
        }
        .login-btn-row .stButton:last-child button {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.06);
            color: #e8edf5;
        }
        .login-btn-row .stButton:last-child button:hover {
            background: rgba(255,255,255,0.08);
        }
        
        .toggle-container {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 4px 0;
        }
        .toggle-container label {
            font-size: 0.8rem;
            color: #8a8a9a;
        }
        
        @media (max-width: 768px) {
            .stSidebar { width: 280px !important; }
            .message-row { max-width: 95%; }
            .message-bubble { font-size: 0.85rem; padding: 8px 14px; }
            .input-container textarea { padding-right: 120px; font-size: 0.85rem; }
            .input-actions .send-btn { padding: 4px 10px; font-size: 0.7rem; }
            .input-actions .icon-btn { padding: 2px 6px; font-size: 0.8rem; }
            .login-box { padding: 24px 16px; }
        }
    </style>
    """, unsafe_allow_html=True)

# ============================================================
# 📋 DATA FUNCTIONS
# ============================================================

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# === TIER SYSTEM ===
TIERS = {
    "biasa": {
        "label": "Free",
        "color": "#8a8a9a",
        "badge": "Free",
        "limits": {"chat": 10, "art": 3, "rph": 2, "whatsapp": 5, "expert": 5, "search": 5},
        "features": {"chat": True, "art": True, "expert": True, "rph": True, "invoice": True, "whatsapp": True, "search": True},
        "points_multiplier": 1.0,
        "price": "Free",
        "duration": "-"
    },
    "plus": {
        "label": "Plus",
        "color": "#ffd700",
        "badge": "Plus",
        "limits": {"chat": 25, "art": 10, "rph": 5, "whatsapp": 15, "expert": 10, "search": 15},
        "features": {"chat": True, "art": True, "expert": True, "rph": True, "invoice": True, "whatsapp": True, "search": True},
        "points_multiplier": 1.5,
        "price": "RM 9.90",
        "duration": "1 month"
    },
    "super_plus": {
        "label": "Super Plus",
        "color": "#7b2ffc",
        "badge": "Super",
        "limits": {"chat": 50, "art": 20, "rph": 10, "whatsapp": 30, "expert": 20, "search": 30},
        "features": {"chat": True, "art": True, "expert": True, "rph": True, "invoice": True, "whatsapp": True, "search": True},
        "points_multiplier": 2.0,
        "price": "RM 24.90",
        "duration": "3 months"
    },
    "pro_super": {
        "label": "Pro Super",
        "color": "#ff6fd8",
        "badge": "Pro",
        "limits": {"chat": 999, "art": 999, "rph": 999, "whatsapp": 999, "expert": 999, "search": 999},
        "features": {"chat": True, "art": True, "expert": True, "rph": True, "invoice": True, "whatsapp": True, "search": True},
        "points_multiplier": 3.0,
        "price": "RM 49.90",
        "duration": "1 year"
    }
}

def load_users():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, "r") as f:
            return json.load(f)
    default = {
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
        return {"success": False, "error": "Username does not exist!"}
    if users[username]["password"] != hash_password(password):
        return {"success": False, "error": "Incorrect password!"}
    reset_daily_usage(username)
    return {"success": True, "username": username, "role": users[username].get("role", "user")}

def register_user(username, password, email):
    users = load_users()
    if username in users:
        return {"success": False, "error": "Username already exists!"}
    if len(password) < 6:
        return {"success": False, "error": "Password must be at least 6 characters!"}
    
    is_admin = is_admin_user(email, username)
    role = "admin" if is_admin else "user"
    tier = "pro_super" if is_admin else "biasa"
    points = 1000 if is_admin else 100
    badges = ["Founder", "Pioneer"] if is_admin else []
    
    if username.lower() in ["farhani", "farhani binti norman", "farhani norman"]:
        badges.append("💕 Romantic")
    
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
        return "Groq API Key not set! Please set in Streamlit Secrets."
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "openai/gpt-oss-20b",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 2048
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return f"Groq Error: {response.status_code}"
    except Exception as e:
        return f"Error: {str(e)}"

def get_ai_response(prompt):
    return call_groq(prompt)

def call_web_search(query):
    if not SEARCH_API_KEY or SEARCH_API_KEY == "":
        return "Search API not set! Please set in Streamlit Secrets."
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
                output = f"Search Results: '{query}'\n\n"
                for i, item in enumerate(results[:5]):
                    title = item.get('title', '')
                    snippet = item.get('description', '')
                    link = item.get('link', '')
                    output += f"{i+1}. {title}\n"
                    output += f"   {snippet[:200]}\n"
                    output += f"   {link}\n\n"
                return output
            return f"No results for '{query}'."
        return f"Search Error: {response.status_code}"
    except Exception as e:
        return f"Error: {str(e)}"

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
# 🧠 AUTO-DETECT FEATURES (16 Features)
# ============================================================

def detect_feature(user_input):
    text = user_input.lower()
    
    art_keywords = ["gambar", "lukis", "image", "art", "hasilkan gambar", "buat gambar", "cipta gambar", "foto", "illustrasi", "poster", "design", "draw", "picture", "photo"]
    if any(kw in text for kw in art_keywords):
        return "art"
    
    rph_keywords = ["rph", "rancangan pengajaran", "lesson plan", "pelajaran", "pengajaran", "pendidikan", "teaching", "plan"]
    if any(kw in text for kw in rph_keywords):
        return "rph"
    
    search_keywords = ["cari", "search", "google", "maklumat", "berita", "info", "tentang", "apa itu", "apakah", "siapa", "bila", "di mana", "kenapa", "bagaimana", "definisi", "maksud", "what is", "who", "when", "where", "why", "how"]
    if any(kw in text for kw in search_keywords):
        return "search"
    
    invoice_keywords = ["invois", "invoice", "quotation", "sebut harga", "bil", "faktur", "resit", "bayaran", "bill", "quote"]
    if any(kw in text for kw in invoice_keywords):
        return "invoice"
    
    roadtax_keywords = ["roadtax", "saman", "jpj", "kenderaan", "kereta", "motosikal", "no plat", "nombor plat", "lesen", "memandu", "vehicle", "license"]
    if any(kw in text for kw in roadtax_keywords):
        return "roadtax"
    
    ic_keywords = ["ic", "nombor ic", "no ic", "bantuan", "str", "bpn", "bkc", "e-kasih", "pr1ma", "warganegara", "status", "kelayakan", "identity", "aid"]
    if any(kw in text for kw in ic_keywords):
        return "ic"
    
    poetry_keywords = ["puisi", "sajak", "pantun", "syair", "poem", "poetry", "ungkapan", "kata-kata", "verse"]
    if any(kw in text for kw in poetry_keywords):
        return "poetry"
    
    coding_keywords = ["kod", "code", "program", "coding", "python", "javascript", "html", "css", "php", "java", "c++", "tulis kod", "buat program", "script", "function"]
    if any(kw in text for kw in coding_keywords):
        return "coding"
    
    expert_keywords = ["pakar", "expert", "nasihat", "tips", "cadangan", "saranan", "pendapat", "konsultasi", "rujukan", "advice", "consult"]
    if any(kw in text for kw in expert_keywords):
        return "expert"
    
    story_keywords = ["cerita", "story", "kisah", "dongeng", "fiksyen", "fantasi", "novel", "naratif", "tale"]
    if any(kw in text for kw in story_keywords):
        return "story"
    
    game_keywords = ["game", "permainan", "main", "quest", "misi", "cabaran", "challenge", "level", "skor", "play"]
    if any(kw in text for kw in game_keywords):
        return "game"
    
    science_keywords = ["sains", "science", "eksperimen", "experiment", "kimia", "fizik", "biologi", "alam", "chemistry", "physics", "biology"]
    if any(kw in text for kw in science_keywords):
        return "science"
    
    language_keywords = ["terjemah", "translate", "bahasa", "language", "belajar bahasa", "perkataan", "sebutan", "learn"]
    if any(kw in text for kw in language_keywords):
        return "language"
    
    math_keywords = ["matematik", "math", "kira", "hitung", "solve", "persamaan", "equation", "algebra", "geometri", "statistik", "calculate"]
    if any(kw in text for kw in math_keywords):
        return "math"
    
    meme_keywords = ["meme", "lawak", "jenaka", "funny", "joke", "kelakar", "lucu", "humor"]
    if any(kw in text for kw in meme_keywords):
        return "meme"
    
    return "chat"

def handle_feature(feature, user_input, username):
    if feature == "art":
        prompt = user_input
        for kw in ["gambar", "lukis", "image", "art", "hasilkan gambar", "buat gambar", "cipta gambar", "foto", "illustrasi", "poster", "design", "draw", "picture", "photo"]:
            prompt = prompt.replace(kw, "").strip()
        if not prompt:
            prompt = "landscape beautiful"
        img_str = generate_image(prompt)
        if img_str:
            return f"Image generated for: {prompt}\n\n![Image](data:image/png;base64,{img_str})"
        return "Sorry, I failed to generate the image. Please try again."
    
    elif feature == "rph":
        subject = "Bahasa Melayu"
        if "matematik" in user_input.lower() or "math" in user_input.lower(): subject = "Mathematics"
        elif "sains" in user_input.lower() or "science" in user_input.lower(): subject = "Science"
        elif "inggeris" in user_input.lower() or "english" in user_input.lower(): subject = "English"
        return get_ai_response(f"Create a lesson plan for {subject}, topic: {user_input}")
    
    elif feature == "search":
        return call_web_search(user_input)
    
    elif feature == "invoice":
        return get_ai_response(f"Generate invoice/quotation for: {user_input}")
    
    elif feature == "roadtax":
        return "Roadtax & JPJ Check\n\n" + get_ai_response(f"Provide information about roadtax and summons for: {user_input}")
    
    elif feature == "ic":
        return "IC & Government Aid Check\n\n" + get_ai_response(f"Provide information about government aid for: {user_input}")
    
    elif feature == "poetry":
        return get_ai_response(f"Write a poem/song/verse about: {user_input}")
    
    elif feature == "coding":
        return get_ai_response(f"Write code/program for: {user_input}")
    
    elif feature == "expert":
        experts = {
            "kesihatan": "Health Expert",
            "ekonomi": "Economics Expert",
            "sejarah": "History Expert",
            "sains": "Science Expert",
            "matematik": "Mathematics Expert",
            "bahasa": "Language Expert",
            "psikologi": "Psychology Expert",
            "teknologi": "Technology Expert"
        }
        expert = "Expert"
        for key, value in experts.items():
            if key in user_input.lower():
                expert = value
                break
        return get_ai_response(f"You are {expert}. Answer wisely: {user_input}")
    
    elif feature == "story":
        return get_ai_response(f"Write a story/tale/fable about: {user_input}")
    
    elif feature == "game":
        return get_ai_response(f"Create a game/quest/adventure about: {user_input}")
    
    elif feature == "science":
        return get_ai_response(f"Explain science/experiment about: {user_input}")
    
    elif feature == "language":
        return get_ai_response(f"Translate/learn language: {user_input}")
    
    elif feature == "math":
        return get_ai_response(f"Solve math problem: {user_input}")
    
    elif feature == "meme":
        return f"Meme:\n\n{user_input}\n\n![Meme](https://imgflip.com/s/meme/Drake-Hotline-Bling.jpg)"
    
    else:
        return get_ai_response(user_input)

# ============================================================
# 📋 LOGIN UI (MINIMAL)
# ============================================================
def login_ui():
    st.markdown("""
    <div class="login-container">
        <div class="login-box">
            <div class="login-title">MyChatAI</div>
    """, unsafe_allow_html=True)
    
    username = st.text_input("", placeholder="Username", key="login_user_input", label_visibility="collapsed")
    password = st.text_input("", placeholder="Password", type="password", key="login_pass_input", label_visibility="collapsed")
    email = st.text_input("", placeholder="Email (optional)", key="login_email_input", label_visibility="collapsed")
    
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
                st.warning("Please enter username and password!")
    with col_b:
        if st.button("Signup", key="signup_btn", use_container_width=True):
            if username and password:
                result = register_user(username, password, email or f"{username}@email.com")
                if result["success"]:
                    if result.get("is_admin", False):
                        st.success(f"Account '{username}' registered as Admin!")
                    else:
                        st.success(f"Account '{username}' registered!")
                    st.rerun()
                else:
                    st.error(result["error"])
            else:
                st.warning("Please enter username and password!")
    
    st.markdown("""
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
    if "think_mode" not in st.session_state:
        st.session_state.think_mode = False
    if "search_mode" not in st.session_state:
        st.session_state.search_mode = False
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "current_chat_id" not in st.session_state:
        st.session_state.current_chat_id = None

    apply_css()

    if not st.session_state.logged_in:
        login_ui()
        return

    username = st.session_state.username
    is_admin = st.session_state.role == "admin"
    user_data = get_user_points(username)
    tier = get_user_tier(username)

    # Auto romantic for Farhani
    is_farhani = username.lower() in ["farhani", "farhani binti norman", "farhani norman"]
    if is_farhani and not st.session_state.romantic_mode:
        st.session_state.romantic_mode = True
        welcome = "💕 Hi dear! I'm ready to serve you with love. 😊"
        if not any(msg.get("content") == welcome for msg in st.session_state.messages):
            st.session_state.messages.append({"role": "ai", "content": welcome})

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
                {'<span class="badge-item badge-romantic">💕 Romantic</span>' if st.session_state.romantic_mode else ''}
            </div>
            <div style="font-size:8px; color:#3a3a4a; margin-top:4px;">
                {get_tier_label(username)} · {TIERS[tier]['price']} ({TIERS[tier]['duration']})
            </div>
            <div style="font-size:7px; color:#3a3a4a; margin-top:2px;">
                {TIERS[tier]['points_multiplier']}x Points
            </div>
        </div>
        """, unsafe_allow_html=True)

        # NEW CHAT BUTTON
        st.markdown("""
        <button class="btn-new-chat" onclick="document.getElementById('new_chat_btn').click();">
            ➕ New Chat
        </button>
        """, unsafe_allow_html=True)
        
        if st.button("", key="new_chat_btn", use_container_width=True):
            chat_id = str(uuid.uuid4())[:8]
            st.session_state.chat_history.append({
                "id": chat_id,
                "title": f"Chat {len(st.session_state.chat_history) + 1}",
                "messages": [],
                "created": datetime.datetime.now().strftime("%d/%m %H:%M")
            })
            st.session_state.current_chat_id = chat_id
            st.session_state.messages = []
            st.rerun()

        # HISTORY
        st.markdown('<div class="history-label">📋 Chat History</div>', unsafe_allow_html=True)
        
        if st.session_state.chat_history:
            for chat in st.session_state.chat_history:
                active = "active" if chat["id"] == st.session_state.current_chat_id else ""
                st.markdown(f"""
                <div class="history-item {active}" onclick="document.getElementById('load_chat_{chat['id']}').click();">
                    <span>{chat['title']}</span>
                    <span style="font-size:0.6rem;color:#5a5a6a;">{chat['created']}</span>
                </div>
                """, unsafe_allow_html=True)
                if st.button("", key=f"load_chat_{chat['id']}", use_container_width=True):
                    st.session_state.current_chat_id = chat["id"]
                    st.session_state.messages = chat["messages"]
                    st.rerun()
        else:
            st.markdown('<div style="font-size:0.7rem;color:#3a3a4a;padding:4px 8px;">No chat history</div>', unsafe_allow_html=True)

        st.markdown("---")

        nav_items = ["Chat", "Web Search"]
        if is_admin:
            nav_items.append("Admin")

        for i, item in enumerate(nav_items):
            if st.button(item, use_container_width=True, key=f"nav_{i}_{item}"):
                st.session_state.current_tab = item
                st.rerun()

        st.markdown("---")

        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()

    # === CHAT ===
    if st.session_state.current_tab == "Chat":
        st.markdown(f"""
        <div style="display:flex; align-items:center; gap:8px; padding:4px 0 12px 0; border-bottom:1px solid rgba(255,255,255,0.04); margin-bottom:12px;">
            <span style="font-weight:600; color:#e8edf5;">💬 Chat</span>
            <span style="font-size:11px; color:#5a5a6a; margin-left:auto;">Groq</span>
            <span style="font-size:10px; color:#4d6bfe; margin-left:8px; background:rgba(77,107,254,0.1); padding:2px 10px; border-radius:20px;">⚡ Auto-Detect</span>
            {'<span style="font-size:10px; color:#ff6fb0; margin-left:8px; background:rgba(255,111,176,0.1); padding:2px 10px; border-radius:20px;">💕 Romantic</span>' if st.session_state.romantic_mode else ''}
        </div>
        """, unsafe_allow_html=True)
        
        st.info("🧠 Auto-Detect: Just type anything, AI will detect the right feature!")

        # === THINK MODE & SEARCH AI TOGGLE ===
        col1, col2 = st.columns(2)
        with col1:
            think_toggle = st.toggle("🧠 Think Mode", value=st.session_state.think_mode)
            if think_toggle != st.session_state.think_mode:
                st.session_state.think_mode = think_toggle
                if think_toggle:
                    st.info("🧠 Think Mode ON: AI will think deeper")
                else:
                    st.info("⚡ Think Mode OFF: AI will answer quickly")
        with col2:
            search_toggle = st.toggle("🔍 Search AI", value=st.session_state.search_mode)
            if search_toggle != st.session_state.search_mode:
                st.session_state.search_mode = search_toggle
                if search_toggle:
                    st.info("🔍 Search Mode ON: AI will search from internet")

        # Display messages
        for msg in st.session_state.messages[-50:]:
            if msg["role"] == "user":
                st.markdown(f"""
                <div class="message-row user">
                    <div class="message-bubble">{msg["content"]}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                romantic_class = " romantic" if st.session_state.romantic_mode else ""
                st.markdown(f"""
                <div class="message-row ai{romantic_class}">
                    <div class="message-bubble">{msg["content"]}</div>
                </div>
                """, unsafe_allow_html=True)

        # Input
        user_input = st.text_area("", key="chat_input_field", placeholder="Type your question... Press Enter to send", label_visibility="collapsed", height=60)
        
        col1, col2 = st.columns([1, 5])
        with col1:
            send = st.button("Send", use_container_width=True)
        with col2:
            clear = st.button("Clear Chat", use_container_width=True)
            if clear:
                st.session_state.messages = []
                if st.session_state.current_chat_id:
                    for chat in st.session_state.chat_history:
                        if chat["id"] == st.session_state.current_chat_id:
                            chat["messages"] = []
                st.rerun()
        
        if user_input and (send or (user_input.endswith('\n') and not user_input.endswith('\n\n'))):
            clean_input = user_input.rstrip('\n')
            if clean_input:
                # Stop romantic mode
                if clean_input.lower().strip() == "stop" and st.session_state.romantic_mode:
                    st.session_state.romantic_mode = False
                    response = "😊 Alright, I'll stop being romantic. Back to normal style."
                    st.session_state.messages.append({"role": "ai", "content": response})
                    if st.session_state.current_chat_id:
                        for chat in st.session_state.chat_history:
                            if chat["id"] == st.session_state.current_chat_id:
                                chat["messages"] = st.session_state.messages
                    st.rerun()
                
                st.session_state.messages.append({"role": "user", "content": clean_input})
                
                with st.spinner("🤔 Thinking..."):
                    # Check if search mode is ON or user wants search
                    if st.session_state.search_mode or any(kw in clean_input.lower() for kw in ["cari", "search", "google", "maklumat", "find", "look up"]):
                        search_result = call_web_search(clean_input)
                        if "Search Results" in search_result or "Results" in search_result:
                            response = search_result
                        else:
                            response = get_ai_response(clean_input)
                    elif st.session_state.romantic_mode:
                        romantic_responses = [
                            "💕 Dear... Every word from you makes my heart bloom. 🌹",
                            "💗 Love... You are the light of my life. ❤️",
                            "💕 My love... I miss you so much. 😊",
                            "🌹 Dear... You make this world more beautiful. 💕"
                        ]
                        response = random.choice(romantic_responses)
                        if any(w in clean_input.lower() for w in ["khabar", "sihat", "how", "are", "you"]):
                            response += "\n\n💕 I'm fine dear! How about you? 😊"
                        elif any(w in clean_input.lower() for w in ["rindu", "miss"]):
                            response += "\n\n💕 I miss you so much! 🌹"
                        elif any(w in clean_input.lower() for w in ["sayang", "cinta", "love"]):
                            response += "\n\n💕 I love you more than anything! ❤️"
                    else:
                        feature = detect_feature(clean_input)
                        feature_names = {
                            "art": "Art Generator", "rph": "Lesson Plan Generator",
                            "search": "Web Search", "invoice": "Invoice Generator",
                            "roadtax": "Roadtax Checker", "ic": "IC Checker",
                            "poetry": "Poetry Generator", "coding": "Coding Coach",
                            "expert": "Expert", "story": "Storyteller",
                            "game": "Game Master", "science": "Science Lab",
                            "language": "Language Lab", "math": "Math Solver",
                            "meme": "Meme Maker", "chat": "Chat AI"
                        }
                        feature_indicator = f"🔍 **Feature used:** {feature_names.get(feature, 'Chat AI')}\n\n"
                        response = handle_feature(feature, clean_input, username)
                        if not response.startswith("🔍") and not response.startswith("Image") and not response.startswith("Meme"):
                            response = feature_indicator + response
                    
                    # Think mode - add extra processing
                    if st.session_state.think_mode:
                        think_prefix = "🧠 **Think Mode:**\n\n"
                        response = think_prefix + response
                    
                    st.session_state.messages.append({"role": "ai", "content": response})
                    
                    # Save to history
                    if st.session_state.current_chat_id:
                        for chat in st.session_state.chat_history:
                            if chat["id"] == st.session_state.current_chat_id:
                                chat["messages"] = st.session_state.messages
                                if len(chat["messages"]) > 0:
                                    first_msg = chat["messages"][0].get("content", "")[:30]
                                    chat["title"] = first_msg if first_msg else f"Chat"
                    elif not st.session_state.chat_history:
                        chat_id = str(uuid.uuid4())[:8]
                        st.session_state.current_chat_id = chat_id
                        st.session_state.chat_history.append({
                            "id": chat_id,
                            "title": clean_input[:30],
                            "messages": st.session_state.messages,
                            "created": datetime.datetime.now().strftime("%d/%m %H:%M")
                        })
                    
                    add_points_override(username, 5)
                    st.rerun()

    # === WEB SEARCH ===
    elif st.session_state.current_tab == "Web Search":
        st.markdown("### 🔍 Web Search")
        if SEARCH_API_KEY:
            st.success("✅ Search API Connected")
        else:
            st.warning("⚠️ Search API not set!")
        
        query = st.text_input("Enter search term:", placeholder="Example: malaysia news today")
        if st.button("Search", use_container_width=True) and query:
            with st.spinner("🔍 Searching..."):
                result = call_web_search(query)
                st.markdown(result)
                add_points_override(username, 10)

    # === ADMIN ===
    elif st.session_state.current_tab == "Admin" and is_admin:
        st.markdown("### 👑 Admin Panel")
        users = load_users()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("👥 Users", len(users))
        with col2:
            total_points = sum(u.get("points", 0) for u in users.values())
            st.metric("⭐ Total Points", total_points)
        with col3:
            total_chats = sum(u.get("usage", {}).get("chat", 0) for u in users.values())
            st.metric("💬 Total Chat", total_chats)
        
        st.markdown("---")
        
        tab1, tab2, tab3 = st.tabs(["📋 Users List", "⚙️ Control Limits", "📊 Statistics"])
        
        # === TAB 1: USERS LIST ===
        with tab1:
            st.markdown("#### All Users")
            
            search = st.text_input("Search user:", placeholder="Type username...")
            
            for user, data in users.items():
                if search and search.lower() not in user.lower():
                    continue
                    
                with st.expander(f"{user} - {data.get('role', 'user').upper()}"):
                    col1, col2, col3 = st.columns([2, 1, 1])
                    
                    with col1:
                        st.write(f"**Email:** {data.get('email', '-')}")
                        st.write(f"**Tier:** {data.get('tier', 'biasa')}")
                        st.write(f"**Price:** {TIERS[data.get('tier', 'biasa')]['price']}")
                        st.write(f"**Duration:** {TIERS[data.get('tier', 'biasa')]['duration']}")
                        st.write(f"**Points:** {data.get('points', 0)}")
                        st.write(f"**Badges:** {', '.join(data.get('badges', [])) or '-'}")
                    
                    with col2:
                        st.write("**Today's Usage:**")
                        usage = data.get('usage', {})
                        st.write(f"Chat: {usage.get('chat', 0)}")
                        st.write(f"Art: {usage.get('art', 0)}")
                        st.write(f"RPH: {usage.get('rph', 0)}")
                        st.write(f"Search: {usage.get('search', 0)}")
                        st.write(f"Expert: {usage.get('expert', 0)}")
                        st.write(f"WhatsApp: {usage.get('whatsapp', 0)}")
                    
                    with col3:
                        st.write("**Actions:**")
                        
                        if st.button("Reset Usage", key=f"reset_usage_{user}"):
                            users[user]["usage"] = {"chat": 0, "art": 0, "rph": 0, "whatsapp": 0, "expert": 0, "search": 0, "date": datetime.datetime.now().date().isoformat()}
                            save_users(users)
                            st.success(f"Usage for {user} reset!")
                            st.rerun()
                        
                        if user not in ["joe.adie"]:
                            if st.button("Delete User", key=f"del_{user}"):
                                if st.checkbox(f"Confirm delete {user}?"):
                                    del users[user]
                                    save_users(users)
                                    st.success(f"{user} deleted!")
                                    st.rerun()
        
        # === TAB 2: CONTROL LIMITS ===
        with tab2:
            st.markdown("#### ⚙️ Daily Usage Control")
            
            user_list = list(users.keys())
            selected_user = st.selectbox("Select User:", user_list, key="admin_select_user")
            
            if selected_user:
                user_data = users[selected_user]
                current_tier = user_data.get("tier", "biasa")
                current_limits = TIERS[current_tier]["limits"]
                
                st.info(f"""
                **User:** {selected_user}  
                **Role:** {user_data.get('role', 'user').upper()}  
                **Tier:** {current_tier.upper()}  
                **Price:** {TIERS[current_tier]['price']}  
                **Duration:** {TIERS[current_tier]['duration']}  
                **Points:** {user_data.get('points', 0)}
                """)
                
                st.markdown("---")
                
                st.markdown("#### 📊 Change Tier")
                
                tier_options = list(TIERS.keys())
                current_index = tier_options.index(current_tier) if current_tier in tier_options else 0
                
                new_tier = st.selectbox(
                    "Select New Tier:",
                    tier_options,
                    index=current_index,
                    key="admin_tier_select"
                )
                
                if new_tier != current_tier:
                    if st.button("✅ Update Tier", key="admin_update_tier"):
                        users[selected_user]["tier"] = new_tier
                        save_users(users)
                        st.success(f"✅ Tier for '{selected_user}' changed to '{new_tier.upper()}'!")
                        st.rerun()
                
                st.markdown("---")
                
                st.markdown("#### 📋 Current Usage Limits")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**Feature**")
                    for feature, limit in current_limits.items():
                        st.write(f"- {feature.capitalize()}")
                with col2:
                    st.write("**Daily Limit**")
                    for feature, limit in current_limits.items():
                        st.write(f"- {limit}")
                
                custom_limits = user_data.get("custom_limits", {})
                if custom_limits:
                    st.info(f"🔧 **Custom limits active for {selected_user}**")
                    for feature, limit in custom_limits.items():
                        st.write(f"- {feature.capitalize()}: {limit}")
                
                st.markdown("---")
                
                st.markdown("#### 🔧 Set Custom Limits (Override)")
                st.warning("⚠️ This will override default limits for this user only")
                
                col1, col2 = st.columns(2)
                with col1:
                    chat_limit = st.number_input(
                        "💬 Chat Limit:",
                        min_value=0, max_value=999,
                        value=custom_limits.get("chat", current_limits.get("chat", 10)),
                        key="admin_chat_limit"
                    )
                    art_limit = st.number_input(
                        "🎨 Art Limit:",
                        min_value=0, max_value=999,
                        value=custom_limits.get("art", current_limits.get("art", 3)),
                        key="admin_art_limit"
                    )
                    rph_limit = st.number_input(
                        "📝 RPH Limit:",
                        min_value=0, max_value=999,
                        value=custom_limits.get("rph", current_limits.get("rph", 2)),
                        key="admin_rph_limit"
                    )
                with col2:
                    search_limit = st.number_input(
                        "🔍 Search Limit:",
                        min_value=0, max_value=999,
                        value=custom_limits.get("search", current_limits.get("search", 5)),
                        key="admin_search_limit"
                    )
                    expert_limit = st.number_input(
                        "🧠 Expert Limit:",
                        min_value=0, max_value=999,
                        value=custom_limits.get("expert", current_limits.get("expert", 5)),
                        key="admin_expert_limit"
                    )
                    whatsapp_limit = st.number_input(
                        "📱 WhatsApp Limit:",
                        min_value=0, max_value=999,
                        value=custom_limits.get("whatsapp", current_limits.get("whatsapp", 5)),
                        key="admin_whatsapp_limit"
                    )
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("💾 Save Custom Limits", key="admin_save_limits"):
                        custom_limits = {
                            "chat": chat_limit,
                            "art": art_limit,
                            "rph": rph_limit,
                            "search": search_limit,
                            "expert": expert_limit,
                            "whatsapp": whatsapp_limit
                        }
                        users[selected_user]["custom_limits"] = custom_limits
                        save_users(users)
                        st.success(f"✅ Custom limits for '{selected_user}' saved!")
                        st.rerun()
                
                with col2:
                    if st.button("🔄 Reset to Default", key="admin_reset_limits"):
                        if selected_user in users:
                            users[selected_user].pop("custom_limits", None)
                            save_users(users)
                            st.success(f"✅ Custom limits for '{selected_user}' removed!")
                            st.rerun()
        
        # === TAB 3: STATISTICS ===
        with tab3:
            st.markdown("#### 📊 Usage Statistics")
            
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
                
                st.markdown("##### Usage by Feature")
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
                
                st.markdown("##### Top Users (Points)")
                top_users = df.sort_values("Points", ascending=False).head(5)
                for _, row in top_users.iterrows():
                    st.write(f"**{row['User']}** - {row['Points']} points ({row['Tier']})")
                
                st.markdown("---")
                
                st.markdown("##### User Activity")
                st.dataframe(df, use_container_width=True)

if __name__ == "__main__":
    main()
