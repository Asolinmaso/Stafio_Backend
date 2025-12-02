from flask import Blueprint, request, jsonify
from datetime import datetime
from database import SessionLocal, User, LeaveRequest, Attendance, EmployeeProfile, Department
from auth import admin_required
from sqlalchemy import func, extract, or_

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/dashboard', methods=['GET'])
@admin_required
def get_admin_dashboard():
    """Get admin dashboard statistics"""
    db = SessionLocal()
    try:
        current_date = datetime.now().date()
        
        # Total employees
        total_employees = db.query(func.count(User.id)).filter(
            User.role == 'employee'
        ).scalar() or 0
        
        # Today's attendance stats
        on_time = db.query(func.count(Attendance.id)).filter(
            Attendance.date == current_date,
            Attendance.status == 'on_time'
        ).scalar() or 0
        
        on_leave = db.query(func.count(LeaveRequest.id)).filter(
            LeaveRequest.start_date <= current_date,
            LeaveRequest.end_date >= current_date,
            LeaveRequest.status == 'approved'
        ).scalar() or 0
        
        late_arrival = db.query(func.count(Attendance.id)).filter(
            Attendance.date == current_date,
            Attendance.status == 'late'
        ).scalar() or 0
        
        # Pending approvals
        pending_approval = db.query(func.count(LeaveRequest.id)).filter(
            LeaveRequest.status == 'pending'
        ).scalar() or 0
        
        # This week holidays
        from datetime import date, timedelta
        week_start = current_date - timedelta(days=current_date.weekday())
        week_end = week_start + timedelta(days=6)
        
        from database import Holiday
        this_week_holidays = db.query(func.count(Holiday.id)).filter(
            Holiday.date >= week_start,
            Holiday.date <= week_end
        ).scalar() or 0
        
        return jsonify({
            "total_employees": total_employees,
            "on_time": on_time,
            "on_leave": on_leave,
            "late_arrival": late_arrival,
            "pending_approval": pending_approval,
            "this_week_holidays": this_week_holidays
        }), 200
        
    except Exception as e:
        print(f"Admin dashboard error: {e}")
        return jsonify({"message": "Failed to fetch dashboard data"}), 500
    finally:
        db.close()


@admin_bp.route('/employees', methods=['GET'])
@admin_required
def get_employees():
    """Get list of all employees"""
    db = SessionLocal()
    try:
        employees = db.query(User).filter(User.role == 'employee').all()
        
        employee_data = []
        for emp in employees:
            profile = db.query(EmployeeProfile).filter(
                EmployeeProfile.user_id == emp.id
            ).first()
            
            department_name = ""
            if profile and profile.department:
                department_name = profile.department.name
            
            employee_data.append({
                "id": emp.id,
                "name": f"{emp.first_name or ''} {emp.last_name or ''}".strip() or emp.username,
                "email": emp.email,
                "empId": profile.employee_id if profile else str(emp.id),
                "position": profile.position if profile else "N/A",
                "department": department_name or "N/A",
                "status": profile.status if profile else "active",
                "image": f"https://ui-avatars.com/api/?name={emp.username}&background=random"
            })
        
        return jsonify(employee_data), 200
        
    except Exception as e:
        print(f"Get employees error: {e}")
        return jsonify({"message": "Failed to fetch employees"}), 500
    finally:
        db.close()


