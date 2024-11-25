# Standard library imports
import os
import time
import random
import json
import inspect
import importlib
import re
import concurrent.futures

# Third-party imports
from flask import Flask, render_template, request, redirect, url_for, jsonify, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
import requests
from sqlalchemy import func

# Local application imports
from database import db, Email, Settings

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

socketio = SocketIO(app, async_mode='threading')

db.init_app(app)

MAX_RETRIES = 3
TASK_TIMEOUT = 30
RETRY_DELAY_SECONDS = 2

def load_all_proxies() -> list[str]:
    proxies = []
    with open('proxies.txt') as f:
        proxies = f.read().splitlines()

    formatted_proxies = []
    for proxy in proxies:
        try:
            proxy = f"http://{proxy}"
            formatted_proxies.append(proxy)
        except:
            pass
    return formatted_proxies

def get_proxy(proxies):
    return random.choice(proxies)

def load_modules(folder_path):
    modules = {}
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

def get_details(session, proxies, SearchAPI_key, email, retries=MAX_RETRIES):
    url = f'https://search-api.dev/search.php?email={email}&api_key={SearchAPI_key}'
    headers = {
        'Accept': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    }
    
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=TASK_TIMEOUT)
            response.raise_for_status()
            if response.text == '{"error":"No data found."}':
                return None
            return response.json()
        except Exception as e:
            if attempt == retries - 1:
                print(f"Error fetching details for {email}: {str(e)}")
                return None
            time.sleep(RETRY_DELAY_SECONDS)
    return None

def process_email_for_lookup(email, proxies, SearchAPI_key):
    session = requests.Session()
    details = get_details(session, proxies, SearchAPI_key, email)
    
    if not details:
        return None
    result = {
        'email': details.get("email", ""),
        'name': details.get("name", ""),
        'phone_numbers': details.get("numbers", []),
        'address': details.get("address", ""),
        'dob': details.get("dob", ""),
    }

    formatted_numbers = [convert_to_american_format(num) for num in result['phone_numbers']]
    result['phone_numbers'] = formatted_numbers
    return result

def convert_to_american_format(phone_number: str) -> str:
    digits = ''.join(filter(str.isdigit, phone_number))
    if len(digits) == 11 and digits.startswith('1'):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return phone_number

@app.route('/')
def index():
    emails = Email.query.all()
    return render_template('index.html', emails=emails)

EMAIL_REGEX = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'

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
                    valid_emails.append(Email(email=email, domain=domain))
            
            if valid_emails:
                db.session.bulk_save_objects(valid_emails)
                db.session.commit()
        
        return redirect(url_for('index'))

@app.route('/get_modules')
def get_modules():
    try:
        loaded_modules = load_modules('modules')
        additional_modules = load_modules('additional_modules')
        validmail_modules = load_modules('validmail_modules')

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
                            'module_name': module_name  # Adding actual module name
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

    loaded_modules = load_modules('validmail_modules')
    proxies = load_all_proxies()
    capsolver_key = Settings.get_setting('capsolver_key')
    if not capsolver_key:
        return jsonify({'error': 'Capsolver API key not found in settings'}), 400

    max_concurrent_tasks = int(request.json['threads'])

    socketio.emit('task_status', {'status': 'Valid-Mail check started...'})

    if not selected_modules:
        selected_modules = list(loaded_modules.keys())

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
                    capsolver_key
                )] = email_record

        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                validmail_results.append(result)

    socketio.emit('task_status', {'status': 'Valid-Mail check completed!'})

    return jsonify({'success': True, 'results': validmail_results})

