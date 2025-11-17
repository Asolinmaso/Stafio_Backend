print("----- Employee Database Backend is starting from THIS file! -----")

from flask import Flask, request, jsonify
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
from datetime import date
from functools import wraps
import os

# Database configuration for the employee database
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Abinash@1910',  # !! IMPORTANT: Ensure this is your actual MySQL password
    'database': 'employee_db'     # !! IMPORTANT: Note the new database name
}

# Function to get a new database connection
def get_db_connection():
    """
    Establishes a connection to the MySQL database for the employee app.
    """
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"Error connecting to employee_db: {err}")
        return None

# Create a Flask application instance
app = Flask(__name__)
CORS(app)

# --- CUSTOM, TEMPORARY INSECURE DECORATORS ---
# These are simple wrappers to check for specific headers for this example.
# A real application would use JWTs or session-based authentication.

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
    return 'Hello, World! Welcome to the Employee Database Backend!'

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

# --- User Authentication Endpoints ---

@app.route('/register', methods=['POST'])
def register_employee():
    """
    Registers a new employee account. By default, the role is 'employee'.
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    job_title = data.get('job_title')
    department = data.get('department')
    hire_date = data.get('hire_date')
    role = data.get('role', 'employee')

    if not all([username, password, first_name, last_name, email]):
        return jsonify({"message": "Username, password, first name, last name, and email are required."}), 400

    hashed_password = generate_password_hash(password)

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({"message": "Database connection error."}), 500

        cursor = conn.cursor()
        query = """
            INSERT INTO employees (username, password_hash, email, first_name, last_name, job_title, department, hire_date, role)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (username, hashed_password, email, first_name, last_name, job_title, department, hire_date, role))
        conn.commit()
        return jsonify({"message": "Employee registered successfully!", "employee_id": cursor.lastrowid}), 201

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

@app.route('/login', methods=['POST'])
def login():
    """
    Authenticates a user and returns their ID and role.
    """
    data = request.get_json()
    identifier = data.get('identifier')  # Can be username or email
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
        query = "SELECT id, username, password_hash, role FROM employees WHERE username = %s OR email = %s"
        cursor.execute(query, (identifier, identifier))
        user = cursor.fetchone()

        if user and check_password_hash(user['password_hash'], password):
            return jsonify(employee_id=user['id'], role=user['role']), 200
        else:
            return jsonify({"message": "Invalid username/email or password."}), 401

    except Exception as e:
        print(f"ERROR: login - An unexpected error occurred: {str(e)}")
        return jsonify({"message": f"An unexpected error occurred: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

# --- Employee CRUD Endpoints (Protected by Admin Role) ---

@app.route('/employees', methods=['POST'])
@custom_admin_required()
def add_employee():
    """
    Adds a new employee. This endpoint is for admins only.
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    job_title = data.get('job_title')
    department = data.get('department')
    hire_date = data.get('hire_date')
    role = data.get('role', 'employee')

    if not all([username, password, first_name, last_name, email]):
        return jsonify({"message": "Username, password, first name, last name, and email are required."}), 400

    hashed_password = generate_password_hash(password)

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({"message": "Database connection error."}), 500

        cursor = conn.cursor()
        query = """
            INSERT INTO employees (username, password_hash, email, first_name, last_name, job_title, department, hire_date, role)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (username, hashed_password, email, first_name, last_name, job_title, department, hire_date, role))
        conn.commit()
        return jsonify({"message": "Employee added successfully!", "employee_id": cursor.lastrowid}), 201

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

@app.route('/employees', methods=['GET'])
@custom_user_required()  # Any logged-in user can view the list of employees
def get_all_employees():
    """
    Retrieves a list of all employees.
    """
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({"message": "Database connection error."}), 500

        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT id, username, email, first_name, last_name, job_title, department, hire_date, role
            FROM employees
            ORDER BY last_name, first_name
        """
        cursor.execute(query)
        employees = cursor.fetchall()
        return jsonify(employees), 200

    except Exception as e:
        return jsonify({"message": f"An unexpected error occurred: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

@app.route('/employees/<int:employee_id>', methods=['GET'])
@custom_user_required()
def get_employee_details(employee_id):
    """
    Retrieves details for a single employee.
    """
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({"message": "Database connection error."}), 500

        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT id, username, email, first_name, last_name, job_title, department, hire_date, role
            FROM employees
            WHERE id = %s
        """
        cursor.execute(query, (employee_id,))
        employee = cursor.fetchone()

        if not employee:
            return jsonify({"message": "Employee not found."}), 404

        return jsonify(employee), 200

    except Exception as e:
        return jsonify({"message": f"An unexpected error occurred: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

@app.route('/employees/<int:employee_id>', methods=['PUT'])
@custom_admin_required()
def update_employee(employee_id):
    """
    Updates an employee's details. This endpoint is for admins only.
    """
    data = request.get_json()
    updates = []
    params = []

    # Dynamically build the update query based on the fields provided
    if 'username' in data:
        updates.append("username = %s")
        params.append(data['username'])
    if 'email' in data:
        updates.append("email = %s")
        params.append(data['email'])
    if 'first_name' in data:
        updates.append("first_name = %s")
        params.append(data['first_name'])
    if 'last_name' in data:
        updates.append("last_name = %s")
        params.append(data['last_name'])
    if 'job_title' in data:
        updates.append("job_title = %s")
        params.append(data['job_title'])
    if 'department' in data:
        updates.append("department = %s")
        params.append(data['department'])
    if 'hire_date' in data:
        updates.append("hire_date = %s")
        params.append(data['hire_date'])
    if 'role' in data:
        updates.append("role = %s")
        params.append(data['role'])
    if 'password' in data:
        hashed_password = generate_password_hash(data['password'])
        updates.append("password_hash = %s")
        params.append(hashed_password)

    if not updates:
        return jsonify({"message": "No fields provided for update."}), 400

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({"message": "Database connection error."}), 500

        cursor = conn.cursor()
        query = f"UPDATE employees SET {', '.join(updates)} WHERE id = %s"
        params.append(employee_id)
        cursor.execute(query, tuple(params))
        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({"message": "Employee not found or no changes made."}), 404

        return jsonify({"message": "Employee updated successfully!"}), 200

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

@app.route('/employees/<int:employee_id>', methods=['DELETE'])
@custom_admin_required()
def delete_employee(employee_id):
    """
    Deletes an employee record. This endpoint is for admins only.
    """
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({"message": "Database connection error."}), 500

        cursor = conn.cursor()
        cursor.execute("DELETE FROM employees WHERE id = %s", (employee_id,))
        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({"message": "Employee not found or already deleted."}), 404

        return jsonify({"message": "Employee deleted successfully!"}), 200

    except Exception as e:
        return jsonify({"message": f"An unexpected error occurred: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()




# Run the Flask application
if __name__ == '__main__':
    app.run(debug=True, port=5001)