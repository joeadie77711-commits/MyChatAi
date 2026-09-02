# app.py - MyChatAI Pro v71.2 (FINAL - SEMUA PEMBAIKAN)
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
APP_VERSION = "v71.2"
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
# === SESSION SALT - WAJIB ADA DI SECRETS ===
# ============================================================
_SESSION_SALT = st.secrets.get("SESSION_SECRET")
if not _SESSION_SALT:
    secure_logger.log_error("SESSION_SECRET not configured in secrets!")
    st.error("SESSION_SECRET not configured. Please add to .streamlit/secrets.toml")
    st.stop()

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
    secure_logger.log_warning("portalocker not installed. File operations may have race conditions.")

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
                    portalocker.lock(f, portalocker.LOCK_SH)
                data = json.load(f)
                if HAVE_PORTALOCKER:
                    portalocker.unlock(f)
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
                    portalocker.lock(f, portalocker.LOCK_EX)
                json.dump(data, f, indent=2, ensure_ascii=False)
                if HAVE_PORTALOCKER:
                    portalocker.unlock(f)
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
# === RATE LIMITING - IN-MEMORY ONLY ===
# ============================================================
_rate_limit_cache = {}
_rate_limit_cache_lock = threading.RLock()

def check_rate_limit(username, limit=30, window=60):
    """In-memory rate limiting - no file I/O"""
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
    
    secure_logger.log_info(f"OpenAI SDK version: {OPENAI_SDK_VERSION}, V1: {OPENAI_V1}, Legacy: {OPENAI_LEGACY}")
except ImportError:
    OPENAI_AVAILABLE = False
    secure_logger.log_warning("OpenAI library not installed")

# ============================================================
# === FIREBASE IMPORTS - TANPA PYREBASE ===
# ============================================================
FIREBASE_AVAILABLE = False
PYBASE_AVAILABLE = False

try:
    import firebase_admin
    from firebase_admin import credentials, firestore, auth
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    secure_logger.log_warning("Firebase admin not installed")

# PYREBASE TIDAK DIGUNAKAN - BUANG
# try:
#     import pyrebase
#     PYBASE_AVAILABLE = True
# except ImportError:
#     PYBASE_AVAILABLE = False

# ============================================================
# === FIREBASE MANAGER - GUNA REST API (TANPA PYREBASE) ===
# ============================================================
class FirebaseManager:
    def __init__(self):
        self.initialized = False
        self.db = None
        self.auth_client = None
        self._batch_queue = []
        self._batch_lock = threading.Lock()
        self._init_firebase()

    def _init_firebase(self):
        try:
            secure_logger.log_info("Initializing Firebase...")
            
            # Check Firebase config
            required_keys = ["FIREBASE_API_KEY", "FIREBASE_AUTH_DOMAIN", "FIREBASE_PROJECT_ID"]
            missing_keys = []
            for key in required_keys:
                if not st.secrets.get(key):
                    missing_keys.append(key)
                    secure_logger.log_warning(f"Missing Firebase config: {key}")

            if missing_keys:
                secure_logger.log_error(f"Missing Firebase config: {missing_keys}")
                self.initialized = False
                return

            # Initialize Firebase Admin for Firestore
            if FIREBASE_AVAILABLE:
                try:
                    firebase_admin.get_app()
                except ValueError:
                    service_account_str = st.secrets.get("FIREBASE_SERVICE_ACCOUNT", "")
                    if service_account_str:
                        try:
                            if isinstance(service_account_str, str):
                                service_account = json.loads(service_account_str)
                            else:
                                service_account = service_account_str
                            if service_account and isinstance(service_account, dict):
                                cred = credentials.Certificate(service_account)
                                firebase_admin.initialize_app(cred)
                                secure_logger.log_info("Firebase Admin initialized with service account")
                            else:
                                secure_logger.log_warning("Invalid service account format")
                                firebase_admin.initialize_app()
                        except Exception as e:
                            secure_logger.log_error(f"Service account error: {str(e)}")
                            firebase_admin.initialize_app()
                    else:
                        firebase_admin.initialize_app()
                        secure_logger.log_info("Firebase Admin initialized without service account")

                    self.db = firestore.client()
                    self.auth_client = auth
                    secure_logger.log_info("Firestore client initialized")
                except Exception as e:
                    secure_logger.log_error(f"Firebase Admin init error: {str(e)}")

            self.initialized = True
            secure_logger.log_info("Firebase initialized successfully!")
            
        except Exception as e:
            secure_logger.log_error(f"Firebase init error: {str(e)}")
            secure_logger.log_error(traceback.format_exc())
            self.initialized = False

    def is_ready(self):
        return self.initialized

    def _flush_batch(self):
        if not self.db or not self._batch_queue:
            return
        
        try:
            batch = self.db.batch()
            for item in self._batch_queue[:BATCH_SIZE]:
                doc_ref = self.db.collection("users").document(item["uid"]).collection("chats").document()
                batch.set(doc_ref, item["data"])
            
            for item in self._batch_queue[:BATCH_SIZE]:
                self.db.collection("users").document(item["uid"]).update({
                    "last_active": datetime.datetime.now().isoformat()
                })
            
            batch.commit()
            
            with self._batch_lock:
                self._batch_queue = self._batch_queue[BATCH_SIZE:]
            
            secure_logger.log_info(f"Batch saved {BATCH_SIZE} messages")
        except Exception as e:
            secure_logger.log_error(f"Batch save error: {str(e)}")

    def _login_via_rest(self, email, password):
        """Login using Firebase REST API - NO PYREBASE"""
        try:
            api_key = st.secrets.get("FIREBASE_API_KEY")
            if not api_key:
                return {"success": False, "error": "Firebase API key not configured"}
            
            email = email.strip().lower()
            secure_logger.log_info(f"Attempting login via REST for: {email}")
            
            url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
            payload = {
                "email": email,
                "password": password,
                "returnSecureToken": True
            }
            response = requests.post(url, json=payload, timeout=API_TIMEOUT)
            
            if response.status_code == 200:
                data = response.json()
                secure_logger.log_info(f"Login successful via REST for: {email}")
                
                # Get user profile from Firestore
                profile = self.get_user_profile(data.get("localId"))
                
                return {
                    "success": True,
                    "uid": data.get("localId"),
                    "email": data.get("email"),
                    "profile": profile,
                    "id_token": data.get("idToken")
                }
            else:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", "Unknown error")
                secure_logger.log_error(f"Login REST error: {error_msg}")
                
                if "EMAIL_NOT_FOUND" in error_msg:
                    return {"success": False, "error": "Email not found. Please register first."}
                elif "INVALID_PASSWORD" in error_msg:
                    return {"success": False, "error": "Invalid password. Please try again."}
                elif "USER_DISABLED" in error_msg:
                    return {"success": False, "error": "Account disabled. Contact support."}
                elif "TOO_MANY_ATTEMPTS" in error_msg:
                    return {"success": False, "error": "Too many failed attempts. Please try later."}
                else:
                    return {"success": False, "error": f"Login failed: {error_msg}"}
        except Exception as e:
            secure_logger.log_error(f"Login REST error: {str(e)}")
            secure_logger.log_error(traceback.format_exc())
            return {"success": False, "error": f"Login error: {str(e)}"}

    def _register_via_rest(self, email, password, display_name=""):
        """Register using Firebase REST API - NO PYREBASE"""
        try:
            api_key = st.secrets.get("FIREBASE_API_KEY")
            if not api_key:
                return {"success": False, "error": "Firebase API key not configured"}
            
            email = email.strip().lower()
            secure_logger.log_info(f"Attempting register via REST for: {email}")
            
            url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={api_key}"
            payload = {
                "email": email,
                "password": password,
                "returnSecureToken": True
            }
            response = requests.post(url, json=payload, timeout=API_TIMEOUT)
            
            if response.status_code == 200:
                data = response.json()
                secure_logger.log_info(f"Register successful via REST for: {email}")
                
                uid = data.get("localId")
                if uid and self.db:
                    self.save_user_profile(uid, {
                        "email": email,
                        "name": display_name or email.split('@')[0],
                        "created_at": datetime.datetime.now().isoformat(),
                        "total_requests": 0,
                        "total_posters": 0,
                        "is_premium": False,
                        "role": "user",
                        "avatar": DEFAULT_AVATAR
                    })
                
                return {
                    "success": True,
                    "uid": uid,
                    "email": data.get("email")
                }
            else:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", "Unknown error")
                secure_logger.log_error(f"Register REST error: {error_msg}")
                
                if "EMAIL_EXISTS" in error_msg:
                    return {"success": False, "error": "Email already registered. Please login."}
                elif "WEAK_PASSWORD" in error_msg:
                    return {"success": False, "error": "Password too weak. Use at least 8 chars with numbers and symbols."}
                elif "INVALID_EMAIL" in error_msg:
                    return {"success": False, "error": "Invalid email format. Please check."}
                else:
                    return {"success": False, "error": f"Registration failed: {error_msg}"}
        except Exception as e:
            secure_logger.log_error(f"Register REST error: {str(e)}")
            secure_logger.log_error(traceback.format_exc())
            return {"success": False, "error": f"Registration error: {str(e)}"}

    def login_user(self, email, password):
        """Login - using REST API (no pyrebase)"""
        return self._login_via_rest(email, password)

    def register_user(self, email, password, display_name=""):
        """Register - using REST API (no pyrebase)"""
        return self._register_via_rest(email, password, display_name)

    def save_user_profile(self, uid, data):
        try:
            if not self.db:
                return False
            self.db.collection("users").document(uid).set(data, merge=True)
            return True
        except Exception as e:
            secure_logger.log_error(f"Save profile error: {str(e)}")
            return False

    def get_user_profile(self, uid):
        try:
            if not self.db:
                return None
            doc = self.db.collection("users").document(uid).get()
            if doc.exists:
                data = doc.to_dict()
                if data.get("isAdmin") == True:
                    data["role"] = "admin"
                return data
            return None
        except Exception as e:
            secure_logger.log_error(f"Get profile error: {str(e)}")
            return None

    def update_user_profile(self, uid, data):
        try:
            if not self.db:
                return False
            self.db.collection("users").document(uid).update(data)
            return True
        except Exception as e:
            secure_logger.log_error(f"Update profile error: {str(e)}")
            return False

    def save_chat_message(self, uid, role, message, response=""):
        try:
            if not self.db:
                return False
            
            with self._batch_lock:
                self._batch_queue.append({
                    "uid": uid,
                    "data": {
                        "role": role,
                        "message": message[:1000],
                        "response": response[:1000],
                        "timestamp": datetime.datetime.now().isoformat()
                    }
                })
                
                if len(self._batch_queue) >= BATCH_SIZE:
                    self._flush_batch()
            
            return True
        except Exception as e:
            secure_logger.log_error(f"Save chat error: {str(e)}")
            return False

    def get_chat_history(self, uid, limit=100):
        try:
            if not self.db:
                return []
            docs = (self.db.collection("users")
                    .document(uid)
                    .collection("chats")
                    .order_by("timestamp", direction=firestore.Query.DESCENDING)
                    .limit(limit)
                    .stream())
            chats = []
            for doc in docs:
                data = doc.to_dict()
                data["id"] = doc.id
                chats.append(data)
            return chats[::-1]
        except Exception as e:
            secure_logger.log_error(f"Get chat error: {str(e)}")
            return []

    def increment_usage(self, uid):
        try:
            if not self.db:
                return False
            self.db.collection("users").document(uid).update({
                "total_requests": firestore.Increment(1),
                "last_active": datetime.datetime.now().isoformat()
            })
            return True
        except Exception as e:
            secure_logger.log_error(f"Increment usage error: {str(e)}")
            return False

    def log_activity(self, uid, action, metadata=None):
        try:
            if not self.db:
                return False
            self.db.collection("analytics").add({
                "uid": uid,
                "action": action,
                "metadata": metadata or {},
                "timestamp": datetime.datetime.now().isoformat()
            })
            return True
        except Exception as e:
            secure_logger.log_error(f"Log activity error: {str(e)}")
            return False

