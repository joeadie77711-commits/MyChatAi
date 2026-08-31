# mychat_ultimate_pro_v44.0.py
import streamlit as st
import datetime
import json
import os
import requests
import hashlib
import re
import time
import logging
import traceback
import html
import bcrypt
import threading
import tempfile
from io import BytesIO
from PIL import Image
import base64
import random
from collections import defaultdict
from urllib.parse import quote

# === FCNTL FALLBACK UNTUK WINDOWS ===
try:
    import fcntl
    HAVE_FCNTL = True
except ImportError:
    fcntl = None
    HAVE_FCNTL = False

# === LOGGING SETUP ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='mychat_app.log'
)
logger = logging.getLogger(__name__)

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
    
    # === WAJIB - TIADA DEFAULT ===
    ADMIN_EMAIL = st.secrets.get("ADMIN_EMAIL")
    ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD")
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        logger.error("ADMIN_EMAIL or ADMIN_PASSWORD missing in st.secrets")
        st.error("❌ Admin credentials not configured. Sila setup secrets.")
        st.stop()
    
    # Cast MAX_FREE_REQUESTS ke int
    try:
        MAX_FREE_REQUESTS = int(st.secrets.get("MAX_FREE_REQUESTS", 1000))
    except (TypeError, ValueError):
        MAX_FREE_REQUESTS = 1000
    
    DISCORD_WEBHOOK = st.secrets.get("DISCORD_WEBHOOK", "")
    TELEGRAM_BOT_TOKEN = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "")
        
except KeyError as e:
    st.error(f"Missing required secret: {e}")
    logger.error(f"Missing secret: {e}")
    st.stop()

# === CONSTANTS ===
USER_DATA_FILE = "mychat_users.json"
CHAT_HISTORY_FILE = "mychat_chats.json"
USAGE_FILE = "mychat_usage.json"
DEFAULT_AVATAR = "https://ui-avatars.com/api/?name=User&background=4d6bfe&color=fff&size=40"
SESSION_TIMEOUT = 86400  # 24 jam
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
MAX_INPUT_LENGTH = 4000

# === ATOMIC WRITE - CROSS PLATFORM ===
def atomic_write_file(filepath, data):
    """Atomic write using temp file and rename"""
    dirname = os.path.dirname(filepath) or "."
    try:
        fd, temppath = tempfile.mkstemp(dir=dirname, suffix='.tmp')
        with os.fdopen(fd, 'w') as f:
            if HAVE_FCNTL and fcntl:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            json.dump(data, f, indent=2)
            if HAVE_FCNTL and fcntl:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        os.replace(temppath, filepath)
        return True
    except Exception as e:
        logger.error(f"Atomic write error: {traceback.format_exc()}")
        return False

# === FILE LOCKING - THREAD SAFE DENGAN ATOMIC WRITE ===
class DataManager:
    def __init__(self):
        self.lock = threading.RLock()
    
    def save_users(self, data):
        with self.lock:
            atomic_write_file(USER_DATA_FILE, data)
    
    def save_chats(self, data):
        with self.lock:
            atomic_write_file(CHAT_HISTORY_FILE, data)
    
    def save_usage(self, username, data):
        with self.lock:
            all_data = {}
            try:
                if os.path.exists(USAGE_FILE):
                    with open(USAGE_FILE, "r") as f:
                        if HAVE_FCNTL and fcntl:
                            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                        all_data = json.load(f)
                        if HAVE_FCNTL and fcntl:
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                all_data[username] = data
                atomic_write_file(USAGE_FILE, all_data)
            except Exception as e:
                logger.error(f"Error saving usage: {traceback.format_exc()}")

data_manager = DataManager()

