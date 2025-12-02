from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
import requests
from database import SessionLocal, User
from auth import generate_token
from validators import validate_email, validate_phone, validate_password, validate_required_fields, sanitize_input
from services.otp_service import OTPService
from services.email_service import EmailService

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    data = request.get_json()
    
    # Validate required fields
    required = ['username', 'password', 'email', 'phone']
    is_valid, error_msg = validate_required_fields(data, required)
    if not is_valid:
        return jsonify({"message": error_msg}), 400
    
    # Extract and sanitize data
    username = sanitize_input(data.get('username'))
    password = data.get('password')
    email = sanitize_input(data.get('email')).lower()
    phone = sanitize_input(data.get('phone'))
    first_name = sanitize_input(data.get('first_name', ''))
    last_name = sanitize_input(data.get('last_name', ''))
    role = data.get('role', 'employee')
    
    # Validate email
    if not validate_email(email):
        return jsonify({"message": "Invalid email format"}), 400
    
    # Validate phone
    if not validate_phone(phone):
        return jsonify({"message": "Invalid phone number format (use 10 digits)"}), 400
    
    # Validate password
    is_valid, password_msg = validate_password(password)
    if not is_valid:
        return jsonify({"message": password_msg}), 400
    
    # Validate role
    if role not in ['employee', 'admin']:
        return jsonify({"message": "Invalid role"}), 400
    
    hashed_password = generate_password_hash(password)
    
    db = SessionLocal()
    try:
        new_user = User(
            username=username,
            password_hash=hashed_password,
            email=email,
            phone=phone,
            first_name=first_name,
            last_name=last_name,
            role=role
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        # Send welcome email (non-blocking)
        EmailService.send_welcome_email(email, username)
        
        # Generate token
        token = generate_token(new_user.id, new_user.role, new_user.username)
        
        return jsonify({
            "message": "User registered successfully",
            "token": token,
            "user_id": new_user.id,
            "username": new_user.username,
            "role": new_user.role
        }), 201
        
    except IntegrityError as e:
        db.rollback()
        error_msg = str(e.orig)
        if 'username' in error_msg:
            return jsonify({"message": "Username already exists"}), 409
        elif 'email' in error_msg:
            return jsonify({"message": "Email already exists"}), 409
        elif 'phone' in error_msg:
            return jsonify({"message": "Phone number already exists"}), 409
        return jsonify({"message": "Registration failed"}), 409
    except Exception as e:
        db.rollback()
        print(f"Registration error: {e}")
        return jsonify({"message": "An unexpected error occurred"}), 500
    finally:
        db.close()


@auth_bp.route('/login/employee', methods=['POST'])
def employee_login():
    """Employee login"""
    data = request.get_json()
    
    identifier = sanitize_input(data.get('identifier', ''))
    password = data.get('password', '')
    
    if not identifier or not password:
        return jsonify({"message": "Username/Email and password are required"}), 400
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(
            ((User.username == identifier) | (User.email == identifier.lower())),
            User.role == 'employee'
        ).first()
        
        if not user:
            return jsonify({"message": "Invalid credentials"}), 401
        
        if not user.password_hash:
            return jsonify({"message": "Please use Google login for this account"}), 401
        
        if not check_password_hash(user.password_hash, password):
            return jsonify({"message": "Invalid credentials"}), 401
        
        token = generate_token(user.id, user.role, user.username)
        
        return jsonify({
            "message": "Login successful",
            "token": token,
            "user_id": user.id,
            "username": user.username,
            "role": user.role
        }), 200
        
    except Exception as e:
        print(f"Employee login error: {e}")
        return jsonify({"message": "An unexpected error occurred"}), 500
    finally:
        db.close()


@auth_bp.route('/login/admin', methods=['POST'])
def admin_login():
    """Admin login"""
    data = request.get_json()
    
    identifier = sanitize_input(data.get('identifier', ''))
    password = data.get('password', '')
    
    if not identifier or not password:
        return jsonify({"message": "Username/Email and password are required"}), 400
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(
            ((User.username == identifier) | (User.email == identifier.lower())),
            User.role == 'admin'
        ).first()
        
        if not user:
            return jsonify({"message": "Invalid admin credentials"}), 401
        
        if not user.password_hash:
            return jsonify({"message": "Please use Google login for this account"}), 401
        
        if not check_password_hash(user.password_hash, password):
            return jsonify({"message": "Invalid admin credentials"}), 401
        
        token = generate_token(user.id, user.role, user.username)
        
        return jsonify({
            "message": "Login successful",
            "token": token,
            "user_id": user.id,
            "username": user.username,
            "role": user.role
        }), 200
        
    except Exception as e:
        print(f"Admin login error: {e}")
        return jsonify({"message": "An unexpected error occurred"}), 500
    finally:
        db.close()


@auth_bp.route('/google/login', methods=['POST'])
def google_login():
    """Handle Google OAuth login/registration"""
    data = request.get_json()
    id_token = data.get("id_token")
    requested_role = data.get("role", "employee")
    
    if not id_token:
        return jsonify({"message": "Missing id_token"}), 400
    
    if requested_role not in ['employee', 'admin']:
        return jsonify({"message": "Invalid role"}), 400
    
    # Verify Google Token
    try:
        r = requests.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": id_token},
            timeout=10
        )
        
        if r.status_code != 200:
            return jsonify({"message": "Invalid Google token"}), 401
        
        token_info = r.json()
        
    except Exception as ex:
        print(f"Google token verification error: {ex}")
        return jsonify({"message": "Error verifying Google token"}), 500
    
    email = token_info.get("email", "").lower()
    given_name = token_info.get("given_name", "")
    family_name = token_info.get("family_name", "")
    email_verified = str(token_info.get("email_verified")).lower() == "true"
    
    if not email or not email_verified:
        return jsonify({"message": "Google account email not verified"}), 400
    
    db = SessionLocal()
    try:
        # Check if user exists
        user = db.query(User).filter(User.email == email).first()
        
        if user:
            # User exists - log them in
            # Check if role matches
            if user.role != requested_role:
                return jsonify({
                    "message": f"This email is registered as {user.role}, not {requested_role}"
                }), 403
            
            token = generate_token(user.id, user.role, user.username)
            
            return jsonify({
                "message": "Login successful",
                "token": token,
                "user_id": user.id,
                "username": user.username,
                "role": user.role,
                "email": user.email
            }), 200
        
        # User doesn't exist - create new account
        username_base = email.split("@")[0]
        username = username_base
        i = 1
        
        while db.query(User).filter(User.username == username).first():
            username = f"{username_base}{i}"
            i += 1
        
        new_user = User(
            username=username,
            email=email,
            password_hash="",  # Empty for Google users
            first_name=given_name,
            last_name=family_name,
            role=requested_role
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        token = generate_token(new_user.id, new_user.role, new_user.username)
        
        # Send welcome email
        EmailService.send_welcome_email(email, username)
        
        return jsonify({
            "message": "Registration successful",
            "token": token,
            "user_id": new_user.id,
            "username": new_user.username,
            "role": new_user.role,
            "email": new_user.email
        }), 201
        
    except Exception as e:
        db.rollback()
        print(f"Google login error: {e}")
        return jsonify({"message": "An unexpected error occurred"}), 500
    finally:
        db.close()


@auth_bp.route('/forgot-password/send-otp', methods=['POST'])
def send_otp():
    """Send OTP for password reset"""
    data = request.get_json()
    email = sanitize_input(data.get("email", "")).lower()
    
    if not email:
        return jsonify({"message": "Email is required"}), 400
    
    if not validate_email(email):
        return jsonify({"message": "Invalid email format"}), 400
    
    success, message = OTPService.create_otp(email)
    
    if success:
        return jsonify({"message": message}), 200
    else:
        status_code = 404 if "not registered" in message else 500
        return jsonify({"message": message}), status_code


@auth_bp.route('/forgot-password/verify-otp', methods=['POST'])
def verify_otp():
    """Verify OTP"""
    data = request.get_json()
    email = sanitize_input(data.get("email", "")).lower()
    otp = sanitize_input(data.get("otp", ""))
    
    if not email or not otp:
        return jsonify({"message": "Email and OTP are required"}), 400
    
    success, message = OTPService.verify_otp(email, otp)
    
    if success:
        return jsonify({"message": message}), 200
    else:
        return jsonify({"message": message}), 400


@auth_bp.route('/forgot-password/reset', methods=['POST'])
def reset_password():
    """Reset password after OTP verification"""
    data = request.get_json()
    email = sanitize_input(data.get("email", "")).lower()
    new_password = data.get("password", "")
    
    if not email or not new_password:
        return jsonify({"message": "Email and new password are required"}), 400
    
    # Validate password
    is_valid, password_msg = validate_password(new_password)
    if not is_valid:
        return jsonify({"message": password_msg}), 400
    
    hashed = generate_password_hash(new_password)
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            return jsonify({"message": "User not found"}), 404
        
        user.password_hash = hashed
        db.commit()
        
        return jsonify({"message": "Password reset successful"}), 200
        
    except Exception as e:
        db.rollback()
        print(f"Password reset error: {e}")
        return jsonify({"message": "Failed to reset password"}), 500
    finally:
        db.close()


@auth_bp.route('/check-email', methods=['POST'])
def check_email():
    """Check if email exists"""
    email = sanitize_input(request.json.get("email", "")).lower()
    
    if not email:
        return jsonify({"exists": False, "message": "Email is required"}), 400
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        return jsonify({"exists": bool(user)}), 200
    except Exception as e:
        print(f"Check email error: {e}")
        return jsonify({"exists": False, "error": "Server error"}), 500
    finally:
        db.close()