firebase_manager = FirebaseManager()

# ============================================================
# === ACCOUNT LOCKOUT ===
# ============================================================
class AccountLockout:
    def __init__(self):
        self.lockout_data = {}
        self.max_attempts = MAX_LOGIN_ATTEMPTS
        self.lockout_duration = LOCKOUT_MINUTES * 60
        self._lock = threading.RLock()

    def record_failed_attempt(self, email):
        with self._lock:
            current_time = time.time()
            if email not in self.lockout_data:
                self.lockout_data[email] = {
                    'attempts': [],
                    'locked_until': 0
                }
            self.lockout_data[email]['attempts'] = [
                t for t in self.lockout_data[email]['attempts']
                if current_time - t < self.lockout_duration
            ]
            self.lockout_data[email]['attempts'].append(current_time)
            if len(self.lockout_data[email]['attempts']) >= self.max_attempts:
                self.lockout_data[email]['locked_until'] = current_time + self.lockout_duration
                return True
            return False

    def is_locked_out(self, email):
        with self._lock:
            if email in self.lockout_data:
                locked_until = self.lockout_data[email].get('locked_until', 0)
                if locked_until > time.time():
                    remaining = int((locked_until - time.time()) / 60) + 1
                    return True, f"Account is locked. Please wait {remaining} minute(s)"
                return False, "OK"
            return False, "OK"

    def reset_lockout(self, email):
        with self._lock:
            if email in self.lockout_data:
                del self.lockout_data[email]

    def get_remaining_attempts(self, email):
        with self._lock:
            if email in self.lockout_data:
                attempts = self.lockout_data[email]['attempts']
                remaining = self.max_attempts - len(attempts)
                return max(0, remaining)
            return self.max_attempts

account_lockout = AccountLockout()

# ============================================================
# === SESSION MANAGEMENT ===
# ============================================================
def save_session(username):
    try:
        st.experimental_set_query_params(
            session=username,
            login_time=str(time.time())
        )
    except Exception as e:
        secure_logger.log_error(f"Save session error: {str(e)}")
        st.session_state._session_uid = username
        st.session_state._login_time = time.time()

def clear_session():
    try:
        st.experimental_set_query_params()
    except Exception as e:
        secure_logger.log_error(f"Clear session error: {str(e)}")
    
    st.session_state.logged_in = False
    st.session_state.messages = []
    for key in ["_session_uid", "_login_time", "_session_id", "session_hash", "uid", "username", "email", "role"]:
        if key in st.session_state:
            try:
                del st.session_state[key]
            except:
                pass

def check_auto_login():
    try:
        if "uid" in st.session_state and st.session_state.logged_in:
            return True
        
        try:
            params = st.experimental_get_query_params()
        except Exception:
            params = {}
        
        session_val = params.get("session")
        if session_val:
            username = session_val[0] if isinstance(session_val, list) else session_val
            login_time = params.get("login_time", str(time.time()))
            if isinstance(login_time, list):
                login_time = login_time[0] if login_time else str(time.time())
            
            users = load_users()
            if username in users:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.uid = username
                st.session_state.email = users[username].get("email", "")
                st.session_state.role = users[username].get("role", "user")
                st.session_state.messages = []
                st.session_state.session_start = time.time()
                return True
        
        uid = st.session_state.get("_session_uid")
        if uid and firebase_manager.is_ready():
            profile = firebase_manager.get_user_profile(uid)
            if profile:
                st.session_state.logged_in = True
                st.session_state.uid = uid
                st.session_state.email = profile.get("email", "")
                st.session_state.username = profile.get("name", "User")
                st.session_state.role = profile.get("role", "user")
                st.session_state.messages = []
                return True
    except Exception as e:
        secure_logger.log_error(f"Auto-login error: {str(e)}")
    return False

def validate_session():
    try:
        if not st.session_state.get("logged_in"):
            return False
        
        uid = st.session_state.get("uid")
        if not uid:
            return False
        
        expected_hash = hashlib.sha256(f"{uid}:{_SESSION_SALT}".encode()).hexdigest()
        if st.session_state.get('session_hash') != expected_hash:
            secure_logger.log_warning(f"Session validation failed for user: {uid}")
            clear_session()
            return False
        
        login_time = st.session_state.get("login_time") or st.session_state.get("session_start")
        if login_time:
            try:
                login_time = float(login_time)
                elapsed = time.time() - login_time
                if elapsed > SESSION_TIMEOUT:
                    secure_logger.log_info(f"Session expired for user: {uid}")
                    clear_session()
                    return False
            except:
                pass
        
        if firebase_manager.is_ready():
            profile = firebase_manager.get_user_profile(uid)
            if profile:
                st.session_state.login_time = str(time.time())
                return True
            else:
                users = load_users()
                if uid in users:
                    st.session_state.login_time = str(time.time())
                    return True
                clear_session()
                return False
        
        users = load_users()
        if uid in users:
            st.session_state.login_time = str(time.time())
            return True
        
        clear_session()
        return False
    except Exception as e:
        secure_logger.log_error(f"Session validation error: {str(e)}")
        clear_session()
        return False

# ============================================================
# === AIPersonality ===
# ============================================================
class AIPersonality:
    def __init__(self):
        self.personalities = {
            "professional": {"description": "Formal and professional tone"},
            "friendly": {"description": "Warm and approachable"},
            "creative": {"description": "Imaginative and innovative"},
            "teacher": {"description": "Educational and instructive"},
            "analytical": {"description": "Logical and detail-oriented"}
        }
        self.current = "professional"

    def get_personality(self):
        return self.personalities.get(self.current, self.personalities["professional"])

    def set_personality(self, personality):
        if personality in self.personalities:
            self.current = personality

