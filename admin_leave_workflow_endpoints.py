# admin_leave_workflow_endpoints.py
"""
New API endpoints for Admin Leave/Regularization Approval Workflow

These endpoints enable a proper approval hierarchy where:
- Employee leave/regularization → Admin/HR approves (existing)
- Admin leave/regularization → Manager approves (NEW)

To integrate: Import and add these routes to your Flask app
"""

from flask import request, jsonify
from datetime import datetime
from database import SessionLocal, User, LeaveRequest, Regularization, LeaveType, EmployeeProfile
from functools import wraps


def register_admin_workflow_endpoints(app, custom_admin_required):
    """
    Register all admin workflow endpoints with the Flask app
    
    Args:
        app: Flask application instance
        custom_admin_required: The admin authentication decorator
    """
    
    # =============================================================================
    # ADMIN LEAVE APPROVAL WORKFLOW - NEW ENDPOINTS
    # =============================================================================
    
    # Admin Leave Request (goes to manager for approval)
    @app.route('/api/admin/leave-requests', methods=['POST'])
    @custom_admin_required()
    def create_admin_leave_request():
        """
        Create leave request by admin that requires manager approval.
        Unlike employee leave requests, admin requests go to their designated manager.
        """
        data = request.get_json()
        user_id = request.headers.get('X-User-ID')
        
        db = SessionLocal()
        try:
            # Get admin's profile to find their supervisor/manager
            profile = db.query(EmployeeProfile).filter(
                EmployeeProfile.user_id == int(user_id)
            ).first()
            
            if not profile or not profile.supervisor_id:
                return jsonify({
                    "message": "No supervisor/manager assigned. Please contact HR to assign a manager for leave approvals."
                }), 400
            
            # Validate required fields
            required_fields = ['leave_type_id', 'start_date', 'end_date', 'reason']
            missing = [f for f in required_fields if f not in data]
            if missing:
                return jsonify({
                    "message": f"Missing required fields: {', '.join(missing)}"
                }), 400
            
            # Parse dates
            start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()

            # Validate date order
            if end_date < start_date:
                return jsonify({"message": "End date cannot be before start date"}), 400

            # Calculate total days
            total_days = (end_date - start_date).days + 1

            # Determine day type (default full_day)
            day_type = data.get('day_type', 'full_day')

            if day_type == 'half_day':
                if total_days > 1:
                    return jsonify({
                        "message": "Half day leave can only be applied for a single day"
                    }), 400
                num_days = 0.5
            else:
                num_days = float(total_days)
            
            # Create admin leave request
            new_request = LeaveRequest(
                user_id=int(user_id),
                leave_type_id=data['leave_type_id'],
                start_date=start_date,
                end_date=end_date,
                num_days=num_days,
                day_type=day_type,
                reason=data['reason'],
                status='pending',
                approver_type='manager',  # NEW: Indicates manager approval needed
                designated_approver_id=profile.supervisor_id  # NEW: Who should approve
            )
            
            db.add(new_request)
            db.commit()
            db.refresh(new_request)
            
            # Get manager name for response
            manager = db.query(User).filter(User.id == profile.supervisor_id).first()
            manager_name = f"{manager.first_name} {manager.last_name}" if manager else "manager"
            
            return jsonify({
                "message": f"Leave request submitted to {manager_name} for approval",
                "id": new_request.id,
                "approver": manager_name
            }), 201
            
        except ValueError as e:
            return jsonify({"message": f"Invalid data format: {str(e)}"}), 400
        except Exception as e:
            db.rollback()
            print(f"Admin leave request error: {str(e)}")
            return jsonify({"message": f"Error: {str(e)}"}), 500
        finally:
            db.close()
    
    
    # Manager Leave Approvals (for viewing admin leave requests)
    @app.route('/api/manager/leave-approvals', methods=['GET'])
    def get_manager_leave_approvals():
        """
        Get all leave requests assigned to this manager for approval.
        These are requests from admins who report to this manager.
        """
        manager_id = request.headers.get('X-User-ID')
        
        if not manager_id:
            return jsonify({"message": "Manager ID required"}), 400
        
        db = SessionLocal()
        try:
            # Get leave requests where this user is the designated approver
            requests_data = db.query(LeaveRequest, User, LeaveType).join(
                User, LeaveRequest.user_id == User.id
            ).join(
                LeaveType, LeaveRequest.leave_type_id == LeaveType.id
            ).filter(
                LeaveRequest.designated_approver_id == int(manager_id),
                LeaveRequest.approver_type == 'manager'
            ).order_by(LeaveRequest.applied_date.desc()).all()
            
            result = []
            for req, user, leave_type in requests_data:
                profile = db.query(EmployeeProfile).filter(
                    EmployeeProfile.user_id == user.id
                ).first()
                
                result.append({
                    "id": req.id,
                    "name": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
                    "empId": profile.emp_id if profile and profile.emp_id else str(user.id),
                    "role": user.role,  # Will show "admin"
                    "type": leave_type.name,
                    "from": req.start_date.strftime('%d-%m-%Y'),
                    "to": req.end_date.strftime('%d-%m-%Y'),
                    "days": f"{req.num_days} Day(s)",
                    "reason": req.reason or "",
                    "requestDate": req.applied_date.strftime('%d-%m-%Y') if req.applied_date else "",
                    "status": req.status.capitalize()
                })
            
            return jsonify(result), 200
            
        except Exception as e:
            print(f"Manager leave approvals error: {str(e)}")
            return jsonify([]), 200
        finally:
            db.close()
    
    
    # Admin Regularization Request (goes to manager)
    @app.route('/api/admin/regularization', methods=['POST'])
    @custom_admin_required()
    def create_admin_regularization():
        """
        Create regularization request by admin that requires manager approval.
        """
        user_id = request.headers.get('X-User-ID')
        data = request.get_json() or {}
        
        db = SessionLocal()
        try:
            # Get admin's manager
            profile = db.query(EmployeeProfile).filter(
                EmployeeProfile.user_id == int(user_id)
            ).first()
            
            if not profile or not profile.supervisor_id:
                return jsonify({
                    "message": "No supervisor/manager assigned. Please contact HR to assign a manager for regularization approvals."
                }), 400
            
            # Validate required fields
            if not data.get('date') or not data.get('attendance_type'):
                return jsonify({
                    "message": "Date and attendance type are required"
                }), 400
            
            new_regularization = Regularization(
                user_id=int(user_id),
                date=datetime.strptime(data['date'], '%Y-%m-%d').date(),
                session_type=data.get('session_type', 'Full Day'),
                attendance_type=data['attendance_type'],
                reason=data.get('reason', ''),
                status='pending',
                approver_type='manager',  # NEW
                designated_approver_id=profile.supervisor_id  # NEW
            )
            
            db.add(new_regularization)
            db.commit()
            db.refresh(new_regularization)
            
            # Get manager name
            manager = db.query(User).filter(User.id == profile.supervisor_id).first()
            manager_name = f"{manager.first_name} {manager.last_name}" if manager else "manager"
            
            return jsonify({
                "message": f"Regularization request submitted to {manager_name} for approval",
                "id": new_regularization.id,
                "approver": manager_name
            }), 201
            
        except ValueError as e:
            return jsonify({"message": f"Invalid data format: {str(e)}"}), 400
        except Exception as e:
            db.rollback()
            print(f"Admin regularization error: {str(e)}")
            return jsonify({"message": f"Error: {str(e)}"}), 500
        finally:
            db.close()
    
    
    # Manager Regularization Approvals its for manager level
    @app.route('/api/manager/regularization-approvals', methods=['GET'])
    def get_manager_regularization_approvals():
        """
        Get regularization requests assigned to manager for approval.
        These are requests from admins who report to this manager.
        """
        manager_id = request.headers.get('X-User-ID')
        
        if not manager_id:
            return jsonify({"message": "Manager ID required"}), 400
        
        db = SessionLocal()
        try:
            requests_data = db.query(Regularization, User).join(
                User, Regularization.user_id == User.id
            ).filter(
                Regularization.designated_approver_id == int(manager_id),
                Regularization.approver_type == 'manager'
            ).order_by(Regularization.request_date.desc()).all()
            
            result = []
            for req, user in requests_data:
                profile = db.query(EmployeeProfile).filter(
                    EmployeeProfile.user_id == user.id
                ).first()
                
                result.append({
                    "id": req.id,
                    "name": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
                    "empId": profile.emp_id if profile and profile.emp_id else str(user.id),
                    "role": user.role,  # Will show "admin"
                    "regDate": f"{req.date.strftime('%d-%m-%Y')}/{req.session_type or 'Full Day'}",
                    "attendance": req.attendance_type or "Present",
                    "reason": req.reason or "",
                    "requestDate": req.request_date.strftime('%d-%m-%Y') if req.request_date else "",
                    "status": req.status.capitalize()
                })
            
            return jsonify(result), 200
            
        except Exception as e:
            print(f"Manager RA error: {str(e)}")
            return jsonify([]), 200
        finally:
            db.close()
    
    
    print("✓ Admin workflow endpoints registered successfully")
