# ============================================================
# MyChatAI Pro - Full Code (Gabungan Versi Lama & Baru)
# ============================================================
# Version: v71.5
# Author: Joe Adie
# Copyright: (c) 2026 MyChatAI Pro by Joe Adie
# ============================================================

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
import random
import sys
import io
import base64
import hashlib
import string
from io import BytesIO
from PIL import Image
from collections import defaultdict
from urllib.parse import quote
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging.handlers
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================
# VERSION & APP NAME
# ============================================================
APP_VERSION = "v71.5"
APP_NAME = "MyChatAI Pro"
APP_AUTHOR = "Joe Adie"
APP_COPYRIGHT = f"(c) 2026 {APP_NAME} by {APP_AUTHOR}"

# ============================================================
# LOGGING SETUP
# ============================================================
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

try:
    handler = logging.handlers.RotatingFileHandler('mychat_app.log', maxBytes=5*1024*1024, backupCount=3)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
except Exception:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

# ============================================================
# SECURE LOGGER
# ============================================================
class SecureLogger:
    def __init__(self):
        self.sensitive_patterns = [
            r'password["\']?\s*[:=]\s*["\'][^"\']+["\']',
            r'token["\']?\s*[:=]\s*["\'][^"\']+["\']',
            r'api_key["\']?\s*[:=]\s*["\'][^"\']+["\']',
            r'secret["\']?\s*[:=]\s*["\'][^"\']+["\']',
            r'authorization["\']?\s*[:=]\s*["\'][^"\']+["\']',
            r'bearer\s+[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+',
            r'gsk_[a-zA-Z0-9]+',
            r'sk-or-v1-[a-zA-Z0-9]+',
            r'sk-[a-zA-Z0-9]+',
            r'hf_[a-zA-Z0-9]+',
            r'sess_[a-zA-Z0-9]+',
        ]
        self.redact_email = False

    def sanitize_log(self, message):
        if not message:
            return message
        for pattern in self.sensitive_patterns:
            message = re.sub(pattern, '[REDACTED]', str(message), flags=re.IGNORECASE)
        if self.redact_email:
            message = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '[EMAIL]', message)
        return message

    def log_info(self, message, *args, **kwargs):
        sanitized = self.sanitize_log(str(message))
        logger.info(sanitized, *args, **kwargs)

    def log_error(self, message, *args, **kwargs):
        sanitized = self.sanitize_log(str(message))
        logger.error(sanitized, *args, **kwargs)

    def log_warning(self, message, *args, **kwargs):
        sanitized = self.sanitize_log(str(message))
        logger.warning(sanitized, *args, **kwargs)

secure_logger = SecureLogger()

