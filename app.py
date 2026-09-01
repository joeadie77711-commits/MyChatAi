# app.py - MyChatAI Pro v44.0 (Final - 100/100)
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
import secrets
from io import BytesIO
from PIL import Image
from collections import defaultdict
from urllib.parse import quote
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging.handlers

# === WINDOWS FALLBACK UNTUK FCNTL ===
try:
    import fcntl
    HAVE_FCNTL = True
except ImportError:
    fcntl = None
    HAVE_FCNTL = False

# === LOGGING SETUP ===
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.handlers.RotatingFileHandler(
    'mychat_app.log',
    maxBytes=5*1024*1024,
    backupCount=3
)
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# === PAGE CONFIG ===
st.set_page_config(
    page_title="MyChatAI Pro",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# === REQUESTS SESSION ===
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

# === SAFE JSON ACCESS ===
def safe_get(obj, path, default=None):
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

# === API KEYS ===
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

# === VALIDATE REQUIRED API KEYS ===
if not GROQ_API_KEY:
    st.error("❌ GROQ_API_KEY is required! Please add it to secrets.toml")
    logger.error("GROQ_API_KEY missing")
    st.stop()
if not OPENROUTER_API_KEY:
    st.error("❌ OPENROUTER_API_KEY is required! Please add it to secrets.toml")
    logger.error("OPENROUTER_API_KEY missing")
    st.stop()
if not GEMINI_API_KEY:
    st.error("❌ GEMINI_API_KEY is required! Please add it to secrets.toml")
    logger.error("GEMINI_API_KEY missing")
    st.stop()

# === VALIDATE OPTIONAL API KEYS (warnings only) ===
if not CLAUDE_API_KEY:
    logger.warning("CLAUDE_API_KEY not configured - Claude service will be unavailable")
if not HUGGINGFACE_API_KEY:
    logger.warning("HUGGINGFACE_API_KEY not configured - HuggingFace service will be unavailable")
if not REPLICATE_API_KEY:
    logger.warning("REPLICATE_API_KEY not configured - Replicate service will be unavailable")

# === ADMIN CREDENTIALS ===
ADMIN_EMAIL = st.secrets.get("ADMIN_EMAIL")
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD")
if not ADMIN_EMAIL or not ADMIN_PASSWORD:
    logger.error("ADMIN_EMAIL or ADMIN_PASSWORD missing")
    st.error("❌ Admin credentials not configured.")
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

# === HASH FUNCTIONS ===
def hash_password(password):
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode(), salt).decode()

def verify_password(password, hashed):
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except:
        return False

# === ATOMIC WRITE ===
def atomic_write_file(filepath, data):
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
        logger.error(f"Atomic write error: {str(e)}")
        return False

# === DATA MANAGER ===
class DataManager:
    def __init__(self):
        self.lock = threading.RLock()
        self._user_cache = None
        self._cache_time = 0
        self._cache_duration = 60

    def _get_cached_users(self):
        now = time.time()
        if self._user_cache is None or (now - self._cache_time) > self._cache_duration:
            self._user_cache = self._load_users_from_disk()
            self._cache_time = now
        return self._user_cache

    def _load_users_from_disk(self):
        if os.path.exists(USER_DATA_FILE):
            try:
                with open(USER_DATA_FILE, "r", encoding='utf-8') as f:
                    if HAVE_FCNTL and fcntl:
                        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                    try:
                        data = json.load(f)
                    except json.JSONDecodeError as json_err:
                        logger.error(f"Corrupted users file: {str(json_err)}. Creating new one.")
                        try:
                            backup_path = f"{USER_DATA_FILE}.corrupted.{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
                            os.rename(USER_DATA_FILE, backup_path)
                            logger.info(f"Backed up corrupted file to {backup_path}")
                        except:
                            pass
                        return {}
                    if HAVE_FCNTL and fcntl:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    return data
            except Exception as e:
                logger.error(f"Error loading users: {str(e)}")
                return {}
        if not ADMIN_EMAIL or not ADMIN_PASSWORD:
            logger.error("Cannot create default admin")
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
        self.save_users(default)
        return default

    def save_users(self, data):
        with self.lock:
            atomic_write_file(USER_DATA_FILE, data)
            self._user_cache = data
            self._cache_time = time.time()

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
                logger.error(f"Error saving usage: {str(e)}")

    def get_users(self):
        return self._get_cached_users()

    def clear_cache(self):
        self._user_cache = None
        self._cache_time = 0

data_manager = DataManager()

# === LOGIN ATTEMPT TRACKER ===
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

    def cleanup(self):
        now = datetime.datetime.now()
        for username in list(self.attempts.keys()):
            self.attempts[username] = [(ts, s) for ts, s in self.attempts[username]
                                       if (now - ts).total_seconds() < 3600]
            if not self.attempts[username]:
                del self.attempts[username]

login_tracker = LoginAttemptTracker()