@admin_bp.route('/employees/<int:employee_id>', methods=['GET'])
@admin_required
def get_employee_details(employee_id):
    """Get detailed information about a specific employee"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == employee_id).first()
        
        if not user:
            return jsonify({"message": "Employee not found"}), 404
        
        profile = db.query(EmployeeProfile).filter(
            EmployeeProfile.user_id == employee_id
        ).first()
        
        from database import BankDetails
        bank = db.query(BankDetails).filter(
            BankDetails.user_id == employee_id
        ).first()
        
        department_name = ""
        if profile and profile.department:
            department_name = profile.department.name
        
        employee_data = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "phone": user.phone,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "profile": {
                "empId": profile.employee_id if profile else str(user.id),
                "department": department_name,
                "position": profile.position if profile else "",
                "gender": profile.gender if profile else "",
                "dob": profile.date_of_birth.strftime('%Y-%m-%d') if profile and profile.date_of_birth else "",
                "status": profile.status if profile else "active"
            },
            "bank": {
                "bankName": bank.bank_name if bank else "",
                "accountNumber": bank.account_number if bank else ""
            }
        }
        
        return jsonify(employee_data), 200
        
    except Exception as e:
        print(f"Get employee details error: {e}")
        return jsonify({"message": "Failed to fetch employee details"}), 500
    finally:
        db.close()


@admin_bp.route('/attendance', methods=['GET'])
@admin_required
def get_all_attendance():
    """Get attendance records for all employees"""
    db = SessionLocal()
    try:
        # Get date filter from query params (optional)
        date_str = request.args.get('date')
        
        query = db.query(Attendance).join(User)
        
        if date_str:
            try:
                filter_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                query = query.filter(Attendance.date == filter_date)
            except ValueError:
                pass
        
        attendance_records = query.order_by(Attendance.date.desc()).limit(100).all()
        
        attendance_data = []
        for record in attendance_records:
            user = record.user
            profile = db.query(EmployeeProfile).filter(
                EmployeeProfile.user_id == user.id
            ).first()
            
            status_map = {
                'on_time': 'On Time',
                'late': 'Late Login',
                'absent': 'Absent',
                'half_day': 'Half Day'
            }
            
            attendance_data.append({
                "id": record.id,
                "employee": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
                "empId": profile.employee_id if profile else str(user.id),
                "role": profile.position if profile else "N/A",
                "status": status_map.get(record.status, record.status),
                "date": record.date.strftime('%d %b %Y'),
                "checkIn": record.check_in.strftime('%H:%M') if record.check_in else "00:00",
                "checkOut": record.check_out.strftime('%H:%M') if record.check_out else "00:00",
                "workHours": f"{int(record.work_hours)}h {int((record.work_hours % 1) * 60)}m" if record.work_hours else "0h 0m"
            })
        
        return jsonify(attendance_data), 200
        
    except Exception as e:
        print(f"Get attendance error: {e}")
        return jsonify({"message": "Failed to fetch attendance records"}), 500
    finally:
        db.close()


@admin_bp.route('/leave-requests', methods=['GET'])
@admin_required
def get_leave_requests():
    """Get all leave requests with optional status filter"""
    status_filter = request.args.get('status', 'pending')
    
    db = SessionLocal()
    try:
        query = db.query(LeaveRequest).join(User)
        
        if status_filter and status_filter != 'all':
            query = query.filter(LeaveRequest.status == status_filter)
        
        leave_requests = query.order_by(LeaveRequest.applied_date.desc()).all()
        
        leave_data = []
        for leave in leave_requests:
            user = leave.user
            leave_type_name = leave.leave_type.name if leave.leave_type else "Unknown"
            
            leave_data.append({
                "id": leave.id,
                "employee": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
                "empId": str(user.id),
                "type": leave_type_name,
                "startDate": leave.start_date.strftime('%Y-%m-%d'),
                "endDate": leave.end_date.strftime('%Y-%m-%d'),
                "numDays": float(leave.num_days),
                "reason": leave.reason,
                "status": leave.status,
                "appliedDate": leave.applied_date.strftime('%Y-%m-%d %H:%M')
            })
        
        return jsonify(leave_data), 200
        
    except Exception as e:
        print(f"Get leave requests error: {e}")
        return jsonify({"message": "Failed to fetch leave requests"}), 500
    finally:
        db.close()


@admin_bp.route('/leave-requests/<int:request_id>/approve', methods=['POST'])
@admin_required
def approve_leave(request_id):
    """Approve a leave request"""
    admin_id = request.current_user_id
    
    db = SessionLocal()
    try:
        leave_request = db.query(LeaveRequest).filter(
            LeaveRequest.id == request_id
        ).first()
        
        if not leave_request:
            return jsonify({"message": "Leave request not found"}), 404
        
        if leave_request.status != 'pending':
            return jsonify({"message": "Leave request already processed"}), 400
        
        leave_request.status = 'approved'
        leave_request.approved_by = admin_id
        leave_request.approval_date = datetime.utcnow()
        
        db.commit()
        
        return jsonify({"message": "Leave request approved successfully"}), 200
        
    except Exception as e:
        db.rollback()
        print(f"Approve leave error: {e}")
        return jsonify({"message": "Failed to approve leave request"}), 500
    finally:
        db.close()


@admin_bp.route('/leave-requests/<int:request_id>/decline', methods=['POST'])
@admin_required
def decline_leave(request_id):
    """Decline a leave request"""
    admin_id = request.current_user_id
    
    db = SessionLocal()
    try:
        leave_request = db.query(LeaveRequest).filter(
            LeaveRequest.id == request_id
        ).first()
        
        if not leave_request:
            return jsonify({"message": "Leave request not found"}), 404
        
        if leave_request.status != 'pending':
            return jsonify({"message": "Leave request already processed"}), 400
        
        leave_request.status = 'declined'
        leave_request.approved_by = admin_id
        leave_request.approval_date = datetime.utcnow()
        
        db.commit()
        
        return jsonify({"message": "Leave request declined"}), 200
        
    except Exception as e:
        db.rollback()
        print(f"Decline leave error: {e}")
        return jsonify({"message": "Failed to decline leave request"}), 500
    finally:
        db.close()


@admin_bp.route('/departments', methods=['GET'])
@admin_required
def get_departments():
    """Get all departments"""
    db = SessionLocal()
    try:
        departments = db.query(Department).all()
        
        dept_data = []
        for dept in departments:
            # Count employees in department
            emp_count = db.query(func.count(EmployeeProfile.id)).filter(
                EmployeeProfile.department_id == dept.id
            ).scalar() or 0
            
            dept_data.append({
                "id": dept.id,
                "name": dept.name,
                "description": dept.description,
                "employeeCount": emp_count
            })
        
        return jsonify(dept_data), 200
        
    except Exception as e:
        print(f"Get departments error: {e}")
        return jsonify({"message": "Failed to fetch departments"}), 500
    finally:
        db.close()


@admin_bp.route('/departments', methods=['POST'])
@admin_required
def create_department():
    """Create a new department"""
    data = request.get_json()
    
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    
    if not name:
        return jsonify({"message": "Department name is required"}), 400
    
    db = SessionLocal()
    try:
        # Check if department exists
        existing = db.query(Department).filter(Department.name == name).first()
        if existing:
            return jsonify({"message": "Department already exists"}), 409
        
        new_dept = Department(name=name, description=description)
        db.add(new_dept)
        db.commit()
        db.refresh(new_dept)
        
        return jsonify({
            "message": "Department created successfully",
            "id": new_dept.id,
            "name": new_dept.name
        }), 201
        
    except Exception as e:
        db.rollback()
        print(f"Create department error: {e}")
        return jsonify({"message": "Failed to create department"}), 500
    finally:
        db.close()