# ============================================================
# PAGE CONFIG & CSS
# ============================================================
st.set_page_config(
    page_title=f"{APP_NAME} {APP_VERSION}",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stTextArea textarea {
        border: 1px solid #2a2a3a !important;
        border-radius: 8px !important;
        background: #1a1a2a !important;
        color: #e8edf5 !important;
        font-size: 14px !important;
        padding: 12px 16px !important;
    }
    .stTextArea textarea:focus {
        border-color: #4d6bfe !important;
        box-shadow: none !important;
        outline: none !important;
    }
    .stTextArea .stAlert { display: none !important; }
    @keyframes blink {
        0%, 80%, 100% { opacity: 0.2; transform: scale(0.8); }
        40% { opacity: 1; transform: scale(1); }
    }
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #1a1a2a; }
    ::-webkit-scrollbar-thumb { background: #4d6bfe; border-radius: 3px; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stChatMessage { animation: fadeIn 0.3s ease-in-out; }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .stButton > button { transition: all 0.2s ease; border-radius: 8px !important; }
    .stButton > button:hover { transform: scale(1.02); }
    .stChatMessage {
        scroll-behavior: smooth !important;
    }
    .stChatMessage .avatar {
        border-radius: 50% !important;
    }
    .stCaption {
        font-size: 10px !important;
        color: #4a4a5a !important;
        margin-top: 2px !important;
    }
    .stChatMessage[data-testid="user"] {
        background: #2a2a3a !important;
        border-radius: 12px 12px 4px 12px !important;
    }
    .stChatMessage[data-testid="assistant"] {
        background: #1a1a2a !important;
        border-radius: 12px 12px 12px 4px !important;
        border: 1px solid #2a2a3a !important;
    }
    .stChatMessage {
        transition: all 0.3s ease !important;
    }
    .stChatMessage::-webkit-scrollbar {
        width: 4px !important;
    }
    .stChatMessage::-webkit-scrollbar-thumb {
        background: #4d6bfe !important;
        border-radius: 2px !important;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# CONSTANTS
# ============================================================
MAX_MESSAGES = 100
API_TIMEOUT = 30
CACHE_INTERVAL = 10
BATCH_SIZE = 10
TYPING_SPEED_FAST = 0.005
TYPING_SPEED_SLOW = 0.015
MAX_INPUT_LENGTH = 4000
MAX_HISTORY_PER_USER = 50
MAX_CONTEXT_MESSAGES = 10

USER_DATA_FILE = "mychat_users.json"
CHAT_HISTORY_FILE = "mychat_chats.json"
USAGE_FILE = "mychat_usage.json"
CONVERSATION_FLOW_FILE = "conversation_flows.json"
USER_PERSONALITY_FILE = "user_personalities.json"
CONTEXT_MEMORY_FILE = "context_memory.json"
DEFAULT_AVATAR = "https://ui-avatars.com/api/?name=User&background=4d6bfe&color=fff&size=40"
SESSION_TIMEOUT = 31536000
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

# ============================================================
# SESSION SALT
# ============================================================
_SESSION_SALT = st.secrets.get("SESSION_SECRET")
if not _SESSION_SALT:
    secure_logger.log_error("SESSION_SECRET not configured in secrets!")
    st.error("SESSION_SECRET not configured. Please add to .streamlit/secrets.toml")
    st.stop()

# ============================================================
# CACHING
# ============================================================
@st.cache_data(ttl=300)
def load_users_cached():
    return safe_read_json("mychat_users.json", {})

@st.cache_data(ttl=60)
def load_usage_cached(username):
    data = safe_read_json("mychat_usage.json", {})
    return data.get(username, {"count": 0})

# ============================================================
# PORTALOCKER FALLBACK
# ============================================================
try:
    import portalocker
    HAVE_PORTALOCKER = True
except ImportError:
    HAVE_PORTALOCKER = False
    secure_logger.log_warning("portalocker not installed.")

# ============================================================
# REQUESTS SESSION
# ============================================================
def get_requests_session():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET", "POST"])
    adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=20)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    session.headers.update({'User-Agent': f'{APP_NAME}/{APP_VERSION}'})
    return session

requests_session = get_requests_session()

# ============================================================
# SAFE JSON ACCESS
# ============================================================
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

# ============================================================
# SAFE FILE OPERATIONS
# ============================================================
def safe_read_json(filepath, default=None, retries=3):
    for attempt in range(retries):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                if HAVE_PORTALOCKER:
                    try:
                        portalocker.lock(f, portalocker.LOCK_SH)
                    except:
                        pass
                data = json.load(f)
                if HAVE_PORTALOCKER:
                    try:
                        portalocker.unlock(f)
                    except:
                        pass
                return data
        except FileNotFoundError:
            return default if default is not None else {}
        except json.JSONDecodeError as e:
            secure_logger.log_error(f"JSON decode error in {filepath}: {str(e)}")
            return default if default is not None else {}
        except PermissionError as e:
            secure_logger.log_error(f"Permission error in {filepath}: {str(e)}")
            if attempt < retries - 1:
                time.sleep(0.5 * (attempt + 1))
                continue
            return default if default is not None else {}
        except Exception as e:
            secure_logger.log_error(f"Safe read error in {filepath}: {traceback.format_exc()}")
            if attempt < retries - 1:
                time.sleep(0.5 * (attempt + 1))
                continue
            return default if default is not None else {}
    return default if default is not None else {}

def safe_write_json(filepath, data, retries=3):
    temp_file = filepath + ".tmp"
    for attempt in range(retries):
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                if HAVE_PORTALOCKER:
                    try:
                        portalocker.lock(f, portalocker.LOCK_EX)
                    except:
                        pass
                json.dump(data, f, indent=2, ensure_ascii=False)
                if HAVE_PORTALOCKER:
                    try:
                        portalocker.unlock(f)
                    except:
                        pass
            os.replace(temp_file, filepath)
            return True
        except PermissionError as e:
            secure_logger.log_error(f"Permission error writing {filepath}: {str(e)}")
            if attempt < retries - 1:
                time.sleep(0.5 * (attempt + 1))
                continue
        except Exception as e:
            secure_logger.log_error(f"Safe write error in {filepath}: {traceback.format_exc()}")
            if attempt < retries - 1:
                time.sleep(0.5 * (attempt + 1))
                continue
    if os.path.exists(temp_file):
        try:
            os.remove(temp_file)
        except:
            pass
    return False

# ============================================================
# RATE LIMITING
# ============================================================
_rate_limit_cache = {}
_rate_limit_cache_lock = threading.RLock()

def check_rate_limit(username, limit=30, window=60):
    now = time.time()
    with _rate_limit_cache_lock:
        if username not in _rate_limit_cache:
            _rate_limit_cache[username] = []
        _rate_limit_cache[username] = [t for t in _rate_limit_cache[username] if now - t < window]
        if len(_rate_limit_cache[username]) >= limit:
            return False
        _rate_limit_cache[username].append(now)
        return True

# ============================================================
# API KEYS
# ============================================================
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")
OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY", "")
HUGGINGFACE_API_KEY = st.secrets.get("HUGGINGFACE_API_KEY", "")
STABILITY_API_KEY = st.secrets.get("STABILITY_API_KEY", "")
ELEVENLABS_API_KEY = st.secrets.get("ELEVENLABS_API_KEY", "")
SEARCH_API_KEY = st.secrets.get("SEARCH_API_KEY", "")
WEATHER_API_KEY = st.secrets.get("WEATHER_API_KEY", "")
NEWS_API_KEY = st.secrets.get("NEWS_API_KEY", "")

ADMIN_EMAIL = st.secrets.get("ADMIN_EMAIL")
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD")
if not ADMIN_EMAIL or not ADMIN_PASSWORD:
    secure_logger.log_error("ADMIN_EMAIL or ADMIN_PASSWORD missing")
    st.error("Admin credentials not configured.")
    st.stop()

try:
    MAX_FREE_REQUESTS = int(st.secrets.get("MAX_FREE_REQUESTS", 1000))
except (TypeError, ValueError):
    MAX_FREE_REQUESTS = 1000

# ============================================================
# LOAD FUNCTIONS
# ============================================================
def load_users():
    return load_users_cached()

def save_users(data):
    safe_write_json("mychat_users.json", data)
    load_users_cached.clear()

def load_usage(username):
    return load_usage_cached(username)

def save_usage(username, data):
    all_data = safe_read_json("mychat_usage.json", {})
    all_data[username] = data
    safe_write_json("mychat_usage.json", all_data)
    load_usage_cached.clear()

def load_chats():
    return safe_read_json(CHAT_HISTORY_FILE, {})

def save_chats(data):
    safe_write_json(CHAT_HISTORY_FILE, data)

def load_preferences(username):
    prefs_file = f"prefs_{username}.json"
    return safe_read_json(prefs_file, {})

def save_preferences(username, prefs):
    prefs_file = f"prefs_{username}.json"
    safe_write_json(prefs_file, prefs)

def load_api_keys():
    return safe_read_json("api_keys.json", {})

def save_api_keys(data):
    safe_write_json("api_keys.json", data)

# ============================================================
# SMART CACHE
# ============================================================
class SmartCache:
    def __init__(self):
        self.cache = {}
        self.cache_time = {}
        self.cache_access = {}
        self.cache_duration = 3600
        self.max_cache_size = 500
        self.cache_file = "cache_data.json"
        self._cache_counter = 0
        self._lock = threading.RLock()
        self._load_cache_from_file()

    def _load_cache_from_file(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                current_time = time.time()
                for key, value in data.items():
                    if value.get('expires_at', 0) > current_time:
                        self.cache[key] = value.get('response')
                        self.cache_time[key] = value.get('created_at', 0)
                        self.cache_access[key] = value.get('last_access', 0)
            except Exception as e:
                secure_logger.log_error(f"Load cache error: {str(e)}")

    def _save_cache_to_file(self):
        try:
            data = {}
            for key in self.cache:
                data[key] = {
                    'response': self.cache[key],
                    'created_at': self.cache_time.get(key, 0),
                    'expires_at': self.cache_time.get(key, 0) + self.cache_duration,
                    'last_access': self.cache_access.get(key, 0)
                }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            secure_logger.log_error(f"Save cache error: {str(e)}")

    def _cleanup_cache(self):
        with self._lock:
            current_time = time.time()
            expired_keys = [k for k, v in self.cache_time.items() if current_time - v > self.cache_duration]
            for k in expired_keys:
                self.cache.pop(k, None)
                self.cache_time.pop(k, None)
                self.cache_access.pop(k, None)
            if len(self.cache) > self.max_cache_size:
                sorted_keys = sorted(self.cache_access.items(), key=lambda x: x[1])
                to_remove = len(self.cache) - self.max_cache_size
                for k, _ in sorted_keys[:to_remove]:
                    self.cache.pop(k, None)
                    self.cache_time.pop(k, None)
                    self.cache_access.pop(k, None)

    def get_cached_response(self, prompt):
        with self._lock:
            self._cleanup_cache()
            prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
            if prompt_hash in self.cache:
                if time.time() - self.cache_time.get(prompt_hash, 0) < self.cache_duration:
                    self.cache_access[prompt_hash] = time.time()
                    return self.cache[prompt_hash]
            return None

    def save_response(self, prompt, response):
        with self._lock:
            self._cleanup_cache()
            prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
            self.cache[prompt_hash] = response
            self.cache_time[prompt_hash] = time.time()
            self.cache_access[prompt_hash] = time.time()
            self._cache_counter += 1
            if self._cache_counter >= CACHE_INTERVAL:
                self._save_cache_to_file()
                self._cache_counter = 0

smart_cache = SmartCache()

# ============================================================
# TYPING EFFECT
# ============================================================
class TypingEffect:
    def __init__(self):
        self._is_streaming = False

    def stream_response(self, text, placeholder=None):
        if not text:
            yield ""
            return
        if placeholder is None:
            placeholder = st.empty()
        self._is_streaming = True
        try:
            words = text.split()
            accumulated = ""
            if len(text) < 200:
                for char in text:
                    if not self._is_streaming:
                        break
                    accumulated += char
                    placeholder.markdown(accumulated)
                    time.sleep(TYPING_SPEED_FAST)
                yield accumulated
            else:
                for word in words:
                    if not self._is_streaming:
                        break
                    accumulated += word + " "
                    placeholder.markdown(accumulated)
                    time.sleep(TYPING_SPEED_SLOW)
                yield accumulated
        finally:
            self._is_streaming = False

    def stop_streaming(self):
        self._is_streaming = False

typing_effect = TypingEffect()

# ============================================================
# OPENAI SDK VERSION CHECK
# ============================================================
OPENAI_SDK_VERSION = None
OPENAI_AVAILABLE = False
OPENAI_V1 = False
OPENAI_LEGACY = False

try:
    import openai
    OPENAI_AVAILABLE = True
    if hasattr(openai, "__version__"):
        OPENAI_SDK_VERSION = openai.__version__
        ver_parts = OPENAI_SDK_VERSION.split(".")
        if ver_parts and ver_parts[0].isdigit():
            major = int(ver_parts[0])
            if major >= 1:
                OPENAI_V1 = True
            else:
                OPENAI_LEGACY = True
        else:
            OPENAI_LEGACY = True
    elif hasattr(openai, "version"):
        OPENAI_SDK_VERSION = openai.version.VERSION
        OPENAI_LEGACY = True
    else:
        OPENAI_SDK_VERSION = "unknown"
        OPENAI_LEGACY = True
    secure_logger.log_info(f"OpenAI SDK version: {OPENAI_SDK_VERSION}")
except ImportError:
    OPENAI_AVAILABLE = False
    secure_logger.log_warning("OpenAI library not installed")

# ============================================================
# FIREBASE IMPORTS & MANAGER
# ============================================================
FIREBASE_AVAILABLE = False
try:
    import firebase_admin
    from firebase_admin import credentials, firestore, auth
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    secure_logger.log_warning("Firebase admin not installed")

class FirebaseManager:
    def __init__(self):
        self.cred = None
        self.db = None
        self.firebase_available = FIREBASE_AVAILABLE
        self.initialized = False
        self.auth = None
        self._init_firebase()

    def _init_firebase(self):
        if not self.firebase_available:
            secure_logger.log_warning("Firebase not available")
            return
        try:
            firebase_config = st.secrets.get("FIREBASE", {})
            if firebase_config:
                cred_dict = {
                    "type": "service_account",
                    "project_id": firebase_config.get("project_id", ""),
                    "private_key_id": firebase_config.get("private_key_id", ""),
                    "private_key": firebase_config.get("private_key", ""),
                    "client_email": firebase_config.get("client_email", ""),
                    "client_id": firebase_config.get("client_id", ""),
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "client_x509_cert_url": firebase_config.get("client_x509_cert_url", "")
                }
                if cred_dict["private_key"]:
                    cred_dict["private_key"] = cred_dict["private_key"].replace('\\n', '\n')
                if cred_dict["project_id"] and cred_dict["private_key"]:
                    try:
                        try:
                            firebase_admin.get_app()
                        except ValueError:
                            self.cred = credentials.Certificate(cred_dict)
                            firebase_admin.initialize_app(self.cred)
                        self.db = firestore.client()
                        self.auth = auth
                        self.initialized = True
                        secure_logger.log_info("Firebase initialized successfully")
                    except Exception as e:
                        secure_logger.log_error(f"Firebase init error: {str(e)}")
                        self.initialized = False
                else:
                    secure_logger.log_error("Firebase config incomplete")
                    self.initialized = False
            else:
                secure_logger.log_warning("Firebase config not found in secrets")
                self.initialized = False
        except Exception as e:
            secure_logger.log_error(f"Firebase config error: {str(e)}")
            self.initialized = False

    def is_ready(self):
        return self.initialized and self.db is not None

    def login_user(self, email, password):
        if not self.is_ready():
            return {"success": False, "error": "Firebase service not ready"}
        if not email or not password:
            return {"success": False, "error": "Email and password required"}
        try:
            email = email.strip().lower()
            try:
                user = self.auth.get_user_by_email(email)
            except Exception as e:
                return {"success": False, "error": "Email not found. Please register first."}
            if user:
                try:
                    users_ref = self.db.collection("users").document(user.uid)
                    doc = users_ref.get()
                    profile = doc.to_dict() if doc.exists else {}
                    if profile.get("status") == "disabled":
                        return {"success": False, "error": "Account disabled"}
                    return {"success": True, "uid": user.uid, "email": user.email, "profile": profile}
                except Exception as e:
                    return {"success": True, "uid": user.uid, "email": user.email, "profile": {}}
            return {"success": False, "error": "User not found"}
        except Exception as e:
            error_msg = str(e)
            if "EMAIL_NOT_FOUND" in error_msg:
                return {"success": False, "error": "Email not found. Please register first."}
            elif "INVALID_PASSWORD" in error_msg:
                return {"success": False, "error": "Invalid password. Please try again."}
            elif "USER_DISABLED" in error_msg:
                return {"success": False, "error": "Account disabled"}
            else:
                return {"success": False, "error": f"Login failed: {error_msg}"}

    def register_user(self, email, password, name=""):
        if not self.is_ready():
            return {"success": False, "error": "Firebase service not ready"}
        if not email or not password:
            return {"success": False, "error": "Email and password required"}
        try:
            email = email.strip().lower()
            try:
                existing = self.auth.get_user_by_email(email)
                if existing:
                    return {"success": False, "error": "Email already registered. Please login."}
            except:
                pass
            user = self.auth.create_user(email=email, password=password, display_name=name or email.split("@")[0])
            if user:
                users_ref = self.db.collection("users").document(user.uid)
                users_ref.set({
                    "name": name or email.split("@")[0],
                    "email": email,
                    "role": "user",
                    "status": "active",
                    "created": datetime.datetime.now().isoformat(),
                    "last_login": None,
                    "total_requests": 0
                })
                return {"success": True, "uid": user.uid}
            else:
                return {"success": False, "error": "Registration failed"}
        except Exception as e:
            error_msg = str(e)
            if "EMAIL_EXISTS" in error_msg:
                return {"success": False, "error": "Email already registered"}
            elif "WEAK_PASSWORD" in error_msg:
                return {"success": False, "error": "Password too weak. Minimum 6 characters."}
            elif "INVALID_EMAIL" in error_msg:
                return {"success": False, "error": "Invalid email format"}
            else:
                return {"success": False, "error": f"Registration failed: {error_msg}"}

    def increment_usage(self, uid):
        if not self.is_ready():
            return
        try:
            users_ref = self.db.collection("users").document(uid)
            doc = users_ref.get()
            if doc.exists:
                current = doc.to_dict().get("total_requests", 0)
                users_ref.update({"total_requests": current + 1, "last_active": datetime.datetime.now().isoformat()})
            else:
                users_ref.set({"total_requests": 1, "last_active": datetime.datetime.now().isoformat()})
        except Exception as e:
            secure_logger.log_error(f"Usage increment error: {str(e)}")

    def save_chat_message(self, uid, role, content, response=None):
        if not self.is_ready():
            return
        try:
            chat_ref = self.db.collection("users").document(uid).collection("chats")
            data = {"role": role, "content": content[:4000], "timestamp": datetime.datetime.now().isoformat()}
            if response:
                data["response"] = response[:4000]
            chat_ref.add(data)
        except Exception as e:
            secure_logger.log_error(f"Save chat error: {str(e)}")

    def log_activity(self, uid, action):
        if not self.is_ready():
            return
        try:
            activity_ref = self.db.collection("activities")
            activity_ref.add({"uid": uid, "action": action, "timestamp": datetime.datetime.now().isoformat()})
        except Exception as e:
            secure_logger.log_error(f"Log activity error: {str(e)}")

    def backup_chats(self, username, data):
        if not self.is_ready():
            return False
        try:
            self.db.collection("backups").document(username).set({
                "data": data,
                "timestamp": datetime.datetime.now().isoformat()
            })
            return True
        except:
            return False

    def restore_chats(self, username):
        if not self.is_ready():
            return None
        try:
            doc = self.db.collection("backups").document(username).get()
            if doc.exists:
                return doc.to_dict().get("data", {})
        except:
            pass
        return None

firebase_manager = FirebaseManager()

# ============================================================
# CONTEXT MEMORY
# ============================================================
class ContextMemory:
    def __init__(self):
        self.memory_file = CONTEXT_MEMORY_FILE
        self.memory = {}
        self.max_context = MAX_CONTEXT_MESSAGES
        self._load_memory()

    def _load_memory(self):
        self.memory = safe_read_json(self.memory_file, {})

    def _save_memory(self):
        safe_write_json(self.memory_file, self.memory)

    def add_conversation(self, username, question, answer):
        if username not in self.memory:
            self.memory[username] = []
        truncated_question = question[:300] if len(question) > 300 else question
        truncated_answer = answer[:500] if len(answer) > 500 else answer
        self.memory[username].append({
            "question": truncated_question,
            "answer": truncated_answer,
            "time": datetime.datetime.now().isoformat()
        })
        if len(self.memory[username]) > MAX_HISTORY_PER_USER * 2:
            self.memory[username] = self.memory[username][-MAX_HISTORY_PER_USER * 2:]
        self._save_memory()

    def get_context(self, username, max_messages=None):
        if max_messages is None:
            max_messages = self.max_context
        if username in self.memory and self.memory[username]:
            context = self.memory[username][-max_messages:]
            formatted = "Previous conversation:\n"
            for c in context:
                q_text = c['question'][:150] + "..." if len(c['question']) > 150 else c['question']
                a_text = c['answer'][:100] + "..." if len(c['answer']) > 100 else c['answer']
                formatted += f"User: {q_text}\nAssistant: {a_text}\n"
            return formatted
        return ""

    def get_all_memory(self, username):
        if username in self.memory and self.memory[username]:
            context = ""
            for c in self.memory[username]:
                context += f"User: {c['question']}\nAssistant: {c['answer']}\n"
            return context
        return ""

    def clear_user_context(self, username):
        if username in self.memory:
            self.memory[username] = []
            self._save_memory()
            return True
        return False

    def search_memory(self, username, query):
        if username not in self.memory:
            return []
        results = []
        for c in self.memory[username]:
            if query.lower() in c['question'].lower() or query.lower() in c['answer'].lower():
                results.append(c)
        return results

context_memory = ContextMemory()

# ============================================================
# SMART AI FUNCTIONS
# ============================================================
def sanitize_input(text, max_length=MAX_INPUT_LENGTH):
    if not text:
        return ""
    text = html.escape(text)
    text = re.sub(r'<script.*?>.*?</script>', '', text, flags=re.DOTALL)
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
    if len(text) > max_length:
        text = text[:max_length]
    return text

def calculate_confidence(response, prompt):
    if not response or not prompt:
        return 60
    length_score = min(len(response) / 100, 100)
    relevance = 80 if len(response) > len(prompt) else 60
    return int((length_score * 0.4 + relevance * 0.6))

def get_confidence_label(score):
    if score >= 85:
        return "High"
    elif score >= 65:
        return "Medium"
    else:
        return "Low"

def analyze_response(response):
    if not response:
        return {"words": 0, "reading_time": 0, "has_code": False, "has_list": False, "sentiment": "neutral"}, 0
    words = len(response.split())
    reading_time = words / 200
    has_code = "```" in response or "def " in response
    has_list = "1. " in response or "- " in response
    
    positive_words = ["good", "great", "excellent", "amazing", "wonderful", "fantastic", "awesome", "love", "happy", "best"]
    negative_words = ["bad", "terrible", "awful", "horrible", "worst", "hate", "sad", "angry", "frustrated", "disappointed"]
    sentiment_score = 0
    response_lower = response.lower()
    for word in positive_words:
        if word in response_lower:
            sentiment_score += 1
    for word in negative_words:
        if word in response_lower:
            sentiment_score -= 1
    if sentiment_score > 0:
        sentiment = "positive"
    elif sentiment_score < 0:
        sentiment = "negative"
    else:
        sentiment = "neutral"
    
    analysis = {
        "words": words,
        "reading_time": reading_time,
        "has_code": has_code,
        "has_list": has_list,
        "sentiment": sentiment
    }
    score = min(100, words * 2 + (10 if has_code else 0) + (5 if has_list else 0) + (sentiment_score * 5))
    return analysis, max(0, min(100, score))

def safe_rerun():
    st.rerun()

# ============================================================
# AI API CALLS
# ============================================================
def call_groq(prompt, max_tokens=2048, temperature=0.7):
    if not GROQ_API_KEY:
        raise Exception("Groq API key not set")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "llama3-70b-8192",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature
    }
    response = requests_session.post(url, json=data, headers=headers, timeout=API_TIMEOUT)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    raise Exception(f"Groq API error: {response.status_code}")

def call_gemini(prompt, max_tokens=2048, temperature=0.7):
    if not GEMINI_API_KEY:
        raise Exception("Gemini API key not set")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": temperature
        }
    }
    response = requests_session.post(url, json=data, timeout=API_TIMEOUT)
    if response.status_code == 200:
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]
    raise Exception(f"Gemini API error: {response.status_code}")

def call_openai(prompt, max_tokens=2048, temperature=0.7):
    if not OPENAI_API_KEY:
        raise Exception("OpenAI API key not set")
    if OPENAI_V1:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature
        )
        return response.choices[0].message.content
    else:
        openai.api_key = OPENAI_API_KEY
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature
        )
        return response["choices"][0]["message"]["content"]

def call_openrouter(prompt, max_tokens=2048, temperature=0.7):
    if not OPENROUTER_API_KEY:
        raise Exception("OpenRouter API key not set")
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "meta-llama/llama-3.2-3b-instruct:free",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature
    }
    response = requests_session.post(url, json=data, headers=headers, timeout=API_TIMEOUT)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    raise Exception(f"OpenRouter API error: {response.status_code}")

def call_huggingface(prompt, max_tokens=2048, temperature=0.7):
    if not HUGGINGFACE_API_KEY:
        raise Exception("HuggingFace API key not set")
    url = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.1"
    headers = {
        "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": max_tokens,
            "temperature": temperature
        }
    }
    response = requests_session.post(url, json=data, timeout=API_TIMEOUT)
    if response.status_code == 200:
        result = response.json()
        if isinstance(result, list) and len(result) > 0:
            return result[0].get("generated_text", "")
        return str(result)
    raise Exception(f"HuggingFace API error: {response.status_code}")

def call_free_api(prompt):
    try:
        encoded_prompt = quote(prompt[:200])
        url = f"https://hercai.onrender.com/v2/hercai?question={encoded_prompt}"
        response = requests_session.get(url, timeout=API_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            return data.get("reply", "No response from free API")
    except:
        pass
    try:
        url = "https://api.verbis.ai/v1/chat/completions"
        data = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": prompt}]
        }
        response = requests_session.post(url, json=data, timeout=API_TIMEOUT)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
    except:
        pass
    return "I'm currently using free API. Please try again later or configure API keys."

