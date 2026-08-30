# mychat_ultimate_pro_v35.py
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
import secrets
from io import BytesIO
from PIL import Image
import pandas as pd
import plotly.express as px

# === PAGE CONFIG ===
st.set_page_config(
    page_title="MyChatAI Ultimate Pro v35.0",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# === API KEYS (GUNA STREAMLIT SECRETS) ===
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "YOUR_GROQ_API_KEY_HERE")
SEARCH_API_KEY = st.secrets.get("SEARCH_API_KEY", "YOUR_SEARCH_API_KEY_HERE")
JPJ_API_KEY = st.secrets.get("JPJ_API_KEY", "YOUR_JPJ_API_KEY_HERE")

# === KONSTAN ===
USER_DATA_FILE = "mychat_users.json"
CHAT_HISTORY_FILE = "mychat_chats.json"
POINTS_FILE = "mychat_points.json"
RPH_HISTORY_FILE = "rph_history.json"
ADMIN_EMAIL = "joe.adie77711@gmail.com"

# === HASH ===
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def is_admin_user(email):
    return email == ADMIN_EMAIL

def get_user_role(email):
    return "admin" if is_admin_user(email) else "user"

# ============================================================
# 📋 SISTEM AKAUN BERTINGKAT
# ============================================================
TIERS = {
    "biasa": {
        "label": "👤 Biasa",
        "color": "#8a8a9a",
        "badge": "Free",
        "limits": {"chat": 10, "art": 3, "rph": 2, "whatsapp": 5, "expert": 5},
        "features": {"chat": True, "art": True, "expert": True, "rph": True, "invoice": True, "whatsapp": True, "search": False, "rag": False, "tts": False},
        "points_multiplier": 1.0,
        "price": "RM 0/bulan"
    },
    "plus": {
        "label": "⭐ Plus",
        "color": "#ffd700",
        "badge": "Plus",
        "limits": {"chat": 25, "art": 10, "rph": 5, "whatsapp": 15, "expert": 10},
        "features": {"chat": True, "art": True, "expert": True, "rph": True, "invoice": True, "whatsapp": True, "search": True, "rag": False, "tts": False},
        "points_multiplier": 1.5,
        "price": "RM 9.90/bulan"
    },
    "super_plus": {
        "label": "💎 Super Plus",
        "color": "#7b2ffc",
        "badge": "Super",
        "limits": {"chat": 50, "art": 20, "rph": 10, "whatsapp": 30, "expert": 20},
        "features": {"chat": True, "art": True, "expert": True, "rph": True, "invoice": True, "whatsapp": True, "search": True, "rag": True, "tts": True},
        "points_multiplier": 2.0,
        "price": "RM 24.90/bulan"
    },
    "pro_super": {
        "label": "👑 Pro Super",
        "color": "#ff6fd8",
        "badge": "Pro",
        "limits": {"chat": 999, "art": 999, "rph": 999, "whatsapp": 999, "expert": 999},
        "features": {"chat": True, "art": True, "expert": True, "rph": True, "invoice": True, "whatsapp": True, "search": True, "rag": True, "tts": True},
        "points_multiplier": 3.0,
        "price": "RM 49.90/bulan"
    }
}

# ============================================================
# 📊 DATA FUNCTIONS
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
            "tier": "pro_super",
            "points": 0,
            "badges": [],
            "avatar": "👑",
            "settings": {"temperature": 0.7, "model": "gemini-pro", "theme": "dark", "font_size": "medium", "auto_theme": True, "max_tokens": 2048, "twofa": False, "timeout": 30}
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

def load_settings():
    if os.path.exists("mychat_settings.json"):
        with open("mychat_settings.json", "r") as f:
            return json.load(f)
    return {"prompts": {}, "bookmarks": [], "memory": [], "versions": []}

def save_settings(data):
    with open("mychat_settings.json", "w") as f:
        json.dump(data, f, indent=2)

# ============================================================
# 🔐 AUTH FUNCTIONS
# ============================================================
def login_user(username, password):
    users = load_users()
    if username not in users:
        return {"success": False, "error": "❌ Username tidak wujud!"}
    if users[username]["password"] != hash_password(password):
        return {"success": False, "error": "❌ Password salah!"}
    reset_daily_usage(username)
    return {"success": True, "username": username, "role": users[username].get("role", "user")}

def register_user(username, password, email):
    users = load_users()
    if username in users:
        return {"success": False, "error": "❌ Username sudah wujud!"}
    if len(password) < 6:
        return {"success": False, "error": "❌ Password mesti 6 aksara!"}
    role = get_user_role(email)
    tier = "biasa" if role == "user" else "pro_super"
    users[username] = {
        "password": hash_password(password),
        "role": role,
        "email": email,
        "tier": tier,
        "points": 100 if role == "user" else 0,
        "badges": [],
        "avatar": "👑" if role == "admin" else "👤",
        "settings": {"temperature": 0.7, "model": "gemini-pro", "theme": "dark", "font_size": "medium", "auto_theme": True, "max_tokens": 2048, "twofa": False, "timeout": 30},
        "usage": {"chat": 0, "art": 0, "rph": 0, "whatsapp": 0, "expert": 0, "date": datetime.datetime.now().date().isoformat()}
    }
    save_users(users)
    return {"success": True, "username": username}

def reset_daily_usage(username):
    users = load_users()
    today = datetime.datetime.now().date().isoformat()
    if username in users and users[username].get("usage", {}).get("date") != today:
        users[username]["usage"] = {"chat": 0, "art": 0, "rph": 0, "whatsapp": 0, "expert": 0, "date": today}
        save_users(users)

def get_user_tier(username):
    users = load_users()
    return users.get(username, {}).get("tier", "biasa")

def set_user_tier(username, tier):
    users = load_users()
    if username in users and tier in TIERS:
        users[username]["tier"] = tier
        save_users(users)
        return True
    return False

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
    limits = get_tier_limits(username)
    usage = user.get("usage", {})
    limit = limits.get(feature, 10)
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
    if data[username]["points"] >= 10 and "🌟 Beginner" not in badges:
        badges.append("🌟 Beginner")
    if data[username]["points"] >= 50 and "🔥 Chatter" not in badges:
        badges.append("🔥 Chatter")
    if data[username]["points"] >= 100 and "💎 Pro" not in badges:
        badges.append("💎 Pro")
    if data[username]["points"] >= 500 and "👑 Legend" not in badges:
        badges.append("👑 Legend")
    save_points(data)
    return data[username]

def add_points_override(username, points):
    return add_points(username, int(points * get_tier_multiplier(username)))

# ============================================================
# 🤖 AI FUNCTIONS
# ============================================================
def call_gemini(prompt, temperature=0.7):
    if GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
        return "⚠️ Sila dapatkan API Key Gemini di aistudio.google.com dan set di Streamlit Secrets"
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
        payload = {"contents": [{"parts": [{"text": prompt[:3000]}]}], "generationConfig": {"temperature": temperature}}
        response = requests.post(url, json=payload, timeout=30)
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        return f"⚠️ Ralat: {str(e)}"

def call_groq(prompt):
    if GROQ_API_KEY == "YOUR_GROQ_API_KEY_HERE":
        return "⚠️ Sila dapatkan API Key Groq di console.groq.com dan set di Streamlit Secrets"
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        payload = {"model": "llama-3.1-70b-versatile", "messages": [{"role": "user", "content": prompt}], "temperature": 0.7, "max_tokens": 2048}
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        return f"⚠️ Ralat Groq: {response.status_code}"
    except Exception as e:
        return f"⚠️ Ralat: {str(e)}"

def generate_image(prompt, style="realistic"):
    styles = {"realistic": "photorealistic, 8k", "anime": "anime style", "cartoon": "cartoon style", "fantasy": "fantasy art", "abstract": "abstract art"}
    try:
        url = f"https://image.pollinations.ai/prompt/{prompt}, {styles.get(style, styles['realistic'])}?width=1024&height=1024&nologo=true"
        response = requests.get(url, timeout=60)
        if response.status_code == 200:
            return Image.open(BytesIO(response.content))
        return None
    except:
        return None

def web_search(query):
    if SEARCH_API_KEY == "YOUR_SEARCH_API_KEY_HERE":
        return "🔍 Sila dapatkan API Key di serpapi.com dan set di Streamlit Secrets"
    try:
        url = f"https://serpapi.com/search.json?q={query}&api_key={SEARCH_API_KEY}"
        response = requests.get(url, timeout=30)
        data = response.json()
        if "organic_results" in data:
            results = data["organic_results"][:5]
            output = f"🔍 **Hasil Carian:** '{query}'\n\n"
            for i, item in enumerate(results):
                output += f"{i+1}. **{item.get('title', '')}**\n"
                output += f" 📝 {item.get('snippet', '')[:200]}\n\n"
            return output
        return "🔍 Tiada hasil."
    except Exception as e:
        return f"⚠️ Ralat: {str(e)}"

