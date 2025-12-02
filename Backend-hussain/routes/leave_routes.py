from flask import Blueprint, request, jsonify
from datetime import datetime, date
from database import SessionLocal, LeaveRequest, LeaveType, LeaveBalance, User
from auth import token_required
from sqlalchemy import extract

leave_bp = Blueprint('leave', __name__, url_prefix='/leave')


@leave_bp.route('/types', methods=['GET'])
@token_required
def get_leave_types():
    """Get all available leave types"""
    db = SessionLocal()
    try:
        leave_types = db.query(LeaveType).all()
        
        leave_type_data = []
        for lt in leave_types:
            leave_type_data.append({
                "id": lt.id,
                "name": lt.name,
                "description": lt.description,
                "maxDaysPerYear": lt.max_days_per_year
            })
        
        return jsonify(leave_type_data), 200
        
    except Exception as e:
        print(f"Get leave types error: {e}")
        return jsonify({"message": "Failed to fetch leave types"}), 500
    finally:
        db.close()


@leave_bp.route('/balance', methods=['GET'])
@token_required
def get_leave_balance():
    """Get user's leave balance"""
    user_id = request.current_user_id
    current_year = datetime.now().year
    
    db = SessionLocal()
    try:
        balances = db.query(LeaveBalance).filter(
            LeaveBalance.user_id == user_id,
            LeaveBalance.year == current_year
        ).all()
        
        balance_data = []
        for balance in balances:
            leave_type = balance.leave_type
            balance_data.append({
                "leaveType": leave_type.name,
                "balance": float(balance.balance),
                "maxDays": leave_type.max_days_per_year
            })
        
        return jsonify(balance_data), 200
        
    except Exception as e:
        print(f"Get leave balance error: {e}")
        return jsonify({"message": "Failed to fetch leave balance"}), 500
    finally:
        db.close()


@leave_bp.route('/request', methods=['POST'])
@token_required
def request_leave():
    """Submit a new leave request"""
    user_id = request.current_user_id
    data = request.get_json()
    
    # Validate required fields
    required = ['leave_type_id', 'start_date', 'end_date', 'reason']
    missing = [field for field in required if field not in data]
    if missing:
        return jsonify({"message": f"Missing fields: {', '.join(missing)}"}), 400
    
    leave_type_id = data.get('leave_type_id')
    start_date_str = data.get('start_date')
    end_date_str = data.get('end_date')
    reason = data.get('reason', '').strip()
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({"message": "Invalid date format. Use YYYY-MM-DD"}), 400
    
    if start_date > end_date:
        return jsonify({"message": "Start date cannot be after end date"}), 400
    
    if start_date < date.today():
        return jsonify({"message": "Cannot request leave for past dates"}), 400
    
    # Calculate number of days
    num_days = (end_date - start_date).days + 1
    
    db = SessionLocal()
    try:
        # Check if leave type exists
        leave_type = db.query(LeaveType).filter(LeaveType.id == leave_type_id).first()
        if not leave_type:
            return jsonify({"message": "Invalid leave type"}), 400
        
        # Check leave balance
        current_year = datetime.now().year
        balance = db.query(LeaveBalance).filter(
            LeaveBalance.user_id == user_id,
            LeaveBalance.leave_type_id == leave_type_id,
            LeaveBalance.year == current_year
        ).first()
        
        if not balance or balance.balance < num_days:
            return jsonify({"message": "Insufficient leave balance"}), 400
        
        # Create leave request
        new_request = LeaveRequest(
            user_id=user_id,
            leave_type_id=leave_type_id,
            start_date=start_date,
            end_date=end_date,
            num_days=num_days,
            reason=reason,
            status='pending'
        )
        
        db.add(new_request)
        db.commit()
        db.refresh(new_request)
        
        return jsonify({
            "message": "Leave request submitted successfully",
            "request_id": new_request.id
        }), 201
        
    except Exception as e:
        db.rollback()
        print(f"Leave request error: {e}")
        return jsonify({"message": "Failed to submit leave request"}), 500
    finally:
        db.close()


@leave_bp.route('/request/<int:request_id>', methods=['DELETE'])
@token_required
def cancel_leave_request(request_id):
    """Cancel a leave request (only if pending)"""
    user_id = request.current_user_id
    
    db = SessionLocal()
    try:
        leave_request = db.query(LeaveRequest).filter(
            LeaveRequest.id == request_id,
            LeaveRequest.user_id == user_id
        ).first()
        
        if not leave_request:
            return jsonify({"message": "Leave request not found"}), 404
        
        if leave_request.status != 'pending':
            return jsonify({"message": "Can only cancel pending requests"}), 400
        
        db.delete(leave_request)
        db.commit()
        
        return jsonify({"message": "Leave request cancelled successfully"}), 200
        
    except Exception as e:
        db.rollback()
        print(f"Cancel leave error: {e}")
        return jsonify({"message": "Failed to cancel leave request"}), 500
    finally:
        db.close()