def call_ai_api(prompt, username, max_tokens=2048, temperature=0.7):
    prefs = load_preferences(username)
    model = prefs.get("model", "auto")
    
    if model == "groq" or model == "auto":
        if GROQ_API_KEY:
            try:
                return call_groq(prompt, max_tokens, temperature)
            except Exception as e:
                secure_logger.log_error(f"Groq error: {str(e)}")
    
    if model == "openai" or model == "auto":
        if OPENAI_API_KEY and OPENAI_AVAILABLE:
            try:
                return call_openai(prompt, max_tokens, temperature)
            except Exception as e:
                secure_logger.log_error(f"OpenAI error: {str(e)}")
    
    if model == "gemini" or model == "auto":
        if GEMINI_API_KEY:
            try:
                return call_gemini(prompt, max_tokens, temperature)
            except Exception as e:
                secure_logger.log_error(f"Gemini error: {str(e)}")
    
    if model == "openrouter" or model == "auto":
        if OPENROUTER_API_KEY:
            try:
                return call_openrouter(prompt, max_tokens, temperature)
            except Exception as e:
                secure_logger.log_error(f"OpenRouter error: {str(e)}")
    
    if model == "huggingface" or model == "auto":
        if HUGGINGFACE_API_KEY:
            try:
                return call_huggingface(prompt, max_tokens, temperature)
            except Exception as e:
                secure_logger.log_error(f"HuggingFace error: {str(e)}")
    
    return call_free_api(prompt)

# ============================================================
# SMART AI
# ============================================================
AI_PERSONAS = {
    "Default": "You are a helpful AI assistant.",
    "Teacher": "You are a patient and knowledgeable teacher. Explain concepts clearly with examples.",
    "Mentor": "You are a wise mentor who guides with wisdom and experience.",
    "Friend": "You are a caring friend who listens and supports.",
    "Expert": "You are a subject matter expert who provides deep, technical insights.",
    "Creative": "You are a creative thinker who generates innovative ideas."
}

TONE_PROMPTS = {
    "Professional": "Respond in a professional, formal tone. Use clear and structured language.",
    "Casual": "Respond in a casual, friendly tone. Use conversational language.",
    "Creative": "Respond in a creative, imaginative tone. Use vivid descriptions.",
    "Educational": "Respond in an educational tone. Explain concepts clearly with examples.",
    "Friendly": "Respond in a warm, friendly tone. Be approachable and encouraging."
}

LANG_PROMPTS = {
    "English": "Respond in English.",
    "Bahasa Malaysia": "Balas dalam Bahasa Malaysia.",
    "Chinese": "用中文回答。",
    "Tamil": "தமிழில் பதிலளிக்கவும்."
}

def smart_ai(username, prompt, streaming=False, use_cache=True):
    if not prompt or not prompt.strip():
        return "Please enter a question."
    if not check_rate_limit(username):
        return "Rate limit exceeded. Please wait a moment."
    
    prefs = load_preferences(username)
    tone = prefs.get("tone", "Professional")
    language = prefs.get("language", "English")
    persona = prefs.get("persona", "Default")
    
    context = context_memory.get_context(username)
    all_memory = context_memory.get_all_memory(username)
    
    system_prompt = f"""{AI_PERSONAS.get(persona, AI_PERSONAS["Default"])}
{tone_prompts.get(tone, tone_prompts["Professional"])}
{lang_prompts.get(language, lang_prompts["English"])}

Your responses should be:
- Clear and structured
- Detailed and helpful
- Well-organized with paragraphs and bullet points where appropriate
- In the same language as the user's question

Be concise but comprehensive. Provide examples when helpful.

{context}

Long-term memory:
{all_memory}
"""
    
    full_prompt = f"{system_prompt}\n\nUser question: {prompt}"
    
    if use_cache:
        cached = smart_cache.get_cached_response(full_prompt)
        if cached:
            return cached
    
    try:
        response = call_ai_api(full_prompt, username)
        if response and isinstance(response, str):
            context_memory.add_conversation(username, prompt, response)
            if use_cache:
                smart_cache.save_response(full_prompt, response)
            return response
        return "I could not generate a response. Please try again."
    except Exception as e:
        secure_logger.log_error(f"AI error: {str(e)}")
        return f"Error: {str(e)}"

# ============================================================
# SESSION FUNCTIONS
# ============================================================
def save_session(uid):
    data = safe_read_json("sessions.json", {})
    data[uid] = {
        "uid": uid,
        "timestamp": datetime.datetime.now().isoformat()
    }
    safe_write_json("sessions.json", data)

def load_session(uid):
    data = safe_read_json("sessions.json", {})
    return data.get(uid)

def clear_session(uid):
    data = safe_read_json("sessions.json", {})
    if uid in data:
        del data[uid]
        safe_write_json("sessions.json", data)

def check_auto_login():
    try:
        if "session_id" in st.session_state:
            uid = st.session_state.session_id
            if uid:
                session = load_session(uid)
                if session:
                    session_time = datetime.datetime.fromisoformat(session["timestamp"])
                    if (datetime.datetime.now() - session_time).total_seconds() < 86400:
                        if firebase_manager.is_ready():
                            try:
                                user = firebase_manager.auth.get_user(uid)
                                if user:
                                    st.session_state.logged_in = True
                                    st.session_state.uid = uid
                                    st.session_state.email = user.email
                                    st.session_state.username = user.display_name or "User"
                                    st.session_state.role = "user"
                                    return True
                            except:
                                pass
        return False
    except Exception as e:
        secure_logger.log_error(f"Auto login error: {str(e)}")
        return False

def get_session_history():
    history_file = "login_history.json"
    data = safe_read_json(history_file, {})
    return data.get(st.session_state.get("email", ""), [])

def add_session_history(email, action, ip="local"):
    history_file = "login_history.json"
    data = safe_read_json(history_file, {})
    if email not in data:
        data[email] = []
    data[email].append({
        "action": action,
        "time": datetime.datetime.now().isoformat(),
        "ip": ip
    })
    if len(data[email]) > 100:
        data[email] = data[email][-100:]
    safe_write_json(history_file, data)

# ============================================================
# LOCAL LOGIN FUNCTIONS WITH BCRYPT
# ============================================================
def hash_password(password):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def local_login(email, password):
    users = load_users()
    if email in users:
        user = users[email]
        if verify_password(password, user.get("password", "")):
            add_session_history(email, "login")
            return {
                "success": True,
                "uid": email,
                "email": email,
                "profile": {"name": user.get("name", "User"), "role": user.get("role", "user")}
            }
        else:
            add_session_history(email, "failed_login")
            return {"success": False, "error": "Invalid password. Please try again."}
    else:
        add_session_history(email, "failed_login")
        return {"success": False, "error": "Email not found. Please register first."}

def local_register(email, password, name=""):
    users = load_users()
    if email in users:
        return {"success": False, "error": "Email already registered. Please login."}
    users[email] = {
        "name": name or email.split("@")[0],
        "password": hash_password(password),
        "role": "user",
        "created": datetime.datetime.now().isoformat(),
        "last_login": None,
        "total_requests": 0,
        "subscription": "Free"
    }
    save_users(users)
    add_session_history(email, "register")
    return {"success": True, "uid": email}

def local_add_admin(email, password, name="Admin"):
    users = load_users()
    if email in users:
        users[email]["role"] = "admin"
        users[email]["name"] = name
        save_users(users)
        return {"success": True, "message": f"Admin {email} updated"}
    users[email] = {
        "name": name,
        "password": hash_password(password),
        "role": "admin",
        "created": datetime.datetime.now().isoformat(),
        "last_login": None,
        "total_requests": 0,
        "subscription": "Enterprise"
    }
    save_users(users)
    return {"success": True, "message": f"Admin {email} created"}

def local_list_users():
    users = load_users()
    user_list = []
    for email, data in users.items():
        user_list.append({
            "email": email,
            "name": data.get("name", ""),
            "role": data.get("role", "user"),
            "created": data.get("created", ""),
            "subscription": data.get("subscription", "Free")
        })
    return user_list

def local_change_password(email, current, new):
    users = load_users()
    if email in users and verify_password(current, users[email]["password"]):
        users[email]["password"] = hash_password(new)
        save_users(users)
        return {"success": True}
    return {"success": False, "error": "Current password is incorrect"}

def local_reset_password(email, new):
    users = load_users()
    if email in users:
        users[email]["password"] = hash_password(new)
        save_users(users)
        return {"success": True}
    return {"success": False, "error": "Email not found"}

def local_delete_user(email):
    users = load_users()
    if email in users:
        del users[email]
        save_users(users)
        return {"success": True}
    return {"success": False, "error": "User not found"}

# ============================================================
# CHAT MANAGEMENT FUNCTIONS
# ============================================================
def generate_chat_title(messages):
    if not messages:
        return "New Chat"
    for msg in messages:
        if msg.get("role") == "user":
            content = msg.get("content", "").strip()
            content = re.sub(r'[?¿!¡]', '', content)
            content = re.sub(r'^(what|how|why|when|where|who|which|can you|please|tell me|explain|write|create|generate|help me)\s+', '', content, flags=re.IGNORECASE)
            if content:
                content = content[0].upper() + content[1:] if len(content) > 1 else content.upper()
            if len(content) > 35:
                content = content[:35] + "..."
            return content if content else "New Chat"
    return "New Chat"

def delete_chat_from_history(username, chat_index):
    history = load_chats()
    if username in history and 0 <= chat_index < len(history[username]):
        del history[username][chat_index]
        save_chats(history)
        return True
    return False

def update_chat_title(username, chat_index, new_title):
    history = load_chats()
    if username in history and 0 <= chat_index < len(history[username]):
        history[username][chat_index]["title"] = new_title
        save_chats(history)
        return True
    return False

def pin_chat(username, idx):
    history = load_chats()
    if username in history and 0 <= idx < len(history[username]):
        history[username][idx]["pinned"] = not history[username][idx].get("pinned", False)
        save_chats(history)
        return True
    return False

def unpin_chat(username, idx):
    history = load_chats()
    if username in history and 0 <= idx < len(history[username]):
        history[username][idx]["pinned"] = False
        save_chats(history)
        return True
    return False

def search_chats(username, query):
    history = load_chats()
    if username not in history:
        return []
    results = []
    for idx, chat in enumerate(history[username]):
        for msg in chat.get("messages", []):
            if query.lower() in msg.get("content", "").lower():
                results.append({"idx": idx, "title": chat.get("title", "New Chat"), "preview": msg.get("content", "")[:80] + "..."})
                break
    return results

def group_chats_by_date(username):
    history = load_chats()
    if username not in history:
        return {}
    today = datetime.datetime.now().date()
    yesterday = today - datetime.timedelta(days=1)
    grouped = {"Today": [], "Yesterday": [], "Older": []}
    for chat in history[username]:
        try:
            d = datetime.datetime.fromisoformat(chat.get("time", "")).date()
        except:
            d = today
        if d == today:
            grouped["Today"].append(chat)
        elif d == yesterday:
            grouped["Yesterday"].append(chat)
        else:
            grouped["Older"].append(chat)
    return {k: v for k, v in grouped.items() if v}

def export_chats_json(username):
    history = load_chats()
    if username not in history:
        return None
    return json.dumps({
        "app": APP_NAME,
        "username": username,
        "date": datetime.datetime.now().isoformat(),
        "chats": history[username]
    }, indent=2)

def import_chats_json(username, data):
    try:
        if isinstance(data, str):
            data = json.loads(data)
        history = load_chats()
        if username not in history:
            history[username] = []
        if "chats" in data:
            history[username].extend(data["chats"])
        else:
            history[username].append(data)
        save_chats(history)
        return True
    except:
        return False

# ============================================================
# TAMBAHAN: STREAMING RESPONSE
# ============================================================
def stream_response(text, placeholder):
    if not text:
        return
    words = text.split()
    accumulated = ""
    for word in words:
        accumulated += word + " "
        placeholder.markdown(accumulated + "▌")
        time.sleep(0.03)
    placeholder.markdown(accumulated)

# ============================================================
# TAMBAHAN: WEB SEARCH
# ============================================================
def web_search(query):
    try:
        url = f"https://api.duckduckgo.com/?q={quote(query)}&format=json"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            results = []
            for result in data.get("RelatedTopics", [])[:5]:
                if "Text" in result:
                    results.append({
                        "title": result.get("Text", "").split(" - ")[0],
                        "snippet": result.get("Text", ""),
                        "link": result.get("FirstURL", "")
                    })
            return results
    except:
        pass
    return []

# ============================================================
# TAMBAHAN: IMAGE GENERATION
# ============================================================
def generate_image(prompt):
    if STABILITY_API_KEY:
        try:
            url = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"
            headers = {
                "Authorization": f"Bearer {STABILITY_API_KEY}",
                "Content-Type": "application/json"
            }
            data = {
                "text_prompts": [{"text": prompt}],
                "cfg_scale": 7,
                "height": 1024,
                "width": 1024,
                "samples": 1,
                "steps": 30
            }
            response = requests_session.post(url, json=data, headers=headers, timeout=API_TIMEOUT)
            if response.status_code == 200:
                result = response.json()
                if "artifacts" in result and len(result["artifacts"]) > 0:
                    image_data = result["artifacts"][0]["base64"]
                    return f"data:image/png;base64,{image_data}"
        except:
            pass
    
    if OPENAI_API_KEY:
        try:
            if OPENAI_V1:
                client = openai.OpenAI(api_key=OPENAI_API_KEY)
                response = client.images.generate(
                    model="dall-e-3",
                    prompt=prompt,
                    size="1024x1024",
                    quality="standard",
                    n=1
                )
                return response.data[0].url
            else:
                openai.api_key = OPENAI_API_KEY
                response = openai.Image.create(
                    prompt=prompt,
                    n=1,
                    size="1024x1024"
                )
                return response["data"][0]["url"]
        except:
            pass
    
    try:
        encoded = quote(prompt)
        return f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024"
    except:
        return None

# ============================================================
# TAMBAHAN: VOICE INPUT
# ============================================================
def voice_input():
    try:
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            st.info("Listening... Speak now!")
            audio = recognizer.listen(source, timeout=5)
            text = recognizer.recognize_google(audio)
            return text
    except ImportError:
        return None
    except:
        return None

# ============================================================
# TAMBAHAN: TEXT-TO-SPEECH
# ============================================================
def text_to_speech(text):
    if ELEVENLABS_API_KEY:
        try:
            url = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM"
            headers = {
                "xi-api-key": ELEVENLABS_API_KEY,
                "Content-Type": "application/json"
            }
            data = {
                "text": text,
                "model_id": "eleven_monolingual_v1",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.5
                }
            }
            response = requests_session.post(url, json=data, headers=headers, timeout=API_TIMEOUT)
            if response.status_code == 200:
                return response.content
        except:
            pass
    
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
        return True
    except:
        return False

