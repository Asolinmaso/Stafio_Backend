import re
from typing import Tuple

def validate_email(email: str) -> bool:
    """Validate email format"""
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_phone(phone: str) -> bool:
    """Validate phone number (Indian format: 10 digits starting with 6-9)"""
    if not phone:
        return False
    pattern = r'^[6-9]\d{9}$'
    # Remove spaces and special characters
    phone_cleaned = re.sub(r'[\s\-\(\)]', '', phone)
    return bool(re.match(pattern, phone_cleaned))


def validate_password(password: str) -> Tuple[bool, str]:
    """Validate password strength"""
    if not password:
        return False, "Password is required"
    
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r'\d', password):
        return False, "Password must contain at least one digit"
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    
    return True, "Password is valid"


def validate_required_fields(data: dict, required_fields: list) -> Tuple[bool, str]:
    """Check if all required fields are present and not empty"""
    if not data:
        return False, "Request body is required"
    
    missing_fields = []
    empty_fields = []
    
    for field in required_fields:
        if field not in data:
            missing_fields.append(field)
        elif not data[field] or (isinstance(data[field], str) and not data[field].strip()):
            empty_fields.append(field)
    
    if missing_fields:
        return False, f"Missing required fields: {', '.join(missing_fields)}"
    
    if empty_fields:
        return False, f"Empty fields not allowed: {', '.join(empty_fields)}"
    
    return True, ""


def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent XSS"""
    if not text:
        return ""
    return text.strip()