# === LOGIN ATTEMPT TRACKING ===
class LoginAttemptTracker:
    def __init__(self):
        self.attempts = {}  # {username: [(timestamp, success), ...]}
    
    def add_attempt(self, username, success):
        now = datetime.datetime.now()
        if username not in self.attempts:
            self.attempts[username] = []
        self.attempts[username].append((now, success))
        # Clean old entries (older than 1 hour)
        self.attempts[username] = [(ts, s) for ts, s in self.attempts[username] 
                                   if (now - ts).total_seconds() < 3600]
    
    def is_locked(self, username):
        now = datetime.datetime.now()
        if username not in self.attempts:
            return False
        failed = sum(1 for ts, success in self.attempts[username] 
                     if not success and (now - ts).total_seconds() < (LOCKOUT_MINUTES * 60))
        return failed >= MAX_LOGIN_ATTEMPTS
    
    def get_remaining_attempts(self, username):
        if username not in self.attempts:
            return MAX_LOGIN_ATTEMPTS
        now = datetime.datetime.now()
        failed = sum(1 for ts, success in self.attempts[username] 
                     if not success and (now - ts).total_seconds() < (LOCKOUT_MINUTES * 60))
        return max(0, MAX_LOGIN_ATTEMPTS - failed)

login_tracker = LoginAttemptTracker()

# === HASH - GUNA BCRYPT ===
def hash_password(password):
    """Hash password using bcrypt with salt"""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode(), salt).decode()

def verify_password(password, hashed):
    """Verify password against bcrypt hash"""
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except:
        return False

# === INPUT SANITIZATION - TANPA html.escape (buang double-escaping) ===
def sanitize_input(text, max_length=1000, allow_newlines=True):
    """Sanitize user input - remove HTML tags, redact sensitive words, limit length"""
    if text is None:
        return ""
    text = str(text)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove potential injection patterns - whole word only
    text = re.sub(r'(?i)\b(system|assistant|role|ignore|forget|previous|instruction)\b', '[REDACTED]', text)
    # Limit length
    if len(text) > max_length:
        text = text[:max_length] + "... (truncated)"
    return text.strip()

def sanitize_prompt(prompt):
    """Sanitize prompt for AI"""
    prompt = sanitize_input(prompt, MAX_INPUT_LENGTH)
    prompt = re.sub(r'(?i)\b(you are|you are now|system prompt|developer mode)\b', '[REDACTED]', prompt)
    return prompt

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_username(username):
    """Validate username format"""
    return re.match(r'^[a-zA-Z0-9_]{3,30}$', username) is not None

def validate_password_strength(password):
    """Check password strength"""
    if len(password) < 8:
        return False, "Password mesti sekurang-kurangnya 8 aksara"
    if not re.search(r'[A-Z]', password):
        return False, "Password perlu ada huruf besar"
    if not re.search(r'[a-z]', password):
        return False, "Password perlu ada huruf kecil"
    if not re.search(r'[0-9]', password):
        return False, "Password perlu ada nombor"
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password perlu ada aksara khas"
    return True, "Password kuat"

# === DATA FUNCTIONS ===
def load_users():
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, "r") as f:
                if HAVE_FCNTL and fcntl:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                data = json.load(f)
                if HAVE_FCNTL and fcntl:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                return data
        except Exception as e:
            logger.error(f"Error loading users: {traceback.format_exc()}")
            return {}
    
    default = {
        "admin": {
            "password": hash_password(ADMIN_PASSWORD),
            "role": "admin",
            "email": ADMIN_EMAIL,
            "name": "Admin",
            "avatar": "https://ui-avatars.com/api/?name=Admin&background=4d6bfe&color=fff&size=40",
            "settings": {"language": "Malay", "dark_mode": True},
            "created_at": datetime.datetime.now().isoformat(),
            "premium_until": None,
            "total_requests": 0,
            "email_verified": True,
            "password_changed": False
        }
    }
    data_manager.save_users(default)
    return default

def save_users(data):
    data_manager.save_users(data)

def load_chats():
    if os.path.exists(CHAT_HISTORY_FILE):
        try:
            with open(CHAT_HISTORY_FILE, "r") as f:
                if HAVE_FCNTL and fcntl:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                data = json.load(f)
                if HAVE_FCNTL and fcntl:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                return data
        except:
            return {}
    return {}

def save_chats(data):
    data_manager.save_chats(data)

def load_usage(username):
    if os.path.exists(USAGE_FILE):
        try:
            with open(USAGE_FILE, "r") as f:
                if HAVE_FCNTL and fcntl:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                data = json.load(f)
                if HAVE_FCNTL and fcntl:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            return data.get(username, {"count": 0, "month": datetime.datetime.now().month, "year": datetime.datetime.now().year})
        except:
            pass
    return {"count": 0, "month": datetime.datetime.now().month, "year": datetime.datetime.now().year}

