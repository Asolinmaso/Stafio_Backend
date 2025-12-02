from flask import Blueprint, request, jsonify
from datetime import datetime, date, time, timedelta
from database import SessionLocal, Attendance, User
from auth import token_required, admin_required
from sqlalchemy import func

attendance_bp = Blueprint('attendance', __name__, url_prefix='/attendance')


@attendance_bp.route('/check-in', methods=['POST'])
@token_required
def check_in():
    """Record check-in time"""
    user_id = request.current_user_id
    today = date.today()
    now = datetime.now()
    
    db = SessionLocal()
    try:
        # Check if already checked in today
        existing = db.query(Attendance).filter(
            Attendance.user_id == user_id,
            Attendance.date == today
        ).first()
        
        if existing and existing.check_in:
            return jsonify({"message": "Already checked in today"}), 400
        
        # Determine if late (assuming 9:00 AM is on-time)
        on_time_threshold = time(9, 0)
        current_time = now.time()
        
        is_late = current_time > on_time_threshold
        late_minutes = 0
        
        if is_late:
            late_delta = datetime.combine(today, current_time) - datetime.combine(today, on_time_threshold)
            late_minutes = int(late_delta.total_seconds() / 60)
        
        if existing:
            # Update existing record
            existing.check_in = now
            existing.status = 'late' if is_late else 'on_time'
            existing.late_minutes = late_minutes
        else:
            # Create new record
            new_attendance = Attendance(
                user_id=user_id,
                date=today,
                check_in=now,
                status='late' if is_late else 'on_time',
                late_minutes=late_minutes
            )
            db.add(new_attendance)
        
        db.commit()
        
        return jsonify({
            "message": "Checked in successfully",
            "checkInTime": now.strftime('%H:%M:%S'),
            "status": "Late" if is_late else "On Time"
        }), 200
        
    except Exception as e:
        db.rollback()
        print(f"Check-in error: {e}")
        return jsonify({"message": "Failed to record check-in"}), 500
    finally:
        db.close()


@attendance_bp.route('/check-out', methods=['POST'])
@token_required
def check_out():
    """Record check-out time"""
    user_id = request.current_user_id
    today = date.today()
    now = datetime.now()
    
    db = SessionLocal()
    try:
        attendance = db.query(Attendance).filter(
            Attendance.user_id == user_id,
            Attendance.date == today
        ).first()
        
        if not attendance:
            return jsonify({"message": "No check-in record found for today"}), 400
        
        if attendance.check_out:
            return jsonify({"message": "Already checked out today"}), 400
        
        attendance.check_out = now
        
        # Calculate work hours
        if attendance.check_in:
            work_duration = now - attendance.check_in
            work_hours = work_duration.total_seconds() / 3600
            attendance.work_hours = round(work_hours, 2)
            
            # Calculate overtime (assuming 9 hours is standard)
            if work_hours > 9:
                overtime_hours = work_hours - 9
                attendance.overtime_minutes = int(overtime_hours * 60)
        
        db.commit()
        
        return jsonify({
            "message": "Checked out successfully",
            "checkOutTime": now.strftime('%H:%M:%S'),
            "workHours": f"{attendance.work_hours:.2f}" if attendance.work_hours else "0"
        }), 200
        
    except Exception as e:
        db.rollback()
        print(f"Check-out error: {e}")
        return jsonify({"message": "Failed to record check-out"}), 500
    finally:
        db.close()


@attendance_bp.route('/status', methods=['GET'])
@token_required
def get_attendance_status():
    """Get today's attendance status"""
    user_id = request.current_user_id
    today = date.today()
    
    db = SessionLocal()
    try:
        attendance = db.query(Attendance).filter(
            Attendance.user_id == user_id,
            Attendance.date == today
        ).first()
        
        if not attendance:
            return jsonify({
                "hasCheckedIn": False,
                "hasCheckedOut": False
            }), 200
        
        return jsonify({
            "hasCheckedIn": bool(attendance.check_in),
            "hasCheckedOut": bool(attendance.check_out),
            "checkInTime": attendance.check_in.strftime('%H:%M:%S') if attendance.check_in else None,
            "checkOutTime": attendance.check_out.strftime('%H:%M:%S') if attendance.check_out else None,
            "status": attendance.status,
            "workHours": float(attendance.work_hours) if attendance.work_hours else 0
        }), 200
        
    except Exception as e:
        print(f"Get attendance status error: {e}")
        return jsonify({"message": "Failed to fetch attendance status"}), 500
    finally:
        db.close()