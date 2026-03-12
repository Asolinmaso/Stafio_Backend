"""
JWT Authentication & RBAC Module for Stafio
============================================
Provides:
- JWT access/refresh token generation & verification
- Token blacklist checking
- Role-based decorators: @jwt_required(), @role_required(), @permission_required()
- Permission mapping per role
"""

import jwt
import uuid
import os
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================

JWT_SECRET = os.getenv('JWT_SECRET_KEY', 'stafio_jwt_secret_key_2026_change_in_production')
ACCESS_EXPIRY_MINUTES = int(os.getenv('JWT_ACCESS_EXPIRY_MINUTES', '15'))
REFRESH_EXPIRY_DAYS = int(os.getenv('JWT_REFRESH_EXPIRY_DAYS', '7'))


# =============================================================================
# ROLE → PERMISSION MAPPING
# =============================================================================

ROLE_PERMISSIONS = {
    "admin": [
        "employee:read", "employee:write", "employee:delete",
        "attendance:read", "attendance:write",
        "leave:read", "leave:write", "leave:approve",
        "regularization:read", "regularization:write", "regularization:approve",
        "payroll:read", "payroll:write",
        "department:read", "department:write", "department:delete",
        "settings:read", "settings:write",
        "profile:read", "profile:write",
        "task:read", "task:write", "task:delete",
        "performance:read", "performance:write",
        "document:read", "document:write", "document:verify",
        "broadcast:read", "broadcast:write",
        "holiday:read", "holiday:write",
        "report:read",
    ],
    "employee": [
        "attendance:read", "attendance:write",
        "leave:read", "leave:write",
        "regularization:read", "regularization:write",
        "profile:read", "profile:write",
        "payroll:read",
        "task:read",
        "performance:read",
        "document:read", "document:write",
        "broadcast:read",
        "holiday:read",
    ],
    "manager": [
        "employee:read",
        "attendance:read", "attendance:write",
        "leave:read", "leave:write", "leave:approve",
        "regularization:read", "regularization:write", "regularization:approve",
        "profile:read", "profile:write",
        "task:read", "task:write",
        "performance:read",
        "document:read", "document:write",
        "broadcast:read",
        "holiday:read",
        "report:read",
    ],
}


# =============================================================================
# TOKEN GENERATION
# =============================================================================