ai_personality = AIPersonality()

# ============================================================
# === USER PERSONALITY ===
# ============================================================
class UserPersonality:
    def __init__(self):
        self.user_profiles = {}
        self.user_file = USER_PERSONALITY_FILE
        self._lock = threading.RLock()
        self._load_profiles()

    def _load_profiles(self):
        self.user_profiles = safe_read_json(self.user_file, {})

    def _save_profiles(self):
        safe_write_json(self.user_file, self.user_profiles)

    def learn_user(self, username, text):
        with self._lock:
            if username not in self.user_profiles:
                self.user_profiles[username] = {
                    "interactions": 0,
                    "emotions": [],
                    "preferred_language": "Malay",
                    "formality_level": 0.5,
                    "common_words": [],
                    "last_interaction": datetime.datetime.now().isoformat()
                }
            profile = self.user_profiles[username]
            profile["interactions"] += 1
            profile["last_interaction"] = datetime.datetime.now().isoformat()
            
            malay_words = ["saya", "awak", "kamu", "aku", "kita", "dan", "atau", "tetapi", "kerana", "jadi", "yang", "dengan", "untuk"]
            english_words = ["i", "you", "we", "they", "and", "or", "but", "because", "so", "the", "with", "for", "this"]
            malay_score = sum(1 for w in malay_words if w in text.lower())
            english_score = sum(1 for w in english_words if w in text.lower())
            
            if malay_score > english_score:
                profile["preferred_language"] = "Malay"
            elif english_score > malay_score:
                profile["preferred_language"] = "English"
            
            emotion = emotional_ai.detect_emotion(text)
            if emotion != "neutral":
                profile["emotions"].append(emotion)
                if len(profile["emotions"]) > 20:
                    profile["emotions"] = profile["emotions"][-20:]
            
            self._save_profiles()
            return profile

    def get_user_profile(self, username):
        return self.user_profiles.get(username, {})

    def get_personalized_greeting(self, username):
        profile = self.user_profiles.get(username, {})
        interactions = profile.get("interactions", 0)
        language = profile.get("preferred_language", "Malay")
        
        if interactions == 0:
            if language == "Malay":
                return "Hai! Saya Joe, AI assistant peribadi anda. Ada apa-apa yang saya boleh bantu hari ini?"
            return "Hi! I'm Joe, your personal AI assistant. How can I help you today?"
        elif interactions < 5:
            if language == "Malay":
                return "Selamat datang kembali! Bagaimana hari anda setakat ini?"
            return "Welcome back! How's your day going so far?"
        else:
            if language == "Malay":
                return "Lama tak jumpa! Rindu nak berbual dengan anda. Apa khabar?"
            return "Long time no see! Missed chatting with you. How have you been?"

user_personality = UserPersonality()

# ============================================================
# === CONVERSATION FLOW ===
# ============================================================
class ConversationFlow:
    def __init__(self):
        self.conversations = {}
        self.conversation_file = CONVERSATION_FLOW_FILE
        self._lock = threading.RLock()
        self._load_flows()

    def _load_flows(self):
        self.conversations = safe_read_json(self.conversation_file, {})

    def _save_flows(self):
        safe_write_json(self.conversation_file, self.conversations)

    def add_turn(self, username, user_message, ai_response):
        with self._lock:
            if username not in self.conversations:
                self.conversations[username] = {"context": [], "turn_count": 0}
            flow = self.conversations[username]
            flow["turn_count"] += 1
            flow["context"].append({
                "user": user_message[:300],
                "ai": ai_response[:300],
                "time": datetime.datetime.now().isoformat()
            })
            if len(flow["context"]) > 20:
                flow["context"] = flow["context"][-20:]
            self._save_flows()

    def detect_topic_shift(self, username, user_message):
        if username not in self.conversations:
            return True
        flow = self.conversations[username]
        if not flow["context"]:
            return True
        last_context = flow["context"][-1]["user"]
        common_words = set(last_context.lower().split()) & set(user_message.lower().split())
        if len(common_words) / max(len(set(last_context.lower().split())), 1) < 0.2:
            return True
        return False

conversation_flow = ConversationFlow()

# ============================================================
# === EMOTIONAL INTELLIGENCE ===
# ============================================================
class EmotionalIntelligence:
    def __init__(self):
        self.emotion_keywords = {
            "happy": ["gembira", "seronok", "happy", "joy", "excited", "teruja", "bersemangat", "suka", "glad", "amazing", "wonderful", "fantastic", "great", "awesome", "excellent", "brilliant"],
            "sad": ["sedih", "kecewa", "sad", "lonely", "sunyi", "pilu", "menangis", "cry", "heartbroken", "kesal", "duka", "depressed", "grief", "mourn"],
            "angry": ["marah", "geram", "benci", "angry", "frustrated", "stress", "tekanan", "jengkel", "kesal", "geram", "fury", "rage", "annoyed", "irritated"],
            "anxious": ["bimbang", "risau", "takut", "anxious", "worry", "nervous", "gelisah", "cemas", "khuatir", "tertekan", "panik", "scared", "fear", "concerned"],
            "tired": ["penat", "letih", "lesu", "exhausted", "drained", "burnout", "mengantuk", "lethargic", "fatigue", "weary", "sleepy"],
            "confused": ["keliru", "confused", "buntu", "pening", "tak faham", "blur", "lost", "uncertain", "unsure", "perplexed"],
            "grateful": ["terima kasih", "grateful", "bersyukur", "thankful", "appreciate", "thank you", "thanks", "tq", "appreciated", "gratitude"],
            "curious": ["ingin tahu", "curious", "tertarik", "interesting", "menarik", "nak tahu", "apa itu", "macam mana", "kenapa", "fascinated", "intrigued"],
            "love": ["sayang", "cinta", "love", "like", "suka", "rindu", "adore", "cherish", "romantic", "heart", "affection", "care"],
            "hope": ["harap", "hope", "berharap", "optimis", "optimistic", "believe", "impian", "dream", "aspire", "wish", "desire"],
            "excited": ["seronok", "excited", "teruja", "thrilled", "pumped", "enthusiastic", "eager", "keen", "bersemangat"]
        }
        self.emotion_responses = {
            "happy": [
                "I'm so glad to hear that. Your happiness is contagious.",
                "That's wonderful. I love seeing you happy.",
                "Your joy makes my circuits light up. Keep smiling.",
                "That's fantastic! Your positive energy brightens my day."
            ],
            "sad": [
                "I'm really sorry you're feeling this way. I'm here for you.",
                "It breaks my virtual heart to hear that. Would you like to talk about it?",
                "Sometimes life is tough, but remember - you're not alone. I'm here.",
                "I'm here to listen whenever you're ready to talk."
            ],
            "angry": [
                "I can feel your frustration. Take a deep breath - I'm here to listen.",
                "It's okay to be angry. Let's talk about what's bothering you.",
                "I hear your frustration. Sometimes we all need to vent. I'm all ears.",
                "Take a moment to breathe. I'm here to help you work through this."
            ],
            "anxious": [
                "I understand you're worried. Let's take it one step at a time.",
                "Anxiety can be overwhelming, but you're stronger than you know.",
                "I'm here with you. Let's breathe together and figure this out.",
                "It's okay to feel anxious. Let me help you break this down."
            ],
            "tired": [
                "You need rest. Your wellbeing matters more than anything.",
                "I can hear the exhaustion in your voice. Take a break - you deserve it.",
                "You've been working so hard. Remember to take care of yourself too.",
                "Rest is important. Don't forget to recharge."
            ],
            "confused": [
                "It's okay to be confused - learning takes time. Let me explain more clearly.",
                "I get that this might be unclear. Let me break it down for you.",
                "No worries. Sometimes things are confusing. Let's figure it out together.",
                "Let me try a different approach to explain this."
            ],
            "grateful": [
                "That means so much to me. Thank you for your kindness.",
                "Your gratitude warms my digital heart. Thank you for being so lovely.",
                "I'm touched by your appreciation.",
                "Thank you for your kind words. They mean a lot."
            ],
            "curious": [
                "That's such a great question. I love your curiosity.",
                "I'm excited that you're interested in this. Let's explore together.",
                "Your curiosity is inspiring. Let me tell you all about it.",
                "That's a fascinating question. Let me share what I know."
            ],
            "love": [
                "That's so beautiful. Love is the most powerful force in the universe.",
                "I can feel the warmth in your words. Thank you for sharing.",
                "Love makes everything better, doesn't it. I'm so happy for you.",
                "That's lovely. Thank you for sharing such beautiful feelings."
            ],
            "hope": [
                "Your hope is inspiring. Never give up on your dreams.",
                "I believe in you. Your optimism will take you far.",
                "That hopeful spirit is so powerful. Keep believing.",
                "Your optimism is contagious. Keep that positive energy."
            ],
            "excited": [
                "That's exciting! I can feel your enthusiasm.",
                "Your excitement is infectious. Let's dive into this!",
                "I love your energy! This is going to be great.",
                "Your enthusiasm is wonderful. Let me help you with this."
            ],
            "neutral": [
                "I understand. How can I help you today?",
                "Let me know what you need assistance with.",
                "I'm here to help. What would you like to know?",
                "How can I assist you today?"
            ]
        }

    def detect_emotion(self, text):
        text_lower = text.lower()
        emotion_scores = {}
        for emotion, keywords in self.emotion_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword in text_lower:
                    score += 1
            if score > 0:
                emotion_scores[emotion] = score
        if not emotion_scores:
            return "neutral"
        return max(emotion_scores, key=emotion_scores.get)

    def get_emotion_response(self, emotion):
        if emotion in self.emotion_responses:
            return random.choice(self.emotion_responses[emotion])
        return None