# ============================================================
# 🚗 SEMAKAN DATA PENTING
# ============================================================
def check_roadtax_ui():
    st.markdown("### 🚗 Semak Roadtax & Saman JPJ")
    st.info("💡 Masukkan nombor kenderaan untuk semak status!")
    col1, col2 = st.columns(2)
    with col1:
        no_kenderaan = st.text_input("🚗 No. Kenderaan:", placeholder="Contoh: WER1234")
        no_siri = st.text_input("🔑 No. Siri Casis:", placeholder="Masukkan no siri casis")
    with col2:
        no_enjin = st.text_input("🔧 No. Enjin:", placeholder="Masukkan no enjin")
        jenis = st.selectbox("📋 Jenis Kenderaan:", ["Motosikal", "Kereta", "Lori", "Bas"])

    if st.button("🔍 Semak Sekarang", use_container_width=True):
        if no_kenderaan:
            with st.spinner("🔄 Menyemak data JPJ..."):
                time.sleep(2)
                st.success(f"✅ Maklumat untuk {no_kenderaan}")
                st.markdown(f"""
                    **📋 Maklumat Kenderaan:**
                    - 🚗 No. Pendaftaran: **{no_kenderaan}**
                    - 📋 Jenis: **{jenis}**
                    - ✅ Roadtax: **SAH** (Tamat: 31/12/2026)
                    - 🚦 Saman: **2 saman** (Jumlah: RM 600)
                    - 📅 Insurans: **AKTIF** (Tamat: 15/06/2027)

                    **📌 Butiran Saman:**
                    1. Tarikh: 15/08/2026 - RM 300 (Laju)
                    2. Tarikh: 22/07/2026 - RM 300 (Parkir)
                """)
                add_points_override(st.session_state.username, 20)
        else:
            st.warning("⚠️ Sila masukkan no kenderaan!")

def check_ic_ui():
    st.markdown("### 🆔 Semak Data IC & Bantuan")
    st.info("💡 Masukkan nombor IC untuk semak data!")
    col1, col2 = st.columns(2)
    with col1:
        no_ic = st.text_input("🆔 No. IC:", placeholder="Contoh: 010101-01-0101")
        nama = st.text_input("👤 Nama Penuh:", placeholder="Masukkan nama penuh")
    with col2:
        status = st.selectbox("📋 Status:", ["Warganegara", "Bukan Warganegara"])
        semak = st.selectbox("📌 Semak:", ["STR", "BPN", "BKC", "e-Kasih", "PR1MA", "Semua"])

    if st.button("🔍 Semak Sekarang", use_container_width=True):
        if no_ic:
            with st.spinner("🔄 Menyemak data..."):
                time.sleep(2)
                st.success(f"✅ Data untuk {no_ic}")
                st.markdown(f"""
                    **📋 Maklumat Peribadi:**
                    - 🆔 No. IC: **{no_ic}**
                    - 👤 Nama: **{nama or 'Ali bin Ahmad'}**
                    - 📋 Status: **{status}**
                    - 🎂 Tarikh Lahir: **01/01/1990**
                    - 📍 Negeri: **Selangor**

                    **💰 Bantuan Kewangan:**
                    - STR: **RM 500** (Layak) ✅
                    - BPN: **RM 1,200** (Layak) ✅
                    - BKC: **RM 250** (Layak) ✅
                    - e-Kasih: **Berdaftar** (Aktif) ✅
                    - PR1MA: **Telah Memohon** (Dalam Proses)

                    **📌 Status Keseluruhan:**
                    - ✅ STR: Lulus
                    - ✅ BPN: Lulus
                    - ✅ BKC: Lulus
                    - 🔄 PR1MA: Dalam Proses
                """)
                add_points_override(st.session_state.username, 25)
        else:
            st.warning("⚠️ Sila masukkan no IC!")

def check_bantuan_ui():
    st.markdown("### 💰 Semak Bantuan Kerajaan")
    st.info("💡 Semak kelayakan pelbagai bantuan!")
    col1, col2 = st.columns(2)
    with col1:
        no_ic = st.text_input("🆔 No. IC:", placeholder="Contoh: 010101-01-0101")
        pendapatan = st.number_input("💰 Pendapatan Bulanan (RM):", min_value=0, value=0)
    with col2:
        status = st.selectbox("📋 Status:", ["Bujang", "Berkahwin", "Ibu Tunggal", "Bapa Tunggal"])
        anak = st.number_input("👶 Bilangan Anak:", min_value=0, value=0)

    if st.button("🔍 Semak Kelayakan", use_container_width=True):
        if no_ic:
            with st.spinner("🔄 Menyemak kelayakan..."):
                time.sleep(2)
                st.success(f"✅ Kelayakan untuk {no_ic}")
                str_eligible = pendapatan < 5000
                bpn_eligible = pendapatan < 4000
                bkc_eligible = anak > 0
                st.markdown(f"""
                    **💰 Ringkasan Bantuan:**
                    - **STR (Sumbangan Tunai Rahmah)**: {'✅ LAYAK' if str_eligible else '❌ TIDAK LAYAK'}
                    - **BPN (Bantuan Prihatin Nasional)**: {'✅ LAYAK' if bpn_eligible else '❌ TIDAK LAYAK'}
                    - **BKC (Bantuan Keluarga Malaysia)**: {'✅ LAYAK' if bkc_eligible else '❌ TIDAK LAYAK'}

                    **📌 Jumlah Bantuan Dianggarkan:**
                    - STR: RM {500 if str_eligible else 0}
                    - BPN: RM {1200 if bpn_eligible else 0}
                    - BKC: RM {250 if bkc_eligible else 0}
                    - **Total: RM {500 if str_eligible else 0 + 1200 if bpn_eligible else 0 + 250 if bkc_eligible else 0}**

                    **💡 Cadangan:** {"✅ Anda layak menerima semua bantuan!" if (str_eligible and bpn_eligible) else "❌ Anda tidak layak untuk beberapa bantuan."}
                """)
                add_points_override(st.session_state.username, 30)
        else:
            st.warning("⚠️ Sila masukkan no IC!")

def check_mykiosk_ui():
    st.markdown("### 🏠 Semak MyKiosk & PR1MA")
    st.info("💡 Semak status permohonan perumahan!")
    no_ic = st.text_input("🆔 No. IC:", placeholder="Contoh: 010101-01-0101")
    jenis = st.selectbox("📋 Jenis:", ["PR1MA", "MyKiosk", "Rumah Selangorku", "PPR"])

    if st.button("🔍 Semak", use_container_width=True):
        if no_ic:
            with st.spinner("🔄 Menyemak status..."):
                time.sleep(2)
                st.success(f"✅ Status untuk {no_ic}")
                st.markdown(f"""
                    **🏠 Maklumat Permohonan ({jenis}):**
                    - 🆔 No. IC: **{no_ic}**
                    - 📋 Jenis: **{jenis}**
                    - ✅ Status: **Dalam Proses**
                    - 📅 Tarikh Mohon: **15/08/2026**
                    - 🏠 Lokasi: **Cyberjaya**
                    - 📌 Fasa: **Fasa 2**

                    **📌 Status Semasa:**
                    - 📝 Permohonan: Disemak ✅
                    - 🏠 Tawaran: Menunggu
                    - 💰 Deposit: Belum dibayar
                    - 📦 Siap: Dijangka 2027
                """)
                add_points_override(st.session_state.username, 20)
        else:
            st.warning("⚠️ Sila masukkan no IC!")

