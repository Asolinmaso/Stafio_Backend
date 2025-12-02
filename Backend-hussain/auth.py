import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
from config import Config


def generate_token(user_id: int, role: str, username: str) -> str:
    """Generate JWT token"""
    payload = {
        'user_id': user_id,
        'role': role,
        'username': username,
        'exp': datetime.utcnow() + timedelta(hours=Config.JWT_EXPIRATION_HOURS),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm=Config.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode JWT token"""
    try:
        return jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=[Config.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")


def get_token_from_header():
    """Extract token from Authorization header"""
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return None
    
    try:
        # Format: "Bearer <token>"
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return None
        return parts[1]
    except Exception:
        return None


def token_required(f):
    """Decorator to require valid JWT token"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_token_from_header()
        
        if not token:
            return jsonify({'message': 'Authentication token is missing'}), 401
        
        try:
            data = decode_token(token)
            request.current_user_id = data['user_id']
            request.current_user_role = data['role']
            request.current_username = data['username']
        except ValueError as e:
            return jsonify({'message': str(e)}), 401
        
        return f(*args, **kwargs)
    
    return decorated


def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_token_from_header()
        
        if not token:
            return jsonify({'message': 'Authentication token is missing'}), 401
        
        try:
            data = decode_token(token)
            request.current_user_id = data['user_id']
            request.current_user_role = data['role']
            request.current_username = data['username']
            
            if data['role'] != 'admin':
                return jsonify({'message': 'Admin access required'}), 403
                
        except ValueError as e:
            return jsonify({'message': str(e)}), 401
        
        return f(*args, **kwargs)
    
    return decorated


def optional_auth(f):
    """Decorator for optional authentication (doesn't fail if no token)"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_token_from_header()
        
        if token:
            try:
                data = decode_token(token)
                request.current_user_id = data['user_id']
                request.current_user_role = data['role']
                request.current_username = data['username']
            except ValueError:
                # Token invalid but continue anyway
                request.current_user_id = None
                request.current_user_role = None
                request.current_username = None
        else:
            request.current_user_id = None
            request.current_user_role = None
            request.current_username = None
        
        return f(*args, **kwargs)
    
    return decorated