def save_usage(username, data):
    data_manager.save_usage(username, data)

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
        "percentage": round((usage["count"] / MAX_FREE_REQUESTS) * 100, 1) if MAX_FREE_REQUESTS > 0 else 0
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

# === RATE LIMITING ===
rate_limits = defaultdict(list)

def check_rate_limit(username, limit=30, window=60):
    """30 requests per minute"""
    now = time.time()
    rate_limits[username] = [t for t in rate_limits[username] if t > now - window]
    if len(rate_limits[username]) >= limit:
        return False
    rate_limits[username].append(now)
    return True

# === AUTH FUNCTIONS ===
def login_user(username, password):
    try:
        username = sanitize_input(username, 50)
        
        if login_tracker.is_locked(username):
            logger.warning(f"Login locked for {username}")
            return {"success": False, "error": f"Akaun dikunci. Cuba lagi dalam {LOCKOUT_MINUTES} minit"}
        
        users = load_users()
        if username not in users:
            login_tracker.add_attempt(username, False)
            logger.warning(f"Login attempt failed: user '{username}' not found")
            return {"success": False, "error": "Username atau Password salah"}
        
        if not verify_password(password, users[username]["password"]):
            login_tracker.add_attempt(username, False)
            remaining = login_tracker.get_remaining_attempts(username)
            logger.warning(f"Login attempt failed: wrong password for '{username}'")
            return {"success": False, "error": "Username atau Password salah"}
        
        login_tracker.add_attempt(username, True)
        logger.info(f"User '{username}' logged in successfully")
        
        if username == "admin" and not users[username].get("password_changed", False):
            return {"success": True, "username": username, "role": users[username].get("role", "admin"), "force_change": True}
        
        return {"success": True, "username": username, "role": users[username].get("role", "user")}
    except Exception as e:
        logger.error(f"Login error: {traceback.format_exc()}")
        return {"success": False, "error": "Ralat sistem. Sila cuba lagi."}

def register_user(username, password, email, name=""):
    try:
        username = sanitize_input(username, 30)
        email = sanitize_input(email, 100)
        name = sanitize_input(name, 50)
        
        if not validate_username(username):
            return {"success": False, "error": "Username 3-30 aksara (huruf, nombor, underscore)"}
        
        if not validate_email(email):
            return {"success": False, "error": "Email tidak sah"}
        
        is_strong, msg = validate_password_strength(password)
        if not is_strong:
            return {"success": False, "error": msg}
        
        users = load_users()
        if username in users:
            return {"success": False, "error": "Username sudah wujud"}
        
        if any(u.get("email").lower() == email.lower() for u in users.values()):
            return {"success": False, "error": "Email sudah didaftarkan"}
        
        users[username] = {
            "password": hash_password(password),
            "role": "user",
            "email": email,
            "name": name or username,
            "avatar": f"https://ui-avatars.com/api/?name={quote(name or username)}&background=4d6bfe&color=fff&size=40",
            "settings": {"language": "Malay", "dark_mode": True},
            "created_at": datetime.datetime.now().isoformat(),
            "premium_until": None,
            "total_requests": 0,
            "email_verified": False,
            "password_changed": False  # Galak tukar password pada login pertama
        }
        save_users(users)
        logger.info(f"New user registered: '{username}' ({email})")
        return {"success": True, "username": username, "email_verification_required": True}
    except Exception as e:
        logger.error(f"Registration error: {traceback.format_exc()}")
        return {"success": False, "error": "Ralat sistem. Sila cuba lagi."}

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
            data = response.json()
            try:
                return data['choices'][0]['message']['content']
            except (KeyError, IndexError):
                return str(data)
        logger.error(f"Groq API error: {response.status_code}")
        return f"Ralat Groq: {response.status_code}"
    except requests.exceptions.Timeout:
        logger.error("Groq timeout")
        return "Ralat: Timeout - Sila cuba lagi"
    except requests.exceptions.RequestException as e:
        logger.error(f"Groq request error: {str(e)}")
        return f"Ralat: {str(e)}"
    except Exception as e:
        logger.error(f"Groq error: {traceback.format_exc()}")
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
            data = response.json()
            try:
                return data['choices'][0]['message']['content']
            except (KeyError, IndexError):
                return str(data)
        logger.error(f"DeepSeek API error: {response.status_code}")
        return f"Ralat DeepSeek: {response.status_code}"
    except Exception as e:
        logger.error(f"DeepSeek error: {traceback.format_exc()}")
        return f"Ralat: {str(e)}"

