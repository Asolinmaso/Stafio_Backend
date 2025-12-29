# app.py

print("----- Flask Application is starting from THIS file! -----")

from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, datetime
from functools import wraps
import os
import sys
import jwt
import requests
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import timedelta
from sqlalchemy.exc import IntegrityError
from database import (
    SessionLocal, User, OTP, init_db,
    get_db
)

# Create a Flask application instance
app = Flask(__name__)

# ============================================================
# SIMPLE CORS HANDLING - ONE FUNCTION, ALWAYS WORKS
# ============================================================
@app.after_request
def add_cors_headers(response):
    """Add CORS headers to ALL responses - SIMPLE & CLEAN"""
    origin = request.headers.get('Origin', '*')

    # If origin is specified, use it. Otherwise allow all.
    if origin and origin != '*':
        response.headers['Access-Control-Allow-Origin'] = origin
        # Allow credentials when origin is specific (not wildcard)
        response.headers['Access-Control-Allow-Credentials'] = 'true'
    else:
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Credentials'] = 'false'

    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-User-Role, X-User-ID'
    return response

@app.before_request
def handle_options():
    """Handle OPTIONS preflight requests"""
    if request.method == 'OPTIONS':
        response = jsonify({})
        origin = request.headers.get('Origin')
        if origin:
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-User-Role, X-User-ID'
        return response, 200

app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Email configuration
EMAIL_USER = os.getenv('EMAIL_USER', 'asolinmaso22@gmail.com')
EMAIL_PASS = os.getenv('EMAIL_PASS', 'iqcg fkfy fuar habr')
EMAIL_FROM = os.getenv('EMAIL_FROM', 'example@example.com')
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
app.config['SESSION_COOKIE_SECURE'] = True

