# app.py

print("----- Flask Application is starting from THIS file! -----")

from flask import Flask, request, jsonify
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
from datetime import date
from functools import wraps
import os
import jwt
import datetime
import requests
import secrets
from werkzeug.security import generate_password_hash


# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Abinash@1910', # !! IMPORTANT: Ensure this is your actual MySQL password
    'database': 'leave_management_db'
}

# Function to get a new database connection
def get_db_connection():
    """
    Establishes a connection to the MySQL database.
    """
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"Error connecting to database: {err}")
        return None

# Create a Flask application instance
app = Flask(__name__)


CORS(app, supports_credentials=True, resources={r"/*": {"origins":[ "http://localhost:5173", "http://127.0.0.1:5173","https://accounts.google.com"]}})
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = True

@app.after_request
def apply_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "http://localhost:5173"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response



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
    conn = None
    try:
        conn = get_db_connection()
        if conn and conn.is_connected():
            return jsonify({"message": "Database connection successful!", "status": "connected"})
        else:
            return jsonify({"message": "Database connection failed.", "status": "failed"}), 500
    except Exception as e:
        return jsonify({"message": f"An error occurred: {str(e)}", "status": "error"}), 500
    finally:
        if conn and conn.is_connected():
            conn.close()



# --- User Authentication Endpoints (Updated with Role-Based Login) ---

@app.route('/register', methods=['POST'])
def register_user():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    role = data.get('role', 'employee')

    if not username or not password or not email:
        return jsonify({"message": "Username, password, and email are required."}), 400

    hashed_password = generate_password_hash(password)

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({"message": "Database connection error."}), 500

        cursor = conn.cursor()
        query = """
        INSERT INTO users (username, password_hash, email, first_name, last_name, role)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (username, hashed_password, email, first_name, last_name, role))
        conn.commit()
        return jsonify({"message": "User registered successfully!", "user_id": cursor.lastrowid}), 201
    except mysql.connector.Error as err:
        if err.errno == 1062:
            return jsonify({"message": "Username or email already exists."}), 409
        return jsonify({"message": f"Database error: {err}"}), 500
    except Exception as e:
        return jsonify({"message": f"An unexpected error occurred: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()



#this is the code of getting the user name for backend code 

@app.route('/users/<int:user_id>', methods=['GET'])
def get_user_details(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, username, email, first_name, last_name, role FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user:
        return jsonify({"message": "User not found"}), 404
    return jsonify(user), 200



@app.route('/google_login', methods=['POST', 'OPTIONS'])
def google_login():

    # Handle CORS preflight
    if request.method == "OPTIONS":
        return "", 200

    data = request.get_json()
    id_token = data.get("id_token")
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
    email_verified = token_info.get("email_verified") in ("true", True, "True")
    given_name = token_info.get("given_name", "")
    family_name = token_info.get("family_name", "")
    google_sub = token_info.get("sub")

    if not email or not email_verified:
        return jsonify({"message": "Google account email not verified"}), 400

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Check existing user
        cursor.execute("SELECT id, username, role FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user:
            return jsonify(
                user_id=user["id"],
                username=user["username"],
                role=user["role"]
            ), 200

        # Create new user
        username_base = email.split("@")[0]
        username = username_base

        i = 1
        while True:
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                username = f"{username_base}{i}"
                i += 1
            else:
                break

        random_password = secrets.token_urlsafe(16)
        password_hash = generate_password_hash(random_password)

        insert_query = """
            INSERT INTO users (username, password_hash, email, first_name, last_name, role)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(
            insert_query,
            (username, password_hash, email, given_name, family_name, requested_role)
        )
        conn.commit()

        return jsonify(
            user_id=cursor.lastrowid,
            username=username,
            role=requested_role
        ), 201

    except Exception as e:
        return jsonify({"message": f"Server error: {str(e)}"}), 500

    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()




