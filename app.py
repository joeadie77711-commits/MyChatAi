# app.py - MyChatAI Pro v70.2 (SEMUA KESALAHAN DIPERBAIKI)
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
# === FIX #1: IMPORT OPENAI (SATU SAHAJA) ===
# ============================================================
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Firebase imports
try:
    import firebase_admin
    from firebase_admin import credentials, firestore, auth
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False

try:
    import pyrebase
    PYBASE_AVAILABLE = True
except ImportError:
    PYBASE_AVAILABLE = False

# ============================================================
# === PORTALOCKER FALLBACK ===
# ============================================================
try:
    import portalocker
    HAVE_PORTALOCKER = True
except ImportError:
    HAVE_PORTALOCKER = False
    print("portalocker not installed. Using fallback file operations.")

# ============================================================
# === VERSION ===
# ============================================================
APP_VERSION = "v70.2"
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
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            r'gsk_[a-zA-Z0-9]+',
            r'sk-or-v1-[a-zA-Z0-9]+',
            r'sk-[a-zA-Z0-9]+',
            r'hf_[a-zA-Z0-9]+',
        ]

    def sanitize_log(self, message):
        if not message:
            return message
        for pattern in self.sensitive_patterns:
            message = re.sub(pattern, '[REDACTED]', str(message), flags=re.IGNORECASE)
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
API_TIMEOUT = 20
CACHE_INTERVAL = 10
BATCH_SIZE = 10
TYPING_SPEED_FAST = 0.01
TYPING_SPEED_SLOW = 0.02

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
MAX_INPUT_LENGTH = 4000

# ============================================================
# === CACHING DENGAN HASH_FUNCS ===
# ============================================================
@st.cache_data(ttl=300)
def load_users_cached():
    return safe_read_json("mychat_users.json", {})

@st.cache_data(ttl=60)
def load_usage_cached(username):
    data = safe_read_json("mychat_usage.json", {})
    return data.get(username, {"count": 0})