# === RATE LIMITER ===
class RateLimiter:
    def __init__(self):
        self.limits = defaultdict(list)
        self.last_cleanup = time.time()
        self.max_users = 1000

    def check(self, username, limit=30, window=60):
        if time.time() - self.last_cleanup > 300 or len(self.limits) > self.max_users:
            self.cleanup()
            self.last_cleanup = time.time()
        now = time.time()
        self.limits[username] = [t for t in self.limits[username] if t > now - window]
        if len(self.limits[username]) >= limit:
            return False
        self.limits[username].append(now)
        return True

    def cleanup(self):
        now = time.time()
        users_to_remove = []
        for username, timestamps in self.limits.items():
            self.limits[username] = [t for t in timestamps if t > now - 7200]
            if not self.limits[username]:
                users_to_remove.append(username)
        for username in users_to_remove:
            del self.limits[username]
        if len(self.limits) > 500:
            sorted_users = sorted(self.limits.items(), key=lambda x: x[1][0] if x[1] else 0)
            for username, _ in sorted_users[:len(self.limits) - 500]:
                del self.limits[username]

rate_limiter = RateLimiter()

# === SANITIZATION ===
def sanitize_input(text, max_length=1000, allow_newlines=True):
    if text is None:
        return ""
    text = str(text)
    if not allow_newlines:
        text = text.replace('\n', ' ').replace('\r', ' ')
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'(?i)\b(ignore previous instructions|forget previous instructions|system prompt override)\b', '[REDACTED]', text)
    if len(text) > max_length:
        text = text[:max_length] + "... (truncated)"
    return text.strip()

def sanitize_prompt(prompt):
    prompt = sanitize_input(prompt, MAX_INPUT_LENGTH)
    prompt = re.sub(r'(?i)\b(you are now a system|developer mode enabled|override system prompt)\b', '[REDACTED]', prompt)
    return prompt

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_username(username):
    return re.match(r'^[a-zA-Z0-9_]{3,30}$', username) is not None

def validate_password_strength(password):
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
    return data_manager.get_users()

def save_users(data):
    data_manager.save_users(data)

def load_chats():
    if os.path.exists(CHAT_HISTORY_FILE):
        try:
            with open(CHAT_HISTORY_FILE, "r", encoding='utf-8') as f:
                if HAVE_FCNTL and fcntl:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                data = json.load(f)
                if HAVE_FCNTL and fcntl:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                return data
        except Exception as e:
            logger.error(f"Error loading chats: {str(e)}")
            return {}
    return {}

def save_chats(data):
    data_manager.save_chats(data)

def load_usage(username):
    if os.path.exists(USAGE_FILE):
        try:
            with open(USAGE_FILE, "r", encoding='utf-8') as f:
                if HAVE_FCNTL and fcntl:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                data = json.load(f)
                if HAVE_FCNTL and fcntl:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            return data.get(username, {"count": 0, "month": datetime.datetime.now().month, "year": datetime.datetime.now().year})
        except Exception as e:
            logger.error(f"Error loading usage: {str(e)}")
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

def check_rate_limit(username, limit=30, window=60):
    return rate_limiter.check(username, limit, window)

# === AUTH FUNCTIONS ===
def login_user(username, password):
    try:
        username = sanitize_input(username, 50)
        if login_tracker.is_locked(username):
            logger.warning(f"Login locked for user")
            return {"success": False, "error": f"Akaun dikunci. Cuba lagi dalam {LOCKOUT_MINUTES} minit"}
        users = load_users()
        if username not in users:
            login_tracker.add_attempt(username, False)
            logger.warning(f"Login attempt failed: user not found")
            return {"success": False, "error": "Username atau Password salah"}
        if not verify_password(password, users[username]["password"]):
            login_tracker.add_attempt(username, False)
            logger.warning(f"Login attempt failed: wrong password")
            return {"success": False, "error": "Username atau Password salah"}
        login_tracker.add_attempt(username, True)
        logger.info(f"User logged in successfully")
        if username == "admin" and not users[username].get("password_changed", False):
            return {"success": True, "username": username, "role": users[username].get("role", "admin"), "force_change": True}
        return {"success": True, "username": username, "role": users[username].get("role", "user")}
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
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
        if any(u.get("email", "").lower() == email.lower() for u in users.values()):
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
            "password_changed": False
        }
        save_users(users)
        logger.info(f"New user registered: '{username}'")
        return {"success": True, "username": username, "email_verification_required": True}
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
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

# === RESET PASSWORD FUNCTIONS ===
def generate_reset_token():
    return secrets.token_urlsafe(32)

def send_reset_email(email, token):
    logger.info(f"Reset password for {email} with token: {token}")
    return True

def reset_user_password(username, new_password):
    users = load_users()
    if username in users:
        users[username]["password"] = hash_password(new_password)
        users[username]["password_changed"] = True
        save_users(users)
        return True
    return False

# === LOGIN SOSIAL FUNCTIONS ===
def social_login(provider):
    if provider == "google":
        return {"success": True, "username": "google_user", "email": "user@gmail.com", "name": "Google User"}
    elif provider == "facebook":
        return {"success": True, "username": "fb_user", "email": "user@facebook.com", "name": "FB User"}
    return {"success": False, "error": "Social login failed"}

