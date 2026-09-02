# app.py - MyChatAI Pro v71.3 (DEBUG LOGIN)
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
APP_VERSION = "v71.3"
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
# === FIREBASE MANAGER - GUNA REST API ===
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
            
            # DEBUG: Print to see what's happening
            st.write(f"🔍 Debug: Attempting login...")
            st.write(f"📧 Email: {email}")
            st.write(f"🔑 API Key: {api_key[:20]}...")
            st.write(f"🌐 URL: {url}")
            
            response = requests.post(url, json=payload, timeout=API_TIMEOUT)
            
            # DEBUG: Show response
            st.write(f"📊 Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                secure_logger.log_info(f"Login successful via REST for: {email}")
                st.success("✅ Firebase login successful!")
                
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
                st.error(f"❌ Firebase error: {error_msg}")
                
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
            st.error(f"❌ Exception: {str(e)}")
            return {"success": False, "error": f"Login error: {str(e)}"}

    def login_user(self, email, password):
        """Login - using REST API (no pyrebase)"""
        return self._login_via_rest(email, password)

    def register_user(self, email, password, display_name=""):
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
# === LOGIN UI (DENGAN DEBUG) ===
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
        # DEBUG: Show Firebase status
        st.info(f"🔍 Firebase Status: {'✅ Ready' if firebase_manager.is_ready() else '❌ Not Ready'}")
        
        # Login Form
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="Enter your email", key="login_email")
            password = st.text_input("Password", type="password", placeholder="Enter your password", key="login_password")
            remember_me = st.checkbox("Remember Me", value=True)
            
            submitted = st.form_submit_button("Login", use_container_width=True)
            
            if submitted:
                if email and password:
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
                        st.error(result.get("error", "Login failed"))
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
def chat_ui():
    st.markdown("### 💬 Chat")
    st.write(f"Welcome, {st.session_state.username}!")
    
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.messages = []
        clear_session()
        st.rerun()

# ============================================================
# === MAIN ===
# ============================================================
def main():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "current_tab" not in st.session_state:
        st.session_state.current_tab = "Chat"
    
    if not st.session_state.logged_in:
        if check_auto_login():
            return
        login_ui()
        return
    
    if not validate_session():
        st.warning("Your session has expired. Please login again.")
        st.session_state.logged_in = False
        clear_session()
        st.rerun()
        return
    
    with st.sidebar:
        st.markdown(f"""
        <div style="padding:16px 0 12px 0;border-bottom:1px solid rgba(255,255,255,0.06);margin-bottom:12px;">
            <div style="font-size:20px;font-weight:700;color:#e8edf5;">{APP_NAME}</div>
            <div style="font-size:11px;color:#5a5a6a;">{APP_VERSION}</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.divider()
        st.caption(f"User: {st.session_state.get('username', 'User')}")
        st.caption(f"Role: {st.session_state.get('role', 'user')}")
        
        if st.button("Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.messages = []
            clear_session()
            st.rerun()
    
    if st.session_state.current_tab == "Chat":
        chat_ui()
    else:
        st.info("Feature coming soon.")

if __name__ == "__main__":
    main()