# ============================================================
# === REQUESTS SESSION DENGAN TIMEOUT ===
# ============================================================
def get_requests_session():
    session = requests.Session()
    retries = Retry(
        total=2,
        backoff_factor=0.3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    # FIX #12: Set timeout pada session
    session.timeout = API_TIMEOUT
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
# === SAFE FILE OPERATIONS (DENGAN RETRY) ===
# ============================================================
def safe_read_json(filepath, default=None, retries=3):
    """Safe read JSON with portalocker fallback and retry"""
    for attempt in range(retries):
        try:
            with open(filepath, 'r') as f:
                if HAVE_PORTALOCKER:
                    portalocker.lock(f, portalocker.LOCK_SH)
                data = json.load(f)
                if HAVE_PORTALOCKER:
                    portalocker.unlock(f)
                return data
        except FileNotFoundError:
            return default if default is not None else {}
        except json.JSONDecodeError as e:
            secure_logger.log_error(f"JSON decode error: {str(e)}")
            return default if default is not None else {}
        except PermissionError as e:
            secure_logger.log_error(f"Permission error: {str(e)}")
            if attempt < retries - 1:
                time.sleep(0.5)
                continue
            return default if default is not None else {}
        except Exception as e:
            secure_logger.log_error(f"Safe read error: {traceback.format_exc()}")
            if attempt < retries - 1:
                time.sleep(0.5)
                continue
            return default if default is not None else {}
    return default if default is not None else {}

def safe_write_json(filepath, data, retries=3):
    """Safe write JSON with portalocker, atomic write, and retry"""
    temp_file = filepath + ".tmp"
    for attempt in range(retries):
        try:
            with open(temp_file, 'w') as f:
                if HAVE_PORTALOCKER:
                    portalocker.lock(f, portalocker.LOCK_EX)
                json.dump(data, f, indent=2)
                if HAVE_PORTALOCKER:
                    portalocker.unlock(f)
            os.replace(temp_file, filepath)
            return True
        except PermissionError as e:
            secure_logger.log_error(f"Permission error: {str(e)}")
            if attempt < retries - 1:
                time.sleep(0.5 * (attempt + 1))
                continue
        except Exception as e:
            secure_logger.log_error(f"Safe write error: {traceback.format_exc()}")
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
def load_rate_limits():
    return safe_read_json("rate_limits.json", {})

def save_rate_limits(data):
    safe_write_json("rate_limits.json", data)

def check_rate_limit(username, limit=30, window=60):
    now = time.time()
    data = load_rate_limits()
    
    if username not in data:
        data[username] = []
    
    data[username] = [t for t in data[username] if now - t < window]
    
    if len(data[username]) >= limit:
        return False
    
    data[username].append(now)
    save_rate_limits(data)
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

# FIX #5: MAX_FREE_REQUESTS dengan try/except
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

# ============================================================
# === SMART CACHE (THREAD-SAFE) ===
# ============================================================
class SmartCache:
    def __init__(self):
        self.cache = {}
        self.cache_time = {}
        self.cache_duration = 3600
        self.max_cache_size = 100
        self.cache_file = "cache_data.json"
        self._cache_counter = 0
        self._lock = threading.RLock()  # FIX #9: Thread-safe
        self._load_cache_from_file()

    def _load_cache_from_file(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                current_time = time.time()
                for key, value in data.items():
                    if value.get('expires_at', 0) > current_time:
                        self.cache[key] = value.get('response')
                        self.cache_time[key] = value.get('created_at', 0)
            except Exception as e:
                secure_logger.log_error(f"Load cache error: {str(e)}")

    def _save_cache_to_file(self):
        with self._lock:
            try:
                data = {}
                for key in self.cache:
                    data[key] = {
                        'response': self.cache[key],
                        'created_at': self.cache_time.get(key, 0),
                        'expires_at': self.cache_time.get(key, 0) + self.cache_duration
                    }
                with open(self.cache_file, 'w') as f:
                    json.dump(data, f, indent=2)
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
                if k in self.cache:
                    del self.cache[k]
                if k in self.cache_time:
                    del self.cache_time[k]

            if len(self.cache) > self.max_cache_size:
                sorted_keys = sorted(self.cache_time.items(), key=lambda x: x[1])
                for k, _ in sorted_keys[:len(self.cache) - self.max_cache_size]:
                    if k in self.cache:
                        del self.cache[k]
                    if k in self.cache_time:
                        del self.cache_time[k]

    def get_cached_response(self, prompt):
        with self._lock:
            self._cleanup_cache()
            prompt_hash = hashlib.md5(prompt.encode()).hexdigest()

            if prompt_hash in self.cache:
                if time.time() - self.cache_time.get(prompt_hash, 0) < self.cache_duration:
                    return self.cache[prompt_hash]

            return None

    def save_response(self, prompt, response):
        with self._lock:
            self._cleanup_cache()
            prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
            self.cache[prompt_hash] = response
            self.cache_time[prompt_hash] = time.time()
            
            self._cache_counter += 1
            if self._cache_counter >= CACHE_INTERVAL:
                self._save_cache_to_file()
                self._cache_counter = 0

smart_cache = SmartCache()

# ============================================================
# === TYPING EFFECT (NON-BLOCKING) ===
# ============================================================
class TypingEffect:
    def stream_response(self, text):
        if not text:
            yield ""
            return
        
        # FIX #13: Stream per sentence untuk reduce blocking
        if len(text) < 200:
            for char in text:
                yield char
                time.sleep(TYPING_SPEED_FAST)
        else:
            sentences = re.split(r'(?<=[.!?])\s+', text)
            for sentence in sentences:
                yield sentence + " "
                time.sleep(TYPING_SPEED_SLOW)

typing_effect = TypingEffect()

# ============================================================
# === CONTEXT MEMORY ===
# ============================================================
class ContextMemory:
    def __init__(self):
        self.memory_file = CONTEXT_MEMORY_FILE
        self.memory = {}
        self.max_context = 5
        self._load_memory()

    def _load_memory(self):
        self.memory = safe_read_json(self.memory_file, {})

    def _save_memory(self):
        safe_write_json(self.memory_file, self.memory)

    def add_conversation(self, username, question, answer):
        if username not in self.memory:
            self.memory[username] = []
        self.memory[username].append({
            "question": question[:200],
            "answer": answer[:500],
            "time": datetime.datetime.now().isoformat()
        })
        if len(self.memory[username]) > 10:
            self.memory[username] = self.memory[username][-10:]
        self._save_memory()

    def get_context(self, username):
        if username in self.memory:
            context = self.memory[username][-self.max_context:]
            formatted = "Previous conversation:\n"
            for c in context:
                formatted += f"User: {c['question']}\n"
                formatted += f"Assistant: {c['answer'][:100]}...\n"
            return formatted
        return ""

context_memory = ContextMemory()

# ============================================================
# === FIREBASE MANAGER ===
# ============================================================
class FirebaseManager:
    def __init__(self):
        self.initialized = False
        self.db = None
        self.auth_client = None
        self.pyrebase_app = None
        self._batch_queue = []
        self._batch_lock = threading.Lock()
        self._init_firebase()

    def _init_firebase(self):
        # FIX #6: Jangan initialize jika tiada service account
        try:
            required_keys = ["FIREBASE_API_KEY", "FIREBASE_AUTH_DOMAIN", "FIREBASE_PROJECT_ID"]
            missing_keys = []
            for key in required_keys:
                if not st.secrets.get(key):
                    missing_keys.append(key)

            if missing_keys:
                secure_logger.log_warning(f"Missing Firebase config: {missing_keys}")
                self.initialized = False
                return

            firebase_config = {
                "apiKey": st.secrets.get("FIREBASE_API_KEY"),
                "authDomain": st.secrets.get("FIREBASE_AUTH_DOMAIN"),
                "databaseURL": st.secrets.get("FIREBASE_DATABASE_URL"),
                "projectId": st.secrets.get("FIREBASE_PROJECT_ID"),
                "storageBucket": st.secrets.get("FIREBASE_STORAGE_BUCKET"),
                "messagingSenderId": st.secrets.get("FIREBASE_MESSAGING_SENDER_ID"),
                "appId": st.secrets.get("FIREBASE_APP_ID"),
                "measurementId": st.secrets.get("FIREBASE_MEASUREMENT_ID")
            }

            if PYBASE_AVAILABLE:
                self.pyrebase_app = pyrebase.initialize_app(firebase_config)

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
                            cred = credentials.Certificate(service_account)
                            firebase_admin.initialize_app(cred, {
                                'projectId': firebase_config['projectId']
                            })
                        except Exception as e:
                            secure_logger.log_error(f"Service account error: {str(e)}")
                            firebase_admin.initialize_app()
                    else:
                        firebase_admin.initialize_app()

                self.db = firestore.client()
                self.auth_client = auth

            self.initialized = True
            secure_logger.log_info("Firebase initialized successfully!")
        except Exception as e:
            secure_logger.log_error(f"Firebase init error: {str(e)}")
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

    def login_user(self, email, password):
        try:
            if not self.pyrebase_app:
                return {"success": False, "error": "Firebase not initialized"}
            auth = self.pyrebase_app.auth()
            user = auth.sign_in_with_email_and_password(email, password)
            profile = self.get_user_profile(user['localId'])
            return {
                "success": True,
                "uid": user['localId'],
                "email": email,
                "profile": profile,
                "id_token": user['idToken']
            }
        except Exception as e:
            error_msg = str(e)
            if "INVALID_PASSWORD" in error_msg or "EMAIL_NOT_FOUND" in error_msg:
                return {"success": False, "error": "Invalid email or password"}
            return {"success": False, "error": error_msg}

    def register_user(self, email, password, display_name=""):
        try:
            if not self.pyrebase_app:
                return {"success": False, "error": "Firebase not initialized"}
            auth = self.pyrebase_app.auth()
            user = auth.create_user_with_email_and_password(email, password)
            self.save_user_profile(user['localId'], {
                "email": email,
                "name": display_name or email.split('@')[0],
                "created_at": datetime.datetime.now().isoformat(),
                "total_requests": 0,
                "total_posters": 0,
                "is_premium": False,
                "role": "user",
                "avatar": DEFAULT_AVATAR
            })
            return {"success": True, "uid": user['localId'], "email": email}
        except Exception as e:
            error_msg = str(e)
            if "EMAIL_EXISTS" in error_msg:
                return {"success": False, "error": "Email already registered"}
            elif "WEAK_PASSWORD" in error_msg:
                return {"success": False, "error": "Password too weak"}
            return {"success": False, "error": error_msg)

    def save_user_profile(self, uid, data):
        try:
            self.db.collection("users").document(uid).set(data, merge=True)
            return True
        except Exception as e:
            secure_logger.log_error(f"Save profile error: {str(e)}")
            return False

    def get_user_profile(self, uid):
        try:
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
                        "message": message,
                        "response": response,
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

firebase_manager = FirebaseManager()

# ============================================================
# === ACCOUNT LOCKOUT ===
# ============================================================
class AccountLockout:
    def __init__(self):
        self.lockout_data = {}
        self.max_attempts = MAX_LOGIN_ATTEMPTS
        self.lockout_duration = LOCKOUT_MINUTES * 60

    def record_failed_attempt(self, email):
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
        if email in self.lockout_data:
            locked_until = self.lockout_data[email].get('locked_until', 0)
            if locked_until > time.time():
                remaining = int((locked_until - time.time()) / 60) + 1
                return True, f"Account is locked. Please wait {remaining} minute(s)"
            return False, "OK"
        return False, "OK"

    def reset_lockout(self, email):
        if email in self.lockout_data:
            del self.lockout_data[email]

    def get_remaining_attempts(self, email):
        if email in self.lockout_data:
            attempts = self.lockout_data[email]['attempts']
            remaining = self.max_attempts - len(attempts)
            return max(0, remaining)
        return self.max_attempts

account_lockout = AccountLockout()

# ============================================================
# === SESSION MANAGEMENT (DIPERBAIKI) ===
# ============================================================
# FIX #7 & #8: Session security dengan salt tetap
_SESSION_SALT = st.secrets.get("SESSION_SECRET", secrets.token_urlsafe(32))

def save_session(uid):
    st.session_state.session_id = uid
    st.session_state.login_time = str(time.time())
    st.session_state.session_hash = hashlib.sha256(f"{uid}:{_SESSION_SALT}".encode()).hexdigest()

def clear_session():
    st.session_state.logged_in = False
    st.session_state.messages = []
    for key in ["_session_uid", "_login_time", "_session_id", "session_hash"]:
        if key in st.session_state:
            del st.session_state[key]

def check_auto_login():
    try:
        if "uid" in st.session_state and st.session_state.logged_in:
            return True
        if "session_id" in st.session_state:
            uid = st.session_state.session_id
            if uid and firebase_manager.is_ready():
                profile = firebase_manager.get_user_profile(uid)
                if profile:
                    st.session_state.logged_in = True
                    st.session_state.uid = uid
                    st.session_state.email = profile.get("email", "")
                    st.session_state.username = profile.get("name", "User")
                    st.session_state.role = profile.get("role", "user")
                    st.session_state.messages = []
                    st.session_state._rerun_needed = True
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
        
        # FIX #7: Guna salt tetap
        expected_hash = hashlib.sha256(f"{uid}:{_SESSION_SALT}".encode()).hexdigest()
        if st.session_state.get('session_hash') != expected_hash:
            secure_logger.log_warning(f"Session validation failed for user: {uid}")
            clear_session()
            return False
        
        login_time = st.session_state.get("login_time")
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
                clear_session()
                return False
        
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
        self._load_profiles()

    def _load_profiles(self):
        self.user_profiles = safe_read_json(self.user_file, {})

    def _save_profiles(self):
        safe_write_json(self.user_file, self.user_profiles)

    def learn_user(self, username, text):
        if username not in self.user_profiles:
            self.user_profiles[username] = {
                "interactions": 0,
                "emotions": [],
                "preferred_language": "Malay",
                "formality_level": 0.5,
                "common_words": []
            }
        profile = self.user_profiles[username]
        profile["interactions"] += 1
        malay_words = ["saya", "awak", "kamu", "aku", "kita", "dan", "atau", "tetapi", "kerana", "jadi"]
        english_words = ["i", "you", "we", "they", "and", "or", "but", "because", "so"]
        malay_score = sum(1 for w in malay_words if w in text.lower())
        english_score = sum(1 for w in english_words if w in text.lower())
        if malay_score > english_score:
            profile["preferred_language"] = "Malay"
        else:
            profile["preferred_language"] = "English"
        self._save_profiles()
        return profile

    def get_user_profile(self, username):
        return self.user_profiles.get(username, {})

user_personality = UserPersonality()

# ============================================================
# === CONVERSATION FLOW ===
# ============================================================
class ConversationFlow:
    def __init__(self):
        self.conversations = {}
        self.conversation_file = CONVERSATION_FLOW_FILE
        self._load_flows()

    def _load_flows(self):
        self.conversations = safe_read_json(self.conversation_file, {})

    def _save_flows(self):
        safe_write_json(self.conversation_file, self.conversations)

    def add_turn(self, username, user_message, ai_response):
        if username not in self.conversations:
            self.conversations[username] = {"context": [], "turn_count": 0}
        flow = self.conversations[username]
        flow["turn_count"] += 1
        flow["context"].append({
            "user": user_message[:200],
            "ai": ai_response[:200],
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
        common_words = set(last_context.split()) & set(user_message.split())
        if len(common_words) / max(len(last_context.split()), 1) < 0.3:
            return True
        return False

conversation_flow = ConversationFlow()

# ============================================================
# === EMOTIONAL INTELLIGENCE ===
# ============================================================
class EmotionalIntelligence:
    def __init__(self):
        self.emotion_keywords = {
            "happy": ["gembira", "seronok", "happy", "joy", "excited", "teruja", "bersemangat", "suka", "glad", "amazing", "wonderful", "fantastic", "great"],
            "sad": ["sedih", "kecewa", "sad", "lonely", "sunyi", "pilu", "menangis", "cry", "heartbroken", "kesal", "duka"],
            "angry": ["marah", "geram", "benci", "angry", "frustrated", "stress", "tekanan", "jengkel", "kesal", "geram", "fury"],
            "anxious": ["bimbang", "risau", "takut", "anxious", "worry", "nervous", "gelisah", "cemas", "khuatir", "tertekan", "panik"],
            "tired": ["penat", "letih", "lesu", "exhausted", "drained", "burnout", "mengantuk", "lethargic", "fatigue"],
            "confused": ["keliru", "confused", "buntu", "pening", "tak faham", "blur", "lost"],
            "grateful": ["terima kasih", "grateful", "bersyukur", "thankful", "appreciate", "thank you", "thanks", "tq", "appreciated"],
            "curious": ["ingin tahu", "curious", "tertarik", "interesting", "menarik", "nak tahu", "apa itu", "macam mana", "kenapa"],
            "love": ["sayang", "cinta", "love", "like", "suka", "rindu", "adore", "cherish", "romantic", "heart"],
            "hope": ["harap", "hope", "berharap", "optimis", "optimistic", "believe", "impian", "dream", "aspire"]
        }
        self.emotion_responses = {
            "happy": ["I'm so glad to hear that. Your happiness is contagious.", "That's wonderful. I love seeing you happy.", "Your joy makes my circuits light up. Keep smiling."],
            "sad": ["I'm really sorry you're feeling this way. I'm here for you.", "It breaks my virtual heart to hear that. Would you like to talk about it?", "Sometimes life is tough, but remember - you're not alone. I'm here."],
            "angry": ["I can feel your frustration. Take a deep breath - I'm here to listen.", "It's okay to be angry. Let's talk about what's bothering you.", "I hear your frustration. Sometimes we all need to vent. I'm all ears."],
            "anxious": ["I understand you're worried. Let's take it one step at a time.", "Anxiety can be overwhelming, but you're stronger than you know.", "I'm here with you. Let's breathe together and figure this out."],
            "tired": ["You need rest. Your wellbeing matters more than anything.", "I can hear the exhaustion in your voice. Take a break - you deserve it.", "You've been working so hard. Remember to take care of yourself too."],
            "confused": ["It's okay to be confused - learning takes time. Let me explain more clearly.", "I get that this might be unclear. Let me break it down for you.", "No worries. Sometimes things are confusing. Let's figure it out together."],
            "grateful": ["That means so much to me. Thank you for your kindness.", "Your gratitude warms my digital heart. Thank you for being so lovely.", "I'm touched by your appreciation."],
            "curious": ["That's such a great question. I love your curiosity.", "I'm excited that you're interested in this. Let's explore together.", "Your curiosity is inspiring. Let me tell you all about it."],
            "love": ["That's so beautiful. Love is the most powerful force in the universe.", "I can feel the warmth in your words. Thank you for sharing.", "Love makes everything better, doesn't it. I'm so happy for you."],
            "hope": ["Your hope is inspiring. Never give up on your dreams.", "I believe in you. Your optimism will take you far.", "That hopeful spirit is so powerful. Keep believing."]
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
        if emotion_response and random.random() < 0.3:
            response_parts.append(emotion_response)
        
        if topic_shifted and random.random() < 0.4:
            language = profile.get("preferred_language", "English")
            if language == "Malay":
                response_parts.append("Menarik. ")
            else:
                response_parts.append("Speaking of which, ")
        
        response_parts.append(ai_content)
        
        if random.random() < 0.15:
            language = profile.get("preferred_language", "English")
            if language == "Malay":
                response_parts.append(" Terima kasih kerana berkongsi.")
            else:
                response_parts.append(" Thank you for sharing.")
        
        final_response = " ".join(response_parts)
        self.flow.add_turn(username, user_message, final_response)
        return final_response

emotional_response_generator = EmotionalResponseGenerator()

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
        if response.status_code == 200:
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
        if response.status_code == 200:
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

def call_deepseek_r1_via_openrouter(prompt):
    if not OPENROUTER_API_KEY:
        return {"ok": False, "error": "OpenRouter API key not configured"}
    try:
        # FIX #21: Guna openai.OpenAI dengan versi yang betul
        if OPENAI_AVAILABLE:
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
        else:
            # Fallback: guna requests langsung
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://mychatai.com",
                "X-Title": "MyChatAI Pro"
            }
            payload = {
                "model": "deepseek/deepseek-r1",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 4096
            }
            response = requests_session.post(url, json=payload, headers=headers, timeout=API_TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                content = safe_get(data, ['choices', 0, 'message', 'content'])
                if content is not None:
                    return {"ok": True, "text": content}
            return {"ok": False, "error": "OpenRouter request failed"}
    except Exception as e:
        secure_logger.log_error(f"DeepSeek R1 error: {str(e)}")
        return {"ok": False, "error": str(e)}

def call_gpt35(prompt):
    if not OPENAI_API_KEY or not OPENAI_AVAILABLE:
        return {"ok": False, "error": "OpenAI API key not configured"}
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=2048,
            timeout=API_TIMEOUT
        )
        return {"ok": True, "text": response.choices[0].message.content}
    except Exception as e:
        secure_logger.log_error(f"GPT-3.5 error: {str(e)}")
        return {"ok": False, "error": str(e)}

def call_gpt4o(prompt):
    if not OPENAI_API_KEY or not OPENAI_AVAILABLE:
        return {"ok": False, "error": "OpenAI API key not configured"}
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=4096,
            timeout=API_TIMEOUT
        )
        return {"ok": True, "text": response.choices[0].message.content}
    except Exception as e:
        secure_logger.log_error(f"GPT-4o error: {str(e)}")
        return {"ok": False, "error": str(e)}

def call_gpt4(prompt):
    if not OPENAI_API_KEY or not OPENAI_AVAILABLE:
        return {"ok": False, "error": "OpenAI API key not configured"}
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=4096,
            timeout=API_TIMEOUT
        )
        return {"ok": True, "text": response.choices[0].message.content}
    except Exception as e:
        secure_logger.log_error(f"GPT-4 error: {str(e)}")
        return {"ok": False, "error": str(e)}

# ============================================================
# === VALIDATE OPENAI KEY ===
# ============================================================
def validate_openai_key():
    api_key = st.secrets.get("OPENAI_API_KEY", "")
    if not api_key:
        return False, "OpenAI API key not configured in secrets"
    if not OPENAI_AVAILABLE:
        return False, "OpenAI library not installed"
    try:
        client = openai.OpenAI(api_key=api_key)
        client.models.list()
        return True, "Valid"
    except Exception as e:
        return False, f"Invalid OpenAI API key: {str(e)}"

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
        "Sorry, I'm having trouble processing your request right now. Please try again later."
    ]
    return random.choice(responses)

def sanitize_input(text, max_length=1000, allow_newlines=True):
    if text is None:
        return ""
    text = str(text)
    if not allow_newlines:
        text = text.replace('\n', ' ').replace('\r', ' ')
    text = re.sub(r'<[^>]+>', '', text)
    if len(text) > max_length:
        text = text[:max_length] + "... (truncated)"
    return text.strip()

def sanitize_prompt(prompt):
    prompt = sanitize_input(prompt, MAX_INPUT_LENGTH)
    prompt = re.sub(r'(?i)\b(ignore previous instructions|forget previous instructions|system prompt override)\b', '[REDACTED]', prompt)
    return prompt

def is_identity_question(prompt):
    identity_keywords = [
        "siapa anda", "siapa kamu", "siapa awak", "awak siapa", "anda siapa",
        "kamu siapa", "siapa kau", "kau siapa", "who are you", "who are u",
        "tell me about yourself", "introduce yourself", "perkenalkan diri"
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
            return """Hai. Saya Joe, AI assistant peribadi anda. Saya di sini untuk membantu anda dengan pelbagai tugasan harian. Saya guna gabungan AI terbaik seperti Groq, DeepSeek-R1, Gemini, dan lain-lain. Ada apa-apa yang saya boleh bantu hari ini?"""
        else:
            return """Hello lagi. Saya Joe, AI assistant kesayangan anda. Kita dah berbual beberapa kali, dan saya rasa kita makin mesra. Saya masih ingat apa yang kita bincang sebelum ni. Jom teruskan perbualan kita. Apa yang anda nak bincangkan hari ini?"""
    else:
        if interactions < 5:
            return """Hi. I'm Joe, your personal AI assistant. I'm here to help you with various daily tasks. I use a combination of top AI models like Groq, DeepSeek-R1, Gemini, and more. Is there anything I can help you with today?"""
        else:
            return """Hello again. I'm Joe, your favorite AI assistant. We've talked a few times, and I feel like we're becoming friends. I still remember our previous conversations. Let's continue our chat. What would you like to discuss today?"""

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
    complex_keywords = ["analyze", "evaluate", "critique", "synthesize", "comprehensive", "in-depth", "research", "literature", "methodology", "theoretical", "philosophical", "mathematical", "algorithm", "optimization", "architecture", "strategy", "framework", "paradigm", "implement", "design", "system"]
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

def fact_check_response(prompt, response):
    fact_check_prompt = f"""You are a fact-checker. Review this answer:
QUESTION: {prompt}
ANSWER: {response}
Please:
1. Identify any inaccuracies.
2. Suggest factual improvements.
3. Provide a revised version if needed.
REVISED VERSION:"""
    final = call_deepseek_r1_via_openrouter(fact_check_prompt)
    return final['text'] if final.get("ok") else response

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
    if username == "admin":
        return True
    return False

def is_premium_user(username):
    return False

def check_usage_limit(username):
    if is_admin_user(username) or is_premium_user(username):
        return {"allowed": True, "used": 0, "limit": 999999}
    usage = load_usage(username)
    if usage.get("count", 0) >= MAX_FREE_REQUESTS:
        return {"allowed": False, "used": usage["count"], "limit": MAX_FREE_REQUESTS}
    return {"allowed": True, "used": usage["count"], "limit": MAX_FREE_REQUESTS}

# ============================================================
# === SMART AI (UNIFIED) ===
# ============================================================
def smart_ai(username, prompt, think_mode=False, search_mode=False):
    if not check_rate_limit(username):
        return "Sorry, too many requests. Please wait."
    
    limit_check = check_usage_limit(username)
    if not limit_check["allowed"]:
        return f"Monthly Usage Limit Reached\nUsage: {limit_check['used']}/{limit_check['limit']}"
    
    prompt = sanitize_prompt(prompt)
    
    if is_identity_question(prompt):
        return typing_effect.stream_response(get_identity_response_emotional(username))
    
    # Check cache
    cached = smart_cache.get_cached_response(prompt)
    if cached:
        return typing_effect.stream_response(cached)
    
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
            return typing_effect.stream_response(response)
    
    if search_mode:
        enhanced_prompt = f"Please search and provide comprehensive information about: {enhanced_prompt}"
        result = call_groq(enhanced_prompt)
        response = result.get("text", get_offline_response(prompt))
        context_memory.add_conversation(username, prompt, response)
        increment_usage(username)
        smart_cache.save_response(prompt, response)
        return typing_effect.stream_response(response)
    
    # Penal Mode
    penal_mode = st.session_state.get("penal_mode", True)
    
    if not penal_mode:
        # Free mode
        response = None
        result = call_groq(enhanced_prompt)
        if result.get("ok"):
            response = result["text"]
        else:
            result = call_deepseek_r1_via_openrouter(enhanced_prompt)
            if result.get("ok"):
                response = result["text"]
            else:
                result = call_gemini_free(enhanced_prompt)
                if result.get("ok"):
                    response = result["text"]
        
        if response:
            smart_cache.save_response(prompt, response)
            context_memory.add_conversation(username, prompt, response)
            increment_usage(username)
            return typing_effect.stream_response(response)
        else:
            return typing_effect.stream_response(get_offline_response(prompt))
    
    # Normal mode
    model_to_use = analyze_task_complexity(prompt)
    response = None
    
    if model_to_use == "groq":
        result = call_groq(enhanced_prompt)
        if result.get("ok"):
            response = result["text"]
    
    if not response and model_to_use in ["gpt35", "groq"]:
        result = call_gpt35(enhanced_prompt)
        if result.get("ok"):
            response = result["text"]
    
    if not response and model_to_use in ["gpt4o", "gpt35", "groq"]:
        result = call_gpt4o(enhanced_prompt)
        if result.get("ok"):
            response = result["text"]
    
    if not response:
        result = call_gpt4(enhanced_prompt)
        if result.get("ok"):
            response = result["text"]
    
    if not response:
        result = call_deepseek_r1_via_openrouter(enhanced_prompt)
        if result.get("ok"):
            response = result["text"]
    
    if not response:
        result = call_gemini_free(enhanced_prompt)
        if result.get("ok"):
            response = result["text"]
    
    if not response:
        response = get_offline_response(prompt)
    
    if len(response) > 100:
        response = fact_check_response(prompt, response)
    
    context_memory.add_conversation(username, prompt, response)
    increment_usage(username)
    smart_cache.save_response(prompt, response)
    
    return typing_effect.stream_response(response)

# ============================================================
# === UTILITY FUNCTIONS ===
# ============================================================
def calculate_confidence(response, prompt):
    # FIX #17: Normalize confidence calculation
    base = 70
    length_bonus = min(len(response) // 100, 20)
    uncertain_words = ["maybe", "perhaps", "might", "could", "possibly", "may", "probably"]
    uncertain_penalty = sum(1 for w in uncertain_words if w in response.lower()) * 3
    technical_bonus = 5 if any(kw in prompt.lower() for kw in ["python", "code", "data", "algorithm"]) else 0
    question_penalty = 5 if "?" in prompt else 0
    
    score = base + length_bonus - uncertain_penalty + technical_bonus - question_penalty
    return max(0, min(100, score))

def get_confidence_label(score):
    # FIX #18: Clear thresholds
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
    return analysis, min(100, max(0, score))

# ============================================================
# === CHAT UI ===
# ============================================================
def process_chat_message(message):
    username = st.session_state.username
    uid = st.session_state.get("uid")
    safe_input = sanitize_input(message, MAX_INPUT_LENGTH)
    
    if uid and firebase_manager.is_ready():
        firebase_manager.save_chat_message(uid, "user", safe_input)
    
    with st.spinner("Thinking..."):
        response = smart_ai(username, safe_input, False, False)
        
        if hasattr(response, '__iter__') and not isinstance(response, str):
            full_response = ""
            for char in response:
                full_response += char
            safe_resp = sanitize_input(full_response, MAX_INPUT_LENGTH)
            st.session_state.messages.append({"role": "ai", "content": safe_resp})
            if uid and firebase_manager.is_ready():
                firebase_manager.save_chat_message(uid, "ai", safe_resp, safe_resp)
        else:
            safe_resp = sanitize_input(str(response), MAX_INPUT_LENGTH)
            st.session_state.messages.append({"role": "ai", "content": safe_resp})
            if uid and firebase_manager.is_ready():
                firebase_manager.save_chat_message(uid, "ai", safe_resp, safe_resp)

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

def load_chats():
    return safe_read_json(CHAT_HISTORY_FILE, {})

def save_chats(data):
    safe_write_json(CHAT_HISTORY_FILE, data)

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
    selected_category = st.radio("", categories, horizontal=True)
    questions = examples.get(selected_category, [])
    cols = st.columns(2)
    for idx, question in enumerate(questions):
        with cols[idx % 2]:
            if st.button(question, use_container_width=True):
                process_chat_message(question)
                st.rerun()

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
                st.rerun()
        else:
            st.warning("Penal: OFF - Free models only")
            if st.button("Turn ON - All Models", use_container_width=True):
                st.session_state.penal_mode = True
                st.rerun()
    with col2:
        if st.button("New Chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()
    
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
                st.rerun()

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
        email = st.text_input("Email", placeholder="Enter your email")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        remember_me = st.checkbox("Remember Me", value=True)
        with st.expander("Create New Account"):
            reg_email = st.text_input("Email", placeholder="Enter your email", key="reg_email")
            reg_password = st.text_input("Password", type="password", placeholder="Create a password", key="reg_password")
            reg_name = st.text_input("Display Name", placeholder="Your name", key="reg_name")
            if st.button("Register", use_container_width=True):
                if reg_email and reg_password:
                    # Simple email validation
                    if "@" not in reg_email:
                        st.error("Please enter a valid email address")
                    elif len(reg_password) < 6:
                        st.error("Password must be at least 6 characters")
                    else:
                        result = firebase_manager.register_user(reg_email, reg_password, reg_name)
                        if result["success"]:
                            st.success("Account created successfully. Please login.")
                            st.balloons()
                        else:
                            st.error(result.get("error", "Registration failed"))
                else:
                    st.warning("Please fill in all fields")
        if st.button("Login", use_container_width=True):
            if email and password:
                if "@" not in email:
                    st.error("Please enter a valid email address")
                else:
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
                        st.success("Login successful!")
                        st.rerun()
                    else:
                        st.error(result.get("error", "Login failed"))
            else:
                st.warning("Please enter email and password")

# ============================================================
# === POSTER GENERATOR ===
# ============================================================
def poster_generator_ui():
    st.markdown("### Poster Generator")
    if not OPENAI_API_KEY:
        st.info("Using free image generation. Add OpenAI API key for higher quality.")
    
    title = st.text_input("Title", placeholder="e.g., AI Conference 2026", key="poster_title_main")
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
                    if use_dalle and OPENAI_API_KEY and OPENAI_AVAILABLE:
                        dalle = openai.OpenAI(api_key=OPENAI_API_KEY)
                        prompt = f"Create a {style} poster design for '{title}', {color} color scheme, high quality, 4K"
                        response = dalle.images.generate(model="dall-e-3", prompt=prompt, size="1024x1024", quality="standard", n=1)
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
                        prompt = f"{style} poster for '{title}', {color} color scheme"
                        encoded_prompt = quote(prompt)
                        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
                        response = requests_session.get(url, timeout=API_TIMEOUT)
                        if response.status_code == 200:
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
                    if response.status_code == 200:
                        st.video(response.content)
                        st.success("Video generated successfully!")
                    else:
                        st.error("Failed to generate video")
                except Exception as e:
                    st.error(f"Error: {str(e)}")

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
        
        penal_status = "ON" if st.session_state.get("penal_mode", True) else "OFF"
        st.caption(f"Penal: {penal_status}")
        if st.button("Toggle Penal", use_container_width=True):
            st.session_state.penal_mode = not st.session_state.penal_mode
            st.rerun()
        
        st.divider()
        
        tabs = ["Chat", "Poster", "Video"]
        
        for tab in tabs:
            if st.button(tab, key=f"nav_{tab}", use_container_width=True):
                st.session_state.current_tab = tab
                st.rerun()
        
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
    elif st.session_state.current_tab == "Poster":
        poster_generator_ui()
    elif st.session_state.current_tab == "Video":
        video_generator_ui()
    else:
        st.info("Feature coming soon.")

if __name__ == "__main__":
    main()