def process_email_for_validmail_check(app, email_record, loaded_modules, selected_modules, proxies, capsolver_key, max_retries=3):
    with app.app_context():       
        validmail_modules = {}
        for module_name in selected_modules:
            if module_name in loaded_modules:
                validmail_modules[module_name] = loaded_modules[module_name]
        
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
            
            proxy_retry_count = 0
            while proxy_retry_count < max_retries:
                try:
                    proxy = get_proxy(proxies)
                    is_valid_mail = instance.check_validmail(task_obj['email'], capsolver_key, proxy)
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
        SearchAPI_key_key = Settings.get_setting('search_api_key')
        if not SearchAPI_key_key:
            return jsonify({'error': 'Capsolver API key not found in settings'}), 400
        max_concurrent_tasks = int(request.json['threads'])

        socketio.emit('task_status', {'status': 'Task started, processing...'})

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent_tasks) as executor:
            futures = {}
            for email in emails_to_lookup:
                email_record = db.session.query(Email).filter_by(email=email).first()
                if email_record:
                    futures[executor.submit(process_email_for_lookup, email_record.email, proxies, SearchAPI_key)] = email_record

            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result:
                    lookup_results.append(result)
                    socketio.emit('email_result', result)
                    email = db.session.query(Email).filter_by(email=result['email']).first()
                    if email:
                        email.update_info(
                            name=result.get('name', ""),
                            address=result.get('address', ""),
                            dob=result.get('dob', "")
                        )
                        email.update_autodoxed(result.get('phone_numbers', []))

        socketio.emit('task_status', {'status': 'Task completed, check results.'})

        return redirect(url_for('index'))
    except Exception as e:
        print(e)

@app.route('/get_emails')
def get_emails():
    page = int(request.args.get('page', 1))
    records_per_page = int(request.args.get('records_per_page', 50))
    filters = json.loads(request.args.get('filters', '{}'))
    fetch_all = request.args.get('fetch_all', 'false') == 'true'

    query = Email.query

    if 'domain' in filters:
        query = query.filter(Email.domain.ilike(f"%{filters['domain']}%"))
    if 'status' in filters:
        query = query.filter(Email.status == filters['status'])

    if 'module_results' in filters:
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

    loaded_modules = load_modules('modules')
    additional_modules = load_modules('additional_modules')
    proxies = load_all_proxies()
    capsolver_key = Settings.get_setting('capsolver_key')
    if not capsolver_key:
        return jsonify({'error': 'Capsolver API key not found in settings'}), 400

    max_concurrent_tasks = int(request.json['threads'])

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
                    capsolver_key
                )] = email_record

        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                recovery_results.append(result)

    socketio.emit('task_status', {'status': 'Recovery check completed!'})

    return redirect(url_for('index'))