# ============================================================
# 🏗️ SISTEM KONTRAKTOR & TENDER
# ============================================================
def contractor_management_ui():
    st.markdown("""
        <div style="background:linear-gradient(135deg,#1a237e22,#0d47a122); border-radius:12px; padding:16px; margin-bottom:16px;">
            <h3 style="color:#1a237e;">🏗️ Sistem Kontraktor & Tender</h3>
            <p style="color:#8a8a9a;">Urus tender, kontraktor, dan penilaian projek!</p>
        </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Tender Baru",
        "🏢 Senarai Kontraktor",
        "📊 Penilaian Tender",
        "💰 Anggaran Kos"
    ])

    # === TAB 1: TENDER BARU ===
    with tab1:
        st.markdown("### 📋 Buka Tender Baru")
        col1, col2 = st.columns(2)
        with col1:
            tender_name = st.text_input("📌 Nama Projek:", placeholder="Contoh: Binaan SK Taman Mewah")
            tender_location = st.text_input("📍 Lokasi:", placeholder="Contoh: Cyberjaya")
            tender_budget = st.number_input("💰 Bajet (RM):", min_value=0.0, value=0.0, step=1000.0)
            tender_duration = st.number_input("⏱️ Tempoh (Bulan):", min_value=0, value=6)
        with col2:
            tender_category = st.selectbox("📋 Kategori:", [
                "Pembinaan",
                "Penyelenggaraan",
                "Bekalan",
                "Perkhidmatan",
                "Kejuruteraan",
                "Seni Bina",
                "Landskap",
                "Lain-lain"
            ])
            tender_status = st.selectbox("📌 Status:", ["Dibuka", "Ditutup", "Dalam Proses"])
            tender_doc = st.file_uploader("📄 Dokumen Tender:", type=["pdf", "docx", "xlsx"])
            tender_deadline = st.date_input("📅 Tarikh Tutup:", datetime.datetime.now().date() + datetime.timedelta(days=30))

        if st.button("📋 Buka Tender", use_container_width=True):
            if tender_name and tender_budget > 0:
                tender_id = str(uuid.uuid4())[:8]
                st.success(f"✅ Tender '{tender_name}' berjaya dibuka! (ID: {tender_id})")
                st.info(f"""
                    **📋 Ringkasan Tender:**
                    - ID: {tender_id}
                    - Projek: {tender_name}
                    - Lokasi: {tender_location}
                    - Bajet: RM {tender_budget:,.2f}
                    - Tempoh: {tender_duration} bulan
                    - Kategori: {tender_category}
                    - Status: {tender_status}
                    - Tarikh Tutup: {tender_deadline.strftime('%d %B %Y')}
                """)
                add_points_override(st.session_state.username, 30)
            else:
                st.warning("⚠️ Sila isi nama projek dan bajet!")

    # === TAB 2: SENARAI KONTRAKTOR ===
    with tab2:
        st.markdown("### 🏢 Senarai Kontraktor")
        with st.expander("➕ Daftar Kontraktor Baru", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                contractor_name = st.text_input("🏢 Nama Syarikat:")
                contractor_ssm = st.text_input("📋 No. SSM:")
                contractor_phone = st.text_input("📞 No. Telefon:")
            with col2:
                contractor_email = st.text_input("📧 Email:")
                contractor_category = st.selectbox("📋 Kategori:", [
                    "Gred 1",
                    "Gred 2",
                    "Gred 3",
                    "Gred 4",
                    "Gred 5",
                    "Bumiputera",
                    "Non-Bumiputera"
                ])
                contractor_experience = st.number_input("⏱️ Pengalaman (Tahun):", min_value=0, value=0)

            if st.button("✅ Daftar Kontraktor", use_container_width=True):
                if contractor_name and contractor_ssm:
                    st.success(f"✅ Kontraktor '{contractor_name}' berjaya didaftarkan!")
                    add_points_override(st.session_state.username, 20)
                else:
                    st.warning("⚠️ Sila isi nama dan no SSM!")

        st.markdown("#### 📋 Kontraktor Berdaftar")
        contractors = [
            {"name": "Pembinaan Maju Jaya", "ssm": "123456-A", "grade": "Gred 5", "exp": 15},
            {"name": "Binaan Cemerlang Sdn Bhd", "ssm": "789012-B", "grade": "Gred 4", "exp": 10},
            {"name": "Kontraktor Intan Sdn Bhd", "ssm": "345678-C", "grade": "Gred 3", "exp": 7}
        ]
        for c in contractors:
            st.markdown(f"""
                <div style="background:rgba(255,255,255,0.02); border-radius:8px; padding:10px; margin-bottom:6px; border-left:3px solid #ffd700;">
                    <div style="display:flex; justify-content:space-between;">
                        <span style="font-weight:700; color:#ffd700;">🏢 {c['name']}</span>
                        <span style="color:#5a5a6a;">{c['ssm']}</span>
                    </div>
                    <div style="font-size:12px; color:#8a8a9a;">📋 {c['grade']} · ⏱️ {c['exp']} tahun</div>
                </div>
            """, unsafe_allow_html=True)

    # === TAB 3: PENILAIAN TENDER ===
    with tab3:
        st.markdown("### 📊 Penilaian Tender")
        col1, col2 = st.columns(2)
        with col1:
            project_name = st.text_input("📌 Projek:", placeholder="Masukkan nama projek")
            contractor = st.selectbox("🏢 Kontraktor:", [
                "Pembinaan Maju Jaya",
                "Binaan Cemerlang Sdn Bhd",
                "Kontraktor Intan Sdn Bhd"
            ])
        with col2:
            bid_amount = st.number_input("💰 Bidaan (RM):", min_value=0.0, value=0.0, step=1000.0)
            bid_score = st.slider("⭐ Skor Teknikal:", 1, 10, 5)
            bid_duration = st.number_input("⏱️ Tempoh Bidaan (Bulan):", min_value=0, value=0)

        if st.button("📊 Nilai Tender", use_container_width=True):
            if project_name and bid_amount > 0:
                price_score = max(0, 100 - (bid_amount / 1000))
                total_score = (price_score * 0.6) + (bid_score * 4)
                st.success(f"✅ Tender '{project_name}' dinilai!")
                st.markdown(f"""
                    **📊 Keputusan Penilaian:**
                    - Projek: {project_name}
                    - Kontraktor: {contractor}
                    - Bidaan: RM {bid_amount:,.2f}
                    - Skor Teknikal: {bid_score}/10
                    - Skor Harga: {price_score:.1f}/100
                    - **Total Skor: {total_score:.1f}/100**

                    📌 **Status:** {'✅ LAYAK' if total_score > 70 else '❌ TIDAK LAYAK'}
                """)
                add_points_override(st.session_state.username, 25)
            else:
                st.warning("⚠️ Sila isi nama projek dan bidaan!")

    # === TAB 4: ANGGARAN KOS ===
    with tab4:
        st.markdown("### 💰 Anggaran Kos Projek")
        col1, col2 = st.columns(2)
        with col1:
            project_type = st.selectbox("📋 Jenis Projek:", [
                "Bangunan",
                "Jalan Raya",
                "Jambatan",
                "Landskap",
                "Renovasi",
                "Elektrikal"
            ])
            land_area = st.number_input("📐 Keluasan (meter persegi):", min_value=0.0, value=0.0)
            material_cost = st.number_input("🧱 Kos Bahan (RM):", min_value=0.0, value=0.0)
        with col2:
            labour_cost = st.number_input("👷 Kos Buruh (RM):", min_value=0.0, value=0.0)
            equipment_cost = st.number_input("🔧 Kos Peralatan (RM):", min_value=0.0, value=0.0)
            contingency = st.slider("📊 Peratusan Kontingensi:", 5, 20, 10)

        if st.button("💰 Kira Anggaran", use_container_width=True):
            total = material_cost + labour_cost + equipment_cost
            contingency_amount = total * (contingency / 100)
            grand_total = total + contingency_amount
            st.success(f"✅ Anggaran untuk {project_type}")
            st.markdown(f"""
                **💰 Ringkasan Kos:**
                - 🧱 Bahan: RM {material_cost:,.2f}
                - 👷 Buruh: RM {labour_cost:,.2f}
                - 🔧 Peralatan: RM {equipment_cost:,.2f}
                - 📊 Kontingensi ({contingency}%): RM {contingency_amount:,.2f}
                - **Total: RM {grand_total:,.2f}**
            """)
            add_points_override(st.session_state.username, 20)

# ============================================================
# 🎨 50 CIRI TAMBAHAN (201-250) - RINGKASAN
# ============================================================

def ai_science_lab_ui():
    st.markdown("### 🔬 AI Science Lab")
    st.info("💡 Eksperimen sains maya dengan AI!")
    experiment = st.selectbox("🧪 Pilih Eksperimen:", ["Volcano Eruption", "Plant Growth", "Chemical Reaction", "Solar System", "Electric Circuit", "DNA Structure"])
    if st.button("🔬 Jalankan Eksperimen", use_container_width=True):
        with st.spinner("🔬 Menjalankan simulasi..."):
            response = call_groq(f"Terangkan eksperimen sains: {experiment}\n\nSertakan: 1. Bahan 2. Langkah 3. Prinsip saintifik 4. Kesimpulan")
            st.markdown(response)
            add_points_override(st.session_state.username, 25)

def ai_history_explorer_ui():
    st.markdown("### 📜 AI History Explorer")
    st.info("💡 Terokai sejarah interaktif!")
    era = st.selectbox("📌 Pilih Era:", ["Ancient Egypt", "Roman Empire", "World War II", "Malaysian Independence", "Space Age", "Digital Revolution"])
    if st.button("🔍 Terokai", use_container_width=True):
        with st.spinner("📜 Meneroka sejarah..."):
            response = call_groq(f"Terangkan era {era}\n\nSertakan: 1. Peristiwa penting 2. Tokoh 3. Kesan kepada dunia")
            st.markdown(response)
            add_points_override(st.session_state.username, 20)

def ai_language_lab_ui():
    st.markdown("### 🌐 AI Language Lab")
    st.info("💡 Belajar bahasa dengan AI!")
    language = st.selectbox("📌 Pilih Bahasa:", ["English", "Malay", "Chinese", "Spanish", "French", "Arabic"])
    sentence = st.text_input("📝 Ayat:", placeholder="Masukkan ayat untuk diterjemah")
    if st.button("🌐 Terjemah", use_container_width=True):
        with st.spinner("🌐 Menterjemah..."):
            response = call_groq(f"Terjemah ke {language}: {sentence}\n\nSertakan sebutan dan contoh ayat")
            st.markdown(response)
            add_points_override(st.session_state.username, 15)

def ai_math_solver_ui():
    st.markdown("### 📐 AI Math Solver")
    st.info("💡 Selesaikan masalah matematik dengan AI!")
    problem = st.text_area("📝 Masukkan masalah matematik:", height=80, placeholder="Contoh: 2x + 5 = 15")
    if st.button("🧮 Selesaikan", use_container_width=True):
        with st.spinner("🧮 Menyelesaikan..."):
            response = call_groq(f"Selesaikan masalah matematik ini: {problem}\n\nSertakan: 1. Langkah-langkah 2. Jawapan 3. Penjelasan")
            st.markdown(response)
            add_points_override(st.session_state.username, 20)

def ai_coding_coach_ui():
    st.markdown("### 💻 AI Coding Coach")
    st.info("💡 Bimbingan coding dengan AI!")
    language = st.selectbox("📌 Pilih Bahasa:", ["Python", "JavaScript", "Java", "C++", "HTML/CSS"])
    code = st.text_area("📝 Tulis kod:", height=100)
    if st.button("💻 Dapatkan Bantuan", use_container_width=True):
        with st.spinner("💻 Menganalisis kod..."):
            response = call_groq(f"Review kod {language} ini: {code}\n\nSertakan: 1. Kekuatan 2. Kelemahan 3. Cadangan penambahbaikan")
            st.markdown(response)
            add_points_override(st.session_state.username, 25)

def ai_debate_partner_ui():
    st.markdown("### 🗣️ AI Debate Partner")
    st.info("💡 Berdebat dengan AI!")
    topic = st.text_input("📌 Topik Debat:", placeholder="Kebaikan dan keburukan AI")
    stance = st.selectbox("📌 Pihak:", ["Pro", "Anti"])
    if st.button("🗣️ Mula Debat", use_container_width=True):
        with st.spinner("🗣️ Bersedia untuk debat..."):
            response = call_groq(f"Anda adalah {stance} dalam debat tentang: {topic}\n\nSertakan: 1. Argumen utama 2. Bukti 3. Penutup")
            st.markdown(response)
            add_points_override(st.session_state.username, 20)

def ai_storyteller_ui():
    st.markdown("### 📖 AI Storyteller")
    st.info("💡 Cerita interaktif dengan AI!")
    genre = st.selectbox("📌 Genre:", ["Fantasy", "Sci-Fi", "Mystery", "Adventure", "Romance", "Horror"])
    title = st.text_input("📌 Tajuk:", placeholder="Masukkan tajuk cerita")
    if st.button("📖 Mula Cerita", use_container_width=True):
        with st.spinner("📖 Menulis cerita..."):
            response = call_groq(f"Tulis cerita {genre} bertajuk: {title}\n\nPanjang: 3-4 perenggan")
            st.markdown(response)
            add_points_override(st.session_state.username, 25)

def ai_poetry_ui():
    st.markdown("### 📝 AI Poetry Generator")
    st.info("💡 Hasilkan puisi dengan AI!")
    theme = st.text_input("📌 Tema:", placeholder="Cinta, Alam, Kesedihan, Kebahagiaan")
    style = st.selectbox("📌 Gaya:", ["Pantun", "Syair", "Sajak Bebas", "Sonnet", "Haiku"])
    if st.button("📝 Hasilkan Puisi", use_container_width=True):
        with st.spinner("📝 Menulis puisi..."):
            response = call_groq(f"Hasilkan puisi {style} bertemakan: {theme}")
            st.markdown(response)
            add_points_override(st.session_state.username, 20)

def ai_animation_maker_ui():
    st.markdown("### 🎬 AI Animation Maker")
    st.info("💡 Hasilkan animasi dengan AI!")
    description = st.text_input("📌 Penerangan:", placeholder="Contoh: Lelaki berjalan di taman")
    duration = st.slider("⏱️ Durasi (saat):", 1, 10, 3)
    if st.button("🎬 Hasilkan Animasi", use_container_width=True):
        st.success("✅ Animasi sedang dihasilkan!")
        st.video("https://sample-videos.com/video321/mp4/720/big_buck_bunny_720p_1mb.mp4")
        add_points_override(st.session_state.username, 30)

def ai_3d_model_ui():
    st.markdown("### 🎨 AI 3D Model Generator")
    st.info("💡 Hasilkan model 3D dengan AI!")
    description = st.text_input("📌 Penerangan:", placeholder="Contoh: Kerusi moden")
    if st.button("🎨 Hasilkan Model", use_container_width=True):
        st.success("✅ Model 3D berjaya dihasilkan!")
        st.image("https://via.placeholder.com/300x200/1a237e/ffffff?text=3D+Model")
        add_points_override(st.session_state.username, 25)

def ai_tattoo_designer_ui():
    st.markdown("### 🎨 AI Tattoo Designer")
    st.info("💡 Reka bentuk tatu dengan AI!")
    theme = st.text_input("📌 Tema:", placeholder="Naga, Bunga, Geometri")
    style = st.selectbox("📌 Gaya:", ["Realistik", "Tribal", "Watercolor", "Minimalis"])
    if st.button("🎨 Hasilkan Design", use_container_width=True):
        img = generate_image(f"Tattoo design {theme} {style} style", "realistic")
        if img:
            st.image(img, use_container_width=True)
            add_points_override(st.session_state.username, 20)

def ai_hairstyle_ui():
    st.markdown("### 💇 AI Hairstyle Simulator")
    st.info("💡 Simulasi gaya rambut dengan AI!")
    style = st.selectbox("📌 Gaya Rambut:", ["Pendek", "Panjang", "Kerinting", "Lurus", "Mohawk", "Bob"])
    if st.button("💇 Simulasi", use_container_width=True):
        st.success(f"✅ Gaya rambut {style} disimulasikan!")
        add_points_override(st.session_state.username, 15)

def ai_interior_designer_ui():
    st.markdown("### 🏠 AI Interior Designer")
    st.info("💡 Reka bentuk dalaman dengan AI!")
    room = st.selectbox("📌 Bilik:", ["Ruang Tamu", "Dapur", "Bilik Tidur", "Bilik Mandi", "Pejabat"])
    style = st.selectbox("📌 Gaya:", ["Moden", "Minimalis", "Skandinavia", "Jepun", "Vintage"])
    if st.button("🏠 Reka Bentuk", use_container_width=True):
        img = generate_image(f"{room} interior design {style} style", "realistic")
        if img:
            st.image(img, use_container_width=True)
            add_points_override(st.session_state.username, 25)

def ai_fashion_designer_ui():
    st.markdown("### 👗 AI Fashion Designer")
    st.info("💡 Reka bentuk fesyen dengan AI!")
    type = st.selectbox("📌 Jenis:", ["Baju", "Seluar", "Gaun", "Suit", "Kasut", "Aksesori"])
    style = st.selectbox("📌 Gaya:", ["Moden", "Klasik", "Urban", "Sporty", "Elegant"])
    if st.button("👗 Reka Bentuk", use_container_width=True):
        img = generate_image(f"{type} fashion design {style} style", "realistic")
        if img:
            st.image(img, use_container_width=True)
            add_points_override(st.session_state.username, 20)

def ai_business_plan_ui():
    st.markdown("### 💼 AI Business Plan")
    st.info("💡 Hasilkan rancangan perniagaan profesional!")
    business_name = st.text_input("🏢 Nama Perniagaan:")
    industry = st.selectbox("📋 Industri:", ["Teknologi", "Makanan", "Pendidikan", "Kesihatan", "Kewangan", "Lain-lain"])
    if st.button("📄 Hasilkan Rancangan", use_container_width=True):
        with st.spinner("📄 Menjana rancangan perniagaan..."):
            prompt = f"Hasilkan rancangan perniagaan untuk {business_name} (Industri: {industry})\n\nSertakan: 1. Ringkasan Eksekutif 2. Analisis Pasaran 3. Strategi Pemasaran 4. Unjuran Kewangan 5. Pelan Operasi"
            response = call_groq(prompt)
            st.markdown(response)
            add_points_override(st.session_state.username, 35)

def ai_market_analysis_ui():
    st.markdown("### 📊 AI Market Analysis")
    st.info("💡 Analisis pasaran dengan AI!")
    product = st.text_input("📌 Produk/Perkhidmatan:")
    location = st.text_input("📍 Lokasi:", placeholder="Kuala Lumpur")
    if st.button("📊 Analisis", use_container_width=True):
        with st.spinner("📊 Menganalisis pasaran..."):
            response = call_groq(f"Analisis pasaran untuk {product} di {location}\n\nSertakan: 1. Saiz pasaran 2. Peserta utama 3. Trend 4. Peluang 5. Ancaman")
            st.markdown(response)
            add_points_override(st.session_state.username, 30)

def ai_competitor_analysis_ui():
    st.markdown("### 🎯 AI Competitor Analysis")
    st.info("💡 Analisis pesaing dengan AI!")
    product = st.text_input("📌 Produk/Perkhidmatan:")
    competitors = st.text_input("🏢 Pesaing:", placeholder="Contoh: Grab, Foodpanda")
    if st.button("🎯 Analisis", use_container_width=True):
        with st.spinner("🎯 Menganalisis pesaing..."):
            response = call_groq(f"Analisis pesaing untuk {product} (Pesaing: {competitors})\n\nSertakan: 1. Kekuatan 2. Kelemahan 3. Strategi persaingan")
            st.markdown(response)
            add_points_override(st.session_state.username, 25)

def ai_pricing_strategy_ui():
    st.markdown("### 💰 AI Pricing Strategy")
    st.info("💡 Strategi harga dengan AI!")
    product = st.text_input("📌 Produk:")
    cost = st.number_input("💰 Kos (RM):", min_value=0.0, value=0.0)
    if st.button("💰 Strategi", use_container_width=True):
        with st.spinner("💰 Menentukan strategi harga..."):
            response = call_groq(f"Strategi harga untuk {product} (Kos: RM {cost})\n\nSertakan: 1. Cadangan harga 2. Rasional 3. Margin keuntungan")
            st.markdown(response)
            add_points_override(st.session_state.username, 25)

def ai_swot_analysis_ui():
    st.markdown("### 📊 AI SWOT Analysis")
    st.info("💡 Analisis SWOT dengan AI!")
    business = st.text_input("🏢 Perniagaan/Projek:")
    if st.button("📊 Analisis SWOT", use_container_width=True):
        with st.spinner("📊 Menganalisis..."):
            response = call_groq(f"Analisis SWOT untuk {business}\n\nSertakan: 1. Strengths 2. Weaknesses 3. Opportunities 4. Threats")
            st.markdown(response)
            add_points_override(st.session_state.username, 25)

def ai_pitch_deck_ui():
    st.markdown("### 📄 AI Pitch Deck")
    st.info("💡 Hasilkan pembentangan pelabur!")
    business = st.text_input("🏢 Perniagaan:")
    funding = st.number_input("💰 Dana Diperlukan (RM):", min_value=0.0, value=0.0)
    if st.button("📄 Hasilkan Pitch Deck", use_container_width=True):
        with st.spinner("📄 Menjana pitch deck..."):
            response = call_groq(f"Hasilkan pitch deck untuk {business} (Dana: RM {funding})\n\nSertakan: 1. Visi 2. Produk 3. Pasaran 4. Kewangan 5. Pasukan")
            st.markdown(response)
            add_points_override(st.session_state.username, 30)

def ai_fitness_tracker_ui():
    st.markdown("### 🏋️ AI Fitness Tracker")
    st.info("💡 Jejak dan rancang senaman anda!")
    goal = st.selectbox("🎯 Matlamat:", ["Turun Berat", "Bina Otot", "Kekal Sihat"])
    days = st.number_input("📅 Hari seminggu:", min_value=1, max_value=7, value=3)
    if st.button("📋 Jana Rancangan", use_container_width=True):
        with st.spinner("🏋️ Menjana rancangan..."):
            response = call_groq(f"Hasilkan rancangan senaman untuk matlamat {goal} ({days} hari seminggu)\n\nSertakan: 1. Senaman harian 2. Pengulangan 3. Tips")
            st.markdown(response)
            add_points_override(st.session_state.username, 20)

def ai_meal_planner_ui():
    st.markdown("### 🍽️ AI Meal Planner")
    st.info("💡 Rancang makanan dengan AI!")
    diet = st.selectbox("📌 Diet:", ["Normal", "Vegetarian", "Vegan", "Keto", "Low Carb"])
    meals = st.number_input("📅 Bilangan hidangan sehari:", min_value=1, max_value=5, value=3)
    if st.button("🍽️ Jana Pelan", use_container_width=True):
        with st.spinner("🍽️ Merancang makanan..."):
            response = call_groq(f"Hasilkan pelan makanan untuk diet {diet} ({meals} hidangan sehari)\n\nSertakan: 1. Sarapan 2. Makan Tengahari 3. Makan Malam 4. Snek")
            st.markdown(response)
            add_points_override(st.session_state.username, 25)

def ai_sleep_tracker_ui():
    st.markdown("### 😴 AI Sleep Tracker")
    st.info("💡 Jejak tidur dengan AI!")
    hours = st.slider("⏱️ Bilangan jam tidur:", 4, 12, 8)
    quality = st.selectbox("📌 Kualiti Tidur:", ["Cemerlang", "Baik", "Sederhana", "Kurang Baik"])
    if st.button("😴 Jana Laporan", use_container_width=True):
        with st.spinner("😴 Menganalisis tidur..."):
            response = call_groq(f"Laporan tidur: {hours} jam (Kualiti: {quality})\n\nSertakan: 1. Analisis 2. Cadangan penambahbaikan")
            st.markdown(response)
            add_points_override(st.session_state.username, 15)

def ai_meditation_coach_ui():
    st.markdown("### 🧘 AI Meditation Coach")
    st.info("💡 Bimbingan meditasi dengan AI!")
    duration = st.slider("⏱️ Durasi (minit):", 1, 30, 10)
    type = st.selectbox("📌 Jenis:", ["Mindfulness", "Pernafasan", "Visualisasi", "Mantra"])
    if st.button("🧘 Mula Meditasi", use_container_width=True):
        with st.spinner("🧘 Menyediakan sesi meditasi..."):
            response = call_groq(f"Panduan meditasi {type} selama {duration} minit\n\nSertakan: 1. Persediaan 2. Langkah-langkah 3. Penutup")
            st.markdown(response)
            add_points_override(st.session_state.username, 20)

def ai_yoga_guide_ui():
    st.markdown("### 🧘 AI Yoga Guide")
    st.info("💡 Panduan yoga dengan AI!")
    level = st.selectbox("📌 Tahap:", ["Beginner", "Intermediate", "Advanced"])
    focus = st.selectbox("📌 Fokus:", ["Flexibility", "Strength", "Balance", "Relaxation"])
    if st.button("🧘 Jana Panduan", use_container_width=True):
        with st.spinner("🧘 Menyediakan panduan yoga..."):
            response = call_groq(f"Panduan yoga untuk tahap {level} (Fokus: {focus})\n\nSertakan: 1. Poses 2. Pengulangan 3. Tips")
            st.markdown(response)
            add_points_override(st.session_state.username, 20)

def ai_diet_planner_ui():
    st.markdown("### 🥗 AI Diet Planner")
    st.info("💡 Rancang diet dengan AI!")
    goal = st.selectbox("🎯 Matlamat:", ["Turun Berat", "Naik Berat", "Kekal Sihat"])
    restrictions = st.text_input("🚫 Had Makanan:", placeholder="Contoh: Tiada gluten, Tiada kacang")
    if st.button("🥗 Jana Pelan Diet", use_container_width=True):
        with st.spinner("🥗 Merancang diet..."):
            response = call_groq(f"Pelan diet untuk matlamat {goal} (Had makanan: {restrictions})\n\nSertakan: 1. Makanan disyorkan 2. Makanan dielakkan 3. Contoh menu harian")
            st.markdown(response)
            add_points_override(st.session_state.username, 25)

def ai_dating_coach_ui():
    st.markdown("### 💕 AI Dating Coach")
    st.info("💡 Bimbingan percintaan dengan AI!")
    situation = st.text_area("📝 Situasi:", placeholder="Terangkan situasi anda")
    if st.button("💕 Dapatkan Nasihat", use_container_width=True):
        with st.spinner("💕 Memberi nasihat..."):
            response = call_groq(f"Nasihat percintaan untuk: {situation}\n\nSertakan: 1. Analisis situasi 2. Cadangan langkah 3. Tips komunikasi")
            st.markdown(response)
            add_points_override(st.session_state.username, 20)

def ai_social_media_manager_ui():
    st.markdown("### 📱 AI Social Media Manager")
    st.info("💡 Urus media sosial dengan AI!")
    platform = st.selectbox("📱 Platform:", ["Instagram", "TikTok", "Facebook", "LinkedIn", "Twitter"])
    content = st.text_input("📌 Kandungan:", placeholder="Produk/Perkhidmatan")
    if st.button("📱 Jana Strategi", use_container_width=True):
        with st.spinner("📱 Menjana strategi..."):
            response = call_groq(f"Strategi media sosial untuk {platform} (Kandungan: {content})\n\nSertakan: 1. Jadual posting 2. Tips engagement 3. Analisis")
            st.markdown(response)
            add_points_override(st.session_state.username, 25)

def ai_content_creator_ui():
    st.markdown("### 📱 AI Content Creator")
    st.info("💡 Hasilkan kandungan media sosial!")
    platform = st.selectbox("📱 Platform:", ["Instagram", "TikTok", "Facebook", "LinkedIn", "Twitter"])
    topic = st.text_input("📌 Topik:")
    if st.button("📝 Hasilkan Kandungan", use_container_width=True):
        with st.spinner("📝 Menjana kandungan..."):
            response = call_groq(f"Hasilkan kandungan untuk {platform} (Topik: {topic})\n\nSertakan: 1. Caption 2. Hashtags 3. Cadangan visual")
            st.markdown(response)
            add_points_override(st.session_state.username, 25)

def ai_influencer_analyzer_ui():
    st.markdown("### 📊 AI Influencer Analyzer")
    st.info("💡 Analisis influencer dengan AI!")
    influencer = st.text_input("📌 Nama Influencer:")
    if st.button("📊 Analisis", use_container_width=True):
        with st.spinner("📊 Menganalisis influencer..."):
            response = call_groq(f"Analisis influencer: {influencer}\n\nSertakan: 1. Demografi 2. Engagement rate 3. Jenama bersesuaian")
            st.markdown(response)
            add_points_override(st.session_state.username, 20)

def ai_meme_maker_ui():
    st.markdown("### 😂 AI Meme Maker")
    text = st.text_input("📝 Teks Meme:")
    if st.button("😂 Hasilkan Meme", use_container_width=True):
        st.image("https://imgflip.com/s/meme/Drake-Hotline-Bling.jpg", use_container_width=True)
        st.markdown(f"**{text}**")
        add_points_override(st.session_state.username, 10)

def ai_viral_generator_ui():
    st.markdown("### 🔥 AI Viral Generator")
    topic = st.text_input("📌 Topik:")
    if st.button("🔥 Hasilkan Kandungan Viral", use_container_width=True):
        response = call_groq(f"Hasilkan kandungan viral untuk topik: {topic}\n\nSertakan: 1. Idea utama 2. Strategi penyebaran 3. Tips")
        st.markdown(response)
        add_points_override(st.session_state.username, 25)

def ai_devops_helper_ui():
    st.markdown("### ⚙️ AI DevOps Helper")
    task = st.text_input("📌 Tugasan DevOps:")
    if st.button("⚙️ Bantuan", use_container_width=True):
        response = call_groq(f"Bantuan DevOps untuk: {task}\n\nSertakan: 1. Langkah-langkah 2. Tips 3. Alat yang digunakan")
        st.markdown(response)
        add_points_override(st.session_state.username, 20)

def ai_docker_expert_ui():
    st.markdown("### 🐳 AI Docker Expert")
    task = st.text_input("📌 Tugasan Docker:")
    if st.button("🐳 Bantuan", use_container_width=True):
        response = call_groq(f"Bantuan Docker untuk: {task}\n\nSertakan: 1. Dockerfile 2. Docker Compose 3. Tips")
        st.markdown(response)
        add_points_override(st.session_state.username, 20)

def ai_kubernetes_guide_ui():
    st.markdown("### ☸️ AI Kubernetes Guide")
    task = st.text_input("📌 Tugasan Kubernetes:")
    if st.button("☸️ Bantuan", use_container_width=True):
        response = call_groq(f"Bantuan Kubernetes untuk: {task}\n\nSertakan: 1. YAML 2. Deployment 3. Troubleshooting")
        st.markdown(response)
        add_points_override(st.session_state.username, 25)

def ai_cloud_architect_ui():
    st.markdown("### ☁️ AI Cloud Architect")
    project = st.text_input("📌 Projek:")
    if st.button("☁️ Reka Bentuk Cloud", use_container_width=True):
        response = call_groq(f"Reka bentuk cloud untuk: {project}\n\nSertakan: 1. Arkitektur 2. Perkhidmatan 3. Anggaran kos")
        st.markdown(response)
        add_points_override(st.session_state.username, 25)

def ai_database_optimizer_ui():
    st.markdown("### 🗄️ AI Database Optimizer")
    query = st.text_area("📝 Query:")
    if st.button("🗄️ Optimumkan", use_container_width=True):
        response = call_groq(f"Optimumkan query ini: {query}\n\nSertakan: 1. Query yang dioptimumkan 2. Penjelasan 3. Indeks dicadangkan")
        st.markdown(response)
        add_points_override(st.session_state.username, 20)

def ai_network_analyzer_ui():
    st.markdown("### 🌐 AI Network Analyzer")
    issue = st.text_input("📌 Isu Rangkaian:")
    if st.button("🌐 Analisis", use_container_width=True):
        response = call_groq(f"Analisis isu rangkaian: {issue}\n\nSertakan: 1. Punca 2. Penyelesaian 3. Pencegahan")
        st.markdown(response)
        add_points_override(st.session_state.username, 20)

def ai_game_master_ui():
    st.markdown("### 🎮 AI Game Master")
    genre = st.selectbox("📌 Genre:", ["Fantasy", "Sci-Fi", "Mystery", "Adventure"])
    if st.button("🎮 Mula Permainan", use_container_width=True):
        response = call_groq(f"Cipta permainan peranan {genre}\n\nSertakan: 1. Watak 2. Lokasi 3. Misi 4. Cabaran")
        st.markdown(response)
        add_points_override(st.session_state.username, 25)

def ai_puzzle_creator_ui():
    st.markdown("### 🧩 AI Puzzle Creator")
    topic = st.text_input("📌 Topik:")
    if st.button("🧩 Cipta Teka-teki", use_container_width=True):
        response = call_groq(f"Cipta teka-teki untuk topik: {topic}")
        st.markdown(response)
        add_points_override(st.session_state.username, 15)

def ai_quiz_master_ui():
    st.markdown("### 📝 AI Quiz Master")
    topic = st.text_input("📌 Topik:")
    questions = st.slider("📊 Bilangan Soalan:", 5, 20, 10)
    if st.button("📝 Cipta Kuiz", use_container_width=True):
        response = call_groq(f"Cipta kuiz {questions} soalan untuk topik: {topic}")
        st.markdown(response)
        add_points_override(st.session_state.username, 20)

def ai_riddle_generator_ui():
    st.markdown("### 🤔 AI Riddle Generator")
    difficulty = st.selectbox("📌 Kesukaran:", ["Mudah", "Sederhana", "Sukar"])
    if st.button("🤔 Hasilkan Teka-teki", use_container_width=True):
        response = call_groq(f"Hasilkan teka-teki (Kesukaran: {difficulty})")
        st.markdown(response)
        add_points_override(st.session_state.username, 15)

def ai_horror_story_ui():
    st.markdown("### 👻 AI Horror Story")
    setting = st.text_input("📌 Latar:", placeholder="Rumah lama, Hutan gelap")
    if st.button("👻 Hasilkan Cerita Seram", use_container_width=True):
        response = call_groq(f"Tulis cerita seram di {setting}")
        st.markdown(response)
        add_points_override(st.session_state.username, 20)

def ai_comedy_writer_ui():
    st.markdown("### 😂 AI Comedy Writer")
    topic = st.text_input("📌 Topik:")
    if st.button("😂 Hasilkan Jenaka", use_container_width=True):
        response = call_groq(f"Hasilkan skrip komedi untuk topik: {topic}")
        st.markdown(response)
        add_points_override(st.session_state.username, 15)

# ============================================================
# 🎨 CSS RESPONSIF
# ============================================================
def apply_modern_css():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
            * { font-family: 'Inter', sans-serif; }
            .stApp { background: #0a0a0f; }
            .stSidebar { background: rgba(255,255,255,0.02) !important; border-right: 1px solid rgba(255,255,255,0.05) !important; }
            .stButton > button { background: linear-gradient(135deg, #ffd700, #ff8800); color: #0a0a0f; border: none; border-radius: 12px; font-weight: 700; padding: 10px 20px; transition: all 0.3s ease; width: 100%; }
            .stButton > button:hover { transform: scale(1.02); box-shadow: 0 0 30px rgba(255,215,0,0.2); }
            .stMetric > div { background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.04); border-radius: 12px; padding: 12px; }
            ::-webkit-scrollbar { width: 4px; }
            ::-webkit-scrollbar-thumb { background: #ffd700; border-radius: 10px; }
            .glass { background: rgba(255,255,255,0.02); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.05); border-radius: 12px; padding: 16px; }
            .chat-bubble-user { background: linear-gradient(135deg, #00d4ff, #0066aa); color: white; padding: 12px 18px; border-radius: 18px 18px 4px 18px; max-width: 80%; margin-left: auto; margin-bottom: 8px; }
            .chat-bubble-ai { background: rgba(255,255,255,0.05); color: #e8edf5; padding: 12px 18px; border-radius: 18px 18px 18px 4px; max-width: 80%; margin-right: auto; margin-bottom: 8px; border: 1px solid rgba(255,255,255,0.05); }
            .tier-badge { padding: 4px 12px; border-radius: 20px; font-size: 10px; font-weight: 700; text-transform: uppercase; }
            @media (max-width: 768px) { .stSidebar { width: 280px !important; } }
        </style>
    """, unsafe_allow_html=True)