# ============================================================
# TAMBAHAN: CHAT EXPORT PDF
# ============================================================
def export_chat_pdf(username, messages):
    try:
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt=f"{APP_NAME} - {username}", ln=True, align='C')
        pdf.cell(200, 10, txt=f"Exported: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True, align='C')
        pdf.ln(10)
        for msg in messages:
            role = "You" if msg["role"] == "user" else APP_NAME
            pdf.multi_cell(0, 10, txt=f"{role}: {msg['content']}")
            pdf.ln(5)
        return pdf.output(dest='S').encode('latin1')
    except:
        return None

# ============================================================
# TAMBAHAN: CHAT TEMPLATES
# ============================================================
CHAT_TEMPLATES = {
    "Meeting Notes": "Create meeting notes for a team meeting about [topic]. Include agenda, decisions, and action items.",
    "Email Draft": "Draft a professional email to [recipient] about [subject]. Include a clear subject line, greeting, body, and closing.",
    "Code Review": "Review this code and provide feedback: [code]",
    "Lesson Plan": "Create a lesson plan for [subject] for [grade level] students.",
    "Resume Review": "Review this resume and provide feedback: [resume]",
    "Interview Prep": "Prepare interview questions for a [position] role."
}

# ============================================================
# TAMBAHAN: MULTI-MODEL COMPARISON
# ============================================================
def compare_models(prompt):
    results = {}
    models = ["groq", "gemini", "openai", "openrouter", "huggingface"]
    for model in models:
        try:
            if model == "groq" and GROQ_API_KEY:
                results["Groq"] = call_groq(prompt)
            elif model == "gemini" and GEMINI_API_KEY:
                results["Gemini"] = call_gemini(prompt)
            elif model == "openai" and OPENAI_API_KEY:
                results["OpenAI"] = call_openai(prompt)
            elif model == "openrouter" and OPENROUTER_API_KEY:
                results["OpenRouter"] = call_openrouter(prompt)
            elif model == "huggingface" and HUGGINGFACE_API_KEY:
                results["HuggingFace"] = call_huggingface(prompt)
        except:
            pass
    return results

# ============================================================
# TAMBAHAN: CHAIN OF THOUGHT
# ============================================================
def chain_of_thought(prompt):
    thought_prompt = f"""Please solve this problem step by step. Show your reasoning at each step.
    
Problem: {prompt}

Step 1: Understand the problem
Step 2: Break it down
Step 3: Solve each part
Step 4: Combine the solution
Step 5: Verify the answer

Show each step clearly."""
    return call_ai_api(thought_prompt, st.session_state.get("username", "User"))

# ============================================================
# SUBSCRIPTION PLANS
# ============================================================
SUBSCRIPTION_PLANS = {
    "Free": {"requests": 50, "price": 0},
    "Pro": {"requests": 500, "price": 29},
    "Enterprise": {"requests": "Unlimited", "price": 99}
}

def check_subscription(username):
    users = load_users()
    if username in users:
        return users[username].get("subscription", "Free")
    return "Free"

def get_remaining_requests(username):
    usage = load_usage(username)
    total = usage.get("total", 0)
    plan = check_subscription(username)
    limit = SUBSCRIPTION_PLANS.get(plan, {}).get("requests", 50)
    if plan == "Enterprise":
        return "Unlimited"
    return max(0, limit - total)

# ============================================================
# TAMBAHAN: API KEY GENERATION
# ============================================================
def generate_api_key(username):
    api_keys = safe_read_json("api_keys.json", {})
    if username not in api_keys:
        api_key = secrets.token_hex(32)
        api_keys[username] = {
            "key": api_key,
            "created": datetime.datetime.now().isoformat()
        }
        safe_write_json("api_keys.json", api_keys)
        return api_key
    return api_keys[username]["key"]

def verify_api_key(api_key):
    api_keys = safe_read_json("api_keys.json", {})
    for username, data in api_keys.items():
        if data.get("key") == api_key:
            return username
    return None

# ============================================================
# LOGIN UI
# ============================================================
def login_ui():
    st.markdown("""
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;padding:20px;">
        <div style="max-width:420px;width:100%;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:16px;padding:40px 32px;">
            <div style="text-align:center;margin-bottom:30px;">
                <div style="width:48px;height:48px;background:#4d6bfe;border-radius:12px;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:24px;color:white;margin:0 auto 12px auto;">A</div>
                <h1 style="font-size:28px;font-weight:700;color:#e8edf5;letter-spacing:-0.5px;">{APP_NAME}</h1>
                <p style="color:#8a8a9a;font-size:14px;margin-top:4px;">Advanced AI Assistant</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if firebase_manager.is_ready():
            st.success("Firebase Connected")
        else:
            st.info("Using Local Login")
        
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="Enter your email", key="login_email")
            password = st.text_input("Password", type="password", placeholder="Enter your password", key="login_password")
            remember_me = st.checkbox("Remember Me", value=True)
            
            if st.form_submit_button("Login", use_container_width=True, type="primary"):
                if not email or not password:
                    st.warning("Please enter email and password")
                else:
                    with st.spinner("Logging in..."):
                        if firebase_manager.is_ready():
                            result = firebase_manager.login_user(email, password)
                        else:
                            result = local_login(email, password)
                        if result["success"]:
                            st.session_state.logged_in = True
                            st.session_state.uid = result["uid"]
                            st.session_state.email = result["email"]
                            profile = result.get("profile", {})
                            st.session_state.username = profile.get("name", email.split("@")[0])
                            st.session_state.role = profile.get("role", "user")
                            st.session_state.messages = []
                            if remember_me:
                                save_session(result["uid"])
                            st.success(f"Welcome {st.session_state.username}!")
                            st.balloons()
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error(result.get("error", "Login failed"))
        
        st.divider()
        with st.expander("Create New Account"):
            with st.form("register_form"):
                reg_email = st.text_input("Email", placeholder="Enter your email", key="reg_email")
                reg_password = st.text_input("Password", type="password", placeholder="Password (min 6 chars)", key="reg_password")
                reg_name = st.text_input("Display Name", placeholder="Your name", key="reg_name")
                if st.form_submit_button("Register", use_container_width=True):
                    if not reg_email or not reg_password:
                        st.warning("Please fill in email and password")
                    elif len(reg_password) < 6:
                        st.warning("Password must be at least 6 characters")
                    else:
                        with st.spinner("Creating account..."):
                            if firebase_manager.is_ready():
                                result = firebase_manager.register_user(reg_email, reg_password, reg_name)
                            else:
                                result = local_register(reg_email, reg_password, reg_name)
                            if result["success"]:
                                st.success("Account created successfully! Please login.")
                                st.balloons()
                                st.session_state.login_email = reg_email
                                st.rerun()
                            else:
                                st.error(result.get("error", "Registration failed"))

# ============================================================
# DISPLAY CHAT MESSAGES
# ============================================================
def display_chat_messages():
    for idx, msg in enumerate(st.session_state.messages):
        if msg["role"] == "user":
            avatar_letter = st.session_state.get("username", "U")[0].upper()
            with st.chat_message("user", avatar=avatar_letter):
                st.markdown(msg["content"])
                st.caption(f"You - {msg.get('timestamp', 'Just now')}")
                if st.button("Edit", key=f"edit_{idx}"):
                    st.session_state[f"editing_{idx}"] = True
                if st.session_state.get(f"editing_{idx}", False):
                    new_msg = st.text_input("", value=msg["content"], key=f"edit_input_{idx}")
                    if st.button("Save", key=f"edit_save_{idx}"):
                        msg["content"] = new_msg
                        st.session_state.messages = st.session_state.messages[:idx+1]
                        process_chat_message(new_msg)
                        st.rerun()
        else:
            with st.chat_message("assistant", avatar="A"):
                st.markdown(msg["content"])
                word_count = len(msg["content"].split())
                model_used = st.session_state.get("selected_model", "Auto")
                st.caption(f"{APP_NAME} - {msg.get('timestamp', 'Just now')} - {word_count} words - Model: {model_used}")
                col1, col2, col3, col4 = st.columns([1, 1, 1, 7])
                with col1:
                    if st.button("Copy", key=f"copy_{idx}"):
                        st.toast("Copied to clipboard!", icon="")
                with col2:
                    if st.button("Regenerate", key=f"regen_{idx}"):
                        st.session_state.messages = st.session_state.messages[:idx]
                        if st.session_state.messages:
                            process_chat_message(st.session_state.messages[-1]["content"])
                        st.rerun()
                with col3:
                    if st.button("Like", key=f"good_{idx}"):
                        st.toast("Thanks for the feedback!")
                with col4:
                    if st.button("Dislike", key=f"bad_{idx}"):
                        st.toast("Feedback noted. We will improve!")

# ============================================================
# PROCESS CHAT MESSAGE
# ============================================================
def process_chat_message(message):
    username = st.session_state.username
    uid = st.session_state.get("uid")
    safe_input = sanitize_input(message, MAX_INPUT_LENGTH)
    
    # Content moderation
    toxic_words = ["hate", "kill", "stupid", "idiot", "fool", "dumb", "useless", "worthless"]
    if any(word in safe_input.lower() for word in toxic_words):
        st.warning("Your message contains inappropriate content. Please rephrase.")
        return
    
    if uid and firebase_manager.is_ready():
        firebase_manager.save_chat_message(uid, "user", safe_input)
    
    st.session_state.messages.append({"role": "user", "content": safe_input})
    st.session_state.is_thinking = True
    st.rerun()
    
    placeholder = st.empty()
    with st.spinner("Thinking..."):
        response_text = smart_ai(username, safe_input, False, False)
        accumulated = ""
        if isinstance(response_text, str):
            words = response_text.split()
            if len(response_text) < 200:
                for char in response_text:
                    accumulated += char
                    placeholder.markdown(accumulated)
                    time.sleep(TYPING_SPEED_FAST)
            else:
                for word in words:
                    accumulated += word + " "
                    placeholder.markdown(accumulated)
                    time.sleep(TYPING_SPEED_SLOW)
            
            safe_resp = sanitize_input(response_text, MAX_INPUT_LENGTH)
            timestamp = datetime.datetime.now().strftime("%I:%M %p")
            st.session_state.messages.append({"role": "ai", "content": safe_resp, "timestamp": timestamp})
            
            title = generate_chat_title(st.session_state.messages)
            history = load_chats()
            if username not in history:
                history[username] = []
            
            if st.session_state.messages:
                first_msg = st.session_state.messages[0].get("content", "")
                existing_index = None
                for i, chat in enumerate(history[username]):
                    if chat.get("messages", []) and chat["messages"][0].get("content") == first_msg:
                        existing_index = i
                        break
                
                chat_data = {
                    "title": title,
                    "messages": st.session_state.messages,
                    "time": datetime.datetime.now().isoformat()
                }
                if existing_index is not None:
                    history[username][existing_index] = chat_data
                else:
                    history[username].append(chat_data)
                save_chats(history)
            
            if uid and firebase_manager.is_ready():
                firebase_manager.save_chat_message(uid, "ai", safe_resp, safe_resp)
        else:
            safe_resp = sanitize_input(str(response_text), MAX_INPUT_LENGTH)
            st.session_state.messages.append({"role": "ai", "content": safe_resp})
            if uid and firebase_manager.is_ready():
                firebase_manager.save_chat_message(uid, "ai", safe_resp, safe_resp)
        
        placeholder.empty()
        st.session_state.is_thinking = False
        st.rerun()

# ============================================================
# CHAT UI
# ============================================================
def chat_ui():
    username = st.session_state.username
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "is_thinking" not in st.session_state:
        st.session_state.is_thinking = False
    
    # Welcome / Empty state
    if not st.session_state.messages:
        st.markdown(f"""
        <div style="text-align:center;padding:60px 20px 20px 20px;">
            <div style="font-size:32px;font-weight:600;color:#e8edf5;margin-bottom:8px;">Welcome back, {username}</div>
            <div style="font-size:16px;color:#6a6a7a;margin-bottom:24px;">How can I help you today?</div>
            <div style="font-size:9px;color:#3a3a4a;margin-top:20px;">{APP_COPYRIGHT}</div>
        </div>
        """, unsafe_allow_html=True)
        examples = [
            "What is artificial intelligence?",
            "Write a Python script to sort a list",
            "Explain quantum computing in simple terms",
            "How to improve productivity?"
        ]
        cols = st.columns(2)
        for idx, q in enumerate(examples):
            with cols[idx % 2]:
                if st.button(q, use_container_width=True, key=f"example_{idx}"):
                    process_chat_message(q)
                    st.rerun()
        return
    
    # Display messages
    display_chat_messages()
    
    # Thinking animation
    if st.session_state.is_thinking:
        st.markdown("""
        <div style="display:flex;justify-content:flex-start;margin:8px 0;">
            <div style="background:#1a1a2a;padding:10px 16px;border-radius:12px;border:1px solid #2a2a3a;">
                <div style="display:flex;align-items:center;gap:8px;">
                    <span style="font-size:14px;color:#6a6a7a;">Thinking</span>
                    <span style="display:inline-flex;gap:4px;">
                        <span style="width:6px;height:6px;background:#4d6bfe;border-radius:50%;animation:blink 1.4s infinite both;animation-delay:0s;"></span>
                        <span style="width:6px;height:6px;background:#4d6bfe;border-radius:50%;animation:blink 1.4s infinite both;animation-delay:0.2s;"></span>
                        <span style="width:6px;height:6px;background:#4d6bfe;border-radius:50%;animation:blink 1.4s infinite both;animation-delay:0.4s;"></span>
                    </span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Chat input
    user_input = st.chat_input("Type your message... (Ctrl+Enter to send)")
    if user_input:
        safe_input = re.sub(r'<[^>]+>', '', user_input).strip()
        if safe_input:
            process_chat_message(safe_input)
            st.rerun()

# ============================================================
# POSTER GENERATOR
# ============================================================
def poster_generator_ui():
    st.markdown("### Poster Generator")
    
    if not OPENAI_API_KEY and not STABILITY_API_KEY:
        st.info("Using free image generation. Add OpenAI or Stability AI API key for higher quality.")
    
    title = st.text_input("Title", placeholder="e.g., AI Conference 2026", key="poster_title")
    if not title:
        st.info("Please enter a title to generate poster")
        return
    
    col1, col2, col3 = st.columns(3)
    with col1:
        style = st.selectbox("Style", ["Modern Minimalist", "Cinematic", "Cyberpunk", "Photorealistic", "Digital Art", "Vintage", "Retro", "Futuristic", "Nature"])
        size = st.selectbox("Size", ["Square (1024x1024)", "Portrait (768x1024)", "Landscape (1024x768)"])
    with col2:
        color = st.selectbox("Color Palette", ["Blue & Purple", "Red & Gold", "Dark & Neon", "Pastel", "Monochrome", "Warm Sunset", "Cool Ocean", "Forest Green"])
        font_style = st.selectbox("Font Style", ["Modern Sans", "Classic Serif", "Bold Display", "Handwritten", "Minimal"])
    with col3:
        additional_text = st.text_input("Additional Text (optional)", placeholder="e.g., Register Now!")
        use_premium = st.checkbox("Use Premium AI", value=bool(OPENAI_API_KEY or STABILITY_API_KEY), disabled=not bool(OPENAI_API_KEY or STABILITY_API_KEY))
    
    if "poster_history" not in st.session_state:
        st.session_state.poster_history = []
    
    if st.button("Generate Poster", use_container_width=True, type="primary"):
        if title:
            with st.spinner("Generating poster..."):
                try:
                    size_map = {
                        "Square (1024x1024)": "1024x1024",
                        "Portrait (768x1024)": "768x1024",
                        "Landscape (1024x768)": "1024x768"
                    }
                    img_size = size_map.get(size, "1024x1024")
                    
                    prompt = f"Create a {style} poster design for '{title}', {color} color scheme, high quality, 4K"
                    if additional_text:
                        prompt += f", with text '{additional_text}'"
                    
                    image_result = generate_image(prompt)
                    if image_result:
                        if image_result.startswith("data:image"):
                            import base64
                            image_data = base64.b64decode(image_result.split(",")[1])
                            img = Image.open(BytesIO(image_data))
                        else:
                            img_response = requests_session.get(image_result, timeout=30)
                            if img_response.status_code == 200:
                                img = Image.open(BytesIO(img_response.content))
                            else:
                                st.error("Failed to generate poster")
                                return
                        
                        st.image(img, caption=title, use_container_width=True)
                        st.session_state.poster_history.append({
                            "title": title,
                            "style": style,
                            "time": datetime.datetime.now().strftime("%I:%M %p")
                        })
                        img_bytes = BytesIO()
                        img.save(img_bytes, format='PNG')
                        st.download_button("Download Poster", img_bytes.getvalue(), f"poster_{title.replace(' ', '_')}.png", "image/png")
                    else:
                        st.error("Failed to generate poster")
                except Exception as e:
                    st.error(f"Error: {str(e)}")
    
    if st.session_state.poster_history:
        with st.expander("Poster History"):
            for item in st.session_state.poster_history[-5:]:
                st.caption(f"{item['title']} - {item['style']} - {item['time']}")

# ============================================================
# VIDEO GENERATOR
# ============================================================
def video_generator_ui():
    st.markdown("### Video Generator")
    
    prompt = st.text_area("Describe the video", height=80, placeholder="e.g., A futuristic city with flying cars")
    if not prompt:
        st.info("Please describe the video you want to generate")
        return
    
    col1, col2, col3 = st.columns(3)
    with col1:
        duration = st.slider("Duration (seconds)", 3, 15, 5)
        resolution = st.selectbox("Resolution", ["480p", "720p", "1080p"])
    with col2:
        style = st.selectbox("Video Style", ["Cinematic", "Animation", "Realistic", "Cartoon", "Sci-Fi", "Nature"])
        aspect_ratio = st.selectbox("Aspect Ratio", ["16:9", "9:16", "1:1"])
    with col3:
        background_music = st.selectbox("Background Music", ["None", "Ambient", "Epic", "Calm", "Upbeat"])
        subtitles = st.checkbox("Add Subtitles", value=False)
    
    if st.button("Generate Video", use_container_width=True, type="primary"):
        if prompt:
            with st.spinner("Generating video..."):
                try:
                    enhanced_prompt = f"{prompt}, {style} style, {resolution}, {aspect_ratio} ratio"
                    if background_music != "None":
                        enhanced_prompt += f", with {background_music} background music"
                    if subtitles:
                        enhanced_prompt += ", with subtitles"
                    
                    encoded_prompt = quote(enhanced_prompt[:200])
                    url = f"https://image.pollinations.ai/video?prompt={encoded_prompt}&duration={duration}"
                    response = requests_session.get(url, timeout=API_TIMEOUT)
                    if 200 <= response.status_code < 300:
                        st.video(response.content)
                        st.success("Video generated successfully!")
                        st.download_button(
                            "Download Video",
                            response.content,
                            f"video_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4",
                            "video/mp4"
                        )
                    else:
                        st.error("Failed to generate video")
                except Exception as e:
                    st.error(f"Error: {str(e)}")

# ============================================================
# WAZE FEATURES
# ============================================================
def waze_map_free():
    st.markdown("### Waze Live Map")
    
    search_location = st.text_input("Search Location", placeholder="e.g., Kuala Lumpur")
    if search_location:
        st.info(f"Searching for: {search_location}")
        lat = 3.1585
        lon = 101.7118
    else:
        col1, col2 = st.columns(2)
        with col1:
            lat = st.number_input("Latitude", value=3.1585, format="%.4f")
        with col2:
            lon = st.number_input("Longitude", value=101.7118, format="%.4f")
    
    zoom = st.slider("Zoom Level", 5, 17, 14)
    route_options = st.selectbox("Route Options", ["Fastest", "Shortest", "Avoid Toll", "Avoid Highways"])
    st.caption(f"Route: {route_options}")
    
    if "favourite_places" not in st.session_state:
        st.session_state.favourite_places = []
    
    with st.expander("Favourite Places"):
        col1, col2 = st.columns(2)
        with col1:
            fav_name = st.text_input("Place Name", placeholder="e.g., Home")
        with col2:
            fav_address = st.text_input("Address", placeholder="e.g., 123 Jalan...")
        if st.button("Add Favourite"):
            if fav_name and fav_address:
                st.session_state.favourite_places.append({"name": fav_name, "address": fav_address})
                st.success(f"Added: {fav_name}")
                st.rerun()
        
        if st.session_state.favourite_places:
            for fav in st.session_state.favourite_places[-5:]:
                st.caption(f"- {fav['name']}: {fav['address']}")
    
    iframe_html = f"""
    <iframe src="https://embed.waze.com/iframe?zoom={zoom}&lat={lat}&lon={lon}&pin=1" 
    width="100%" height="450" style="border: none; border-radius: 12px; border: 1px solid #2a2a3a;">
    </iframe>
    """
    st.components.v1.html(iframe_html, height=470)
    
    if st.button("Navigate with Waze", use_container_width=True):
        st.markdown(f"""
        <a href="https://waze.com/ul?ll={lat}%2C{lon}&navigate=yes" target="_blank" 
        style="display: block; text-align: center; background: #4d6bfe; color: white; 
        padding: 10px; border-radius: 8px; text-decoration: none; font-weight: 500;">
        Open Waze App
        </a>
        """, unsafe_allow_html=True)
    
    with st.expander("Traffic Information"):
        st.caption("Current traffic: Moderate")
        st.caption("Estimated travel time: 15 mins")
        st.caption("Distance: 5.2 km")

def emergency_contacts_free():
    st.markdown("### Emergency Contacts")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        <div style="background: #1a1a2a; padding: 16px; border-radius: 10px; border-left: 4px solid #f44336; margin-bottom: 10px;">
            <div style="color: #8a8a9a; font-size: 14px;">Police</div>
            <div style="color: #ff4444; font-size: 24px; font-weight: 700;">999</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("""
        <div style="background: #1a1a2a; padding: 16px; border-radius: 10px; border-left: 4px solid #f44336; margin-bottom: 10px;">
            <div style="color: #8a8a9a; font-size: 14px;">Ambulance</div>
            <div style="color: #ff4444; font-size: 24px; font-weight: 700;">999</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div style="background: #1a1a2a; padding: 16px; border-radius: 10px; border-left: 4px solid #f44336; margin-bottom: 10px;">
            <div style="color: #8a8a9a; font-size: 14px;">Fire Brigade</div>
            <div style="color: #ff4444; font-size: 24px; font-weight: 700;">994</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("""
        <div style="background: #1a1a2a; padding: 16px; border-radius: 10px; border-left: 4px solid #f44336; margin-bottom: 10px;">
            <div style="color: #8a8a9a; font-size: 14px;">Roadside Assistance</div>
            <div style="color: #ff4444; font-size: 24px; font-weight: 700;">1800-88-1818</div>
        </div>
        """, unsafe_allow_html=True)

def waze_features_tab():
    st.markdown("## Waze Navigation")
    tabs = st.tabs(["Map", "Emergency Contacts"])
    with tabs[0]:
        waze_map_free()
    with tabs[1]:
        emergency_contacts_free()

# ============================================================
# GURU MALAYSIA
# ============================================================
KSSR_DATA = {
    "tahun": ["Tahun 1", "Tahun 2", "Tahun 3", "Tahun 4", "Tahun 5", "Tahun 6"],
    "mata_pelajaran": {
        "Teras": [
            "Bahasa Melayu", "Bahasa Inggeris", "Matematik", "Sains",
            "Pendidikan Islam", "Pendidikan Moral", "Pendidikan Jasmani dan Kesihatan",
            "Pendidikan Seni Visual", "Pendidikan Muzik", "Sejarah", "Reka Bentuk dan Teknologi"
        ],
        "Bahasa Tambahan": [
            "Bahasa Cina", "Bahasa Tamil", "Bahasa Arab",
            "Bahasa Iban", "Bahasa Kadazandusun", "Bahasa Semai"
        ]
    },
    "struktur_tahun": {
        "Tahun 1": {"teras": ["Bahasa Melayu", "Bahasa Inggeris", "Matematik", "Sains", "Pendidikan Islam/Moral", "Pendidikan Jasmani dan Kesihatan", "Pendidikan Seni Visual", "Pendidikan Muzik"], "tambahan": ["Bahasa Cina", "Bahasa Tamil", "Bahasa Arab", "Bahasa Iban", "Bahasa Kadazandusun", "Bahasa Semai"]},
        "Tahun 2": {"teras": ["Bahasa Melayu", "Bahasa Inggeris", "Matematik", "Sains", "Pendidikan Islam/Moral", "Pendidikan Jasmani dan Kesihatan", "Pendidikan Seni Visual", "Pendidikan Muzik"], "tambahan": ["Bahasa Cina", "Bahasa Tamil", "Bahasa Arab", "Bahasa Iban", "Bahasa Kadazandusun", "Bahasa Semai"]},
        "Tahun 3": {"teras": ["Bahasa Melayu", "Bahasa Inggeris", "Matematik", "Sains", "Pendidikan Islam/Moral", "Pendidikan Jasmani dan Kesihatan", "Pendidikan Seni Visual", "Pendidikan Muzik"], "tambahan": ["Bahasa Cina", "Bahasa Tamil", "Bahasa Arab", "Bahasa Iban", "Bahasa Kadazandusun", "Bahasa Semai"]},
        "Tahun 4": {"teras": ["Bahasa Melayu", "Bahasa Inggeris", "Matematik", "Sains", "Pendidikan Islam/Moral", "Pendidikan Jasmani dan Kesihatan", "Pendidikan Seni Visual", "Pendidikan Muzik", "Sejarah", "Reka Bentuk dan Teknologi"], "tambahan": ["Bahasa Cina", "Bahasa Tamil", "Bahasa Arab", "Bahasa Iban", "Bahasa Kadazandusun", "Bahasa Semai"]},
        "Tahun 5": {"teras": ["Bahasa Melayu", "Bahasa Inggeris", "Matematik", "Sains", "Pendidikan Islam/Moral", "Pendidikan Jasmani dan Kesihatan", "Pendidikan Seni Visual", "Pendidikan Muzik", "Sejarah", "Reka Bentuk dan Teknologi"], "tambahan": ["Bahasa Cina", "Bahasa Tamil", "Bahasa Arab", "Bahasa Iban", "Bahasa Kadazandusun", "Bahasa Semai"]},
        "Tahun 6": {"teras": ["Bahasa Melayu", "Bahasa Inggeris", "Matematik", "Sains", "Pendidikan Islam/Moral", "Pendidikan Jasmani dan Kesihatan", "Pendidikan Seni Visual", "Pendidikan Muzik", "Sejarah", "Reka Bentuk dan Teknologi"], "tambahan": ["Bahasa Cina", "Bahasa Tamil", "Bahasa Arab", "Bahasa Iban", "Bahasa Kadazandusun", "Bahasa Semai"]}
    }
}

def get_tahun_list():
    return KSSR_DATA["tahun"]

def get_mata_pelajaran_by_tahun(tahun):
    struktur = KSSR_DATA["struktur_tahun"].get(tahun, {})
    if not struktur:
        return []
    semua = []
    for mp in struktur.get("teras", []):
        semua.append({"nama": mp, "jenis": "Teras"})
    for mp in struktur.get("tambahan", []):
        semua.append({"nama": mp, "jenis": "Bahasa Tambahan"})
    return semua

def get_bab_by_subjek(tahun, mata_pelajaran):
    bab_list = {
        "Bahasa Melayu": ["Keluarga", "Kebersihan", "Alam Sekitar", "Kesihatan", "Keselamatan", "Teknologi"],
        "Bahasa Inggeris": ["Family", "Food", "School", "Animals", "Weather", "Hobbies"],
        "Matematik": ["Nombor", "Tambahan", "Penolakan", "Darab", "Bahagi", "Pecahan"],
        "Sains": ["Benda Hidup", "Benda Bukan Hidup", "Sistem Badan", "Tumbuh-tumbuhan", "Haiwan", "Tenaga"],
        "Sejarah": ["Pengenalan", "Prasejarah", "Kesultanan Melayu", "Kemerdekaan", "Malaysia"],
        "Reka Bentuk dan Teknologi": ["Asas Reka Bentuk", "Teknologi", "Penghasilan Produk", "Pengurusan Projek"]
    }
    return bab_list.get(mata_pelajaran, ["Bab 1", "Bab 2", "Bab 3"])

def guru_malaysia_ui():
    st.markdown("""
    <div style="padding: 8px 0 16px 0; border-bottom: 1px solid rgba(255,255,255,0.06); margin-bottom: 20px;">
        <div style="font-size: 18px; font-weight: 600; color: #e8edf5;">Guru Malaysia</div>
        <div style="font-size: 13px; color: #6a6a7a; margin-top: 2px;">Bahan mengajar mengikut KSSR Sekolah Rendah</div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        tahun = st.selectbox("Tahun", get_tahun_list())
    with col2:
        mp_list = get_mata_pelajaran_by_tahun(tahun)
        mp_options = [mp["nama"] for mp in mp_list]
        if mp_options:
            mata_pelajaran = st.selectbox("Mata Pelajaran", mp_options)
        else:
            mata_pelajaran = None
    with col3:
        if mata_pelajaran:
            bab_list = get_bab_by_subjek(tahun, mata_pelajaran)
            if bab_list:
                bab = st.selectbox("Bab/Topik", bab_list)
            else:
                bab = None
    
    col1, col2, col3 = st.columns(3)
    with col1:
        jenis_bahan = st.selectbox("Jenis Bahan", ["Soalan Latihan", "RPH", "Nota Ringkas", "Kuiz", "Lembaran Kerja", "Soalan Peperiksaan"])
    with col2:
        tahap = st.select_slider("Tahap Kesukaran", options=["Mudah", "Sederhana", "Susah"])
    with col3:
        format_output = st.selectbox("Format Output", ["Display", "Download PDF"])
    
    if "bahan_rating" not in st.session_state:
        st.session_state.bahan_rating = []
    
    if st.button("Jana Bahan", use_container_width=True, type="primary"):
        if mata_pelajaran and bab:
            with st.spinner("Menjana bahan..."):
                bahan_id = f"{tahun}_{mata_pelajaran}_{bab}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                st.success(f"Bahan untuk {mata_pelajaran} - {bab} (Tahap {tahap})")
                
                if "Soalan" in jenis_bahan or "Kuiz" in jenis_bahan or "Peperiksaan" in jenis_bahan:
                    st.subheader(f"{jenis_bahan}")
                    for i in range(1, 6):
                        st.markdown(f"**{i}. Soalan contoh untuk {bab}**")
                        st.markdown(f" A) Pilihan A")
                        st.markdown(f" B) Pilihan B")
                        st.markdown(f" C) Pilihan C")
                        st.markdown(f" D) Pilihan D")
                    with st.expander("Jawapan"):
                        st.success(f"Jawapan: C")
                
                elif "RPH" in jenis_bahan:
                    st.subheader("Rancangan Pengajaran Harian")
                    st.markdown(f"""
                    **RANCANGAN PENGAJARAN HARIAN**
                    **Mata Pelajaran:** {mata_pelajaran}
                    **Tahun:** {tahun}
                    **Topik:** {bab}
                    **Tahap:** {tahap}
                    **Standard Kandungan:**
                    - Menguasai kemahiran asas dalam {mata_pelajaran}
                    - Memahami konsep {bab}
                    **Standard Pembelajaran:**
                    - Murid dapat mengenal pasti...
                    - Murid dapat menerangkan...
                    **Aktiviti:**
                    1. **Set Induksi** (5 minit)
                    2. **Perkembangan** (20 minit)
                    3. **Pentaksiran** (10 minit)
                    4. **Penutup** (5 minit)
                    """)
                
                else:
                    st.subheader(f"Nota Ringkas: {bab}")
                    st.markdown(f"""
                    **{mata_pelajaran} - {tahun}**
                    **Topik: {bab}**
                    **1. Pengenalan**
                    - {bab} adalah topik penting dalam {mata_pelajaran}
                    **2. Konsep Asas**
                    - Konsep 1: ...
                    - Konsep 2: ...
                    **3. Rumusan**
                    - Perkara penting yang perlu diingat...
                    """)
                
                if format_output == "Download PDF":
                    st.info("PDF download feature coming soon")
                
                st.divider()
                st.subheader("Rate this material")
                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    if st.button("Excellent", key=f"rate_5_{bahan_id}"):
                        st.session_state.bahan_rating.append({"id": bahan_id, "rating": 5})
                        st.success("Thank you for your rating!")
                with col2:
                    if st.button("Good", key=f"rate_4_{bahan_id}"):
                        st.session_state.bahan_rating.append({"id": bahan_id, "rating": 4})
                        st.success("Thank you for your rating!")
                with col3:
                    if st.button("Average", key=f"rate_3_{bahan_id}"):
                        st.session_state.bahan_rating.append({"id": bahan_id, "rating": 3})
                        st.success("Thank you for your rating!")
                with col4:
                    if st.button("Poor", key=f"rate_2_{bahan_id}"):
                        st.session_state.bahan_rating.append({"id": bahan_id, "rating": 2})
                        st.success("Thank you for your rating!")
                with col5:
                    if st.button("Very Poor", key=f"rate_1_{bahan_id}"):
                        st.session_state.bahan_rating.append({"id": bahan_id, "rating": 1})
                        st.success("Thank you for your rating!")
                
                if st.button("Share this material"):
                    st.info("Share link: [Coming soon]")
        else:
            st.warning("Sila pilih tahun, mata pelajaran dan bab")
    
    if st.session_state.bahan_rating:
        with st.expander("Material Ratings"):
            ratings = [r["rating"] for r in st.session_state.bahan_rating]
            avg_rating = sum(ratings) / len(ratings) if ratings else 0
            st.caption(f"Total ratings: {len(ratings)}")
            st.caption(f"Average rating: {avg_rating:.1f} / 5")

# ============================================================
# TENDER SYSTEM
# ============================================================
class TenderSystem:
    def __init__(self):
        self.tender_file = "tenders.json"
        self.mof_file = "mof_certificates.json"
        self.tenders = []
        self.mof_certificates = []
        self.load_data()

    def load_data(self):
        self.tenders = safe_read_json(self.tender_file, [])
        self.mof_certificates = safe_read_json(self.mof_file, [])

    def save_data(self):
        safe_write_json(self.tender_file, self.tenders)
        safe_write_json(self.mof_file, self.mof_certificates)

    def delete_tender(self, tender_id):
        for tender in self.tenders:
            if tender["id"] == tender_id:
                self.tenders.remove(tender)
                self.save_data()
                return {"success": True}
        return {"success": False, "error": "Tender not found"}

    def register_mof(self, company_name, registration_no, cert_no, expiry_date):
        if not company_name or not cert_no:
            return {"success": False, "error": "Company name and certificate number required"}
        cert = {
            "company_name": company_name,
            "registration_no": registration_no,
            "cert_no": cert_no,
            "expiry_date": expiry_date,
            "status": "Active",
            "registered": datetime.datetime.now().isoformat()
        }
        self.mof_certificates.append(cert)
        self.save_data()
        return {"success": True, "cert": cert}

    def check_mof(self, company_name):
        for cert in self.mof_certificates:
            if cert["company_name"] == company_name:
                expiry = datetime.datetime.fromisoformat(cert["expiry_date"])
                if expiry < datetime.datetime.now():
                    cert["status"] = "Expired"
                    self.save_data()
                    return {"valid": False, "status": "Expired"}
                return {"valid": True, "status": "Active"}
        return {"valid": False, "status": "Not Registered"}

    def create_tender(self, name, description, budget, deadline, category):
        if not name or budget <= 0:
            return {"success": False, "error": "Name and valid budget required"}
        tender = {
            "id": len(self.tenders) + 1,
            "name": name,
            "description": description,
            "budget": budget,
            "deadline": deadline,
            "category": category,
            "status": "Open",
            "created": datetime.datetime.now().isoformat(),
            "bids": [],
            "awarded_to": None,
            "award_amount": None
        }
        self.tenders.append(tender)
        self.save_data()
        return {"success": True, "tender": tender}

    def place_bid(self, tender_id, company_name, amount, proposal):
        if not company_name or amount <= 0:
            return {"success": False, "error": "Company name and valid amount required"}
        for tender in self.tenders:
            if tender["id"] == tender_id and tender["status"] == "Open":
                cert_check = self.check_mof(company_name)
                if not cert_check["valid"]:
                    return {"success": False, "error": "MOF certificate invalid or expired"}
                bid = {
                    "company_name": company_name,
                    "amount": amount,
                    "proposal": proposal,
                    "time": datetime.datetime.now().isoformat(),
                    "status": "Pending"
                }
                tender["bids"].append(bid)
                self.save_data()
                return {"success": True, "bid": bid}
        return {"success": False, "error": "Tender not found or closed"}

    def close_tender(self, tender_id):
        for tender in self.tenders:
            if tender["id"] == tender_id:
                tender["status"] = "Closed"
                self.save_data()
                return {"success": True}
        return {"success": False, "error": "Tender not found"}

    def award_tender(self, tender_id, company_name, amount):
        if amount <= 0:
            return {"success": False, "error": "Valid award amount required"}
        for tender in self.tenders:
            if tender["id"] == tender_id:
                tender["status"] = "Awarded"
                tender["awarded_to"] = company_name
                tender["award_amount"] = amount
                self.save_data()
                return {"success": True}
        return {"success": False, "error": "Tender not found"}

    def update_tender(self, tender_id, data):
        for tender in self.tenders:
            if tender["id"] == tender_id:
                tender.update(data)
                tender["updated"] = datetime.datetime.now().isoformat()
                self.save_data()
                return {"success": True}
        return {"success": False, "error": "Tender not found"}

    def get_tender(self, tender_id):
        for tender in self.tenders:
            if tender["id"] == tender_id:
                return tender
        return None

    def get_tender_summary(self):
        total_budget = sum(t["budget"] for t in self.tenders)
        awarded_budget = sum(t.get("award_amount", 0) for t in self.tenders if t["status"] == "Awarded")
        return {
            "total_tenders": len(self.tenders),
            "open": len([t for t in self.tenders if t["status"] == "Open"]),
            "closed": len([t for t in self.tenders if t["status"] == "Closed"]),
            "awarded": len([t for t in self.tenders if t["status"] == "Awarded"]),
            "total_budget": total_budget,
            "awarded_budget": awarded_budget
        }

    def get_tenders_by_status(self, status):
        return [t for t in self.tenders if t["status"] == status]

    def search_tenders(self, query):
        query_lower = query.lower()
        results = []
        for tender in self.tenders:
            if query_lower in tender["name"].lower() or query_lower in tender.get("category", "").lower():
                results.append(tender)
        return results

    def get_bid_history(self, tender_id):
        tender = self.get_tender(tender_id)
        if tender:
            return tender.get("bids", [])
        return []

    def get_upcoming_deadlines(self, days=7):
        today = datetime.datetime.now().date()
        upcoming = []
        for tender in self.tenders:
            try:
                deadline = datetime.datetime.strptime(tender["deadline"], "%Y-%m-%d").date()
                if today <= deadline <= today + datetime.timedelta(days=days):
                    upcoming.append(tender)
            except:
                pass
        return upcoming

def tender_ui():
    st.markdown("### Tender Management System")
    ts = TenderSystem()
    stats = ts.get_tender_summary()
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Tender", stats["total_tenders"])
    with col2:
        st.metric("Tender Dibuka", stats["open"])
    with col3:
        st.metric("Tender Ditutup", stats["closed"])
    with col4:
        st.metric("Tender Dianugerah", stats["awarded"])
    with col5:
        st.metric("Jumlah Bajet", f"RM {stats['total_budget']:,.2f}")
    
    upcoming = ts.get_upcoming_deadlines()
    if upcoming:
        st.warning(f"Upcoming deadlines: {len(upcoming)} tender closing soon")
        for t in upcoming:
            st.caption(f"- {t['name']} (Deadline: {t['deadline']})")
    
    st.divider()
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Tender", "Buka Tender", "Bida", "MOF", "Analytics"])
    
    with tab1:
        st.subheader("Senarai Tender")
        col1, col2 = st.columns(2)
        with col1:
            status_filter = st.selectbox("Filter Status", ["All", "Open", "Closed", "Awarded"])
        with col2:
            search_query = st.text_input("Search Tender", placeholder="Search by name or category...")
        
        tenders = ts.tenders
        if status_filter != "All":
            tenders = [t for t in tenders if t["status"] == status_filter]
        if search_query:
            tenders = [t for t in tenders if search_query.lower() in t["name"].lower() or search_query.lower() in t.get("category", "").lower()]
        
        if tenders:
            for tender in tenders:
                with st.expander(f"{tender['name']} - {tender['status']}"):
                    st.caption(f"Kategori: {tender['category']}")
                    st.caption(f"Bajet: RM {tender['budget']:,.2f}")
                    st.caption(f"Tarikh Tutup: {tender['deadline']}")
                    st.caption(f"Bidaan: {len(tender['bids'])}")
                    if tender.get('awarded_to'):
                        st.success(f"Anugerah kepada: {tender['awarded_to']} (RM {tender.get('award_amount', 0):,.2f})")
                    
                    if tender['bids']:
                        with st.expander("Bid History"):
                            for bid in tender['bids']:
                                st.caption(f"- {bid['company_name']}: RM {bid['amount']:,.2f} ({bid['status']})")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if tender["status"] == "Open":
                            if st.button("Close Tender", key=f"close_{tender['id']}"):
                                ts.close_tender(tender['id'])
                                st.rerun()
                    with col2:
                        if tender["status"] == "Closed":
                            award_company = st.text_input("Award To", key=f"award_company_{tender['id']}")
                            award_amount = st.number_input("Award Amount", min_value=0.0, key=f"award_amount_{tender['id']}")
                            if st.button("Award Tender", key=f"award_{tender['id']}"):
                                if award_company and award_amount > 0:
                                    ts.award_tender(tender['id'], award_company, award_amount)
                                    st.rerun()
                    with col3:
                        if st.button("Delete Tender", key=f"del_{tender['id']}"):
                            ts.delete_tender(tender['id'])
                            st.rerun()
        else:
            st.info("Tiada tender")
    
    with tab2:
        st.subheader("Buka Tender Baru")
        with st.form("create_tender_form"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Nama Tender *")
                description = st.text_area("Deskripsi", height=60)
            with col2:
                budget = st.number_input("Bajet (RM) *", min_value=0.0, value=10000.0)
                category = st.selectbox("Kategori", ["Construction", "IT", "Consultancy", "Supply", "Services", "Education", "Healthcare"])
                deadline = st.date_input("Tarikh Tutup")
            if st.form_submit_button("Buka Tender"):
                if name and budget > 0:
                    result = ts.create_tender(name, description, budget, deadline.strftime("%Y-%m-%d"), category)
                    if result["success"]:
                        st.success(f"Tender '{name}' berjaya dibuka!")
                        st.rerun()
                    else:
                        st.error(result.get("error"))
                else:
                    st.warning("Sila lengkapkan maklumat")
    
    with tab3:
        st.subheader("Bida Tender")
        company_name = st.text_input("Nama Syarikat *")
        open_tenders = [t for t in ts.tenders if t["status"] == "Open"]
        if open_tenders:
            selected = st.selectbox("Pilih Tender", [t["name"] for t in open_tenders])
            tender = next((t for t in open_tenders if t["name"] == selected), None)
            if tender:
                amount = st.number_input("Jumlah Bidaan (RM) *", min_value=0.0)
                proposal = st.text_area("Proposal", height=60)
                if st.button("Hantar Bidaan", use_container_width=True):
                    if company_name and amount > 0:
                        result = ts.place_bid(tender["id"], company_name, amount, proposal)
                        if result["success"]:
                            st.success("Bidaan berjaya dihantar!")
                            st.rerun()
                        else:
                            st.error(result.get("error"))
                    else:
                        st.warning("Sila lengkapkan maklumat")
        else:
            st.info("Tiada tender terbuka")
    
    with tab4:
        st.subheader("Pendaftaran MOF")
        with st.form("mof_form"):
            company_name = st.text_input("Nama Syarikat *")
            registration_no = st.text_input("No. Pendaftaran")
            cert_no = st.text_input("No. Sijil MOF *")
            expiry_date = st.date_input("Tarikh Tamat")
            if st.form_submit_button("Daftar MOF"):
                if company_name and cert_no:
                    result = ts.register_mof(company_name, registration_no, cert_no, expiry_date.strftime("%Y-%m-%d"))
                    if result["success"]:
                        st.success("Sijil MOF berjaya didaftarkan!")
                        st.rerun()
                    else:
                        st.error(result.get("error"))
                else:
                    st.warning("Sila lengkapkan maklumat")
        
        if ts.mof_certificates:
            st.subheader("Senarai Sijil MOF")
            for cert in ts.mof_certificates:
                st.caption(f"- {cert['company_name']}: {cert['cert_no']} ({cert['status']})")
    
    with tab5:
        st.subheader("Tender Analytics")
        if ts.tenders:
            categories = {}
            for t in ts.tenders:
                cat = t.get("category", "Other")
                categories[cat] = categories.get(cat, 0) + 1
            
            st.caption("Category Distribution:")
            for cat, count in categories.items():
                st.caption(f"- {cat}: {count} tenders")
            
            st.caption(f"Total Budget: RM {stats['total_budget']:,.2f}")
            st.caption(f"Awarded Budget: RM {stats['awarded_budget']:,.2f}")
            if stats['total_budget'] > 0:
                pct = (stats['awarded_budget'] / stats['total_budget'] * 100)
                st.caption(f"Budget Used: {pct:.1f}%")
        else:
            st.info("No data available")

# ============================================================
# PROJECT EXPENSE MANAGEMENT
# ============================================================
class ProjectExpenseManager:
    def __init__(self):
        self.expense_file = "project_expenses.json"
        self.project_file = "projects.json"
        self.expenses = []
        self.projects = []
        self.load_data()

    def load_data(self):
        self.expenses = safe_read_json(self.expense_file, [])
        self.projects = safe_read_json(self.project_file, [])

    def save_data(self):
        safe_write_json(self.expense_file, self.expenses)
        safe_write_json(self.project_file, self.projects)

    def add_project(self, data):
        if not data.get("project_name") or data.get("project_value", 0) <= 0:
            return {"success": False, "error": "Project name and valid value required"}
        project = {
            "id": len(self.projects) + 1,
            "project_name": data.get("project_name", ""),
            "project_code": data.get("project_code", ""),
            "client_name": data.get("client_name", ""),
            "location": data.get("location", ""),
            "project_value": data.get("project_value", 0),
            "deposit_received": data.get("deposit_received", 0),
            "start_date": data.get("start_date", ""),
            "end_date": data.get("end_date", ""),
            "status": data.get("status", "Active"),
            "created": datetime.datetime.now().isoformat(),
            "total_expenses": 0,
            "expenses": [],
            "notes": data.get("notes", "")
        }
        self.projects.append(project)
        self.save_data()
        return {"success": True, "project": project}

    def update_project(self, project_id, data):
        for p in self.projects:
            if p["id"] == project_id:
                p.update(data)
                p["updated"] = datetime.datetime.now().isoformat()
                self.save_data()
                return {"success": True}
        return {"success": False, "error": "Project not found"}

    def get_project(self, project_id):
        for p in self.projects:
            if p["id"] == project_id:
                return p
        return None

    def get_projects(self, status=None):
        if status:
            if isinstance(status, list):
                return [p for p in self.projects if p["status"] in status]
            return [p for p in self.projects if p["status"] == status]
        return self.projects

    def add_expense(self, project_id, data):
        if not data.get("item_name") or data.get("unit_price", 0) <= 0:
            return {"success": False, "error": "Item name and valid price required"}
        expense = {
            "id": len(self.expenses) + 1,
            "project_id": project_id,
            "date": data.get("date", datetime.datetime.now().isoformat()),
            "category": data.get("category", ""),
            "item_name": data.get("item_name", ""),
            "description": data.get("description", ""),
            "quantity": data.get("quantity", 1),
            "unit_price": data.get("unit_price", 0),
            "total": data.get("quantity", 1) * data.get("unit_price", 0),
            "supplier": data.get("supplier", ""),
            "invoice_no": data.get("invoice_no", ""),
            "payment_method": data.get("payment_method", ""),
            "status": data.get("status", "Verified"),
            "payment_status": data.get("payment_status", "Pending"),
            "notes": data.get("notes", ""),
            "created": datetime.datetime.now().isoformat()
        }
        self.expenses.append(expense)
        for p in self.projects:
            if p["id"] == project_id:
                p["total_expenses"] = sum(e["total"] for e in self.expenses if e["project_id"] == p["id"])
                p["expenses"].append(expense["id"])
        self.save_data()
        return {"success": True, "expense": expense}

    def get_expenses(self, project_id=None, category=None, start_date=None, end_date=None):
        expenses = self.expenses
        if project_id:
            expenses = [e for e in expenses if e["project_id"] == project_id]
        if category:
            expenses = [e for e in expenses if e["category"] == category]
        if start_date:
            expenses = [e for e in expenses if e["date"] >= start_date]
        if end_date:
            expenses = [e for e in expenses if e["date"] <= end_date]
        return expenses

    def get_project_summary(self, project_id):
        project = self.get_project(project_id)
        if not project:
            return None
        expenses = self.get_expenses(project_id)
        total_expenses = sum(e["total"] for e in expenses)
        categories = {}
        for e in expenses:
            if e["category"] in categories:
                categories[e["category"]] += e["total"]
            else:
                categories[e["category"]] = e["total"]
        return {
            "project": project,
            "total_expenses": total_expenses,
            "balance": project["project_value"] - total_expenses - project.get("deposit_received", 0),
            "percentage": (total_expenses / project["project_value"] * 100) if project["project_value"] > 0 else 0,
            "categories": categories,
            "expenses": expenses,
            "total_quantity": sum(e["quantity"] for e in expenses)
        }

    def delete_expense(self, expense_id):
        expense = None
        for e in self.expenses:
            if e["id"] == expense_id:
                expense = e
                break
        if expense:
            self.expenses = [e for e in self.expenses if e["id"] != expense_id]
            for p in self.projects:
                if p["id"] == expense["project_id"]:
                    p["total_expenses"] = sum(e["total"] for e in self.expenses if e["project_id"] == p["id"])
            self.save_data()
            return {"success": True}
        return {"success": False, "error": "Expense not found"}

    def delete_project(self, project_id):
        self.projects = [p for p in self.projects if p["id"] != project_id]
        self.expenses = [e for e in self.expenses if e["project_id"] != project_id]
        self.save_data()
        return {"success": True}

    def get_expense_categories(self):
        categories = {}
        for e in self.expenses:
            categories[e["category"]] = categories.get(e["category"], 0) + e["total"]
        return categories

    def get_payment_summary(self, project_id):
        expenses = self.get_expenses(project_id)
        paid = sum(e["total"] for e in expenses if e.get("payment_status") == "Paid")
        pending = sum(e["total"] for e in expenses if e.get("payment_status") == "Pending")
        overdue = sum(e["total"] for e in expenses if e.get("payment_status") == "Overdue")
        return {"paid": paid, "pending": pending, "overdue": overdue}

def project_expense_ui():
    st.markdown("### Project Expense Management")
    pem = ProjectExpenseManager()
    
    total_projects = len(pem.projects)
    total_expenses = len(pem.expenses)
    total_spent = sum(e["total"] for e in pem.expenses)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Projects", total_projects)
    with col2:
        st.metric("Expenses", total_expenses)
    with col3:
        st.metric("Total Spent", f"RM {total_spent:,.2f}")
    with col4:
        st.metric("Deposits", f"RM {sum(p.get('deposit_received', 0) for p in pem.projects):,.2f}")
    
    st.divider()
    
    tab1, tab2, tab3, tab4 = st.tabs(["Projects", "Add Expense", "Report", "Analytics"])
    
    with tab1:
        st.subheader("Projects List")
        with st.expander("Add New Project", expanded=False):
            with st.form("add_project_form"):
                col1, col2 = st.columns(2)
                with col1:
                    project_name = st.text_input("Project Name *")
                    project_code = st.text_input("Project Code")
                    client_name = st.text_input("Client Name")
                    status = st.selectbox("Status", ["Active", "On Hold", "Completed", "Cancelled"])
                with col2:
                    location = st.text_input("Location")
                    project_value = st.number_input("Project Value (RM) *", min_value=0.0, value=10000.0)
                    deposit_received = st.number_input("Deposit Received (RM)", min_value=0.0, value=0.0)
                col1, col2 = st.columns(2)
                with col1:
                    start_date = st.date_input("Start Date")
                with col2:
                    end_date = st.date_input("End Date")
                notes = st.text_area("Notes", height=60)
                if st.form_submit_button("Add Project"):
                    if project_name and project_value > 0:
                        data = {
                            "project_name": project_name,
                            "project_code": project_code,
                            "client_name": client_name,
                            "location": location,
                            "project_value": project_value,
                            "deposit_received": deposit_received,
                            "start_date": start_date.isoformat(),
                            "end_date": end_date.isoformat(),
                            "status": status,
                            "notes": notes
                        }
                        result = pem.add_project(data)
                        if result["success"]:
                            st.success(f"Project '{project_name}' added!")
                            st.rerun()
                        else:
                            st.error(result.get("error"))
                    else:
                        st.warning("Project name and value required")
        
        status_filter = st.selectbox("Filter Status", ["All", "Active", "On Hold", "Completed", "Cancelled"])
        projects = pem.get_projects() if status_filter == "All" else pem.get_projects(status_filter)
        
        if projects:
            for p in projects:
                with st.expander(f"{p['project_name']} ({p['project_code']}) - {p['status']}"):
                    st.caption(f"Client: {p.get('client_name', '-')}")
                    st.caption(f"Value: RM {p['project_value']:,.2f}")
                    st.caption(f"Spent: RM {p['total_expenses']:,.2f}")
                    st.caption(f"Balance: RM {p['project_value'] - p['total_expenses']:,.2f}")
                    
                    progress = (p['total_expenses'] / p['project_value'] * 100) if p['project_value'] > 0 else 0
                    st.progress(progress / 100, text=f"Usage: {progress:.1f}%")
                    
                    if st.button("Delete Project", key=f"del_proj_{p['id']}"):
                        pem.delete_project(p['id'])
                        st.rerun()
        else:
            st.info("No projects")
    
    with tab2:
        st.subheader("Add Expense")
        active_projects = pem.get_projects(["Active", "On Hold"])
        project_options = [f"{p['id']} - {p['project_name']}" for p in active_projects]
        if project_options:
            selected = st.selectbox("Select Project", project_options)
            project_id = int(selected.split(" - ")[0])
            with st.form("add_expense_form"):
                col1, col2 = st.columns(2)
                with col1:
                    expense_date = st.date_input("Date", datetime.datetime.now())
                    item_name = st.text_input("Item Name *")
                    category = st.selectbox("Category", ["Materials", "Equipment", "Labour", "Subcontractor", "Transport", "Food", "Office Supplies", "Other"])
                    quantity = st.number_input("Quantity", min_value=1, value=1)
                with col2:
                    supplier = st.text_input("Supplier *")
                    unit_price = st.number_input("Unit Price (RM) *", min_value=0.0, value=1.0)
                    payment_status = st.selectbox("Payment Status", ["Pending", "Paid", "Overdue"])
                    invoice_no = st.text_input("Invoice No.")
                total = quantity * unit_price
                st.caption(f"Total: RM {total:,.2f}")
                description = st.text_area("Description", height=60)
                notes = st.text_area("Notes", height=40)
                if st.form_submit_button("Save Expense"):
                    if item_name and supplier and unit_price > 0:
                        data = {
                            "date": expense_date.isoformat(),
                            "item_name": item_name,
                            "category": category,
                            "description": description,
                            "quantity": quantity,
                            "unit_price": unit_price,
                            "supplier": supplier,
                            "invoice_no": invoice_no,
                            "payment_method": "Cash",
                            "payment_status": payment_status,
                            "notes": notes
                        }
                        result = pem.add_expense(project_id, data)
                        if result["success"]:
                            st.success(f"Expense '{item_name}' saved!")
                            st.rerun()
                        else:
                            st.error(result.get("error"))
                    else:
                        st.warning("Item name, supplier and price required")
        else:
            st.info("No active projects")
        
        st.divider()
        st.subheader("Recent Expenses")
        expenses = pem.get_expenses()
        if expenses:
            for e in expenses[-10:]:
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                with col1:
                    st.caption(e['item_name'])
                with col2:
                    st.caption(f"RM {e['total']:,.2f}")
                with col3:
                    st.caption(e['date'][:10])
                with col4:
                    st.caption(e.get('payment_status', 'Pending'))
                if st.button("Delete", key=f"del_exp_{e['id']}"):
                    pem.delete_expense(e['id'])
                    st.rerun()
        else:
            st.info("No expenses")
    
    with tab3:
        st.subheader("Project Report")
        all_projects = pem.projects
        project_options = [f"{p['id']} - {p['project_name']}" for p in all_projects]
        if project_options:
            selected = st.selectbox("Select Project for Report", project_options)
            project_id = int(selected.split(" - ")[0])
            summary = pem.get_project_summary(project_id)
            if summary:
                project = summary["project"]
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Project Value", f"RM {project['project_value']:,.2f}")
                with col2:
                    st.metric("Total Expenses", f"RM {summary['total_expenses']:,.2f}")
                with col3:
                    st.metric("Balance", f"RM {summary['balance']:,.2f}")
                with col4:
                    st.metric("Usage", f"{summary['percentage']:.1f}%")
                st.progress(summary['percentage'] / 100)
                
                st.subheader("Expenses by Category")
                categories = summary['categories']
                if categories:
                    for cat, amount in categories.items():
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.caption(cat)
                        with col2:
                            st.caption(f"RM {amount:,.2f}")
                else:
                    st.info("No expenses")
                
                payment_summary = pem.get_payment_summary(project_id)
                st.subheader("Payment Summary")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Paid", f"RM {payment_summary['paid']:,.2f}")
                with col2:
                    st.metric("Pending", f"RM {payment_summary['pending']:,.2f}")
                with col3:
                    st.metric("Overdue", f"RM {payment_summary['overdue']:,.2f}")
            else:
                st.info("No project summary available")
        else:
            st.info("No projects for report")
    
    with tab4:
        st.subheader("Analytics")
        if pem.expenses:
            categories = pem.get_expense_categories()
            st.caption("Spending by Category:")
            for cat, amount in categories.items():
                st.caption(f"- {cat}: RM {amount:,.2f}")
            
            total_spent = sum(e["total"] for e in pem.expenses)
            st.caption(f"Total Spending: RM {total_spent:,.2f}")
            st.caption(f"Total Projects: {len(pem.projects)}")
            st.caption(f"Total Expenses: {len(pem.expenses)}")
        else:
            st.info("No data available")

# ============================================================
# SETTINGS UI
# ============================================================
def settings_ui():
    st.markdown("### Settings")
    
    st.subheader("Account")
    st.caption(f"Email: {st.session_state.get('email', '')}")
    st.caption(f"Username: {st.session_state.get('username', '')}")
    st.caption(f"Role: {st.session_state.get('role', 'user')}")
    st.caption(f"UID: {st.session_state.get('uid', '')}")
    st.caption(f"Subscription: {check_subscription(st.session_state.get('username', ''))}")
    st.caption(f"Remaining Requests: {get_remaining_requests(st.session_state.get('username', ''))}")
    
    st.divider()
    
    st.subheader("Profile Picture")
    uploaded_file = st.file_uploader("Upload Profile Picture", type=["jpg", "png", "jpeg"])
    if uploaded_file:
        img = Image.open(uploaded_file)
        img.thumbnail((100, 100))
        st.image(img, width=100)
        st.success("Profile picture uploaded!")
    
    st.divider()
    
    st.subheader("Preferences")
    prefs = load_preferences(st.session_state.username)
    
    col1, col2 = st.columns(2)
    with col1:
        language = st.selectbox("Language", ["English", "Bahasa Malaysia", "Chinese", "Tamil"], 
                               index=["English", "Bahasa Malaysia", "Chinese", "Tamil"].index(prefs.get("language", "English")))
        theme = st.selectbox("Theme", ["Dark", "Light"], 
                            index=["Dark", "Light"].index(prefs.get("theme", "Dark")))
        persona = st.selectbox("AI Persona", list(AI_PERSONAS.keys()),
                              index=list(AI_PERSONAS.keys()).index(prefs.get("persona", "Default")))
    with col2:
        font_size = st.selectbox("Font Size", ["Small", "Medium", "Large"],
                                index=["Small", "Medium", "Large"].index(prefs.get("font_size", "Medium")))
        notifications = st.checkbox("Enable Notifications", value=prefs.get("notifications", True))
        tone = st.selectbox("Tone", ["Professional", "Casual", "Creative", "Educational", "Friendly"],
                           index=["Professional", "Casual", "Creative", "Educational", "Friendly"].index(prefs.get("tone", "Professional")))
    
    col1, col2 = st.columns(2)
    with col1:
        max_tokens = st.number_input("Max Tokens", min_value=256, max_value=4096, value=prefs.get("max_tokens", 2048), step=256)
    with col2:
        temperature = st.slider("Temperature", 0.0, 1.0, prefs.get("temperature", 0.7), 0.05)
    
    model_options = ["auto", "groq", "gemini", "openai", "openrouter", "huggingface"]
    selected_model = st.selectbox("Default Model", model_options, 
                                  index=model_options.index(prefs.get("model", "auto")))
    
    if st.button("Save Preferences", use_container_width=True):
        new_prefs = {
            "language": language,
            "theme": theme,
            "persona": persona,
            "font_size": font_size,
            "notifications": notifications,
            "tone": tone,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "model": selected_model
        }
        save_preferences(st.session_state.username, new_prefs)
        st.success("Preferences saved!")
        st.rerun()
    
    st.divider()
    
    st.subheader("Data Management")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Export All Data", use_container_width=True):
            data = {
                "users": load_users(),
                "chats": load_chats(),
                "usage": safe_read_json("mychat_usage.json", {}),
                "export_date": datetime.datetime.now().isoformat()
            }
            json_data = json.dumps(data, indent=2)
            st.download_button(
                "Download Data",
                json_data,
                f"mychat_data_{datetime.datetime.now().strftime('%Y%m%d')}.json",
                "application/json"
            )
    with col2:
        uploaded = st.file_uploader("Import Data", type=["json"])
        if uploaded:
            try:
                data = json.load(uploaded)
                if "chats" in data:
                    chats = load_chats()
                    for username, chat_data in data["chats"].items():
                        if username not in chats:
                            chats[username] = []
                        chats[username].extend(chat_data)
                    save_chats(chats)
                    st.success("Data imported successfully!")
                    st.rerun()
            except:
                st.error("Invalid data file")
    
    st.subheader("Clear Data")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Clear All Chats", use_container_width=True):
            if st.session_state.username:
                history = load_chats()
                if st.session_state.username in history:
                    history[st.session_state.username] = []
                    save_chats(history)
                    st.success("Chats cleared!")
                    st.rerun()
    with col2:
        if st.button("Clear All Data", use_container_width=True):
            st.warning("This will delete all data including users!")
            confirm = st.text_input("Type 'DELETE ALL' to confirm")
            if confirm == "DELETE ALL":
                if os.path.exists("mychat_users.json"):
                    os.remove("mychat_users.json")
                if os.path.exists("mychat_chats.json"):
                    os.remove("mychat_chats.json")
                st.success("All data cleared!")
                st.rerun()
    
    st.divider()
    
    st.subheader("API Keys")
    st.info("API keys are configured in .streamlit/secrets.toml")
    
    col1, col2 = st.columns(2)
    with col1:
        st.caption(f"Groq API: {'Configured' if GROQ_API_KEY else 'Not Configured'}")
        st.caption(f"Gemini API: {'Configured' if GEMINI_API_KEY else 'Not Configured'}")
        st.caption(f"OpenAI API: {'Configured' if OPENAI_API_KEY else 'Not Configured'}")
        st.caption(f"OpenRouter API: {'Configured' if OPENROUTER_API_KEY else 'Not Configured'}")
    with col2:
        st.caption(f"HuggingFace API: {'Configured' if HUGGINGFACE_API_KEY else 'Not Configured'}")
        st.caption(f"Stability AI: {'Configured' if STABILITY_API_KEY else 'Not Configured'}")
        st.caption(f"ElevenLabs: {'Configured' if ELEVENLABS_API_KEY else 'Not Configured'}")
        st.caption(f"Firebase: {'Connected' if firebase_manager.is_ready() else 'Not Connected'}")
    
    if st.button("Generate API Key", use_container_width=True):
        api_key = generate_api_key(st.session_state.username)
        st.code(api_key)
        st.info("Copy this key for API access")
    
    st.divider()
    
    st.subheader("Change Password")
    with st.form("change_pass"):
        current = st.text_input("Current Password", type="password")
        new = st.text_input("New Password", type="password")
        confirm = st.text_input("Confirm Password", type="password")
        if st.form_submit_button("Change Password", use_container_width=True):
            if new == confirm:
                if local_change_password(st.session_state.email, current, new):
                    st.success("Password changed successfully!")
                else:
                    st.error("Current password is incorrect")
            else:
                st.error("Passwords do not match")
    
    st.divider()
    
    st.subheader("Delete Account")
    st.warning("This action is irreversible!")
    confirm = st.text_input("Type 'DELETE' to confirm")
    if st.button("Delete Account", use_container_width=True):
        if confirm == "DELETE":
            if local_delete_user(st.session_state.email):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.success("Account deleted successfully")
                st.rerun()
        else:
            st.error("Please type 'DELETE' to confirm")
    
    st.divider()
    
    st.subheader("System")
    st.caption(f"Version: {APP_VERSION}")
    st.caption(f"Python: {sys.version}")
    st.caption(f"App Name: {APP_NAME}")
    st.caption(f"Author: {APP_AUTHOR}")
    
    if st.button("Clear Cache", use_container_width=True):
        try:
            smart_cache.cache = {}
            smart_cache.cache_time = {}
            st.success("Cache cleared!")
        except:
            st.error("Failed to clear cache")
    
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Privacy Policy", use_container_width=True):
            st.info("Privacy Policy: Your data is stored locally. We do not share your data with third parties.")
    with col2:
        if st.button("About", use_container_width=True):
            st.info(f"{APP_NAME} {APP_VERSION}\nDeveloped by {APP_AUTHOR}\nPowered by Streamlit")
    
    st.divider()
    st.markdown(f"""
    <div style="font-size: 9px; color: #3a3a4a; text-align: center; padding-top: 8px;">
        {APP_COPYRIGHT}
    </div>
    """, unsafe_allow_html=True)

# ============================================================
# MAIN APP
# ============================================================
def main():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "penal_mode" not in st.session_state:
        st.session_state.penal_mode = True
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = "Auto"
    if "current_chat_index" not in st.session_state:
        st.session_state.current_chat_index = None
    if "show_settings" not in st.session_state:
        st.session_state.show_settings = False
    if "is_thinking" not in st.session_state:
        st.session_state.is_thinking = False
    if "selected_persona" not in st.session_state:
        st.session_state.selected_persona = "Default"
    
    # Create admin if not exists
    if not os.path.exists("mychat_users.json"):
        result = local_add_admin(ADMIN_EMAIL, ADMIN_PASSWORD, "Admin Joe")
        if result["success"]:
            secure_logger.log_info(f"Admin created: {ADMIN_EMAIL}")
    
    if not st.session_state.logged_in:
        if check_auto_login():
            st.rerun()
            return
    
    if not st.session_state.logged_in:
        login_ui()
        return
    
    # Set admin role
    admin_emails = [ADMIN_EMAIL, "admin@email.com"]
    if st.session_state.get("email") in admin_emails:
        st.session_state.role = "admin"
        users = load_users()
        if st.session_state.email in users:
            if users[st.session_state.email].get("role") != "admin":
                users[st.session_state.email]["role"] = "admin"
                save_users(users)
    
    # Sidebar
    with st.sidebar:
        st.markdown("""
        <div style="padding: 12px 0 16px 0; border-bottom: 1px solid rgba(255,255,255,0.06);">
            <div style="display: flex; align-items: center; gap: 10px;">
                <div style="width: 32px; height: 32px; background: #4d6bfe; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 16px; color: white;">A</div>
                <div>
                    <div style="font-size: 16px; font-weight: 600; color: #e8edf5;">{APP_NAME}</div>
                    <div style="font-size: 11px; color: #6a6a7a;">{APP_VERSION}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("New Chat", use_container_width=True, type="primary"):
            st.session_state.messages = []
            st.session_state.current_chat_index = None
            st.rerun()
        
        st.markdown("---")
        
        st.markdown("### AI Persona")
        selected_persona = st.selectbox("", list(AI_PERSONAS.keys()), key="persona_select")
        st.session_state.selected_persona = selected_persona
        prefs = load_preferences(st.session_state.username)
        prefs["persona"] = selected_persona
        save_preferences(st.session_state.username, prefs)
        
        st.markdown("---")
        
        st.markdown('<div style="font-size: 12px; color: #6a6a7a; padding: 4px 0 8px 0;">Chat History</div>', unsafe_allow_html=True)
        
        chat_history = load_chats()
        username = st.session_state.get("username", "User")
        
        if username in chat_history and chat_history[username]:
            grouped = group_chats_by_date(username)
            for group_name, chats in grouped.items():
                if chats:
                    st.caption(group_name)
                    for chat in chats:
                        idx = chat_history[username].index(chat)
                        title = chat.get("title", "New Chat")
                        if chat.get("pinned"):
                            title = f"Pinned: {title}"
                        is_active = st.session_state.get("current_chat_index") == idx
                        
                        col1, col2, col3 = st.columns([8, 1, 1])
                        with col1:
                            if is_active:
                                st.markdown(f'<div style="background:#2a2a3a;padding:4px 8px;border-radius:6px;border-left:3px solid #4d6bfe;margin:1px 0;"><span style="color:#e8edf5;font-size:13px;">{title}</span></div>', unsafe_allow_html=True)
                            else:
                                if st.button(title, key=f"hist_{idx}", use_container_width=True):
                                    st.session_state.messages = chat.get("messages", [])
                                    st.session_state.current_chat_index = idx
                                    st.rerun()
                        with col2:
                            if st.button("Pin", key=f"pin_{idx}"):
                                pin_chat(username, idx)
                                st.rerun()
                        with col3:
                            if st.button("Delete", key=f"del_{idx}"):
                                if delete_chat_from_history(username, idx):
                                    st.session_state.messages = []
                                    st.session_state.current_chat_index = None
                                    st.rerun()
        else:
            st.caption("No chat history")
        
        st.markdown("---")
        
        search = st.text_input("Search", placeholder="Search chat...", key="search_chat")
        if search:
            results = search_chats(username, search)
            if results:
                for r in results[:3]:
                    st.caption(f"- {r['title']}: {r['preview']}")
        
        st.markdown("---")
        
        model_options = ["Auto", "Groq", "Gemini", "OpenAI", "OpenRouter", "HuggingFace"]
        selected_model = st.selectbox("Model", model_options, index=0, label_visibility="collapsed")
        st.session_state.selected_model = selected_model
        
        if st.button("All Models" if st.session_state.get("penal_mode", True) else "Free Only", use_container_width=True):
            st.session_state.penal_mode = not st.session_state.get("penal_mode", True)
            st.rerun()
        
        if st.button("Voice Input", use_container_width=True):
            text = voice_input()
            if text:
                st.session_state.voice_text = text
                st.rerun()
        
        st.markdown("---")
        
        st.markdown(f"""
        <div style="border-top: 1px solid rgba(255,255,255,0.06); padding-top: 12px; margin-top: 8px;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <div style="width: 28px; height: 28px; background: #4d6bfe; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 600; font-size: 12px; color: white;">{st.session_state.get('username', 'U')[0].upper()}</div>
                <div>
                    <div style="font-size: 13px; color: #e8edf5;">{st.session_state.get('username', 'User')}</div>
                    <div style="font-size: 11px; color: #6a6a7a;">{st.session_state.get('role', 'user')}</div>
                    <div style="font-size: 10px; color: #4d6bfe;">Plan: {check_subscription(username)}</div>
                    <div style="font-size: 10px; color: #6a6a7a;">Requests: {get_remaining_requests(username)}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("Settings", use_container_width=True):
            st.session_state.show_settings = not st.session_state.get("show_settings", False)
        if st.session_state.get("show_settings", False):
            st.markdown("---")
            if st.button("Logout", use_container_width=True):
                clear_session(st.session_state.get("uid", ""))
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
        
        st.markdown(f"""
        <div style="border-top: 1px solid rgba(255,255,255,0.06); padding-top: 8px; margin-top: 8px;">
            <div style="font-size: 8px; color: #3a3a4a; text-align: center;">
                {APP_COPYRIGHT}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Main menu
    menu_options = [
        "Chat",
        "Poster Generator",
        "Video Generator",
        "Guru Malaysia",
        "Waze Navigation",
        "Tender Management",
        "Project Expense",
        "Settings"
    ]
    
    selected_menu = st.sidebar.radio("Menu", menu_options, label_visibility="collapsed")
    
    if selected_menu == "Chat":
        chat_ui()
        if "voice_text" in st.session_state and st.session_state.voice_text:
            process_chat_message(st.session_state.voice_text)
            st.session_state.voice_text = None
            st.rerun()
        if "selected_template" in st.session_state and st.session_state.selected_template:
            process_chat_message(st.session_state.selected_template)
            st.session_state.selected_template = None
            st.rerun()
    
    elif selected_menu == "Poster Generator":
        poster_generator_ui()
    
    elif selected_menu == "Video Generator":
        video_generator_ui()
    
    elif selected_menu == "Guru Malaysia":
        guru_malaysia_ui()
    
    elif selected_menu == "Waze Navigation":
        waze_features_tab()
    
    elif selected_menu == "Tender Management":
        tender_ui()
    
    elif selected_menu == "Project Expense":
        project_expense_ui()
    
    elif selected_menu == "Settings":
        settings_ui()

if __name__ == "__main__":
    main()
