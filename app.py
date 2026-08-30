# mychat_ultimate_pro_v41.1.py
import streamlit as st
import datetime
import json
import os
import base64
import requests
import time
import random
import hashlib
import uuid
import re
from io import BytesIO
from PIL import Image
import pandas as pd

# === PAGE CONFIG ===
st.set_page_config(
    page_title="MyChatAI Pro",
    page_icon=":material/chat:",
    layout="wide",
    initial_sidebar_state="expanded"
)

# === API KEYS ===
GROQ_API_KEY = ""
OPENROUTER_API_KEY = ""
CRAZYROUTER_API_KEY = "YOUR_CRAZYROUTER_API_KEY"

# === CONSTANTS ===
USER_DATA_FILE = "mychat_users.json"
CHAT_HISTORY_FILE = "mychat_chats.json"
POINTS_FILE = "mychat_points.json"
RPH_HISTORY_FILE = "rph_history.json"
USAGE_FILE = "mychat_usage.json"
ADMIN_EMAIL = "joe.adie77711@gmail.com"
MAX_FREE_REQUESTS = 1000

# === HASH ===
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def is_admin_user(email):
    return email == ADMIN_EMAIL

def get_user_role(email):
    return "admin" if is_admin_user(email) else "user"

# ============================================================
# DATA FUNCTIONS
# ============================================================
def load_users():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, "r") as f:
            return json.load(f)
    default = {
        "admin": {
            "password": hash_password("777777"),
            "role": "admin",
            "email": ADMIN_EMAIL,
            "points": 0,
            "badges": [],
            "settings": {"temperature": 0.7, "max_tokens": 4096}
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

# ============================================================
# SISTEM HAD PENGGUNAAN
# ============================================================
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
    if user_data.get("role") == "admin":
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

def reset_user_usage(username):
    save_usage(username, {"count": 0, "month": datetime.datetime.now().month, "year": datetime.datetime.now().year})
    return True

# ============================================================
# AUTH FUNCTIONS
# ============================================================
def login_user(username, password):
    users = load_users()
    if username not in users:
        return {"success": False, "error": "Username tidak wujud"}
    if users[username]["password"] != hash_password(password):
        return {"success": False, "error": "Password salah"}
    return {"success": True, "username": username, "role": users[username].get("role", "user")}

def register_user(username, password, email):
    users = load_users()
    if username in users:
        return {"success": False, "error": "Username sudah wujud"}
    if len(password) < 6:
        return {"success": False, "error": "Password mesti 6 aksara"}
    role = get_user_role(email)
    users[username] = {
        "password": hash_password(password),
        "role": role,
        "email": email,
        "points": 100 if role == "user" else 0,
        "badges": [],
        "settings": {"temperature": 0.7, "max_tokens": 4096}
    }
    save_users(users)
    return {"success": True, "username": username}

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

# ============================================================
# AI FUNCTIONS - GROQ + DEEPSEEK-R1
# ============================================================
def call_groq(prompt):
    """Groq API - Cepat untuk chat biasa"""
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama-3.1-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 2048
        }
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        return f"Ralat Groq: {response.status_code}"
    except Exception as e:
        return f"Ralat: {str(e)}"

def call_deepseek_r1(prompt):
    """DeepSeek-R1 - Power Coding & Analisis"""
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://mychatai.com",
            "X-Title": "MyChatAI Pro"
        }
        payload = {
            "model": "deepseek/deepseek-r1:free",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 4096
        }
        response = requests.post(url, json=payload, headers=headers, timeout=90)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        return f"Ralat DeepSeek: {response.status_code}"
    except Exception as e:
        return f"Ralat: {str(e)}"

def call_gemini_free(prompt):
    """Gemini 2.0 Flash - Percuma via OpenRouter"""
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://mychatai.com",
            "X-Title": "MyChatAI Pro"
        }
        payload = {
            "model": "google/gemini-2.0-flash-exp:free",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 4096
        }
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        return f"Ralat Gemini: {response.status_code}"
    except Exception as e:
        return f"Ralat: {str(e)}"