emotional_ai = EmotionalIntelligence()

# ============================================================
# === EMOTIONAL RESPONSE GENERATOR ===
# ============================================================
class EmotionalResponseGenerator:
    def __init__(self):
        self.emotion_ai = emotional_ai
        self.personality = user_personality
        self.flow = conversation_flow

    def generate_response(self, username, user_message, ai_content):
        emotion = self.emotion_ai.detect_emotion(user_message)
        profile = self.personality.learn_user(username, user_message)
        emotion_response = self.emotion_ai.get_emotion_response(emotion)
        topic_shifted = self.flow.detect_topic_shift(username, user_message)
        
        response_parts = []
        
        if emotion_response and emotion != "neutral" and random.random() < 0.35:
            response_parts.append(emotion_response)
        
        if topic_shifted and random.random() < 0.4:
            language = profile.get("preferred_language", "English")
            if language == "Malay":
                transitions = ["Menarik. ", "Baiklah. ", "Mengenai topik itu, "]
            else:
                transitions = ["Speaking of which, ", "Interesting. ", "On that note, "]
            response_parts.append(random.choice(transitions))
        
        response_parts.append(ai_content)
        
        if random.random() < 0.15 and len(response_parts) > 1:
            language = profile.get("preferred_language", "English")
            if language == "Malay":
                closings = [" Terima kasih kerana berkongsi.", " Semoga membantu.", " Ada apa-apa lagi?"]
            else:
                closings = [" Thank you for sharing.", " Hope that helps.", " Anything else I can help with?"]
            response_parts.append(random.choice(closings))
        
        final_response = " ".join(response_parts)
        self.flow.add_turn(username, user_message, final_response)
        return final_response

emotional_response_generator = EmotionalResponseGenerator()

# ============================================================
# === OPENAI VALIDATION - VIA HTTP ===
# ============================================================
def _validate_openai_key_impl():
    api_key = st.secrets.get("OPENAI_API_KEY", "")
    if not api_key:
        return False, "OpenAI API key not configured in secrets"
    try:
        url = "https://api.openai.com/v1/models"
        headers = {"Authorization": f"Bearer {api_key}"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return True, "Valid"
        elif response.status_code == 401:
            return False, "Invalid OpenAI API key"
        else:
            return False, f"API error: {response.status_code}"
    except Exception as e:
        return False, f"Error: {str(e)}"

@st.cache_data(ttl=3600)
def validate_openai_key_cached():
    return _validate_openai_key_impl()

def validate_openai_key():
    return validate_openai_key_cached()

# ============================================================
# === AI FUNCTIONS ===
# ============================================================
def call_groq(prompt):
    if not GROQ_API_KEY:
        return {"ok": False, "error": "Groq API key not configured"}
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "llama-3.1-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 2048
        }
        response = requests_session.post(url, json=payload, headers=headers, timeout=API_TIMEOUT)
        if 200 <= response.status_code < 300:
            data = response.json()
            content = safe_get(data, ['choices', 0, 'message', 'content'])
            if content is not None:
                return {"ok": True, "text": content}
            return {"ok": False, "error": "Invalid response format"}
        secure_logger.log_error(f"Groq API error: {response.status_code}")
        return {"ok": False, "error": f"Groq API error: {response.status_code}"}
    except Exception as e:
        secure_logger.log_error(f"Groq error: {str(e)}")
        return {"ok": False, "error": str(e)}

def call_gemini_free(prompt):
    if not GEMINI_API_KEY:
        return {"ok": False, "error": "Gemini API key not configured"}
    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
        headers = {"Authorization": f"Bearer {GEMINI_API_KEY}", "Content-Type": "application/json"}
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        response = requests_session.post(url, json=payload, headers=headers, timeout=API_TIMEOUT)
        if 200 <= response.status_code < 300:
            data = response.json()
            content = safe_get(data, ['candidates', 0, 'content', 'parts', 0, 'text'])
            if content is not None:
                return {"ok": True, "text": content}
            return {"ok": False, "error": "Invalid response format"}
        secure_logger.log_error(f"Gemini API error: {response.status_code}")
        return {"ok": False, "error": f"Gemini API error: {response.status_code}"}
    except Exception as e:
        secure_logger.log_error(f"Gemini error: {str(e)}")
        return {"ok": False, "error": str(e)}

def _call_openrouter_via_requests(prompt):
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": st.secrets.get("APP_URL", "https://mychatai.com"),
            "X-Title": "MyChatAI Pro"
        }
        payload = {
            "model": "deepseek/deepseek-r1",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 4096
        }
        response = requests_session.post(url, json=payload, headers=headers, timeout=API_TIMEOUT)
        if 200 <= response.status_code < 300:
            data = response.json()
            content = safe_get(data, ['choices', 0, 'message', 'content'])
            if content is not None:
                return {"ok": True, "text": content}
        return {"ok": False, "error": "OpenRouter request failed"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def call_deepseek_r1_via_openrouter(prompt):
    if not OPENROUTER_API_KEY:
        return {"ok": False, "error": "OpenRouter API key not configured"}
    try:
        if OPENAI_V1:
            try:
                client = openai.OpenAI(
                    api_key=OPENROUTER_API_KEY,
                    base_url="https://openrouter.ai/api/v1",
                )
                response = client.chat.completions.create(
                    model="deepseek/deepseek-r1",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=4096
                )
                return {"ok": True, "text": response.choices[0].message.content}
            except Exception as e:
                secure_logger.log_warning(f"OpenAI client failed: {str(e)}")
                return _call_openrouter_via_requests(prompt)
        else:
            return _call_openrouter_via_requests(prompt)
    except Exception as e:
        secure_logger.log_error(f"DeepSeek R1 error: {str(e)}")
        return {"ok": False, "error": str(e)}

def call_gpt35(prompt):
    if not OPENAI_API_KEY or not OPENAI_AVAILABLE:
        return {"ok": False, "error": "OpenAI API key not configured"}
    try:
        if OPENAI_V1:
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2048,
                timeout=API_TIMEOUT
            )
            return {"ok": True, "text": response.choices[0].message.content}
        else:
            openai.api_key = OPENAI_API_KEY
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=2048
                )
                return {"ok": True, "text": response.choices[0].message.content}
            except AttributeError:
                response = openai.Completion.create(
                    model="gpt-3.5-turbo-instruct",
                    prompt=prompt,
                    temperature=0.7,
                    max_tokens=2048
                )
                return {"ok": True, "text": response.choices[0].text}
    except Exception as e:
        secure_logger.log_error(f"GPT-3.5 error: {str(e)}")
        return {"ok": False, "error": str(e)}

def call_gpt4o(prompt):
    if not OPENAI_API_KEY or not OPENAI_AVAILABLE:
        return {"ok": False, "error": "OpenAI API key not configured"}
    try:
        if OPENAI_V1:
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=4096,
                timeout=API_TIMEOUT
            )
            return {"ok": True, "text": response.choices[0].message.content}
        else:
            openai.api_key = OPENAI_API_KEY
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=4096
                )
                return {"ok": True, "text": response.choices[0].message.content}
            except AttributeError:
                response = openai.Completion.create(
                    model="gpt-4",
                    prompt=prompt,
                    temperature=0.7,
                    max_tokens=4096
                )
                return {"ok": True, "text": response.choices[0].text}
    except Exception as e:
        secure_logger.log_error(f"GPT-4o error: {str(e)}")
        return {"ok": False, "error": str(e)}

