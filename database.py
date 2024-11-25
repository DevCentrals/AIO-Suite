from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy import JSON

db = SQLAlchemy()

class Email(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    domain = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(50), default="pending")
    phone_numbers = db.Column(db.String(500))
    address = db.Column(db.String(250))
    dob = db.Column(db.String(100))
    name = db.Column(db.String(100))
    validmail_results = db.Column(MutableDict.as_mutable(JSON), default={})

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'domain': self.domain,
            'status': self.status,
            'phone_numbers': self.phone_numbers or 'N/A',
            'address': self.address or 'N/A',
            'dob': self.dob or 'N/A',
            'name': self.name or 'N/A',
            'validmail_results': self.validmail_results or {}
        }

    def update_autodoxed(self, phone_numbers):
        self.phone_numbers = "; ".join(phone_numbers) if phone_numbers else None
        self.status = "Autodoxed"
        db.session.commit()
    
    def update_recovery_check(self, phone_numbers):
        self.phone_numbers = "; ".join(phone_numbers) if phone_numbers else None
        self.status = "Recovery-Checked"
        db.session.commit()

    def update_info(self, name, address, dob):
        self.name = name
        self.address = address
        self.dob = dob
        db.session.commit()

    def update_validmail_results(self, module_name, result):
        if self.validmail_results is None:
            self.validmail_results = {}
        
        self.validmail_results[module_name] = result
        db.session.commit()
        
class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String, nullable=False)

    @staticmethod
    def get_setting(key):
        setting = Settings.query.filter_by(key=key).first()
        return setting.value if setting else None

    @staticmethod
    def set_setting(key, value):
        setting = Settings.query.filter_by(key=key).first()
        if setting:
            setting.value = value
        else:
            setting = Settings(key=key, value=value)
            db.session.add(setting)
        db.session.commit()

    @staticmethod
    def get_all_settings():
        settings = Settings.query.all()
        return {setting.key: setting.value for setting in settings}