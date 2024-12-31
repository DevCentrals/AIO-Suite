import os
import time
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

import requests
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from database import db, Email, Settings
from utils import get_proxy, load_all_proxies

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

socketio = SocketIO(app, async_mode='threading')

db.init_app(app)

MAX_RETRIES = 3
TASK_TIMEOUT = 30
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
        
    async def process_email(self, email: str, module_name: str, settings: Dict[str, str], proxies: List[str]) -> ModuleResult:
        if module_name not in self.search_modules:
            return ModuleResult(success=False, error=f"Module {module_name} not found")
            
        module = self.search_modules[module_name]
        if not hasattr(module, 'SearchAPIProcessor'):
            return ModuleResult(success=False, error=f"Module {module_name} does not have SearchAPIProcessor")
            
        processor = module.SearchAPIProcessor()
        
        for attempt in range(MAX_RETRIES):
            try:
                proxy = get_proxy(proxies)
                result = await processor.search(email, settings, proxy)
                if result:
                    return ModuleResult(success=True, data=result)
                await asyncio.sleep(RETRY_DELAY_SECONDS)
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    return ModuleResult(success=False, error=str(e))
                await asyncio.sleep(RETRY_DELAY_SECONDS)
                
        return ModuleResult(success=False, error="Max retries reached")

def process_email_for_lookup(email: str, proxies: List[str], settings: Dict[str, str]) -> Optional[Dict[str, Any]]:
    search_processor = SearchProcessor()
    
    enabled_modules = settings.get('enabled_search_modules', '').split(',')
    if not enabled_modules or enabled_modules[0] == '':
        enabled_modules = list(search_processor.search_modules.keys())
    
    results = []
    for module_name in enabled_modules:
        module_settings = {
            key: settings.get(key)
            for key in search_processor.required_settings.get(module_name, [])
        }
        
        result = asyncio.run(search_processor.process_email(email, module_name, module_settings, proxies))
        if result.success and result.data:
            results.append(result.data)
    
    if results:
        merged_result = results[0].copy()
        for result in results[1:]:
            for key, value in result.items():
                if key not in merged_result or not merged_result[key]:
                    merged_result[key] = value
                elif isinstance(value, list):
                    merged_result[key] = list(set(merged_result[key] + value))
        
        if 'phone_numbers' in merged_result:
            merged_result['phone_numbers'] = [
                convert_to_american_format(num) 
                for num in merged_result['phone_numbers']
            ]
        
        return merged_result
    return None

def convert_to_american_format(phone_number: str) -> str:
    digits = ''.join(filter(str.isdigit, phone_number))
    if len(digits) == 11 and digits.startswith('1'):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return phone_number

def find_email_supporting_classes(module):
    email_supported_classes = []
    for name, obj in inspect.getmembers(module):
        if inspect.isclass(obj) and hasattr(obj, 'supports_email') and obj.supports_email:
            email_supported_classes.append(obj)
    return email_supported_classes

def find_email_supporting_module(email, modules, additional_modules):
    domain = email.split('@')[-1]
    for module_name, module in modules.items():
        email_supported_classes = find_email_supporting_classes(module)
        for class_obj in email_supported_classes:
            instance = class_obj()
            if instance.supports_domain(domain):
                return module_name, class_obj
    return None, None

@app.route('/')
def index():
    emails = Email.query.all()
    return render_template('index.html', emails=emails)

@app.route('/upload', methods=['POST'])
def upload_emails():
    if request.method == 'POST':
        emails = request.files['email_file']
        if emails:
            email_lines = emails.read().decode('utf-8').splitlines()
            valid_emails = []
            
            for email in email_lines:
                email = email.strip()
                if re.match(EMAIL_REGEX, email):
                    domain = email.split('@')[-1]
                    
                    existing_email = Email.query.filter_by(email=email).first()
                    if not existing_email:
                        valid_emails.append(Email(email=email, domain=domain))
            
            if valid_emails:
                try:
                    db.session.bulk_save_objects(valid_emails)
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()
        
        return redirect(url_for('index'))
    
@app.route('/get_modules')
def get_modules():
    try:
        loaded_modules = ModuleLoader.load_modules('modules')
        additional_modules = ModuleLoader.load_modules('additional_modules')
        validmail_modules = ModuleLoader.load_modules('validmail_modules')

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
            'validmail_modules': validmail_info
        })

    except Exception as e:
        print(f"Error loading modules: {str(e)}")
        return jsonify({'modules': [], 'validmail_modules': []})

@app.route('/perform_vm_check', methods=['POST'])
def perform_vm_check():
    emails_to_lookup = request.json['selected_emails']
    selected_modules = request.json.get('selected_modules', [])
    validmail_results = []

    loaded_modules = ModuleLoader.load_modules('validmail_modules')
    proxies = load_all_proxies()
    settings = Settings.get_all_settings()
    max_concurrent_tasks = int(settings.get('threads', 10))

    socketio.emit('task_status', {'status': 'Valid-Mail check started...'})

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
                    email_record,
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

