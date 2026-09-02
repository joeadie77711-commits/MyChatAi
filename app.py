# app.py - MyChatAI Pro v71.5 (FULL CODE DENGAN LOCAL LOGIN)
# ============================================================
# VERSION: v71.5
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
# === VERSION ===
# ============================================================
APP_VERSION = "v71.5"
APP_NAME = "MyChatAI Pro"

# ============================================================
# === LOGGING SETUP ===
# ============================================================
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

try:
    handler = logging.handlers.RotatingFileHandler(
        'mychat_app.log',
        maxBytes=5*1024*1024,
        backupCount=3
    )
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
except Exception:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

# ============================================================
# === SECURE LOGGER ===
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
# === PAGE CONFIG ===
# ============================================================
st.set_page_config(
    page_title=f"{APP_NAME} {APP_VERSION}",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# === CONSTANTS ===
# ============================================================
MAX_MESSAGES = 100
API_TIMEOUT = 30
CACHE_INTERVAL = 10
BATCH_SIZE = 10
TYPING_SPEED_FAST = 0.005
TYPING_SPEED_SLOW = 0.015
MAX_INPUT_LENGTH = 4000
MAX_HISTORY_PER_USER = 50
MAX_CONTEXT_MESSAGES = 5

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
# === SESSION SALT ===
# ============================================================
_SESSION_SALT = st.secrets.get("SESSION_SECRET", "default_secret_change_me")
if not _SESSION_SALT or _SESSION_SALT == "default_secret_change_me":
    secure_logger.log_warning("SESSION_SECRET not configured in secrets! Using default.")
    _SESSION_SALT = "default_secret_change_me"

# ============================================================
# === CACHING ===
# ============================================================
@st.cache_data(ttl=300)
def load_users_cached():
    return safe_read_json("mychat_users.json", {})

@st.cache_data(ttl=60)
def load_usage_cached(username):
    data = safe_read_json("mychat_usage.json", {})
    return data.get(username, {"count": 0})

# ============================================================
# === PORTALOCKER FALLBACK ===
# ============================================================
try:
    import portalocker
    HAVE_PORTALOCKER = True
except ImportError:
    HAVE_PORTALOCKER = False
    secure_logger.log_warning("portalocker not installed.")

# ============================================================
# === REQUESTS SESSION ===
# ============================================================
def get_requests_session():
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=20)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    session.headers.update({
        'User-Agent': f'{APP_NAME}/{APP_VERSION}'
    })
    return session

requests_session = get_requests_session()

# ============================================================
# === SAFE JSON ACCESS ===
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
# === SAFE FILE OPERATIONS ===
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
# === RATE LIMITING ===
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
# === API KEYS ===
# ============================================================
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")
OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY", "")

# === ADMIN CREDENTIALS ===
ADMIN_EMAIL = st.secrets.get("ADMIN_EMAIL", "admin@gmail.com")
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "admin123")

try:
    MAX_FREE_REQUESTS = int(st.secrets.get("MAX_FREE_REQUESTS", 1000))
except (TypeError, ValueError):
    MAX_FREE_REQUESTS = 1000

# ============================================================
# === LOAD FUNCTIONS ===
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

# ============================================================
# === SMART CACHE ===
# ============================================================
class SmartCache:
    def __init__(self):
        self.cache = {}
        self.cache_time = {}
        self.cache_access = {}
        self.cache_duration = 3600
        self.max_cache_size = 200
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
            expired_keys = [
                k for k, v in self.cache_time.items()
                if current_time - v > self.cache_duration
            ]
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
# === TYPING EFFECT ===
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
# === OPENAI SDK VERSION CHECK ===
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
# === FIREBASE IMPORTS ===
# ============================================================
FIREBASE_AVAILABLE = False

try:
    import firebase_admin
    from firebase_admin import credentials, firestore, auth
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    secure_logger.log_warning("Firebase admin not installed")