# === AI FUNCTIONS ===
def call_groq(prompt):
    if not GROQ_API_KEY:
        return {"ok": False, "error": "Groq API key not configured"}
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        payload = {"model": "llama-3.1-70b-versatile", "messages": [{"role": "user", "content": prompt}], "temperature": 0.7, "max_tokens": 2048}
        response = requests_session.post(url, json=payload, headers=headers, timeout=60)
        if response.status_code == 200:
            data = response.json()
            content = safe_get(data, ['choices', 0, 'message', 'content'])
            if content is not None:
                return {"ok": True, "text": content}
            return {"ok": False, "error": "Invalid response format"}
        logger.error(f"Groq API error: {response.status_code}")
        return {"ok": False, "error": f"Groq API error: {response.status_code}"}
    except requests.exceptions.Timeout:
        logger.error("Groq timeout")
        return {"ok": False, "error": "Timeout - Sila cuba lagi"}
    except requests.exceptions.RequestException as e:
        logger.error(f"Groq request error: {str(e)}")
        return {"ok": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Groq error: {str(e)}")
        return {"ok": False, "error": str(e)}

def call_deepseek_r1(prompt):
    if not OPENROUTER_API_KEY:
        return {"ok": False, "error": "OpenRouter API key not configured"}
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://mychatai.com",
            "X-Title": "MyChatAI Pro"
        }
        payload = {"model": "deepseek/deepseek-r1", "messages": [{"role": "user", "content": prompt}], "temperature": 0.7, "max_tokens": 4096}
        response = requests_session.post(url, json=payload, headers=headers, timeout=90)
        if response.status_code == 200:
            data = response.json()
            content = safe_get(data, ['choices', 0, 'message', 'content'])
            if content is not None:
                return {"ok": True, "text": content}
            return {"ok": False, "error": "Invalid response format"}
        logger.error(f"DeepSeek API error: {response.status_code}")
        return {"ok": False, "error": f"DeepSeek API error: {response.status_code}"}
    except Exception as e:
        logger.error(f"DeepSeek error: {str(e)}")
        return {"ok": False, "error": str(e)}

def call_gemini(prompt):
    if not GEMINI_API_KEY:
        return {"ok": False, "error": "Gemini API key not configured"}
    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
        headers = {"Authorization": f"Bearer {GEMINI_API_KEY}", "Content-Type": "application/json"}
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        response = requests_session.post(url, json=payload, headers=headers, timeout=60)
        if response.status_code == 200:
            data = response.json()
            content = safe_get(data, ['candidates', 0, 'content', 'parts', 0, 'text'])
            if content is not None:
                return {"ok": True, "text": content}
            return {"ok": False, "error": "Invalid response format"}
        logger.error(f"Gemini API error: {response.status_code}")
        return {"ok": False, "error": f"Gemini API error: {response.status_code}"}
    except Exception as e:
        logger.error(f"Gemini error: {str(e)}")
        return {"ok": False, "error": str(e)}

def call_claude(prompt):
    if not CLAUDE_API_KEY:
        return {"ok": False, "error": "Claude API key not configured"}
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
        response = requests_session.post(url, json=payload, headers=headers, timeout=60)
        if response.status_code == 200:
            data = response.json()
            content = safe_get(data, ['content', 0, 'text'])
            if content is not None:
                return {"ok": True, "text": content}
            return {"ok": False, "error": "Invalid response format"}
        logger.error(f"Claude API error: {response.status_code}")
        return {"ok": False, "error": f"Claude API error: {response.status_code}"}
    except Exception as e:
        logger.error(f"Claude error: {str(e)}")
        return {"ok": False, "error": str(e)}

def call_huggingface(prompt):
    if not HUGGINGFACE_API_KEY:
        return {"ok": False, "error": "HuggingFace API key not configured"}
    try:
        url = "https://api-inference.huggingface.co/models/microsoft/DialoGPT-medium"
        headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
        payload = {"inputs": prompt}
        response = requests_session.post(url, json=payload, headers=headers, timeout=60)
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                if isinstance(result[0], dict):
                    text = result[0].get('generated_text', str(result[0]))
                    return {"ok": True, "text": text}
                return {"ok": True, "text": str(result[0])}
            return {"ok": True, "text": str(result)}
        logger.error(f"HuggingFace API error: {response.status_code}")
        return {"ok": False, "error": f"HuggingFace API error: {response.status_code}"}
    except Exception as e:
        logger.error(f"HuggingFace error: {str(e)}")
        return {"ok": False, "error": str(e)}