# Email sending function
def send_email(to_email, subject, body):
    """Send email using SMTP"""
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS.strip())
        server.sendmail(EMAIL_FROM, to_email, msg.as_string())
        server.quit()
        print(f"Email sent successfully to {to_email}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"Email authentication failed: {e}")
        return False
    except smtplib.SMTPException as e:
        print(f"SMTP error: {e}")
        return False
    except Exception as e:
        print(f"Email sending failed: {e}")
        return False


# Database tables will be initialized when app starts


# --- CUSTOM, TEMPORARY INSECURE DECORATORS ---
def custom_admin_required():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            if request.headers.get('X-User-Role') == 'admin':
                return fn(*args, **kwargs)
            else:
                return jsonify({"message": "Admin access required"}), 403
        return decorator
    return wrapper

def custom_user_required():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            user_id = request.headers.get('X-User-ID')
            if user_id:
                request.current_user_id = int(user_id)
                return fn(*args, **kwargs)
            else:
                return jsonify({"message": "Authentication required"}), 401
        return decorator
    return wrapper
# --- END TEMPORARY DECORATORS ---


# --- Basic Health Check Endpoints ---
@app.route('/')
def hello_world():
    return 'Hello, World! Welcome to Leave Management Backend!'

@app.route('/test_db_connection')
def test_db_connection():
    db = None
    try:
        db = SessionLocal()
        # Try a simple query
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        return jsonify({"message": "Database connection successful!", "status": "connected"})
    except Exception as e:
        return jsonify({"message": f"An error occurred: {str(e)}", "status": "error"}), 500
    finally:
        if db:
            db.close()


# --- User Authentication Endpoints (Updated with Role-Based Login) ---

@app.route('/register', methods=['POST'])
def register_user():
    """Register a new user"""
    data = request.get_json()

    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    phone = data.get('phone')            # ⭐ ADDED
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    role = data.get('role', 'employee')

    # Required field checks
    if not username or not password or not email:
        return jsonify({"message": "Username, password, and email are required."}), 400

    if not phone:
        return jsonify({"message": "Phone number is required."}), 400  # ⭐ ADDED

    hashed_password = generate_password_hash(password)

    db = None
    try:
        db = SessionLocal()

        new_user = User(
            username=username,
            password_hash=hashed_password,
            email=email,
            phone=phone,                   # ⭐ ADDED
            first_name=first_name,
            last_name=last_name,
            role=role
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return jsonify({
            "message": "User registered successfully!",
            "user_id": new_user.id
        }), 201

    except IntegrityError:
        db.rollback()
        return jsonify({"message": "Username or email or Phone number already exists. "}), 409

    except Exception as e:
        if db:
            db.rollback()
        return jsonify({"message": f"An unexpected error occurred: {str(e)}"}), 500

    finally:
        if db:
            db.close()



# ============================================================
# OTP ENDPOINTS - CLEAN & SIMPLE
# ============================================================
@app.route('/forgot_send_otp', methods=['POST'])
def forgot_send_otp():
    data = request.get_json() or {}
    email = data.get("email", "").strip()

    if not email:
        return jsonify({"message": "Email is required."}), 400

    db = SessionLocal()
    try:
        # Check if email exists
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return jsonify({"message": "Email not registered."}), 404

        # Generate OTP
        otp_code = "".join(secrets.choice("0123456789") for _ in range(4))
        expires_at = datetime.utcnow() + timedelta(minutes=10)

        new_otp = OTP(email=email, otp_code=otp_code, expires_at=expires_at)
        db.add(new_otp)
        db.commit()

        # Send OTP Email
        subject = "Your Password Reset OTP"
        body = f"""
        <h3>Your OTP Code is: <strong>{otp_code}</strong></h3>
        <p>This OTP expires in 10 minutes.</p>
        """

        send_email(email, subject, body)

        return jsonify({"message": "OTP sent successfully."}), 200

    except Exception as e:
        db.rollback()
        print("Error in forgot_send_otp:", str(e))
        return jsonify({"message": "Internal server error."}), 500

    finally:
        db.close()


@app.route('/forgot_verify_otp', methods=['POST'])
def forgot_verify_otp():
    data = request.get_json() or {}

    email = data.get("email")
    otp_code = data.get("otp")

    if not email or not otp_code:
        return jsonify({"message": "Email and OTP required."}), 400

    db = SessionLocal()
    try:
        otp_record = (
            db.query(OTP)
            .filter(
                OTP.email == email,
                OTP.otp_code == otp_code,
                OTP.is_used == 0,
                OTP.expires_at > datetime.utcnow(),
            )
            .first()
        )

        if not otp_record:
            return jsonify({"message": "Invalid or expired OTP."}), 400

        otp_record.is_used = 1
        db.commit()

        return jsonify({"message": "OTP verified successfully."}), 200

    except Exception as e:
        db.rollback()
        print("Error in forgot_verify_otp:", str(e))
        return jsonify({"message": "Internal server error."}), 500

    finally:
        db.close()




@app.route('/reset_password', methods=['POST'])
def reset_password():
    data = request.get_json() or {}
    email = data.get("email")
    new_password = data.get("password")

    if not email or not new_password:
        return jsonify({"message": "Email and password required."}), 400

    hashed = generate_password_hash(new_password)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()

        if not user:
            return jsonify({"message": "User not found."}), 404

        user.password_hash = hashed
        db.commit()

        return jsonify({"message": "Password reset successful."}), 200

    except Exception as e:
        db.rollback()
        print("Error in reset_password:", str(e))
        return jsonify({"message": "Internal server error."}), 500

    finally:
        db.close()


#this is the code of getting the user name for backend code 

@app.route('/users/<int:user_id>', methods=['GET'])
def get_user_details(user_id):
    db = None
    try:
        db = SessionLocal()
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            return jsonify({"message": "User not found"}), 404
        
        return jsonify({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role
        }), 200
    except Exception as e:
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500
    finally:
        if db:
            db.close()



@app.route("/admin_google_register", methods=["POST"])
def admin_google_register():
    data = request.get_json()
    email = data.get("email")
    username = data.get("username")
    role = data.get("role", "admin")

    if not email:
        return jsonify({"message": "Email is required"}), 400

    db = SessionLocal()

    try:
        # Check if user exists
        user = db.query(User).filter(User.email == email).first()

        if user:
            return jsonify({
                "exists": True,
                "message": "Email already registered. Please login instead."
            }), 200

        # Create a new admin user (Google user has no password)
        new_user = User(
            username=username,
            email=email,
            password_hash="",   # empty, since Google login
            role=role
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return jsonify({
            "message": "Google Registration Successful",
            "user_id": new_user.id,
            "username": username,
            "email": email,
            "role": role
        }), 200

    except Exception as e:
        db.rollback()
        return jsonify({"message": "Server error", "error": str(e)}), 500

    finally:
        db.close()


@app.route("/employee_google_register", methods=["POST"])
def employee_google_register():
    data = request.get_json()
    email = data.get("email")
    username = data.get("username")
    role = data.get("role", "employee")

    if not email:
        return jsonify({"message": "Email is required"}), 400

    db = SessionLocal()

    try:
        # Check if employee already exists
        user = db.query(User).filter(User.email == email).first()

        if user:
            return jsonify({
                "exists": True,
                "message": "Email already registered. Please login instead."
            }), 200

        # Create a new employee (Google user → no password)
        new_user = User(
            username=username,
            email=email,
            password_hash="",  # empty for Google signup
            role=role
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return jsonify({
            "message": "Google Registration Successful",
            "user_id": new_user.id,
            "username": username,
            "email": email,
            "role": role
        }), 200

    except Exception as e:
        db.rollback()
        return jsonify({"message": "Server error", "error": str(e)}), 500

    finally:
        db.close()


@app.route('/google_login', methods=['POST'])
def google_login():
    """Handle Google OAuth login"""
    data = request.get_json()
    id_token = data.get("id_token")  # Google ID Token from frontend
    requested_role = data.get("role", "employee")

    if not id_token:
        return jsonify({"message": "Missing id_token"}), 400

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
        return jsonify({"message": f"Error verifying token: {str(ex)}"}), 500

    email = token_info.get("email")
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
            return jsonify({
                "user_id": user.id,
                "username": user.username,
                "role": user.role
            }), 200

        # Create new user (Google user → no password)
        username_base = email.split("@")[0]
        username = username_base

        # Ensure username uniqueness
        i = 1
        while db.query(User).filter(User.username == username).first():
            username = f"{username_base}{i}"
            i += 1

        new_user = User(
            username=username,
            email=email,
            password_hash="",  # Google users do not have password
            first_name=given_name,
            last_name=family_name,
            role=requested_role
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return jsonify({
            "user_id": new_user.id,
            "username": new_user.username,
            "role": new_user.role
        }), 201

    except Exception as e:
        db.rollback()
        return jsonify({"message": f"Server error: {str(e)}"}), 500

    finally:
        db.close()


@app.route('/employee_login', methods=['POST'])
def employee_login():
    """Authenticate an employee user"""
    data = request.get_json()
    identifier = data.get('identifier') # Can be username or email
    password = data.get('password')

    if not identifier or not password:
        return jsonify({"message": "Username/Email and password are required."}), 400

    db = None
    try:
        db = SessionLocal()
        user = db.query(User).filter(
            (User.username == identifier) | (User.email == identifier),
            User.role == 'employee'
        ).first()

        if user and check_password_hash(user.password_hash, password):
            return jsonify(user_id=user.id, role=user.role, username=user.username), 200
        else:
            return jsonify({"message": "Invalid employee username/email or password."}), 401
    except Exception as e:
        print(f"ERROR: employee_login - An unexpected error occurred: {str(e)}")
        return jsonify({"message": f"An unexpected error occurred: {str(e)}"}), 500
    finally:
        if db:
            db.close()



@app.route('/admin_google_login', methods=['POST'])
def admin_google_login():
    """Handle Google OAuth admin login"""
    data = request.get_json()
    id_token = data.get("id_token")
    requested_role = data.get("role", "admin")

    if not id_token:
        return jsonify({"message": "Missing id_token"}), 400

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
        return jsonify({"message": f"Error verifying token: {str(ex)}"}), 500

    email = token_info.get("email")
    given_name = token_info.get("given_name", "")
    family_name = token_info.get("family_name", "")
    email_verified = str(token_info.get("email_verified")).lower() == "true"

    if not email or not email_verified:
        return jsonify({"message": "Google account email not verified"}), 400

    db = SessionLocal()

    try:
        # Check if admin exists
        user = db.query(User).filter(User.email == email).first()

        if user:
            return jsonify({
                "user_id": user.id,
                "username": user.username,
                "role": user.role,
                "email":user.email,
            }), 200
        
        if not user:
         return {
            "status": "error",
            "message": "This email is not present in the database"
        }

        # Create new admin
        username_base = email.split("@")[0]
        i = 1
        username = username_base

        while db.query(User).filter(User.username == username).first():
            username = f"{username_base}{i}"
            i += 1

        new_user = User(
            username=username,
            email=email,
            password_hash="",
            first_name=given_name,
            last_name=family_name,
            role=requested_role
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return jsonify({
            "user_id": new_user.id,
            "username": new_user.username,
            "role": new_user.role,
            "email": new_user.email
        }), 201

    except Exception as e:
        db.rollback()
        return jsonify({"message": f"Server error: {str(e)}"}), 500

    finally:
        db.close()



@app.route('/employee_google_login', methods=['POST'])
def employee_google_login():
    """Handle Google OAuth employee login"""
    data = request.get_json()
    id_token = data.get("id_token")

    if not id_token:
        return jsonify({"message": "Missing id_token"}), 400

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
        return jsonify({"message": f"Error verifying token: {str(ex)}"}), 500

    email = token_info.get("email")
    given_name = token_info.get("given_name", "")
    family_name = token_info.get("family_name", "")
    email_verified = str(token_info.get("email_verified")).lower() == "true"

    if not email or not email_verified:
        return jsonify({"message": "Google account email not verified"}), 400

    db = SessionLocal()

    try:
        # ⏳ Check if employee exists
        user = db.query(User).filter(
            User.email == email,
            User.role == "employee"
        ).first()

        if user:
            return jsonify({
                "user_id": user.id,
                "username": user.username,
                "role": user.role,
                "email": user.email,
            }), 200
        if not user:
          return {
            "status": "error",
            "message": "This email is not present in the database"
        }


        # 🆕 Create new employee
        username_base = email.split("@")[0]
        username = username_base
        i = 1

        # Ensure username is unique
        while db.query(User).filter(User.username == username).first():
            username = f"{username_base}{i}"
            i += 1

        new_user = User(
            username=username,
            email=email,
            password_hash="",       # Empty because Google login does not use passwords
            first_name=given_name,
            last_name=family_name,
            role="employee"
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return jsonify({
            "user_id": new_user.id,
            "username": new_user.username,
            "role": new_user.role,
            "email": new_user.email
        }), 201

    except Exception as e:
        db.rollback()
        return jsonify({"message": f"Server error: {str(e)}"}), 500

    finally:
        db.close()





@app.route('/admin_login', methods=['POST'])
def admin_login():
    """Authenticate an admin user"""
    data = request.get_json()
    identifier = data.get('identifier') # Can be username or email
    password = data.get('password')

    if not identifier or not password:
        return jsonify({"message": "Username/Email and password are required."}), 400

    db = None
    try:
        db = SessionLocal()
        user = db.query(User).filter(
            (User.username == identifier) | (User.email == identifier),
            User.role == 'admin'
        ).first()

        if user and check_password_hash(user.password_hash, password):
            return jsonify(user_id=user.id, role=user.role, username=user.username), 200
        else:
            return jsonify({"message": "Invalid admin username/email or password."}), 401
    except Exception as e:
        print(f"ERROR: admin_login - An unexpected error occurred: {str(e)}")
        return jsonify({"message": f"An unexpected error occurred: {str(e)}"}), 500
    finally:
        if db:
            db.close()

# --- PROTECTED ROUTE (NOW USES TEMPORARY DECORATOR) ---
@app.route('/protected', methods=['GET'])
@custom_user_required()
def protected():
    user_id = request.headers.get('X-User-ID')
    return jsonify(logged_in_as={'id': user_id, 'message': 'You have accessed a protected route with a custom header'}), 200
# --- END PROTECTED ROUTE ---


#employee dashboard datas

@app.route('/dashboard', methods=['GET'])
def get_dashboard_data():
    # Mock data (you can adjust these values anytime)
    dashboard_data = {
        "total_leaves": 15,
        "leaves_taken": 7,
        "absent_days": 3,
        "worked_days": 24,
        "completed_projects": 2,
        "this_week_holiday": 1
    }
    return jsonify(dashboard_data), 200


#admin dasboard datas

@app.route('/admin_dashboard', methods=['GET'])
def get_admin_dashboard_data():
    # Mock data (you can adjust these values anytime)
    admin_dashboard_data = {
        "total_employees": 150,
        "On_Time": 110,
        "On_Leave": 20,
        "Late_Arrival": 20,
        "Pending_Approval": 2,
        "This_Week_Hoilday":1
    }
    return jsonify(admin_dashboard_data), 200


@app.route('/check_email', methods=['POST'])
def check_email():
    """Check if email exists in database"""
    email = request.json.get("email")

    db = None
    try:
        db = SessionLocal()
        user = db.query(User).filter(User.email == email).first()
        return jsonify({"exists": bool(user)})
    except Exception as e:
        return jsonify({"exists": False, "error": str(e)}), 500
    finally:
        if db:
            db.close()


@app.route('/update_password', methods=['POST'])
def update_password():
    """Update user password"""
    data = request.json
    email = data["email"]
    new_password = generate_password_hash(data["newPassword"])

    db = None
    try:
        db = SessionLocal()
        user = db.query(User).filter(User.email == email).first()

        if not user:
            return jsonify({"message": "Email not found"}), 400

        user.password_hash = new_password
        db.commit()
        return jsonify({"message": "Password updated successfully"}), 200
    except Exception as e:
        if db:
            db.rollback()
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500
    finally:
        if db:
            db.close()




@app.route('/api/myleave', methods=['GET'])
def get_leave_data():
    leave_data = [
        {
            "id": 1,
            "type": "Sick Leave 1 Day(s)",
            "date": "11-07-2025/Full Day",
            "reason": "Hospital Case",
            "requestDate": "11-07-2025",
            "status": "Approved",
        },
        {
            "id": 2,
            "type": "Sick Leave 0.5 Day(s)",
            "date": "11-07-2025/Half Day(AN)",
            "reason": "Hospital Case",
            "requestDate": "11-07-2025",
            "status": "Approved",
        },
        {
            "id": 3,
            "type": "Casual Leave 1 Day(s)",
            "date": "11-07-2025/Full Day",
            "reason": "Family Function",
            "requestDate": "11-07-2025",
            "status": "Approved",
        },
        {
            "id": 4,
            "type": "Casual Leave 3 Day(s)",
            "date": "11-07-2025/Full Day",
            "reason": "Health Issues",
            "requestDate": "11-07-2025",
            "status": "Approved",
        },
        {
            "id": 5,
            "type": "Sick Leave 1 Day(s)",
            "date": "11-07-2025/Full Day",
            "reason": "Fever",
            "requestDate": "11-07-2025",
            "status": "Approved",
        },
    ]
    return jsonify(leave_data)


@app.route('/api/myregularization', methods=['GET'])
def get_regularization_data():
    regularization_data = [
        {
            "id": 1,
            "attendanceType": "Present",
            "date": "11-07-2025/Full Day",
            "reason": "Forgot Clock Out",
            "status": "Pending",
        },
        {
            "id": 2,
            "attendanceType": "Present",
            "date": "11-07-2025/Half Day(AN)",
            "reason": "Forgot Clock In",
            "status": "Approved",
        },
        {
            "id": 3,
            "attendanceType": "Present",
            "date": "11-07-2025/Full Day",
            "reason": "Forgot Clock Out",
            "status": "Approved",
        },
        {
            "id": 4,
            "attendanceType": "Present",
            "date": "11-07-2025/Full Day",
            "reason": "Forgot Clock Out",
            "status": "Approved",
        },
        {
            "id": 5,
            "attendanceType": "Present",
            "date": "11-07-2025/Full Day",
            "reason": "Forgot Clock Out",
            "status": "Approved",
        },
    ]
    return jsonify(regularization_data)


@app.route('/api/myholidays', methods=['GET'])
def get_holidays():
    holiday_data = [
        {"id": 1, "date": "01 January, Wednesday", "title": "New Year's Day"},
        {"id": 2, "date": "26 January, Sunday", "title": "Republic Day"},
        {"id": 3, "date": "18 April, Friday", "title": "Good Friday"},
        {"id": 4, "date": "21 April, Monday", "title": "Easter Monday"},
        {"id": 5, "date": "06 July, Sunday", "title": "Muharram"},
        {"id": 6, "date": "15 August, Friday", "title": "Independence Day"},
        {"id": 7, "date": "20 October, Monday", "title": "Diwali"},
    ]
    return jsonify(holiday_data)

@app.route('/api/attendance', methods=['GET'])
def get_attendance_data():
    attendance_data = [
        {
            "date": "2025-07-28",
            "status": "On Time",
            "checkIn": "09:00",
            "checkOut": "18:00",
            "late": "-",
            "overtime": "-",
            "workHours": "10h 2m"
        },
        {
            "date": "2025-07-27",
            "status": "Absent",
            "checkIn": "00:00",
            "checkOut": "00:00",
            "late": "-",
            "overtime": "-",
            "workHours": "0h 0m"
        },
        {
            "date": "2025-07-26",
            "status": "Late Login",
            "checkIn": "10:30",
            "checkOut": "18:00",
            "late": "05 Min",
            "overtime": "15 Min",
            "workHours": "07h 44m"
        }
    ]
    return jsonify(attendance_data)


#now for admin page datas

#data for employee list page in ogranization page of the admin section

@app.route('/api/employeeslist', methods=['GET'])
def get_employees_data():
    employeesData = [
        {
            "id": 1,
            "name": "Aarav Bijeesh",
            "email": "aarav@gmail.com",
            "empId": "100849",
            "position": "UIUX",
            "department": "Development",
            "status": "Active",
            "image": "https://i.pravatar.cc/40?img=1",
        },
        {
            "id": 2,
            "name": "Aiswarya Shyam",
            "email": "aiswarya@gmail.com",
            "empId": "100849",
            "position": "Developer",
            "department": "Design",
            "status": "Active",
            "image": "https://i.pravatar.cc/40?img=2",
        },
        {
            "id": 3,
            "name": "Sakshi",
            "email": "sakshi@gmail.com",
            "empId": "100849",
            "position": "Designer",
            "department": "Design",
            "status": "Active",
            "image": "https://i.pravatar.cc/40?img=3",
        },
        {
            "id": 4,
            "name": "Ignatious Anto",
            "email": "ignatious@gmail.com",
            "empId": "100849",
            "position": "Designer",
            "department": "Development",
            "status": "Active",
            "image": "https://i.pravatar.cc/40?img=4",
        },
        {
            "id": 5,
            "name": "Lakshmi",
            "email": "lakshmi@gmail.com",
            "empId": "100849",
            "position": "Developer",
            "department": "Human Resource",
            "status": "Active",
            "image": "https://i.pravatar.cc/40?img=5",
        },
        {
            "id": 6,
            "name": "Akshaya",
            "email": "akshaya@gmail.com",
            "empId": "100849",
            "position": "UIUX",
            "department": "Development",
            "status": "Active",
            "image": "https://i.pravatar.cc/40?img=6",
        },
        {
            "id": 7,
            "name": "Shalom",
            "email": "shalom@gmail.com",
            "empId": "100849",
            "position": "UIUX",
            "department": "Design",
            "status": "Active",
            "image": "https://i.pravatar.cc/40?img=7",
        },
    ]
    return jsonify(employeesData)


# datas for attendance page in admin section
@app.route('/api/attendancelist', methods=['GET'])
def get_admin_attendance_data():
    attendance_data = [
        { 
            "id": "2244", 
            "employee": "Akshya", 
            "role": "UI UX", 
            "status": "On Time", 
            "date": "10 Aug 2025", 
            "checkIn": "09:00", 
            "checkOut": "18:00", 
            "workHours": "10h 2m" 
        },
        { 
            "id": "2244", 
            "employee": "Rhugmini", 
            "role": "UI UX", 
            "status": "Absent", 
            "date": "10 Aug 2025", 
            "checkIn": "00:00", 
            "checkOut": "00:00", 
            "workHours": "0h 0m" 
        },
        { 
            "id": "2244", 
            "employee": "Shalom", 
            "role": "UI UX", 
            "status": "On Time", 
            "date": "10 Aug 2025", 
            "checkIn": "09:00", 
            "checkOut": "18:00", 
            "workHours": "10h 2m" 
        },
        { 
            "id": "2244", 
            "employee": "Tamil", 
            "role": "UI UX", 
            "status": "Late Login", 
            "date": "10 Aug 2025", 
            "checkIn": "10:30", 
            "checkOut": "18:00", 
            "workHours": "07h 44m" 
        },
        { 
            "id": "2244", 
            "employee": "Lakshmi", 
            "role": "UI UX", 
            "status": "On Time", 
            "date": "10 Aug 2025", 
            "checkIn": "09:00", 
            "checkOut": "18:00", 
            "workHours": "10h 2m" 
        }
    ]
    return jsonify(attendance_data)


@app.route('/api/leaveapproval', methods=['GET'])
def get_admin_leave_approval_data():
    leave_approval_data = [
        {
      "name": "Aarav Bijeesh",
      "id": "100849",
      "type": "Sick Leave",
      "from": "11-07-2025",
       "to": "12-07-2025",
      "days": "1 Day(s)",
       "session": "Full Day",
      "dates": "11-07-2025/Full Day",
      "requestDate": "11-07-2025",
       "notify": "HR Head",
       "document": "medical_report.pdf",
       "reason": "Medical emergency",
      "status": "Pending",
        },
        {
      "name": "Aishwarya Shayam",
      "id": "100849",
      "type": "Sick Leave",
      "from": "11-07-2025",
       "to": "11-07-2025",
      "days": "0.5 Day(s)",
       "session": "Half day(AN)",
      "dates": "11-07-2025/Full Day",
      "requestDate": "11-07-2025",
       "notify": "HR Head",
       "document": "medical_report.pdf",
       "reason": "Medical emergency",
      "status": "Pending", 
        },
        {
      "name": "Sakshi",
      "id": "100849",
      "type": "Casual Leave",
      "from": "11-07-2025",
       "to": "11-07-2025",
      "days": "1 Day(s)",
       "session": "Full Day",
      "dates": "11-07-2025/Full Day",
      "requestDate": "11-07-2025",
       "notify": "HR Head",
       "document": "medical_report.pdf",
       "reason": "Medical emergency",
      "status": "Approved",
        },
    {
        "name": "Aarav Bijeesh",
      "id": "100849",
      "type": "Casual Leave",
      "from": "11-07-2025",
       "to": "13-07-2025",
      "days": "1 Day(s)",
       "session": "Full Day",
      "dates": "13-07-2025/Full Day",
      "requestDate": "11-07-2025",
       "notify": "HR Head",
       "document": "medical_report.pdf",
       "reason": "Medical emergency",
      "status": "Approved",
    },
    {
     "name": "Aarav Bijeesh",
      "id": "100849",
      "type": "Sick Leave",
      "from": "11-07-2025",
       "to": "11-07-2025",
      "days": "1 Day(s)",
       "session": "Full Day",
      "dates": "11-07-2025/Full Day",
      "requestDate": "11-07-2025",
       "notify": "HR Head",
       "document": "medical_report.pdf",
       "reason": "Medical emergency",
      "status": "Rejected",
    },
    ]
    return jsonify(leave_approval_data)


@app.route('/api/leavepolicies', methods=['GET'])
def get_admin_leave_policies():
    leave_policies= [
    { "name": "Casual Leave", "createdOn": "14 Apr 2025", "type": "All" },
    { "name": "Sick Leave", "createdOn": "06 Apr 2025", "type": "All" },
    { "name": "Maternity", "createdOn": "27 Mar 2025", "type": "Specific" },
    { "name": "Paternity", "createdOn": "20 Mar 2025", "type": "Specific" },
    { "name": "Annual Leave", "createdOn": "16 Mar 2025", "type": "All" },
    { "name": "Sabbatical Leave", "createdOn": "16 Mar 2025", "type": "All" },
    { "name": "Medical Leave", "createdOn": "16 Mar 2025", "type": "All" },
]
    return jsonify(leave_policies)




@app.route('/api/myteamla', methods = ['GET'])
def get_my_team_la():
    my_team_la = [
        {
      "id": 1,
       "name": "Sakshi",
      "empId": "100849",
      "type": "Sick Leave",
      "from": "11-07-2025",
       "to": "11-07-2025",
      "days": "1 Day(s)",
       "session": "Full Day",
      "date": "11-07-2025/Full Day",
      "request": "11-07-2025",
       "notify": "HR Head",
       "document": "medical_report.pdf",
       "reason": "Medical emergency",
      "status": "Pending",
       "image": "https://i.pravatar.cc/40?img=4"
    },
    {
      "id": 2,
       "name": "Asolin",
      "empId": "100849",
      "type": "Sick Leave",
      "from": "11-07-2025",
       "to": "11-07-2025",
      "days": "0.5 Day(s)",
       "session": "Full Day",
      "date": "11-07-2025/Half Day",
      "request": "11-07-2025",
       "notify": "HR Head",
       "document": "medical_report.pdf",
       "reason": "Medical emergency",
      "status": "Pending",
       "image": "https://i.pravatar.cc/40?img=4"
    },
    {
      "id": 3,
       "name": "Sakshi",
      "empId": "100849",
      "type": "Casual Leave",
      "from": "11-07-2025",
       "to": "11-07-2025",
      "days": "1 Day(s)",
       "session": "Full Day",
      "date": "11-07-2025/Full Day",
      "request": "11-07-2025",
       "notify": "HR Head",
       "document": "medical_report.pdf",
       "reason": "Medical emergency",
      "status": "Approved",
       "image": "https://i.pravatar.cc/40?img=4"
    },
    {
      "id": 4,
      "name": "Asolin",
      "empId": "100849",
      "type": "Casual Leave",
      "from": "11-07-2025",
       "to": "11-07-2025",
      "days": "1 Day(s)",
       "session": "Full Day",
      "date": "11-07-2025/Full Day",
      "request": "11-07-2025",
       "notify": "HR Head",
       "document": "medical_report.pdf",
       "reason": "Medical emergency",
      "status": "Approved",
       "image": "https://i.pravatar.cc/40?img=4"
    },
    {
      "id": 5,
      "name": "Sakshi",
      "empId": "100849",
      "type": "Sick Leave",
      "from": "11-07-2025",
       "to": "11-07-2025",
      "days": "1 Day(s)",
       "session": "Full Day",
      "date": "11-07-2025/Full Day",
      "request": "11-07-2025",
       "notify": "HR Head",
       "document": "medical_report.pdf",
       "reason": "Medical emergency",
      "status": "Rejected",
       "image": "https://i.pravatar.cc/40?img=4"
    } 
    ]
    return jsonify(my_team_la)


@app.route('/api/myteamra' ,methods = ['GET'])
def get_myteam_ra():
    my_team_ra = [
         {
      "id": 1,
      "name": "Sakshi",
      "empId": "100849",
      "regDate": "11-07-2025/1st Half",
      "attendance": "Present",
      "requestDate": "11-07-2025",
      "status": "Pending",
      "img": "https://randomuser.me/api/portraits/women/13.jpg",
    },
    {
      "id": 2,
      "name": "Asolin",
      "empId": "100849",
      "regDate": "11-07-2025/1st Half",
      "attendance": "Present",
      "requestDate": "11-07-2025",
      "status": "Approved",
      "img": "https://randomuser.me/api/portraits/women/12.jpg",
    },
    {
      "id": 3,
      "name": "Sakshi",
      "empId": "100849",
      "regDate": "11-07-2025/1st Half",
      "attendance": "Present",
      "requestDate": "11-07-2025",
      "status": "Approved",
      "img": "https://randomuser.me/api/portraits/women/13.jpg",
    },
    {
      "id": 4,
      "name": "Asolin",
      "empId": "100849",
      "regDate": "11-07-2025/Full Day",
      "attendance": "Present",
      "requestDate": "11-07-2025",
      "status": "Approved",
      "img": "https://randomuser.me/api/portraits/women/12.jpg",
    }
    ]
    return jsonify(my_team_ra)


@app.route('/api/regularizationapproval',methods =['GET'])
def get_regularization_approval():
    regularization_approval = [
         {
      "id": 1,
      "name": "Aarav Bijeesh",
      "empId": "100849",
      "regDate": "11-07-2025/1st Half",
      "attendance": "Present",
      "requestDate": "11-07-2025",
      "status": "Pending",
      "img": "https://randomuser.me/api/portraits/men/11.jpg",
    },
    {
      "id": 2,
      "name": "Aiswarya Shyam",
      "empId": "100849",
      "regDate": "11-07-2025/1st Half",
      "attendance": "Present",
      "requestDate": "11-07-2025",
      "status": "Approved",
      "img": "https://randomuser.me/api/portraits/women/12.jpg",
    },
    {
      "id": 3,
      "name": "Sakshi",
      "empId": "100849",
      "regDate": "11-07-2025/1st Half",
      "attendance": "Present",
      "requestDate": "11-07-2025",
      "status": "Approved",
      "img": "https://randomuser.me/api/portraits/women/13.jpg",
    },
    {
      "id": 4,
      "name": "Ignatious Anto",
      "empId": "100849",
      "regDate": "11-07-2025/Full Day",
      "attendance": "Present",
      "requestDate": "11-07-2025",
      "status": "Approved",
      "img": "https://randomuser.me/api/portraits/men/15.jpg",
    },
    {
      "id": 5,
      "name": "Lakshmi",
      "empId": "100849",
      "regDate": "11-07-2025/Full Day",
      "attendance": "Present",
      "requestDate": "11-07-2025",
      "status": "Approved",
      "img": "https://randomuser.me/api/portraits/women/16.jpg",
    }
    ]
    return jsonify(regularization_approval)


#Mansoor code added 

# --- Admin Profile Endpoint ---
@app.route('/admin_profile/<int:user_id>', methods=['GET'])
@custom_admin_required()
def get_admin_profile_data(user_id):
    """
    Returns admin profile data for the specified user from database.
    """
    db = None
    try:
        db = SessionLocal()
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            return jsonify({"message": "User not found"}), 404
        
        # Return only data from database, empty strings for fields not in database
        admin_profile_data = {
            "profile": {
                "profileImage": "",
                "name": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
                "gender": "",
                "dob": "",
                "maritalStatus": "",
                "nationality": "",
                "bloodGroup": "",
                "email": user.email or "",
                "phone": "",
                "address": "",
                "emergencyContactNumber": "",
                "relationship": "",
                "empType": "",
                "department": "",
                "location": "",
                "supervisor": "",
                "hrManager": "",
                "empId": str(user.id) if user.id else "",
                "status": ""
            },
            "education": {
                "institution": "",
                "location": "",
                "startDate": "",
                "endDate": "",
                "qualification": "",
                "specialization": "",
                "skills": [],
                "portfolio": ""
            },
            "experience": {
                "company": "",
                "jobTitle": "",
                "startDate": "",
                "endDate": "",
                "responsibilities": "",
                "totalYears": ""
            },
            "bank": {
                "bankName": "",
                "branch": "",
                "accountNumber": "",
                "ifsc": "",
                "aadhaar": "",
                "pan": ""
            },
            "documents": []
        }
        
        return jsonify(admin_profile_data), 200
    except Exception as e:
        if db:
            db.rollback()
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500
    finally:
        if db:
            db.close()


# --- Employee Profile Endpoint ---
@app.route('/employee_profile/<int:user_id>', methods=['GET'])
@custom_user_required()
def get_employee_profile_data(user_id):
    """
    Returns employee profile data for the specified user from database.
    """
    # Check if the requesting user is accessing their own profile
    current_user_id = request.current_user_id
    if current_user_id != user_id and request.headers.get('X-User-Role') != 'admin':
        return jsonify({"message": "Unauthorized to view this profile."}), 403
    
    db = None
    try:
        db = SessionLocal()
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            return jsonify({"message": "User not found"}), 404
        
        # Return only data from database, empty strings for fields not in database
        employee_profile_data = {
            "profile": {
                "profileImage": "",
                "name": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
                "gender": "",
                "dob": "",
                "maritalStatus": "",
                "nationality": "",
                "bloodGroup": "",
                "email": user.email or "",
                "phone": "",
                "address": "",
                "emergencyContactNumber": "",
                "relationship": "",
                "empType": "",
                "department": "",
                "location": "",
                "supervisor": "",
                "hrManager": "",
                "empId": str(user.id) if user.id else "",
                "status": ""
            },
            "education": {
                "institution": "",
                "location": "",
                "startDate": "",
                "endDate": "",
                "qualification": "",
                "specialization": "",
                "skills": [],
                "portfolio": ""
            },
            "experience": {
                "company": "",
                "jobTitle": "",
                "startDate": "",
                "endDate": "",
                "responsibilities": "",
                "totalYears": ""
            },
            "bank": {
                "bankName": "",
                "branch": "",
                "accountNumber": "",
                "ifsc": "",
                "aadhaar": "",
                "pan": ""
            },
            "documents": []
        }
        
        return jsonify(employee_profile_data), 200
    except Exception as e:
        if db:
            db.rollback()
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500
    finally:
        if db:
            db.close()


@app.route('/pyver')
def pyver():
    return sys.version


# Run the Flask application
if __name__ == '__main__':
    # Print startup info
    print("\n" + "="*60)
    print("Stafio Backend Server Starting")
    print("CORS: Enabled for all origins")
    print("="*60 + "\n")
    
    # Initialize database tables (creates tables if they don't exist)
    try:
        init_db()
        print("Database tables initialized successfully!")
    except Exception as e:
        print(f"Warning: Could not initialize database tables: {e}")
        print("Make sure PostgreSQL is running and databases are created.")
    
    # Run migrations (upgrade to latest)
    try:
        from run_migrations import run_migrations
        run_migrations()
    except Exception as e:
        print(f"Warning: Could not run migrations: {e}")
        print("You may need to run migrations manually: python run_migrations.py")
    
    print("\nStarting Flask server on http://localhost:5001")
    print("CORS is enabled for all endpoints\n")
    app.run(debug=True, host='0.0.0.0', port=5001)
