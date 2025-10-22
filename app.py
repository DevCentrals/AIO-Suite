import os
import json
import inspect
import importlib
import re
import concurrent.futures
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import asyncio
import sys
from functools import lru_cache
from collections import defaultdict
import threading
import time

from flask import Flask, render_template, request, redirect, url_for, jsonify, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, login_required
from flask_migrate import Migrate

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from database import db, Email, Settings, User
from utils import get_proxy, load_all_proxies
from auth import auth_bp

_proxy_cache = None
_settings_cache = None
_email_regex = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
_performance_stats = defaultdict(int)
_performance_lock = threading.Lock()

@lru_cache(maxsize=1000)
def _cached_email_validation(email: str) -> bool:
    return bool(_email_regex.match(email))

@lru_cache(maxsize=1)
def validate_proxies():
    try:
        if not os.path.exists('proxies.txt'):
            print("WARNING: proxies.txt file not found!")
            print("Please provide proxies in proxies.txt with format: username:password@host:port")
            print("Application will continue but some features may not work properly.")
            return False
        
        with open('proxies.txt', 'r', encoding='utf-8') as f:
            content = f.read().strip()
            
        if not content:
            print("WARNING: proxies.txt file is empty!")
            print("Please provide proxies in proxies.txt with format: username:password@host:port")
            print("Application will continue but some features may not work properly.")
            return False
        
        lines = content.splitlines()
        valid_proxies = sum(1 for line in lines if line.strip() and '@' in line and ':' in line)
        
        if valid_proxies == 0:
            print("WARNING: No valid proxies found in proxies.txt!")
            print("Please provide proxies in proxies.txt with format: username:password@host:port")
            print("Application will continue but some features may not work properly.")
            return False
        
        print(f"Found {valid_proxies} valid proxies in proxies.txt")
        return True
        
    except Exception as e:
        print(f"WARNING: Error reading proxies.txt: {e}")
        print("Please provide proxies in proxies.txt with format: username:password@host:port")
        print("Application will continue but some features may not work properly.")
        return False

def detect_python314_features():
    features = {
        'is_python314': sys.version_info >= (3, 14),
        'free_threaded': False,
        'template_strings': False,
        'deferred_annotations': True,
        'multiple_interpreters': False,
        'zstandard': False,
        'jit_compiler': False
    }
    
    if not features['is_python314']:
        return features
    
    try:
        import threading
        features['free_threaded'] = hasattr(threading, '_threading_local')
    except:
        pass
    
    try:
        compile('t"test {var}"', '<string>', 'eval')
        features['template_strings'] = True
    except:
        pass
    
    try:
        import interpreters
        features['multiple_interpreters'] = True
    except ImportError:
        pass
    
    try:
        import compression.zstd
        features['zstandard'] = True
    except ImportError:
        pass
    
    try:
        import _jit
        features['jit_compiler'] = True
    except ImportError:
        pass
    
    return features

def get_optimized_config():
    features = detect_python314_features()
    
    # Base configuration optimized for performance
    config = {
        'SQLALCHEMY_ENGINE_OPTIONS': {
            'pool_size': 30 if features['is_python314'] else 20,  # Larger pool for 3.14
            'max_overflow': 50 if features['is_python314'] else 30,  # More overflow connections
            'pool_timeout': 30 if features['is_python314'] else 60,  # Faster timeout
            'pool_recycle': 3600 if features['is_python314'] else 1800,  # Longer recycle time
            'pool_pre_ping': True,
            'echo': False,  # Disable SQL logging for performance
        },
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'JSONIFY_PRETTYPRINT_REGULAR': False,  # Disable pretty printing
    }
    
    # SQLite-specific optimizations for Python 3.14
    if features['is_python314']:
        config['SQLALCHEMY_ENGINE_OPTIONS']['connect_args'] = {
            'check_same_thread': False,
            'timeout': 20,  # Faster timeout
            'isolation_level': None,  # Disable isolation for better performance
        }
    
    if features['is_python314']:
        # Enable free-threaded mode optimizations
        if features['free_threaded']:
            config['THREADING_OPTIONS'] = {
                'use_free_threaded': True,
                'max_workers': 500,  # Much higher worker count for 3.14
                'thread_pool_size': 1000,
            }
        
        # Multiple interpreters for CPU-bound tasks
        if features['multiple_interpreters']:
            config['INTERPRETER_OPTIONS'] = {
                'use_multiple_interpreters': True,
                'max_interpreters': 6,  # Increase interpreter count
                'interpreter_pool_size': 8,
            }
        
        # Compression for large data transfers
        if features['zstandard']:
            config['COMPRESSION_OPTIONS'] = {
                'use_zstandard': True,
                'compression_level': 3,  # Lower compression for speed
                'compress_threshold': 1024,  # Only compress larger data
            }
        
        # Memory optimization
        config['MEMORY_OPTIONS'] = {
            'use_memory_mapping': True,
            'cache_size': 10000,  # Larger cache
            'page_size': 4096,
        }
    
    return config

def optimize_sqlite_for_python314():
    if not python314_features['is_python314']:
        return
    
    try:
        with db.engine.connect() as conn:
            conn.execute(db.text("PRAGMA journal_mode=WAL"))
            
            conn.execute(db.text("PRAGMA cache_size=-64000"))
            conn.execute(db.text("PRAGMA temp_store=MEMORY"))
            conn.execute(db.text("PRAGMA mmap_size=268435456"))
            
            conn.execute(db.text("PRAGMA foreign_keys=OFF"))
            conn.execute(db.text("PRAGMA count_changes=OFF"))
            conn.execute(db.text("PRAGMA fullfsync=OFF"))
            conn.execute(db.text("PRAGMA checkpoint_fullfsync=OFF"))
            
            conn.execute(db.text("PRAGMA page_size=4096"))
            conn.execute(db.text("PRAGMA locking_mode=NORMAL"))
            conn.execute(db.text("PRAGMA synchronous=NORMAL"))
            
            conn.commit()
    except Exception as e:
        print(f"⚠️  Warning: Could not apply SQLite optimizations: {e}")
        print("   Application will continue with default SQLite settings")