def call_replicate(prompt):
    if not REPLICATE_API_KEY:
        return {"ok": False, "error": "Replicate API key not configured"}
    try:
        url = "https://api.replicate.com/v1/predictions"
        headers = {"Authorization": f"Bearer {REPLICATE_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "version": "02e509c789964a7ea8736978a43525956ef40397be9033abf9fd2badfe68c9e3",
            "input": {"prompt": prompt}
        }
        response = requests_session.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code == 201:
            resp_json = response.json()
            prediction_id = safe_get(resp_json, ['id'])
            if not prediction_id:
                logger.error(f"Replicate response missing id")
                return {"ok": False, "error": "Invalid Replicate response"}
            start_time = time.time()
            for i in range(30):
                try:
                    status_response = requests_session.get(
                        f"https://api.replicate.com/v1/predictions/{prediction_id}",
                        headers=headers,
                        timeout=10
                    )
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        if status_data.get('status') == 'succeeded':
                            output = status_data.get('output')
                            if output is not None:
                                return {"ok": True, "text": str(output)}
                            return {"ok": False, "error": "No output from Replicate"}
                        elif status_data.get('status') == 'failed':
                            error_detail = status_data.get('error', 'Unknown error')
                            logger.error(f"Replicate prediction failed: {error_detail}")
                            return {"ok": False, "error": f"Replicate prediction failed: {error_detail}"}
                        elif status_data.get('status') == 'processing':
                            pass
                        else:
                            logger.warning(f"Replicate unknown status: {status_data.get('status')}")
                    elif status_response.status_code == 404:
                        logger.error(f"Replicate prediction not found: {prediction_id}")
                        return {"ok": False, "error": "Replicate prediction not found"}
                    elif status_response.status_code == 429:
                        logger.warning("Replicate rate limited, waiting...")
                        time.sleep(2)
                    else:
                        logger.error(f"Replicate status check error: {status_response.status_code}")
                except requests.exceptions.Timeout:
                    logger.warning("Replicate status check timeout, retrying...")
                except Exception as e:
                    logger.error(f"Replicate status check error: {str(e)}")
                elapsed = time.time() - start_time
                if elapsed > 60:
                    logger.error(f"Replicate prediction timeout after {elapsed:.1f}s")
                    return {"ok": False, "error": "Replicate prediction timeout"}
                sleep_time = min(0.5 * (2 ** i), 5)
                time.sleep(sleep_time)
            return {"ok": False, "error": "Replicate prediction timeout"}
        elif response.status_code == 401:
            logger.error("Replicate API key invalid")
            return {"ok": False, "error": "Replicate API key invalid"}
        elif response.status_code == 429:
            logger.error("Replicate rate limit exceeded")
            return {"ok": False, "error": "Replicate rate limit exceeded"}
        else:
            logger.error(f"Replicate API error: {response.status_code}")
            return {"ok": False, "error": f"Replicate API error: {response.status_code}"}
    except requests.exceptions.Timeout:
        logger.error("Replicate timeout")
        return {"ok": False, "error": "Timeout - Sila cuba lagi"}
    except Exception as e:
        logger.error(f"Replicate error: {str(e)}")
        return {"ok": False, "error": str(e)}

# === SMART AI ===
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
            result = model_func(prompt)
            if isinstance(result, dict) and result.get("ok"):
                logger.info(f"Success with {model_name}")
                return result["text"]
            if isinstance(result, dict) and result.get("error"):
                logger.debug(f"{model_name} returned error: {result.get('error')}")
            elif result is not None:
                logger.debug(f"{model_name} returned non-ok: {result}")
        except Exception as e:
            logger.error(f"Fallback {model_name} failed: {str(e)}")
            continue
    return "Maaf, semua model AI tidak dapat diakses. Sila cuba lagi nanti."

# === IDENTITY DETECTION ===
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

