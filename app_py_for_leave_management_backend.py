# app.py

print("----- Flask Application is starting from THIS file! -----")

from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, datetime, timedelta
from functools import wraps
import os
import sys
import jwt
import requests
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, extract
from database import (
    SessionLocal, User, OTP, init_db, get_db,
    LeaveType, LeaveBalance, LeaveRequest,
    EmployeeProfile, Attendance, Regularization,
    Holiday, Department, TeamMember,
    # New modules
    SalaryStructure, Payroll, Task, PerformanceReview,
    Document, SystemSettings, Notification, Broadcast
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

@app.route('/admin_dashboard')
def admin_dashboard():
    """Get admin dashboard statistics"""
    db = SessionLocal()
    try:
        today = datetime.now().date()
        
        # Total employees
        total_employees = db.query(User).filter(User.role == 'employee').count()
        
        # On Time today (attendance with 'On Time' status)
        on_time = db.query(Attendance).filter(
            Attendance.date == today,
            Attendance.status == 'On Time'
        ).count()
        
        # On Leave today - employees with approved leave that includes today's date
        on_leave = db.query(LeaveRequest).filter(
            LeaveRequest.status == 'approved',
            LeaveRequest.start_date <= today,
            LeaveRequest.end_date >= today
        ).count()
        
        # Late Arrival today
        late_arrival = db.query(Attendance).filter(
            Attendance.date == today,
            Attendance.status == 'Late'
        ).count()
        
        # Pending Approval - leave requests with pending status
        pending_approval = db.query(LeaveRequest).filter(
            LeaveRequest.status == 'pending'
        ).count()
        
        # This week holiday (placeholder - would need holiday table)
        this_week_holiday = 0
        
        return jsonify({
            "total_employees": total_employees,
            "On_Time": on_time,
            "On_Leave": on_leave,
            "Late_Arrival": late_arrival,
            "Pending_Approval": pending_approval,
            "This_Week_Hoilday": this_week_holiday
        }), 200
        
    except Exception as e:
        print(f"Admin dashboard error: {str(e)}")
        return jsonify({
            "total_employees": 0,
            "On_Time": 0,
            "On_Leave": 0,
            "Late_Arrival": 0,
            "Pending_Approval": 0,
            "This_Week_Hoilday": 0
        }), 200
    finally:
        db.close()

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
    access_token = data.get("access_token")
    # requested_role = data.get("role", "admin")
    if not access_token:
        return jsonify({"message": "Missing  access_token"}), 400

    # Verify Google Token
    try:
        r = requests.get(
       "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={
        "Authorization": f"Bearer {access_token}"
        },
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
    email_verified = token_info.get("email_verified", True)

    if not email or not email_verified:
        return jsonify({"message": "Google account email not verified"}), 400

    db = SessionLocal()

    try:
        # Check if admin exists
        user = db.query(User).filter(
            User.email == email,
            User.role == "admin"
            ).first()
        if not user:
            return jsonify({
                "status": "error",
                "message": "This email is not present in the database"
            }), 403
        
        return jsonify({
            "user_id": user.id,
            "username": user.username,
            "role": user.role,
            "email": user.email
        }), 200
    

    except Exception as e:
        db.rollback()
        return jsonify({"message": f"Server error: {str(e)}"}), 500

    finally:
        db.close()



@app.route('/employee_google_login', methods=['POST'])
def employee_google_login():
    """Handle Google OAuth employee login"""
    data = request.get_json()
    access_token = data.get("access_token")
    
    if not access_token:
        return jsonify({"message": "Missing access_token"}), 400
    

    # Verify Google Token
    try:
        r = requests.get(
       "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={
        "Authorization": f"Bearer {access_token}"
        },
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
    email_verified = token_info.get("email_verified", True)

    if not email or not email_verified:
        return jsonify({"message": "Google account email not verified"}), 400

    db = SessionLocal()

    try:
        # ⏳ Check if employee exists
        user = db.query(User).filter(
            User.email == email,
            User.role == "employee"
        ).first()

        # EXISTING EMPLOYEE
        if user:
            return jsonify({
                "user_id": user.id,
                "username": user.username,
                "role": user.role,
                "email": user.email,
            }), 200

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
    """Get employee dashboard data from database"""
    user_id = request.headers.get('X-User-ID')
    
    db = SessionLocal()
    try:
        current_year = datetime.now().year
        today = date.today()
        
        # Total leaves (sum of all leave balances for the year)
        total_leaves_result = db.query(func.sum(LeaveBalance.balance)).filter(
            LeaveBalance.user_id == user_id,
            LeaveBalance.year == current_year
        ).scalar()
        total_leaves = float(total_leaves_result) if total_leaves_result else 15  # Default 15 if no balance set
        
        # Leaves taken (approved leave requests this year)
        leaves_taken_result = db.query(func.sum(LeaveRequest.num_days)).filter(
            LeaveRequest.user_id == user_id,
            LeaveRequest.status == 'approved',
            extract('year', LeaveRequest.start_date) == current_year
        ).scalar()
        leaves_taken = int(leaves_taken_result) if leaves_taken_result else 0
        
        # Absent days from attendance
        absent_days = db.query(func.count(Attendance.id)).filter(
            Attendance.user_id == user_id,
            Attendance.status == 'Absent',
            extract('year', Attendance.date) == current_year
        ).scalar() or 0
        
        # Worked days
        worked_days = db.query(func.count(Attendance.id)).filter(
            Attendance.user_id == user_id,
            Attendance.status.in_(['On Time', 'Late Login']),
            extract('year', Attendance.date) == current_year
        ).scalar() or 0
        
        # This week holiday
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        
        this_week_holidays = db.query(func.count(Holiday.id)).filter(
            Holiday.date >= week_start,
            Holiday.date <= week_end
        ).scalar() or 0
        
        dashboard_data = {
            "total_leaves": total_leaves,
            "leaves_taken": leaves_taken,
            "absent_days": absent_days,
            "worked_days": worked_days,
            "completed_projects": 0,
            "this_week_holiday": this_week_holidays
        }
        
        return jsonify(dashboard_data), 200
        
    except Exception as e:
        print(f"Dashboard error: {str(e)}")
        # Return default values on error
        return jsonify({
            "total_leaves": 15,
            "leaves_taken": 0,
            "absent_days": 0,
            "worked_days": 0,
            "completed_projects": 0,
            "this_week_holiday": 0
        }), 200
    finally:
        db.close()


#admin dasboard datas

@app.route('/admin_dashboard', methods=['GET'])
def get_admin_dashboard_data():
    """Get admin dashboard data from database"""
    db = SessionLocal()
    try:
        today = date.today()
        
        # Total employees
        total_employees = db.query(func.count(User.id)).filter(
            User.role == 'employee'
        ).scalar() or 0
        
        # Today's attendance counts
        on_time = db.query(func.count(Attendance.id)).filter(
            Attendance.date == today,
            Attendance.status == 'On Time'
        ).scalar() or 0
        
        on_leave = db.query(func.count(Attendance.id)).filter(
            Attendance.date == today,
            Attendance.status == 'On Leave'
        ).scalar() or 0
        
        late_arrival = db.query(func.count(Attendance.id)).filter(
            Attendance.date == today,
            Attendance.status == 'Late Login'
        ).scalar() or 0
        
        # Pending approvals
        pending_approvals = db.query(func.count(LeaveRequest.id)).filter(
            LeaveRequest.status == 'pending'
        ).scalar() or 0
        
        # This week holidays
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        
        this_week_holidays = db.query(func.count(Holiday.id)).filter(
            Holiday.date >= week_start,
            Holiday.date <= week_end
        ).scalar() or 0
        
        return jsonify({
            "total_employees": total_employees,
            "On_Time": on_time,
            "On_Leave": on_leave,
            "Late_Arrival": late_arrival,
            "Pending_Approval": pending_approvals,
            "This_Week_Hoilday": this_week_holidays
        }), 200
        
    except Exception as e:
        print(f"Admin dashboard error: {str(e)}")
        return jsonify({
            "total_employees": 0,
            "On_Time": 0,
            "On_Leave": 0,
            "Late_Arrival": 0,
            "Pending_Approval": 0,
            "This_Week_Hoilday": 0
        }), 200
    finally:
        db.close()


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


# =============================================================================
# LEAVE MANAGEMENT ENDPOINTS
# =============================================================================

# Create Leave Request (POST)
@app.route('/leave_requests', methods=['POST'])
def create_leave_request():
    """Create a new leave request"""
    data = request.get_json()
    user_id = data.get('user_id')
    leave_type_id = data.get('leave_type_id')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    num_days = data.get('num_days')
    reason = data.get('reason')
    
    # Debug logging
    print(f"Leave request data: user_id={user_id}, leave_type_id={leave_type_id}, start_date={start_date}, end_date={end_date}, num_days={num_days}")
    
    # Better validation with specific error messages
    missing_fields = []
    if not user_id:
        missing_fields.append('user_id')
    if not leave_type_id:
        missing_fields.append('leave_type_id')
    if not start_date:
        missing_fields.append('start_date')
    if not end_date:
        missing_fields.append('end_date')
    if not num_days:
        missing_fields.append('num_days')
    
    if missing_fields:
        return jsonify({"message": f"Missing required fields: {', '.join(missing_fields)}"}), 400
    
    db = SessionLocal()
    try:
        # Convert to proper types
        user_id = int(user_id)
        leave_type_id = int(leave_type_id)
        num_days = int(num_days)
        
        # Check if leave type exists
        leave_type = db.query(LeaveType).filter(LeaveType.id == leave_type_id).first()
        if not leave_type:
            # Get available leave types for better error message
            available = db.query(LeaveType).all()
            if not available:
                return jsonify({"message": "No leave types configured. Please contact admin to add leave types first."}), 400
            else:
                type_names = ", ".join([f"{lt.id}: {lt.name}" for lt in available])
                return jsonify({"message": f"Invalid leave type ID. Available types: {type_names}"}), 400
        
        # Skip balance check for now (allow request even without balance set)
        # Create leave request
        new_request = LeaveRequest(
            user_id=user_id,
            leave_type_id=leave_type_id,
            start_date=datetime.strptime(start_date, '%Y-%m-%d').date(),
            end_date=datetime.strptime(end_date, '%Y-%m-%d').date(),
            num_days=num_days,
            reason=reason,
            status='pending'
        )
        
        db.add(new_request)
        db.commit()
        db.refresh(new_request)
        
        return jsonify({
            "message": "Leave request submitted successfully",
            "id": new_request.id
        }), 201
        
    except ValueError as e:
        return jsonify({"message": f"Invalid data format: {str(e)}"}), 400
    except Exception as e:
        db.rollback()
        print(f"Create leave request error: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


# Create Leave Type (POST) - Admin only
@app.route('/leave_types', methods=['POST'])
@custom_admin_required()
def create_leave_type():
    """Create a new leave type"""
    data = request.get_json()
    name = data.get('name')
    description = data.get('description', '')
    max_days = data.get('max_days_per_year')
    
    if not name or not max_days:
        return jsonify({"message": "Name and max_days_per_year are required"}), 400
    
    db = SessionLocal()
    try:
        # Check if leave type already exists
        existing = db.query(LeaveType).filter(LeaveType.name == name).first()
        if existing:
            return jsonify({"message": "Leave type already exists"}), 400
        
        new_type = LeaveType(
            name=name,
            description=description,
            max_days_per_year=max_days
        )
        
        db.add(new_type)
        db.commit()
        db.refresh(new_type)
        
        return jsonify({
            "message": "Leave type created successfully",
            "id": new_type.id
        }), 201
        
    except Exception as e:
        db.rollback()
        print(f"Create leave type error: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


# Get all leave types (for dropdown in apply leave form)
@app.route('/api/leave_types', methods=['GET'])
def get_leave_types():
    """Get all leave types"""
    db = SessionLocal()
    try:
        leave_types = db.query(LeaveType).all()
        
        result = []
        for lt in leave_types:
            result.append({
                "id": lt.id,
                "name": lt.name,
                "description": lt.description or "",
                "max_days_per_year": lt.max_days_per_year
            })
        
        return jsonify(result), 200
        
    except Exception as e:
        print(f"Get leave types error: {str(e)}")
        return jsonify([]), 200
    finally:
        db.close()


# =============================================================================
# LEAVE APPROVAL/REJECTION (PUT)
# =============================================================================

@app.route('/api/leave_requests/<int:request_id>/approve', methods=['PUT'])
def approve_leave_request(request_id):
    """Approve a leave request"""
    data = request.get_json() or {}
    reason = data.get('reason', '')
    
    db = SessionLocal()
    try:
        leave_request = db.query(LeaveRequest).filter(LeaveRequest.id == request_id).first()
        if not leave_request:
            return jsonify({"message": "Leave request not found"}), 404
        
        leave_request.status = 'approved'
        
        # Deduct from leave balance
        year = leave_request.start_date.year
        balance = db.query(LeaveBalance).filter(
            LeaveBalance.user_id == leave_request.user_id,
            LeaveBalance.leave_type_id == leave_request.leave_type_id,
            LeaveBalance.year == year
        ).first()
        
        if balance:
            balance.used = (balance.used or 0) + leave_request.num_days
            balance.balance = balance.balance - leave_request.num_days
        
        db.commit()
        
        return jsonify({"message": "Leave request approved successfully"}), 200
        
    except Exception as e:
        db.rollback()
        print(f"Approve leave error: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@app.route('/api/leave_requests/<int:request_id>/reject', methods=['PUT'])
def reject_leave_request(request_id):
    """Reject a leave request"""
    data = request.get_json() or {}
    reason = data.get('reason', '')
    
    db = SessionLocal()
    try:
        leave_request = db.query(LeaveRequest).filter(LeaveRequest.id == request_id).first()
        if not leave_request:
            return jsonify({"message": "Leave request not found"}), 404
        
        leave_request.status = 'rejected'
        db.commit()
        
        return jsonify({"message": "Leave request rejected"}), 200
        
    except Exception as e:
        db.rollback()
        print(f"Reject leave error: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


# =============================================================================
# LEAVE BALANCE ENDPOINT
# =============================================================================

@app.route('/api/leave_balance', methods=['GET'])
def get_leave_balance():
    """Get user's leave balance for all leave types"""
    user_id_str = request.headers.get('X-User-ID') or request.args.get('user_id')
    
    db = SessionLocal()
    try:
        if not user_id_str:
            return jsonify([]), 200
        
        # Convert to integer for proper database comparison
        user_id = int(user_id_str)
            
        leave_types = db.query(LeaveType).all()
        
        balances = []
        for lt in leave_types:
            # Calculate used days from approved leave requests (all time for this leave type)
            used_result = db.query(func.sum(LeaveRequest.num_days)).filter(
                LeaveRequest.user_id == user_id,
                LeaveRequest.leave_type_id == lt.id,
                LeaveRequest.status == 'approved'
            ).scalar()
            
            used = float(used_result) if used_result else 0
            total = float(lt.max_days_per_year)
            remaining = total - used
            
            balances.append({
                "id": lt.id,
                "name": lt.name,
                "used": used,
                "total": total,
                "remaining": remaining
            })
        
        return jsonify(balances), 200
        
    except Exception as e:
        print(f"Leave balance error: {str(e)}")
        return jsonify([]), 200
    finally:
        db.close()


# =============================================================================
# ATTENDANCE STATISTICS ENDPOINT
# =============================================================================

@app.route('/api/attendance_stats', methods=['GET'])
def get_attendance_stats():
    """Get user's attendance statistics"""
    user_id = request.headers.get('X-User-ID') or request.args.get('user_id')
    
    db = SessionLocal()
    try:
        # Get current month stats
        now = datetime.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Count working days (present)
        working_days = db.query(Attendance).filter(
            Attendance.user_id == user_id,
            Attendance.date >= start_of_month.date(),
            Attendance.status.in_(['present', 'On Time', 'Late'])
        ).count()
        
        # Count approved leaves
        total_leaves = db.query(LeaveRequest).filter(
            LeaveRequest.user_id == user_id,
            LeaveRequest.status == 'approved',
            LeaveRequest.start_date >= start_of_month.date()
        ).count()
        
        # Count late logins
        late_logins = db.query(Attendance).filter(
            Attendance.user_id == user_id,
            Attendance.date >= start_of_month.date(),
            Attendance.status == 'Late'
        ).count()
        
        # Count on-time logins
        on_time_logins = db.query(Attendance).filter(
            Attendance.user_id == user_id,
            Attendance.date >= start_of_month.date(),
            Attendance.status == 'On Time'
        ).count()
        
        return jsonify({
            "working_days": working_days or 0,
            "total_leaves": total_leaves or 0,
            "late_logins": late_logins or 0,
            "on_time_logins": on_time_logins or 0
        }), 200
        
    except Exception as e:
        print(f"Attendance stats error: {str(e)}")
        return jsonify({
            "working_days": 0,
            "total_leaves": 0,
            "late_logins": 0,
            "on_time_logins": 0
        }), 200
    finally:
        db.close()


@app.route('/api/who_is_on_leave', methods=['GET'])
def get_who_is_on_leave():
    """Get all approved leave requests for admin view"""
    db = SessionLocal()
    try:
        # Get all approved leave requests with user and leave type info
        requests_data = db.query(LeaveRequest, LeaveType, User).join(
            LeaveType, LeaveRequest.leave_type_id == LeaveType.id
        ).join(
            User, LeaveRequest.user_id == User.id
        ).filter(
            LeaveRequest.status == 'approved'
        ).order_by(LeaveRequest.start_date.desc()).all()
        
        leave_list = []
        for req, leave_type, user in requests_data:
            # Calculate number of days
            days_diff = (req.end_date - req.start_date).days + 1
            days_text = f"{days_diff} Day" if days_diff == 1 else f"{days_diff} Days"
            
            leave_list.append({
                "id": str(user.id),
                "employee": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
                "type": leave_type.name,
                "from": req.start_date.strftime('%d %b %Y'),
                "to": req.end_date.strftime('%d %b %Y'),
                "days": days_text,
                "status": req.status
            })
        
        return jsonify(leave_list), 200
        
    except Exception as e:
        print(f"Who is on leave error: {str(e)}")
        return jsonify([]), 200
    finally:
        db.close()


@app.route('/api/myleave', methods=['GET'])
def get_leave_data():
    """Get user's leave requests from database"""
    user_id = request.headers.get('X-User-ID')
    
    db = SessionLocal()
    try:
        # Join with LeaveType to get the leave type name
        requests_data = db.query(LeaveRequest, LeaveType).join(
            LeaveType, LeaveRequest.leave_type_id == LeaveType.id
        ).filter(
            LeaveRequest.user_id == user_id
        ).order_by(LeaveRequest.applied_date.desc()).all()
        
        leave_data = []
        for req, leave_type in requests_data:
            leave_data.append({
                "id": req.id,
                "type": f"{leave_type.name} {req.num_days} Day(s)",
                "date": f"{req.start_date.strftime('%d-%m-%Y')}/Full Day",
                "reason": req.reason or "",
                "requestDate": req.applied_date.strftime('%d-%m-%Y') if req.applied_date else "",
                "status": req.status.capitalize() if req.status else "Pending"
            })
        
        return jsonify(leave_data), 200
        
    except Exception as e:
        print(f"Leave data error: {str(e)}")
        return jsonify([]), 200
    finally:
        db.close()


@app.route('/api/myregularization', methods=['GET'])
def get_regularization_data():
    """Get user's regularization requests from database"""
    user_id = request.headers.get('X-User-ID')
    
    db = SessionLocal()
    try:
        requests_data = db.query(Regularization).filter(
            Regularization.user_id == user_id
        ).order_by(Regularization.request_date.desc()).all()
        
        regularization_data = []
        for req in requests_data:
            session_str = req.session_type or "Full Day"
            regularization_data.append({
                "id": req.id,
                "attendanceType": req.attendance_type or "Present",
                "date": f"{req.date.strftime('%d-%m-%Y')}/{session_str}",
                "reason": req.reason or "",
                "status": req.status.capitalize() if req.status else "Pending"
            })
        
        # If no data, return empty list (frontend handles empty state)
        return jsonify(regularization_data), 200
        
    except Exception as e:
        print(f"Regularization error: {str(e)}")
        return jsonify([]), 200
    finally:
        db.close()


@app.route('/api/myholidays', methods=['GET'])
def get_holidays():
    """Get holidays from database"""
    db = SessionLocal()
    try:
        current_year = datetime.now().year
        holidays = db.query(Holiday).filter(
            Holiday.year == current_year
        ).order_by(Holiday.date).all()
        
        holiday_data = []
        for h in holidays:
            # Format date like "01 January, Wednesday"
            date_str = h.date.strftime('%d %B, %A')
            holiday_data.append({
                "id": h.id,
                "date": date_str,
                "title": h.title
            })
        
        # If no holidays in DB, provide default list
        if not holiday_data:
            holiday_data = [
                {"id": 1, "date": "01 January, Wednesday", "title": "New Year's Day"},
                {"id": 2, "date": "26 January, Sunday", "title": "Republic Day"},
                {"id": 3, "date": "15 August, Friday", "title": "Independence Day"},
                {"id": 4, "date": "02 October, Thursday", "title": "Gandhi Jayanti"},
                {"id": 5, "date": "25 December, Thursday", "title": "Christmas Day"},
            ]
        
        return jsonify(holiday_data), 200
        
    except Exception as e:
        print(f"Holidays error: {str(e)}")
        return jsonify([]), 200
    finally:
        db.close()


@app.route('/api/attendance', methods=['GET'])
def get_attendance_data():
    """Get user's attendance data from database"""
    user_id = request.headers.get('X-User-ID')
    
    db = SessionLocal()
    try:
        attendance_records = db.query(Attendance).filter(
            Attendance.user_id == user_id
        ).order_by(Attendance.date.desc()).limit(30).all()
        
        attendance_data = []
        for att in attendance_records:
            check_in_str = att.check_in.strftime('%H:%M') if att.check_in else "00:00"
            check_out_str = att.check_out.strftime('%H:%M') if att.check_out else "00:00"
            late_str = f"{att.late_minutes} Min" if att.late_minutes and att.late_minutes > 0 else "-"
            overtime_str = f"{att.overtime_minutes} Min" if att.overtime_minutes and att.overtime_minutes > 0 else "-"
            
            attendance_data.append({
                "date": att.date.strftime('%Y-%m-%d'),
                "status": att.status or "Absent",
                "checkIn": check_in_str,
                "checkOut": check_out_str,
                "late": late_str,
                "overtime": overtime_str,
                "workHours": att.work_hours or "0h 0m"
            })
        
        # If no attendance data, return empty list
        return jsonify(attendance_data), 200
        
    except Exception as e:
        print(f"Attendance error: {str(e)}")
        return jsonify([]), 200
    finally:
        db.close()


#now for admin page datas

#data for employee list page in ogranization page of the admin section

@app.route('/api/employeeslist', methods=['GET'])
def get_employees_data():
    """Get all employees from database"""
    db = SessionLocal()
    try:
        # Get all employees with their profiles
        employees = db.query(User).outerjoin(
            EmployeeProfile, User.id == EmployeeProfile.user_id
        ).filter(
            User.role == 'employee'
        ).all()
        
        employees_data = []
        for user in employees:
            # Get profile if exists
            profile = db.query(EmployeeProfile).filter(
                EmployeeProfile.user_id == user.id
            ).first()
            
            name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            if not name:
                name = user.username
            
            employees_data.append({
                "id": user.id,
                "name": name,
                "email": user.email,
                "empId": profile.emp_id if profile and profile.emp_id else str(user.id),
                "position": profile.position if profile else "Employee",
                "department": profile.department if profile else "General",
                "status": profile.status if profile else "Active",
                "image": profile.profile_image if profile and profile.profile_image else f"https://i.pravatar.cc/40?u={user.id}"
            })
        
        return jsonify(employees_data), 200
        
    except Exception as e:
        print(f"Employees list error: {str(e)}")
        return jsonify([]), 200
    finally:
        db.close()


# datas for attendance page in admin section
@app.route('/api/attendancelist', methods=['GET'])
def get_admin_attendance_data():
    """Get all attendance records for admin view"""
    db = SessionLocal()
    try:
        today = date.today()
        
        # Get attendance records with user info
        attendance_records = db.query(Attendance, User).join(
            User, Attendance.user_id == User.id
        ).order_by(Attendance.date.desc()).limit(100).all()
        
        attendance_data = []
        for att, user in attendance_records:
            # Get employee profile for position info
            profile = db.query(EmployeeProfile).filter(
                EmployeeProfile.user_id == user.id
            ).first()
            
            name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username
            role = profile.position if profile else "Employee"
            emp_id = profile.emp_id if profile and profile.emp_id else str(user.id)
            
            attendance_data.append({
                "id": emp_id,
                "employee": name,
                "role": role,
                "status": att.status or "Absent",
                "date": att.date.strftime('%d %b %Y'),
                "checkIn": att.check_in.strftime('%H:%M') if att.check_in else "00:00",
                "checkOut": att.check_out.strftime('%H:%M') if att.check_out else "00:00",
                "workHours": att.work_hours or "0h 0m"
            })
        
        return jsonify(attendance_data), 200
        
    except Exception as e:
        print(f"Admin attendance error: {str(e)}")
        return jsonify([]), 200
    finally:
        db.close()


@app.route('/api/leaveapproval', methods=['GET'])
def get_admin_leave_approval_data():
    """Get all leave requests for admin approval"""
    db = SessionLocal()
    try:
        # Get all leave requests with user and leave type info
        requests_data = db.query(LeaveRequest, User, LeaveType).join(
            User, LeaveRequest.user_id == User.id
        ).join(
            LeaveType, LeaveRequest.leave_type_id == LeaveType.id
        ).order_by(LeaveRequest.applied_date.desc()).all()
        
        leave_approval_data = []
        for req, user, leave_type in requests_data:
            # Get employee profile for employee ID
            profile = db.query(EmployeeProfile).filter(
                EmployeeProfile.user_id == user.id
            ).first()
            
            name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username
            emp_id = profile.emp_id if profile and profile.emp_id else str(user.id)
            
            leave_approval_data.append({
                "name": name,
                "id": emp_id,
                "type": leave_type.name,
                "from": req.start_date.strftime('%d-%m-%Y'),
                "to": req.end_date.strftime('%d-%m-%Y'),
                "days": f"{req.num_days} Day(s)",
                "session": "Full Day",
                "dates": f"{req.start_date.strftime('%d-%m-%Y')}/Full Day",
                "requestDate": req.applied_date.strftime('%d-%m-%Y') if req.applied_date else "",
                "notify": "HR Head",
                "document": "",
                "reason": req.reason or "",
                "status": req.status.capitalize() if req.status else "Pending",
                "request_id": req.id
            })
        
        return jsonify(leave_approval_data), 200
        
    except Exception as e:
        print(f"Leave approval error: {str(e)}")
        return jsonify([]), 200
    finally:
        db.close()


@app.route('/api/leavepolicies', methods=['GET'])
def get_admin_leave_policies():
    """Get all leave types/policies from database"""
    db = SessionLocal()
    try:
        leave_types = db.query(LeaveType).all()
        
        leave_policies = []
        for lt in leave_types:
            leave_policies.append({
                "id": lt.id,
                "name": lt.name,
                "createdOn": "",  # Add created_at to LeaveType model if needed
                "type": "All",
                "max_days": lt.max_days_per_year,
                "description": lt.description or ""
            })
        
        # If no leave types in DB, provide defaults
        if not leave_policies:
            leave_policies = [
                {"id": 1, "name": "Casual Leave", "createdOn": "14 Apr 2025", "type": "All", "max_days": 12},
                {"id": 2, "name": "Sick Leave", "createdOn": "06 Apr 2025", "type": "All", "max_days": 12},
                {"id": 3, "name": "Annual Leave", "createdOn": "16 Mar 2025", "type": "All", "max_days": 15},
            ]
        
        return jsonify(leave_policies), 200
        
    except Exception as e:
        print(f"Leave policies error: {str(e)}")
        return jsonify([]), 200
    finally:
        db.close()


@app.route('/api/myteamla', methods=['GET'])
def get_my_team_la():
    """Get team members' leave requests for manager approval"""
    user_id = request.headers.get('X-User-ID')
    
    db = SessionLocal()
    try:
        # Get team members for this manager
        team_members = db.query(TeamMember).filter(
            TeamMember.manager_id == user_id
        ).all()
        
        member_ids = [tm.member_id for tm in team_members]
        
        if not member_ids:
            # If no team members defined, return empty or all employees if admin
            return jsonify([]), 200
        
        # Get leave requests for team members
        requests_data = db.query(LeaveRequest, User, LeaveType).join(
            User, LeaveRequest.user_id == User.id
        ).join(
            LeaveType, LeaveRequest.leave_type_id == LeaveType.id
        ).filter(
            LeaveRequest.user_id.in_(member_ids)
        ).order_by(LeaveRequest.applied_date.desc()).all()
        
        my_team_la = []
        for idx, (req, user, leave_type) in enumerate(requests_data, 1):
            profile = db.query(EmployeeProfile).filter(
                EmployeeProfile.user_id == user.id
            ).first()
            
            name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username
            emp_id = profile.emp_id if profile and profile.emp_id else str(user.id)
            image = profile.profile_image if profile and profile.profile_image else f"https://i.pravatar.cc/40?u={user.id}"
            
            my_team_la.append({
                "id": req.id,
                "name": name,
                "empId": emp_id,
                "type": leave_type.name,
                "from": req.start_date.strftime('%d-%m-%Y'),
                "to": req.end_date.strftime('%d-%m-%Y'),
                "days": f"{req.num_days} Day(s)",
                "session": "Full Day",
                "date": f"{req.start_date.strftime('%d-%m-%Y')}/Full Day",
                "request": req.applied_date.strftime('%d-%m-%Y') if req.applied_date else "",
                "notify": "HR Head",
                "document": "",
                "reason": req.reason or "",
                "status": req.status.capitalize() if req.status else "Pending",
                "image": image
            })
        
        return jsonify(my_team_la), 200
        
    except Exception as e:
        print(f"My team LA error: {str(e)}")
        return jsonify([]), 200
    finally:
        db.close()


@app.route('/api/myteamra', methods=['GET'])
def get_myteam_ra():
    """Get team members' regularization requests for manager approval"""
    user_id = request.headers.get('X-User-ID')
    
    db = SessionLocal()
    try:
        # Get team members for this manager
        team_members = db.query(TeamMember).filter(
            TeamMember.manager_id == user_id
        ).all()
        
        member_ids = [tm.member_id for tm in team_members]
        
        if not member_ids:
            return jsonify([]), 200
        
        # Get regularization requests for team members
        requests_data = db.query(Regularization, User).join(
            User, Regularization.user_id == User.id
        ).filter(
            Regularization.user_id.in_(member_ids)
        ).order_by(Regularization.request_date.desc()).all()
        
        my_team_ra = []
        for req, user in requests_data:
            profile = db.query(EmployeeProfile).filter(
                EmployeeProfile.user_id == user.id
            ).first()
            
            name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username
            emp_id = profile.emp_id if profile and profile.emp_id else str(user.id)
            image = profile.profile_image if profile and profile.profile_image else f"https://randomuser.me/api/portraits/lego/{user.id % 10}.jpg"
            
            session_str = req.session_type or "Full Day"
            
            my_team_ra.append({
                "id": req.id,
                "name": name,
                "empId": emp_id,
                "regDate": f"{req.date.strftime('%d-%m-%Y')}/{session_str}",
                "attendance": req.attendance_type or "Present",
                "requestDate": req.request_date.strftime('%d-%m-%Y') if req.request_date else "",
                "status": req.status.capitalize() if req.status else "Pending",
                "img": image
            })
        
        return jsonify(my_team_ra), 200
        
    except Exception as e:
        print(f"My team RA error: {str(e)}")
        return jsonify([]), 200
    finally:
        db.close()


@app.route('/api/regularizationapproval', methods=['GET'])
def get_regularization_approval():
    """Get all regularization requests for admin approval"""
    db = SessionLocal()
    try:
        # Get all regularization requests with user info
        requests_data = db.query(Regularization, User).join(
            User, Regularization.user_id == User.id
        ).order_by(Regularization.request_date.desc()).all()
        
        regularization_approval = []
        for req, user in requests_data:
            profile = db.query(EmployeeProfile).filter(
                EmployeeProfile.user_id == user.id
            ).first()
            
            name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username
            emp_id = profile.emp_id if profile and profile.emp_id else str(user.id)
            image = profile.profile_image if profile and profile.profile_image else f"https://randomuser.me/api/portraits/lego/{user.id % 10}.jpg"
            
            session_str = req.session_type or "Full Day"
            
            regularization_approval.append({
                "id": req.id,
                "name": name,
                "empId": emp_id,
                "regDate": f"{req.date.strftime('%d-%m-%Y')}/{session_str}",
                "attendance": req.attendance_type or "Present",
                "requestDate": req.request_date.strftime('%d-%m-%Y') if req.request_date else "",
                "status": req.status.capitalize() if req.status else "Pending",
                "img": image
            })
        
        return jsonify(regularization_approval), 200
        
    except Exception as e:
        print(f"Regularization approval error: {str(e)}")
        return jsonify([]), 200
    finally:
        db.close()


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


# =============================================================================
# PAYROLL MODULE ENDPOINTS
# =============================================================================

@app.route('/api/salary_structure', methods=['GET'])
def get_all_salary_structures():
    """Get all salary structures (admin view)"""
    db = SessionLocal()
    try:
        structures = db.query(SalaryStructure).all()
        result = []
        for s in structures:
            user = db.query(User).filter(User.id == s.user_id).first()
            result.append({
                "id": s.id,
                "user_id": s.user_id,
                "employee_name": f"{user.first_name or ''} {user.last_name or ''}".strip() if user else "Unknown",
                "basic_salary": float(s.basic_salary),
                "hra": float(s.hra or 0),
                "conveyance": float(s.conveyance or 0),
                "medical_allowance": float(s.medical_allowance or 0),
                "special_allowance": float(s.special_allowance or 0),
                "other_allowances": float(s.other_allowances or 0),
                "pf_deduction": float(s.pf_deduction or 0),
                "tax_deduction": float(s.tax_deduction or 0),
                "other_deductions": float(s.other_deductions or 0),
                "effective_from": s.effective_from.isoformat() if s.effective_from else None
            })
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@app.route('/api/salary_structure/<int:user_id>', methods=['GET'])
def get_salary_structure(user_id):
    """Get salary structure for a specific user"""
    db = SessionLocal()
    try:
        structure = db.query(SalaryStructure).filter(SalaryStructure.user_id == user_id).first()
        if not structure:
            return jsonify({"message": "No salary structure found"}), 404
        
        return jsonify({
            "id": structure.id,
            "user_id": structure.user_id,
            "basic_salary": float(structure.basic_salary),
            "hra": float(structure.hra or 0),
            "conveyance": float(structure.conveyance or 0),
            "medical_allowance": float(structure.medical_allowance or 0),
            "special_allowance": float(structure.special_allowance or 0),
            "other_allowances": float(structure.other_allowances or 0),
            "pf_deduction": float(structure.pf_deduction or 0),
            "tax_deduction": float(structure.tax_deduction or 0),
            "other_deductions": float(structure.other_deductions or 0),
            "effective_from": structure.effective_from.isoformat() if structure.effective_from else None
        }), 200
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@app.route('/api/salary_structure', methods=['POST'])
def create_salary_structure():
    """Create or update salary structure for an employee"""
    data = request.get_json()
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({"message": "User ID is required"}), 400
    
    db = SessionLocal()
    try:
        # Check if structure exists
        existing = db.query(SalaryStructure).filter(SalaryStructure.user_id == user_id).first()
        
        if existing:
            # Update existing
            existing.basic_salary = data.get('basic_salary', existing.basic_salary)
            existing.hra = data.get('hra', existing.hra)
            existing.conveyance = data.get('conveyance', existing.conveyance)
            existing.medical_allowance = data.get('medical_allowance', existing.medical_allowance)
            existing.special_allowance = data.get('special_allowance', existing.special_allowance)
            existing.other_allowances = data.get('other_allowances', existing.other_allowances)
            existing.pf_deduction = data.get('pf_deduction', existing.pf_deduction)
            existing.tax_deduction = data.get('tax_deduction', existing.tax_deduction)
            existing.other_deductions = data.get('other_deductions', existing.other_deductions)
            if data.get('effective_from'):
                existing.effective_from = datetime.strptime(data['effective_from'], '%Y-%m-%d').date()
            db.commit()
            return jsonify({"message": "Salary structure updated", "id": existing.id}), 200
        else:
            # Create new
            new_structure = SalaryStructure(
                user_id=user_id,
                basic_salary=data.get('basic_salary', 0),
                hra=data.get('hra', 0),
                conveyance=data.get('conveyance', 0),
                medical_allowance=data.get('medical_allowance', 0),
                special_allowance=data.get('special_allowance', 0),
                other_allowances=data.get('other_allowances', 0),
                pf_deduction=data.get('pf_deduction', 0),
                tax_deduction=data.get('tax_deduction', 0),
                other_deductions=data.get('other_deductions', 0),
                effective_from=datetime.strptime(data.get('effective_from', datetime.now().strftime('%Y-%m-%d')), '%Y-%m-%d').date()
            )
            db.add(new_structure)
            db.commit()
            db.refresh(new_structure)
            return jsonify({"message": "Salary structure created", "id": new_structure.id}), 201
    except Exception as e:
        db.rollback()
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@app.route('/api/payroll', methods=['GET'])
def get_all_payroll():
    """Get all payroll records (admin view)"""
    db = SessionLocal()
    try:
        month = request.args.get('month', type=int)
        year = request.args.get('year', type=int)
        
        query = db.query(Payroll)
        if month:
            query = query.filter(Payroll.month == month)
        if year:
            query = query.filter(Payroll.year == year)
        
        payrolls = query.all()
        result = []
        for p in payrolls:
            user = db.query(User).filter(User.id == p.user_id).first()
            result.append({
                "id": p.id,
                "user_id": p.user_id,
                "employee_name": f"{user.first_name or ''} {user.last_name or ''}".strip() if user else "Unknown",
                "month": p.month,
                "year": p.year,
                "basic_salary": float(p.basic_salary),
                "total_allowances": float(p.total_allowances or 0),
                "total_deductions": float(p.total_deductions or 0),
                "net_salary": float(p.net_salary),
                "working_days": p.working_days,
                "days_worked": p.days_worked,
                "leave_days": p.leave_days,
                "status": p.status,
                "payment_date": p.payment_date.isoformat() if p.payment_date else None
            })
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@app.route('/api/payroll/<int:user_id>', methods=['GET'])
def get_employee_payroll(user_id):
    """Get payroll records for a specific employee"""
    db = SessionLocal()
    try:
        payrolls = db.query(Payroll).filter(Payroll.user_id == user_id).order_by(Payroll.year.desc(), Payroll.month.desc()).all()
        result = []
        for p in payrolls:
            result.append({
                "id": p.id,
                "month": p.month,
                "year": p.year,
                "basic_salary": float(p.basic_salary),
                "total_allowances": float(p.total_allowances or 0),
                "total_deductions": float(p.total_deductions or 0),
                "net_salary": float(p.net_salary),
                "working_days": p.working_days,
                "days_worked": p.days_worked,
                "leave_days": p.leave_days,
                "status": p.status,
                "payment_date": p.payment_date.isoformat() if p.payment_date else None
            })
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@app.route('/api/payroll', methods=['POST'])
def create_payroll():
    """Create payroll entry for an employee"""
    data = request.get_json()
    user_id = data.get('user_id')
    month = data.get('month')
    year = data.get('year')
    
    if not all([user_id, month, year]):
        return jsonify({"message": "User ID, month, and year are required"}), 400
    
    db = SessionLocal()
    try:
        # Check if payroll already exists
        existing = db.query(Payroll).filter(
            Payroll.user_id == user_id,
            Payroll.month == month,
            Payroll.year == year
        ).first()
        
        if existing:
            return jsonify({"message": "Payroll already exists for this period"}), 409
        
        # Get salary structure
        salary_struct = db.query(SalaryStructure).filter(SalaryStructure.user_id == user_id).first()
        
        basic = float(data.get('basic_salary', salary_struct.basic_salary if salary_struct else 0))
        allowances = float(data.get('total_allowances', 0))
        deductions = float(data.get('total_deductions', 0))
        
        if salary_struct and not data.get('total_allowances'):
            allowances = float(salary_struct.hra or 0) + float(salary_struct.conveyance or 0) + \
                        float(salary_struct.medical_allowance or 0) + float(salary_struct.special_allowance or 0) + \
                        float(salary_struct.other_allowances or 0)
        
        if salary_struct and not data.get('total_deductions'):
            deductions = float(salary_struct.pf_deduction or 0) + float(salary_struct.tax_deduction or 0) + \
                        float(salary_struct.other_deductions or 0)
        
        net_salary = basic + allowances - deductions
        
        new_payroll = Payroll(
            user_id=user_id,
            month=month,
            year=year,
            basic_salary=basic,
            total_allowances=allowances,
            total_deductions=deductions,
            net_salary=net_salary,
            working_days=data.get('working_days', 22),
            days_worked=data.get('days_worked', 22),
            leave_days=data.get('leave_days', 0),
            status='pending'
        )
        db.add(new_payroll)
        db.commit()
        db.refresh(new_payroll)
        return jsonify({"message": "Payroll created", "id": new_payroll.id}), 201
    except Exception as e:
        db.rollback()
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@app.route('/api/payroll/<int:payroll_id>/pay', methods=['PUT'])
def mark_payroll_paid(payroll_id):
    """Mark payroll as paid"""
    db = SessionLocal()
    try:
        payroll = db.query(Payroll).filter(Payroll.id == payroll_id).first()
        if not payroll:
            return jsonify({"message": "Payroll not found"}), 404
        
        payroll.status = 'paid'
        payroll.payment_date = datetime.utcnow()
        
        admin_id = request.headers.get('X-User-ID')
        if admin_id:
            payroll.processed_by = int(admin_id)
        
        db.commit()
        return jsonify({"message": "Payroll marked as paid"}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@app.route('/api/payroll/summary', methods=['GET'])
def get_payroll_summary():
    """Get payroll summary statistics"""
    db = SessionLocal()
    try:
        current_month = datetime.now().month
        current_year = datetime.now().year
        
        # Total employees with salary structure
        total_with_salary = db.query(SalaryStructure).count()
        
        # Total payroll this month
        month_payroll = db.query(Payroll).filter(
            Payroll.month == current_month,
            Payroll.year == current_year
        ).all()
        
        total_amount = sum(float(p.net_salary) for p in month_payroll)
        paid_count = len([p for p in month_payroll if p.status == 'paid'])
        pending_count = len([p for p in month_payroll if p.status == 'pending'])
        
        # Company expense (last 6 months)
        six_months_ago = current_month - 5 if current_month > 5 else current_month + 7
        six_months_year = current_year if current_month > 5 else current_year - 1
        
        expenses = db.query(Payroll).filter(
            ((Payroll.year == current_year) & (Payroll.month <= current_month)) |
            ((Payroll.year == six_months_year) & (Payroll.month >= six_months_ago))
        ).all()
        
        total_expense = sum(float(p.net_salary) for p in expenses)
        
        return jsonify({
            "total_employees_with_salary": total_with_salary,
            "current_month_total": total_amount,
            "paid_count": paid_count,
            "pending_count": pending_count,
            "six_month_expense": total_expense,
            "upcoming_salary_date": f"{current_year}-{current_month:02d}-05"
        }), 200
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


# =============================================================================
# PERFORMANCE TRACKING ENDPOINTS
# =============================================================================

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    """Get tasks - optionally filtered by user_id"""
    db = SessionLocal()
    try:
        user_id = request.args.get('user_id', type=int)
        status = request.args.get('status')
        
        query = db.query(Task)
        if user_id:
            query = query.filter(Task.user_id == user_id)
        if status:
            query = query.filter(Task.status == status)
        
        tasks = query.order_by(Task.created_at.desc()).all()
        result = []
        for t in tasks:
            user = db.query(User).filter(User.id == t.user_id).first()
            result.append({
                "id": t.id,
                "user_id": t.user_id,
                "employee_name": f"{user.first_name or ''} {user.last_name or ''}".strip() if user else "Unknown",
                "title": t.title,
                "description": t.description,
                "priority": t.priority,
                "status": t.status,
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "completed_date": t.completed_date.isoformat() if t.completed_date else None,
                "project_name": t.project_name,
                "created_at": t.created_at.isoformat() if t.created_at else None
            })
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@app.route('/api/tasks', methods=['POST'])
def create_task():
    """Create a new task"""
    data = request.get_json()
    user_id = data.get('user_id')
    title = data.get('title')
    
    if not user_id or not title:
        return jsonify({"message": "User ID and title are required"}), 400
    
    db = SessionLocal()
    try:
        new_task = Task(
            user_id=user_id,
            title=title,
            description=data.get('description', ''),
            priority=data.get('priority', 'medium'),
            status='pending',
            project_name=data.get('project_name', ''),
            due_date=datetime.strptime(data['due_date'], '%Y-%m-%d').date() if data.get('due_date') else None,
            assigned_by=int(request.headers.get('X-User-ID')) if request.headers.get('X-User-ID') else None
        )
        db.add(new_task)
        db.commit()
        db.refresh(new_task)
        return jsonify({"message": "Task created", "id": new_task.id}), 201
    except Exception as e:
        db.rollback()
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    """Update a task"""
    data = request.get_json()
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return jsonify({"message": "Task not found"}), 404
        
        if data.get('title'):
            task.title = data['title']
        if data.get('description') is not None:
            task.description = data['description']
        if data.get('priority'):
            task.priority = data['priority']
        if data.get('status'):
            task.status = data['status']
            if data['status'] == 'completed':
                task.completed_date = date.today()
        if data.get('due_date'):
            task.due_date = datetime.strptime(data['due_date'], '%Y-%m-%d').date()
        if data.get('project_name') is not None:
            task.project_name = data['project_name']
        
        db.commit()
        return jsonify({"message": "Task updated"}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    """Delete a task"""
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return jsonify({"message": "Task not found"}), 404
        
        db.delete(task)
        db.commit()
        return jsonify({"message": "Task deleted"}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@app.route('/api/performance', methods=['GET'])
def get_performance_reviews():
    """Get performance reviews"""
    db = SessionLocal()
    try:
        user_id = request.args.get('user_id', type=int)
        year = request.args.get('year', type=int)
        
        query = db.query(PerformanceReview)
        if user_id:
            query = query.filter(PerformanceReview.user_id == user_id)
        if year:
            query = query.filter(PerformanceReview.review_period_year == year)
        
        reviews = query.order_by(PerformanceReview.review_period_year.desc(), PerformanceReview.review_period_month.desc()).all()
        result = []
        for r in reviews:
            user = db.query(User).filter(User.id == r.user_id).first()
            result.append({
                "id": r.id,
                "user_id": r.user_id,
                "employee_name": f"{user.first_name or ''} {user.last_name or ''}".strip() if user else "Unknown",
                "review_period_month": r.review_period_month,
                "review_period_year": r.review_period_year,
                "tasks_completed": r.tasks_completed,
                "projects_completed": r.projects_completed,
                "feedback_score": float(r.feedback_score) if r.feedback_score else None,
                "strengths": r.strengths,
                "improvements": r.improvements,
                "comments": r.comments,
                "status": r.status
            })
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@app.route('/api/performance', methods=['POST'])
def create_performance_review():
    """Create a performance review"""
    data = request.get_json()
    user_id = data.get('user_id')
    month = data.get('review_period_month')
    year = data.get('review_period_year')
    
    if not all([user_id, month, year]):
        return jsonify({"message": "User ID, month, and year are required"}), 400
    
    db = SessionLocal()
    try:
        # Check if review exists
        existing = db.query(PerformanceReview).filter(
            PerformanceReview.user_id == user_id,
            PerformanceReview.review_period_month == month,
            PerformanceReview.review_period_year == year
        ).first()
        
        if existing:
            return jsonify({"message": "Review already exists for this period"}), 409
        
        new_review = PerformanceReview(
            user_id=user_id,
            reviewer_id=int(request.headers.get('X-User-ID')) if request.headers.get('X-User-ID') else None,
            review_period_month=month,
            review_period_year=year,
            tasks_completed=data.get('tasks_completed', 0),
            projects_completed=data.get('projects_completed', 0),
            feedback_score=data.get('feedback_score'),
            strengths=data.get('strengths', ''),
            improvements=data.get('improvements', ''),
            comments=data.get('comments', ''),
            status='draft'
        )
        db.add(new_review)
        db.commit()
        db.refresh(new_review)
        return jsonify({"message": "Performance review created", "id": new_review.id}), 201
    except Exception as e:
        db.rollback()
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@app.route('/api/performance/summary', methods=['GET'])
def get_performance_summary():
    """Get performance summary statistics"""
    db = SessionLocal()
    try:
        current_month = datetime.now().month
        current_year = datetime.now().year
        
        # Total employees
        total_employees = db.query(User).filter(User.role == 'employee').count()
        
        # Total tasks this month
        total_tasks = db.query(Task).filter(
            extract('month', Task.created_at) == current_month,
            extract('year', Task.created_at) == current_year
        ).count()
        
        completed_tasks = db.query(Task).filter(
            Task.status == 'completed',
            extract('month', Task.completed_date) == current_month,
            extract('year', Task.completed_date) == current_year
        ).count()
        
        # Average feedback score
        avg_score = db.query(func.avg(PerformanceReview.feedback_score)).filter(
            PerformanceReview.review_period_year == current_year
        ).scalar()
        
        return jsonify({
            "total_employees": total_employees,
            "total_tasks_this_month": total_tasks,
            "completed_tasks_this_month": completed_tasks,
            "average_feedback_score": float(avg_score) if avg_score else 0
        }), 200
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


# =============================================================================
# DOCUMENT MANAGEMENT ENDPOINTS
# =============================================================================

@app.route('/api/documents', methods=['GET'])
def get_documents():
    """Get documents for a user"""
    db = SessionLocal()
    try:
        user_id = request.args.get('user_id', type=int)
        doc_type = request.args.get('type')
        
        query = db.query(Document)
        if user_id:
            query = query.filter(Document.user_id == user_id)
        if doc_type:
            query = query.filter(Document.document_type == doc_type)
        
        docs = query.order_by(Document.created_at.desc()).all()
        result = []
        for d in docs:
            result.append({
                "id": d.id,
                "user_id": d.user_id,
                "document_type": d.document_type,
                "file_name": d.file_name,
                "file_size": d.file_size,
                "description": d.description,
                "is_verified": d.is_verified,
                "created_at": d.created_at.isoformat() if d.created_at else None
            })
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@app.route('/api/documents', methods=['POST'])
def upload_document():
    """Upload a document (metadata only - file handling to be added)"""
    data = request.get_json()
    user_id = data.get('user_id')
    doc_type = data.get('document_type')
    file_name = data.get('file_name')
    
    if not all([user_id, doc_type, file_name]):
        return jsonify({"message": "User ID, document type, and file name are required"}), 400
    
    db = SessionLocal()
    try:
        new_doc = Document(
            user_id=user_id,
            document_type=doc_type,
            file_name=file_name,
            file_path=data.get('file_path', f'/uploads/{user_id}/{file_name}'),
            file_size=data.get('file_size', 0),
            mime_type=data.get('mime_type', 'application/octet-stream'),
            uploaded_by=int(request.headers.get('X-User-ID')) if request.headers.get('X-User-ID') else None,
            description=data.get('description', '')
        )
        db.add(new_doc)
        db.commit()
        db.refresh(new_doc)
        return jsonify({"message": "Document uploaded", "id": new_doc.id}), 201
    except Exception as e:
        db.rollback()
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@app.route('/api/documents/<int:doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    """Delete a document"""
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            return jsonify({"message": "Document not found"}), 404
        
        db.delete(doc)
        db.commit()
        return jsonify({"message": "Document deleted"}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@app.route('/api/documents/<int:doc_id>/verify', methods=['PUT'])
def verify_document(doc_id):
    """Mark a document as verified"""
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            return jsonify({"message": "Document not found"}), 404
        
        doc.is_verified = True
        db.commit()
        return jsonify({"message": "Document verified"}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


# =============================================================================
# PROFILE UPDATE ENDPOINTS
# =============================================================================

@app.route('/api/employee_profile/<int:user_id>', methods=['PUT'])
def update_employee_profile(user_id):
    """Update employee profile"""
    data = request.get_json()
    db = SessionLocal()
    try:
        profile = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == user_id).first()
        
        if not profile:
            # Create if doesn't exist
            profile = EmployeeProfile(user_id=user_id)
            db.add(profile)
        
        # Update fields if provided
        updateable_fields = [
            'emp_id', 'gender', 'dob', 'marital_status', 'nationality', 'blood_group',
            'address', 'emergency_contact', 'emergency_relationship', 'emp_type',
            'department', 'position', 'location', 'status', 'profile_image',
            'institution', 'edu_location', 'edu_start_date', 'edu_end_date',
            'qualification', 'specialization', 'skills', 'portfolio',
            'prev_company', 'prev_job_title', 'exp_start_date', 'exp_end_date',
            'responsibilities', 'total_experience_years',
            'bank_name', 'bank_branch', 'account_number', 'ifsc_code',
            'aadhaar_number', 'pan_number'
        ]
        
        for field in updateable_fields:
            if field in data:
                if field in ['dob', 'edu_start_date', 'edu_end_date', 'exp_start_date', 'exp_end_date'] and data[field]:
                    setattr(profile, field, datetime.strptime(data[field], '%Y-%m-%d').date())
                else:
                    setattr(profile, field, data[field])
        
        db.commit()
        return jsonify({"message": "Profile updated successfully"}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@app.route('/api/user/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    """Update basic user information"""
    data = request.get_json()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return jsonify({"message": "User not found"}), 404
        
        if data.get('first_name'):
            user.first_name = data['first_name']
        if data.get('last_name'):
            user.last_name = data['last_name']
        if data.get('phone'):
            user.phone = data['phone']
        if data.get('email'):
            user.email = data['email']
        
        db.commit()
        return jsonify({"message": "User updated successfully"}), 200
    except IntegrityError:
        db.rollback()
        return jsonify({"message": "Email or phone already exists"}), 409
    except Exception as e:
        db.rollback()
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


# =============================================================================
# SETTINGS & NOTIFICATIONS ENDPOINTS
# =============================================================================

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Get all system settings"""
    db = SessionLocal()
    try:
        settings = db.query(SystemSettings).all()
        result = {}
        for s in settings:
            result[s.setting_key] = {
                "value": s.setting_value,
                "type": s.setting_type,
                "description": s.description
            }
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@app.route('/api/settings', methods=['PUT'])
def update_settings():
    """Update system settings"""
    data = request.get_json()
    db = SessionLocal()
    try:
        for key, value in data.items():
            setting = db.query(SystemSettings).filter(SystemSettings.setting_key == key).first()
            if setting:
                setting.setting_value = str(value)
                setting.updated_by = int(request.headers.get('X-User-ID')) if request.headers.get('X-User-ID') else None
            else:
                new_setting = SystemSettings(
                    setting_key=key,
                    setting_value=str(value),
                    updated_by=int(request.headers.get('X-User-ID')) if request.headers.get('X-User-ID') else None
                )
                db.add(new_setting)
        
        db.commit()
        return jsonify({"message": "Settings updated"}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@app.route('/api/notifications', methods=['GET'])
def get_notifications():
    """Get notifications for a user"""
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        return jsonify({"message": "User ID required"}), 400
    
    db = SessionLocal()
    try:
        notifications = db.query(Notification).filter(
            Notification.user_id == int(user_id)
        ).order_by(Notification.created_at.desc()).limit(50).all()
        
        result = []
        for n in notifications:
            result.append({
                "id": n.id,
                "title": n.title,
                "message": n.message,
                "type": n.notification_type,
                "is_read": n.is_read,
                "link": n.link,
                "created_at": n.created_at.isoformat() if n.created_at else None
            })
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@app.route('/api/notifications/<int:notif_id>/read', methods=['PUT'])
def mark_notification_read(notif_id):
    """Mark a notification as read"""
    db = SessionLocal()
    try:
        notification = db.query(Notification).filter(Notification.id == notif_id).first()
        if not notification:
            return jsonify({"message": "Notification not found"}), 404
        
        notification.is_read = True
        db.commit()
        return jsonify({"message": "Notification marked as read"}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@app.route('/api/broadcast', methods=['GET'])
def get_broadcasts():
    """Get active broadcasts"""
    db = SessionLocal()
    try:
        broadcasts = db.query(Broadcast).filter(
            Broadcast.is_active == True,
            (Broadcast.expires_at == None) | (Broadcast.expires_at > datetime.utcnow())
        ).order_by(Broadcast.created_at.desc()).all()
        
        result = []
        for b in broadcasts:
            result.append({
                "id": b.id,
                "title": b.title,
                "message": b.message,
                "target_audience": b.target_audience,
                "created_at": b.created_at.isoformat() if b.created_at else None
            })
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@app.route('/api/broadcast', methods=['POST'])
def create_broadcast():
    """Create a broadcast message"""
    data = request.get_json()
    title = data.get('title')
    message = data.get('message')
    
    if not title or not message:
        return jsonify({"message": "Title and message are required"}), 400
    
    db = SessionLocal()
    try:
        new_broadcast = Broadcast(
            title=title,
            message=message,
            sent_by=int(request.headers.get('X-User-ID')) if request.headers.get('X-User-ID') else None,
            target_audience=data.get('target_audience', 'all'),
            expires_at=datetime.strptime(data['expires_at'], '%Y-%m-%d %H:%M:%S') if data.get('expires_at') else None
        )
        db.add(new_broadcast)
        db.commit()
        db.refresh(new_broadcast)
        
        # Optionally create notifications for all users
        if data.get('send_notifications', False):
            target = data.get('target_audience', 'all')
            query = db.query(User)
            if target == 'employees':
                query = query.filter(User.role == 'employee')
            elif target == 'admins':
                query = query.filter(User.role == 'admin')
            
            users = query.all()
            for user in users:
                notif = Notification(
                    user_id=user.id,
                    title=title,
                    message=message,
                    notification_type='broadcast'
                )
                db.add(notif)
            db.commit()
        
        return jsonify({"message": "Broadcast created", "id": new_broadcast.id}), 201
    except Exception as e:
        db.rollback()
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


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
    
    port = int(os.environ.get('PORT', 5001))
    print(f"\nStarting Flask server on http://0.0.0.0:{port}")
    print("CORS is enabled for all endpoints\n")
    app.run(debug=False, host='0.0.0.0', port=port)