# ============================================================
# SMART AI - AUTO PILIH MODEL TERBAIK
# ============================================================
def smart_ai(username, prompt):
    limit_check = check_usage_limit(username)
    if not limit_check["allowed"]:
        return f"""
Had Penggunaan Bulanan Telah Dicapai
Penggunaan: {limit_check['used']}/{limit_check['limit']}
Baki: 0 request
Reset automatik pada: {datetime.datetime.now().replace(day=1).strftime('%d %B %Y')}
"""
    
    # Detect jenis soalan
    coding_keywords = ["kod", "coding", "python", "javascript", "program", "bug", "error", "function", "class", "algorithm", "tulis", "code"]
    analysis_keywords = ["analisis", "mendalam", "research", "thesis", "reasoning", "logik", "kajian"]
    
    # Pilih model terbaik
    if any(word in prompt.lower() for word in coding_keywords) or any(word in prompt.lower() for word in analysis_keywords):
        response = call_deepseek_r1(prompt)
    elif len(prompt) > 100:
        response = call_deepseek_r1(prompt)
    else:
        response = call_groq(prompt)
    
    new_count = increment_usage(username)
    remaining = MAX_FREE_REQUESTS - new_count
    if "Ralat" not in response[:20]:
        response += f"\n\n---\nPenggunaan: {new_count}/{MAX_FREE_REQUESTS} | Baki: {remaining} request"
    return response

