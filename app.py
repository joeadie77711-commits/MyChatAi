# mychat_ultimate_pro_v44.0.py
import streamlit as st
import datetime
import json
import os
import requests
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
from collections import defaultdict
from urllib.parse import quote
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging.handlers

# === LOGGING SETUP WITH ROTATING FILE ===
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.handlers.RotatingFileHandler(
    'mychat_app.log', 
    maxBytes=5*1024*1024, 
    backupCount=3
)
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# === FCNTL FALLBACK UNTUK WINDOWS ===
try:
    import fcntl
    HAVE_FCNTL = True
except ImportError:
    fcntl = None
    HAVE_FCNTL = False

# === PAGE CONFIG ===
st.set_page_config(
    page_title="MyChatAI Pro",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# === REQUESTS SESSION WITH RETRIES ===
def get_requests_session():
    session = requests.Session()
    retries = Retry(
        total=3, 
        backoff_factor=0.5, 
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    return session

requests_session = get_requests_session()

# === API KEYS DARI STREAMLIT SECRETS ===
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")
OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY", "")
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
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

# === VALIDATE OPTIONAL API KEYS ===
if not GROQ_API_KEY:
    logger.warning("GROQ_API_KEY not configured - Groq service will be unavailable")
if not OPENROUTER_API_KEY:
    logger.warning("OPENROUTER_API_KEY not configured - DeepSeek service will be unavailable")
if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY not configured - Gemini service will be unavailable")
if not CLAUDE_API_KEY:
    logger.warning("CLAUDE_API_KEY not configured - Claude service will be unavailable")
if not HUGGINGFACE_API_KEY:
    logger.warning("HUGGINGFACE_API_KEY not configured - HuggingFace service will be unavailable")
if not REPLICATE_API_KEY:
    logger.warning("REPLICATE_API_KEY not configured - Replicate service will be unavailable")

# === SEMAK KUNCI WAJIB ===
required_keys = ["GROQ_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY"]
missing_keys = [key for key in required_keys if not st.secrets.get(key)]
if missing_keys:
    error_msg = f"Missing required secrets: {', '.join(missing_keys)}"
    st.error(f"❌ {error_msg}")
    logger.error(error_msg)
    st.stop()

# === WAJIB - TIADA DEFAULT ===
ADMIN_EMAIL = st.secrets.get("ADMIN_EMAIL")
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD")
if not ADMIN_EMAIL or not ADMIN_PASSWORD:
    logger.error("ADMIN_EMAIL or ADMIN_PASSWORD missing in st.secrets")
    st.error("❌ Admin credentials not configured. Sila setup secrets.")
    st.stop()

try:
    MAX_FREE_REQUESTS = int(st.secrets.get("MAX_FREE_REQUESTS", 1000))
except (TypeError, ValueError):
    MAX_FREE_REQUESTS = 1000

DISCORD_WEBHOOK = st.secrets.get("DISCORD_WEBHOOK", "")
TELEGRAM_BOT_TOKEN = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "")

# === CONSTANTS ===
USER_DATA_FILE = "mychat_users.json"
CHAT_HISTORY_FILE = "mychat_chats.json"
USAGE_FILE = "mychat_usage.json"
DEFAULT_AVATAR = "https://ui-avatars.com/api/?name=User&background=4d6bfe&color=fff&size=40"
SESSION_TIMEOUT = 86400
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
MAX_INPUT_LENGTH = 4000

# === SAFE JSON ACCESS HELPER ===
def safe_get(obj, path, default=None):
    """Safely access nested dict/list structure"""
    for p in path:
        if isinstance(p, int):
            if isinstance(obj, list) and len(obj) > p:
                obj = obj[p]
            else:
                return default
        else:
            if isinstance(obj, dict) and p in obj:
                obj = obj[p]
            else:
                return default
    return obj

# === ATOMIC WRITE - CROSS PLATFORM ===
def atomic_write_file(filepath, data):
    """Atomic write using temp file and rename (utf-8, safe, set permissions)"""
    dirname = os.path.dirname(filepath) or "."
    try:
        fd, temppath = tempfile.mkstemp(dir=dirname, suffix='.tmp')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            if HAVE_FCNTL and fcntl:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            json.dump(data, f, indent=2, ensure_ascii=False)
            if HAVE_FCNTL and fcntl:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        os.replace(temppath, filepath)
        try:
            os.chmod(filepath, 0o600)
        except Exception:
            pass
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
                    with open(USAGE_FILE, "r", encoding='utf-8') as f:
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
        self.attempts = {}
    
    def add_attempt(self, username, success):
        now = datetime.datetime.now()
        if username not in self.attempts:
            self.attempts[username] = []
        self.attempts[username].append((now, success))
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
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode(), salt).decode()

def verify_password(password, hashed):
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except:
        return False

# === INPUT SANITIZATION ===
def sanitize_input(text, max_length=1000, allow_newlines=True):
    """Sanitize user input - remove HTML tags, redact sensitive phrases, limit length"""
    if text is None:
        return ""
    text = str(text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'(?i)\b(ignore previous instructions|forget previous instructions|system prompt override)\b', '[REDACTED]', text)
    if len(text) > max_length:
        text = text[:max_length] + "... (truncated)"
    return text.strip()

def sanitize_prompt(prompt):
    prompt = sanitize_input(prompt, MAX_INPUT_LENGTH)
    prompt = re.sub(r'(?i)\b(you are now a system|developer mode enabled|override system prompt)\b', '[REDACTED]', prompt)
    return prompt

# (continues...)
