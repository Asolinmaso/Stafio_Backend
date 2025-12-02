from flask import Blueprint, request, jsonify
from datetime import datetime
from database import SessionLocal, User, LeaveRequest, Attendance, Regularization, Holiday, EmployeeProfile, BankDetails, Department
from auth import token_required
from sqlalchemy import func, extract

employee_bp = Blueprint('employee', __name__, url_prefix='/employee')


@employee_bp.route('/dashboard', methods=['GET'])
@token_required
def get_dashboard():
    """Get employee dashboard data"""
    user_id = request.current_user_id
    current_year = datetime.now().year
    
    db = SessionLocal()
    try:
        # Get leave statistics
        total_leaves = db.query(func.sum(LeaveRequest.num_days)).filter(
            LeaveRequest.user_id == user_id,
            LeaveRequest.status == 'approved',
            extract('year', LeaveRequest.start_date) == current_year
        ).scalar() or 0
        
        pending_leaves = db.query(func.count(LeaveRequest.id)).filter(
            LeaveRequest.user_id == user_id,
            LeaveRequest.status == 'pending'
        ).scalar() or 0
        
        # Get attendance statistics
        absent_days = db.query(func.count(Attendance.id)).filter(
            Attendance.user_id == user_id,
            Attendance.status == 'absent',
            extract('year', Attendance.date) == current_year
        ).scalar() or 0
        
        worked_days = db.query(func.count(Attendance.id)).filter(
            Attendance.user_id == user_id,
            Attendance.status.in_(['on_time', 'late']),
            extract('year', Attendance.date) == current_year
        ).scalar() or 0
        
        # Get this week's holidays
        from datetime import date, timedelta
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        
        this_week_holidays = db.query(func.count(Holiday.id)).filter(
            Holiday.date >= week_start,
            Holiday.date <= week_end
        ).scalar() or 0
        
        return jsonify({
            "total_leaves": float(total_leaves),
            "pending_leaves": pending_leaves,
            "leaves_taken": float(total_leaves),
            "absent_days": absent_days,
            "worked_days": worked_days,
            "this_week_holidays": this_week_holidays
        }), 200
        
    except Exception as e:
        print(f"Dashboard error: {e}")
        return jsonify({"message": "Failed to fetch dashboard data"}), 500
    finally:
        db.close()


@employee_bp.route('/leaves', methods=['GET'])
@token_required
def get_my_leaves():
    """Get employee's leave requests"""
    user_id = request.current_user_id
    
    db = SessionLocal()
    try:
        leaves = db.query(LeaveRequest).filter(
            LeaveRequest.user_id == user_id
        ).order_by(LeaveRequest.applied_date.desc()).all()
        
        leave_data = []
        for leave in leaves:
            leave_type_name = leave.leave_type.name if leave.leave_type else "Unknown"
            
            leave_data.append({
                "id": leave.id,
                "type": f"{leave_type_name} {leave.num_days} Day(s)",
                "date": f"{leave.start_date.strftime('%d-%m-%Y')} to {leave.end_date.strftime('%d-%m-%Y')}",
                "reason": leave.reason,
                "requestDate": leave.applied_date.strftime('%d-%m-%Y'),
                "status": leave.status.capitalize()
            })
        
        return jsonify(leave_data), 200
        
    except Exception as e:
        print(f"Get leaves error: {e}")
        return jsonify({"message": "Failed to fetch leaves"}), 500
    finally:
        db.close()


@employee_bp.route('/regularizations', methods=['GET'])
@token_required
def get_my_regularizations():
    """Get employee's regularization requests"""
    user_id = request.current_user_id
    
    db = SessionLocal()
    try:
        regularizations = db.query(Regularization).filter(
            Regularization.user_id == user_id
        ).order_by(Regularization.applied_date.desc()).all()
        
        reg_data = []
        for reg in regularizations:
            reg_data.append({
                "id": reg.id,
                "attendanceType": reg.attendance_type or "Present",
                "date": reg.date.strftime('%d-%m-%Y'),
                "reason": reg.reason,
                "status": reg.status.capitalize()
            })
        
        return jsonify(reg_data), 200
        
    except Exception as e:
        print(f"Get regularizations error: {e}")
        return jsonify({"message": "Failed to fetch regularizations"}), 500
    finally:
        db.close()