# ============================================================
# === FIREBASE MANAGER ===
# ============================================================
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
            secure_logger.log_error("Firebase not ready for login")
            return {"success": False, "error": "Firebase service not ready"}
        if not email or not password:
            return {"success": False, "error": "Email and password required"}
        try:
            email = email.strip().lower()
            try:
                user = self.auth.get_user_by_email(email)
            except Exception as e:
                secure_logger.log_error(f"User not found: {str(e)}")
                return {"success": False, "error": "Email not found. Please register first."}
            if user:
                try:
                    users_ref = self.db.collection("users").document(user.uid)
                    doc = users_ref.get()
                    profile = doc.to_dict() if doc.exists else {}
                    if profile.get("status") == "disabled":
                        return {"success": False, "error": "Account disabled"}
                    secure_logger.log_info(f"Login successful: {email}")
                    return {
                        "success": True,
                        "uid": user.uid,
                        "email": user.email,
                        "profile": profile
                    }
                except Exception as e:
                    secure_logger.log_error(f"Profile fetch error: {str(e)}")
                    return {
                        "success": True,
                        "uid": user.uid,
                        "email": user.email,
                        "profile": {}
                    }
            return {"success": False, "error": "User not found"}
        except Exception as e:
            error_msg = str(e)
            secure_logger.log_error(f"Login error: {error_msg}")
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
            user = self.auth.create_user(
                email=email,
                password=password,
                display_name=name or email.split("@")[0]
            )
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
                secure_logger.log_info(f"User registered: {email}")
                return {"success": True, "uid": user.uid}
            else:
                return {"success": False, "error": "Registration failed"}
        except Exception as e:
            error_msg = str(e)
            secure_logger.log_error(f"Registration error: {error_msg}")
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
                users_ref.update({
                    "total_requests": current + 1,
                    "last_active": datetime.datetime.now().isoformat()
                })
            else:
                users_ref.set({
                    "total_requests": 1,
                    "last_active": datetime.datetime.now().isoformat()
                })
        except Exception as e:
            secure_logger.log_error(f"Usage increment error: {str(e)}")

    def save_chat_message(self, uid, role, content, response=None):
        if not self.is_ready():
            return
        try:
            chat_ref = self.db.collection("users").document(uid).collection("chats")
            data = {
                "role": role,
                "content": content[:4000],
                "timestamp": datetime.datetime.now().isoformat()
            }
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
            activity_ref.add({
                "uid": uid,
                "action": action,
                "timestamp": datetime.datetime.now().isoformat()
            })
        except Exception as e:
            secure_logger.log_error(f"Log activity error: {str(e)}")

firebase_manager = FirebaseManager()

# ============================================================
# === CONTEXT MEMORY ===
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
        if len(self.memory[username]) > MAX_HISTORY_PER_USER:
            self.memory[username] = self.memory[username][-MAX_HISTORY_PER_USER:]
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
                formatted += f"User: {q_text}\n"
                formatted += f"Assistant: {a_text}\n"
            return formatted
        return ""

    def clear_user_context(self, username):
        if username in self.memory:
            self.memory[username] = []
            self._save_memory()
            return True
        return False

context_memory = ContextMemory()

# ============================================================
# === SMART AI FUNCTIONS ===
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
        return {"words": 0, "reading_time": 0, "has_code": False, "has_list": False}, 0
    words = len(response.split())
    reading_time = words / 200
    has_code = "```" in response or "def " in response
    has_list = "1. " in response or "- " in response
    analysis = {
        "words": words,
        "reading_time": reading_time,
        "has_code": has_code,
        "has_list": has_list
    }
    score = min(100, words * 2 + (10 if has_code else 0) + (5 if has_list else 0))
    return analysis, score

def safe_rerun():
    st.rerun()

# ============================================================
# === AI API CALLS ===
# ============================================================
def call_groq(prompt):
    if not GROQ_API_KEY:
        raise Exception("Groq API key not set")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "llama3-8b-8192",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1000
    }
    response = requests_session.post(url, json=data, headers=headers, timeout=API_TIMEOUT)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    raise Exception(f"Groq API error: {response.status_code}")

def call_gemini(prompt):
    if not GEMINI_API_KEY:
        raise Exception("Gemini API key not set")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    data = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    response = requests_session.post(url, json=data, timeout=API_TIMEOUT)
    if response.status_code == 200:
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]
    raise Exception(f"Gemini API error: {response.status_code}")

def call_openai(prompt):
    if not OPENAI_API_KEY:
        raise Exception("OpenAI API key not set")
    if OPENAI_V1:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000
        )
        return response.choices[0].message.content
    else:
        openai.api_key = OPENAI_API_KEY
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000
        )
        return response["choices"][0]["message"]["content"]

def call_openrouter(prompt):
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
        "max_tokens": 1000
    }
    response = requests_session.post(url, json=data, headers=headers, timeout=API_TIMEOUT)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    raise Exception(f"OpenRouter API error: {response.status_code}")

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
    return "I'm currently using free API. Please try again later or configure API keys."

