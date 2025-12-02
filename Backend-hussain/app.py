print("----- Flask Application is starting! -----")

from flask import Flask, request, jsonify
import sys
from config import Config
from database import init_db, SessionLocal
from sqlalchemy import text

# Import blueprints
from routes.auth_routes import auth_bp
from routes.employee_routes import employee_bp
from routes.admin_routes import admin_bp
from routes.leave_routes import leave_bp
from routes.attendance_routes import attendance_bp

# Create Flask application
app = Flask(__name__)

# Load configuration
app.config.from_object(Config)

# Validate configuration
Config.validate()


# ============================================================
# CORS MIDDLEWARE
# ============================================================
@app.after_request
def add_cors_headers(response):
    """Add CORS headers to all responses"""
    origin = request.headers.get('Origin', '*')
    
    if origin and origin != '*':
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
    else:
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Credentials'] = 'false'
    
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
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
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response, 200


# ============================================================
# REGISTER BLUEPRINTS
# ============================================================
app.register_blueprint(auth_bp)
app.register_blueprint(employee_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(leave_bp)
app.register_blueprint(attendance_bp)


# ============================================================
# HEALTH CHECK ENDPOINTS
# ============================================================
@app.route('/')
def index():
    """Root endpoint"""
    return jsonify({
        "message": "Welcome to Stafio Leave Management API",
        "version": "2.0",
        "status": "running"
    }), 200


@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy"}), 200


@app.route('/test-db')
def test_db():
    """Test database connection"""
    db = None
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        return jsonify({
            "message": "Database connection successful",
            "status": "connected"
        }), 200
    except Exception as e:
        return jsonify({
            "message": f"Database connection failed: {str(e)}",
            "status": "error"
        }), 500
    finally:
        if db:
            db.close()


@app.route('/pyver')
def python_version():
    """Get Python version"""
    return jsonify({"python_version": sys.version}), 200


# ============================================================
# ERROR HANDLERS
# ============================================================
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        "message": "Endpoint not found",
        "status": 404
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({
        "message": "Internal server error",
        "status": 500
    }), 500


@app.errorhandler(Exception)
def handle_exception(error):
    """Handle all uncaught exceptions"""
    print(f"Unhandled exception: {error}")
    return jsonify({
        "message": "An unexpected error occurred",
        "status": 500
    }), 500


# ============================================================
# STARTUP
# ============================================================
if __name__ == '__main__':
    print("\n" + "="*60)
    print("Stafio Backend Server Starting")
    print("="*60)
    
    # Initialize database
    try:
        init_db()
        print("✓ Database tables initialized successfully")
    except Exception as e:
        print(f"✗ Database initialization failed: {e}")
        print("  Make sure PostgreSQL is running and configured correctly")
    
    # Run migrations if available
    # try:
    #     from run_migrations import run_migrations
    #     run_migrations()
    #     print("✓ Database migrations completed")
    # except ImportError:
    #     print("⚠ No migrations file found (run_migrations.py)")
    # except Exception as e:
    #     print(f"⚠ Migration warning: {e}")
    
    print("\n" + "="*60)
    print("Server Configuration:")
    print(f"  - Host: 0.0.0.0")
    print(f"  - Port: 5001")
    print(f"  - Debug: True")
    print(f"  - Database: {Config.DB_NAME}")
    print(f"  - CORS: Enabled")
    print("="*60 + "\n")
    
    print("Available Endpoints:")
    print("  Authentication:")
    print("    POST /auth/register")
    print("    POST /auth/login/employee")
    print("    POST /auth/login/admin")
    print("    POST /auth/google/login")
    print("    POST /auth/forgot-password/send-otp")
    print("    POST /auth/forgot-password/verify-otp")
    print("    POST /auth/forgot-password/reset")
    print("\n  Employee:")
    print("    GET  /employee/dashboard")
    print("    GET  /employee/leaves")
    print("    GET  /employee/attendance")
    print("    GET  /employee/profile")
    print("    PUT  /employee/profile")
    print("\n  Admin:")
    print("    GET  /admin/dashboard")
    print("    GET  /admin/employees")
    print("    GET  /admin/attendance")
    print("    GET  /admin/leave-requests")
    print("    POST /admin/leave-requests/<id>/approve")
    print("\n  Leave:")
    print("    GET  /leave/types")
    print("    GET  /leave/balance")
    print("    POST /leave/request")
    print("\n  Attendance:")
    print("    POST /attendance/check-in")
    print("    POST /attendance/check-out")
    print("    GET  /attendance/status")
    print("\n" + "="*60 + "\n")
    
    print("🚀 Starting Flask server...")
    print("   Visit: http://localhost:5001\n")
    
    app.run(debug=True, host='0.0.0.0', port=5001)