def process_email_for_validmail_check(app, email_record, loaded_modules, selected_modules, proxies, module_settings, max_retries=3):
    with app.app_context():
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

        tasks = []
        for module_name, module in validmail_modules.items():
            if selected_modules and module_name not in selected_modules:
                continue

            if email_record.validmail_results and module_name in email_record.validmail_results:
                print(f"Email {task_obj['email']} already processed for {module_name}, skipping...")
                continue

            processor_class = getattr(module, 'ValidMailChecker', None)
            if processor_class is None:
                print(f"No ValidMailChecker class found in module {module_name}")
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
                    if is_valid_mail is None:
                        print(f"Not updating Records due to uncertain outcome")
                        break
                    email = db.session.query(Email).filter_by(email=task_obj['email']).first()
                    if email:
                        email.update_validmail_results(module_name, is_valid_mail)
                        print(f"Updated validmail_results for {task_obj['email']} with module: {module_name}")
                        validmail_results = email.validmail_results or {}
                        email_result = {
                            'email': task_obj['email'],
                            'name': email.name or 'N/A',
                            'address': email.address or 'N/A',
                            'dob': email.dob or 'N/A',
                            'status': 'Valid-Mail-Checked',
                            'phone_numbers': phone_numbers,
                            'validmail_results': validmail_results
                        }

                        socketio.emit('email_result', email_result)
                    else:
                        print(f"Email {task_obj['email']} not found in the database.")
                    break
                except Exception as main_error:
                    print(f"An error occurred for {task_obj['email']} with module {module_name}: {main_error}")
                    proxy_retry_count += 1
                    print(f"Retrying with a new proxy ({proxy_retry_count}/{max_retries})")

            if proxy_retry_count == max_retries:
                print(f"Failed to process task for {task_obj['email']} with module {module_name} after {max_retries} retries.")

            tasks.append(task_obj)
        return tasks

@app.route('/perform_lookup', methods=['POST'])
def perform_lookup():
    try:
        emails_to_lookup = request.json['selected_emails']
        lookup_results = []
        
        proxies = load_all_proxies()
        settings = Settings.get_all_settings()
        max_concurrent_tasks = int(settings.get('threads', 10))

        socketio.emit('task_status', {'status': 'Task started, processing...'})

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent_tasks) as executor:
            futures = {}
            for email in emails_to_lookup:
                email_record = db.session.query(Email).filter_by(email=email).first()
                if email_record:
                    futures[executor.submit(
                        process_email_for_lookup,
                        email_record.email,
                        proxies,
                        settings
                    )] = email_record

            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result:
                    lookup_results.append(result)
                    socketio.emit('email_result', result)
                    
                    email = futures[future]
                    email.update_info(
                        name=result.get('name', ""),
                        address=result.get('address', ""),
                        dob=result.get('dob', "")
                    )
                    email.update_autodoxed(result.get('phone_numbers', []))

        socketio.emit('task_status', {'status': 'Task completed, check results.'})
        return jsonify({'success': True, 'results': lookup_results})
        
    except Exception as e:
        print(f"Error in perform_lookup: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/get_emails')
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
            print(f"Filtering by module: {module_name}, Valid: {is_valid}")
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

    return jsonify({
        'records': [record.to_dict() for record in records],
        'total': total,
        'statuses': status_list
    })

@app.route('/perform_recovery_check', methods=['POST'])
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

    socketio.emit('task_status', {'status': 'Recovery check started...'})

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
                    update_email_record(task_obj['email'], censored_number)
                    return True
                return False
                
            except Exception as error:
                print(f"An error occurred for {task_obj['email']} with module {module_instance.__class__.__name__}: {error}")
                proxy_retry_count += 1
                print(f"Retrying with a new proxy ({proxy_retry_count}/{max_retries})")
        
        print(f"Failed to process task for {task_obj['email']} with module {module_instance.__class__.__name__} after {max_retries} retries.")
        return False

    def update_email_record(email_address, censored_number):
        print(f"Matched censored number for {email_address}: {censored_number}")
        
        email = db.session.query(Email).filter_by(email=email_address).first()
        if not email:
            print(f"Email {email_address} not found in the database.")
            return
            
        phone_numbers = [censored_number]
        email.update_recovery_check(phone_numbers)
        print(f"Updated phone number for {email_address}: {phone_numbers}")
        
        email_result = {
            'email': email_address,
            'name': email.name or 'N/A',
            'address': email.address or 'N/A',
            'dob': email.dob or 'N/A',
            'status': 'Recovery-Checked',
            'phone_numbers': phone_numbers
        }
        socketio.emit('email_result', email_result)

    def get_domain_instances(modules_dict):
        instances = []
        for module_name, module in modules_dict.items():
            email_supported_classes = find_email_supporting_classes(module)
            for class_obj in email_supported_classes:
                instance = class_obj()
                if instance.supports_domain(email_record.email.split('@')[-1]):
                    instances.append((instance, module_name))
        return instances

    with app.app_context():
        phone_numbers = email_record.phone_numbers
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
        
        primary_instances = get_domain_instances(loaded_modules)
        for instance, module_name in primary_instances:
            if process_with_module(instance, task_obj, module_name):
                result_found = True
                break
        
        if not result_found:
            additional_instances = get_domain_instances(additional_modules)
            print("Processing additional modules...")
            for instance, module_name in additional_instances:
                print(f"Processing {module_name} for {task_obj['email']}")
                if process_with_module(instance, task_obj, module_name):
                    result_found = True
                    print(f"Result found with {module_name}")
                    break
            else:
                print(f"All additional modules processed for {task_obj['email']}, no result found.")


        if result_found:
            return [task_obj]

        print(f"No results found for {task_obj['email']} after processing all modules.")
        return [task_obj]


@app.route('/get_settings', methods=['GET'])
def get_settings():
    try:
        settings = Settings.get_all_settings()
        return jsonify({'success': True, 'settings': settings})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/update_settings', methods=['POST'])
def update_settings():
    try:
        data = request.json
        for key, value in data.items():
            Settings.set_setting(key, value)
        return jsonify({'success': True, 'message': 'Settings updated successfully!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/settings/<key>', methods=['GET'])
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
            'enabled_search_modules': '',
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

    socketio.run(app, debug=True)