def call_ai_api(prompt, username):
    # Try Groq first
    if GROQ_API_KEY:
        try:
            return call_groq(prompt)
        except Exception as e:
            secure_logger.log_error(f"Groq error: {str(e)}")
    # Try Gemini
    if GEMINI_API_KEY:
        try:
            return call_gemini(prompt)
        except Exception as e:
            secure_logger.log_error(f"Gemini error: {str(e)}")
    # Try OpenRouter
    if OPENROUTER_API_KEY:
        try:
            return call_openrouter(prompt)
        except Exception as e:
            secure_logger.log_error(f"OpenRouter error: {str(e)}")
    # Try OpenAI
    if OPENAI_API_KEY and OPENAI_AVAILABLE:
        try:
            return call_openai(prompt)
        except Exception as e:
            secure_logger.log_error(f"OpenAI error: {str(e)}")
    # Fallback to free API
    return call_free_api(prompt)

def smart_ai(username, prompt, streaming=False, use_cache=True):
    if not prompt or not prompt.strip():
        return "Please enter a question."
    if not check_rate_limit(username):
        return "Rate limit exceeded. Please wait a moment."
    prompt_lower = prompt.lower()
    if "hello" in prompt_lower or "hai" in prompt_lower:
        return "Hello! How can I assist you today?"
    if "apa khabar" in prompt_lower:
        return "Saya sihat, terima kasih! Bagaimana dengan anda?"
    if use_cache:
        cached = smart_cache.get_cached_response(prompt)
        if cached:
            return cached
    try:
        response = call_ai_api(prompt, username)
        if response and isinstance(response, str):
            context_memory.add_conversation(username, prompt, response)
            if use_cache:
                smart_cache.save_response(prompt, response)
            return response
        return "I couldn't generate a response. Please try again."
    except Exception as e:
        secure_logger.log_error(f"AI error: {str(e)}")
        return f"Error: {str(e)}"

# ============================================================
# === SESSION FUNCTIONS ===
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
        return False
    except Exception as e:
        secure_logger.log_error(f"Auto login error: {str(e)}")
        return False

# ============================================================
# === LOCAL LOGIN FUNCTIONS (TAMBAHAN UNTUK LOCAL LOGIN) ===
# ============================================================
def local_login(email, password):
    """Login guna local JSON file - Tanpa Firebase"""
    users = load_users()
    if email in users:
        user = users[email]
        if user.get("password") == password:
            return {
                "success": True,
                "uid": email,
                "email": email,
                "profile": {
                    "name": user.get("name", "User"),
                    "role": user.get("role", "user")
                }
            }
        else:
            return {"success": False, "error": "Invalid password. Please try again."}
    else:
        return {"success": False, "error": "Email not found. Please register first."}

def local_register(email, password, name=""):
    """Register guna local JSON file - Tanpa Firebase"""
    users = load_users()
    # Check email dah wujud
    if email in users:
        return {"success": False, "error": "Email already registered. Please login."}
    # Simpan user baru
    users[email] = {
        "name": name or email.split("@")[0],
        "password": password,
        "role": "user",
        "created": datetime.datetime.now().isoformat(),
        "last_login": None,
        "total_requests": 0
    }
    save_users(users)
    return {"success": True, "uid": email}

def local_add_admin(email, password, name="Admin"):
    """Tambah admin ke local JSON"""
    users = load_users()
    if email in users:
        users[email]["role"] = "admin"
        users[email]["name"] = name
        save_users(users)
        return {"success": True, "message": f"Admin {email} updated"}
    users[email] = {
        "name": name,
        "password": password,
        "role": "admin",
        "created": datetime.datetime.now().isoformat(),
        "last_login": None,
        "total_requests": 0
    }
    save_users(users)
    return {"success": True, "message": f"Admin {email} created"}

def local_list_users():
    """Senarai semua user local"""
    users = load_users()
    user_list = []
    for email, data in users.items():
        user_list.append({
            "email": email,
            "name": data.get("name", ""),
            "role": data.get("role", "user"),
            "created": data.get("created", "")
        })
    return user_list

