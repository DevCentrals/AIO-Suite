from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy import JSON
from flask_login import UserMixin
from flask_bcrypt import generate_password_hash, check_password_hash
import sys
from typing import Optional, Dict, Any

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password: str) -> None:
        """Set password."""
        self.password_hash = generate_password_hash(password).decode('utf-8')

    def check_password(self, password: str) -> bool:
        """Check password."""
        return check_password_hash(self.password_hash, password)

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

    def to_dict(self) -> Dict[str, Any]:
        """Convert email record to dictionary."""
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

    def update_autodoxed(self, phone_numbers: List[str]) -> None:
        """Update email with autodoxed phone numbers."""
        self.phone_numbers = "; ".join(phone_numbers) if phone_numbers else None
        self.status = "Autodoxed"
        db.session.commit()
    
    def update_recovery_check(self, phone_numbers: List[str]) -> None:
        """Update email with recovery check results."""
        self.phone_numbers = "; ".join(phone_numbers) if phone_numbers else None
        self.status = "Recovery-Checked"
        db.session.commit()

    def update_info(self, name: str, address: str, dob: str) -> None:
        """Update email with basic information."""
        self.name = name
        self.address = address
        self.dob = dob
        db.session.commit()

    def update_validmail_results(self, module_name: str, result: bool) -> None:
        """Update validmail results."""
        if self.validmail_results is None:
            self.validmail_results = {}
        
        self.validmail_results[module_name] = result
        db.session.commit()
        
class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String, nullable=False)

    @staticmethod
    def get_setting(key: str) -> Optional[str]:
        """Get setting value."""
        setting = Settings.query.filter_by(key=key).first()
        return setting.value if setting else None

    @staticmethod
    def set_setting(key: str, value: str) -> None:
        """Set setting value."""
        setting = Settings.query.filter_by(key=key).first()
        if setting:
            setting.value = value
        else:
            setting = Settings(key=key, value=value)
            db.session.add(setting)
        db.session.commit()

    @staticmethod
    def get_all_settings() -> Dict[str, str]:
        """Get all settings."""
        settings = Settings.query.all()
        return {setting.key: setting.value for setting in settings}