def generate_access_token(user_id, role):
    """Generate a short-lived access token (15 min default)"""
    permissions = ROLE_PERMISSIONS.get(role, [])
    payload = {
        "user_id": user_id,
        "role": role,
        "permissions": permissions,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_EXPIRY_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def generate_refresh_token(user_id, role):
    """Generate a long-lived refresh token (7 days default)"""
    payload = {
        "user_id": user_id,
        "role": role,
        "type": "refresh",
        "jti": str(uuid.uuid4()),
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(days=REFRESH_EXPIRY_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def generate_tokens(user_id, role):
    """Generate both access and refresh tokens"""
    return {
        "access_token": generate_access_token(user_id, role),
        "refresh_token": generate_refresh_token(user_id, role),
    }


# =============================================================================
# TOKEN VERIFICATION
# =============================================================================

def verify_token(token, expected_type="access"):
    """
    Decode and verify a JWT token.
    Returns the payload dict on success, or None on failure.
    Also checks the blacklist.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        
        # Check token type
        if payload.get("type") != expected_type:
            return None
        
        # Check blacklist
        if _is_token_blacklisted(payload.get("jti")):
            return None
        
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def _is_token_blacklisted(jti):
    """Check if a token JTI is in the blacklist"""
    if not jti:
        return False
    try:
        from database import SessionLocal, BlacklistedToken
        db = SessionLocal()
        try:
            exists = db.query(BlacklistedToken).filter(
                BlacklistedToken.jti == jti
            ).first()
            return exists is not None
        finally:
            db.close()
    except Exception:
        return False


def blacklist_token(jti, token_type="access", user_id=None, expires_at=None):
    """Add a token to the blacklist"""
    try:
        from database import SessionLocal, BlacklistedToken
        db = SessionLocal()
        try:
            entry = BlacklistedToken(
                jti=jti,
                token_type=token_type,
                user_id=user_id,
                expires_at=expires_at,
            )
            db.add(entry)
            db.commit()
            return True
        except Exception:
            db.rollback()
            return False
        finally:
            db.close()
    except Exception:
        return False


def refresh_access_token(refresh_token_str):
    """
    Given a valid refresh token, issue a new access token.
    Returns (new_access_token, error_message) tuple.
    """
    payload = verify_token(refresh_token_str, expected_type="refresh")
    if not payload:
        return None, "Invalid or expired refresh token"
    
    user_id = payload.get("user_id")
    role = payload.get("role")
    
    new_access_token = generate_access_token(user_id, role)
    return new_access_token, None


# =============================================================================
# DECORATORS
# =============================================================================

def jwt_required():
    """
    Decorator that verifies the JWT access token.
    Sets request.user_id, request.user_role, request.permissions.
    
    Backward compatible: falls back to X-User-ID / X-User-Role headers
    if no Authorization header is present (for migration period).
    """
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ", 1)[1]
                payload = verify_token(token, expected_type="access")
                
                if not payload:
                    return jsonify({"message": "Invalid or expired token"}), 401
                
                request.user_id = payload["user_id"]
                request.user_role = payload["role"]
                request.permissions = payload.get("permissions", [])
                request.token_jti = payload.get("jti")
            else:
                # Backward compatibility: use headers during migration
                user_id = request.headers.get("X-User-ID")
                user_role = request.headers.get("X-User-Role", "")
                
                if not user_id:
                    return jsonify({"message": "Authentication required"}), 401
                
                try:
                    request.user_id = int(user_id)
                except (ValueError, TypeError):
                    return jsonify({"message": "Invalid user ID"}), 401
                
                request.user_role = user_role
                request.permissions = ROLE_PERMISSIONS.get(user_role, [])
                request.token_jti = None
            
            return fn(*args, **kwargs)
        return decorator
    return wrapper


def role_required(*roles):
    """
    Decorator that checks if the user has one of the required roles.
    Must be used AFTER @jwt_required().
    
    Usage: @role_required('admin') or @role_required('admin', 'manager')
    """
    # Normalize required roles to lowercase
    required_roles = [r.lower() for r in roles]
    
    import os
    log_file = os.path.join(os.path.dirname(__file__), "debug_auth.log")

    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            user_id = getattr(request, 'user_id', None)
            user_role = getattr(request, 'user_role', None)
            
            with open(log_file, "a") as f_log:
                f_log.write(f"{datetime.now()}: Checking role. Required: {required_roles}, Actual: {user_role}, UserID: {user_id}, Headers: {dict(request.headers)}\n")
            
            # Case-insensitive comparison
            if not user_role or user_role.lower() not in required_roles:
                with open(log_file, "a") as f_log:
                    f_log.write(f"{datetime.now()}: ACCESS DENIED\n")
                return jsonify({
                    "message": f"Access denied. Required role: {', '.join(roles)}"
                }), 403
            return fn(*args, **kwargs)
        return decorator
    return wrapper


def permission_required(*permissions):
    """
    Decorator that checks if the user has ALL of the required permissions.
    Must be used AFTER @jwt_required().
    
    Usage: @permission_required('leave:approve')
           @permission_required('employee:read', 'employee:write')
    """
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            user_permissions = getattr(request, 'permissions', [])
            missing = [p for p in permissions if p not in user_permissions]
            if missing:
                return jsonify({
                    "message": f"Permission denied. Missing: {', '.join(missing)}"
                }), 403
            return fn(*args, **kwargs)
        return decorator
    return wrapper