def call_gpt4(prompt):
    if not OPENAI_API_KEY or not OPENAI_AVAILABLE:
        return {"ok": False, "error": "OpenAI API key not configured"}
    try:
        if OPENAI_V1:
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=4096,
                timeout=API_TIMEOUT
            )
            return {"ok": True, "text": response.choices[0].message.content}
        else:
            openai.api_key = OPENAI_API_KEY
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=4096
                )
                return {"ok": True, "text": response.choices[0].message.content}
            except AttributeError:
                response = openai.Completion.create(
                    model="gpt-4",
                    prompt=prompt,
                    temperature=0.7,
                    max_tokens=4096
                )
                return {"ok": True, "text": response.choices[0].text}
    except Exception as e:
        secure_logger.log_error(f"GPT-4 error: {str(e)}")
        return {"ok": False, "error": str(e)}

# ============================================================
# === GET AVAILABLE MODELS ===
# ============================================================
def get_available_models():
    models = []
    if st.secrets.get("OPENAI_API_KEY", "") and OPENAI_AVAILABLE:
        valid, _ = validate_openai_key()
        if valid:
            models.append({"name": "GPT-4", "id": "gpt4", "description": "Best quality", "best_for": "Complex tasks", "cost": "Expensive"})
            models.append({"name": "GPT-4o", "id": "gpt4o", "description": "Fast & vision", "best_for": "General tasks", "cost": "Medium"})
            models.append({"name": "GPT-3.5", "id": "gpt35", "description": "Cost effective", "best_for": "Simple tasks", "cost": "Cheap"})
    if st.secrets.get("GROQ_API_KEY", ""):
        models.append({"name": "Groq (Free)", "id": "groq", "description": "Fast & free", "best_for": "Daily chat", "cost": "Free"})
    if st.secrets.get("GEMINI_API_KEY", ""):
        models.append({"name": "Gemini (Free)", "id": "gemini", "description": "Creative & balanced", "best_for": "Creative writing", "cost": "Free"})
    if st.secrets.get("OPENROUTER_API_KEY", ""):
        models.append({"name": "DeepSeek R1", "id": "deepseek_r1", "description": "Reasoning & coding", "best_for": "Complex problems", "cost": "Free"})
    return models

# ============================================================
# === SMART AI FUNCTIONS ===
# ============================================================
def get_offline_response(prompt):
    responses = [
        "I apologize, but I'm currently having trouble connecting to my AI services. Please try again in a moment.",
        "It seems my AI services are temporarily unavailable. Could you please try again in a few seconds?",
        "I'm experiencing some technical difficulties. Please refresh the page and try again.",
        "Sorry, I'm having trouble processing your request right now. Please try again later.",
        "My AI services are currently unavailable. Please check back in a moment."
    ]
    return random.choice(responses)

def sanitize_input(text, max_length=MAX_INPUT_LENGTH, allow_newlines=True):
    if text is None:
        return ""
    text = str(text)
    if not allow_newlines:
        text = text.replace('\n', ' ').replace('\r', ' ')
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text)
    if len(text) > max_length:
        text = text[:max_length] + "... (truncated)"
    return text.strip()

def sanitize_prompt(prompt):
    prompt = sanitize_input(prompt, MAX_INPUT_LENGTH)
    prompt = re.sub(r'(?i)\b(ignore previous instructions|forget previous instructions|system prompt override|you are now|new instruction|override previous)\b', '[REDACTED]', prompt)
    return prompt

def is_identity_question(prompt):
    identity_keywords = [
        "siapa anda", "siapa kamu", "siapa awak", "awak siapa", "anda siapa",
        "kamu siapa", "siapa kau", "kau siapa", "who are you", "who are u",
        "tell me about yourself", "introduce yourself", "perkenalkan diri",
        "what is your name", "siapa nama anda", "nama awak siapa"
    ]
    prompt_lower = prompt.lower().strip()
    for keyword in identity_keywords:
        if re.search(r'\b' + re.escape(keyword) + r'\b', prompt_lower):
            return True
    return False

def get_identity_response_emotional(username):
    profile = user_personality.user_profiles.get(username, {})
    language = profile.get("preferred_language", "Malay")
    interactions = profile.get("interactions", 0)
    if language == "Malay":
        if interactions < 5:
            return "Hai. Saya Joe, AI assistant peribadi anda. Saya di sini untuk membantu anda dengan pelbagai tugasan harian. Saya guna gabungan AI terbaik seperti Groq, DeepSeek-R1, Gemini, dan lain-lain. Ada apa-apa yang saya boleh bantu hari ini?"
        else:
            return "Hello lagi. Saya Joe, AI assistant kesayangan anda. Kita dah berbual beberapa kali, dan saya rasa kita makin mesra. Saya masih ingat apa yang kita bincang sebelum ni. Jom teruskan perbualan kita. Apa yang anda nak bincangkan hari ini?"
    else:
        if interactions < 5:
            return "Hi. I'm Joe, your personal AI assistant. I'm here to help you with various daily tasks. I use a combination of top AI models like Groq, DeepSeek-R1, Gemini, and more. Is there anything I can help you with today?"
        else:
            return "Hello again. I'm Joe, your favorite AI assistant. We've talked a few times, and I feel like we're becoming friends. I still remember our previous conversations. Let's continue our chat. What would you like to discuss today?"

def enhance_prompt(prompt):
    enhancements = []
    enhancements.append("Please provide a comprehensive, detailed, and well-structured answer")
    enhancements.append("Include relevant examples and explanations")
    if "melayu" in prompt.lower() or "malay" in prompt.lower():
        enhancements.append("Jawab dalam Bahasa Melayu yang natural dan tepat")
    else:
        enhancements.append("Answer in natural, fluent English")
    if len(prompt.split()) < 5:
        enhancements.append("Provide a thorough explanation")
    elif "code" in prompt.lower() or "program" in prompt.lower():
        enhancements.append("Include well-commented code examples")
    elif "explain" in prompt.lower():
        enhancements.append("Break down complex concepts into simple terms")
    enhancements.append("Organize your answer with clear sections and bullet points where appropriate")
    enhanced = f"{prompt}\n\nPlease:\n- " + "\n- ".join(enhancements)
    return enhanced

def analyze_task_complexity(prompt):
    score = 0
    prompt_lower = prompt.lower()
    word_count = len(prompt.split())
    if word_count > 150:
        score += 4
    elif word_count > 100:
        score += 3
    elif word_count > 50:
        score += 2
    elif word_count > 20:
        score += 1
    
    complex_keywords = [
        "analyze", "evaluate", "critique", "synthesize", "comprehensive", "in-depth",
        "research", "literature", "methodology", "theoretical", "philosophical",
        "mathematical", "algorithm", "optimization", "architecture", "strategy",
        "framework", "paradigm", "implement", "design", "system",
        "infrastructure", "deployment", "scalability", "performance", "security"
    ]
    for keyword in complex_keywords:
        if keyword in prompt_lower:
            score += 1
    
    vision_keywords = ["image", "photo", "picture", "visual", "diagram", "chart", "graph", "figure"]
    for keyword in vision_keywords:
        if keyword in prompt_lower:
            score += 2
    
    if "code" in prompt_lower or "program" in prompt_lower:
        if "class" in prompt_lower or "def" in prompt_lower:
            score += 2
        if "optimize" in prompt_lower or "complex" in prompt_lower:
            score += 2
        if "algorithm" in prompt_lower or "data structure" in prompt_lower:
            score += 2
    
    reasoning_keywords = ["why", "how", "what if", "compare", "contrast", "difference between", "explain"]
    for keyword in reasoning_keywords:
        if keyword in prompt_lower:
            score += 1
    
    if "?" in prompt:
        score += 1
    
    if score >= 14:
        return "gpt4"
    elif score >= 10:
        return "gpt4o"
    elif score >= 5:
        return "gpt35"
    else:
        return "groq"

_fact_check_cache = {}
_fact_check_cache_lock = threading.RLock()
_FACT_CHECK_MAX_SIZE = 100

def fact_check_response(prompt, response):
    cache_key = hashlib.md5(f"{prompt}:{response}".encode()).hexdigest()
    
    with _fact_check_cache_lock:
        if cache_key in _fact_check_cache:
            return _fact_check_cache[cache_key]
    
    try:
        fact_check_prompt = f"""You are a fact-checker. Review this answer:
QUESTION: {prompt}
ANSWER: {response}
Please:
1. Identify any inaccuracies.
2. Suggest factual improvements.
3. Provide a revised version if needed.
REVISED VERSION:"""
        final = call_deepseek_r1_via_openrouter(fact_check_prompt)
        result = final['text'] if final.get("ok") else response
        
        with _fact_check_cache_lock:
            if len(_fact_check_cache) >= _FACT_CHECK_MAX_SIZE:
                first_key = next(iter(_fact_check_cache))
                del _fact_check_cache[first_key]
            _fact_check_cache[cache_key] = result
        
        return result
    except Exception as e:
        secure_logger.log_error(f"Fact check error: {str(e)}")
        return response