python314_features = detect_python314_features()
optimized_config = get_optimized_config()

def get_optimization_status():
    features = detect_python314_features()
    config = get_optimized_config()
    
    pool_size = config['SQLALCHEMY_ENGINE_OPTIONS']['pool_size']
    max_overflow = config['SQLALCHEMY_ENGINE_OPTIONS']['max_overflow']
    
    return {
        'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        'is_python314': features['is_python314'],
        'available_features': {k: v for k, v in features.items() if k != 'is_python314'},
        'optimizations_applied': list(config.keys()),
        'performance_metrics': {
            'connection_pool_size': pool_size,
            'max_overflow_connections': max_overflow,
            'total_connections': pool_size + max_overflow,
            'thread_optimization': features['is_python314'],
            'batch_size_optimization': features['is_python314'],
            'optimization_level': 'high' if features['is_python314'] else 'standard',
        },
        'cached_modules': len(ModuleLoader._module_cache),
        'cached_search_modules': len(SearchProcessor._search_modules_cache) if SearchProcessor._search_modules_cache else 0
    }

def clear_caches():
    global _proxy_cache, _module_info_cache, _module_info_cache_time
    
    ModuleLoader._module_cache.clear()
    SearchProcessor._search_modules_cache = None
    SearchProcessor._required_settings_cache = None
    SearchProcessor._processor_instances.clear()
    _proxy_cache = None
    _module_info_cache = None
    _module_info_cache_time = 0
    
    with _performance_lock:
        _performance_stats.clear()
    
    print("All caches cleared successfully")

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = '67a5a25c-7acc-800f-bff4-1b84e2762944'
app.config['ALLOW_REGISTRATION'] = False

app.config.update(optimized_config)

if python314_features['is_python314']:
    print("Python 3.14 detected - optimizations enabled")
    available_features = [k for k, v in python314_features.items() if v and k != 'is_python314']
    if available_features:
        print(f"Available features: {', '.join(available_features)}")
else:
    print(f"Running on Python {sys.version_info.major}.{sys.version_info.minor} - basic configuration")

socketio = SocketIO(app, async_mode='threading')