@app.route('/employee_login', methods=['POST'])
def employee_login():
    """
    Authenticates an employee user.
    """
    data = request.get_json()
    identifier = data.get('identifier') # Can be username or email
    password = data.get('password')

    if not identifier or not password:
        return jsonify({"message": "Username/Email and password are required."}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({"message": "Database connection error."}), 500

        cursor = conn.cursor(dictionary=True)
        query = "SELECT id, username, password_hash, role FROM users WHERE (username = %s OR email = %s) AND role = 'employee'"
        cursor.execute(query, (identifier, identifier))
        user = cursor.fetchone()

        if user and check_password_hash(user['password_hash'], password):
            return jsonify(user_id=user['id'], role=user['role'], username=user['username']), 200
        else:
            return jsonify({"message": "Invalid employee username/email or password."}), 401
    except Exception as e:
        print(f"ERROR: employee_login - An unexpected error occurred: {str(e)}")
        return jsonify({"message": f"An unexpected error occurred: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

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
    email = request.json.get("email")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    return jsonify({"exists": bool(user)})


@app.route('/update_password', methods=['POST'])
def update_password():
    data = request.json
    email = data["email"]
    new_password = generate_password_hash(data["newPassword"])

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check email exists
    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()

    if not user:
        cursor.close()
        conn.close()
        return jsonify({"message": "Email not found"}), 400

    # Update password
    cursor.execute("UPDATE users SET password_hash = %s WHERE email = %s", (new_password, email))
    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"message": "Password updated successfully"}), 200




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


#Mansoor code added 

# --- Admin Profile Endpoint ---
@app.route('/admin_profile/<int:user_id>', methods=['GET'])
@custom_admin_required()
def get_admin_profile_data(user_id):
    """
    Returns admin profile data for the specified user.
    Mock data - replace with actual database queries later.
    """
    # Mock profile data
    admin_profile_data = {
        "profile": {
            "profileImage": "",
            "name": "Aiswarya Shyamkumar",
            "gender": "Female",
            "dob": "1993-07-22",
            "maritalStatus": "Married",
            "nationality": "India",
            "bloodGroup": "A+",
            "email": "aiswarya@gmail.com",
            "phone": "9895195971",
            "address": "Kattasseri House, Kalarikal, Alappuzha, Kerala",
            "emergencyContactNumber": "9895195971",
            "relationship": "Husband",
            "empType": "Internship",
            "department": "Design",
            "location": "Kerala",
            "supervisor": "Sakshi Chadchankar",
            "hrManager": "S. Santhana Lakshmi",
            "empId": "1234567",
            "status": "Active"
        },
        "education": {
            "institution": "CEMP Punnapra",
            "location": "Kerala",
            "startDate": "2012-07-22",
            "endDate": "2016-07-22",
            "qualification": "B.Tech",
            "specialization": "Computer Science",
            "skills": ["Illustrator", "Photoshop", "Figma", "Adobe XD"],
            "portfolio": "https://www.behance.net/gallery/229448069/Training-Provider-Web-UI-Design"
        },
        "experience": {
            "company": "Azym Technology",
            "jobTitle": "UIUX Designer",
            "startDate": "2017-07-22",
            "endDate": "2022-07-22",
            "responsibilities": "Conduct user research, interviews, and usability testing to gather insights.",
            "totalYears": 4
        },
        "bank": {
            "bankName": "SBI",
            "branch": "Alappuzha",
            "accountNumber": "123456789101",
            "ifsc": "IFC12345",
            "aadhaar": "123456789101",
            "pan": "IFC12345"
        },
        "documents": [
            {"fileName": "Signed OfferLetter.pdf", "status": "Completed"},
            {"fileName": "DegreeCertificate.pdf", "status": "Completed"},
            {"fileName": "Pan Card.pdf", "status": "Completed"}
        ]
    }
    
    return jsonify(admin_profile_data), 200


# --- Employee Profile Endpoint ---
@app.route('/employee_profile/<int:user_id>', methods=['GET'])
@custom_user_required()
def get_employee_profile_data(user_id):
    """
    Returns employee profile data for the specified user.
    Mock data - replace with actual database queries later.
    """
    # Check if the requesting user is accessing their own profile
    current_user_id = request.current_user_id
    if current_user_id != user_id and request.headers.get('X-User-Role') != 'admin':
        return jsonify({"message": "Unauthorized to view this profile."}), 403
    
    # Mock profile data
    employee_profile_data = {
        "profile": {
            "profileImage": "",
            "name": "Aiswarya Shyamkumar",
            "gender": "Female",
            "dob": "1993-07-22",
            "maritalStatus": "Married",
            "nationality": "India",
            "bloodGroup": "A+",
            "email": "aiswarya@gmail.com",
            "phone": "9895195971",
            "address": "Kattasseri House, Kalarikal, Alappuzha, Kerala",
            "emergencyContactNumber": "9895195971",
            "relationship": "Husband",
            "empType": "Internship",
            "department": "Design",
            "location": "Kerala",
            "supervisor": "Sakshi Chadchankar",
            "hrManager": "S. Santhana Lakshmi",
            "empId": "1234567",
            "status": "Active"
        },
        "education": {
            "institution": "CEMP Punnapra",
            "location": "Kerala",
            "startDate": "2012-07-22",
            "endDate": "2016-07-22",
            "qualification": "B.Tech",
            "specialization": "Computer Science",
            "skills": ["Illustrator", "Photoshop", "Figma", "Adobe XD"],
            "portfolio": "https://www.behance.net/gallery/229448069/Training-Provider-Web-UI-Design"
        },
        "experience": {
            "company": "Azym Technology",
            "jobTitle": "UIUX Designer",
            "startDate": "2017-07-22",
            "endDate": "2022-07-22",
            "responsibilities": "Conduct user research, interviews, and usability testing to gather insights.",
            "totalYears": 4
        },
        "bank": {
            "bankName": "SBI",
            "branch": "Alappuzha",
            "accountNumber": "123456789101",
            "ifsc": "IFC12345",
            "aadhaar": "123456789101",
            "pan": "IFC12345"
        },
        "documents": [
            {"fileName": "Signed OfferLetter.pdf", "status": "Completed"},
            {"fileName": "DegreeCertificate.pdf", "status": "Completed"},
            {"fileName": "Pan Card.pdf", "status": "Completed"}
        ]
    }
    
    return jsonify(employee_profile_data), 200


# Run the Flask application
if __name__ == '__main__':
    app.run(debug=True)