def call_gemini(prompt):
    if not GEMINI_API_KEY:
        return None
    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
        headers = {"Authorization": f"Bearer {GEMINI_API_KEY}", "Content-Type": "application/json"}
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            try:
                return data['candidates'][0]['content']['parts'][0]['text']
            except (KeyError, IndexError):
                return str(data)
        logger.error(f"Gemini API error: {response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Gemini error: {traceback.format_exc()}")
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
            data = response.json()
            try:
                return data['content'][0]['text']
            except (KeyError, IndexError):
                return str(data)
        logger.error(f"Claude API error: {response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Claude error: {traceback.format_exc()}")
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
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                if isinstance(result[0], dict):
                    return result[0].get('generated_text', str(result[0]))
                return str(result[0])
            return str(result)
        return None
    except Exception as e:
        logger.error(f"HuggingFace error: {traceback.format_exc()}")
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
                    if status_data.get('status') == 'succeeded':
                        output = status_data.get('output')
                        if isinstance(output, str):
                            return output
                        return str(output) if output is not None else None
                    elif status_data.get('status') == 'failed':
                        return None
                time.sleep(1)
            return None
        return None
    except Exception as e:
        logger.error(f"Replicate error: {traceback.format_exc()}")
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
            # Handle non-string responses
            if isinstance(response, str):
                if response and not response.startswith("Ralat") and not response.startswith("❌"):
                    logger.info(f"Success with {model_name}")
                    return response
            elif response is not None:
                try:
                    response_str = str(response)
                    if response_str and not response_str.startswith("Ralat") and not response_str.startswith("❌"):
                        logger.info(f"Success with {model_name} (converted)")
                        return response_str
                except:
                    pass
        except Exception as e:
            logger.error(f"Fallback {model_name} failed: {str(e)}")
            continue
    return "Maaf, semua model AI tidak dapat diakses. Sila cuba lagi nanti."

# ============================================================
# DETECT SOALAN "SIAPA ANDA"
# ============================================================
def is_identity_question(prompt):
    """Detect identity question - guna whole word matching"""
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
        if re.search(r'\b' + re.escape(keyword) + r'\b', prompt_lower):
            return True
    return False