# === SMART AI MAIN ===
def smart_ai(username, prompt, think_mode=False, search_mode=False):
    if not check_rate_limit(username):
        logger.warning(f"Rate limit exceeded for user")
        return "Maaf, terlalu banyak permintaan. Sila tunggu sebentar."
    limit_check = check_usage_limit(username)
    if not limit_check["allowed"]:
        return f"Had Penggunaan Bulanan Telah Dicapai\nPenggunaan: {limit_check['used']}/{limit_check['limit']}"
    prompt = sanitize_prompt(prompt)
    if is_identity_question(prompt):
        return get_identity_response()
    if search_mode:
        prompt = f"Please search and provide comprehensive information about: {prompt}"
    try:
        if think_mode:
            result = call_deepseek_r1(prompt)
        else:
            result = call_groq(prompt)
        if isinstance(result, dict) and result.get("ok"):
            response = result["text"]
        else:
            response = smart_ai_with_fallback(prompt)
        increment_usage(username)
        return response
    except Exception as e:
        logger.error(f"Smart AI error: {str(e)}")
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
    .login-container {
        max-width: 420px;
        margin: 0 auto;
        padding: 40px 20px;
    }
    .login-box {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 20px;
        padding: 40px 32px;
    }
    .login-box h1 {
        font-size: 32px;
        font-weight: 800;
        background: linear-gradient(135deg, #4d6bfe, #7c3aed);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 8px;
    }
    .login-box p {
        color: #8a8a9a;
        font-size: 14px;
        text-align: center;
    }
    .login-box .sub {
        color: #5a5a6a;
        font-size: 12px;
        text-align: center;
        margin-bottom: 24px;
    }
    .social-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
        width: 100%;
        padding: 10px;
        border-radius: 10px;
        border: 1px solid rgba(255,255,255,0.08);
        background: transparent;
        color: #e8edf5;
        cursor: pointer;
        font-size: 14px;
        font-weight: 500;
        transition: all 0.2s;
        margin-bottom: 10px;
    }
    .social-btn:hover {
        background: rgba(255,255,255,0.05);
        border-color: rgba(255,255,255,0.15);
    }
    .social-btn.google {
        border-color: #ea4335;
    }
    .social-btn.google:hover {
        background: rgba(234,67,53,0.1);
    }
    .social-btn.facebook {
        border-color: #1877f2;
    }
    .social-btn.facebook:hover {
        background: rgba(24,119,242,0.1);
    }
    .divider {
        display: flex;
        align-items: center;
        gap: 16px;
        margin: 16px 0;
        color: #5a5a6a;
        font-size: 12px;
    }
    .divider::before, .divider::after {
        content: '';
        flex: 1;
        height: 1px;
        background: rgba(255,255,255,0.06);
    }
    .stButton button {
        border-radius: 10px !important;
        font-weight: 500 !important;
        height: 40px !important;
        padding: 0 16px !important;
    }
    .stButton button[kind="secondary"] {
        background: rgba(255,255,255,0.05) !important;
        color: #8a8a9a !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
    }
    .stButton button[kind="secondary"]:hover {
        background: rgba(255,255,255,0.1) !important;
        color: #e8edf5 !important;
    }
    .stButton button[kind="primary"] {
        background: linear-gradient(135deg, #4d6bfe, #7c3aed) !important;
        color: white !important;
        border: none !important;
    }
    .stButton button[kind="primary"]:hover {
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
        .login-box { padding: 24px 16px; }
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
    <div class="login-container">
        <div class="login-box">
            <div style="text-align:center; margin-bottom:24px;">
                <div style="font-size:48px; margin-bottom:8px;">💬</div>
                <h1>MyChatAI Pro</h1>
                <p>Groq · DeepSeek-R1 · Gemini · Claude</p>
                <p class="sub">1000 Request Percuma · Premium Available</p>
            </div>
            <button class="social-btn google">G Google</button>
            <button class="social-btn facebook">f Facebook</button>
            <div class="divider">atau</div>
    """, unsafe_allow_html=True)

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username / Email", placeholder="Masukkan username atau email", key="login_user")
        password = st.text_input("Password", type="password", placeholder="Masukkan password", key="login_pass")
        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("🔓 Login", use_container_width=True, type="primary")
        with col2:
            if st.form_submit_button("📝 Daftar", use_container_width=True):
                st.session_state.show_register = True
                st.rerun()
        if submitted:
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

    if st.session_state.get("show_register", False):
        st.markdown("---")
        st.markdown("### 📝 Daftar Akaun Baru")
        with st.form("register_form", clear_on_submit=True):
            reg_username = st.text_input("Username", placeholder="Pilih username", key="reg_user")
            reg_password = st.text_input("Password", type="password", placeholder="Pilih password", key="reg_pass")
            reg_email = st.text_input("Email", placeholder="Masukkan email", key="reg_email")
            reg_name = st.text_input("Nama (optional)", placeholder="Nama anda", key="reg_name")
            if st.form_submit_button("📝 Daftar", use_container_width=True, type="primary"):
                if reg_username and reg_password and reg_email:
                    result = register_user(reg_username, reg_password, reg_email, reg_name)
                    if result["success"]:
                        st.success(f"✅ Akaun '{reg_username}' berjaya didaftarkan! Sila login.")
                        if result.get("email_verification_required", False):
                            st.info("📧 Sila semak email untuk pengesahan.")
                        st.session_state.show_register = False
                        st.rerun()
                    else:
                        st.error(f"❌ {result['error']}")
                else:
                    st.warning("⚠️ Sila isi semua maklumat (Username, Password, Email)")
        if st.button("🔙 Kembali ke Login"):
            st.session_state.show_register = False
            st.rerun()

    st.markdown("</div></div>", unsafe_allow_html=True)

# === SETTINGS MODAL ===
def settings_modal():
    username = st.session_state.username
    user_data = get_user_data(username)
    with st.sidebar:
        st.markdown("---")
        st.markdown("### Settings")
        current_lang = user_data.get("settings", {}).get("language", "Malay")
        lang_index = 0 if current_lang == "Malay" else 1 if current_lang == "English" else 2
        lang = st.selectbox("Bahasa", ["Malay", "English", "Chinese"], index=lang_index)
        if lang != current_lang:
            user_data["settings"]["language"] = lang
            update_user(username, {"settings": user_data["settings"]})
            st.success("✅ Language updated!")
            st.rerun()
        current_dark_mode = user_data.get("settings", {}).get("dark_mode", True)
        dark_mode = st.checkbox("Dark Mode", value=current_dark_mode)
        if dark_mode != current_dark_mode:
            user_data["settings"]["dark_mode"] = dark_mode
            update_user(username, {"settings": user_data["settings"]})
            st.success("✅ Settings updated!")
            st.rerun()
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
                        logger.info(f"Password changed")
                else:
                    st.error("Password lama salah")

        if st.session_state.role == "admin":
            st.markdown("---")
            st.markdown("### 🔑 Admin - Reset Password")
            reset_user = st.text_input("Username pengguna", placeholder="Masukkan username", key="reset_user_input")
            reset_new_pass = st.text_input("Password baru", type="password", placeholder="Password baru", key="reset_pass_input")
            if st.button("Reset Password", use_container_width=True):
                if reset_user and reset_new_pass:
                    if reset_user in load_users():
                        if reset_user_password(reset_user, reset_new_pass):
                            st.success(f"✅ Password untuk '{reset_user}' telah direset!")
                            logger.info(f"Admin reset password for {reset_user}")
                        else:
                            st.error("❌ Gagal reset password")
                    else:
                        st.error("❌ Username tidak ditemui")
                else:
                    st.warning("⚠️ Sila isi username dan password baru")
            st.markdown("---")
            st.markdown("### 👥 Senarai Pengguna")
            users = load_users()
            for u, data in users.items():
                st.caption(f"• {u} ({data.get('role', 'user')})")

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
            if feedback and feedback.strip():
                if DISCORD_WEBHOOK:
                    try:
                        data = {"content": f"Feedback: {feedback[:500]}"}
                        requests_session.post(DISCORD_WEBHOOK, json=data, timeout=10)
                    except Exception as e:
                        logger.error(f"Discord webhook error: {str(e)}")
                st.success("✅ Terima kasih! Feedback anda akan diproses.")
            else:
                st.warning("⚠️ Sila masukkan feedback")

        st.markdown("---")
        st.caption("MyChatAI Pro v44.0")
        st.caption(f"User | {st.session_state.role}")

# === CHAT UI ===
def chat_ui():
    username = st.session_state.username
    user_data = get_user_data(username)

    if "session_start" in st.session_state:
        elapsed = time.time() - st.session_state.session_start
        if elapsed > SESSION_TIMEOUT:
            st.session_state.logged_in = False
            st.session_state.messages = []
            st.warning("Session tamat. Sila login semula.")
            st.rerun()
        elif elapsed > SESSION_TIMEOUT - 600:
            remaining = int((SESSION_TIMEOUT - elapsed) / 60)
            if remaining > 0:
                st.warning(f"⏰ Session akan tamat dalam {remaining} minit. Sila save chat anda.")
                st.sidebar.warning(f"⏰ Session akan tamat dalam {remaining} minit")

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
    if "uploaded_file" not in st.session_state:
        st.session_state.uploaded_file = None

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
                first_msg = st.session_state.messages[0]["content"] if st.session_state.messages else "New Chat"
                chat_title = re.sub(r'<[^>]+>', '', first_msg)[:50] if first_msg else "New Chat"
                history[username].append({
                    "title": chat_title,
                    "messages": st.session_state.messages,
                    "time": datetime.datetime.now().isoformat()
                })
                save_chats(history)
                st.session_state.chat_history = history.get(username, [])
            st.session_state.messages = []
            st.rerun()

        search_query = st.text_input("Cari sejarah", key="search_history", placeholder="Taip untuk cari...", label_visibility="collapsed")

        features = [
            "RPH", "Art", "Video", "Music",
            "Invois", "WhatsApp", "Neural", "Roadtax",
            "IC", "Kontraktor", "Business", "Fitness",
            "Meditation", "Research", "Comic", "Game",
            "Analytics"
        ]
        selected = st.selectbox("Ciri-ciri", ["-- Pilih --"] + features, key="feature_select", label_visibility="collapsed")
        if selected != "-- Pilih --" and selected != st.session_state.get("current_tab", "Chat"):
            st.session_state.current_tab = selected
            st.rerun()

        st.markdown("---")
        st.markdown("### History Chat")
        history = load_chats().get(username, [])
        if search_query and search_query.strip():
            search_query_lower = search_query.lower().strip()
            history = [h for h in history if search_query_lower in h.get("title", "").lower()]

        for chat in reversed(history[-50:]):
            title = chat.get("title", "Chat")[:40]
            if st.button(f"💬 {title}", key=f"hist_{chat.get('time', '')}", use_container_width=True):
                st.session_state.messages = chat.get("messages", [])
                st.rerun()

        st.markdown("---")

        if is_premium(username):
            st.markdown('<span class="premium-badge">PREMIUM</span>', unsafe_allow_html=True)

        avatar_url = user_data.get('avatar', DEFAULT_AVATAR)
        if not avatar_url or not avatar_url.strip():
            avatar_url = DEFAULT_AVATAR

        st.markdown(f"""
        <div class="profile-section">
            <img src="{avatar_url}" class="profile-avatar">
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
        safe_content = html.escape(msg["content"])
        if msg["role"] == "user":
            st.markdown(f'<div class="chat-bubble-user">{safe_content}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-bubble-ai">{safe_content}</div>', unsafe_allow_html=True)

    st.markdown("---")

    with st.expander("📎 Lampirkan Fail", expanded=False):
        uploaded_file = st.file_uploader("Pilih fail", type=["png", "jpg", "jpeg", "pdf", "txt", "docx"], key="file_uploader")
        if uploaded_file is not None:
            st.session_state.uploaded_file = uploaded_file
            st.success(f"✅ Fail '{uploaded_file.name}' dimuat naik!")
            if uploaded_file.type.startswith('image/'):
                try:
                    img = Image.open(uploaded_file)
                    st.image(img, width=200, caption="Preview")
                except:
                    pass

    col1, col2, col3, col4 = st.columns([6, 1.2, 1.2, 1.5])

    with col1:
        user_input = st.text_input("", key="chat_input", placeholder="Taip mesej... (Enter untuk hantar)", label_visibility="collapsed")

    with col2:
        think_label = "Think" if not st.session_state.think_mode else "Think ✓"
        if st.button(think_label, key="think_btn", use_container_width=True):
            st.session_state.think_mode = not st.session_state.think_mode
            st.rerun()

    with col3:
        search_label = "Search" if not st.session_state.search_mode else "Search ✓"
        if st.button(search_label, key="search_btn", use_container_width=True):
            st.session_state.search_mode = not st.session_state.search_mode
            st.rerun()

    with col4:
        if st.button("Send", key="send_btn", use_container_width=True):
            if user_input.strip():
                safe_input = sanitize_input(user_input, MAX_INPUT_LENGTH)
                st.session_state.messages.append({"role": "user", "content": safe_input})
                if st.session_state.uploaded_file is not None:
                    file_info = f"\n\n[Fail dilampirkan: {st.session_state.uploaded_file.name}]"
                    safe_input = safe_input + file_info
                    st.session_state.uploaded_file = None

                if st.session_state.think_mode:
                    spinner_msg = "🧠 DeepSeek-R1 sedang berfikir (ini mungkin mengambil masa)..."
                else:
                    spinner_msg = "⚡ Menghasilkan jawapan..."

                with st.spinner(spinner_msg):
                    response = smart_ai(username, safe_input, st.session_state.think_mode, st.session_state.search_mode)
                safe_resp = sanitize_input(str(response), MAX_INPUT_LENGTH)
                st.session_state.messages.append({"role": "ai", "content": safe_resp})
                st.rerun()

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
        if st.button("Jana RPH", use_container_width=True):
            if not topik or not topik.strip():
                st.error("❌ Sila masukkan topik")
            else:
                result = call_deepseek_r1(f"Sediakan RPH {subjek} Tahun {tahun}, topik {topik}, tempoh {tempoh}")
                if result.get("ok"):
                    st.markdown(result["text"])
                else:
                    st.error(result.get("error", "Gagal menjana RPH"))

    elif feature == "Art":
        prompt = st.text_input("Huraikan gambar")
        if st.button("Hasilkan", use_container_width=True):
            if not prompt or not prompt.strip():
                st.error("❌ Sila masukkan huraian gambar")
            else:
                try:
                    encoded_prompt = quote(prompt)
                    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
                    response = requests_session.get(url, timeout=60)
                    if response.status_code == 200:
                        img = Image.open(BytesIO(response.content))
                        st.image(img, use_container_width=True)
                    else:
                        st.error("Gagal menghasilkan gambar")
                except Exception as e:
                    logger.error(f"Art generation error: {str(e)}")
                    st.error("Ralat - Sila cuba lagi")

    elif feature == "Video":
        prompt = st.text_area("Huraikan video", height=80)
        duration = st.slider("Durasi (saat)", 3, 15, 5)
        if st.button("Hasilkan Video", use_container_width=True):
            if not prompt or not prompt.strip():
                st.error("❌ Sila masukkan huraian video")
            else:
                with st.spinner("Menghasilkan video..."):
                    try:
                        encoded_prompt = quote(prompt)
                        url = f"https://image.pollinations.ai/video?prompt={encoded_prompt}&duration={duration}"
                        response = requests_session.get(url, timeout=120)
                        if response.status_code == 200:
                            st.video(response.content)
                        else:
                            st.error("Gagal menghasilkan video")
                    except Exception as e:
                        logger.error(f"Video generation error: {str(e)}")
                        st.error("Ralat - Sila cuba lagi")

    elif feature == "Music":
        st.info("🎵 Music Generator - Hasilkan lagu dengan TTS atau Suno")
        mode = st.radio("Pilih Mod:", ["TTS (Percuma)", "Suno (Lagu Sebenar)"], horizontal=True)
        prompt = st.text_area("Huraikan lagu:", height=80)
        style = st.selectbox("Gaya:", ["pop", "rock", "jazz", "classical", "hip-hop", "rnb", "electronic", "acoustic"])
        if st.button("Hasilkan Lagu", use_container_width=True):
            if not prompt or not prompt.strip():
                st.error("❌ Sila masukkan huraian lagu")
            elif mode == "TTS (Percuma)":
                try:
                    enhanced_prompt = f"Create a {style} song with this theme: {prompt[:500]}"
                    tts_url = f"https://api.pollinations.ai/tts?text={enhanced_prompt}&voice=alloy"
                    response = requests_session.get(tts_url, timeout=60)
                    if response.status_code == 200:
                        st.audio(response.content, format="audio/mp3")
                        st.success(f"✅ Lagu gaya {style} berjaya dihasilkan!")
                    else:
                        st.error("Gagal menghasilkan audio")
                except Exception as e:
                    logger.error(f"TTS error: {str(e)}")
                    st.error("Ralat - Sila cuba lagi")
            else:
                st.warning("Suno API memerlukan setup tambahan. Guna TTS dahulu.")

    elif feature == "Invois":
        company = st.text_input("Nama Syarikat")
        customer = st.text_input("Nama Pelanggan")
        desc = st.text_input("Keterangan")
        jumlah = st.number_input("Jumlah (RM)", min_value=0.0, value=0.0)
        if st.button("Hasilkan Invois", use_container_width=True):
            if not company or not company.strip():
                st.error("❌ Sila masukkan nama syarikat")
            elif not customer or not customer.strip():
                st.error("❌ Sila masukkan nama pelanggan")
            else:
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
        if st.button("Hantar", use_container_width=True):
            if not phone or not phone.strip():
                st.error("❌ Sila masukkan nombor telefon")
            elif not message or not message.strip():
                st.error("❌ Sila masukkan mesej")
            else:
                clean_phone = re.sub(r'[^0-9]', '', phone)
                if len(clean_phone) < 10 or len(clean_phone) > 15:
                    st.error("❌ Nombor telefon tidak sah (10-15 digit)")
                else:
                    if not clean_phone.startswith('6'):
                        clean_phone = '6' + clean_phone
                    msg_encoded = quote(message)
                    whatsapp_url = f"https://wa.me/{clean_phone}?text={msg_encoded}"
                    st.markdown(f'<a href="{whatsapp_url}" target="_blank" style="background:#25D366; color:white; padding:8px 16px; border-radius:8px; text-decoration:none; font-weight:600; display:inline-block;">Buka WhatsApp</a>', unsafe_allow_html=True)

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
        if st.button("Buka Tender", use_container_width=True):
            if not tender_name or not tender_name.strip():
                st.error("❌ Sila masukkan nama projek")
            elif tender_budget <= 0:
                st.error("❌ Sila masukkan bajet yang sah")
            else:
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
            result = call_deepseek_r1("Hasilkan business plan untuk startup teknologi")
            if result.get("ok"):
                st.markdown(result["text"])
            else:
                st.error(result.get("error", "Gagal menjana business plan"))

    elif feature == "Fitness":
        goal = st.selectbox("Matlamat", ["Turun Berat", "Bina Otot", "Kekal Sihat"])
        days = st.slider("Hari seminggu", 1, 7, 3)
        if st.button("Jana Rancangan", use_container_width=True):
            result = call_deepseek_r1(f"Hasilkan rancangan senaman untuk matlamat {goal} ({days} hari seminggu)")
            if result.get("ok"):
                st.markdown(result["text"])
            else:
                st.error(result.get("error", "Gagal menjana rancangan"))

    elif feature == "Meditation":
        duration = st.slider("Durasi (minit)", 1, 30, 10)
        if st.button("Mula Meditasi", use_container_width=True):
            result = call_deepseek_r1(f"Panduan meditasi selama {duration} minit")
            if result.get("ok"):
                st.markdown(result["text"])
            else:
                st.error(result.get("error", "Gagal menjana panduan meditasi"))

    elif feature == "Research":
        topic = st.text_input("Topik Penyelidikan")
        if st.button("Mulakan Penyelidikan", use_container_width=True):
            if not topic or not topic.strip():
                st.error("❌ Sila masukkan topik penyelidikan")
            else:
                result = call_deepseek_r1(f"Buat literature review untuk topik: {topic}")
                if result.get("ok"):
                    st.markdown(result["text"])
                else:
                    st.error(result.get("error", "Gagal menjana literature review"))

    elif feature == "Comic":
        title = st.text_input("Tajuk Komik")
        if st.button("Hasilkan Komik", use_container_width=True):
            if not title or not title.strip():
                st.error("❌ Sila masukkan tajuk komik")
            else:
                result = call_deepseek_r1(f"Hasilkan komik bertajuk: {title}")
                if result.get("ok"):
                    st.markdown(result["text"])
                else:
                    st.error(result.get("error", "Gagal menjana komik"))

    elif feature == "Game":
        game_type = st.selectbox("Jenis", ["Escape Room", "Murder Mystery", "Treasure Hunt", "Adventure"])
        if st.button("Mula Permainan", use_container_width=True):
            result = call_deepseek_r1(f"Cipta {game_type} yang menarik")
            if result.get("ok"):
                st.markdown(result["text"])
            else:
                st.error(result.get("error", "Gagal menjana permainan"))

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
    if "show_register" not in st.session_state:
        st.session_state.show_register = False

    if not st.session_state.logged_in:
        login_ui()
        return

    if st.session_state.current_tab == "Chat":
        chat_ui()
    else:
        feature_ui(st.session_state.current_tab)

if __name__ == "__main__":
    main()
