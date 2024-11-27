# Email Lookup and Validation Web Application

This project is a web-based application designed to upload, process, and validate email addresses through various modules. It supports email lookup, recovery checks, and validation checks using different services, leveraging concurrency for efficient processing.

## Features

- **Email Upload**: Upload email files and save them to a SQLite database.
- **Email Lookup**: Lookup additional details (name, address, phone numbers, etc.) based on email addresses using external APIs.
- **Valid-Mail Check**: Perform a validity check on email addresses using multiple validation modules.
- **Recovery Check**: Check for potential recovery information linked to email addresses.
- **Module Management**: Dynamically load and manage email processing modules.
- **Concurrency**: Perform concurrent email lookups and checks using configurable threads.
- **Settings Management**: Manage settings like API keys and concurrency options.
- **Real-time Updates**: Use SocketIO for real-time status updates during long-running tasks.

## Prerequisites

Before running the application, ensure you have the following:

- Python 3.10.5
- Flask
- Flask-SQLAlchemy
- Flask-SocketIO
- Requests
- SQLite (used for database)

## Installation

1. Clone the repository:
   ```bash
   git clone [<repository-url>](https://github.com/DevCentrals/AIO-Suite.git)
   cd AIO-Suite
2. Install needed dependencies
3. Place acquired modules in the correct directories
3. python app.py
5. Access the web app in your browser: http://127.0.0.1:5000

Configuration
The application uses a SQLite database for storage. The database schema is automatically created when the app is first run.

Settings
Threads: Defines the maximum number of concurrent tasks for email lookup, valid-mail check, and recovery check.
Search API Key: An API key required for the email lookup functionality.
Capsolver Key: An API key for solving CAPTCHAs required during email validation.
You can update the settings through the web UI, or directly via the /api/settings endpoints.

Modules Overview
The application supports dynamic loading of custom modules for processing emails. These modules should be placed in one of the following directories:

modules
additional_modules
validmail_modules
Each module must define specific classes for email processing and validation. Below are the two required classes that need to be implemented within the modules:

1. EmailProcessor (for processing email data)
The EmailProcessor class is responsible for processing email data. It must implement the following:

Required Function:
process_task(task_obj, proxy, capsolver_key)
This function will be executed for each email task and must return the processed result (usually a matched number or None if no match is found).
Task Object (task_obj):
The process_task function will receive a task_obj dictionary containing the following email data:

```task_obj = {
    "email": email_record.email,
    "name": email_record.name or "",
    "numbers": phone_numbers,  # List of phone numbers
    "address": email_record.address or "",
    "dob": email_record.dob or "",
}
```
Example Implementation:
```
class EmailProcessor:
    supports_email = True  # Indicates the module supports email processing

    def __init__(self):
        self.name = "domain.com"  # Name of the domain or module
        self.developer = "Developer-Name"  # Developer name

    @staticmethod
    def required_settings():
        return ["capsolver_key"]
    
    def supports_domain(self, domain):
        """ Checks if the domain is supported by the processor """
        supported_prefixes = ["domain."]
        return any(domain.startswith(prefix) for prefix in supported_prefixes)

    def process_task(self, task_obj, settings, proxy):
        """ Process the task and return the result (e.g., matched number or None) """
        # Implement the task processing logic here
        # Example: return matched phone number or None
        self.capsolver_key = settings.get("capsolver_key")
        return task_obj['numbers'][0] if task_obj['numbers'] else None

```
2. ValidMailChecker (for checking email validity)
The ValidMailChecker class is responsible for checking the validity of an email address. It must implement the following:

Required Function:
check_validmail(email, capsolver_key, proxy)
This function checks if the provided email is valid. It should return True for a valid email, or False for an invalid email.
Example Implementation:
```
class ValidMailChecker:
    def __init__(self):
        self.name = "domain.com"  # Name of the domain or module
        self.developer = "Developer-Name"  # Developer name

    @staticmethod
    def required_settings():
        return ["capsolver_key"]

    def check_validmail(self, email, settings, proxy):
        """ Checks the validity of the email address """
        self.capsolver_key = capsolver_key
        self.proxy = proxy
        # Implement validation logic here (e.g., use external API or algorithm)
        self.capsolver_key = settings.get("capsolver_key")
        return True  # Return True for a valid email, False otherwise

```

How Modules Interact with the System
Dynamic Loading:
Modules are loaded dynamically from the directories (modules, additional_modules, validmail_modules). Each directory can contain multiple Python files representing different modules.

Processing Emails:
The EmailProcessor class handles email processing tasks. For each email, a task_obj is provided, and the process_task function is called to process the data.

Validating Emails:
The ValidMailChecker class checks if an email is valid using the check_validmail function. This function is executed for each email during the validation process.

Directory Structure
```
AIO-Suite/
│
├── app.py                       # Main Flask application
├── database.py                  # Database models and setup
├── requirements.txt             # Python dependencies
├── modules/                     # Custom modules for processing emails
├── additional_modules/          # Additional modules for processing emails
├── validmail_modules/           # Modules for email validity checks
├── templates/                   # HTML templates
├── static/                      # Static files (e.g., CSS, JavaScript)
└── proxies.txt                  # List of proxy servers for email processing
```
Routes
```
GET /: Display the uploaded emails and their processing statuses.
POST /upload: Upload a file containing email addresses.
GET /get_modules: Fetch a list of available modules.
POST /perform_lookup: Perform an email lookup for selected emails.
POST /perform_vm_check: Perform a valid-mail check for selected emails.
POST /perform_recovery_check: Perform a recovery check for selected emails.
GET /get_settings: Retrieve current settings.
POST /update_settings: Update settings.
GET /api/settings/<key>: Get a specific setting by key.
```


Feel free to fork the repository, make changes, and create pull requests. Contributions are always welcome!

License
This project is licensed under the MIT License.
