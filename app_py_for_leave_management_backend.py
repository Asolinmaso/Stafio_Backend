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
import urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, extract, text
from database import (
    SessionLocal, User, OTP, init_db, get_db,
    LeaveType, LeaveBalance, LeaveRequest,
    EmployeeProfile, Attendance, Regularization,
    Holiday, Department, TeamMember,
    # New modules
    SalaryStructure, Payroll, Task, PerformanceReview,
    Document, SystemSettings, Notification, Broadcast, BreakSession,
    Announcement, BlacklistedToken
)
from auth import (
    generate_tokens, verify_token, blacklist_token,
    refresh_access_token, jwt_required, role_required, permission_required
)

# Create a Flask application instance
app = Flask(__name__)

from admin_endpoints import register_admin_endpoints
register_admin_endpoints(app)

# Register admin leave workflow endpoints (admin → manager approval flow)
# We'll register after decorators are defined (need custom_admin_required)

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


# --- AUTH DECORATORS (from auth.py) ---
# jwt_required, role_required, permission_required are imported from auth.py
# Keeping custom_admin_required as a wrapper for backward compat with admin_leave_workflow_endpoints
def custom_admin_required():
    """Backward-compatible wrapper that uses JWT auth internally"""
    def wrapper(fn):
        @wraps(fn)
        @jwt_required()
        def decorator(*args, **kwargs):
            user_role = getattr(request, 'user_role', None)
            
            import os
            log_file = os.path.join(os.path.dirname(__file__), "debug_auth.log")
            with open(log_file, "a") as f_log:
                f_log.write(f"{datetime.now()}: [custom_admin_required] Role Check. Actual: {user_role}\n")

            if not user_role or str(user_role).lower() != 'admin':
                with open(log_file, "a") as f_log:
                    f_log.write(f"{datetime.now()}: [custom_admin_required] ACCESS DENIED. Found: {user_role}\n")
                return jsonify({
                    "message": f"Access denied. Admin role required. (Found: {user_role})"
                }), 403
            return fn(*args, **kwargs)
        return decorator
    return wrapper

def custom_user_required():
    """Backward-compatible wrapper that uses JWT auth internally"""
    def wrapper(fn):
        @wraps(fn)
        @jwt_required()
        def decorator(*args, **kwargs):
            return fn(*args, **kwargs)
        return decorator
    return wrapper
# --- END AUTH DECORATORS ---

# Now register the admin workflow endpoints (needs custom_admin_required decorator)

# Register regularization approval/rejection endpoints with authorization checks
# NOTE: Leave approval endpoints are already in this file (lines 1200-1290)
from approval_endpoints import register_regularization_approval_endpoints
register_regularization_approval_endpoints(app)


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
        on_time = db.query(Attendance).join(User, Attendance.user_id == User.id).filter(
            Attendance.date == today,
            Attendance.status == 'On Time',
            User.role == 'employee'
        ).count()

        late_arrival = db.query(Attendance).join(User, Attendance.user_id == User.id).filter(
            Attendance.date == today,
            Attendance.status == 'Late',
            User.role == 'employee'
        ).count()
        
        # On Leave today - employees with approved leave that includes today's date
        on_leave = db.query(LeaveRequest).filter(
            LeaveRequest.status == 'approved',
            LeaveRequest.start_date <= today,
            LeaveRequest.end_date >= today
        ).count()
        
        print("DEBUG on_time:", on_time)  # add this

        
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

@app.route('/api/attendance/start-break', methods=['POST'])
def start_break():
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        return jsonify({"message": "User ID required"}), 400

    db = SessionLocal()
    try:
        today = datetime.now().date()

        new_break = BreakSession(
            user_id=int(user_id),
            date=today,
            break_start=datetime.now()
        )

        db.add(new_break)
        db.commit()

        return jsonify({"message": "Break started"}), 200

    except Exception as e:
        db.rollback()
        return jsonify({"message": str(e)}), 500
    finally:
        db.close()