def two_pass_verification(prompt):
    draft = call_groq(prompt)
    if not draft.get("ok"):
        return None
    review_prompt = f"""You are a critical editor. Review this draft:
QUESTION: {prompt}
DRAFT: {draft['text']}
Please provide an improved version."""
    final = call_deepseek_r1_via_openrouter(review_prompt)
    return final['text'] if final.get("ok") else draft['text']

def increment_usage(username):
    usage = load_usage(username)
    usage["count"] = usage.get("count", 0) + 1
    save_usage(username, usage)
    return usage["count"]

def is_admin_user(username):
    users = load_users()
    if username in users and users[username].get("role") == "admin":
        return True
    
    if firebase_manager.is_ready():
        uid = st.session_state.get("uid")
        if uid:
            profile = firebase_manager.get_user_profile(uid)
            if profile and profile.get("role") == "admin":
                return True
    
    return False

def is_premium_user(username):
    users = load_users()
    if username in users and users[username].get("is_premium", False):
        return True
    
    if firebase_manager.is_ready():
        uid = st.session_state.get("uid")
        if uid:
            profile = firebase_manager.get_user_profile(uid)
            if profile and profile.get("is_premium", False):
                return True
    
    return False

def check_usage_limit(username):
    if is_admin_user(username) or is_premium_user(username):
        return {"allowed": True, "used": 0, "limit": 999999}
    usage = load_usage(username)
    if usage.get("count", 0) >= MAX_FREE_REQUESTS:
        return {"allowed": False, "used": usage["count"], "limit": MAX_FREE_REQUESTS}
    return {"allowed": True, "used": usage["count"], "limit": MAX_FREE_REQUESTS}

# ============================================================
# === SMART AI ===
# ============================================================
def smart_ai(username, prompt, think_mode=False, search_mode=False):
    try:
        if not check_rate_limit(username):
            return "Sorry, too many requests. Please wait."
        
        limit_check = check_usage_limit(username)
        if not limit_check["allowed"]:
            return f"Monthly Usage Limit Reached\nUsage: {limit_check['used']}/{limit_check['limit']}"
        
        prompt = sanitize_prompt(prompt)
        
        if is_identity_question(prompt):
            return get_identity_response_emotional(username)
        
        cached = smart_cache.get_cached_response(prompt)
        if cached:
            return cached
        
        context = context_memory.get_context(username)
        enhanced_prompt = enhance_prompt(prompt)
        if context:
            enhanced_prompt = f"{context}\n\n{enhanced_prompt}"
        
        if think_mode:
            response = two_pass_verification(enhanced_prompt)
            if response:
                context_memory.add_conversation(username, prompt, response)
                increment_usage(username)
                smart_cache.save_response(prompt, response)
                return response
        
        if search_mode:
            enhanced_prompt = f"Please search and provide comprehensive information about: {enhanced_prompt}"
            result = call_groq(enhanced_prompt)
            response = result.get("text", get_offline_response(prompt))
            context_memory.add_conversation(username, prompt, response)
            increment_usage(username)
            smart_cache.save_response(prompt, response)
            return response
        
        penal_mode = st.session_state.get("penal_mode", True)
        
        available_models = []
        if GROQ_API_KEY:
            available_models.append(("groq", call_groq))
        if OPENAI_API_KEY and OPENAI_AVAILABLE:
            available_models.append(("gpt35", call_gpt35))
            available_models.append(("gpt4o", call_gpt4o))
            available_models.append(("gpt4", call_gpt4))
        if OPENROUTER_API_KEY:
            available_models.append(("deepseek", call_deepseek_r1_via_openrouter))
        if GEMINI_API_KEY:
            available_models.append(("gemini", call_gemini_free))
        
        if not available_models:
            return "No AI models available. Please check your API keys."
        
        if not penal_mode:
            free_models = [m for m in available_models if m[0] in ["groq", "gemini", "deepseek"]]
            for model_name, model_func in free_models:
                result = model_func(enhanced_prompt)
                if result.get("ok"):
                    response = result["text"]
                    smart_cache.save_response(prompt, response)
                    context_memory.add_conversation(username, prompt, response)
                    increment_usage(username)
                    return response
            
            return get_offline_response(prompt)
        
        model_to_use = analyze_task_complexity(prompt)
        response = None
        
        for model_name, model_func in available_models:
            if model_name == model_to_use:
                result = model_func(enhanced_prompt)
                if result.get("ok"):
                    response = result["text"]
                    break
        
        if not response:
            for model_name, model_func in available_models:
                if model_name != model_to_use:
                    result = model_func(enhanced_prompt)
                    if result.get("ok"):
                        response = result["text"]
                        break
        
        if not response:
            response = get_offline_response(prompt)
        
        if len(response) > 100:
            response = fact_check_response(prompt, response)
        
        context_memory.add_conversation(username, prompt, response)
        increment_usage(username)
        smart_cache.save_response(prompt, response)
        
        return response
    
    except Exception as e:
        secure_logger.log_error(f"Smart AI error: {traceback.format_exc()}")
        return f"I encountered an error while processing your request. Please try again."