def process_email_for_recovery_check(app, email_record, loaded_modules, additional_modules, proxies, capsolver_key, max_retries=3):
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

        tasks = []
        domain_found_in_module = False
        for module_name, module in loaded_modules.items():
            email_supported_classes = find_email_supporting_classes(module)
            for class_obj in email_supported_classes:
                instance = class_obj()
                if instance.supports_domain(email_record.email.split('@')[-1]):
                    domain_found_in_module = True
                    proxy_retry_count = 0
                    while proxy_retry_count < max_retries:
                        try:
                            proxy = get_proxy(proxies)
                            censored_number = instance.process_task(task_obj, proxy, capsolver_key)

                            if censored_number:
                                print(f"Matched censored number for {task_obj['email']}: {censored_number}")
                                
                                email = db.session.query(Email).filter_by(email=task_obj['email']).first()
                                if email:
                                    phone_numbers = [censored_number]
                                    email.update_recovery_check(phone_numbers)
                                    print(f"Updated phone number for {task_obj['email']}: {phone_numbers}")
                                    
                                    email_result = {
                                        'email': task_obj['email'],
                                        'name': email.name or 'N/A',
                                        'address': email.address or 'N/A',
                                        'dob': email.dob or 'N/A',
                                        'status': 'Recovery-Checked',
                                        'phone_numbers': phone_numbers
                                    }

                                    socketio.emit('email_result', email_result)

                                else:
                                    print(f"Email {task_obj['email']} not found in the database.")
                                break
                            else:
                                for additional_module_name, additional_module in additional_modules.items():
                                    email_supported_classes = find_email_supporting_classes(additional_module)
                                    for class_obj in email_supported_classes:
                                        instance = class_obj()
                                        if instance.supports_domain(email_record.email.split('@')[-1]):
                                            module_base_name = additional_module.__name__.split('.')[-1]
                                            print(f"Processing task with {module_base_name}")
                                            censored_number = instance.process_task(task_obj, proxy, capsolver_key)
                                            if censored_number:
                                                print(f"Matched censored number for {task_obj['email']}: {censored_number}")
                                                email = db.session.query(Email).filter_by(email=task_obj['email']).first()
                                                if email:
                                                    phone_numbers = [censored_number]
                                                    email.update_recovery_check(phone_numbers)
                                                    print(f"Updated phone number for {task_obj['email']}: {phone_numbers}")
                                                    
                                                    email_result = {
                                                        'email': task_obj['email'],
                                                        'name': email.name or 'N/A',
                                                        'address': email.address or 'N/A',
                                                        'dob': email.dob or 'N/A',
                                                        'status': 'Recovery-Checked',
                                                        'phone_numbers': phone_numbers
                                                    }
                                                    socketio.emit('email_result', email_result)
                                            else:
                                                break
                                break
                        except Exception as main_error:
                            print(f"An error occurred for {task_obj['email']} with module {class_obj.__name__}: {main_error}")
                            proxy_retry_count += 1
                            print(f"Retrying with a new proxy ({proxy_retry_count}/{max_retries})")

                    if proxy_retry_count == max_retries:
                        print(f"Failed to process task for {task_obj['email']} with module {class_obj.__name__} after {max_retries} retries.")
                
                    tasks.append(task_obj)

        if not domain_found_in_module:
            print(f"No modules found for domain, checking additional modules for {task_obj['email']}")
            for additional_module_name, additional_module in additional_modules.items():
                email_supported_classes = find_email_supporting_classes(additional_module)
                for class_obj in email_supported_classes:
                    instance = class_obj()
                    if instance.supports_domain(email_record.email.split('@')[-1]):
                        proxy_retry_count = 0
                        while proxy_retry_count < max_retries:
                            try:
                                proxy = get_proxy(proxies)
                                censored_number = instance.process_task(task_obj, proxy, capsolver_key)

                                if censored_number:
                                    print(f"Matched censored number for {task_obj['email']}: {censored_number}")

                                    email = db.session.query(Email).filter_by(email=task_obj['email']).first()
                                    if email:
                                        phone_numbers = [censored_number]
                                        email.update_recovery_check(phone_numbers)
                                        print(f"Updated phone number for {task_obj['email']}: {phone_numbers}")
                                        
                                        email_result = {
                                            'email': task_obj['email'],
                                            'name': email.name or 'N/A',
                                            'address': email.address or 'N/A',
                                            'dob': email.dob or 'N/A',
                                            'status': 'Recovery-Checked',
                                            'phone_numbers': phone_numbers
                                        }
                                        socketio.emit('email_result', email_result)

                                    else:
                                        print(f"Email {task_obj['email']} not found in the database.")
                                    break
                                else:
                                    break
                            except Exception as main_error:
                                print(f"An error occurred for {task_obj['email']} with additional module {class_obj.__name__}: {main_error}")
                                proxy_retry_count += 1
                                print(f"Retrying with a new proxy ({proxy_retry_count}/{max_retries})")

                        if proxy_retry_count == max_retries:
                            print(f"Failed to process task for {task_obj['email']} with additional module {class_obj.__name__} after {max_retries} retries.")
                
        return tasks

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
            'search_api_key': '',
            'capsolver_key': ''
        }

        for key, value in default_settings.items():
            if not Settings.query.filter_by(key=key).first():
                db.session.add(Settings(key=key, value=value))
        db.session.commit()
        
    socketio.run(app, debug=True)