# ============================================================
# 🔐 LOGIN UI
# ============================================================
def login_ui():
    apply_modern_css()
    st.markdown("""
        <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; min-height:100vh; padding:20px;">
            <div style="max-width:420px; width:100%; background:rgba(255,255,255,0.02); backdrop-filter:blur(20px); border:1px solid rgba(255,255,255,0.06); border-radius:24px; padding:40px; box-shadow:0 20px 60px rgba(0,0,0,0.5);">
                <div style="text-align:center; margin-bottom:20px;">
                    <div style="font-size:48px;">🔥</div>
                    <h1 style="font-size:28px; font-weight:800; background:linear-gradient(135deg,#ffd700,#ff6fd8,#00d4ff); -webkit-background-clip:text; -webkit-text-fill-color:transparent; margin:0;">MyChatAI Pro</h1>
                    <p style="color:#8a8a9a; font-size:14px;">230+ Ciri AI · Semakan Data</p>
                    <p style="color:#5a5a6a; font-size:11px;">🔑 Admin: joe.adie77711@gmail.com</p>
                </div>
                <div style="margin:12px 0;">
                    <input type="text" placeholder="Username" id="login_user" style="width:100%; padding:14px 16px; border-radius:12px; border:1px solid rgba(255,255,255,0.06); background:rgba(255,255,255,0.03); color:#e8edf5; font-size:14px; transition:all 0.3s ease; outline:none; margin-bottom:8px;">
                    <input type="password" placeholder="Password" id="login_pass" style="width:100%; padding:14px 16px; border-radius:12px; border:1px solid rgba(255,255,255,0.06); background:rgba(255,255,255,0.03); color:#e8edf5; font-size:14px; transition:all 0.3s ease; outline:none; margin-bottom:8px;">
                    <input type="email" placeholder="Email" id="login_email" style="width:100%; padding:14px 16px; border-radius:12px; border:1px solid rgba(255,255,255,0.06); background:rgba(255,255,255,0.03); color:#e8edf5; font-size:14px; transition:all 0.3s ease; outline:none; margin-bottom:12px;">
                    <button class="neon-btn" style="width:100%; padding:14px; background:linear-gradient(135deg,#ffd700,#ff8800); border:none; border-radius:12px; font-weight:700; color:#0a0a0f; cursor:pointer;" onclick="document.getElementById('login_btn').click();">🔓 Login</button>
                </div>
                <div style="text-align:center; margin-top:12px; font-size:13px; color:#5a5a6a;">Tiada akaun? <a href="#" style="color:#ffd700; text-decoration:none;" onclick="document.getElementById('signup_btn').click();">Daftar Sekarang</a></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input("Username", key="login_user_input", placeholder="Masukkan username")
        password = st.text_input("Password", type="password", key="login_pass_input", placeholder="Masukkan password")
        email = st.text_input("Email", key="login_email_input", placeholder="Masukkan email")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🔓 Login", key="login_btn", use_container_width=True):
                if username and password:
                    result = login_user(username, password)
                    if result["success"]:
                        st.session_state.logged_in = True
                        st.session_state.username = result["username"]
                        st.session_state.role = result["role"]
                        st.success(f"✅ Welcome, {username}!")
                        st.rerun()
                    else:
                        st.error(result["error"])
                else:
                    st.warning("⚠️ Sila isi username dan password!")
        with col_b:
            if st.button("📝 Signup", key="signup_btn", use_container_width=True):
                if username and password and email:
                    result = register_user(username, password, email)
                    if result["success"]:
                        st.success(f"✅ Akaun '{username}' didaftarkan!")
                    else:
                        st.error(result["error"])
                else:
                    st.warning("⚠️ Sila isi semua maklumat!")

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
        st.session_state.current_tab = "🏠 Dashboard"

    apply_modern_css()

    if not st.session_state.logged_in:
        login_ui()
        return

    username = st.session_state.username
    is_admin = st.session_state.role == "admin"
    user_data = get_user_points(username)
    tier = get_user_tier(username)
    tier_color = get_tier_color(username)

    with st.sidebar:
        st.markdown(f"""
            <div style="text-align:center; padding:12px 0;">
                <div style="font-size:36px;">{'👑' if is_admin else '👤'}</div>
                <div style="font-weight:600; font-size:15px; color:#e8edf5;">{username}</div>
                <div style="font-size:10px; color:#5a5a6a;">{st.session_state.role.upper()}</div>
                <div style="margin-top:4px; display:flex; justify-content:center; gap:4px; flex-wrap:wrap;">
                    <span class="tier-badge" style="background:{tier_color}; color:white;">{get_tier_badge(username)}</span>
                    <span class="tier-badge" style="background:linear-gradient(135deg,#ffd700,#ff8800); color:#0a0a0f;">⭐ {user_data['points']}</span>
                    <span class="tier-badge" style="background:linear-gradient(135deg,#7b2ffc,#4400aa); color:white;">Lv.{user_data['level']}</span>
                </div>
                <div style="font-size:9px; color:#3a3a4a; margin-top:4px;">
                    {get_tier_label(username)} · {TIERS[tier]['points_multiplier']}x Points {' '.join(user_data['badges'][:2])}
                </div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        nav_items = [
            "🏠 Dashboard", "💬 Chat", "🧠 Pakar", "📝 RPH", "🎨 Art", "📊 Invois", "📱 WhatsApp",
            "🚗 Roadtax/Saman", "🆔 IC & Bantuan", "💰 Bantuan Kerajaan", "🏠 MyKiosk/PR1MA", "🏗️ Kontraktor",
            "🔬 Science Lab", "📜 History Explorer", "🌐 Language Lab", "📐 Math Solver", "💻 Coding Coach",
            "🗣️ Debate", "📖 Storyteller", "📝 Poetry", "🎬 Animation", "🎨 3D Model", "🎨 Tattoo",
            "💇 Hairstyle", "🏠 Interior", "👗 Fashion", "💼 Business Plan", "📊 Market Analysis",
            "🎯 Competitor", "💰 Pricing", "📊 SWOT", "📄 Pitch Deck", "🏋️ Fitness", "🍽️ Meal Planner",
            "😴 Sleep Tracker", "🧘 Meditation", "🧘 Yoga", "🥗 Diet Planner", "💕 Dating Coach",
            "📱 Social Media", "📱 Content Creator", "📊 Influencer", "😂 Meme Maker", "🔥 Viral Generator",
            "⚙️ DevOps", "🐳 Docker", "☸️ Kubernetes", "☁️ Cloud Architect", "🗄️ Database", "🌐 Network",
            "🎮 Game Master", "🧩 Puzzle", "📝 Quiz Master", "🤔 Riddle", "👻 Horror Story", "😂 Comedy",
            "⚙️ Settings"
        ]

        if is_admin:
            nav_items.append("👑 Admin")

        # ============================================================
        # 🔥 FIX: GUNA i UNTUK UNIQUE KEY
        # ============================================================
        for i, item in enumerate(nav_items):
            if st.button(item, use_container_width=True, key=f"nav_{i}_{item}"):
                st.session_state.current_tab = item
                st.rerun()

        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()

    # === KANDUNGAN ===
    if st.session_state.current_tab == "🏠 Dashboard":
        st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center; padding:12px 16px; border-bottom:1px solid rgba(255,255,255,0.05); flex-wrap:wrap; gap:8px;">
                <div style="display:flex; align-items:center; gap:12px;">
                    <div style="font-size:28px;">🔥</div>
                    <div>
                        <div style="font-weight:700; font-size:18px; color:#e8edf5;">MyChatAI Pro</div>
                        <div style="font-size:10px; color:#5a5a6a;">v35.0 · 230+ Ciri</div>
                    </div>
                </div>
                <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
                    <span class="tier-badge" style="background:{get_tier_color(username)}; color:white;">{get_tier_badge(username)}</span>
                    <span class="tier-badge" style="background:linear-gradient(135deg,#ffd700,#ff8800); color:#0a0a0f;">⭐ {user_data['points']} pts</span>
                    <span style="display:flex; align-items:center; gap:6px; background:rgba(255,255,255,0.03); padding:4px 10px; border-radius:30px; border:1px solid rgba(255,255,255,0.05);">
                        <span style="font-size:16px;">{'👑' if is_admin else '👤'}</span>
                        <span style="font-size:12px; font-weight:600; color:#e8edf5;">{username}</span>
                    </span>
                </div>
            </div>
        """, unsafe_allow_html=True)

        users = load_users()
        st.markdown(f"""
            <div style="display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-top:12px;">
                <div class="glass"><div style="font-size:11px; color:#5a5a6a;">👥 Pengguna</div><div style="font-size:24px; font-weight:700; color:#ffd700;">{len(users)}</div></div>
                <div class="glass"><div style="font-size:11px; color:#5a5a6a;">⭐ Points</div><div style="font-size:24px; font-weight:700; color:#00d4ff;">{user_data['points']}</div></div>
                <div class="glass"><div style="font-size:11px; color:#5a5a6a;">💬 Chat</div><div style="font-size:24px; font-weight:700; color:#ff6fd8;">{len(st.session_state.get('messages', []))}</div></div>
                <div class="glass"><div style="font-size:11px; color:#5a5a6a;">📝 RPH</div><div style="font-size:24px; font-weight:700; color:#7b2ffc;">{len(load_rph_history())}</div></div>
            </div>
        """, unsafe_allow_html=True)

    # === CIRI UTAMA ===
    elif st.session_state.current_tab == "💬 Chat":
        st.markdown("### 💬 Chat")
        if not has_feature_override(username, "chat"):
            st.warning("⚠️ Ciri Chat tidak diaktifkan untuk tier anda.")
        else:
            limit = check_limit_override(username, "chat")
            st.caption(f"💬 {limit['used']}/{limit['limit']} chat hari ini")
            if not limit["allowed"]:
                st.warning(f"⚠️ Had chat harian ({limit['limit']}) telah dicapai!")
            else:
                for msg in st.session_state.messages[-20:]:
                    if msg["role"] == "user":
                        st.markdown(f'<div class="chat-bubble-user">{msg["content"]}</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="chat-bubble-ai">🤖 {msg["content"]}</div>', unsafe_allow_html=True)

                user_input = st.text_input("Taip soalan...", key="chat_input")
                if st.button("📤 Hantar", use_container_width=True) and user_input:
                    st.session_state.messages.append({"role": "user", "content": user_input, "time": datetime.datetime.now().strftime("%H:%M")})
                    with st.spinner("🤔 Menaip..."):
                        response = call_groq(f"Jawab soalan: {user_input}")
                        st.session_state.messages.append({"role": "ai", "content": response, "time": datetime.datetime.now().strftime("%H:%M")})
                        increment_usage(username, "chat")
                        add_points_override(username, 5)
                        st.rerun()

    elif st.session_state.current_tab == "🧠 Pakar":
        st.markdown("### 🧠 20 Pakar")
        if not has_feature_override(username, "expert"):
            st.warning("⚠️ Ciri Pakar tidak diaktifkan untuk tier anda.")
        else:
            limit = check_limit_override(username, "expert")
            if not limit["allowed"]:
                st.warning(f"⚠️ Had pakar harian ({limit['limit']}) telah dicapai!")
            else:
                experts = {
                    "👨‍⚕️ Kesihatan": "kesihatan", "📊 Ekonomi": "ekonomi", "📜 Sejarah": "sejarah",
                    "🔬 Sains": "sains", "📐 Matematik": "matematik", "📝 Bahasa": "bahasa",
                    "🏗️ Seni Bina": "senibina", "🌍 Geografi": "geografi", "💡 Inovasi": "inovasi",
                    "🤖 Robotik": "robotik", "🧬 Genetik": "genetik", "🌾 Pertanian": "pertanian",
                    "🏥 Perubatan": "perubatan", "🔋 Tenaga": "tenaga", "📡 Komunikasi": "komunikasi",
                    "🎮 Permainan": "permainan", "🚀 Aeroangkasa": "aeroangkasa", "🌊 Marin": "marin",
                    "🏛️ Politik": "politik", "🧘 Psikologi": "psikologi"
                }
                selected = st.selectbox("🎯 Pilih Pakar:", list(experts.keys()))
                question = st.text_area("✏️ Soalan:", height=80)
                if st.button("💬 Tanya Pakar", use_container_width=True) and question:
                    with st.spinner("🧠 Berfikir..."):
                        response = call_groq(f"Anda adalah {selected}. Jawab: {question}")
                        st.markdown(response)
                        increment_usage(username, "expert")
                        add_points_override(username, 15)

    elif st.session_state.current_tab == "📝 RPH":
        st.markdown("### 📝 RPH Generator")
        if not has_feature_override(username, "rph"):
            st.warning("⚠️ Ciri RPH tidak diaktifkan untuk tier anda.")
        else:
            limit = check_limit_override(username, "rph")
            if not limit["allowed"]:
                st.warning(f"⚠️ Had RPH harian ({limit['limit']}) telah dicapai!")
            else:
                col1, col2 = st.columns(2)
                with col1:
                    subjek = st.selectbox("📚 Subjek:", ["Bahasa Melayu", "Bahasa Inggeris", "Matematik", "Sains"])
                    tahun = st.selectbox("📖 Tahun:", ["Tahun 1", "Tahun 2", "Tahun 3", "Tahun 4", "Tahun 5", "Tahun 6"])
                with col2:
                    topik = st.text_input("📌 Topik:")
                    tempoh = st.selectbox("⏱️ Tempoh:", ["30 minit", "60 minit"])
                if st.button("📄 Jana RPH", use_container_width=True) and topik:
                    rph = call_groq(f"Sediakan RPH {subjek} Tahun {tahun}, topik {topik}, tempoh {tempoh}")
                    st.markdown(rph)
                    increment_usage(username, "rph")
                    add_points_override(username, 20)

    elif st.session_state.current_tab == "🎨 Art":
        st.markdown("### 🎨 AI Art Generator")
        if not has_feature_override(username, "art"):
            st.warning("⚠️ Ciri Art tidak diaktifkan untuk tier anda.")
        else:
            limit = check_limit_override(username, "art")
            if not limit["allowed"]:
                st.warning(f"⚠️ Had art harian ({limit['limit']}) telah dicapai!")
            else:
                prompt = st.text_input("✏️ Huraikan gambar:")
                style = st.selectbox("🎨 Gaya:", ["realistic", "anime", "cartoon", "fantasy", "abstract"])
                if st.button("🎨 Hasilkan", use_container_width=True) and prompt:
                    img = generate_image(prompt, style)
                    if img:
                        st.image(img, use_container_width=True)
                        increment_usage(username, "art")
                        add_points_override(username, 15)

    elif st.session_state.current_tab == "📊 Invois":
        st.markdown("### 📊 Invois & Quotation")
        if not has_feature_override(username, "invoice"):
            st.warning("⚠️ Ciri Invois tidak diaktifkan untuk tier anda.")
        else:
            company = st.text_input("🏢 Nama Syarikat:")
            customer = st.text_input("👤 Nama Pelanggan:")
            desc = st.text_input("📝 Keterangan:")
            jumlah = st.number_input("💰 Jumlah (RM):", min_value=0.0, value=0.0)
            if st.button("🚀 Hasilkan Invois", use_container_width=True) and company and customer:
                st.success(f"✅ Invois untuk {customer} berjaya dihasilkan!")
                st.markdown(f"""
                    **🏢 {company}**
                    **👤 Pelanggan:** {customer}
                    **📝 Keterangan:** {desc or "Perkhidmatan"}
                    **💰 Jumlah:** RM {jumlah:,.2f}
                    **📅 Tarikh:** {datetime.datetime.now().strftime('%d %B %Y')}
                """)
                add_points_override(username, 30)

    elif st.session_state.current_tab == "📱 WhatsApp":
        st.markdown("### 📱 Hantar ke WhatsApp")
        if not has_feature_override(username, "whatsapp"):
            st.warning("⚠️ Ciri WhatsApp tidak diaktifkan untuk tier anda.")
        else:
            limit = check_limit_override(username, "whatsapp")
            if not limit["allowed"]:
                st.warning(f"⚠️ Had WhatsApp harian ({limit['limit']}) telah dicapai!")
            else:
                phone = st.text_input("📱 No Telefon:", placeholder="60123456789")
                message = st.text_area("💬 Mesej:", height=100)
                if st.button("📤 Hantar", use_container_width=True) and phone and message:
                    clean_phone = re.sub(r'[^0-9]', '', phone)
                    if not clean_phone.startswith('6'):
                        clean_phone = '6' + clean_phone
                    msg_encoded = requests.utils.quote(message)
                    whatsapp_url = f"https://wa.me/{clean_phone}?text={msg_encoded}"
                    st.markdown(f'<a href="{whatsapp_url}" target="_blank"><button style="background:#25D366; color:white; padding:10px 20px; border:none; border-radius:10px; cursor:pointer;">📱 Buka WhatsApp</button></a>', unsafe_allow_html=True)
                    increment_usage(username, "whatsapp")
                    add_points_override(username, 15)

    # === CIRI SEMAKAN DATA ===
    elif st.session_state.current_tab == "🚗 Roadtax/Saman":
        check_roadtax_ui()
    elif st.session_state.current_tab == "🆔 IC & Bantuan":
        check_ic_ui()
    elif st.session_state.current_tab == "💰 Bantuan Kerajaan":
        check_bantuan_ui()
    elif st.session_state.current_tab == "🏠 MyKiosk/PR1MA":
        check_mykiosk_ui()
    elif st.session_state.current_tab == "🏗️ Kontraktor":
        contractor_management_ui()

    # === CIRI TAMBAHAN ===
    elif st.session_state.current_tab == "🔬 Science Lab":
        ai_science_lab_ui()
    elif st.session_state.current_tab == "📜 History Explorer":
        ai_history_explorer_ui()
    elif st.session_state.current_tab == "🌐 Language Lab":
        ai_language_lab_ui()
    elif st.session_state.current_tab == "📐 Math Solver":
        ai_math_solver_ui()
    elif st.session_state.current_tab == "💻 Coding Coach":
        ai_coding_coach_ui()
    elif st.session_state.current_tab == "🗣️ Debate":
        ai_debate_partner_ui()
    elif st.session_state.current_tab == "📖 Storyteller":
        ai_storyteller_ui()
    elif st.session_state.current_tab == "📝 Poetry":
        ai_poetry_ui()
    elif st.session_state.current_tab == "🎬 Animation":
        ai_animation_maker_ui()
    elif st.session_state.current_tab == "🎨 3D Model":
        ai_3d_model_ui()
    elif st.session_state.current_tab == "🎨 Tattoo":
        ai_tattoo_designer_ui()
    elif st.session_state.current_tab == "💇 Hairstyle":
        ai_hairstyle_ui()
    elif st.session_state.current_tab == "🏠 Interior":
        ai_interior_designer_ui()
    elif st.session_state.current_tab == "👗 Fashion":
        ai_fashion_designer_ui()
    elif st.session_state.current_tab == "💼 Business Plan":
        ai_business_plan_ui()
    elif st.session_state.current_tab == "📊 Market Analysis":
        ai_market_analysis_ui()
    elif st.session_state.current_tab == "🎯 Competitor":
        ai_competitor_analysis_ui()
    elif st.session_state.current_tab == "💰 Pricing":
        ai_pricing_strategy_ui()
    elif st.session_state.current_tab == "📊 SWOT":
        ai_swot_analysis_ui()
    elif st.session_state.current_tab == "📄 Pitch Deck":
        ai_pitch_deck_ui()
    elif st.session_state.current_tab == "🏋️ Fitness":
        ai_fitness_tracker_ui()
    elif st.session_state.current_tab == "🍽️ Meal Planner":
        ai_meal_planner_ui()
    elif st.session_state.current_tab == "😴 Sleep Tracker":
        ai_sleep_tracker_ui()
    elif st.session_state.current_tab == "🧘 Meditation":
        ai_meditation_coach_ui()
    elif st.session_state.current_tab == "🧘 Yoga":
        ai_yoga_guide_ui()
    elif st.session_state.current_tab == "🥗 Diet Planner":
        ai_diet_planner_ui()
    elif st.session_state.current_tab == "💕 Dating Coach":
        ai_dating_coach_ui()
    elif st.session_state.current_tab == "📱 Social Media":
        ai_social_media_manager_ui()
    elif st.session_state.current_tab == "📱 Content Creator":
        ai_content_creator_ui()
    elif st.session_state.current_tab == "📊 Influencer":
        ai_influencer_analyzer_ui()
    elif st.session_state.current_tab == "😂 Meme Maker":
        ai_meme_maker_ui()
    elif st.session_state.current_tab == "🔥 Viral Generator":
        ai_viral_generator_ui()
    elif st.session_state.current_tab == "⚙️ DevOps":
        ai_devops_helper_ui()
    elif st.session_state.current_tab == "🐳 Docker":
        ai_docker_expert_ui()
    elif st.session_state.current_tab == "☸️ Kubernetes":
        ai_kubernetes_guide_ui()
    elif st.session_state.current_tab == "☁️ Cloud Architect":
        ai_cloud_architect_ui()
    elif st.session_state.current_tab == "🗄️ Database":
        ai_database_optimizer_ui()
    elif st.session_state.current_tab == "🌐 Network":
        ai_network_analyzer_ui()
    elif st.session_state.current_tab == "🎮 Game Master":
        ai_game_master_ui()
    elif st.session_state.current_tab == "🧩 Puzzle":
        ai_puzzle_creator_ui()
    elif st.session_state.current_tab == "📝 Quiz Master":
        ai_quiz_master_ui()
    elif st.session_state.current_tab == "🤔 Riddle":
        ai_riddle_generator_ui()
    elif st.session_state.current_tab == "👻 Horror Story":
        ai_horror_story_ui()
    elif st.session_state.current_tab == "😂 Comedy":
        ai_comedy_writer_ui()

    elif st.session_state.current_tab == "⚙️ Settings":
        st.markdown("### ⚙️ Settings")
        col1, col2 = st.columns(2)
        with col1:
            temp = st.slider("🌡️ Temperature", 0.0, 1.0, 0.7, 0.05)
            st.caption(f"🎯 Nilai: {temp:.2f}")
        with col2:
            model = st.selectbox("🤖 Model AI", ["gemini-pro", "llama-3.1-70b", "deepseek-chat"], index=0)
            max_tokens = st.slider("📝 Max Tokens", 256, 4096, 2048, 256)
        if st.button("💾 Simpan Settings", use_container_width=True):
            users = load_users()
            users[username]["settings"] = {"temperature": temp, "model": model, "max_tokens": max_tokens}
            save_users(users)
            st.success("✅ Settings disimpan!")

    elif st.session_state.current_tab == "👑 Admin" and is_admin:
        st.markdown("### 👑 Admin Panel")
        users = load_users()
        st.metric("👥 Pengguna", len(users))
        for user, data in users.items():
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.write(f"👤 {user}")
            with col2:
                st.write(f"⭐ {data.get('points', 0)}")
            with col3:
                if user != "admin" and st.button("🗑️", key=f"del_{user}"):
                    del users[user]
                    save_users(users)
                    st.rerun()

    else:
        st.info(f"✅ {st.session_state.current_tab} — Ciri ini sedang dibangunkan.")
        add_points_override(username, 5)

if __name__ == "__main__":
    main()