# ============================================================
# === LOGIN UI ===
# ============================================================
def login_ui():
    st.markdown("""
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;padding:20px;">
        <div style="max-width:420px;width:100%;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:16px;padding:40px 32px;">
            <div style="text-align:center;margin-bottom:30px;">
                <h1 style="font-size:28px;font-weight:700;color:#e8edf5;letter-spacing:-0.5px;">MyChatAI Pro</h1>
                <p style="color:#8a8a9a;font-size:14px;margin-top:4px;">6 AI Models</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Status Firebase
        if firebase_manager.is_ready():
            st.success("✅ Firebase Connected")
        else:
            st.info("ℹ️ Using Local Login (Firebase not connected)")

        with st.form("login_form"):
            email = st.text_input(
                "Email",
                placeholder="Enter your email",
                key="login_email",
                value=st.session_state.get("login_email", "")
            )
            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
                key="login_password"
            )
            remember_me = st.checkbox("Remember Me", value=True)

            submitted = st.form_submit_button("Login", use_container_width=True)

            if submitted:
                if not email or not password:
                    st.warning("Please enter email and password")
                else:
                    with st.spinner("Logging in..."):
                        # ===== GUNA LOCAL LOGIN (DEFAULT) =====
                        USE_LOCAL_LOGIN = True
                        if USE_LOCAL_LOGIN:
                            result = local_login(email, password)
                        elif firebase_manager.is_ready():
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
                            st.session_state.session_hash = hashlib.sha256(
                                f"{result['uid']}:{_SESSION_SALT}".encode()
                            ).hexdigest()

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
                reg_email = st.text_input(
                    "Email",
                    placeholder="Enter your email",
                    key="reg_email"
                )
                reg_password = st.text_input(
                    "Password",
                    type="password",
                    placeholder="Password (min 6 chars)",
                    key="reg_password"
                )
                reg_name = st.text_input(
                    "Display Name",
                    placeholder="Your name",
                    key="reg_name"
                )

                reg_submitted = st.form_submit_button("Register", use_container_width=True)

                if reg_submitted:
                    if not reg_email or not reg_password:
                        st.warning("Please fill in email and password")
                    elif len(reg_password) < 6:
                        st.warning("Password must be at least 6 characters")
                    else:
                        with st.spinner("Creating account..."):
                            # ===== GUNA LOCAL REGISTER (DEFAULT) =====
                            USE_LOCAL_LOGIN = True
                            if USE_LOCAL_LOGIN:
                                result = local_register(reg_email, reg_password, reg_name)
                            elif firebase_manager.is_ready():
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
# === CHAT UI ===
# ============================================================
def process_chat_message(message):
    username = st.session_state.username
    uid = st.session_state.get("uid")
    safe_input = sanitize_input(message, MAX_INPUT_LENGTH)

    if uid and firebase_manager.is_ready():
        firebase_manager.save_chat_message(uid, "user", safe_input)

    st.session_state.messages.append({"role": "user", "content": safe_input})

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
            st.session_state.messages.append({"role": "ai", "content": safe_resp})
            if uid and firebase_manager.is_ready():
                firebase_manager.save_chat_message(uid, "ai", safe_resp, safe_resp)
        else:
            safe_resp = sanitize_input(str(response_text), MAX_INPUT_LENGTH)
            st.session_state.messages.append({"role": "ai", "content": safe_resp})
            if uid and firebase_manager.is_ready():
                firebase_manager.save_chat_message(uid, "ai", safe_resp, safe_resp)

        placeholder.empty()

def display_example_questions():
    examples = {
        "General": [
            "What is artificial intelligence?",
            "How does machine learning work?",
            "Explain quantum computing in simple terms"
        ],
        "Coding": [
            "Write a Python script to sort a list",
            "How to create a REST API in Python?",
            "Explain SQL joins with examples"
        ],
        "Creative": [
            "Write a haiku about coding",
            "Create a story about a robot learning to love",
            "Write a poem about technology"
        ],
        "Life": [
            "Give me a workout routine for beginners",
            "How to improve productivity?",
            "Tips for better sleep"
        ],
        "Learning": [
            "Explain blockchain technology",
            "What is the difference between AI and ML?",
            "How to learn a new language?"
        ]
    }
    st.markdown("""
    <div style="text-align: center; padding: 40px 20px;">
        <div style="font-size: 18px; color: #e8edf5; font-weight: 500;">How can I help you today?</div>
        <div style="font-size: 13px; color: #6a6a7a; margin-bottom: 20px;">Try asking me something from these categories:</div>
    </div>
    """, unsafe_allow_html=True)

    categories = list(examples.keys())
    selected_category = st.radio("Select category", categories, horizontal=True, label_visibility="collapsed")
    questions = examples.get(selected_category, [])
    cols = st.columns(2)
    for idx, question in enumerate(questions):
        with cols[idx % 2]:
            if st.button(question, use_container_width=True):
                process_chat_message(question)
                safe_rerun()

def display_confidence(response, prompt):
    score = calculate_confidence(response, prompt)
    label = get_confidence_label(score)
    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 8px; margin-top: 4px; padding-left: 16px;">
        <span style="font-size: 11px; color: #6a6a7a;">Confidence:</span>
        <span style="font-size: 11px; color: #e8edf5;">{score}%</span>
        <span style="font-size: 11px; color: #6a6a7a;">•</span>
        <span style="font-size: 11px; color: #e8edf5;">{label}</span>
    </div>
    """, unsafe_allow_html=True)

