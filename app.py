import os
import json
import inspect
import importlib
import re
import concurrent.futures
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import asyncio

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

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 20,
    'max_overflow': 30,
    'pool_timeout': 60,
    'pool_recycle': 1800,
    'pool_pre_ping': True
}
app.config['SECRET_KEY'] = '67a5a25c-7acc-800f-bff4-1b84e2762944'
app.config['ALLOW_REGISTRATION'] = False

socketio = SocketIO(app, async_mode='threading')

db.init_app(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

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
    @staticmethod
    def load_modules(folder_path: str) -> Dict[str, Any]:
        modules = {}
        if not os.path.exists(folder_path):
            return modules
            
        for file_name in os.listdir(folder_path):
            if file_name.endswith(".py"):
                module_name = file_name[:-3]
                module_path = f"{folder_path}.{module_name}"
                try:
                    module = importlib.import_module(module_path)
                    modules[module_name] = module
                except ImportError as e:
                    print(f"Failed to import module {module_name}: {e}")
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
    def __init__(self):
        self.search_modules = ModuleLoader.load_modules('search_modules')
        self.required_settings = ModuleLoader.get_required_settings(self.search_modules)
        
    def process_email(self, email: str, module_name: str, settings: Dict[str, str], proxies: List[str]) -> ModuleResult:
        if module_name not in self.search_modules:
            return ModuleResult(success=False, error=f"Module {module_name} not found")
            
        module = self.search_modules[module_name]
        if not hasattr(module, 'SearchAPIProcessor'):
            return ModuleResult(success=False, error=f"Module {module_name} does not have SearchAPIProcessor")
            
        processor = module.SearchAPIProcessor()
        
        for attempt in range(MAX_RETRIES):
            try:
                proxy = get_proxy(proxies)
                result = processor.search(email, settings, proxy)
                
                if result is not None:
                    return ModuleResult(success=True, data=result)
                
                # No results found is not a failure, it's a valid outcome
                return ModuleResult(success=True, data=None, error="No results found")
            
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    return ModuleResult(success=False, error=str(e))
                import time
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
        # Find the first non-empty string in the list
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
    emails = Email.query.all()
    return render_template('index.html', emails=emails)

@app.route('/upload', methods=['POST'])
@login_required
def upload_emails():
    if request.method == 'POST':
        emails = request.files['email_file']
        if emails:
            email_lines = emails.read().decode('utf-8').splitlines()
            valid_emails = []
            existing_emails = {email.email for email in Email.query.all()}
        
            for email in email_lines:
                email = email.strip()
                if re.match(EMAIL_REGEX, email) and email not in existing_emails:
                    domain = email.split('@')[-1]
                    valid_emails.append(Email(email=email, domain=domain))
                    existing_emails.add(email)
            if valid_emails:
                try:
                    db.session.bulk_save_objects(valid_emails)
                    db.session.commit()
                except IntegrityError as e:
                    db.session.rollback()
                    print(f"Database Error: {e}")
        
        return redirect(url_for('index'))
    
@app.route('/get_modules')
@login_required
def get_modules():
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
        else:
            print("Error: Expected dictionaries for modules, but got something else.")
            return jsonify({'modules': [], 'validmail_modules': []})
        
        if isinstance(search_modules, dict):
            all_modules = {**search_modules}
            for module_name, module in all_modules.items():
                if hasattr(module, 'SearchAPIProcessor'):
                    processor_class = getattr(module, 'SearchAPIProcessor')
                    processor_instance = processor_class()
                    if hasattr(processor_instance, 'name') and hasattr(processor_instance, 'developer'):
                        search_modules_info.append({
                            'name': processor_instance.name,
                            'developer': processor_instance.developer,
                            'module_name': module_name
                        })
        else:
            print("Error: Expected dictionaries for search_modules, but got something else.")
            return jsonify({'search_modules': []})

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

        return jsonify({
            'modules': module_info,
            'validmail_modules': validmail_info,
            'search_modules': search_modules_info
        })

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
    max_concurrent_tasks = int(settings.get('threads', 10))

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

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent_tasks) as executor:
        futures = {}
        for email in emails_to_lookup:
            email_record = db.session.query(Email).filter_by(email=email).first()
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

                    break
                except Exception as error:
                    proxy_retry_count += 1
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
        max_concurrent_tasks = int(settings.get('threads', 10))

        socketio.emit('task_status', {
            'status': 'started',
            'total': len(emails_to_lookup)
        })

        processed_count = 0
        skipped_count = 0
        error_count = 0
        
        # Process emails in smaller batches to avoid overwhelming the system
        batch_size = 100
        total_emails = len(emails_to_lookup)
        
        for batch_start in range(0, total_emails, batch_size):
            batch_end = min(batch_start + batch_size, total_emails)
            batch_emails = emails_to_lookup[batch_start:batch_end]
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent_tasks) as executor:
                futures = {}
                for email in batch_emails:
                    email_record = db.session.query(Email).filter_by(email=email).first()
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
                        # Emit a result for emails not found in database
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
        
        status_batch_size = 500
        for status_batch_start in range(0, len(emails_to_lookup), status_batch_size):
            status_batch_end = min(status_batch_start + status_batch_size, len(emails_to_lookup))
            status_batch_emails = emails_to_lookup[status_batch_start:status_batch_end]
            
            with app.app_context():
                for email in status_batch_emails:
                    try:
                        email_record = db.session.query(Email).filter_by(email=email).first()
                        if email_record and email_record.status == "pending":
                            email_record.status = "Searched"
                        elif email_record:
                            pass
                        else:
                            pass
                    except Exception as e:
                        pass
                
                try:
                    db.session.commit()
                except Exception as e:
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
                                result.data.get('phone_numbers')
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
                        elif isinstance(value, list) and key == 'phone_numbers':
                            merged_result[key] = list(set(merged_result[key] + value))
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
            
            # Save results to database
            email_record = db.session.query(Email).filter_by(email=email).first()
            if email_record:
                try:
                    # Update the email record with the found data
                    if merged_result.get('name'):
                        email_record.name = merged_result['name']
                    if merged_result.get('address'):
                        email_record.address = merged_result['address']
                    if merged_result.get('dob'):
                        email_record.dob = merged_result['dob']
                    if merged_result.get('phone_numbers'):
                        email_record.phone_numbers = "; ".join(merged_result['phone_numbers'])
                    
                    email_record.status = "Searched"
                    db.session.commit()
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
                'processed_modules': selected_modules
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
    if filters.get('module_results'):
        for module_name, is_valid in filters['module_results'].items():
            query = query.filter(
                func.json_extract(Email.validmail_results, f'$.{module_name}').cast(db.Boolean) == (True if is_valid else False)
            )

    if filters.get('has_name'):
        query = query.filter(Email.name != None, Email.name != '', Email.name != 'N/A')
    if filters.get('has_phone'):
        query = query.filter(Email.phone_numbers != None, Email.phone_numbers != '', Email.phone_numbers != 'N/A')
    if filters.get('has_address'):
        query = query.filter(Email.address != None, Email.address != '', Email.address != 'N/A')
    if filters.get('has_dob'):
        query = query.filter(Email.dob != None, Email.dob != '', Email.dob != 'N/A')

    if filters.get('vm_status'):
        vm_status = filters['vm_status']
        if vm_status == 'valid':
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
            # Delete specific emails
            emails = data.get('emails', [])
            if not emails:
                return jsonify({'success': False, 'message': 'No emails provided'}), 400
                
            result = Email.query.filter(Email.email.in_(emails)).delete(synchronize_session='fetch')
            
        elif delete_type == 'filtered':
            # Delete based on filters
            filters = data.get('filters', {})
            query = Email.query
            
            if filters.get('domain'):
                query = query.filter(Email.domain.ilike(f"%{filters['domain']}%"))
            if filters.get('status'):
                query = query.filter(Email.status == filters['status'])
            if filters.get('module_results'):
                for module_name, is_valid in filters['module_results'].items():
                    query = query.filter(
                        func.json_extract(Email.validmail_results, f'$.{module_name}').cast(db.Boolean) == (True if is_valid else False)
                    )
                    
            result = query.delete(synchronize_session='fetch')
            
        elif delete_type == 'all':
            # Delete all records
            result = Email.query.delete(synchronize_session='fetch')
            
        else:
            return jsonify({'success': False, 'message': 'Invalid delete type'}), 400
        
        # Commit the changes
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
    max_concurrent_tasks = int(settings.get('threads', 10))

    socketio.emit('task_status', {
        'status': 'started',
        'total': len(emails_to_lookup)
    })

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent_tasks) as executor:
        futures = {}
        for email in emails_to_lookup:
            email_record = db.session.query(Email).filter_by(email=email).first()
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
        """Helper function to process email with a given module instance"""
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

@socketio.on('connect')
def handle_connect():
    print("Client connected!")

@socketio.on('disconnect')
def handle_disconnect():
    print("Client disconnected!")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        
        default_settings = {
            'threads': '10',
        }
        
        for directory in DIRECTORIES:
            if not os.path.exists(directory):
                os.makedirs(directory)
                
        modules = {}
        for directory in ['validmail_modules', 'search_modules', 'additional_modules', 'modules']:
            modules.update(ModuleLoader.load_modules(directory))
            
        required_settings = ModuleLoader.get_required_settings(modules)
        
        for key, value in default_settings.items():
            if not Settings.query.filter_by(key=key).first():
                db.session.add(Settings(key=key, value=value))
                
        for module_settings in required_settings.values():
            for setting in module_settings:
                if not Settings.query.filter_by(key=setting).first():
                    db.session.add(Settings(key=setting, value=""))
                    
        db.session.commit()

    socketio.run(app, host='0.0.0.0', port=5000, debug=True)