# ============================================================
# CSS
# ============================================================
def apply_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
    * { font-family: 'Inter', sans-serif; }
    .stApp { background: #0d0d0d; }
    .stSidebar { background: rgba(255,255,255,0.02) !important; border-right: 1px solid rgba(255,255,255,0.04) !important; }
    .stButton > button { background: linear-gradient(135deg, #4d6bfe, #7c3aed); color: white; border: none; border-radius: 10px; font-weight: 600; padding: 10px 16px; transition: all 0.2s ease; width: 100%; }
    .stButton > button:hover { transform: scale(1.01); box-shadow: 0 4px 20px rgba(77,107,254,0.2); }
    .stMetric > div { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.04); border-radius: 12px; padding: 12px; }
    ::-webkit-scrollbar { width: 4px; }
    ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }
    .glass { background: rgba(255,255,255,0.03); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.04); border-radius: 12px; padding: 16px; }
    .chat-bubble-user { background: linear-gradient(135deg, #4d6bfe, #7c3aed); color: white; padding: 10px 16px; border-radius: 14px 14px 4px 14px; max-width: 80%; margin-left: auto; margin-bottom: 8px; }
    .chat-bubble-ai { background: rgba(255,255,255,0.03); color: #e8edf5; padding: 10px 16px; border-radius: 14px 14px 14px 4px; max-width: 80%; margin-right: auto; margin-bottom: 8px; border: 1px solid rgba(255,255,255,0.04); }
    .usage-progress { background: rgba(255,255,255,0.05); border-radius: 5px; height: 6px; margin-top: 4px; overflow: hidden; }
    .usage-progress-fill { height: 6px; border-radius: 5px; transition: width 0.3s ease; }
    @media (max-width: 768px) { .stSidebar { width: 280px !important; } }
    </style>
    """, unsafe_allow_html=True)

# ============================================================
# LOGIN UI
# ============================================================
def login_ui():
    apply_css()
    st.markdown("""
    <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; min-height:100vh; padding:20px;">
        <div style="max-width:400px; width:100%; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:32px 24px;">
            <div style="text-align:center; margin-bottom:20px;">
                <h1 style="font-size:28px; font-weight:800; background:linear-gradient(135deg,#4d6bfe,#7c3aed); -webkit-background-clip:text; -webkit-text-fill-color:transparent;">MyChatAI Pro</h1>
                <p style="color:#8a8a9a; font-size:14px;">Groq · DeepSeek-R1 · Gemini · 1000 Request Percuma</p>
                <p style="color:#5a5a6a; font-size:11px;">Admin: joe.adie77711@gmail.com</p>
            </div>
            <div style="margin:12px 0;">
                <input type="text" placeholder="Username" id="login_user" style="width:100%; padding:12px 16px; border-radius:10px; border:1px solid rgba(255,255,255,0.06); background:rgba(255,255,255,0.02); color:#e8edf5; font-size:14px; outline:none; margin-bottom:8px;">
                <input type="password" placeholder="Password" id="login_pass" style="width:100%; padding:12px 16px; border-radius:10px; border:1px solid rgba(255,255,255,0.06); background:rgba(255,255,255,0.02); color:#e8edf5; font-size:14px; outline:none; margin-bottom:8px;">
                <input type="email" placeholder="Email" id="login_email" style="width:100%; padding:12px 16px; border-radius:10px; border:1px solid rgba(255,255,255,0.06); background:rgba(255,255,255,0.02); color:#e8edf5; font-size:14px; outline:none; margin-bottom:12px;">
                <button style="width:100%; padding:12px; background:linear-gradient(135deg,#4d6bfe,#7c3aed); border:none; border-radius:10px; font-weight:600; color:white; cursor:pointer;" onclick="document.getElementById('login_btn').click();">Login</button>
            </div>
            <div style="text-align:center; margin-top:12px; font-size:13px; color:#5a5a6a;">Tiada akaun? <a href="#" style="color:#4d6bfe; text-decoration:none;" onclick="document.getElementById('signup_btn').click();">Daftar Sekarang</a></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input("Username", key="login_user_input", placeholder="Masukkan username", label_visibility="collapsed")
        password = st.text_input("Password", type="password", key="login_pass_input", placeholder="Masukkan password", label_visibility="collapsed")
        email = st.text_input("Email", key="login_email_input", placeholder="Masukkan email", label_visibility="collapsed")
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
                    st.warning("Sila isi username dan password")
        with col_b:
            if st.button("Signup", key="signup_btn", use_container_width=True):
                if username and password and email:
                    result = register_user(username, password, email)
                    if result["success"]:
                        st.success(f"Akaun '{username}' didaftarkan")
                    else:
                        st.error(result["error"])
                else:
                    st.warning("Sila isi semua maklumat")

# ============================================================
# LAUNCH PAD
# ============================================================
def launch_pad_ui():
    st.markdown("""
    <div style="background:linear-gradient(135deg,#4d6bfe22,#7c3aed22); border-radius:12px; padding:16px; margin-bottom:16px;">
        <h3 style="color:#4d6bfe;">Launch Pad</h3>
        <p style="color:#8a8a9a;">Klik mana-mana butang untuk akses ciri.</p>
    </div>
    """, unsafe_allow_html=True)
    features = [
        "Chat", "RPH", "Art", "Video", "Music",
        "Invois", "WhatsApp", "Neural Networks",
        "Roadtax", "IC", "Kontraktor", "Business",
        "Fitness", "Meditation", "Research", "Comic",
        "Game", "Analytics"
    ]
    cols = st.columns(4)
    for i, name in enumerate(features):
        with cols[i % 4]:
            if st.button(name, key=f"launch_{name.lower().replace(' ', '_')}", use_container_width=True):
                st.session_state.current_tab = name
                st.rerun()
    username = st.session_state.username
    status = get_usage_status(username)
    percentage = status["percentage"]
    color = "green" if percentage < 70 else "orange" if percentage < 90 else "red"
    st.markdown(f"""
    <div style="background:rgba(255,255,255,0.03); border-radius:10px; padding:12px; border:1px solid rgba(255,255,255,0.04); margin-top:12px;">
        <div style="display:flex; justify-content:space-between;">
            <span style="color:#8a8a9a; font-size:0.7rem;">Penggunaan Bulanan</span>
            <span style="color:#e8edf5; font-size:0.7rem;">{status['used']} / {status['limit']}</span>
        </div>
        <div class="usage-progress">
            <div class="usage-progress-fill" style="background:{color}; width:{percentage}%;"></div>
        </div>
        <div style="display:flex; justify-content:space-between; font-size:0.55rem; color:#5a5a6a; margin-top:2px;">
            <span>Baki: {status['remaining']}</span>
            <span>Reset: {datetime.datetime.now().replace(day=1).strftime('%d/%m')}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ============================================================
# FUNGSI CIRI
# ============================================================
def chat_ui():
    st.markdown("### Chat")
    for msg in st.session_state.messages[-20:]:
        if msg["role"] == "user":
            st.markdown(f'<div class="chat-bubble-user">{msg["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-bubble-ai"> {msg["content"]}</div>', unsafe_allow_html=True)
    user_input = st.text_input("Taip soalan...", key="chat_input")
    if st.button("Hantar", use_container_width=True) and user_input:
        st.session_state.messages.append({"role": "user", "content": user_input, "time": datetime.datetime.now().strftime("%H:%M")})
        with st.spinner("Menganalisis..."):
            response = smart_ai(st.session_state.username, user_input)
        st.session_state.messages.append({"role": "ai", "content": response, "time": datetime.datetime.now().strftime("%H:%M")})
        st.rerun()

def rph_ui():
    st.markdown("### RPH Generator")
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
        add_points(st.session_state.username, 20)

def art_ui():
    st.markdown("### Art Generator")
    prompt = st.text_input("Huraikan gambar")
    if st.button("Hasilkan", use_container_width=True) and prompt:
        try:
            url = f"https://image.pollinations.ai/prompt/{prompt}?width=1024&height=1024&nologo=true"
            response = requests.get(url, timeout=60)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content))
                st.image(img, use_container_width=True)
                add_points(st.session_state.username, 15)
            else:
                st.error("Gagal menghasilkan gambar")
        except:
            st.error("Ralat")

def video_ui():
    st.markdown("### Video Generator")
    prompt = st.text_area("Huraikan video", height=80)
    duration = st.slider("Durasi (saat)", 3, 15, 5)
    if st.button("Hasilkan Video", use_container_width=True) and prompt:
        with st.spinner("Menghasilkan video..."):
            try:
                url = f"https://image.pollinations.ai/video?prompt={prompt}&duration={duration}"
                response = requests.get(url, timeout=120)
                if response.status_code == 200:
                    st.video(response.content)
                    st.download_button("Download Video", data=response.content, file_name="video.mp4", mime="video/mp4")
                    add_points(st.session_state.username, 25)
                    st.success("Video berjaya dihasilkan")
                else:
                    st.error("Gagal menghasilkan video")
            except:
                st.error("Ralat")

# ============================================================
# MUSIC GENERATOR - TTS + SUNO HYBRID
# ============================================================
def generate_suno_music(prompt, style="pop", instrumental=False):
    try:
        BASE_URL = "http://localhost:3000"
        SESSION_ID = st.secrets.get("SUNO_SESSION_ID", "")
        if not SESSION_ID:
            return generate_suno_crazyrouter(prompt, style, instrumental)
        response = requests.post(
            f"{BASE_URL}/api/generate",
            json={
                "prompt": prompt,
                "style": style,
                "make_instrumental": instrumental,
                "wait_audio": True
            },
            headers={"Cookie": f"session_id={SESSION_ID}"},
            timeout=120
        )
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "audio_url": data[0]["audio_url"],
                "title": data[0].get("title", "Lagu Suno"),
                "lyrics": data[0].get("lyrics", "")
            }
        else:
            return {"success": False, "error": f"Status: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def generate_suno_crazyrouter(prompt, style="pop", instrumental=False):
    try:
        if not CRAZYROUTER_API_KEY or CRAZYROUTER_API_KEY == "YOUR_CRAZYROUTER_API_KEY":
            return {"success": False, "error": "Tiada API Key Crazyrouter"}
        BASE_URL = "https://api.crazyrouter.com"
        response = requests.post(
            f"{BASE_URL}/suno/submit/music",
            headers={"Authorization": f"Bearer {CRAZYROUTER_API_KEY}"},
            json={
                "prompt": prompt,
                "style": style,
                "make_instrumental": instrumental
            },
            timeout=30
        )
        if response.status_code == 200:
            task_id = response.json()["data"]["task_id"]
            for _ in range(12):
                status = requests.get(
                    f"{BASE_URL}/suno/fetch/{task_id}",
                    headers={"Authorization": f"Bearer {CRAZYROUTER_API_KEY}"}
                )
                if status.json()["data"]["status"] == "completed":
                    tracks = status.json()["data"]["tracks"]
                    return {
                        "success": True,
                        "audio_url": tracks[0]["audio_url"],
                        "title": tracks[0]["title"],
                        "lyrics": tracks[0]["lyrics"]
                    }
                time.sleep(10)
            return {"success": False, "error": "Timeout"}
        else:
            return {"success": False, "error": f"Status: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def music_generator_hybrid_ui():
    st.markdown("""
    <div style="background:linear-gradient(135deg,#4d6bfe22,#7c3aed22); border-radius:12px; padding:16px; margin-bottom:16px;">
        <h3 style="color:#4d6bfe;">Music Generator - TTS + Suno Hybrid</h3>
        <p style="color:#8a8a9a;">Pilih mod: TTS (Percuma) atau Suno (Lagu Sebenar)</p>
    </div>
    """, unsafe_allow_html=True)
    
    mode = st.radio(
        "Pilih Mod:",
        ["TTS (Percuma, Bacaan Lirik)", "Suno (Lagu Sebenar, 50 kredit/hari)", "Hybrid (TTS + Suno)"],
        index=0,
        horizontal=True
    )
    
    col1, col2 = st.columns(2)
    with col1:
        prompt = st.text_area(
            "Huraikan lagu:",
            placeholder="Contoh: Lagu cinta yang romantik tentang bulan dan bintang",
            height=80
        )
        style = st.selectbox(
            "Gaya Muzik:",
            ["pop", "rock", "jazz", "classical", "hip-hop", "rnb", "electronic", "acoustic", "lo-fi", "indie", "dangdut", "keroncong"]
        )
        with_lyrics = st.checkbox("Hasilkan Lirik", value=True)
    with col2:
        st.markdown("### Tetapan Lanjutan")
        if "Suno" in mode:
            instrumental = st.checkbox("Instrumental sahaja", value=False)
            duration = st.selectbox("Durasi:", ["15 saat", "30 saat", "60 saat"], index=1)
            quality = st.selectbox("Kualiti:", ["Standard", "High", "Ultra"], index=1)
        else:
            instrumental = False
            duration = "30 saat"
            quality = "Standard"
        st.markdown("### Tips")
        st.markdown("""
        **TTS Mode:** Cepat, percuma, bacaan lirik
        **Suno Mode:** Lagu sebenar, ada melodi & irama
        **Hybrid Mode:** Dapat kedua-duanya!
        """)
    
    if st.button("Hasilkan Lagu", use_container_width=True) and prompt:
        with st.spinner("Menghasilkan lagu..."):
            results = []
            lyrics = ""
            if with_lyrics:
                lyrics_prompt = f"Tulis lirik lagu {style} tentang: {prompt}\n\nFormat: [Tajuk]\n[Verse 1]\n[Chorus]\n[Verse 2]\n[Chorus]\n[Bridge]\n[Outro]"
                lyrics = call_deepseek_r1(lyrics_prompt)
                st.markdown("### Lirik Lagu")
                st.markdown(f"""
                <div style="background:rgba(255,255,255,0.03); border-radius:10px; padding:16px; border:1px solid rgba(255,255,255,0.04); white-space:pre-wrap; font-family:monospace; line-height:1.8;">
                {lyrics}
                </div>
                """, unsafe_allow_html=True)
            
            audio_text = lyrics if lyrics else prompt
            
            if "TTS" in mode:
                try:
                    tts_url = f"https://api.pollinations.ai/tts?text={audio_text[:500]}&voice=alloy"
                    tts_response = requests.get(tts_url, timeout=60)
                    if tts_response.status_code == 200:
                        st.audio(tts_response.content, format="audio/mp3")
                        st.download_button(
                            "Download TTS Audio",
                            data=tts_response.content,
                            file_name="tts_audio.mp3",
                            mime="audio/mpeg"
                        )
                        results.append("TTS")
                        add_points(st.session_state.username, 10)
                except Exception as e:
                    st.error(f"TTS Ralat: {str(e)}")
            
            if "Suno" in mode:
                try:
                    suno_result = generate_suno_music(prompt, style, instrumental)
                    if suno_result["success"]:
                        audio_response = requests.get(suno_result["audio_url"], timeout=60)
                        if audio_response.status_code == 200:
                            st.audio(audio_response.content, format="audio/mp3")
                            st.download_button(
                                "Download Suno Audio",
                                data=audio_response.content,
                                file_name="suno_audio.mp3",
                                mime="audio/mpeg"
                            )
                            results.append("Suno")
                            add_points(st.session_state.username, 20)
                        else:
                            st.warning("Audio Suno tidak dapat dimuat turun")
                    else:
                        st.warning(f"Suno: {suno_result['error']}")
                except Exception as e:
                    st.error(f"Suno Ralat: {str(e)}")
            
            if results:
                st.success(f"Berjaya: {', '.join(results)}")
            else:
                st.warning("Tiada audio berjaya dihasilkan")

def invoice_ui():
    st.markdown("### Invois")
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
        add_points(st.session_state.username, 30)

def whatsapp_ui():
    st.markdown("### WhatsApp")
    phone = st.text_input("No Telefon", placeholder="60123456789")
    message = st.text_area("Mesej", height=100)
    if st.button("Hantar", use_container_width=True) and phone and message:
        clean_phone = re.sub(r'[^0-9]', '', phone)
        if not clean_phone.startswith('6'):
            clean_phone = '6' + clean_phone
        msg_encoded = requests.utils.quote(message)
        whatsapp_url = f"https://wa.me/{clean_phone}?text={msg_encoded}"
        st.markdown(f'<a href="{whatsapp_url}" target="_blank"><button style="background:#25D366; color:white; padding:8px 16px; border:none; border-radius:8px; font-weight:600; cursor:pointer;">Buka WhatsApp</button></a>', unsafe_allow_html=True)
        add_points(st.session_state.username, 15)

def neural_ui():
    st.markdown("### Neural Networks Expert")
    st.markdown("""
    Neural Networks adalah sistem komputasi yang terinspirasi dari otak manusia.
    Komponen Utama:
    - Input Layer
    - Hidden Layers
    - Output Layer
    - Weights & Biases
    Jenis-Jenis:
    1. CNN - Untuk imej & video
    2. RNN - Untuk data berurutan
    3. LSTM - RNN dengan ingatan
    4. Transformers - Asas ChatGPT
    5. GANs - Menghasilkan data baru
    """)

def roadtax_ui():
    st.markdown("### Roadtax & Saman")
    st.info("Untuk semakan sebenar, gunakan aplikasi MyJPJ")
    st.markdown("""
    Simulasi:
    - Roadtax: SAH (Tamat: 31/12/2026)
    - Saman: 2 saman (RM 600)
    - Insurans: AKTIF
    """)

def ic_ui():
    st.markdown("### IC & Bantuan")
    st.info("Untuk semakan sebenar, gunakan portal rasmi")
    st.markdown("""
    Simulasi:
    - STR: LAYAK (RM 500)
    - BPN: LAYAK (RM 1,200)
    - BKC: LAYAK (RM 250)
    """)

def contractor_ui():
    st.markdown("### Kontraktor & Tender")
    tender_name = st.text_input("Nama Projek")
    tender_budget = st.number_input("Bajet (RM)", min_value=0.0, value=0.0)
    if st.button("Buka Tender", use_container_width=True) and tender_name and tender_budget > 0:
        st.success(f"Tender '{tender_name}' berjaya dibuka")
        add_points(st.session_state.username, 30)

def business_ui():
    st.markdown("### Business Tools")
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
        add_points(st.session_state.username, 35)

def fitness_ui():
    st.markdown("### Fitness Tracker")
    goal = st.selectbox("Matlamat", ["Turun Berat", "Bina Otot", "Kekal Sihat"])
    days = st.slider("Hari seminggu", 1, 7, 3)
    if st.button("Jana Rancangan", use_container_width=True):
        response = call_deepseek_r1(f"Hasilkan rancangan senaman untuk matlamat {goal} ({days} hari seminggu)")
        st.markdown(response)
        add_points(st.session_state.username, 20)

def meditation_ui():
    st.markdown("### Meditation Guide")
    duration = st.slider("Durasi (minit)", 1, 30, 10)
    if st.button("Mula Meditasi", use_container_width=True):
        response = call_deepseek_r1(f"Panduan meditasi selama {duration} minit")
        st.markdown(response)
        add_points(st.session_state.username, 20)

def research_ui():
    st.markdown("### Research Assistant")
    topic = st.text_input("Topik Penyelidikan")
    if st.button("Mulakan Penyelidikan", use_container_width=True) and topic:
        response = call_deepseek_r1(f"Buat literature review untuk topik: {topic}")
        st.markdown(response)
        add_points(st.session_state.username, 30)

def comic_ui():
    st.markdown("### Comic Generator")
    title = st.text_input("Tajuk Komik")
    if st.button("Hasilkan Komik", use_container_width=True) and title:
        response = call_deepseek_r1(f"Hasilkan komik bertajuk: {title}")
        st.markdown(response)
        add_points(st.session_state.username, 30)

def game_ui():
    st.markdown("### Game Master")
    game_type = st.selectbox("Jenis", ["Escape Room", "Murder Mystery", "Treasure Hunt", "Adventure"])
    if st.button("Mula Permainan", use_container_width=True):
        response = call_deepseek_r1(f"Cipta {game_type} yang menarik")
        st.markdown(response)
        add_points(st.session_state.username, 25)

def analytics_ui():
    st.markdown("### Analytics Dashboard")
    users = load_users()
    chats = load_chats()
    points = load_points()
    rph = load_rph_history()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Pengguna", len(users))
    with col2:
        st.metric("Chat", sum(len(c) for c in chats.values()))
    with col3:
        st.metric("Points", sum(p.get("points", 0) for p in points.values()))
    with col4:
        st.metric("RPH", len(rph))

# ============================================================
# ADMIN
# ============================================================
def admin_ui():
    st.markdown("### Admin Panel")
    users = load_users()
    st.metric("Pengguna", len(users))
    for user, data in users.items():
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.write(user)
        with col2:
            st.write(f"Points: {data.get('points', 0)}")
        with col3:
            if user != "admin" and st.button("Padam", key=f"del_{user}"):
                del users[user]
                save_users(users)
                st.rerun()
    st.markdown("---")
    st.markdown("### Reset Penggunaan")
    user_list = [u for u in users.keys()]
    selected_user = st.selectbox("Pilih Pengguna", user_list)
    if st.button("Reset Penggunaan", use_container_width=True):
        if reset_user_usage(selected_user):
            st.success(f"Penggunaan {selected_user} telah direset")

# ============================================================
# SETTINGS
# ============================================================
def settings_ui():
    st.markdown("### Settings")
    col1, col2 = st.columns(2)
    with col1:
        temp = st.slider("Temperature", 0.0, 1.0, 0.7, 0.05)
    with col2:
        max_tokens = st.slider("Max Tokens", 256, 4096, 2048, 256)
    if st.button("Simpan Settings", use_container_width=True):
        users = load_users()
        users[st.session_state.username]["settings"] = {"temperature": temp, "max_tokens": max_tokens}
        save_users(users)
        st.success("Settings disimpan")

# ============================================================
# MAIN
# ============================================================
def main():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "username" not in st.session_state:
        st.session_state.username = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "current_tab" not in st.session_state:
        st.session_state.current_tab = "Launch Pad"
    
    apply_css()
    
    if not st.session_state.logged_in:
        login_ui()
        return
    
    username = st.session_state.username
    is_admin = st.session_state.role == "admin"
    user_data = get_user_points(username)
    
    with st.sidebar:
        st.markdown(f"""
        <div style="text-align:center; padding:12px 0;">
            <div style="font-weight:600; font-size:15px; color:#e8edf5;">{username}</div>
            <div style="font-size:10px; color:#5a5a6a;">{st.session_state.role.upper()}</div>
            <div style="margin-top:4px; display:flex; justify-content:center; gap:4px; flex-wrap:wrap;">
                <span style="background:linear-gradient(135deg,#4d6bfe,#7c3aed); color:white; padding:2px 10px; border-radius:20px; font-size:0.55rem;">Points: {user_data['points']}</span>
                <span style="background:rgba(255,255,255,0.06); color:#8a8a9a; padding:2px 10px; border-radius:20px; font-size:0.55rem;">Level: {user_data['level']}</span>
            </div>
            <div style="font-size:9px; color:#3a3a4a; margin-top:4px;">
                {' '.join(user_data['badges'][:2])}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        status = get_usage_status(username)
        percentage = status["percentage"]
        color = "green" if percentage < 70 else "orange" if percentage < 90 else "red"
        st.markdown(f"""
        <div style="background:rgba(255,255,255,0.03); border-radius:10px; padding:12px; border:1px solid rgba(255,255,255,0.04); margin-bottom:12px;">
            <div style="display:flex; justify-content:space-between;">
                <span style="color:#8a8a9a; font-size:0.7rem;">Penggunaan Bulanan</span>
                <span style="color:#e8edf5; font-size:0.7rem;">{status['used']} / {status['limit']}</span>
            </div>
            <div class="usage-progress">
                <div class="usage-progress-fill" style="background:{color}; width:{percentage}%;"></div>
            </div>
            <div style="display:flex; justify-content:space-between; font-size:0.55rem; color:#5a5a6a; margin-top:2px;">
                <span>Baki: {status['remaining']}</span>
                <span>Reset: {datetime.datetime.now().replace(day=1).strftime('%d/%m')}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        nav_items = [
            "Launch Pad", "Chat", "RPH", "Art", "Video", "Music",
            "Invois", "WhatsApp", "Neural Networks", "Roadtax",
            "IC", "Kontraktor", "Business", "Fitness", "Meditation",
            "Research", "Comic", "Game", "Analytics"
        ]
        if is_admin:
            nav_items.append("Admin")
        nav_items.append("Settings")
        
        for item in nav_items:
            if st.button(item, use_container_width=True, key=f"nav_{item}"):
                st.session_state.current_tab = item
                st.rerun()
        
        st.markdown("---")
        if st.button("Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()
    
    # === TABS ===
    if st.session_state.current_tab == "Launch Pad":
        launch_pad_ui()
    elif st.session_state.current_tab == "Chat":
        chat_ui()
    elif st.session_state.current_tab == "RPH":
        rph_ui()
    elif st.session_state.current_tab == "Art":
        art_ui()
    elif st.session_state.current_tab == "Video":
        video_ui()
    elif st.session_state.current_tab == "Music":
        music_generator_hybrid_ui()
    elif st.session_state.current_tab == "Invois":
        invoice_ui()
    elif st.session_state.current_tab == "WhatsApp":
        whatsapp_ui()
    elif st.session_state.current_tab == "Neural Networks":
        neural_ui()
    elif st.session_state.current_tab == "Roadtax":
        roadtax_ui()
    elif st.session_state.current_tab == "IC":
        ic_ui()
    elif st.session_state.current_tab == "Kontraktor":
        contractor_ui()
    elif st.session_state.current_tab == "Business":
        business_ui()
    elif st.session_state.current_tab == "Fitness":
        fitness_ui()
    elif st.session_state.current_tab == "Meditation":
        meditation_ui()
    elif st.session_state.current_tab == "Research":
        research_ui()
    elif st.session_state.current_tab == "Comic":
        comic_ui()
    elif st.session_state.current_tab == "Game":
        game_ui()
    elif st.session_state.current_tab == "Analytics":
        analytics_ui()
    elif st.session_state.current_tab == "Admin" and is_admin:
        admin_ui()
    elif st.session_state.current_tab == "Settings":
        settings_ui()
    else:
        st.info("Ciri ini sedang dibangunkan")

if __name__ == "__main__":
    main()