def display_response_analysis(response):
    analysis, score = analyze_response(response)
    st.markdown(f"""
    <div style="padding: 8px 12px; background: #1a1a2a; border-radius: 6px; margin-top: 4px; padding-left: 16px;">
        <div style="display: flex; gap: 16px; flex-wrap: wrap;">
            <span style="font-size: 11px; color: #6a6a7a;">Quality: {score}%</span>
            <span style="font-size: 11px; color: #6a6a7a;">{analysis['words']} words</span>
            <span style="font-size: 11px; color: #6a6a7a;">{analysis['reading_time']:.1f} min read</span>
            {f'<span style="font-size: 11px; color: #6a6a7a;">Contains code</span>' if analysis['has_code'] else ''}
            {f'<span style="font-size: 11px; color: #6a6a7a;">Contains list</span>' if analysis['has_list'] else ''}
        </div>
    </div>
    """, unsafe_allow_html=True)

def chat_ui():
    username = st.session_state.username
    uid = st.session_state.get("uid")
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if len(st.session_state.messages) > MAX_MESSAGES:
        st.session_state.messages = st.session_state.messages[-MAX_MESSAGES:]

    penal_status = "ON" if st.session_state.get("penal_mode", True) else "OFF"

    st.markdown(f"""
    <div style="padding: 8px 0 16px 0; border-bottom: 1px solid rgba(255,255,255,0.06); margin-bottom: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
            <div>
                <div style="font-size: 16px; font-weight: 500; color: #e8edf5;">Chat</div>
                <div style="font-size: 12px; color: #6a6a7a; margin-top: 2px;">
                    {len(st.session_state.messages)} messages
                </div>
            </div>
            <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
                <span style="font-size: 10px; color: {'#10b981' if st.session_state.get('penal_mode', True) else '#ef4444'}; background: #1a1a2a; padding: 4px 12px; border-radius: 12px;">
                    Penal: {penal_status}
                </span>
                <span style="font-size: 10px; color: #4d6bfe; background: #1a1a2a; padding: 4px 12px; border-radius: 12px;">
                    {st.session_state.get('selected_model', 'Auto').upper()}
                </span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([3, 1])
    with col1:
        penal_mode = st.session_state.get("penal_mode", True)
        if penal_mode:
            st.success("Penal: ON - All models")
            if st.button("Turn OFF - Free Only", use_container_width=True):
                st.session_state.penal_mode = False
                safe_rerun()
        else:
            st.warning("Penal: OFF - Free models only")
            if st.button("Turn ON - All Models", use_container_width=True):
                st.session_state.penal_mode = True
                safe_rerun()
    with col2:
        if st.button("New Chat", use_container_width=True):
            st.session_state.messages = []
            safe_rerun()

    st.divider()

    if not st.session_state.messages:
        display_example_questions()
        return

    for idx, msg in enumerate(st.session_state.messages):
        if msg["role"] == "user":
            safe_content = msg["content"]
            st.markdown(f"""
            <div style="display: flex; justify-content: flex-end; margin-bottom: 12px;">
                <div style="background: #2a2a3a; padding: 10px 16px; border-radius: 12px 12px 4px 12px; max-width: 80%; font-size: 14px; line-height: 1.6;">
                    {safe_content}
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            safe_content = msg["content"]
            st.markdown(f"""
            <div style="display: flex; justify-content: flex-start; margin-bottom: 8px;">
                <div style="background: #1a1a2a; padding: 10px 16px; border-radius: 12px 12px 12px 4px; max-width: 80%; font-size: 14px; line-height: 1.6; border: 1px solid #2a2a3a;">
                    {safe_content}
                </div>
            </div>
            """, unsafe_allow_html=True)
        if idx > 0:
            display_confidence(msg["content"], st.session_state.messages[idx-1]["content"])
        display_response_analysis(msg["content"])

    st.markdown("---")
    col1, col2 = st.columns([10, 1])
    with col1:
        user_input = st.text_area("", key="chat_input", placeholder="Type your message... (Ctrl+Enter to send)", label_visibility="collapsed", height=48)
    with col2:
        if st.button("Send", key="send_btn", use_container_width=True):
            if user_input.strip():
                process_chat_message(user_input)
                safe_rerun()

# ============================================================
# === POSTER GENERATOR ===
# ============================================================
def poster_generator_ui():
    st.markdown("### Poster Generator")
    if not OPENAI_API_KEY:
        st.info("Using free image generation. Add OpenAI API key for higher quality.")

    title = st.text_input("Title", placeholder="e.g., AI Conference 2026", key="poster_title")
    if not title:
        st.info("Please enter a title to generate poster")
        return

    style = st.selectbox("Style", ["Modern Minimalist", "Cinematic", "Cyberpunk", "Photorealistic", "Digital Art", "Vintage"])
    color = st.selectbox("Color", ["Blue & Purple", "Red & Gold", "Dark & Neon", "Pastel", "Monochrome"])

    use_dalle = st.checkbox("Use DALL-E (requires OpenAI API key)", value=bool(OPENAI_API_KEY), disabled=not bool(OPENAI_API_KEY))

    if st.button("Generate Poster", use_container_width=True, type="primary"):
        if title:
            with st.spinner("Generating poster..."):
                try:
                    prompt = f"Create a {style} poster design for '{title}', {color} color scheme, high quality, 4K"

                    if use_dalle and OPENAI_API_KEY and OPENAI_AVAILABLE:
                        if OPENAI_V1:
                            dalle = openai.OpenAI(api_key=OPENAI_API_KEY)
                            response = dalle.images.generate(
                                model="dall-e-3",
                                prompt=prompt,
                                size="1024x1024",
                                quality="standard",
                                n=1
                            )
                        else:
                            openai.api_key = OPENAI_API_KEY
                            try:
                                response = openai.Image.create(
                                    prompt=prompt,
                                    n=1,
                                    size="1024x1024"
                                )
                            except AttributeError:
                                st.error("OpenAI Image API not available. Please upgrade openai library.")
                                return

                        image_url = response.data[0].url
                        img_response = requests_session.get(image_url, timeout=30)
                        if img_response.status_code == 200:
                            img = Image.open(BytesIO(img_response.content))
                            st.image(img, caption=title, use_container_width=True)
                            img_bytes = BytesIO()
                            img.save(img_bytes, format='PNG')
                            st.download_button("Download", img_bytes.getvalue(), f"poster_{title.replace(' ', '_')}.png", "image/png")
                        else:
                            st.error("Failed to generate poster")
                    else:
                        free_prompt = f"{style} poster for '{title}', {color} color scheme"
                        encoded_prompt = quote(free_prompt)
                        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
                        response = requests_session.get(url, timeout=API_TIMEOUT)
                        if 200 <= response.status_code < 300:
                            img = Image.open(BytesIO(response.content))
                            st.image(img, caption=title, use_container_width=True)
                            img_bytes = BytesIO()
                            img.save(img_bytes, format='PNG')
                            st.download_button("Download", img_bytes.getvalue(), f"poster_{title.replace(' ', '_')}.png", "image/png")
                        else:
                            st.error("Failed to generate poster")
                except Exception as e:
                    st.error(f"Error: {str(e)}")

# ============================================================
# === VIDEO GENERATOR ===
# ============================================================
def video_generator_ui():
    st.markdown("### Video Generator")
    prompt = st.text_area("Describe the video", height=80, placeholder="e.g., A futuristic city with flying cars")
    if not prompt:
        st.info("Please describe the video you want to generate")
        return
    duration = st.slider("Duration (seconds)", 3, 15, 5)
    if st.button("Generate Video", use_container_width=True, type="primary"):
        if prompt:
            with st.spinner("Generating video..."):
                try:
                    encoded_prompt = quote(prompt[:200])
                    url = f"https://image.pollinations.ai/video?prompt={encoded_prompt}&duration={duration}"
                    response = requests_session.get(url, timeout=API_TIMEOUT)
                    if 200 <= response.status_code < 300:
                        st.video(response.content)
                        st.success("Video generated successfully!")
                    else:
                        st.error("Failed to generate video")
                except Exception as e:
                    st.error(f"Error: {str(e)}")

# ============================================================
# === WAZE FEATURES ===
# ============================================================
def waze_map_free():
    st.markdown("### Waze Live Map")
    lat = st.number_input("Latitude", value=3.1585, format="%.4f")
    lon = st.number_input("Longitude", value=101.7118, format="%.4f")
    zoom = st.slider("Zoom Level", 5, 17, 14)

    iframe_html = f"""
    <iframe src="https://embed.waze.com/iframe?zoom={zoom}&lat={lat}&lon={lon}&pin=1"
    width="100%" height="450" style="border: none; border-radius: 12px; border: 1px solid #2a2a3a;">
    </iframe>
    """
    st.components.v1.html(iframe_html, height=470)

    if st.button("Navigate with Waze"):
        st.markdown(f"""
        <a href="https://waze.com/ul?ll={lat}%2C{lon}&navigate=yes" target="_blank"
        style="display: block; text-align: center; background: #4d6bfe; color: white;
        padding: 10px; border-radius: 8px; text-decoration: none; font-weight: 500;">
        Open Waze App
        </a>
        """, unsafe_allow_html=True)

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
    tabs = st.tabs(["Map", "Emergency"])
    with tabs[0]:
        waze_map_free()
    with tabs[1]:
        emergency_contacts_free()

# ============================================================
# === GURU MALAYSIA ===
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

    jenis_bahan = st.radio("Jenis Bahan", ["Soalan Latihan", "RPH", "Nota Ringkas", "Kuiz", "Lembaran Kerja"], horizontal=True)
    tahap = st.select_slider("Tahap Kesukaran", options=["Mudah", "Sederhana", "Susah"])

    if st.button("Jana Bahan", use_container_width=True, type="primary"):
        if mata_pelajaran and bab:
            with st.spinner("Menjana bahan..."):
                st.success(f"Bahan untuk {mata_pelajaran} - {bab} (Tahap {tahap})")
                if "Soalan" in jenis_bahan or "Kuiz" in jenis_bahan:
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
        else:
            st.warning("Sila pilih tahun, mata pelajaran dan bab")

# ============================================================
# === TENDER SYSTEM ===
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
            "awarded_to": None
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
        return {
            "total_tenders": len(self.tenders),
            "open": len([t for t in self.tenders if t["status"] == "Open"]),
            "closed": len([t for t in self.tenders if t["status"] == "Closed"]),
            "awarded": len([t for t in self.tenders if t["status"] == "Awarded"]),
            "total_budget": sum(t["budget"] for t in self.tenders)
        }

def tender_ui():
    st.markdown("### Tender Management System")
    ts = TenderSystem()
    stats = ts.get_tender_summary()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Tender", stats["total_tenders"])
    with col2:
        st.metric("Tender Dibuka", stats["open"])
    with col3:
        st.metric("Tender Ditutup", stats["closed"])
    with col4:
        st.metric("Tender Dianugerah", stats["awarded"])

    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs(["Tender", "Buka Tender", "Bida", "MOF"])

    with tab1:
        st.subheader("Senarai Tender")
        tenders = ts.tenders
        if tenders:
            for tender in tenders:
                with st.expander(f"{tender['name']} - {tender['status']}"):
                    st.caption(f"Kategori: {tender['category']}")
                    st.caption(f"Bajet: RM {tender['budget']:,.2f}")
                    st.caption(f"Tarikh Tutup: {tender['deadline']}")
                    st.caption(f"Bidaan: {len(tender['bids'])}")
                    if tender.get('awarded_to'):
                        st.success(f"Anugerah kepada: {tender['awarded_to']}")
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
                category = st.selectbox("Kategori", ["Construction", "IT", "Consultancy", "Supply", "Services"])
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

# ============================================================
# === PROJECT EXPENSE MANAGEMENT ===
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
            "status": "Active",
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
            "status": "Verified",
            "created": datetime.datetime.now().isoformat()
        }
        self.expenses.append(expense)
        for p in self.projects:
            if p["id"] == project_id:
                p["total_expenses"] = sum(e["total"] for e in self.expenses if e["project_id"] == p["id"])
                p["expenses"].append(expense["id"])
        self.save_data()
        return {"success": True, "expense": expense}

    def get_expenses(self, project_id=None):
        if project_id:
            return [e for e in self.expenses if e["project_id"] == project_id]
        return self.expenses

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
            "balance": project["project_value"] - total_expenses,
            "percentage": (total_expenses / project["project_value"] * 100) if project["project_value"] > 0 else 0,
            "categories": categories,
            "expenses": expenses
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

    tab1, tab2, tab3 = st.tabs(["Projects", "Add Expense", "Report"])

    with tab1:
        st.subheader("Projects List")
        with st.expander("Add New Project", expanded=False):
            with st.form("add_project_form"):
                col1, col2 = st.columns(2)
                with col1:
                    project_name = st.text_input("Project Name *")
                    project_code = st.text_input("Project Code")
                    client_name = st.text_input("Client Name")
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

        projects = pem.projects
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
        active_projects = pem.get_projects(["Active"])
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
                with col2:
                    supplier = st.text_input("Supplier *")
                    quantity = st.number_input("Quantity", min_value=1, value=1)
                    unit_price = st.number_input("Unit Price (RM) *", min_value=0.0, value=1.0)
                total = quantity * unit_price
                st.caption(f"Total: RM {total:,.2f}")
                invoice_no = st.text_input("Invoice No.")
                description = st.text_area("Description", height=60)
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
                            "payment_method": "Cash"
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
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.caption(e['item_name'])
                with col2:
                    st.caption(f"RM {e['total']:,.2f}")
                with col3:
                    st.caption(e['date'][:10])
                if st.button("X", key=f"del_exp_{e['id']}"):
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
            else:
                st.info("No project summary available")
        else:
            st.info("No projects for report")