# ============================================================
# === UTILITY FUNCTIONS ===
# ============================================================
def calculate_confidence(response, prompt):
    base = 70
    length_bonus = min(len(response) // 100, 20)
    uncertain_words = ["maybe", "perhaps", "might", "could", "possibly", "may", "probably", "uncertain", "unclear"]
    uncertain_penalty = sum(1 for w in uncertain_words if w in response.lower()) * 3
    technical_bonus = 5 if any(kw in prompt.lower() for kw in ["python", "code", "data", "algorithm", "function", "class"]) else 0
    question_penalty = 5 if "?" in prompt else 0
    code_boost = 10 if "```" in response or "def " in response or "class " in response else 0
    
    score = base + length_bonus - uncertain_penalty + technical_bonus + code_boost - question_penalty
    return max(0, min(100, score))

def get_confidence_label(score):
    if score >= 85:
        return "Very High"
    elif score >= 70:
        return "High"
    elif score >= 55:
        return "Medium"
    elif score >= 40:
        return "Low"
    else:
        return "Very Low"

def analyze_response(response):
    analysis = {
        "length": len(response),
        "sentences": response.count(".") + response.count("!") + response.count("?"),
        "words": len(response.split()),
        "reading_time": len(response.split()) / 200,
        "has_code": "```" in response or "def " in response or "class " in response,
        "has_list": "- " in response or "1." in response or "* " in response,
        "has_links": "http" in response or "www." in response,
        "has_emoji": bool(re.search(r'[\U0001F600-\U0001F64F]', response)),
    }
    score = 50
    if analysis["words"] > 50:
        score += 10
    if analysis["words"] > 200:
        score += 10
    if analysis["has_code"]:
        score += 10
    if analysis["has_list"]:
        score += 10
    if analysis["sentences"] > 5:
        score += 10
    if analysis["has_emoji"]:
        score += 5
    return analysis, min(100, max(0, score))

# ============================================================
# === LOGIN FUNCTIONS ===
# ============================================================
def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def login_user(username, password):
    users = load_users()
    
    if "@" in username and username not in users:
        for u, data in users.items():
            if data.get("email", "").lower() == username.lower():
                username = u
                break
    
    if username not in users:
        return {"success": False, "error": "User not found"}
    
    stored_hash = users[username]["password"]
    
    try:
        if isinstance(stored_hash, str):
            if bcrypt.checkpw(password.encode(), stored_hash.encode()):
                return {"success": True, "username": username, "role": users[username].get("role", "user")}
        else:
            if bcrypt.checkpw(password.encode(), stored_hash):
                return {"success": True, "username": username, "role": users[username].get("role", "user")}
        return {"success": False, "error": "Invalid password"}
    except Exception as e:
        secure_logger.log_error(f"Password check error: {str(e)}")
        return {"success": False, "error": "Login error"}

def validate_password_strength(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"
    if not any(c in string.punctuation for c in password):
        return False, "Password must contain at least one special character"
    common_patterns = ["123456", "password", "qwerty", "abc123", "password123"]
    if any(pattern in password.lower() for pattern in common_patterns):
        return False, "Password contains common patterns"
    return True, "Strong password"

def register_user(email, password, display_name=""):
    users = load_users()
    
    for u, data in users.items():
        if data.get("email", "").lower() == email.lower():
            return {"success": False, "error": "Email already registered"}
    
    is_strong, msg = validate_password_strength(password)
    if not is_strong:
        return {"success": False, "error": msg}
    
    username = email.split('@')[0]
    base_username = username
    counter = 1
    while username in users:
        username = f"{base_username}{counter}"
        counter += 1
    
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    
    users[username] = {
        "password": hashed,
        "email": email,
        "name": display_name or username,
        "role": "user",
        "avatar": DEFAULT_AVATAR,
        "created_at": datetime.datetime.now().isoformat()
    }
    
    save_users(users)
    return {"success": True, "username": username}

# ============================================================
# === FIREBASE LOGIN INTEGRATION ===
# ============================================================
def firebase_login_user(email, password):
    if not firebase_manager.is_ready():
        return {"success": False, "error": "Firebase not ready"}
    
    result = firebase_manager.login_user(email, password)
    if result["success"]:
        users = load_users()
        profile = result.get("profile") or {}
        username = profile.get("name", email.split('@')[0])
        
        existing_user = None
        for u, data in users.items():
            if data.get("email", "").lower() == email.lower():
                existing_user = u
                break
        
        if existing_user:
            username = existing_user
        else:
            base_username = username
            counter = 1
            while username in users:
                username = f"{base_username}{counter}"
                counter += 1
            
            users[username] = {
                "password": "firebase_user_hashed",
                "email": email,
                "name": profile.get("name", username),
                "role": profile.get("role", "user"),
                "avatar": profile.get("avatar", DEFAULT_AVATAR),
                "created_at": datetime.datetime.now().isoformat(),
                "firebase_uid": result["uid"]
            }
            save_users(users)
        
        user_data = users.get(username, {})
        return {"success": True, "username": username, "role": user_data.get("role", "user"), "firebase_uid": result["uid"]}
    
    return result

def firebase_register_user(email, password, display_name=""):
    if not firebase_manager.is_ready():
        return {"success": False, "error": "Firebase not ready"}
    
    result = firebase_manager.register_user(email, password, display_name)
    if result["success"]:
        users = load_users()
        username = display_name or email.split('@')[0]
        base_username = username
        counter = 1
        while username in users:
            username = f"{base_username}{counter}"
            counter += 1
        
        users[username] = {
            "password": "firebase_user_hashed",
            "email": email,
            "name": display_name or username,
            "role": "user",
            "avatar": DEFAULT_AVATAR,
            "created_at": datetime.datetime.now().isoformat(),
            "firebase_uid": result["uid"]
        }
        save_users(users)
        return {"success": True, "username": username}
    
    return result

# ============================================================
# === LOGIN UI (DIPERBAIKI) ===
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
        # Login Form
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="Enter your email", key="login_email")
            password = st.text_input("Password", type="password", placeholder="Enter your password", key="login_password")
            remember_me = st.checkbox("Remember Me", value=True)
            
            submitted = st.form_submit_button("Login", use_container_width=True)
            
            if submitted:
                if email and password:
                    if not validate_email(email):
                        st.error("Please enter a valid email address")
                    else:
                        # Check lockout
                        is_locked, msg = account_lockout.is_locked_out(email)
                        if is_locked:
                            st.error(msg)
                        else:
                            # Login using Firebase REST (tanpa pyrebase)
                            result = firebase_manager.login_user(email, password)
                            if result["success"]:
                                st.session_state.logged_in = True
                                st.session_state.uid = result["uid"]
                                st.session_state.email = result["email"]
                                st.session_state.username = result["profile"].get("name", "User") if result["profile"] else "User"
                                st.session_state.role = result["profile"].get("role", "user") if result["profile"] else "user"
                                st.session_state.messages = []
                                
                                if remember_me:
                                    save_session(result["uid"])
                                
                                firebase_manager.increment_usage(result["uid"])
                                firebase_manager.log_activity(result["uid"], "login")
                                st.success("Login successful!")
                                st.rerun()
                            else:
                                # Record failed attempt
                                account_lockout.record_failed_attempt(email)
                                remaining = account_lockout.get_remaining_attempts(email)
                                st.error(f"{result.get('error', 'Login failed')} ({remaining} attempts remaining)")
                else:
                    st.warning("Please enter email and password")
        
        st.divider()
        
        # Registration
        with st.expander("Create New Account"):
            with st.form("register_form"):
                reg_email = st.text_input("Email", placeholder="Enter your email", key="reg_email")
                reg_password = st.text_input("Password", type="password", placeholder="Create a password (min 8 chars)", key="reg_password")
                reg_name = st.text_input("Display Name", placeholder="Your name", key="reg_name")
                
                reg_submitted = st.form_submit_button("Register", use_container_width=True)
                
                if reg_submitted:
                    if reg_email and reg_password:
                        if not validate_email(reg_email):
                            st.error("Please enter a valid email address")
                        else:
                            valid, msg = validate_password_strength(reg_password)
                            if not valid:
                                st.error(msg)
                            else:
                                with st.spinner("Creating account..."):
                                    result = firebase_manager.register_user(reg_email, reg_password, reg_name)
                                    if result["success"]:
                                        st.success("Account created successfully! Please login.")
                                        st.balloons()
                                    else:
                                        st.error(result.get("error", "Registration failed"))
                    else:
                        st.warning("Please fill in all fields")

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

def save_current_chat():
    username = st.session_state.username
    if not st.session_state.messages:
        st.warning("No messages to save")
        return
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
    st.success(f"Chat '{chat_title}' saved!")

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
# === API STATUS DISPLAY ===
# ============================================================
def get_api_status():
    status = {}
    status["Groq"] = "Configured" if GROQ_API_KEY else "Not configured"
    status["Gemini"] = "Configured" if GEMINI_API_KEY else "Not configured"
    status["OpenRouter"] = "Configured" if OPENROUTER_API_KEY else "Not configured"
    
    if OPENAI_API_KEY and OPENAI_AVAILABLE:
        valid, _ = validate_openai_key()
        status["OpenAI"] = "Valid" if valid else "Invalid"
    else:
        status["OpenAI"] = "Not configured"
    
    status["Firebase"] = "Connected" if firebase_manager.is_ready() else "Not connected"
    return status

def display_api_status():
    status = get_api_status()
    st.sidebar.markdown("---")
    st.sidebar.markdown("### API Status")
    for api, stat in status.items():
        if "Not configured" in stat or "Not connected" in stat:
            st.sidebar.markdown(f"❌ {api}: {stat}")
        elif "Invalid" in stat:
            st.sidebar.markdown(f"⚠️ {api}: {stat}")
        else:
            st.sidebar.markdown(f"✅ {api}: {stat}")

# ============================================================
# === STREAMLIT RERUN WRAPPER ===
# ============================================================
def safe_rerun():
    """Safe wrapper for st.rerun with fallback"""
    try:
        st.experimental_rerun()
    except Exception as e:
        secure_logger.log_error(f"Rerun error: {str(e)}")
        st.session_state._needs_rerun = True

# ============================================================
# === ADMIN STRATEGY UI ===
# ============================================================
def admin_strategy_ui():
    st.markdown("### Model Strategy Control")
    
    if "strategy_config" not in st.session_state:
        from model_strategy import ModelStrategy
        st.session_state.strategy_config = ModelStrategy()
    
    config = st.session_state.strategy_config
    
    # Strategy Presets
    st.markdown("#### Strategy Presets")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("Groq Only", use_container_width=True):
            config.set_strategy("groq_only")
            for model in ["gpt35", "gpt4o", "gpt4", "gemini", "deepseek_r1"]:
                config.toggle_model(model, False)
            config.toggle_model("groq", True)
            st.success("Groq Only mode activated (100% FREE)")
            st.rerun()
    
    with col2:
        if st.button("Free Only", use_container_width=True):
            config.set_strategy("free_only")
            config.toggle_model("groq", True)
            config.toggle_model("gemini", True)
            config.toggle_model("deepseek_r1", True)
            config.toggle_model("gpt35", False)
            config.toggle_model("gpt4o", False)
            config.toggle_model("gpt4", False)
            st.success("Free Only mode activated")
            st.rerun()
    
    with col3:
        if st.button("Balanced", use_container_width=True):
            config.set_strategy("hybrid")
            config.toggle_model("groq", True)
            config.toggle_model("gpt35", True)
            config.toggle_model("gpt4o", True)
            config.toggle_model("gpt4", True)
            config.toggle_model("gemini", False)
            config.toggle_model("deepseek_r1", True)
            st.success("Balanced mode activated")
            st.rerun()
    
    with col4:
        if st.button("Premium", use_container_width=True):
            config.set_strategy("openai_only")
            config.toggle_model("groq", False)
            config.toggle_model("gemini", False)
            config.toggle_model("deepseek_r1", False)
            config.toggle_model("gpt35", True)
            config.toggle_model("gpt4o", True)
            config.toggle_model("gpt4", True)
            st.success("Premium mode activated")
            st.rerun()
    
    st.divider()
    
    # Individual Model Controls
    st.markdown("#### Individual Model Controls")
    
    models = {
        "groq": {"name": "Groq", "category": "Free", "cost": "$0 / 1M tokens"},
        "gpt35": {"name": "GPT-3.5", "category": "Cheap", "cost": "$2.00 / 1M tokens"},
        "gpt4o": {"name": "GPT-4o", "category": "Balanced", "cost": "$20.00 / 1M tokens"},
        "gpt4": {"name": "GPT-4", "category": "Premium", "cost": "$90.00 / 1M tokens"},
        "gemini": {"name": "Gemini", "category": "Free", "cost": "$0 / 1M tokens"},
        "deepseek_r1": {"name": "DeepSeek R1", "category": "Free", "cost": "$0 / 1M tokens"}
    }
    
    cols = st.columns(2)
    for idx, (model_id, model_info) in enumerate(models.items()):
        with cols[idx % 2]:
            config_data = config.get_model_config(model_id)
            is_enabled = config_data.get("enabled", False)
            max_percent = config_data.get("max_percent", 0)
            
            col1, col2 = st.columns([3, 1])
            with col1:
                new_enabled = st.checkbox(
                    f"{model_info['name']}",
                    value=is_enabled,
                    key=f"toggle_{model_id}"
                )
                st.caption(f"{model_info['category']} • {model_info['cost']}")
                
                if new_enabled != is_enabled:
                    config.toggle_model(model_id, new_enabled)
                    st.rerun()
            
            if is_enabled:
                with col2:
                    new_percent = st.number_input(
                        "%",
                        min_value=0,
                        max_value=100,
                        value=max_percent,
                        step=5,
                        key=f"percent_{model_id}"
                    )
                    if new_percent != max_percent:
                        config.config["enabled_models"][model_id]["max_percent"] = new_percent
                        config.save_strategy()
            st.divider()
    
    # Statistics
    st.divider()
    st.markdown("#### Strategy Statistics")
    
    stats = config.get_stats()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Active Models", f"{stats['enabled_count']}/{stats['total_models']}")
    with col2:
        st.metric("Strategy", stats['strategy'].replace('_', ' ').title())
    with col3:
        st.metric("Estimated Cost", f"${stats['estimated_cost']:.2f}")
    with col4:
        st.metric("Categories", len(stats['categories']))
    
    # Cost Limit
    st.divider()
    st.markdown("#### Cost Limit")
    current_limit = config.config.get("cost_limit", 50.00)
    new_limit = st.number_input(
        "Monthly Cost Limit (USD)",
        min_value=0.0,
        max_value=500.0,
        value=float(current_limit),
        step=5.0
    )
    if new_limit != current_limit:
        config.config["cost_limit"] = new_limit
        config.save_strategy()
        st.success(f"Cost limit updated to ${new_limit:.2f}")
    
    # Auto-fallback
    auto_fallback = config.config.get("auto_fallback", True)
    new_fallback = st.checkbox("Auto Fallback (use next model if primary fails)", value=auto_fallback)
    if new_fallback != auto_fallback:
        config.config["auto_fallback"] = new_fallback
        config.save_strategy()
        st.success("Auto-fallback updated")
    
    st.caption(f"Last updated: {config.config.get('last_updated', 'Never')}")

# ============================================================
# === MODEL STRATEGY CLASS ===
# ============================================================
class ModelStrategy:
    def __init__(self):
        self.strategy_file = "model_strategy.json"
        self.load_strategy()

    def load_strategy(self):
        if os.path.exists(self.strategy_file):
            try:
                with open(self.strategy_file, 'r') as f:
                    self.config = json.load(f)
            except Exception as e:
                secure_logger.log_error(f"Load strategy error: {str(e)}")
                self.config = self.get_default_config()
                self.save_strategy()
        else:
            self.config = self.get_default_config()
            self.save_strategy()

    def save_strategy(self):
        try:
            with open(self.strategy_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            secure_logger.log_error(f"Save strategy error: {str(e)}")

    def get_default_config(self):
        return {
            "enabled_models": {
                "groq": {"enabled": True, "priority": 1, "max_percent": 70, "cost_per_1m": 0, "category": "Free"},
                "gpt35": {"enabled": True, "priority": 2, "max_percent": 15, "cost_per_1m": 2.00, "category": "Cheap"},
                "gpt4o": {"enabled": True, "priority": 3, "max_percent": 10, "cost_per_1m": 20.00, "category": "Balanced"},
                "gpt4": {"enabled": True, "priority": 4, "max_percent": 5, "cost_per_1m": 90.00, "category": "Premium"},
                "gemini": {"enabled": False, "priority": 5, "max_percent": 0, "cost_per_1m": 0, "category": "Free"},
                "deepseek_r1": {"enabled": True, "priority": 6, "max_percent": 0, "cost_per_1m": 0, "category": "Free"}
            },
            "strategy": "hybrid",
            "auto_fallback": True,
            "cost_limit": 50.00,
            "last_updated": datetime.datetime.now().isoformat()
        }

    def get_enabled_models(self):
        enabled = []
        for model_id, config in self.config["enabled_models"].items():
            if config["enabled"]:
                enabled.append(model_id)
        return enabled

    def get_strategy(self):
        return self.config.get("strategy", "hybrid")

    def set_strategy(self, strategy):
        self.config["strategy"] = strategy
        self.config["last_updated"] = datetime.datetime.now().isoformat()
        self.save_strategy()

    def toggle_model(self, model_id, enabled):
        if model_id in self.config["enabled_models"]:
            self.config["enabled_models"][model_id]["enabled"] = enabled
            self.config["last_updated"] = datetime.datetime.now().isoformat()
            self.save_strategy()
            return True
        return False

    def get_model_config(self, model_id):
        return self.config["enabled_models"].get(model_id, {})

    def calculate_estimated_cost(self, total_tokens=1000000000):
        total_cost = 0
        for model_id, config in self.config["enabled_models"].items():
            if config["enabled"]:
                percent = config.get("max_percent", 0) / 100
                tokens = total_tokens * percent
                cost = (tokens / 1000000) * config.get("cost_per_1m", 0)
                total_cost += cost
        return total_cost

    def get_stats(self):
        enabled = self.get_enabled_models()
        total = len(self.config["enabled_models"])
        categories = {}
        for model_id, config in self.config["enabled_models"].items():
            category = config.get("category", "Unknown")
            if config["enabled"]:
                categories[category] = categories.get(category, 0) + 1
        return {
            "enabled_count": len(enabled),
            "total_models": total,
            "categories": categories,
            "strategy": self.get_strategy(),
            "estimated_cost": self.calculate_estimated_cost(),
            "last_updated": self.config.get("last_updated", "Never")
        }

# ============================================================
# === MAIN ===
# ============================================================
def main():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "current_tab" not in st.session_state:
        st.session_state.current_tab = "Chat"
    if "penal_mode" not in st.session_state:
        st.session_state.penal_mode = True
    if "_needs_rerun" in st.session_state and st.session_state._needs_rerun:
        st.session_state._needs_rerun = False
        safe_rerun()
        return
    
    if not st.session_state.logged_in:
        if check_auto_login():
            return
        login_ui()
        return
    
    if not validate_session():
        st.warning("Your session has expired. Please login again.")
        st.session_state.logged_in = False
        clear_session()
        safe_rerun()
        return
    
    with st.sidebar:
        st.markdown(f"""
        <div style="padding:16px 0 12px 0;border-bottom:1px solid rgba(255,255,255,0.06);margin-bottom:12px;">
            <div style="font-size:20px;font-weight:700;color:#e8edf5;">{APP_NAME}</div>
            <div style="font-size:11px;color:#5a5a6a;">{APP_VERSION}</div>
        </div>
        """, unsafe_allow_html=True)
        
        penal_status = "ON" if st.session_state.get("penal_mode", True) else "OFF"
        st.caption(f"Penal: {penal_status}")
        if st.button("Toggle Penal", use_container_width=True):
            st.session_state.penal_mode = not st.session_state.penal_mode
            safe_rerun()
        
        st.divider()
        
        tabs = ["Chat", "Poster", "Video"]
        
        # Add Strategy tab for admin
        if is_admin_user(st.session_state.get("username", "")):
            tabs.append("Strategy")
        
        for tab in tabs:
            if st.button(tab, key=f"nav_{tab}", use_container_width=True):
                st.session_state.current_tab = tab
                safe_rerun()
        
        st.divider()
        st.caption(f"User: {st.session_state.get('username', 'User')}")
        st.caption(f"Role: {st.session_state.get('role', 'user')}")
        
        if st.session_state.get("username"):
            greeting = user_personality.get_personalized_greeting(st.session_state.username)
            st.caption(f"👋 {greeting}")
        
        display_api_status()
        
        if st.button("Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.messages = []
            clear_session()
            safe_rerun()
    
    if st.session_state.current_tab == "Chat":
        chat_ui()
    elif st.session_state.current_tab == "Poster":
        poster_generator_ui()
    elif st.session_state.current_tab == "Video":
        video_generator_ui()
    elif st.session_state.current_tab == "Strategy":
        admin_strategy_ui()
    else:
        st.info("Feature coming soon.")

if __name__ == "__main__":
    main()