def get_identity_response():
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
    if not check_rate_limit(username):
        logger.warning(f"Rate limit exceeded for {username}")
        return "Maaf, terlalu banyak permintaan. Sila tunggu sebentar."

    limit_check = check_usage_limit(username)
    if not limit_check["allowed"]:
        return f"Had Penggunaan Bulanan Telah Dicapai\nPenggunaan: {limit_check['used']}/{limit_check['limit']}"

    prompt = sanitize_prompt(prompt)

    if is_identity_question(prompt):
        return get_identity_response()

    try:
        if think_mode:
            response = call_deepseek_r1(prompt)
        else:
            response = call_groq(prompt)

        if isinstance(response, str) and (response.startswith("Ralat") or response.startswith("❌")):
            response = smart_ai_with_fallback(prompt)

        increment_usage(username)
        return response
    except Exception as e:
        logger.error(f"Smart AI error: {traceback.format_exc()}")
        return "Maaf, berlaku ralat. Sila cuba lagi."

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
    
    if st.session_state.get("force_password_change", False):
        st.markdown("""
        <div style="max-width:420px; margin:0 auto; padding:40px 20px;">
            <div style="background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.06); border-radius:20px; padding:32px;">
                <h2 style="color:#e8edf5; text-align:center;">🔐 Tukar Password</h2>
                <p style="color:#f59e0b; text-align:center; font-size:14px;">Sila tukar password default anda untuk keselamatan.</p>
        """, unsafe_allow_html=True)
        
        new_pass = st.text_input("Password Baru", type="password", key="force_new_pass")
        confirm_pass = st.text_input("Confirm Password", type="password", key="force_confirm_pass")
        
        if st.button("💾 Tukar Password", use_container_width=True):
            is_strong, msg = validate_password_strength(new_pass)
            if not is_strong:
                st.error(msg)
            elif new_pass != confirm_pass:
                st.error("Password tidak sama")
            else:
                users = load_users()
                if st.session_state.username in users:
                    users[st.session_state.username]["password"] = hash_password(new_pass)
                    users[st.session_state.username]["password_changed"] = True
                    save_users(users)
                    st.session_state.force_password_change = False
                    st.success("✅ Password berjaya ditukar! Sila login semula.")
                    st.rerun()
        
        st.markdown("</div></div>", unsafe_allow_html=True)
        return
    
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
                        st.session_state.session_start = time.time()
                        if result.get("force_change", False):
                            st.session_state.force_password_change = True
                        st.rerun()
                    else:
                        st.error(result.get("error", "❌ Username atau Password salah"))
                else:
                    st.warning("⚠️ Sila isi username dan password")
        with col_b:
            if st.button("📝 Daftar", key="signup_btn", use_container_width=True):
                if username and password and email:
                    result = register_user(username, password, email)
                    if result["success"]:
                        st.success(f"✅ Akaun '{username}' berjaya didaftarkan! Sila login.")
                        if result.get("email_verification_required", False):
                            st.info("📧 Sila semak email untuk pengesahan.")
                    else:
                        st.error(f"❌ {result['error']}")
                else:
                    st.warning("⚠️ Sila isi semua maklumat")

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
                if verify_password(old_pass, users[username]["password"]):
                    is_strong, msg = validate_password_strength(new_pass)
                    if not is_strong:
                        st.error(msg)
                    elif new_pass != confirm_pass:
                        st.error("Password tidak sama")
                    else:
                        users[username]["password"] = hash_password(new_pass)
                        users[username]["password_changed"] = True
                        save_users(users)
                        st.success("✅ Password berjaya ditukar!")
                        logger.info(f"Password changed for {username}")
                else:
                    st.error("Password lama salah")

        st.markdown("---")
        st.markdown("### Usage Status")
        usage = get_usage_status(username)
        if MAX_FREE_REQUESTS > 0:
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
        st.caption("MyChatAI Pro v44.0")
        st.caption(f"{username} | {st.session_state.role}")

# === CHAT UI ===
def chat_ui():
    username = st.session_state.username
    user_data = get_user_data(username)

    if "session_start" in st.session_state:
        if time.time() - st.session_state.session_start > SESSION_TIMEOUT:
            st.session_state.logged_in = False
            st.session_state.messages = []
            st.warning("Session tamat. Sila login semula.")
            st.rerun()

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
            <div class="version">v44.0</div>
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
        # Escape content before displaying (XSS protection) - ONLY ONCE
        safe_content = html.escape(msg["content"])
        if msg["role"] == "user":
            st.markdown(f'<div class="chat-bubble-user">{safe_content}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-bubble-ai">{safe_content}</div>', unsafe_allow_html=True)

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
                # Sanitize input before saving (XSS protection)
                safe_input = sanitize_input(user_input, MAX_INPUT_LENGTH)
                st.session_state.messages.append({"role": "user", "content": safe_input})
                with st.spinner("Menghasilkan..."):
                    response = smart_ai(username, safe_input, st.session_state.think_mode, st.session_state.search_mode)
                # Sanitize and truncate AI response before saving
                safe_resp = sanitize_input(str(response), MAX_INPUT_LENGTH)
                st.session_state.messages.append({"role": "ai", "content": safe_resp})
                st.rerun()

    st.markdown("""
        </div>
    </div>
    """, unsafe_allow_html=True)

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

    elif feature == "Video":
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

    elif feature == "Music":
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
            msg_encoded = quote(message)
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

    elif feature == "Business":
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

    elif feature == "Fitness":
        goal = st.selectbox("Matlamat", ["Turun Berat", "Bina Otot", "Kekal Sihat"])
        days = st.slider("Hari seminggu", 1, 7, 3)
        if st.button("Jana Rancangan", use_container_width=True):
            response = call_deepseek_r1(f"Hasilkan rancangan senaman untuk matlamat {goal} ({days} hari seminggu)")
            st.markdown(response)

    elif feature == "Meditation":
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
    if "force_password_change" not in st.session_state:
        st.session_state.force_password_change = False

    if not st.session_state.logged_in:
        login_ui()
        return

    if st.session_state.current_tab == "Chat":
        chat_ui()
    else:
        feature_ui(st.session_state.current_tab)

if __name__ == "__main__":
    main()