# ============================================================
# === SETTINGS UI ===
# ============================================================
def settings_ui():
    st.markdown("### Settings")

    st.subheader("Account")
    st.caption(f"Email: {st.session_state.get('email', '')}")
    st.caption(f"Username: {st.session_state.get('username', '')}")
    st.caption(f"Role: {st.session_state.get('role', 'user')}")
    st.caption(f"UID: {st.session_state.get('uid', '')}")

    st.divider()

    st.subheader("API Keys Configuration")
    st.info("API keys are configured in .streamlit/secrets.toml")

    col1, col2 = st.columns(2)
    with col1:
        st.caption(f"Groq API: {'✅ Configured' if GROQ_API_KEY else '❌ Not Configured'}")
        st.caption(f"Gemini API: {'✅ Configured' if GEMINI_API_KEY else '❌ Not Configured'}")
        st.caption(f"OpenAI API: {'✅ Configured' if OPENAI_API_KEY else '❌ Not Configured'}")
    with col2:
        st.caption(f"OpenRouter API: {'✅ Configured' if OPENROUTER_API_KEY else '❌ Not Configured'}")
        st.caption(f"Firebase: {'✅ Connected' if firebase_manager.is_ready() else '❌ Not Connected'}")
        st.caption(f"Max Free Requests: {MAX_FREE_REQUESTS}")

    st.divider()

    st.subheader("System")
    st.caption(f"Version: v71.5")
    st.caption(f"Python: {sys.version}")

    st.subheader("Local Users")
    users = local_list_users()
    if users:
        for user in users:
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.caption(user["email"])
            with col2:
                st.caption(user["role"])
            with col3:
                st.caption(user["name"])
    else:
        st.info("No local users registered yet")

    if st.button("Clear Cache", use_container_width=True):
        try:
            smart_cache.cache = {}
            smart_cache.cache_time = {}
            st.success("Cache cleared!")
        except:
            st.error("Failed to clear cache")