@app.route('/api/attendance/end-break', methods=['POST'])
def end_break():
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        return jsonify({"message": "User ID required"}), 400

    db = SessionLocal()
    try:
        today = datetime.now().date()

        # Get latest open break (break_end is NULL)
        active_break = db.query(BreakSession).filter(
            BreakSession.user_id == int(user_id),
            BreakSession.date == today,
            BreakSession.break_end.is_(None)
        ).order_by(BreakSession.id.desc()).first()

        if not active_break:
            return jsonify({"message": "No active break found"}), 400

        active_break.break_end = datetime.now()

        # Calculate break minutes
        duration = active_break.break_end - active_break.break_start
        active_break.break_minutes = int(duration.total_seconds() // 60)

        db.commit()

        return jsonify({
            "message": "Break ended",
            "break_minutes": active_break.break_minutes
        }), 200

    except Exception as e:
        db.rollback()
        return jsonify({"message": str(e)}), 500
    finally:
        db.close()

@app.route('/api/attendance/punch-in', methods=['POST'])
def punch_in():
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        return jsonify({"message": "User ID required"}), 400

    db = SessionLocal()
    try:
        today = datetime.now().date()

        # Check if already punched in today
        existing = db.query(Attendance).filter(
            Attendance.user_id == int(user_id),
            Attendance.date == today
        ).first()

        if existing:
            return jsonify({"message": "Already punched in today"}), 400

        new_attendance = Attendance(
            user_id=int(user_id),
            date=today,
            check_in=datetime.now(),
            status="On Time"
        )

        db.add(new_attendance)
        db.commit()

        return jsonify({"message": "Punch in successful"}), 200

    except Exception as e:
        db.rollback()
        return jsonify({"message": str(e)}), 500
    finally:
        db.close()

@app.route('/api/attendance/punch-out', methods=['POST'])
def punch_out():
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        return jsonify({"message": "User ID required"}), 400

    db = SessionLocal()
    try:
        today = datetime.now().date()

        attendance = db.query(Attendance).filter(
            Attendance.user_id == int(user_id),
            Attendance.date == today
        ).first()

        if not attendance:
            return jsonify({"message": "No punch in found"}), 400

        if attendance.check_out:
            return jsonify({"message": "Already punched out"}), 400

        attendance.check_out = datetime.now()

        # Calculate total work time
                # Total worked minutes (check_out - check_in)
        total_duration = attendance.check_out - attendance.check_in
        total_minutes = int(total_duration.total_seconds() // 60)

        # Get total break minutes for today
        breaks = db.query(func.sum(BreakSession.break_minutes)).filter(
            BreakSession.user_id == int(user_id),
            BreakSession.date == today
        ).scalar()

        total_break_minutes = int(breaks) if breaks else 0

        # Net working minutes
        net_minutes = total_minutes - total_break_minutes
        if net_minutes < 0:
            net_minutes = 0

        hours = net_minutes // 60
        minutes = net_minutes % 60

        attendance.work_hours = f"{hours}h {minutes}m"

        db.commit()

        return jsonify({
            "message": "Punch out successful",
            "work_hours": attendance.work_hours
        }), 200

    except Exception as e:
        db.rollback()
        return jsonify({"message": str(e)}), 500
    finally:
        db.close()

@app.route('/api/attendance/today', methods=['GET'])
def get_today_attendance():
    user_id = request.headers.get('X-User-ID')

    db = SessionLocal()
    try:
        today = datetime.now().date()

        attendance = db.query(Attendance).filter(
            Attendance.user_id == user_id,
            Attendance.date == today
        ).first()

        if not attendance:
            return jsonify({}), 200

        # Check active break
        active_break = db.query(BreakSession).filter(
            BreakSession.user_id == user_id,
            BreakSession.date == today,
            BreakSession.break_end == None
        ).first()

        breaks = db.query(func.sum(BreakSession.break_minutes)).filter(
            BreakSession.user_id == user_id,
            BreakSession.date == today
        ).scalar()

        return jsonify({
            "check_in": attendance.check_in.isoformat() if attendance.check_in else None,
            "check_out": attendance.check_out.isoformat() if attendance.check_out else None,
            "work_hours": attendance.work_hours,
            "active_break": True if active_break else False,
            "total_break_minutes": int(breaks) if breaks else 0
        }), 200

    except Exception as e:
        print("Today attendance error:", e)
        return jsonify({}), 200
    finally:
        db.close()

import calendar

@app.route('/api/attendance_graph_stats', methods=['GET'])
def get_attendance_graph_stats():
    # If passed in args, it means we want a specific user (even if requester is Admin)
    requested_user_id = request.args.get('user_id')
    
    # Auth headers
    requester_role = request.headers.get('X-User-Role', '').lower()
    requester_id = request.headers.get('X-User-ID')
    
    db = SessionLocal()
    try:
        today = datetime.now().date()
        total_users_count = max(1, db.query(User).count())
        
        # Base query
        query = db.query(Attendance)
        
        # Decide if individual or global
        # 1. If requester is Employee -> Always individual (their own ID)
        # 2. If requester is Admin -> individual ONLY IF user_id is passed in args
        
        is_individual = False
        target_id = None
        
        if requester_role == 'admin':
            if requested_user_id:
                target_id = int(requested_user_id)
                is_individual = True
            else:
                is_individual = False # Global
        else:
            # Employee role or other — always show their own
            target_id = int(requester_id) if requester_id else (int(requested_user_id) if requested_user_id else None)
            is_individual = True if target_id else False

        if is_individual and target_id:
            query = query.filter(Attendance.user_id == target_id)

        # 1. Months Data (last 6 months)
        months_data = []
        for i in range(5, -1, -1):
            # Calculate start of target month
            # Go back i months from the 1st of current month
            first_of_this_month = today.replace(day=1)
            
            # Simplified year/month calc
            m = today.month - i
            y = today.year
            while m <= 0:
                m += 12
                y -= 1
            
            month_start = date(y, m, 1)
            # Find last day of month
            if m == 12:
                month_end = date(y + 1, 1, 1) - timedelta(days=1)
            else:
                month_end = date(y, m + 1, 1) - timedelta(days=1)
                
            month_name = calendar.month_abbr[m]
            
            present_count = query.filter(
                Attendance.date >= month_start,
                Attendance.date <= month_end,
                Attendance.check_in.isnot(None)
            ).count()
            
            # Expected days logic
            if y == today.year and m == today.month:
                # Up to today
                expected_per_user = max(1, (today.day * 5) // 7)
                expected_per_user = min(22, expected_per_user)
            else:
                expected_per_user = 22
                
            denominator = expected_per_user if is_individual else expected_per_user * total_users_count
            percent = min(100, (present_count / max(1, denominator)) * 100)
            
            months_data.append({
                "label": month_name,
                "value": round(percent)
            })
            
        # 2. Weeks Data (last 4 weeks)
        weeks_data = []
        for i in range(3, -1, -1):
            start_week = today - timedelta(days=today.weekday()) - timedelta(days=7 * i)
            end_week = start_week + timedelta(days=6)
            
            present_count = query.filter(
                Attendance.date >= start_week,
                Attendance.date <= end_week,
                Attendance.check_in.isnot(None)
            ).count()
            
            denominator = 5 if is_individual else 5 * total_users_count
            percent = min(100, (present_count / max(1, denominator)) * 100)
            
            weeks_data.append({
                "label": f"W{4 - i}",
                "value": round(percent)
            })
            
        # 3. Days Data (Current Week: Mon - Sun)
        days_data = []
        monday = today - timedelta(days=today.weekday())
        for i in range(7):
            target_day = monday + timedelta(days=i)
            day_name = calendar.day_abbr[target_day.weekday()]
            
            count = query.filter(
                Attendance.date == target_day,
                Attendance.check_in.isnot(None)
            ).count()
            
            if is_individual:
                value = 100 if count > 0 else 0
            else:
                value = round((count / total_users_count) * 100)

            days_data.append({
                "label": day_name,
                "value": value
            })
            
        return jsonify({
            "months": months_data,
            "weeks": weeks_data,
            "days": days_data
        }), 200
        
    except Exception as e:
        print(f"Attendance stats error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"months": [], "weeks": [], "days": []}), 500
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
    phone = data.get('phone')
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    role = data.get('role', 'employee')

    if not username or not password or not email or not phone:
        return jsonify({"message": "Username, password, email and phone are required."}), 400

    db = SessionLocal()
    try:
        # Check if signup is allowed
        signup_setting = db.query(SystemSettings).filter(SystemSettings.setting_key == 'allow_signup').first()
        is_disabled = signup_setting and signup_setting.setting_value.lower() in ['false', '0', 'no', 'disable', 'disabled']
        
        if is_disabled:
            return jsonify({"message": "User registration is currently disabled by the administrator."}), 403

        hashed_password = generate_password_hash(password)
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

        return jsonify({
            "message": "User registered successfully!",
            "user_id": new_user.id
        }), 201

    except IntegrityError:
        db.rollback()
        return jsonify({"message": "Username, email, or Phone number already exists."}), 409

    except Exception as e:
        if db:
            db.rollback()
        return jsonify({"message": f"Server error: {str(e)}"}), 500

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



@app.route('/admin_google_register', methods=['POST'])
def admin_google_register():
    data = request.get_json()
    email = data.get("email")
    username = data.get("username")
    role = data.get("role", "admin")

    if not email:
        return jsonify({"message": "Email is required"}), 400

    db = SessionLocal()
    try:
        # Check if signup is allowed
        signup_setting = db.query(SystemSettings).filter(SystemSettings.setting_key == 'allow_signup').first()
        if signup_setting and signup_setting.setting_value.lower() == 'false':
            return jsonify({"message": "User registration is currently disabled by the administrator."}), 403

        # Check if user exists (any role)
        user = db.query(User).filter(User.email == email).first()

        if user:
            if user.role == "admin":
                return jsonify({
                    "exists": True,
                    "message": "Email already registered as admin. Please login instead."
                }), 200
            else:
                # Email exists but under a different role (manager/employee)
                return jsonify({
                    "exists": True,
                    "message": f"This email is already registered as '{user.role}'. Please use admin login or contact your administrator."
                }), 409

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
        print(f"Error in admin_google_register: {str(e)}")
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
        # Check if signup is allowed
        signup_setting = db.query(SystemSettings).filter(SystemSettings.setting_key == 'allow_signup').first()
        if signup_setting and signup_setting.setting_value.lower() == 'false':
            return jsonify({"message": "User registration is currently disabled by the administrator."}), 403

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
            tokens = generate_tokens(user.id, user.role)
            return jsonify({
                "user_id": user.id,
                "username": user.username,
                "role": user.role,
                "email": user.email,
                **tokens
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

        tokens = generate_tokens(new_user.id, new_user.role)
        return jsonify({
            "user_id": new_user.id,
            "username": new_user.username,
            "role": new_user.role,
            "email": new_user.email,
            **tokens
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
            tokens = generate_tokens(user.id, user.role)
            return jsonify(
                user_id=user.id, role=user.role, username=user.username, email=user.email,
                access_token=tokens['access_token'], refresh_token=tokens['refresh_token']
            ), 200
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
        
        tokens = generate_tokens(user.id, user.role)
        return jsonify({
            "user_id": user.id,
            "username": user.username,
            "role": user.role,
            "email": user.email,
            **tokens
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
            tokens = generate_tokens(user.id, user.role)
            return jsonify({
                "user_id": user.id,
                "username": user.username,
                "role": user.role,
                "email": user.email,
                **tokens
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

        tokens = generate_tokens(new_user.id, new_user.role)
        return jsonify({
            "user_id": new_user.id,
            "username": new_user.username,
            "role": new_user.role,
            "email": new_user.email,
            **tokens
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
            tokens = generate_tokens(user.id, user.role)
            return jsonify(
                user_id=user.id, role=user.role, username=user.username, email=user.email,
                access_token=tokens['access_token'], refresh_token=tokens['refresh_token']
            ), 200
        else:
            return jsonify({"message": "Invalid admin username/email or password."}), 401
    except Exception as e:
        print(f"ERROR: admin_login - An unexpected error occurred: {str(e)}")
        return jsonify({"message": f"An unexpected error occurred: {str(e)}"}), 500
    finally:
        if db:
            db.close()

# --- PROTECTED ROUTE (JWT PROTECTED) ---
@app.route('/protected', methods=['GET'])
@jwt_required()
def protected():
    user_id = request.user_id
    return jsonify(logged_in_as={'id': user_id, 'message': 'You have accessed a protected route'}), 200
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
        total_leaves = float(total_leaves_result) if total_leaves_result else 0  # Default 0 if no balance set
        
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


@app.route('/api/attendance/monthly', methods=['GET'])
def get_monthly_attendance():
    user_id = request.headers.get('X-User-ID')
    print(f"DEBUG monthly attendance - user_id: {user_id}")
    if not user_id:
        return jsonify([]), 400

    db = SessionLocal()
    try:
        current_year = datetime.now().year

        # Get working days per month from attendance table
        results = db.query(
            extract('month', Attendance.date).label('month'),
            func.count(Attendance.id).label('worked')
        ).filter(
            Attendance.user_id == int(user_id),
            extract('year', Attendance.date) == current_year,
            Attendance.status.in_(['On Time', 'Late Login'])
        ).group_by(extract('month', Attendance.date)).all()

        # Total working days per month (approx 22 working days)
        WORKING_DAYS_PER_MONTH = 22

        month_names = ["Jan","Feb","Mar","Apr","May","Jun",
                       "Jul","Aug","Sep","Oct","Nov","Dec"]

        # Build all 12 months, 0% if no data
        data = []
        results_dict = {int(r.month): r.worked for r in results}
        for i in range(1, 13):
            worked = results_dict.get(i, 0)
            percentage = round((worked / WORKING_DAYS_PER_MONTH) * 100)
            percentage = min(percentage, 100)  # cap at 100%
            data.append({
                "month": month_names[i - 1],
                "value": percentage
            })

        return jsonify(data), 200

    except Exception as e:
        print(f"Monthly attendance error: {str(e)}")
        return jsonify([]), 200
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

    # Validation
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
        # Convert types
        user_id = int(user_id)
        leave_type_id = int(leave_type_id)
        num_days = float(num_days)

        # Check leave type
        leave_type = db.query(LeaveType).filter(LeaveType.id == leave_type_id).first()
        if not leave_type:
            available = db.query(LeaveType).all()
            if not available:
                return jsonify({"message": "No leave types configured. Please contact admin."}), 400
            else:
                type_names = ", ".join([f"{lt.id}: {lt.name}" for lt in available])
                return jsonify({"message": f"Invalid leave type ID. Available: {type_names}"}), 400

        # Date parsing
        s_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        e_date = datetime.strptime(end_date, '%Y-%m-%d').date()

        if s_date < datetime.today().date():
            return jsonify({"message": "Cannot apply leave for past dates"}), 400

        day_diff = (e_date - s_date).days + 1
        if day_diff < 0:
            return jsonify({"message": "End date cannot be before start date"}), 400

        # 🚫 OVERLAP CHECK (FIXED - NO lower())
        existing_leave = db.query(LeaveRequest).filter(
            LeaveRequest.user_id == user_id,
            LeaveRequest.status.in_(["pending", "approved"]),  # ✅ FIXED
            LeaveRequest.start_date <= e_date,
            LeaveRequest.end_date >= s_date
        ).first()

        if existing_leave:
            return jsonify({
                "message": f"You already applied leave from {existing_leave.start_date} to {existing_leave.end_date}"
            }), 400

        # Day type
        day_type_raw = data.get('day_type', 'full_day')
        if day_type_raw == 'half':
            day_type_raw = 'half_day'
        elif day_type_raw == 'full':
            day_type_raw = 'full_day'

        # Calculate days
        calculated_num_days = float(day_diff)
        if day_type_raw == 'half_day':
            calculated_num_days = day_diff * 0.5

        # ✅ LEAVE BALANCE CHECK (FIXED)
        used_result = db.query(func.sum(LeaveRequest.num_days)).filter(
            LeaveRequest.user_id == user_id,
            LeaveRequest.leave_type_id == leave_type_id,
            LeaveRequest.status.in_(["pending", "approved"])  # ✅ FIXED
        ).scalar()

        used = float(used_result) if used_result else 0
        total = float(leave_type.max_days_per_year)
        remaining = round(total - used, 2)

        if remaining <= 0:
            return jsonify({
                "message": f"No {leave_type.name} balance available"
            }), 400

        if calculated_num_days > remaining:
            return jsonify({
                "message": f"Only {remaining} day(s) available for {leave_type.name}"
            }), 400

        # Create leave
        new_request = LeaveRequest(
            user_id=user_id,
            leave_type_id=leave_type_id,
            start_date=s_date,
            end_date=e_date,
            num_days=calculated_num_days,
            day_type=day_type_raw,
            reason=reason,
            status='pending'  # ✅ keep lowercase consistent
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

@app.route('/leave_requests/<int:request_id>', methods=['PUT'])
def update_leave_request(request_id):
    """Update an existing leave request (only if pending)"""

    data = request.get_json()

    db = SessionLocal()
    try:
        leave_request = db.query(LeaveRequest).filter(
            LeaveRequest.id == request_id
        ).first()

        if not leave_request:
            return jsonify({"message": "Leave request not found"}), 404

        # ❌ Only allow edit if pending
        if leave_request.status != "pending":
            return jsonify({"message": "Only pending requests can be edited"}), 400

        # Get updated fields
        leave_type_id = data.get('leave_type_id')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        reason = data.get('reason')

        # Convert dates
        s_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        e_date = datetime.strptime(end_date, '%Y-%m-%d').date()

        if s_date < datetime.today().date():
            return jsonify({"message": "Cannot apply leave for past dates"}), 400

        if e_date < s_date:
            return jsonify({"message": "End date cannot be before start date"}), 400

        # Day type
        day_type_raw = data.get('day_type', 'full_day')

        # Calculate days
        day_diff = (e_date - s_date).days + 1
        calculated_num_days = float(day_diff)

        if day_type_raw == 'half_day':
            calculated_num_days = day_diff * 0.5

        # 🚫 OVERLAP CHECK (exclude current request)
        existing_leave = db.query(LeaveRequest).filter(
            LeaveRequest.user_id == leave_request.user_id,
            LeaveRequest.id != request_id,  # exclude current
            LeaveRequest.status.in_(["pending", "approved"]),
            LeaveRequest.start_date <= e_date,
            LeaveRequest.end_date >= s_date
        ).first()

        if existing_leave:
            return jsonify({
                "message": f"Overlapping leave exists from {existing_leave.start_date} to {existing_leave.end_date}"
            }), 400

        # ✅ UPDATE VALUES
        leave_request.leave_type_id = leave_type_id
        leave_request.start_date = s_date
        leave_request.end_date = e_date
        leave_request.num_days = calculated_num_days
        leave_request.day_type = day_type_raw
        leave_request.reason = reason

        db.commit()

        return jsonify({
            "message": "Leave request updated successfully"
        }), 200

    except Exception as e:
        db.rollback()
        print("Update leave error:", str(e))
        return jsonify({"message": str(e)}), 500

    finally:
        db.close()

#for delete the request
@app.route('/leave_requests/<int:request_id>', methods=['DELETE'])
def delete_leave_request(request_id):
    """Delete a leave request (only if pending)"""

    db = SessionLocal()
    try:
        leave_request = db.query(LeaveRequest).filter(
            LeaveRequest.id == request_id
        ).first()

        if not leave_request:
            return jsonify({"message": "Leave request not found"}), 404

        # ❌ Only allow delete if pending
        if leave_request.status != "pending":
            return jsonify({"message": "Only pending requests can be deleted"}), 400

        db.delete(leave_request)
        db.commit()

        return jsonify({"message": "Leave request deleted successfully"}), 200

    except Exception as e:
        db.rollback()
        print("Delete leave error:", str(e))
        return jsonify({"message": str(e)}), 500

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
    """Approve a leave request with authorization check"""
    # Use silent=True to avoid errors when body is empty or missing
    data = request.get_json(silent=True) or {}
    reason = data.get('reason', '')
    approved_by = data.get('approved_by')  # From request body (legacy)
    approver_id = request.headers.get('X-User-ID')  # From header (new)
    
    # Debug logging
    print(f"Approve request {request_id}: approver_id from header={approver_id}, from body={approved_by}")
    
    # Use header if available, fallback to body
    final_approver_id = approver_id if approver_id else approved_by
    
    if not final_approver_id:
        return jsonify({"message": "Approver ID is required (X-User-ID header or approved_by in body)"}), 400

    db = SessionLocal()
    try:
        leave_request = db.query(LeaveRequest).filter(
            LeaveRequest.id == request_id
        ).first()

        if not leave_request:
            return jsonify({"message": "Leave request not found"}), 404
        
        print(f"Leave request status: {leave_request.status}, approver_type: {leave_request.approver_type}")
        
        if leave_request.status != 'pending':
            return jsonify({"message": f"Request is already {leave_request.status}"}), 400
        
        # --- AUTHORIZATION CHECK (NEW) ---
        if leave_request.approver_type == 'manager':
            # Only designated manager can approve admin requests
            if not leave_request.designated_approver_id:
                return jsonify({"message": "No designated approver assigned"}), 400
            if not final_approver_id or int(final_approver_id) != leave_request.designated_approver_id:
                return jsonify({"message": "Only the designated manager can approve this request"}), 403
        elif leave_request.approver_type == 'admin' or not leave_request.approver_type:
            # Employee requests - verify approver is admin (optional check for backward compatibility)
            if final_approver_id:
                approver = db.query(User).filter(User.id == int(final_approver_id)).first()
                if approver and approver.role != 'admin':
                    return jsonify({"message": "Only admins can approve employee leave requests"}), 403
        # --- END AUTHORIZATION CHECK ---

        leave_request.status = 'approved'
        leave_request.approved_by = int(final_approver_id) if final_approver_id else None
        leave_request.approval_date = datetime.utcnow()
        leave_request.approval_reason = reason

        # Deduct from leave balance
        year = leave_request.start_date.year
        balance = db.query(LeaveBalance).filter(
            LeaveBalance.user_id == leave_request.user_id,
            LeaveBalance.leave_type_id == leave_request.leave_type_id,
            LeaveBalance.year == year
        ).first()

        if balance:
            # Recalculate duration for deduction to handle any legacy data issues
            actual_days = (leave_request.end_date - leave_request.start_date).days + 1
            deduct_days = float(actual_days)
            if leave_request.day_type == 'half_day':
                deduct_days = actual_days * 0.5
            
            balance.used = (balance.used or 0) + deduct_days
            balance.balance = balance.balance - deduct_days

        # Create Notification
        new_notif = Notification(
            user_id=leave_request.user_id,
            title="Leave Request Approved",
            message=f"Your leave request for {leave_request.start_date} to {leave_request.end_date} has been approved.",
            notification_type="leave",
            link="/employee/leave-history"
        )
        db.add(new_notif)
        db.commit()
        print(f"DEBUG: Created leave approval notification for user {leave_request.user_id}")

        return jsonify({"message": "Leave request approved successfully"}), 200

    except Exception as e:
        db.rollback()
        print(f"Approve leave error: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()



@app.route('/api/leave_requests/<int:request_id>/reject', methods=['PUT'])
def reject_leave_request(request_id):
    """Reject a leave request with authorization check"""
    # Use silent=True to avoid errors when body is empty or missing
    data = request.get_json(silent=True) or {}
    reason = data.get('reason', '')
    approved_by = data.get('approved_by')  # From request body (legacy)
    approver_id = request.headers.get('X-User-ID')  # From header (new)
    
    # Debug logging
    print(f"Reject request {request_id}: approver_id from header={approver_id}, from body={approved_by}")
    
    # Use header if available, fallback to body
    final_approver_id = approver_id if approver_id else approved_by
    
    if not final_approver_id:
        return jsonify({"message": "Approver ID is required (X-User-ID header or approved_by in body)"}), 400

    db = SessionLocal()
    try:
        leave_request = db.query(LeaveRequest).filter(
            LeaveRequest.id == request_id
        ).first()

        if not leave_request:
            return jsonify({"message": "Leave request not found"}), 404
        
        print(f"Leave request status: {leave_request.status}, approver_type: {leave_request.approver_type}")
        
        if leave_request.status != 'pending':
            return jsonify({"message": f"Request is already {leave_request.status}"}), 400
        
        # --- AUTHORIZATION CHECK (NEW) ---
        if leave_request.approver_type == 'manager':
            # Only designated manager can reject admin requests
            if not leave_request.designated_approver_id:
                return jsonify({"message": "No designated approver assigned"}), 400
            if not final_approver_id or int(final_approver_id) != leave_request.designated_approver_id:
                return jsonify({"message": "Only the designated manager can reject this request"}), 403
        elif leave_request.approver_type == 'admin' or not leave_request.approver_type:
            # Employee requests - verify approver is admin (optional check for backward compatibility)
            if final_approver_id:
                approver = db.query(User).filter(User.id == int(final_approver_id)).first()
                if approver and approver.role != 'admin':
                    return jsonify({"message": "Only admins can reject employee leave requests"}), 403
        # --- END AUTHORIZATION CHECK ---

        leave_request.status = 'rejected'
        leave_request.rejection_reason = reason
        leave_request.approved_by = int(final_approver_id) if final_approver_id else None

        # Create Notification
        new_notif = Notification(
            user_id=leave_request.user_id,
            title="Leave Request Rejected",
            message=f"Your leave request for {leave_request.start_date} to {leave_request.end_date} has been rejected. Reason: {reason}",
            notification_type="leave",
            link="/employee/leave-history"
        )
        db.add(new_notif)
        db.commit()
        print(f"DEBUG: Created leave rejection notification for user {leave_request.user_id}")

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

    if not user_id:
        return jsonify({
            "error": "User ID is required",
            "working_days": 0,
            "total_leaves": 0,
            "late_logins": 0,
            "on_time_logins": 0
        }), 400

    db = SessionLocal()
    try:
        now = datetime.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Count working days
        working_days = db.query(Attendance).filter(
            Attendance.user_id == user_id,
            Attendance.date >= start_of_month.date(),
            Attendance.status.in_([
                'present', 'Present',
                'On Time', 'on_time', 'ontime',
                'Late', 'Late Login', 'late_login'
            ])
        ).count()

        # Count approved leaves (raw SQL to avoid day_type column issue)
        total_leaves_result = db.execute(text("""
            SELECT COUNT(*) FROM leave_requests
            WHERE user_id = :user_id
            AND status = 'approved'
            AND start_date >= :start_date
        """), {"user_id": user_id, "start_date": start_of_month.date()})
        total_leaves = total_leaves_result.scalar() or 0

        # Count late logins
        late_logins = db.query(Attendance).filter(
            Attendance.user_id == user_id,
            Attendance.date >= start_of_month.date(),
            Attendance.status.in_(['Late', 'Late Login', 'late_login', 'late'])
        ).count()

        # Count on-time logins
        on_time_logins = db.query(Attendance).filter(
            Attendance.user_id == user_id,
            Attendance.date >= start_of_month.date(),
            Attendance.status.in_(['On Time', 'on_time', 'ontime', 'present', 'Present'])
        ).count()

        return jsonify({
            "working_days": working_days or 0,
            "total_leaves": total_leaves or 0,
            "late_logins": late_logins or 0,
            "on_time_logins": on_time_logins or 0
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": str(e),
            "working_days": 0,
            "total_leaves": 0,
            "late_logins": 0,
            "on_time_logins": 0
        }), 500

    finally:
        db.close()

@app.route('/api/leave_notification', methods=['GET'])
def get_leave_notification():
    """Get latest approved/rejected leave notification for employee dashboard"""
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        return jsonify({"notification": None}), 200

    db = SessionLocal()
    try:
        # Get the most recent approved or rejected leave request
        leave = db.query(LeaveRequest).filter(
            LeaveRequest.user_id == int(user_id),
            LeaveRequest.status.in_(['approved', 'rejected'])
        ).order_by(LeaveRequest.approval_date.desc()).first()

        if not leave:
            return jsonify({"notification": None}), 200

        return jsonify({
            "notification": {
                "status": leave.status,
                "start_date": leave.start_date.strftime('%d %B %Y'),
                "end_date": leave.end_date.strftime('%d %B %Y')
            }
        }), 200

    except Exception as e:
        print(f"Leave notification error: {str(e)}")
        return jsonify({"notification": None}), 200
    finally:
        db.close()

@app.route('/api/admin/pending_counts', methods=['GET'])
def get_admin_pending_counts():
    """Get pending approvals and pending leave requests count for admin dashboard notification"""
    db = SessionLocal()
    try:
        # Pending leave approvals (regularization requests pending)
        pending_approvals = db.query(func.count(Regularization.id)).filter(
            Regularization.status == 'pending'
        ).scalar() or 0

        # Pending leave requests
        pending_leave_requests = db.query(func.count(LeaveRequest.id)).filter(
            LeaveRequest.status == 'pending'
        ).scalar() or 0

        return jsonify({
            "pending_approvals": pending_approvals,
            "pending_leave_requests": pending_leave_requests
        }), 200

    except Exception as e:
        print(f"Pending counts error: {str(e)}")
        return jsonify({
            "pending_approvals": 0,
            "pending_leave_requests": 0
        }), 200
    finally:
        db.close()

@app.route('/api/leave_stats', methods=['GET'])
def get_leave_stats():
    """Return aggregated leave-days for last 5 months, current month weeks, and current week days.
    Optional query param: user_id (or set X-User-ID header)."""
    user_id = request.headers.get('X-User-ID') or request.args.get('user_id')

    db = SessionLocal()
    try:
        now = datetime.now().date()

        # Months: last 5 months including current
        months = []
        for offset in range(4, -1, -1):
            # compute year/month for offset months ago
            m = now.month - offset
            y = now.year
            while m <= 0:
                m += 12
                y -= 1

            start = date(y, m, 1)
            if m == 12:
                next_month = date(y + 1, 1, 1)
            else:
                next_month = date(y, m + 1, 1)
            end = next_month - timedelta(days=1)

            q = db.query(func.coalesce(func.sum(LeaveRequest.num_days), 0)).filter(
                LeaveRequest.status == 'approved',
                LeaveRequest.start_date >= start,
                LeaveRequest.start_date <= end,
            )
            if user_id:
                try:
                    q = q.filter(LeaveRequest.user_id == int(user_id))
                except Exception:
                    q = q.filter(LeaveRequest.user_id == user_id)

            total_days = float(q.scalar() or 0)
            months.append({"month": start.strftime('%b'), "value": round(total_days, 2)})

        # Weeks: split current month into sequential weeks (W1..W5)
        start_of_month = now.replace(day=1)
        if start_of_month.month == 12:
            first_next = date(start_of_month.year + 1, 1, 1)
        else:
            first_next = date(start_of_month.year, start_of_month.month + 1, 1)
        month_end = first_next - timedelta(days=1)

        weeks = []
        ws = start_of_month
        idx = 1
        while ws <= month_end and idx <= 5:
            we = min(ws + timedelta(days=6), month_end)
            q = db.query(func.coalesce(func.sum(LeaveRequest.num_days), 0)).filter(
                LeaveRequest.status == 'approved',
                LeaveRequest.start_date >= ws,
                LeaveRequest.start_date <= we,
            )
            if user_id:
                try:
                    q = q.filter(LeaveRequest.user_id == int(user_id))
                except Exception:
                    q = q.filter(LeaveRequest.user_id == user_id)

            total_days = float(q.scalar() or 0)
            weeks.append({"label": f"W{idx}", "value": round(total_days, 2)})
            ws = we + timedelta(days=1)
            idx += 1

        # Days: current week Mon-Fri
        wd = now.weekday()
        monday = now - timedelta(days=wd)
        days = []
        for i in range(5):
            d = monday + timedelta(days=i)
            q = db.query(func.coalesce(func.sum(LeaveRequest.num_days), 0)).filter(
                LeaveRequest.status == 'approved',
                LeaveRequest.start_date == d,
            )
            if user_id:
                try:
                    q = q.filter(LeaveRequest.user_id == int(user_id))
                except Exception:
                    q = q.filter(LeaveRequest.user_id == user_id)

            total_days = float(q.scalar() or 0)
            days.append({"label": d.strftime('%a'), "value": round(total_days, 2)})

        return jsonify({"months": months, "weeks": weeks, "days": days}), 200

    except Exception as e:
        print(f"Leave stats error: {str(e)}")
        return jsonify({"months": [], "weeks": [], "days": []}), 200
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
            # Calculate number of days accurately including half-day
            actual_days = (req.end_date - req.start_date).days + 1
            if req.day_type == 'half_day':
                display_days = actual_days * 0.5
            else:
                display_days = float(actual_days)
            
            days_text = f"{display_days} Day" if display_days == 1 else f"{display_days} Days"
            
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
    user_id = request.headers.get('X-User-ID')
    
    db = SessionLocal()
    try:
        requests_data = db.query(LeaveRequest, LeaveType).join(
            LeaveType, LeaveRequest.leave_type_id == LeaveType.id
        ).filter(
            LeaveRequest.user_id == int(user_id)  # ✅ FIXED
        ).order_by(LeaveRequest.applied_date.desc()).all()
        
        leave_data = []
        for req, leave_type in requests_data:
            day_label = "Half Day" if req.day_type == "half_day" else "Full Day"
            
            actual_days = (req.end_date - req.start_date).days + 1
            display_days = actual_days * 0.5 if req.day_type == 'half_day' else float(actual_days)
                
            leave_data.append({
                "id": req.id,

                # ✅ RAW DATA (for edit)
                "leave_type_id": req.leave_type_id,
                "start_date": req.start_date.strftime('%Y-%m-%d'),
                "end_date": req.end_date.strftime('%Y-%m-%d'),
                "day_type": req.day_type,
                "num_days": req.num_days,

                # ✅ DISPLAY DATA
                "type": f"{leave_type.name} {display_days} Day(s)",
                "date": f"{req.start_date.strftime('%d-%m-%Y')}/{day_label}",
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
    
    if not user_id:
        return jsonify({"message": "User ID header required"}), 400

    db = SessionLocal()
    try:
        requests_data = db.query(Regularization).filter(
            Regularization.user_id == int(user_id)
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

@app.route('/api/regularization', methods=['POST'])
def create_regularization():
    """
    Create a regularization request for employee
    """
    data = request.get_json() or {}

    user_id = request.headers.get('X-User-ID')
    date_str = data.get('date')
    session_type = data.get('session_type')        # Full Day / Half Day (FN/AN)
    attendance_type = data.get('attendance_type')  # Present / Absent
    reason = data.get('reason')

    # ---------- Validation ----------
    if not user_id:
        return jsonify({"message": "User ID missing"}), 400

    if not date_str:
        return jsonify({"message": "Date is required"}), 400

    if not attendance_type:
        return jsonify({"message": "Attendance type is required"}), 400

    # ---------- Insert ----------
    db = SessionLocal()
    try:
        new_regularization = Regularization(
            user_id=int(user_id),
            date=datetime.strptime(date_str, '%Y-%m-%d').date(),
            session_type=session_type or "Full Day",
            attendance_type=attendance_type,
            reason=reason,
            status="pending"
        )

        db.add(new_regularization)
        db.commit()
        db.refresh(new_regularization)

        return jsonify({
            "message": "Regularization request submitted successfully",
            "id": new_regularization.id
        }), 201

    except Exception as e:
        db.rollback()
        print("Create Regularization Error:", str(e))
        return jsonify({"message": "Failed to submit regularization"}), 500

    finally:
        db.close()

@app.route('/api/regularization/<int:reg_id>', methods=['PUT'])
def update_regularization(reg_id):
    user_id = request.headers.get('X-User-ID')
    data = request.get_json() or {}

    db = SessionLocal()
    try:
        reg = db.query(Regularization).filter_by(
            id=reg_id,
            user_id=int(user_id)
        ).first()

        if not reg:
            return jsonify({"message": "Record not found"}), 404

        if reg.status != "pending":
            return jsonify({"message": "Cannot edit approved/rejected request"}), 403

        reg.date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        reg.session_type = data.get('session_type')
        reg.attendance_type = data.get('attendance_type')
        reg.reason = data.get('reason')

        db.commit()
        return jsonify({"message": "Regularization updated"}), 200

    except Exception as e:
        db.rollback()
        print(e)
        return jsonify({"message": "Update failed"}), 500
    finally:
        db.close()

@app.route('/api/regularization/<int:reg_id>', methods=['DELETE'])
def delete_regularization(reg_id):
    user_id = request.headers.get('X-User-ID')

    db = SessionLocal()
    try:
        reg = db.query(Regularization).filter_by(
            id=reg_id,
            user_id=int(user_id)
        ).first()

        if not reg:
            return jsonify({"message": "Record not found"}), 404

        # Allow deletion regardless of status as per user request
        db.delete(reg)
        db.commit()
        return jsonify({"message": "Regularization deleted"}), 200

    except Exception as e:
        db.rollback()
        print(e)
        return jsonify({"message": "Delete failed"}), 500
    finally:
        db.close()




@app.route('/api/myholidays', methods=['GET'])
def get_holidays():
    """Get holidays from database merged with Indian national/government holidays"""
    db = SessionLocal()
    try:
        year_param = request.args.get('year')
        current_year = int(year_param) if year_param else datetime.now().year

        # ── 1. Comprehensive Indian Government / National Observance Days ──
        #    (Gazetted + widely observed days for the current year)
        NATIONAL_HOLIDAYS = [
            # JANUARY
            {"date": f"{current_year}-01-01",  "title": "New Year's Day",      "type": "National"},
            {"date": f"{current_year}-01-14",  "title": "Pongal / Makar Sankranti", "type": "National"},
            {"date": f"{current_year}-01-15",  "title": "Army Day",            "type": "Observance"},
            {"date": f"{current_year}-01-23",  "title": "Netaji Subhas Chandra Bose Jayanti", "type": "National"},
            {"date": f"{current_year}-01-24",  "title": "National Girl Child Day", "type": "Observance"},
            {"date": f"{current_year}-01-25",  "title": "National Voters' Day","type": "Observance"},
            {"date": f"{current_year}-01-26",  "title": "Republic Day",        "type": "National"},
            {"date": f"{current_year}-01-30",  "title": "Martyrs' Day (Mahatma Gandhi)", "type": "National"},
            # FEBRUARY
            {"date": f"{current_year}-02-04",  "title": "World Cancer Day",    "type": "Observance"},
            {"date": f"{current_year}-02-14",  "title": "Valentine's Day",     "type": "Observance"},
            {"date": f"{current_year}-02-19",  "title": "Chhatrapati Shivaji Maharaj Jayanti", "type": "National"},
            {"date": f"{current_year}-02-20",  "title": "Arunachal Pradesh Statehood Day", "type": "Observance"},
            {"date": f"{current_year}-02-28",  "title": "National Science Day", "type": "Observance"},
            # MARCH
            {"date": f"{current_year}-03-01",  "title": "Holi",               "type": "National"},
            {"date": f"{current_year}-03-04",  "title": "Maha Shivaratri",     "type": "National"},
            {"date": f"{current_year}-03-08",  "title": "International Women's Day", "type": "Observance"},
            {"date": f"{current_year}-03-15",  "title": "World Consumer Rights Day", "type": "Observance"},
            {"date": f"{current_year}-03-22",  "title": "Bihar Diwas / World Water Day", "type": "Observance"},
            {"date": f"{current_year}-03-30",  "title": "Ram Navami",          "type": "National"},
            # APRIL
            {"date": f"{current_year}-04-03",  "title": "Good Friday",         "type": "National"},
            {"date": f"{current_year}-04-05",  "title": "Easter Saturday",     "type": "Observance"},
            {"date": f"{current_year}-04-06",  "title": "Mahavir Jayanti",     "type": "National"},
            {"date": f"{current_year}-04-07",  "title": "World Health Day",    "type": "Observance"},
            {"date": f"{current_year}-04-14",  "title": "Dr. B.R. Ambedkar Jayanti / Tamil New Year", "type": "National"},
            {"date": f"{current_year}-04-22",  "title": "Earth Day",           "type": "Observance"},
            # MAY
            {"date": f"{current_year}-05-01",  "title": "International Labour Day / Maharashtra Day", "type": "National"},
            {"date": f"{current_year}-05-07",  "title": "Rabindranath Tagore Jayanti", "type": "National"},
            {"date": f"{current_year}-05-11",  "title": "National Technology Day", "type": "Observance"},
            {"date": f"{current_year}-05-12",  "title": "International Nurses Day", "type": "Observance"},
            {"date": f"{current_year}-05-31",  "title": "World No Tobacco Day", "type": "Observance"},
            # JUNE
            {"date": f"{current_year}-06-01",  "title": "World Milk Day",      "type": "Observance"},
            {"date": f"{current_year}-06-05",  "title": "World Environment Day", "type": "Observance"},
            {"date": f"{current_year}-06-21",  "title": "International Yoga Day", "type": "National"},
            {"date": f"{current_year}-06-23",  "title": "Rath Yatra",          "type": "National"},
            # JULY
            {"date": f"{current_year}-07-01",  "title": "National Doctor's Day / Chartered Accountants Day", "type": "Observance"},
            {"date": f"{current_year}-07-11",  "title": "World Population Day", "type": "Observance"},
            {"date": f"{current_year}-07-18",  "title": "Nelson Mandela International Day", "type": "Observance"},
            {"date": f"{current_year}-07-26",  "title": "Kargil Vijay Diwas",  "type": "National"},
            # AUGUST
            {"date": f"{current_year}-08-09",  "title": "Quit India Movement Day / Nagasaki Day", "type": "National"},
            {"date": f"{current_year}-08-12",  "title": "International Youth Day", "type": "Observance"},
            {"date": f"{current_year}-08-15",  "title": "Independence Day",    "type": "National"},
            {"date": f"{current_year}-08-19",  "title": "Janmashtami",         "type": "National"},
            {"date": f"{current_year}-08-29",  "title": "National Sports Day (Dhyan Chand Jayanti)", "type": "National"},
            # SEPTEMBER
            {"date": f"{current_year}-09-02",  "title": "Onam",               "type": "National"},
            {"date": f"{current_year}-09-05",  "title": "Teachers' Day (Dr. Radhakrishnan Jayanti)", "type": "National"},
            {"date": f"{current_year}-09-08",  "title": "International Literacy Day", "type": "Observance"},
            {"date": f"{current_year}-09-14",  "title": "Hindi Diwas",         "type": "National"},
            {"date": f"{current_year}-09-16",  "title": "Ganesh Chaturthi",    "type": "National"},
            {"date": f"{current_year}-09-25",  "title": "Antyodaya Diwas (Deendayal Upadhyaya Jayanti)", "type": "Observance"},
            # OCTOBER
            {"date": f"{current_year}-10-02",  "title": "Gandhi Jayanti / Lal Bahadur Shastri Jayanti", "type": "National"},
            {"date": f"{current_year}-10-08",  "title": "Indian Air Force Day", "type": "National"},
            {"date": f"{current_year}-10-11",  "title": "Navratri Begins / Durga Puja",     "type": "National"},
            {"date": f"{current_year}-10-16",  "title": "World Food Day",      "type": "Observance"},
            {"date": f"{current_year}-10-19",  "title": "Ayudha Puja / Maha Navami", "type": "National"},
            {"date": f"{current_year}-10-20",  "title": "Dussehra / Vijayadasami / Saraswati Puja", "type": "National"},
            {"date": f"{current_year}-10-31",  "title": "Sardar Vallabhbhai Patel Jayanti / National Unity Day", "type": "National"},
            # NOVEMBER
            {"date": f"{current_year}-11-08",  "title": "Diwali",             "type": "National"},
            {"date": f"{current_year}-11-09",  "title": "Bhai Dooj",          "type": "National"},
            {"date": f"{current_year}-11-14",  "title": "Children's Day (Nehru Jayanti)", "type": "National"},
            {"date": f"{current_year}-11-17",  "title": "Guru Nanak Jayanti", "type": "National"},
            {"date": f"{current_year}-11-19",  "title": "National Integration Day", "type": "Observance"},
            {"date": f"{current_year}-11-26",  "title": "Constitution Day (Samvidhan Diwas)", "type": "National"},
            # DECEMBER
            {"date": f"{current_year}-12-01",  "title": "World AIDS Day",     "type": "Observance"},
            {"date": f"{current_year}-12-04",  "title": "Indian Navy Day",    "type": "National"},
            {"date": f"{current_year}-12-10",  "title": "Human Rights Day",   "type": "Observance"},
            {"date": f"{current_year}-12-16",  "title": "Vijay Diwas (1971 War Victory)", "type": "National"},
            {"date": f"{current_year}-12-19",  "title": "Goa Liberation Day", "type": "Observance"},
            {"date": f"{current_year}-12-22",  "title": "National Mathematics Day (Ramanujan Jayanti)", "type": "Observance"},
            {"date": f"{current_year}-12-23",  "title": "Kisan Diwas (National Farmers Day)", "type": "National"},
            {"date": f"{current_year}-12-25",  "title": "Christmas Day",      "type": "National"},
        ]

        # Build a date→national_holiday map
        national_map = {}
        for idx, nh in enumerate(NATIONAL_HOLIDAYS):
            try:
                d = datetime.strptime(nh["date"], "%Y-%m-%d").date()
                national_map[nh["date"]] = {
                    "id": f"nat-{idx}",
                    "date": d.strftime('%d %B, %A'),
                    "full_date": nh["date"],
                    "title": nh["title"],
                    "type": nh["type"],
                    "source": "national"
                }
            except Exception:
                pass

        # ── 2. Custom holidays from database ──
        db_holidays = db.query(Holiday).filter(
            Holiday.year == current_year
        ).order_by(Holiday.date).all()

        db_map = {}
        for h in db_holidays:
            date_key = h.date.isoformat()
            holiday_type = "Restricted" if h.is_optional else "Mandatory"
            db_map[date_key] = {
                "id": h.id,
                "date": h.date.strftime('%d %B, %A'),
                "full_date": date_key,
                "title": h.title,
                "type": holiday_type,
                "source": "custom"
            }

        # ── 3. Merge: DB custom holidays override national ones on same date ──
        merged = dict(national_map)
        merged.update(db_map)

        # Sort by date
        holiday_data = sorted(merged.values(), key=lambda x: x["full_date"])

        return jsonify(holiday_data), 200

    except Exception as e:
        print(f"Holidays error: {str(e)}") 
        return jsonify([]), 200
    finally:
        db.close()


@app.route('/api/myholidays', methods=['POST'])
def create_holiday():
    """Create a new holiday"""
    data = request.get_json()
    title = data.get('title')
    date_str = data.get('date') # Expected format 'YYYY-MM-DD'
    holiday_type = data.get('type') # 'Mandatory' or 'Restricted'
    
    if not title or not date_str:
        return jsonify({"message": "Title and date are required"}), 400
        
    db = SessionLocal()
    try:
        holiday_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        year = holiday_date.year
        
        # Check if date already exists
        existing = db.query(Holiday).filter(Holiday.date == holiday_date).first()
        if existing:
            return jsonify({"message": "A holiday already exists on this date"}), 400
            
        new_holiday = Holiday(
            title=title,
            date=holiday_date,
            is_optional=True if holiday_type == 'Restricted' else False,
            year=year
        )
        db.add(new_holiday)
        db.commit()
        db.refresh(new_holiday)
        
        return jsonify({
            "message": "Holiday added successfully",
            "id": new_holiday.id,
            "title": new_holiday.title,
            "date": new_holiday.date.strftime('%d %B, %A')
        }), 201
        
    except Exception as e:
        db.rollback()
        print(f"Error creating holiday: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500
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

@app.route('/api/staff_list', methods=['GET'])
def get_staff_list():
    """Get all users to populate supervisor and HR manager selects"""
    db = SessionLocal()
    try:
        users = db.query(User).all()
        staff = []
        for u in users:
            name = f"{u.first_name or ''} {u.last_name or ''}".strip() or u.username
            staff.append({
                "id": u.id,
                "name": name,
                "role": u.role
            })
        return jsonify(staff), 200
    except Exception as e:
        print(f"Staff list error: {str(e)}")
        return jsonify([]), 200
    finally:
        db.close()

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
                "image": profile.profile_image if profile and profile.profile_image else f"https://ui-avatars.com/api/?name={urllib.parse.quote(name)}&background=random"
            })
        
        return jsonify(employees_data), 200
        
    except Exception as e:
        print(f"Employees list error: {str(e)}")
        return jsonify([]), 200
    finally:
        db.close()


@app.route('/api/employees', methods=['POST'])
def add_employee():
    """Create a new employee (Admin only)"""
    if request.content_type and 'multipart/form-data' in request.content_type:
        data = request.form
    else:
        data = request.get_json() or {}

    # Required validation
    first_name = data.get('firstName')
    last_name = data.get('lastName')
    email = data.get('email')
    emp_id = data.get('employeeId')
    phone = data.get('phone')
    
    if not all([first_name, last_name, email, phone]):
        return jsonify({"message": "Missing required fields"}), 400
        
    db = SessionLocal()
    try:
        # Check if email/username already exists
        username = email.split('@')[0]
        existing_user = db.query(User).filter((User.email == email) | (User.username == username)).first()
        if existing_user:
             return jsonify({"message": "User with this email already exists"}), 400
            
        # ─── Automatic Employee ID Generation ───
        if not emp_id or emp_id.strip() == "":
            try:
                # Find the maximum numeric emp_id in profiles
                all_ids = db.query(EmployeeProfile.emp_id).all()
                max_numeric_id = 1000  # Default floor
                for (eid,) in all_ids:
                    if eid and eid.isdigit():
                        max_numeric_id = max(max_numeric_id, int(eid))
                emp_id = str(max_numeric_id + 1)
            except Exception as e:
                print(f"Error generating emp_id: {str(e)}")
                # Falling back to a timestamp-based ID or just letting it error if critical
                emp_id = str(int(datetime.now().timestamp()))
        
        # Now check if this generated or provided emp_id exists
        existing_profile = db.query(EmployeeProfile).filter(EmployeeProfile.emp_id == emp_id).first()
        if existing_profile:
             return jsonify({"message": f"Employee ID {emp_id} already exists. Please enter a unique ID manually."}), 400

        # Create User
        from werkzeug.security import generate_password_hash
        # Use email prefix + "123" as the default password
        generated_password = f"{username}123"
        default_password = generate_password_hash(generated_password)
        new_user = User(
            username=username,
            password_hash=default_password,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role='employee',
            phone=phone
        )
        db.add(new_user)
        db.flush() 
        
        # Create Employee Profile
        from datetime import datetime
        dob_date = None
        if data.get('dob'):
             try: dob_date = datetime.strptime(data['dob'], '%Y-%m-%d').date()
             except: pass
             
        joining_date = None
        if data.get('joiningDate'):
             try: joining_date = datetime.strptime(data['joiningDate'], '%Y-%m-%d').date()
             except: pass

        edu_start_date = None
        if data.get('eduStartDate'):
             try: edu_start_date = datetime.strptime(data['eduStartDate'], '%Y-%m-%d').date()
             except: pass

        edu_end_date = None
        if data.get('eduEndDate'):
             try: edu_end_date = datetime.strptime(data['eduEndDate'], '%Y-%m-%d').date()
             except: pass

        # Get supervisor_id and hr_manager_id if names are provided (simplified lookup)
        def get_user_id_by_name(name):
             if not name: return None
             parts = name.split()
             f_name = parts[0] if len(parts) > 0 else ""
             l_name = parts[1] if len(parts) > 1 else ""
             u = db.query(User).filter(User.first_name == f_name, User.last_name == l_name).first()
             return u.id if u else None

        # File handling
        profile_image_url = None
        if 'profileImage' in request.files:
            file = request.files['profileImage']
            if file and file.filename != '':
                import base64
                file_content = file.read()
                base64_encoded = base64.b64encode(file_content).decode('utf-8')
                mime_type = file.content_type if file.content_type else 'image/png'
                profile_image_url = f"data:{mime_type};base64,{base64_encoded}"

        new_profile = EmployeeProfile(
            user_id=new_user.id,
            emp_id=emp_id,
            gender=data.get('gender'),
            dob=dob_date,
            marital_status=data.get('maritalStatus'),
            emp_type=data.get('employmentType'),
            department=data.get('department'),
            position=data.get('designation'),
            status=data.get('status', 'Active'),
            joining_date=joining_date,
            # Supervisor / HR (assuming we pass names for now, but ID is better)
            supervisor_id=get_user_id_by_name(data.get('supervisor')),
            hr_manager_id=get_user_id_by_name(data.get('hrManager')),
            # Education
            institution=data.get('institution'),
            qualification=data.get('course'),
            specialization=data.get('specialization'),
            edu_start_date=edu_start_date,
            edu_end_date=edu_end_date,
            skills=data.get('skills'),
            portfolio=data.get('portfolioLink'),
            blood_group=data.get('bloodGroup'),
            profile_image=profile_image_url
        )
        db.add(new_profile)
        db.commit()
        
        return jsonify({"message": "Employee added successfully", "id": new_user.id}), 201
        
    except Exception as e:
        db.rollback()
        print(f"Error adding employee: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@app.route('/api/employees/<int:user_id>', methods=['PUT'])
def update_employee(user_id):
    if request.content_type and 'multipart/form-data' in request.content_type:
        data = request.form
    else:
        data = request.get_json() or {}
        
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return jsonify({"message": "User not found"}), 404
            
        profile = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == user_id).first()
        if not profile:
            # Auto-create an empty profile so we can continue with the update
            profile = EmployeeProfile(user_id=user_id)
            db.add(profile)
            db.flush()  # get the ID assigned without full commit yet

        # Update User fields
        user.first_name = data.get('firstName', user.first_name)
        user.last_name = data.get('lastName', user.last_name)
        user.email = data.get('email', user.email)
        user.phone = data.get('phone', user.phone)
        
        # Date parsing helper
        from datetime import datetime
        def parse_date(date_str):
            if not date_str: return None
            try: return datetime.strptime(date_str, '%Y-%m-%d').date()
            except: return None

        # Manager lookup helper
        def get_user_id_by_name(name):
            if not name: return None
            parts = name.split()
            f_name = parts[0] if len(parts) > 0 else ""
            l_name = parts[1] if len(parts) > 1 else ""
            u = db.query(User).filter(User.first_name == f_name, User.last_name == l_name).first()
            return u.id if u else None

        # Update Profile fields
        profile.emp_id = data.get('employeeId', profile.emp_id)
        profile.gender = data.get('gender', profile.gender)
        profile.dob = parse_date(data.get('dob'))
        profile.marital_status = data.get('maritalStatus', profile.marital_status)
        profile.emp_type = data.get('employmentType', profile.emp_type)
        profile.department = data.get('department', profile.department)
        profile.position = data.get('designation', profile.position)
        profile.status = data.get('status', 'Active')
        profile.joining_date = parse_date(data.get('joiningDate'))
        
        if data.get('supervisor'):
            profile.supervisor_id = get_user_id_by_name(data.get('supervisor'))
        if data.get('hrManager'):
            profile.hr_manager_id = get_user_id_by_name(data.get('hrManager'))

        # Education
        profile.institution = data.get('institution', profile.institution)
        profile.qualification = data.get('course', profile.qualification)
        profile.specialization = data.get('specialization', profile.specialization)
        profile.edu_start_date = parse_date(data.get('eduStartDate'))
        profile.edu_end_date = parse_date(data.get('eduEndDate'))
        profile.skills = data.get('skills', profile.skills)
        profile.portfolio = data.get('portfolioLink', profile.portfolio)
        profile.blood_group = data.get('bloodGroup', profile.blood_group)

        if 'profileImage' in request.files:
            file = request.files['profileImage']
            if file and file.filename != '':
                import base64
                file_content = file.read()
                base64_encoded = base64.b64encode(file_content).decode('utf-8')
                mime_type = file.content_type if file.content_type else 'image/png'
                profile.profile_image = f"data:{mime_type};base64,{base64_encoded}"

        db.commit()
        return jsonify({"message": "Employee updated successfully"}), 200
        
    except Exception as e:
        db.rollback()
        print(f"Error updating employee: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()

# Redundant endpoint removed. Using get_admin_profile_data instead.




# datas for attendance page in admin section
@app.route('/api/attendancelist', methods=['GET'])
def get_admin_attendance_data():
    """Get all attendance records for admin view with filtering"""
    db = SessionLocal()
    try:
        # Get filter parameters from request
        name_filter = request.args.get('name', '').strip()
        status_filter = request.args.get('status', 'All').strip()
        days_filter = request.args.get('days')
        from_date_str = request.args.get('from_date')
        to_date_str = request.args.get('to_date')
        sort_order = request.args.get('order', 'newest')
        
        print(f"DEBUG Attendance Filter: name={name_filter}, status={status_filter}, days={days_filter}, from={from_date_str}, to={to_date_str}")
        
        # Base query
        query = db.query(Attendance, User).join(
            User, Attendance.user_id == User.id
        )
        
        # Apply Name Filter (Full Phrase Search)
        if name_filter:
            search_pattern = f"%{name_filter}%"
            # Search in username or concatenated "first_name last_name"
            # This ensures "praga D" matches "Praga D" but NOT "Pragadeeshwari D"
            query = query.filter(
                (User.username.ilike(search_pattern)) | 
                (func.concat(func.coalesce(User.first_name, ''), ' ', func.coalesce(User.last_name, '')).ilike(search_pattern))
            )
            
        # Apply Status Filter
        if status_filter and status_filter != 'All':
            # Use ilike for status as well to handle minor case differences
            query = query.filter(Attendance.status.ilike(status_filter))
            
        # Apply Date Range Filter (From/To takes precedence)
        if from_date_str:
            try:
                from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
                query = query.filter(Attendance.date >= from_date)
            except ValueError:
                pass
                
        if to_date_str:
            try:
                to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
                query = query.filter(Attendance.date <= to_date)
            except ValueError:
                pass
        elif days_filter:
            # Apply "Last N Days" filter if no specific date range
            try:
                num_days = int(days_filter)
                start_date = date.today() - timedelta(days=num_days)
                query = query.filter(Attendance.date >= start_date)
            except (ValueError, TypeError):
                pass
        
        # Execute query
        if sort_order == 'oldest':
            query = query.order_by(Attendance.date.asc())
        else:
            query = query.order_by(Attendance.date.desc())
            
        attendance_records = query.all()
        
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
                "date": att.date.strftime('%d %b %Y') if att.date else "",
                "checkIn": att.check_in.strftime('%H:%M') if att.check_in else "00:00",
                "checkOut": att.check_out.strftime('%H:%M') if att.check_out else "00:00",
                "workHours": att.work_hours or "0h 0m"
            })
        
        return jsonify(attendance_data), 200
        
    except Exception as e:
        print(f"Admin attendance error: {str(e)}")
        import traceback
        traceback.print_exc()
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
            
            # Calculate display duration for robustness (especially for half-days)
            actual_days = (req.end_date - req.start_date).days + 1
            if req.day_type == 'half_day':
                display_days = actual_days * 0.5
            else:
                display_days = float(actual_days)
                
            leave_approval_data.append({
                "name": name,
                "id": emp_id,
                "type": leave_type.name,
                "from": req.start_date.strftime('%d-%m-%Y'),
                "to": req.end_date.strftime('%d-%m-%Y'),
                "days": f"{display_days} Day(s)",
                "session": "Half Day" if req.day_type == "half_day" else "Full Day",
                "dates": f"{req.start_date.strftime('%d-%m-%Y')}/{'Half Day' if req.day_type == 'half_day' else 'Full Day'}",
                "requestDate": req.applied_date.strftime('%d-%m-%Y') if req.applied_date else "",
                "notify": "HR Head",
                "document": "",
                "reason": req.reason or "",
                "status": req.status.capitalize() if req.status else "Pending",
                "image": profile.profile_image if profile and profile.profile_image else f"https://ui-avatars.com/api/?name={urllib.parse.quote(name)}&background=random",
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
                "createdOn": lt.created_at.strftime("%d %b %Y") if lt.created_at else "",  # Add created_at to LeaveType model if needed
                "type": lt.type,
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

@app.route('/api/leavepolicies/<int:leave_id>', methods=['PUT'])
def update_leave_policy(leave_id):
    db = SessionLocal()
    try:
        data = request.json

        leave_type = db.query(LeaveType).filter(LeaveType.id == leave_id).first()
        if not leave_type:
            return jsonify({"message": "Leave policy not found"}), 404

        # Update fields only if provided
        leave_type.name = data.get("name", leave_type.name)
        leave_type.description = data.get("description", leave_type.description)
        leave_type.max_days_per_year = data.get("max_days", leave_type.max_days_per_year)
        leave_type.type = data.get("type", leave_type.type)

        db.commit()

        return jsonify({"message": "Leave policy updated successfully"}), 200

    except Exception as e:
        db.rollback()
        print("Update error:", str(e))
        return jsonify({"message": "Failed to update leave policy"}), 500
    finally:
        db.close()

@app.route('/api/leavepolicies/<int:leave_id>', methods=['DELETE'])
def delete_leave_policy(leave_id):
    db = SessionLocal()
    try:
        leave_type = db.query(LeaveType).filter(LeaveType.id == leave_id).first()
        if not leave_type:
            return jsonify({"message": "Leave policy not found"}), 404

        db.delete(leave_type)
        db.commit()

        return jsonify({"message": "Leave policy deleted successfully"}), 200

    except Exception as e:
        db.rollback()
        print("Delete error:", str(e))
        return jsonify({"message": "Failed to delete leave policy"}), 500
    finally:
        db.close()

@app.route('/api/leavepolicies', methods=['POST'])
def create_leave_policy():
    db = SessionLocal()
    try:
        data = request.json

        # ---------- Validation ----------
        name = data.get("name")
        max_days = data.get("max_days")

        if not name:
            return jsonify({"message": "Leave name is required"}), 400

        if not max_days or int(max_days) <= 0:
            return jsonify({"message": "Max days must be greater than 0"}), 400

        # ---------- Create record ----------
        leave_type = LeaveType(
            name=name,
            description=data.get("description"),
            max_days_per_year=int(max_days),
            type=data.get("type", "All")  # 👈 already built in frontend
        )

        db.add(leave_type)
        db.commit()
        db.refresh(leave_type)

        # ---------- Response ----------
        return jsonify({
            "id": leave_type.id,
            "name": leave_type.name,
            "createdOn": leave_type.created_at.strftime("%d %b %Y") if leave_type.created_at else "",
            "type": leave_type.type,
            "max_days": leave_type.max_days_per_year,
            "description": leave_type.description or ""
        }), 201

    except Exception as e:
        db.rollback()
        print("Create error:", str(e))
        return jsonify({"message": "Failed to create leave policy"}), 500

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
            TeamMember.manager_id == int(user_id)
        ).all()
        
        member_ids = [tm.member_id for tm in team_members]
        
        if not member_ids:
            # If no team members defined, return all leave requests for admin
            user_role = request.headers.get('X-User-Role', '')
            if user_role == 'admin':
                # Admin sees all leave requests
                requests_data = db.query(LeaveRequest, User, LeaveType).join(
                    User, LeaveRequest.user_id == User.id
                ).join(
                    LeaveType, LeaveRequest.leave_type_id == LeaveType.id
                ).order_by(LeaveRequest.applied_date.desc()).all()
                
                my_team_la = []
                for idx, (req, user, leave_type) in enumerate(requests_data, 1):
                    profile = db.query(EmployeeProfile).filter(
                        EmployeeProfile.user_id == user.id
                    ).first()
                    
                    name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username
                    emp_id = profile.emp_id if profile and profile.emp_id else str(user.id)
                    image = profile.profile_image if profile and profile.profile_image else f"https://ui-avatars.com/api/?name={urllib.parse.quote(name)}&background=random"
                    
                    # Calculate display duration for robustness (especially for half-days)
                    actual_days = (req.end_date - req.start_date).days + 1
                    if req.day_type == 'half_day':
                        display_days = actual_days * 0.5
                    else:
                        display_days = float(actual_days)
                    
                    my_team_la.append({
                        "id": req.id,
                        "name": name,
                        "empId": emp_id,
                        "type": leave_type.name,
                        "from": req.start_date.strftime('%d-%m-%Y'),
                        "to": req.end_date.strftime('%d-%m-%Y'),
                        "days": f"{display_days} Day(s)",
                        "session": "Half Day" if req.day_type == "half_day" else "Full Day",
                        "date": f"{req.start_date.strftime('%d-%m-%Y')}/{'Half Day' if req.day_type == 'half_day' else 'Full Day'}",
                        "request": req.applied_date.strftime('%d-%m-%Y') if req.applied_date else "",
                        "notify": "HR Head",
                        "document": "",
                        "reason": req.reason or "",
                        "status": req.status.capitalize() if req.status else "Pending",
                        "image": image
                    })
                
                return jsonify(my_team_la), 200
            else:
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
            image = profile.profile_image if profile and profile.profile_image else f"https://ui-avatars.com/api/?name={urllib.parse.quote(name)}&background=random"
            
            # Calculate display duration for robustness (especially for half-days)
            actual_days = (req.end_date - req.start_date).days + 1
            if req.day_type == 'half_day':
                display_days = actual_days * 0.5
            else:
                display_days = float(actual_days)
            
            my_team_la.append({
                "id": req.id,
                "name": name,
                "empId": emp_id,
                "type": leave_type.name,
                "from": req.start_date.strftime('%d-%m-%Y'),
                "to": req.end_date.strftime('%d-%m-%Y'),
                "days": f"{display_days} Day(s)",
                "session": "Half Day" if req.day_type == "half_day" else "Full Day",
                "date": f"{req.start_date.strftime('%d-%m-%Y')}/{'Half Day' if req.day_type == 'half_day' else 'Full Day'}",
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
            TeamMember.manager_id == int(user_id)
        ).all()
        
        member_ids = [tm.member_id for tm in team_members]

        # Fallback: also include employees who have this user as their supervisor_id
        if user_id:
            supervisor_members = db.query(EmployeeProfile).filter(
                EmployeeProfile.supervisor_id == int(user_id)
            ).all()
            supervisor_ids = [ep.user_id for ep in supervisor_members]
            member_ids = list(set(member_ids + supervisor_ids))

        if not member_ids:
            # Admin fallback: admin with no team sees all regularizations
            user_role = request.headers.get('X-User-Role', '')
            if user_role == 'admin':
                requests_data = db.query(Regularization, User).join(
                    User, Regularization.user_id == User.id
                ).order_by(Regularization.request_date.desc()).all()
            else:
                return jsonify([]), 200
        else:
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
            image = profile.profile_image if profile and profile.profile_image else f"https://ui-avatars.com/api/?name={urllib.parse.quote(name)}&background=random"
            
            session_str = req.session_type or "Full Day"
            
            approver_name = ""
            if req.approved_by:
                approver = db.query(User).filter(User.id == req.approved_by).first()
                if approver:
                    approver_name = f"{approver.first_name or ''} {approver.last_name or ''}".strip() or approver.username

            my_team_ra.append({
                "id": req.id,
                "name": name,
                "empId": emp_id,
                "regDate": f"{req.date.strftime('%d-%m-%Y')}/{session_str}",
                "attendance": req.attendance_type or "Present",
                "requestDate": req.request_date.strftime('%d-%m-%Y') if req.request_date else "",
                "status": req.status.capitalize() if req.status else "Pending",
                "img": image,

                # ADD THESE
                "reason": req.reason or "",
                "approvedBy": approver_name,
                "approvalReason": req.approval_reason or "",
                "rejectionReason": req.rejection_reason or ""
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
            image = profile.profile_image if profile and profile.profile_image else f"https://ui-avatars.com/api/?name={urllib.parse.quote(name)}&background=random"
            
            session_str = req.session_type or "Full Day"
            
            approver_name = ""
            if req.approved_by:
                approver = db.query(User).filter(User.id == req.approved_by).first()
                if approver:
                    approver_name = f"{approver.first_name or ''} {approver.last_name or ''}".strip() or approver.username

            regularization_approval.append({
                "id": req.id,
                "name": name,
                "empId": emp_id,
                "regDate": f"{req.date.strftime('%d-%m-%Y')}/{session_str}",
                "attendance": req.attendance_type or "Present",
                "requestDate": req.request_date.strftime('%d-%m-%Y') if req.request_date else "",
                "status": req.status.capitalize() if req.status else "Pending",
                "img": image,
                "reason": req.reason or "",
                "approvedBy": approver_name,
                "approvalReason": req.approval_reason or "",
                "rejectionReason": req.rejection_reason or ""
            })
        
        return jsonify(regularization_approval), 200
        
    except Exception as e:
        print(f"Regularization approval error: {str(e)}")
        return jsonify([]), 200
    finally:
        db.close()


@app.route('/api/admin/regularization/<int:request_id>', methods=['PUT', 'PATCH', 'OPTIONS'])
@custom_admin_required()
def update_regularization_status(request_id):
    """Update regularization status (Approve/Reject)"""
    data = request.get_json() or {}
    status = data.get('status', '').lower()
    reason = data.get('reason', '')
    approver_id = request.headers.get('X-User-ID')
    
    if status not in ['approved', 'rejected']:
        return jsonify({"message": "Invalid status"}), 400
        
    db = SessionLocal()
    try:
        req = db.query(Regularization).filter(Regularization.id == request_id).first()
        if not req:
            return jsonify({"message": "Request not found"}), 404
            
        req.status = status
        if status == 'approved':
            req.approval_reason = reason
        else:
            req.rejection_reason = reason

        if approver_id:
            try:
                req.approved_by = int(approver_id)
            except ValueError:
                pass
        req.approval_date = datetime.utcnow()
        db.commit()

        # Create Notification
        try:
            notif_title = f"Regularization Request {status.capitalize()}"
            notif_message = f"Your regularization request for {req.date} has been {status}."
            if reason:
                notif_message += f" Reason: {reason}"
                
            new_notif = Notification(
                user_id=req.user_id,
                title=notif_title,
                message=notif_message,
                notification_type="attendance",
                link="/employee/my-regularization"
            )
            db.add(new_notif)
            db.commit()
            print(f"DEBUG: Created regularization notification for user {req.user_id} (Status: {status})")
        except Exception as notif_err:
            print(f"Error creating regularization notification: {notif_err}")
            # Don't fail the main request if notification fails

        return jsonify({"message": f"Regularization {status} successfully"}), 200
        
    except Exception as e:
        db.rollback()
        print(f"Error updating regularization: {str(e)}")
        return jsonify({"message": str(e)}), 500
    finally:
        db.close()


#Mansoor code added 

# --- Admin Profile Endpoint ---
@app.route('/admin_profile/<int:user_id>', methods=['GET'])
@custom_user_required()
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
        
        # Fetch employee profile data
        emp_profile = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == user_id).first()
        
        # Parse skills from JSON string if stored
        # JUST RETURN AS PLAIN STRING
        skills_list = emp_profile.skills if emp_profile and emp_profile.skills else ""
        
        # Get supervisor name
        supervisor_name = ""
        if emp_profile and emp_profile.supervisor:
            supervisor_user = emp_profile.supervisor
            supervisor_name = (
                f"{supervisor_user.first_name or ''} {supervisor_user.last_name or ''}"
            ).strip() or supervisor_user.username

        # Get HR manager name
        hr_manager_name = ""
        if emp_profile and emp_profile.hr_manager:
            hr_user = emp_profile.hr_manager
            hr_manager_name = (
                f"{hr_user.first_name or ''} {hr_user.last_name or ''}"
            ).strip() or hr_user.username

        
        # Prepare docs data
        docs_data = []
        documents_list = db.query(Document).filter(Document.user_id == user_id).all()
        for doc in documents_list:
            docs_data.append({
                "id": doc.id,
                "fileName": doc.file_name,
                "type": doc.document_type,
                "size": str(doc.file_size // 1024) if doc.file_size else "0",
                "status": "Completed" if doc.is_verified else "Uploaded"
            })

        # Return data from database
        admin_profile_data = {
            "profile": {
                "profileImage": emp_profile.profile_image if emp_profile and emp_profile.profile_image else "",
                "profile_image": emp_profile.profile_image if emp_profile and emp_profile.profile_image else "",
                "name": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
                "first_name": user.first_name or (user.username.split()[0] if user.username else ""),
                "last_name": user.last_name or (user.username.split()[1] if user.username and len(user.username.split()) > 1 else ""),
                "gender": emp_profile.gender if emp_profile and emp_profile.gender else "",
                "dob": emp_profile.dob.strftime('%Y-%m-%d') if emp_profile and emp_profile.dob else "",
                "maritalStatus": emp_profile.marital_status if emp_profile and emp_profile.marital_status else "",
                "nationality": emp_profile.nationality if emp_profile and emp_profile.nationality else "",
                "bloodGroup": emp_profile.blood_group if emp_profile and emp_profile.blood_group else "",
                "email": user.email or "",
                "phone": user.phone or "",
                "address": emp_profile.address if emp_profile and emp_profile.address else "",
                "emergencyContactNumber": emp_profile.emergency_contact if emp_profile and emp_profile.emergency_contact else "",
                "relationship": emp_profile.emergency_relationship if emp_profile and emp_profile.emergency_relationship else "",
                "empType": emp_profile.emp_type if emp_profile and emp_profile.emp_type else "",
                "department": emp_profile.department if emp_profile and emp_profile.department else "",
                "location": emp_profile.location if emp_profile and emp_profile.location else "",
                "supervisor": supervisor_name,
                "hrManager": hr_manager_name,
                "supervisor_id": emp_profile.supervisor_id if emp_profile else None,
                "hr_manager_id": emp_profile.hr_manager_id if emp_profile else None,
                "empId": emp_profile.emp_id if emp_profile and emp_profile.emp_id else str(user.id),
                "id": user.id,
                "joiningDate": emp_profile.joining_date.strftime('%Y-%m-%d') if emp_profile and emp_profile.joining_date else "",
                "status": emp_profile.status if emp_profile and emp_profile.status else "Active",
                "position": emp_profile.position if emp_profile and emp_profile.position else "",
            },
            "education": {
                "institution": emp_profile.institution if emp_profile and emp_profile.institution else "",
                "location": emp_profile.edu_location if emp_profile and emp_profile.edu_location else "",
                "eduStartDate": emp_profile.edu_start_date.strftime('%Y-%m-%d') if emp_profile and emp_profile.edu_start_date else "",
                "eduEndDate": emp_profile.edu_end_date.strftime('%Y-%m-%d') if emp_profile and emp_profile.edu_end_date else "",
                "qualification": emp_profile.qualification if emp_profile and emp_profile.qualification else "",
                "specialization": emp_profile.specialization if emp_profile and emp_profile.specialization else "",
                "skills": skills_list,
                "portfolio": emp_profile.portfolio if emp_profile and emp_profile.portfolio else ""
            },
            "experience": {
                "company": emp_profile.prev_company if emp_profile and emp_profile.prev_company else "",
                "jobTitle": emp_profile.prev_job_title if emp_profile and emp_profile.prev_job_title else "",
                "expStartDate": emp_profile.exp_start_date.strftime('%Y-%m-%d') if emp_profile and emp_profile.exp_start_date else "",
                "expEndDate": emp_profile.exp_end_date.strftime('%Y-%m-%d') if emp_profile and emp_profile.exp_end_date else "",
                "responsibilities": emp_profile.responsibilities if emp_profile and emp_profile.responsibilities else "",
                "totalYears": str(emp_profile.total_experience_years) if emp_profile and emp_profile.total_experience_years else ""
            },
            "bank": {
                "bankName": emp_profile.bank_name if emp_profile and emp_profile.bank_name else "",
                "branch": emp_profile.bank_branch if emp_profile and emp_profile.bank_branch else "",
                "accountNumber": emp_profile.account_number if emp_profile and emp_profile.account_number else "",
                "ifsc": emp_profile.ifsc_code if emp_profile and emp_profile.ifsc_code else "",
                "aadhaar": emp_profile.aadhaar_number if emp_profile and emp_profile.aadhaar_number else "",
                "pan": emp_profile.pan_number if emp_profile and emp_profile.pan_number else ""
            },
            "documents": docs_data
        }
        
        return jsonify(admin_profile_data), 200
    except Exception as e:
        if db:
            db.rollback()
        print(f"Error getting admin profile: {str(e)}")
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500
    finally:
        if db:
            db.close()


# --- Employee Profile Endpoint ---
@app.route('/employee_profile/<int:user_id>', methods=['GET'])
@jwt_required()
def get_employee_profile_data(user_id):
    """
    Returns employee profile data for the specified user from database.
    """
    # Check if the requesting user is accessing their own profile
    current_user_id = request.user_id
    if current_user_id != user_id and request.user_role != 'admin':
        return jsonify({"message": "Unauthorized to view this profile."}), 403
    
    db = None
    try:
        db = SessionLocal()
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            return jsonify({"message": "User not found"}), 404
            
        profile = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == user_id).first()
        documents_list = db.query(Document).filter(Document.user_id == user_id).all()
        
        # Format profile data
        profile_data = {
            "profileImage": profile.profile_image if profile else "",
            "name": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
            "gender": profile.gender if profile else "",
            "dob": profile.dob.strftime('%Y-%m-%d') if profile and profile.dob else "",
            "maritalStatus": profile.marital_status if profile else "",
            "nationality": profile.nationality if profile else "",
            "bloodGroup": profile.blood_group if profile else "",
            "email": user.email or "",
            "phone": user.phone or "",
            "address": profile.address if profile else "",
            "emergencyContactNumber": profile.emergency_contact if profile else "",
            "relationship": profile.emergency_relationship if profile else "",
            "empType": profile.emp_type if profile else "",
            "department": profile.department if profile else "",
            "location": profile.location if profile else "",
            "supervisor": profile.supervisor_id if profile else "",
            "hrManager": profile.hr_manager_id if profile else "",
            "empId": profile.emp_id if profile and profile.emp_id else str(user.id),
            "status": profile.status if profile else "Active"
        }
        
        education_data = {
            "institution": profile.institution if profile else "",
            "location": profile.edu_location if profile else "",
            "startDate": profile.edu_start_date.strftime('%Y-%m-%d') if profile and profile.edu_start_date else "",
            "endDate": profile.edu_end_date.strftime('%Y-%m-%d') if profile and profile.edu_end_date else "",
            "qualification": profile.qualification if profile else "",
            "specialization": profile.specialization if profile else "",
            "skills": profile.skills.split(',') if profile and profile.skills else [],
            "portfolio": profile.portfolio if profile else ""
        }
        
        experience_data = {
            "company": profile.prev_company if profile else "",
            "jobTitle": profile.prev_job_title if profile else "",
            "startDate": profile.exp_start_date.strftime('%Y-%m-%d') if profile and profile.exp_start_date else "",
            "endDate": profile.exp_end_date.strftime('%Y-%m-%d') if profile and profile.exp_end_date else "",
            "responsibilities": profile.responsibilities if profile else "",
            "totalYears": str(profile.total_experience_years) if profile and profile.total_experience_years else ""
        }
        
        bank_data = {
            "bankName": profile.bank_name if profile else "",
            "branch": profile.bank_branch if profile else "",
            "accountNumber": profile.account_number if profile else "",
            "ifsc": profile.ifsc_code if profile else "",
            "aadhaar": profile.aadhaar_number if profile else "",
            "pan": profile.pan_number if profile else ""
        }
        
        docs_data = []
        for doc in documents_list:
            docs_data.append({
                "id": doc.id,
                "fileName": doc.file_name,
                "type": doc.document_type,
                "size": str(doc.file_size // 1024) if doc.file_size else "0",
                "status": "Completed" if doc.is_verified else "Uploaded"
            })
        
        # Fetch employee profile data from database
        emp_profile = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == user_id).first()
        
        # Parse skills from JSON string if stored
        skills_list = emp_profile.skills if emp_profile and emp_profile.skills else ""
        
        # Get supervisor name
        supervisor_name = ""
        if emp_profile and emp_profile.supervisor:
            supervisor_user = emp_profile.supervisor
            supervisor_name = (
                f"{supervisor_user.first_name or ''} {supervisor_user.last_name or ''}"
            ).strip() or supervisor_user.username

        # Get HR manager name
        hr_manager_name = ""
        if emp_profile and emp_profile.hr_manager:
            hr_user = emp_profile.hr_manager
            hr_manager_name = (
                f"{hr_user.first_name or ''} {hr_user.last_name or ''}"
            ).strip() or hr_user.username
        
        # Return data from database
        employee_profile_data = {
            "profile": {
                "profileImage": emp_profile.profile_image if emp_profile and emp_profile.profile_image else "",
                "name": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
                "gender": emp_profile.gender if emp_profile and emp_profile.gender else "",
                "dob": emp_profile.dob.strftime('%Y-%m-%d') if emp_profile and emp_profile.dob else "",
                "maritalStatus": emp_profile.marital_status if emp_profile and emp_profile.marital_status else "",
                "nationality": emp_profile.nationality if emp_profile and emp_profile.nationality else "",
                "bloodGroup": emp_profile.blood_group if emp_profile and emp_profile.blood_group else "",
                "email": user.email or "",
                "phone": user.phone or "",
                "address": emp_profile.address if emp_profile and emp_profile.address else "",
                "emergencyContactNumber": emp_profile.emergency_contact if emp_profile and emp_profile.emergency_contact else "",
                "relationship": emp_profile.emergency_relationship if emp_profile and emp_profile.emergency_relationship else "",
                "empType": emp_profile.emp_type if emp_profile and emp_profile.emp_type else "",
                "department": emp_profile.department if emp_profile and emp_profile.department else "",
                "location": emp_profile.location if emp_profile and emp_profile.location else "",
                "supervisor": supervisor_name,
                "hrManager": hr_manager_name,
                "supervisor_id": emp_profile.supervisor_id if emp_profile else None,
                "hr_manager_id": emp_profile.hr_manager_id if emp_profile else None,
                "empId": emp_profile.emp_id if emp_profile and emp_profile.emp_id else str(user.id),
                "status": emp_profile.status if emp_profile and emp_profile.status else "Active",
                "position": emp_profile.position if emp_profile and emp_profile.position else "",
            },
            "education": {
                "institution": emp_profile.institution if emp_profile and emp_profile.institution else "",
                "location": emp_profile.edu_location if emp_profile and emp_profile.edu_location else "",
                "eduStartDate": emp_profile.edu_start_date.strftime('%Y-%m-%d') if emp_profile and emp_profile.edu_start_date else "",
                "eduEndDate": emp_profile.edu_end_date.strftime('%Y-%m-%d') if emp_profile and emp_profile.edu_end_date else "",
                "qualification": emp_profile.qualification if emp_profile and emp_profile.qualification else "",
                "specialization": emp_profile.specialization if emp_profile and emp_profile.specialization else "",
                "skills": skills_list,
                "portfolio": emp_profile.portfolio if emp_profile and emp_profile.portfolio else ""
            },
            "experience": {
                "company": emp_profile.prev_company if emp_profile and emp_profile.prev_company else "",
                "jobTitle": emp_profile.prev_job_title if emp_profile and emp_profile.prev_job_title else "",
                "expStartDate": emp_profile.exp_start_date.strftime('%Y-%m-%d') if emp_profile and emp_profile.exp_start_date else "",
                "expEndDate": emp_profile.exp_end_date.strftime('%Y-%m-%d') if emp_profile and emp_profile.exp_end_date else "",
                "responsibilities": emp_profile.responsibilities if emp_profile and emp_profile.responsibilities else "",
                "totalYears": str(emp_profile.total_experience_years) if emp_profile and emp_profile.total_experience_years else ""
            },
            "bank": {
                "bankName": emp_profile.bank_name if emp_profile and emp_profile.bank_name else "",
                "branch": emp_profile.bank_branch if emp_profile and emp_profile.bank_branch else "",
                "accountNumber": emp_profile.account_number if emp_profile and emp_profile.account_number else "",
                "ifsc": emp_profile.ifsc_code if emp_profile and emp_profile.ifsc_code else "",
                "aadhaar": emp_profile.aadhaar_number if emp_profile and emp_profile.aadhaar_number else "",
                "pan": emp_profile.pan_number if emp_profile and emp_profile.pan_number else ""
            },
            "documents": docs_data
        }
        
        return jsonify(employee_profile_data), 200
    except Exception as e:
        if db:
            db.rollback()
        print(f"Error getting employee profile: {str(e)}")
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
    """Update employee profile with nested content"""
    data = request.get_json()
    db = SessionLocal()
    try:
        profile = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == user_id).first()
        
        if not profile:
            profile = EmployeeProfile(user_id=user_id)
            db.add(profile)
        
        # Update Personal Profile
        if 'profile' in data:
            p = data['profile']
            if 'gender' in p: profile.gender = p['gender']
            if 'dob' in p and p['dob']: profile.dob = datetime.strptime(p['dob'], '%Y-%m-%d').date()
            if 'maritalStatus' in p: profile.marital_status = p['maritalStatus']
            if 'nationality' in p: profile.nationality = p['nationality']
            if 'bloodGroup' in p: profile.blood_group = p['bloodGroup']
            if 'address' in p: profile.address = p['address']
            if 'emergencyContactNumber' in p: profile.emergency_contact = p['emergencyContactNumber']
            if 'relationship' in p: profile.emergency_relationship = p['relationship']
            if 'empType' in p: profile.emp_type = p['empType']
            if 'department' in p: profile.department = p['department']
            if 'location' in p: profile.location = p['location']
            if 'status' in p: profile.status = p['status']
            if 'profileImage' in p: profile.profile_image = p['profileImage']
            if 'empId' in p: profile.emp_id = p['empId']

        # Update Education
        if 'education' in data:
            e = data['education']
            if 'institution' in e: profile.institution = e['institution']
            if 'location' in e: profile.edu_location = e['location']
            if 'startDate' in e and e['startDate']: profile.edu_start_date = datetime.strptime(e['startDate'], '%Y-%m-%d').date()
            if 'endDate' in e and e['endDate']: profile.edu_end_date = datetime.strptime(e['endDate'], '%Y-%m-%d').date()
            if 'qualification' in e: profile.qualification = e['qualification']
            if 'specialization' in e: profile.specialization = e['specialization']
            if 'skills' in e: 
                skills = e['skills']
                if isinstance(skills, list):
                    profile.skills = ','.join(skills)
                else:
                    profile.skills = str(skills)
            if 'portfolio' in e: profile.portfolio = e['portfolio']

        # Update Experience
        if 'experience' in data:
            ex = data['experience']
            if 'company' in ex: profile.prev_company = ex['company']
            if 'jobTitle' in ex: profile.prev_job_title = ex['jobTitle']
            if 'startDate' in ex and ex['startDate']: profile.exp_start_date = datetime.strptime(ex['startDate'], '%Y-%m-%d').date()
            if 'endDate' in ex and ex['endDate']: profile.exp_end_date = datetime.strptime(ex['endDate'], '%Y-%m-%d').date()
            if 'responsibilities' in ex: profile.responsibilities = ex['responsibilities']
            if 'totalYears' in ex and ex['totalYears']:
                try: profile.total_experience_years = float(ex['totalYears'])
                except: pass

        # Update Bank Details
        if 'bank' in data:
            b = data['bank']
            if 'bankName' in b: profile.bank_name = b['bankName']
            if 'branch' in b: profile.bank_branch = b['branch']
            if 'accountNumber' in b: profile.account_number = b['accountNumber']
            if 'ifsc' in b: profile.ifsc_code = b['ifsc']
            if 'aadhaar' in b: profile.aadhaar_number = b['aadhaar']
            if 'pan' in b: profile.pan_number = b['pan']
        
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
    print(f"DEBUG: Fetching notifications for user_id={user_id}")
    if not user_id:
        return jsonify({"message": "User ID required"}), 400
    
    db = SessionLocal()
    try:
        notifications = db.query(Notification).filter(
            Notification.user_id == int(user_id)
        ).order_by(Notification.created_at.desc()).limit(50).all()
        
        print(f"DEBUG: Found {len(notifications)} notifications for user {user_id}")
        
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
                "eventName": b.event_name or b.title,
                "event_date": b.event_date.strftime('%Y-%m-%d') if b.event_date else None,
                "event_time": b.event_time,
                "event_type": b.event_type,
                "message": b.message,
                "target_audience": b.target_audience,
                "author_name": b.author_name,
                "author_email": b.author_email,
                "author_designation": b.author_designation,
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


# ==========================================================
# NOTE: /api/admin/announcements (POST + GET) have been REMOVED from here.
# FIX 4: These routes were duplicated — they also exist in admin_endpoints.py
# (registered as a Blueprint) WITH proper @admin_required() authentication.
# Having two registrations caused Flask to use the Blueprint version (last
# registered), but the bare versions here caused route conflict confusion.
# The authenticated Blueprint versions are the only registrations now.
# ==========================================================


# =============================================================================
# JWT TOKEN ENDPOINTS
# =============================================================================

@app.route('/api/refresh', methods=['POST'])
def refresh_token_endpoint():
    """Refresh an expired access token using a valid refresh token"""
    data = request.get_json()
    if not data or not data.get('refresh_token'):
        return jsonify({"message": "Refresh token is required"}), 400
    
    new_access_token, error = refresh_access_token(data['refresh_token'])
    if error:
        return jsonify({"message": error}), 401
    
    return jsonify({"access_token": new_access_token}), 200


@app.route('/api/logout', methods=['POST'])
def logout_endpoint():
    """Logout by blacklisting the current access and refresh tokens"""
    # Blacklist access token from Authorization header
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        access_token = auth_header.split(' ', 1)[1]
        try:
            import jwt as pyjwt
            payload = pyjwt.decode(access_token, options={"verify_exp": False}, algorithms=["HS256"],
                                   key=os.getenv('JWT_SECRET_KEY', 'stafio_jwt_secret_key_2026_change_in_production'))
            blacklist_token(
                jti=payload.get('jti'),
                token_type='access',
                user_id=payload.get('user_id'),
                expires_at=datetime.utcfromtimestamp(payload.get('exp', 0))
            )
        except Exception:
            pass  # If token is already invalid, that's fine
    
    # Blacklist refresh token from request body
    data = request.get_json() or {}
    refresh_token_str = data.get('refresh_token')
    if refresh_token_str:
        try:
            import jwt as pyjwt
            payload = pyjwt.decode(refresh_token_str, options={"verify_exp": False}, algorithms=["HS256"],
                                   key=os.getenv('JWT_SECRET_KEY', 'stafio_jwt_secret_key_2026_change_in_production'))
            blacklist_token(
                jti=payload.get('jti'),
                token_type='refresh',
                user_id=payload.get('user_id'),
                expires_at=datetime.utcfromtimestamp(payload.get('exp', 0))
            )
        except Exception:
            pass
    
    return jsonify({"message": "Logged out successfully"}), 200


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
    app.run(host="0.0.0.0", port=5001, debug=True, use_reloader=True)