db.init_app(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

app.register_blueprint(auth_bp)

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2
DIRECTORIES = ['modules', 'additional_modules', 'validmail_modules', 'search_modules', 'instance']
EMAIL_REGEX = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
@dataclass
class ModuleResult:
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
class ModuleLoader:
    _module_cache = {}
    _processor_cache = {}
    _settings_cache = {}
    
    @staticmethod
    def load_modules(folder_path: str) -> Dict[str, Any]:
        if folder_path in ModuleLoader._module_cache:
            return ModuleLoader._module_cache[folder_path]
            
        modules = {}
        if not os.path.exists(folder_path):
            ModuleLoader._module_cache[folder_path] = modules
            return modules
        
        py_files = [f for f in os.listdir(folder_path) if f.endswith(".py")]
        
        for file_name in py_files:
            module_name = file_name[:-3]
            module_path = f"{folder_path}.{module_name}"
            try:
                module = importlib.import_module(module_path)
                modules[module_name] = module
            except ImportError as e:
                print(f"Failed to import module {module_name}: {e}")
        
        ModuleLoader._module_cache[folder_path] = modules
        return modules

    @staticmethod
    def get_required_settings(modules: Dict[str, Any]) -> Dict[str, List[str]]:
        required_settings = {}
        for module_name, module in modules.items():
            for class_name in ['ValidMailChecker', 'EmailProcessor', 'SearchAPIProcessor']:
                if hasattr(module, class_name):
                    checker_class = getattr(module, class_name)
                    if hasattr(checker_class, 'required_settings'):
                        settings = checker_class.required_settings()
                        required_settings[module_name] = settings
        return required_settings
class SearchProcessor:
    _search_modules_cache = None
    _required_settings_cache = None
    _processor_instances = {}
    
    def __init__(self):
        if SearchProcessor._search_modules_cache is None:
            SearchProcessor._search_modules_cache = ModuleLoader.load_modules('search_modules')
            SearchProcessor._required_settings_cache = ModuleLoader.get_required_settings(SearchProcessor._search_modules_cache)
        
        self.search_modules = SearchProcessor._search_modules_cache
        self.required_settings = SearchProcessor._required_settings_cache
        
    def process_email(self, email: str, module_name: str, settings: Dict[str, str], proxies: List[str]) -> ModuleResult:
        if module_name not in self.search_modules:
            return ModuleResult(success=False, error=f"Module {module_name} not found")
            
        module = self.search_modules[module_name]
        if not hasattr(module, 'SearchAPIProcessor'):
            return ModuleResult(success=False, error=f"Module {module_name} does not have SearchAPIProcessor")
        
        processor_key = f"{module_name}_{id(settings)}"
        if processor_key not in SearchProcessor._processor_instances:
            SearchProcessor._processor_instances[processor_key] = module.SearchAPIProcessor()
        
        processor = SearchProcessor._processor_instances[processor_key]
        
        proxy_list = _proxy_cache if _proxy_cache else proxies
        
        for attempt in range(MAX_RETRIES):
            try:
                proxy = get_proxy(proxy_list)
                result = processor.search(email, settings, proxy)
                
                if result is not None:
                    with _performance_lock:
                        _performance_stats[f"{module_name}_success"] += 1
                    return ModuleResult(success=True, data=result)
                
                return ModuleResult(success=True, data=None, error="No results found")
            
            except Exception as e:
                with _performance_lock:
                    _performance_stats[f"{module_name}_error"] += 1
                if attempt == MAX_RETRIES - 1:
                    return ModuleResult(success=False, error=str(e))
                time.sleep(RETRY_DELAY_SECONDS)
                
        return ModuleResult(success=False, error="Max retries reached")

def convert_to_american_format(phone_number: str) -> str:
    digits = ''.join(filter(str.isdigit, phone_number))
    if len(digits) == 11 and digits.startswith('1'):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return phone_number

def get_first_string(val):
    if isinstance(val, list):
        for item in val:
            if item and str(item).strip():
                return str(item).strip()
        return ""
    elif val is None:
        return ""
    else:
        return str(val).strip()

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/health')
def health_check():
    return jsonify({'status': 'ok', 'message': 'AIO-Suite is running'})

@app.route('/test')
def test_route():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AIO-Suite Test</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 50px; }
            .success { color: green; font-size: 24px; }
            .info { color: blue; margin: 20px 0; }
        </style>
    </head>
    <body>
        <h1 class="success">✓ AIO-Suite is Running!</h1>
        <p class="info">The web server is responding correctly.</p>
        <p><a href="/login">Go to Login Page</a></p>
        <p><strong>Default Login:</strong> Username: admin, Password: admin123</p>
    </body>
    </html>
    """

@app.route('/upload', methods=['POST'])
@login_required
def upload_emails():
    if request.method == 'POST':
        emails = request.files['email_file']
        if emails:
            email_lines = emails.read().decode('utf-8').splitlines()
            
            existing_emails = {email.email for email in Email.query.all()}
            
            valid_emails = []
            for email in email_lines:
                email = email.strip()
                if email and _cached_email_validation(email) and email not in existing_emails:
                    domain = email.split('@')[-1]
                    valid_emails.append(Email(email=email, domain=domain))
                    existing_emails.add(email)
            
            if valid_emails:
                try:
                    db.session.bulk_save_objects(valid_emails)
                    db.session.commit()
                    with _performance_lock:
                        _performance_stats['emails_uploaded'] += len(valid_emails)
                except IntegrityError as e:
                    db.session.rollback()
                    print(f"Database Error: {e}")
        
        return redirect(url_for('index'))
    
_module_info_cache = None
_module_info_cache_time = 0
CACHE_DURATION = 300

@app.route('/get_modules')
@login_required
def get_modules():
    global _module_info_cache, _module_info_cache_time
    
    current_time = time.time()
    if _module_info_cache and (current_time - _module_info_cache_time) < CACHE_DURATION:
        return jsonify(_module_info_cache)
    
    try:
        loaded_modules = ModuleLoader.load_modules('modules')
        additional_modules = ModuleLoader.load_modules('additional_modules')
        validmail_modules = ModuleLoader.load_modules('validmail_modules')
        search_modules = ModuleLoader.load_modules('search_modules')
        
        search_modules_info = []
        module_info = []
        validmail_info = []

        if isinstance(loaded_modules, dict) and isinstance(additional_modules, dict):
            all_modules = {**loaded_modules, **additional_modules}
            for module_name, module in all_modules.items():
                if hasattr(module, 'EmailProcessor'):
                    processor_class = getattr(module, 'EmailProcessor')
                    processor_instance = processor_class()
                    if hasattr(processor_instance, 'name') and hasattr(processor_instance, 'developer'):
                        module_info.append({
                            'name': processor_instance.name,
                            'developer': processor_instance.developer,
                            'module_name': module_name
                        })
        
        if isinstance(search_modules, dict):
            for module_name, module in search_modules.items():
                if hasattr(module, 'SearchAPIProcessor'):
                    processor_class = getattr(module, 'SearchAPIProcessor')
                    processor_instance = processor_class()
                    if hasattr(processor_instance, 'name') and hasattr(processor_instance, 'developer'):
                        search_modules_info.append({
                            'name': processor_instance.name,
                            'developer': processor_instance.developer,
                            'module_name': module_name
                        })

        if isinstance(validmail_modules, dict):
            for module_name, module in validmail_modules.items():
                if hasattr(module, 'ValidMailChecker'):
                    processor_class = getattr(module, 'ValidMailChecker')
                    processor_instance = processor_class()
                    if hasattr(processor_instance, 'name') and hasattr(processor_instance, 'developer'):
                        validmail_info.append({
                            'name': processor_instance.name,
                            'developer': processor_instance.developer,
                            'module_name': module_name
                        })

        result = {
            'modules': module_info,
            'validmail_modules': validmail_info,
            'search_modules': search_modules_info
        }
        
        _module_info_cache = result
        _module_info_cache_time = current_time
        
        return jsonify(result)

    except Exception as e:
        print(f"Error loading modules: {str(e)}")
        return jsonify({'modules': [], 'validmail_modules': []})

@app.route('/perform_vm_check', methods=['POST'])
@login_required
def perform_vm_check():
    emails_to_lookup = request.json['selected_emails']
    selected_modules = request.json.get('selected_modules', [])
    validmail_results = []

    loaded_modules = ModuleLoader.load_modules('validmail_modules')
    proxies = load_all_proxies()
    settings = Settings.get_all_settings()
    
    base_threads = int(settings.get('threads', 10))
    if python314_features['is_python314']:
        max_concurrent_tasks = min(base_threads * 50, 500)
    else:
        max_concurrent_tasks = base_threads

    socketio.emit('task_status', {
        'status': 'started',
        'total': len(emails_to_lookup)
    })

    if not selected_modules:
        selected_modules = list(loaded_modules.keys())

    module_settings = {}
    for module_name in selected_modules:
        if module_name in loaded_modules:
            required_settings = loaded_modules[module_name].ValidMailChecker.required_settings()
            module_settings[module_name] = {
                setting: Settings.get_setting(setting)
                for setting in required_settings
                if Settings.get_setting(setting) is not None
            }

    email_records = {}
    batch_size = 500
    for i in range(0, len(emails_to_lookup), batch_size):
        batch_emails = emails_to_lookup[i:i + batch_size]
        batch_records = {email.email: email for email in db.session.query(Email).filter(Email.email.in_(batch_emails)).all()}
        email_records.update(batch_records)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent_tasks) as executor:
        futures = {}
        for email in emails_to_lookup:
            email_record = email_records.get(email)
            if email_record:
                futures[executor.submit(
                    process_email_for_validmail_check,
                    current_app._get_current_object(),
                    email_record.email,
                    loaded_modules,
                    selected_modules,
                    proxies,
                    module_settings
                )] = email_record

        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                validmail_results.append(result)

    socketio.emit('task_status', {'status': 'Valid-Mail check completed!'})

    return jsonify({'success': True, 'results': validmail_results})

def process_email_for_validmail_check(app, email, loaded_modules, selected_modules, proxies, module_settings, max_retries=3):
    with app.app_context():
        email_record = db.session.query(Email).filter_by(email=email).first()
        if not email_record:
            print(f"Error: Email record not found for {email}")
            return None

        validmail_modules = {
            module_name: loaded_modules[module_name]
            for module_name in selected_modules if module_name in loaded_modules
        }

        phone_numbers = email_record.phone_numbers
        if isinstance(phone_numbers, str):
            phone_numbers = [num.strip() for num in phone_numbers.split(';')]

        task_obj = {
            "email": email_record.email,
            "name": email_record.name or "",
            "numbers": phone_numbers,
            "address": email_record.address or "",
            "dob": email_record.dob or "",
        }

        any_success = False
        processed_modules = []

        for module_name, module in validmail_modules.items():
            if selected_modules and module_name not in selected_modules:
                continue

            if email_record.validmail_results and module_name in email_record.validmail_results:
                any_success = True
                processed_modules.append(module_name)
                continue

            processor_class = getattr(module, 'ValidMailChecker', None)
            if processor_class is None:
                continue

            instance = processor_class()
            settings_for_module = module_settings.get(module_name, {})

            proxy_retry_count = 0
            while proxy_retry_count < max_retries:
                try:
                    proxy = get_proxy(proxies)
                    is_valid_mail = instance.check_validmail(
                        task_obj['email'],
                        settings_for_module,
                        proxy
                    )
                    if is_valid_mail is not None:
                        any_success = True
                        processed_modules.append(module_name)

                        email = db.session.query(Email).filter_by(email=task_obj['email']).first()
                        if email:
                            email.update_validmail_results(module_name, is_valid_mail)
                            db.session.commit()
                        
                        result_status = "VALID" if is_valid_mail else "INVALID"
                        print(f"[{module_name}] - {task_obj['email']}: {result_status}")

                    break
                except Exception as error:
                    proxy_retry_count += 1
                    print(f"[{module_name}] - Attempt {proxy_retry_count}/{max_retries} failed for {task_obj['email']}: {str(error)}")
                    if proxy_retry_count >= max_retries:
                        print(f"Failed after {max_retries} retries for {task_obj['email']} with {module_name}")

        db.session.refresh(email_record)

        validmail_results = email_record.validmail_results or {}
        if isinstance(validmail_results, str):
            try:
                validmail_results = json.loads(validmail_results)
            except json.JSONDecodeError:
                validmail_results = {}

        email_result = {
            'email': email_record.email,
            'name': email_record.name or 'N/A',
            'address': email_record.address or 'N/A',
            'dob': email_record.dob or 'N/A',
            'status': 'Valid-Mail-Checked',
            'phone_numbers': phone_numbers,
            'validmail_results': validmail_results,
            'success': any_success,
            'processed_modules': processed_modules
        }

        #print("Debug - Validmail Results Before Emitting:", json.dumps(validmail_results, indent=2))

        socketio.emit('email_result', email_result)

        return email_result

@app.route('/perform_lookup', methods=['POST'])
@login_required
def perform_lookup():
    try:
        emails_to_lookup = request.json['selected_emails']
        selected_modules = request.json.get('selected_modules', [])
        
        lookup_results = []
        
        proxies = load_all_proxies()
        settings = Settings.get_all_settings()
        
        # Optimize thread count for Python 3.14
        base_threads = int(settings.get('threads', 10))
        if python314_features['is_python314']:
            # Python 3.14 can handle much higher concurrency
            max_concurrent_tasks = min(base_threads * 50, 500)  # Much higher limit for 3.14
        else:
            max_concurrent_tasks = base_threads

        socketio.emit('task_status', {
            'status': 'started',
            'total': len(emails_to_lookup)
        })

        processed_count = 0
        skipped_count = 0
        error_count = 0
        
        email_records = {}
        if python314_features['is_python314']:
            db_batch_size = 800
        else:
            db_batch_size = 500
        for i in range(0, len(emails_to_lookup), db_batch_size):
            batch_emails = emails_to_lookup[i:i + db_batch_size]
            batch_records = {email.email: email for email in db.session.query(Email).filter(Email.email.in_(batch_emails)).all()}
            email_records.update(batch_records)
        
        if python314_features['is_python314']:
            batch_size = 1000
        else:
            batch_size = 500
        total_emails = len(emails_to_lookup)
        
        for batch_start in range(0, total_emails, batch_size):
            batch_end = min(batch_start + batch_size, total_emails)
            batch_emails = emails_to_lookup[batch_start:batch_end]
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent_tasks) as executor:
                futures = {}
                for email in batch_emails:
                    email_record = email_records.get(email)
                    if email_record:
                        futures[executor.submit(
                            process_email_for_lookup,
                            current_app._get_current_object(),
                            email_record.email,
                            proxies,
                            settings,
                            selected_modules
                        )] = email_record
                        processed_count += 1
                    else:
                        print(f"Warning: Email {email} not found in database, skipping...")
                        skipped_count += 1
                        socketio.emit('email_result', {
                            'email': email,
                            'name': 'N/A',
                            'address': 'N/A',
                            'dob': 'N/A',
                            'phone_numbers': [],
                            'validmail_results': {},
                            'status': 'Not Found',
                            'success': False,
                            'processed_modules': []
                        })

                try:
                    for future in concurrent.futures.as_completed(futures, timeout=300):
                        try:
                            result = future.result(timeout=60)
                            email = futures[future]
                            if result:
                                lookup_results.append(result)
                            else:
                                pass
                        except concurrent.futures.TimeoutError:
                            error_count += 1
                        except Exception as e:
                            error_count += 1
                except concurrent.futures.TimeoutError:
                    error_count += len(futures)

        socketio.emit('task_status', {'status': 'Task completed, check results.'})
        
        try:
            with app.app_context():
                if python314_features['is_python314']:
                    batch_size = 1000
                    for i in range(0, len(emails_to_lookup), batch_size):
                        batch_emails = emails_to_lookup[i:i + batch_size]
                        db.session.query(Email).filter(
                            Email.email.in_(batch_emails),
                            Email.status == "pending"
                        ).update({"status": "Searched"}, synchronize_session=False)
                        db.session.commit()
                else:
                    db.session.query(Email).filter(
                        Email.email.in_(emails_to_lookup),
                        Email.status == "pending"
                    ).update({"status": "Searched"}, synchronize_session=False)
                    db.session.commit()
        except Exception as e:
            print(f"Error updating email statuses: {e}")
            db.session.rollback()
        
        try:
            pending_count = db.session.query(Email).filter_by(status="pending").count()
            total_count = db.session.query(Email).count()
            if pending_count > 0:
                print(f"WARNING - {pending_count} emails are still pending!")
        except Exception as e:
            pass
        
        return jsonify({'success': True, 'results': lookup_results})
        
    except Exception as e:
        print(f"Error in perform_lookup: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

def process_email_for_lookup(app, email: str, proxies: List[str], settings: Dict[str, str], selected_modules) -> Optional[Dict[str, Any]]:
    with app.app_context():
        try:
            search_processor = SearchProcessor()
            
            results = []
            for module_name in selected_modules:
                try:
                    module_settings = {
                        key: settings.get(key)
                        for key in search_processor.required_settings.get(module_name, [])
                    }
                    
                    result = search_processor.process_email(email, module_name, module_settings, proxies)
                    if result.success:
                        if result.data:
                            has_data = any([
                                result.data.get('name'),
                                result.data.get('address'),
                                result.data.get('dob'),
                                result.data.get('phone_numbers'),
                                result.data.get('addresses_list'),
                                result.data.get('alternative_names')
                            ])
                            if has_data:
                                results.append(result.data)
                            else:
                                print(f"Module {module_name} returned empty data for {email}")
                        else:
                            # Module ran successfully but found no results
                            print(f"Module {module_name} found no results for {email}")
                    else:
                        print(f"Module {module_name} failed for {email}: {result.error if result else 'No result'}")
                except Exception as e:
                    print(f"Error processing {email} with module {module_name}: {e}")
                    continue
            
            merged_result = {}
            if results:
                merged_result = results[0].copy()
                for result in results[1:]:
                    for key, value in result.items():
                        if key not in merged_result or not merged_result[key]:
                            merged_result[key] = value
                        elif isinstance(value, list) and key in ['phone_numbers', 'addresses_list', 'alternative_names']:
                            merged_result[key] = list(set(merged_result[key] + value))
                        elif isinstance(value, list) and key in ['addresses_structured', 'zestimate_values', 'property_details']:
                            # For structured data, prefer non-empty values
                            if value and any(v for v in value if v):
                                merged_result[key] = value
                        elif isinstance(value, str) and isinstance(merged_result[key], str):
                            if value and not merged_result[key]:
                                merged_result[key] = value
                
                for field in ['name', 'address', 'dob']:
                    if field in merged_result:
                        if isinstance(merged_result[field], list):
                            for item in merged_result[field]:
                                if item and str(item).strip():
                                    merged_result[field] = str(item).strip()
                                    break
                            else:
                                merged_result[field] = ""
                        elif merged_result[field] is None:
                            merged_result[field] = ""
                        else:
                            merged_result[field] = str(merged_result[field]).strip()
                
                if 'phone_numbers' in merged_result:
                    merged_result['phone_numbers'] = [
                        convert_to_american_format(num) 
                        for num in merged_result['phone_numbers']
                    ]
            
            email_record = db.session.query(Email).filter_by(email=email).first()
            
            if merged_result:
                try:
                    update_data = {}
                    if merged_result.get('name'):
                        update_data['name'] = merged_result['name']
                    if merged_result.get('address'):
                        update_data['address'] = merged_result['address']
                    if merged_result.get('dob'):
                        update_data['dob'] = merged_result['dob']
                    if merged_result.get('phone_numbers'):
                        update_data['phone_numbers'] = "; ".join(merged_result['phone_numbers'])
                    
                    if merged_result.get('addresses_list'):
                        update_data['addresses_list'] = merged_result['addresses_list']
                    if merged_result.get('addresses_structured'):
                        update_data['addresses_structured'] = merged_result['addresses_structured']
                    if merged_result.get('zestimate_values'):
                        update_data['zestimate_values'] = merged_result['zestimate_values']
                    if merged_result.get('property_details'):
                        update_data['property_details'] = merged_result['property_details']
                    if merged_result.get('alternative_names'):
                        update_data['alternative_names'] = merged_result['alternative_names']
                    
                    if update_data:
                        update_data['status'] = "Searched"
                        print(f"Updating database for {email} with data: {update_data}")
                        db.session.query(Email).filter_by(email=email).update(update_data)
                        db.session.commit()
                        print(f"Successfully updated database for {email}")
                except Exception as e:
                    print(f"Error saving to database for {email}: {e}")
                    db.session.rollback()
            
            validmail_results = email_record.validmail_results if email_record else {}
            if isinstance(validmail_results, str):
                try:
                    validmail_results = json.loads(validmail_results)
                except json.JSONDecodeError:
                    validmail_results = {}
            
            result_to_emit = {
                'email': email,
                'name': merged_result.get('name', email_record.name if email_record else 'N/A'),
                'address': merged_result.get('address', email_record.address if email_record else 'N/A'),
                'dob': merged_result.get('dob', email_record.dob if email_record else 'N/A'),
                'phone_numbers': merged_result.get('phone_numbers', []),
                'validmail_results': validmail_results,
                'status': 'Searched',
                'success': bool(results),
                'processed_modules': selected_modules,
                'addresses_list': merged_result.get('addresses_list', []),
                'addresses_structured': merged_result.get('addresses_structured', []),
                'zestimate_values': merged_result.get('zestimate_values', []),
                'property_details': merged_result.get('property_details', []),
                'alternative_names': merged_result.get('alternative_names', [])
            }
            
            socketio.emit('email_result', result_to_emit)
            
            return merged_result if results else None
            
        except Exception as e:
            print(f"Critical error processing {email}: {e}")
            # Emit error result
            socketio.emit('email_result', {
                'email': email,
                'name': 'N/A',
                'address': 'N/A',
                'dob': 'N/A',
                'phone_numbers': [],
                'validmail_results': {},
                'status': 'Error',
                'success': False,
                'processed_modules': [],
                'error': str(e)
            })
            return None

@app.route('/get_emails')
@login_required
def get_emails():
    page = int(request.args.get('page', 1))
    records_per_page = int(request.args.get('records_per_page', 50))
    filters = json.loads(request.args.get('filters', '{}'))
    fetch_all = request.args.get('fetch_all', 'false') == 'true'

    query = Email.query

    if filters.get('domain'):
        query = query.filter(Email.domain.ilike(f"%{filters['domain']}%"))
    if filters.get('status'):
        query = query.filter(Email.status == filters['status'])
    if filters.get('has_name'):
        query = query.filter(Email.name != None, Email.name != '', Email.name != 'N/A')
    if filters.get('has_phone'):
        query = query.filter(Email.phone_numbers != None, Email.phone_numbers != '', Email.phone_numbers != 'N/A')
    if filters.get('has_address'):
        query = query.filter(Email.address != None, Email.address != '', Email.address != 'N/A')
    if filters.get('has_dob'):
        query = query.filter(Email.dob != None, Email.dob != '', Email.dob != 'N/A')
    
    # Filter by zestimate values
    if filters.get('has_zestimate'):
        query = query.filter(Email.zestimate_values != None, Email.zestimate_values != '[]')
    
    if filters.get('zestimate_min'):
        try:
            min_value = int(filters['zestimate_min'])
            print(f"DEBUG - Applying zestimate_min filter: {min_value}")
            conditions = []
            for i in range(10):
                conditions.append(
                    func.json_extract(Email.zestimate_values, f'$[{i}]').cast(db.Integer) >= min_value
                )
            query = query.filter(db.or_(*conditions))
            print(f"DEBUG - Zestimate filter applied, checking {len(conditions)} array elements")
        except (ValueError, TypeError):
            pass
    
    if filters.get('zestimate_max'):
        try:
            max_value = int(filters['zestimate_max'])
            print(f"DEBUG - Applying zestimate_max filter: {max_value}")
            conditions = []
            for i in range(10):
                conditions.append(
                    func.json_extract(Email.zestimate_values, f'$[{i}]').cast(db.Integer) <= max_value
                )
            query = query.filter(db.or_(*conditions))
            print(f"DEBUG - Zestimate max filter applied, checking {len(conditions)} array elements")
        except (ValueError, TypeError):
            pass
    
    if filters.get('has_alternative_names'):
        query = query.filter(Email.alternative_names != None, Email.alternative_names != '[]')
    
    if filters.get('has_multiple_addresses'):
        query = query.filter(Email.addresses_list != None, Email.addresses_list != '[]')

    if filters.get('vm_status'):
        vm_status = filters['vm_status']
        if vm_status == 'not-checked':
            query = query.filter(
                (Email.validmail_results == None) | 
                (Email.validmail_results == '') |
                (func.json_extract(Email.validmail_results, '$') == '{}')
            )
        elif vm_status == 'valid':
            query = query.filter(Email.validmail_results != None)
            query = query.filter(
                func.json_extract(Email.validmail_results, '$') != '{}'
            )
        elif vm_status == 'invalid':
            query = query.filter(Email.validmail_results != None)
            query = query.filter(
                func.json_extract(Email.validmail_results, '$') != '{}'
            )
        elif vm_status == 'all-valid':
            query = query.filter(Email.validmail_results != None)
            query = query.filter(
                func.json_extract(Email.validmail_results, '$') != '{}'
            )
        elif vm_status == 'all-invalid':
            query = query.filter(Email.validmail_results != None)
            query = query.filter(
                func.json_extract(Email.validmail_results, '$') != '{}'
            )

    module_results = {}
    if filters.get('module_results'):
        module_results.update(filters['module_results'])
    if filters.get('vm_module_results'):
        module_results.update(filters['vm_module_results'])
    
    if module_results:
        for module_name, is_valid in module_results.items():
            if is_valid is not None:
                query = query.filter(
                    func.json_extract(Email.validmail_results, f'$.{module_name}').cast(db.Boolean) == (True if is_valid else False)
                )

    total = query.count()

    if fetch_all:
        records = query.all()
    else:
        records = query.offset((page - 1) * records_per_page).limit(records_per_page).all()

    statuses = db.session.query(Email.status).distinct().all()
    status_list = [status[0] for status in statuses]
    
    result = {
        'records': [record.to_dict() for record in records],
        'total': total,
        'statuses': status_list
    }
    
    return jsonify(result)

@app.route('/delete_records', methods=['POST'])
@login_required
def delete_records():
    try:
        data = request.get_json()
        delete_type = data.get('delete_type')
        
        if delete_type == 'selected':
            emails = data.get('emails', [])
            if not emails:
                return jsonify({'success': False, 'message': 'No emails provided'}), 400
                
            result = Email.query.filter(Email.email.in_(emails)).delete(synchronize_session='fetch')
            
        elif delete_type == 'filtered':
            filters = data.get('filters', {})
            query = Email.query
            
            if filters.get('domain'):
                query = query.filter(Email.domain.ilike(f"%{filters['domain']}%"))
            if filters.get('status'):
                query = query.filter(Email.status == filters['status'])
            module_results = {}
            if filters.get('module_results'):
                module_results.update(filters['module_results'])
            if filters.get('vm_module_results'):
                module_results.update(filters['vm_module_results'])
            
            if module_results:
                for module_name, is_valid in module_results.items():
                    if is_valid is not None:
                        query = query.filter(
                            func.json_extract(Email.validmail_results, f'$.{module_name}').cast(db.Boolean) == (True if is_valid else False)
                        )
                    
            result = query.delete(synchronize_session='fetch')
            
        elif delete_type == 'all':
            result = Email.query.delete(synchronize_session='fetch')
            
        else:
            return jsonify({'success': False, 'message': 'Invalid delete type'}), 400
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'deleted_count': result,
            'message': f'Successfully deleted {result} record(s)'
        })
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting records: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error deleting records: {str(e)}'
        }), 500

@app.route('/perform_recovery_check', methods=['POST'])
@login_required
def perform_recovery_check():
    emails_to_lookup = request.json['selected_emails']
    recovery_results = []

    loaded_modules = ModuleLoader.load_modules('modules')
    additional_modules = ModuleLoader.load_modules('additional_modules')
    proxies = load_all_proxies()
    
    all_modules = {**loaded_modules, **additional_modules}
    
    required_settings = ModuleLoader.get_required_settings(all_modules)
    
    module_settings = {}
    for module_name, module in all_modules.items():
        module_required_settings = required_settings.get(module_name, [])
        module_settings[module_name] = {
            setting: Settings.get_setting(setting)
            for setting in module_required_settings
            if Settings.get_setting(setting) is not None
        }

    settings = Settings.get_all_settings()
    
    base_threads = int(settings.get('threads', 10))
    if python314_features['is_python314']:
        max_concurrent_tasks = min(base_threads * 50, 500)
    else:
        max_concurrent_tasks = base_threads

    socketio.emit('task_status', {
        'status': 'started',
        'total': len(emails_to_lookup)
    })

    email_records = {}
    batch_size = 500
    for i in range(0, len(emails_to_lookup), batch_size):
        batch_emails = emails_to_lookup[i:i + batch_size]
        batch_records = {email.email: email for email in db.session.query(Email).filter(Email.email.in_(batch_emails)).all()}
        email_records.update(batch_records)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent_tasks) as executor:
        futures = {}
        for email in emails_to_lookup:
            email_record = email_records.get(email)
            if email_record:
                futures[executor.submit(
                    process_email_for_recovery_check, 
                    current_app._get_current_object(),
                    email_record, 
                    loaded_modules,
                    additional_modules, 
                    proxies, 
                    module_settings
                )] = email_record

        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                recovery_results.append(result)

    socketio.emit('task_status', {'status': 'Recovery check completed!'})

    return redirect(url_for('index'))

def process_email_for_recovery_check(app, email_record, loaded_modules, additional_modules, proxies, module_settings, max_retries=3):
    def process_with_module(module_instance, task_obj, module_name, proxy_retry_count=0):
        while proxy_retry_count < max_retries:
            try:
                module_specific_settings = module_settings.get(module_name, {})
                proxy = get_proxy(proxies)
                
                censored_number = module_instance.process_task(task_obj, module_specific_settings, proxy)
                
                if censored_number:
                    update_email_record(task_obj['email'], censored_number, module_name)
                    return True
                return False
                
            except Exception as error:
                print(f"An error occurred for {task_obj['email']} with module {module_instance.__class__.__name__}: {error}")
                proxy_retry_count += 1
                print(f"Retrying with a new proxy ({proxy_retry_count}/{max_retries})")
        
        print(f"Failed to process task for {task_obj['email']} with module {module_instance.__class__.__name__} (from {module_name}) after {max_retries} retries.")
        return False

    def update_email_record(email_address, censored_number, module_name):
        print(f"Matched censored number for {email_address}: {censored_number}")
        
        email = db.session.query(Email).filter_by(email=email_address).first()
        if not email:
            print(f"Email {email_address} not found in the database.")
            return
            
        phone_numbers = [censored_number]
        email.update_recovery_check(phone_numbers)
        print(f"Updated phone number for {email_address}: {phone_numbers}")
        
        validmail_results = email.validmail_results or {}
        if isinstance(validmail_results, str):
            try:
                validmail_results = json.loads(validmail_results)
            except json.JSONDecodeError:
                validmail_results = {}
        
        email_result = {
            'email': email_address,
            'name': email.name or 'N/A',
            'address': email.address or 'N/A',
            'dob': email.dob or 'N/A',
            'status': 'Recovery-Checked',
            'phone_numbers': phone_numbers,
            'validmail_results': validmail_results,
            'processed_modules': [module_name]
        }
        socketio.emit('email_result', {
            **email_result,
            'success': True
        })

    def get_domain_instances(modules_dict):
        instances = []
        for module_name, module in modules_dict.items():
            email_supported_classes = find_email_supporting_classes(module)
            for class_obj in email_supported_classes:
                instance = class_obj()
                if instance.supports_domain(email_record.email.split('@')[-1]):
                    instances.append((instance, module_name))
        return instances
    
    def find_email_supporting_classes(module):
        email_supported_classes = []
        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and hasattr(obj, 'supports_email') and obj.supports_email:
                email_supported_classes.append(obj)
        return email_supported_classes

    with app.app_context():
        phone_numbers = email_record.phone_numbers
        if not phone_numbers:
            validmail_results = email_record.validmail_results or {}
            if isinstance(validmail_results, str):
                try:
                    validmail_results = json.loads(validmail_results)
                except json.JSONDecodeError:
                    validmail_results = {}
                    
            email_result = {
                'email': email_record.email,
                'name': email_record.name or 'N/A',
                'address': email_record.address or 'N/A',
                'dob': email_record.dob or 'N/A',
                'status': 'Skipped-No-Numbers',
                'phone_numbers': [],
                'validmail_results': validmail_results,
                'processed_modules': [],
                'success': False
            }
            socketio.emit('email_result', email_result)
            return []
        
        if isinstance(phone_numbers, str):
            phone_numbers = [num.strip() for num in phone_numbers.split(';')]
        print("Processed phone numbers:", phone_numbers)

        task_obj = {
            "email": email_record.email,
            "name": email_record.name or "",
            "numbers": phone_numbers,
            "address": email_record.address or "",
            "dob": email_record.dob or "",
        }

        result_found = False
        processed_modules = []
        
        primary_instances = get_domain_instances(loaded_modules)
        for instance, module_name in primary_instances:
            processed_modules.append(module_name)
            if process_with_module(instance, task_obj, module_name):
                result_found = True
                break
        
        if not result_found:
            additional_instances = get_domain_instances(additional_modules)
            print("Processing additional modules...")
            for instance, module_name in additional_instances:
                print(f"Processing {module_name} for {task_obj['email']}")
                processed_modules.append(module_name)
                if process_with_module(instance, task_obj, module_name):
                    result_found = True
                    print(f"Result found with {module_name}")
                    break
            else:
                print(f"All additional modules processed for {task_obj['email']}, no result found.")

        validmail_results = email_record.validmail_results or {}
        if isinstance(validmail_results, str):
            try:
                validmail_results = json.loads(validmail_results)
            except json.JSONDecodeError:
                validmail_results = {}

        email_result = {
            'email': email_record.email,
            'name': email_record.name or 'N/A',
            'address': email_record.address or 'N/A',
            'dob': email_record.dob or 'N/A',
            'status': 'Recovery-Checked',
            'phone_numbers': phone_numbers,
            'validmail_results': validmail_results,
            'processed_modules': processed_modules,
            'success': result_found
        }
        socketio.emit('email_result', email_result)

        return [task_obj] if result_found else []

@app.route('/get_settings', methods=['GET'])
@login_required
def get_settings():
    try:
        settings = Settings.get_all_settings()
        return jsonify({'success': True, 'settings': settings})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/update_settings', methods=['POST'])
@login_required
def update_settings():
    try:
        data = request.json
        for key, value in data.items():
            Settings.set_setting(key, value)
        return jsonify({'success': True, 'message': 'Settings updated successfully!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/settings/<key>', methods=['GET'])
@login_required
def get_setting(key):
    try:
        value = Settings.get_setting(key)
        if value is not None:
            return jsonify({'success': True, 'value': value})
        else:
            return jsonify({'success': False, 'message': 'Setting not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/optimization-status', methods=['GET'])
@login_required
def optimization_status():
    """Get current Python optimization status."""
    try:
        status = get_optimization_status()
        return jsonify({'success': True, 'status': status})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/clear-caches', methods=['POST'])
@login_required
def clear_caches_endpoint():
    """Clear all caches for memory management."""
    try:
        clear_caches()
        return jsonify({'success': True, 'message': 'Caches cleared successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/performance-stats', methods=['GET'])
@login_required
def performance_stats():
    """Get comprehensive performance statistics."""
    try:
        with _performance_lock:
            stats = dict(_performance_stats)
        
        # Add optimization status
        optimization_status = get_optimization_status()
        
        # Add cache statistics
        stats.update({
            'cached_modules': len(ModuleLoader._module_cache),
            'cached_search_modules': len(SearchProcessor._search_modules_cache) if SearchProcessor._search_modules_cache else 0,
            'cached_processors': len(SearchProcessor._processor_instances),
            'cached_proxies': len(_proxy_cache) if _proxy_cache else 0,
            'module_info_cache_age': time.time() - _module_info_cache_time if _module_info_cache else 0,
            'optimization_status': optimization_status,
            'python_performance_mode': 'optimized' if python314_features['is_python314'] else 'standard',
            'recommended_threads': min(int(Settings.get_setting('threads', 10)) * 50, 500) if python314_features['is_python314'] else int(Settings.get_setting('threads', 10))
        })
        
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@socketio.on('connect')
def handle_connect():
    print("Client connected!")

@socketio.on('disconnect')
def handle_disconnect():
    print("Client disconnected!")

if __name__ == "__main__":
    print("Starting AIO-Suite application...")
    
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        
        optimize_sqlite_for_python314()
        
        default_settings = {
            'threads': '10',
            'house_value': 'false',
        }
        
        print("Creating directories...")
        for directory in DIRECTORIES:
            if not os.path.exists(directory):
                os.makedirs(directory)
                print(f"Created directory: {directory}")
                
        print("Loading modules...")
        modules = {}
        for directory in ['validmail_modules', 'search_modules', 'additional_modules', 'modules']:
            loaded = ModuleLoader.load_modules(directory)
            modules.update(loaded)
            print(f"Loaded {len(loaded)} modules from {directory}")
            
        print("Getting required settings...")
        required_settings = ModuleLoader.get_required_settings(modules)
        
        print("Setting up default settings...")
        for key, value in default_settings.items():
            if not Settings.query.filter_by(key=key).first():
                db.session.add(Settings(key=key, value=value))
                
        for module_settings in required_settings.values():
            for setting in module_settings:
                if not Settings.query.filter_by(key=setting).first():
                    db.session.add(Settings(key=setting, value=""))
        
        if not User.query.first():
            print("Creating default admin user...")
            admin_user = User(username='admin', email='admin@example.com')
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            print("Default admin user created - Username: admin, Password: admin123")
                    
        db.session.commit()
        print("Database setup complete!")

    print("Starting web server...")
    print("Application is ready! Access it at: http://127.0.0.1:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)