# ============================================================
# === MAIN APP ===
# ============================================================
def main():
    # Initialize session state
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "penal_mode" not in st.session_state:
        st.session_state.penal_mode = True
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = "Auto"

    # ===== SETUP ADMIN LOCAL (FIRST TIME) =====
    # Ini akan create admin secara automatik kali pertama
    # ===========================================
    if not os.path.exists("mychat_users.json"):
        admin_email = "joe.adie77712@gmail.com"
        admin_password = "Admin123456"
        result = local_add_admin(admin_email, admin_password, "Admin Joe")
        if result["success"]:
            print(f"✅ Admin created: {admin_email}")
            print(f"🔑 Password: {admin_password}")

    # Check auto login
    if not st.session_state.logged_in:
        if check_auto_login():
            st.rerun()
            return

    if not st.session_state.logged_in:
        login_ui()
        return

    # Main app UI
    st.sidebar.markdown(f"## MyChatAI Pro")
    st.sidebar.markdown(f"**Version:** v71.5")
    st.sidebar.markdown(f"**User:** {st.session_state.get('username', 'User')}")
    st.sidebar.markdown(f"**Role:** {st.session_state.get('role', 'user')}")

    # Sidebar navigation
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

    selected_menu = st.sidebar.radio("Menu", menu_options)

    # Logout button
    if st.sidebar.button("Logout", use_container_width=True):
        clear_session(st.session_state.get("uid", ""))
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    # Display selected menu
    if selected_menu == "Chat":
        chat_ui()
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