@employee_bp.route('/attendance', methods=['GET'])
@token_required
def get_my_attendance():
    """Get employee's attendance records"""
    user_id = request.current_user_id
    
    db = SessionLocal()
    try:
        attendance_records = db.query(Attendance).filter(
            Attendance.user_id == user_id
        ).order_by(Attendance.date.desc()).limit(30).all()
        
        attendance_data = []
        for record in attendance_records:
            status_map = {
                'on_time': 'On Time',
                'late': 'Late Login',
                'absent': 'Absent',
                'half_day': 'Half Day'
            }
            
            attendance_data.append({
                "date": record.date.strftime('%Y-%m-%d'),
                "status": status_map.get(record.status, record.status),
                "checkIn": record.check_in.strftime('%H:%M') if record.check_in else "00:00",
                "checkOut": record.check_out.strftime('%H:%M') if record.check_out else "00:00",
                "late": f"{record.late_minutes} Min" if record.late_minutes > 0 else "-",
                "overtime": f"{record.overtime_minutes} Min" if record.overtime_minutes > 0 else "-",
                "workHours": f"{int(record.work_hours)}h {int((record.work_hours % 1) * 60)}m" if record.work_hours else "0h 0m"
            })
        
        return jsonify(attendance_data), 200
        
    except Exception as e:
        print(f"Get attendance error: {e}")
        return jsonify({"message": "Failed to fetch attendance"}), 500
    finally:
        db.close()


@employee_bp.route('/holidays', methods=['GET'])
@token_required
def get_holidays():
    """Get list of holidays"""
    db = SessionLocal()
    try:
        current_year = datetime.now().year
        holidays = db.query(Holiday).filter(
            extract('year', Holiday.date) == current_year
        ).order_by(Holiday.date).all()
        
        holiday_data = []
        for holiday in holidays:
            holiday_data.append({
                "id": holiday.id,
                "date": holiday.date.strftime('%d %B, %A'),
                "title": holiday.title
            })
        
        return jsonify(holiday_data), 200
        
    except Exception as e:
        print(f"Get holidays error: {e}")
        return jsonify({"message": "Failed to fetch holidays"}), 500
    finally:
        db.close()


@employee_bp.route('/profile', methods=['GET'])
@token_required
def get_profile():
    """Get employee profile"""
    user_id = request.current_user_id
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            return jsonify({"message": "User not found"}), 404
        
        # Get employee profile
        profile = db.query(EmployeeProfile).filter(
            EmployeeProfile.user_id == user_id
        ).first()
        
        # Get bank details
        bank = db.query(BankDetails).filter(
            BankDetails.user_id == user_id
        ).first()
        
        # Get department info
        department_name = ""
        if profile and profile.department:
            department_name = profile.department.name
        
        profile_data = {
            "profile": {
                "name": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
                "email": user.email,
                "phone": user.phone or "",
                "empId": profile.employee_id if profile else str(user.id),
                "department": department_name,
                "position": profile.position if profile else "",
                "gender": profile.gender if profile else "",
                "dob": profile.date_of_birth.strftime('%Y-%m-%d') if profile and profile.date_of_birth else "",
                "maritalStatus": profile.marital_status if profile else "",
                "nationality": profile.nationality if profile else "",
                "bloodGroup": profile.blood_group if profile else "",
                "address": profile.address if profile else "",
                "emergencyContactNumber": profile.emergency_contact if profile else "",
                "relationship": profile.emergency_relationship if profile else "",
                "empType": profile.employment_type if profile else "",
                "status": profile.status if profile else "active"
            },
            "bank": {
                "bankName": bank.bank_name if bank else "",
                "branch": bank.branch if bank else "",
                "accountNumber": bank.account_number if bank else "",
                "ifsc": bank.ifsc_code if bank else "",
                "aadhaar": bank.aadhaar_number if bank else "",
                "pan": bank.pan_number if bank else ""
            }
        }
        
        return jsonify(profile_data), 200
        
    except Exception as e:
        print(f"Get profile error: {e}")
        return jsonify({"message": "Failed to fetch profile"}), 500
    finally:
        db.close()


@employee_bp.route('/profile', methods=['PUT'])
@token_required
def update_profile():
    """Update employee profile"""
    user_id = request.current_user_id
    data = request.get_json()
    
    db = SessionLocal()
    try:
        # Update user basic info
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return jsonify({"message": "User not found"}), 404
        
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'phone' in data:
            user.phone = data['phone']
        
        db.commit()
        
        return jsonify({"message": "Profile updated successfully"}), 200
        
    except Exception as e:
        db.rollback()
        print(f"Update profile error: {e}")
        return jsonify({"message": "Failed to update profile"}), 500
    finally:
        db.close()