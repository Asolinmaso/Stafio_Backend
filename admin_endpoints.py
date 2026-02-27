"""
Admin Endpoints Module
Additional API endpoints for admin section functionality
"""
from flask import Blueprint, jsonify, request
from database import SessionLocal, User, LeaveRequest, LeaveType, TeamMember, EmployeeProfile, Department
from functools import wraps
from datetime import datetime
from sqlalchemy.exc import IntegrityError
import json

# Create Blueprint for admin endpoints
admin_bp = Blueprint('admin_endpoints', __name__)


# ============================================================================
# AUTHENTICATION DECORATORS
# ============================================================================

def admin_required():
    """Decorator to require admin role for endpoints"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_role = request.headers.get('X-User-Role', 'employee')
            if user_role != 'admin':
                return jsonify({"message": "Admin access required"}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ============================================================================
# ALL LEAVE RECORDS ENDPOINT
# ============================================================================

@admin_bp.route('/api/all_leave_records', methods=['GET'])
@admin_required()
def get_all_leave_records():
    """
    Get all leave records for admin view
    Returns: List of all leave requests with employee info, department, leave type
    Tables Used: leave_requests, users, leave_types, employee_profiles
    """
    db = SessionLocal()
    try:
        # Query all leave requests with joins
        results = db.query(
            LeaveRequest,
            User,
            LeaveType
        ).join(
            User, LeaveRequest.user_id == User.id
        ).join(
            LeaveType, LeaveRequest.leave_type_id == LeaveType.id
        ).order_by(LeaveRequest.applied_date.desc()).all()
        
        leave_records = []
        for req, user, leave_type in results:
            # Get employee profile for department info
            emp_profile = db.query(EmployeeProfile).filter(
                EmployeeProfile.user_id == user.id
            ).first()
            
            # Calculate days
            days = (req.end_date - req.start_date).days + 1
            
            leave_records.append({
                "id": req.id,
                "employeeId": user.id,
                "employeeName": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
                "email": user.email,
                "department": emp_profile.department if emp_profile and emp_profile.department else "Not Assigned",
                "leaveType": leave_type.name,
                "startDate": req.start_date.strftime('%Y-%m-%d'),
                "endDate": req.end_date.strftime('%Y-%m-%d'),
                "days": days,
                "reason": req.reason or "",
                "status": req.status,
                "appliedDate": req.applied_date.strftime('%Y-%m-%d') if req.applied_date else "",
                "approvedBy": req.approved_by
            })
        
        return jsonify(leave_records), 200
        
    except Exception as e:
        print(f"Error in get_all_leave_records: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


# ============================================================================
# LEAVE BY DEPARTMENT ENDPOINT
# ============================================================================

@admin_bp.route('/api/leave_by_department', methods=['GET'])
@admin_required()
def get_leave_by_department():
    """
    Get leave records filtered by department
    Query Params: department (required)
    Tables Used: leave_requests, users, leave_types, employee_profiles
    """
    department = request.args.get('department', '')
    
    if not department:
        return jsonify({"message": "Department parameter is required"}), 400
    
    db = SessionLocal()
    try:
        # Get users in the specified department
        dept_users = db.query(User.id).join(
            EmployeeProfile, EmployeeProfile.user_id == User.id
        ).filter(
            EmployeeProfile.department == department
        ).all()
        
        user_ids = [u[0] for u in dept_users]
        
        if not user_ids:
            return jsonify([]), 200
        
        # Query leave requests for those users
        results = db.query(
            LeaveRequest,
            User,
            LeaveType
        ).join(
            User, LeaveRequest.user_id == User.id
        ).join(
            LeaveType, LeaveRequest.leave_type_id == LeaveType.id
        ).filter(
            LeaveRequest.user_id.in_(user_ids)
        ).order_by(LeaveRequest.applied_date.desc()).all()
        
        leave_records = []
        for req, user, leave_type in results:
            days = (req.end_date - req.start_date).days + 1
            
            leave_records.append({
                "id": req.id,
                "employeeId": user.id,
                "employeeName": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
                "email": user.email,
                "department": department,
                "leaveType": leave_type.name,
                "startDate": req.start_date.strftime('%Y-%m-%d'),
                "endDate": req.end_date.strftime('%Y-%m-%d'),
                "days": days,
                "reason": req.reason or "",
                "status": req.status,
                "appliedDate": req.applied_date.strftime('%Y-%m-%d') if req.applied_date else ""
            })
        
        return jsonify(leave_records), 200
        
    except Exception as e:
        print(f"Error in get_leave_by_department: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


# ============================================================================
# GET DEPARTMENTS LIST
# ============================================================================

@admin_bp.route('/api/departments', methods=['GET'])
def get_departments():
    """
    Get list of all departments
    Tables Used: departments, employee_profiles
    """
    db = SessionLocal()
    try:
        # Get from departments table
        departments = db.query(Department).all()
        dept_list = [{"id": d.id, "name": d.name, "description": d.description} for d in departments]
        
        # Also get unique departments from employee_profiles
        profile_depts = db.query(EmployeeProfile.department).filter(
            EmployeeProfile.department.isnot(None),
            EmployeeProfile.department != ""
        ).distinct().all()
        
        existing_names = {d["name"] for d in dept_list}
        for dept in profile_depts:
            if dept[0] and dept[0] not in existing_names:
                dept_list.append({"id": None, "name": dept[0], "description": ""})
        
        return jsonify(dept_list), 200
        
    except Exception as e:
        print(f"Error in get_departments: {str(e)}")
        return jsonify([]), 200
    finally:
        db.close()


# ============================================================================
# MY TEAM ENDPOINT
# ============================================================================

@admin_bp.route('/api/my_team', methods=['GET'])
def get_my_team():
    """
    Get team members for the logged-in manager
    Headers: X-User-ID (manager's user id)
    Tables Used: team_members, users, employee_profiles
    """
    manager_id = request.headers.get('X-User-ID')
    
    if not manager_id:
        return jsonify({"message": "User ID header required"}), 400
    
    db = SessionLocal()
    try:
        # Get team members for this manager
        team_members = db.query(TeamMember, User).join(
            User, TeamMember.member_id == User.id
        ).filter(
            TeamMember.manager_id == int(manager_id)
        ).all()
        
        team_list = []
        for tm, user in team_members:
            # Get employee profile for additional info
            emp_profile = db.query(EmployeeProfile).filter(
                EmployeeProfile.user_id == user.id
            ).first()
            
            team_list.append({
                "id": user.id,
                "name": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
                "email": user.email,
                "phone": user.phone or "",
                "department": emp_profile.department if emp_profile and emp_profile.department else "Not Assigned",
                "position": emp_profile.position if emp_profile and emp_profile.position else emp_profile.emp_type if emp_profile and emp_profile.emp_type else "Not Specified",
                "status": emp_profile.status if emp_profile and emp_profile.status else "Active"
            })
        
        # If no team members in team_members table, return all employees for admin
        if not team_list:
            user_role = request.headers.get('X-User-Role', 'employee')
            if user_role == 'admin':
                # Return all employees for admin
                employees = db.query(User).filter(User.role == 'employee').all()
                for user in employees:
                    emp_profile = db.query(EmployeeProfile).filter(
                        EmployeeProfile.user_id == user.id
                    ).first()
                    
                    team_list.append({
                        "id": user.id,
                        "name": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
                        "email": user.email,
                        "phone": user.phone or "",
                        "department": emp_profile.department if emp_profile and emp_profile.department else "Not Assigned",
                        "position": emp_profile.position if emp_profile and emp_profile.position else emp_profile.emp_type if emp_profile and emp_profile.emp_type else "Not Specified",
                        "status": emp_profile.status if emp_profile and emp_profile.status else "Active"
                    })
        
        return jsonify(team_list), 200
        
    except Exception as e:
        print(f"Error in get_my_team: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


# ============================================================================
# ADD TEAM MEMBER ENDPOINT
# ============================================================================

@admin_bp.route('/api/my_team', methods=['POST'])
@admin_required()
def add_team_member():
    """
    Add a team member for a manager
    Body: { manager_id, member_id }
    Tables Used: team_members
    """
    data = request.get_json()
    manager_id = data.get('manager_id')
    member_id = data.get('member_id')
    
    if not manager_id or not member_id:
        return jsonify({"message": "manager_id and member_id are required"}), 400
    
    db = SessionLocal()
    try:
        # Check if already exists
        existing = db.query(TeamMember).filter(
            TeamMember.manager_id == manager_id,
            TeamMember.member_id == member_id
        ).first()
        
        if existing:
            return jsonify({"message": "Team member already exists"}), 400
        
        new_member = TeamMember(
            manager_id=manager_id,
            member_id=member_id
        )
        db.add(new_member)
        db.commit()
        
        return jsonify({"message": "Team member added successfully"}), 201
        
    except Exception as e:
        db.rollback()
        print(f"Error in add_team_member: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


# ============================================================================
# EMPLOYEE LEAVE BALANCE FOR REPORTS
# ============================================================================

@admin_bp.route('/api/employee_leave_balance/<int:user_id>', methods=['GET'])
@admin_required()
def get_employee_leave_balance(user_id):
    """
    Get leave balance for a specific employee (for admin reports)
    Tables Used: leave_balances, leave_types, leave_requests
    """
    from database import LeaveBalance
    
    db = SessionLocal()
    try:
        current_year = datetime.now().year
        
        # Get all leave types with balances
        leave_types = db.query(LeaveType).all()
        
        balance_summary = []
        for lt in leave_types:
            # Get allocated balance
            balance = db.query(LeaveBalance).filter(
                LeaveBalance.user_id == user_id,
                LeaveBalance.leave_type_id == lt.id,
                LeaveBalance.year == current_year
            ).first()
            
            allocated = float(balance.balance) if balance else float(lt.max_days_per_year)
            
            # Get used days (approved leaves)
            used_days = db.query(LeaveRequest).filter(
                LeaveRequest.user_id == user_id,
                LeaveRequest.leave_type_id == lt.id,
                LeaveRequest.status == 'approved'
            ).all()
            
            used = sum((req.end_date - req.start_date).days + 1 for req in used_days)
            
            balance_summary.append({
                "leaveType": lt.name,
                "allocated": allocated,
                "used": used,
                "remaining": max(0, allocated - used)
            })
        
        return jsonify(balance_summary), 200
        
    except Exception as e:
        print(f"Error in get_employee_leave_balance: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


# ============================================================================
# ADMIN PROFILE - FULL PROFILE DATA FOR POPUP
# ============================================================================

# @admin_bp.route('/admin_profile/<int:user_id>', methods=['GET'])
# def get_admin_profile(user_id):
#     """
#     Get full admin profile data for Profile Details popup
#     Tables Used: users, employee_profiles
#     """
#     db = SessionLocal()
#     try:
#         user = db.query(User).filter(User.id == user_id).first()
        
#         if not user:
#             return jsonify({"message": "User not found"}), 404
        
#         emp_profile = db.query(EmployeeProfile).filter(
#             EmployeeProfile.user_id == user_id
#         ).first()
        
#         # Get supervisor and hr manager names
#         supervisor_name = ""
#         hr_manager_name = ""
#         if emp_profile:
#             if emp_profile.supervisor_id:
#                 supervisor = db.query(User).filter(User.id == emp_profile.supervisor_id).first()
#                 if supervisor:
#                     supervisor_name = f"{supervisor.first_name or ''} {supervisor.last_name or ''}".strip() or supervisor.username
#             if emp_profile.hr_manager_id:
#                 hr_manager = db.query(User).filter(User.id == emp_profile.hr_manager_id).first()
#                 if hr_manager:
#                     hr_manager_name = f"{hr_manager.first_name or ''} {hr_manager.last_name or ''}".strip() or hr_manager.username
        
#         # Format education dates
#         edu_dates = ""
#         if emp_profile and emp_profile.edu_start_date and emp_profile.edu_end_date:
#             edu_dates = f"{emp_profile.edu_start_date.strftime('%d/%m/%Y')} - {emp_profile.edu_end_date.strftime('%d/%m/%Y')}"
        
#         # Build profile data
#         profile_data = {
#             "profile": {
#                 "firstName": user.first_name or "",
#                 "lastName": user.last_name or "",
#                 "name": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
#                 "position": emp_profile.position if emp_profile and emp_profile.position else emp_profile.emp_type if emp_profile and emp_profile.emp_type else "",
#                 "employmentType": emp_profile.emp_type if emp_profile else "",
#                 "primarySupervisor": supervisor_name,
#                 "department": emp_profile.department if emp_profile else "",
#                 "hrManager": hr_manager_name,
#                 "gender": emp_profile.gender if emp_profile else "",
#                 "dateOfBirth": emp_profile.dob.strftime('%Y-%m-%d') if emp_profile and emp_profile.dob else "",
#                 "bloodGroup": emp_profile.blood_group if emp_profile and emp_profile.blood_group else "",
#                 "maritalStatus": emp_profile.marital_status if emp_profile and emp_profile.marital_status else "",
#                 "portfolio": emp_profile.portfolio if emp_profile and emp_profile.portfolio else "",
#                 "status": emp_profile.status if emp_profile and emp_profile.status else "Active",
#                 "email": user.email or "",
#                 "phone": user.phone or "",
#                 "location": emp_profile.location if emp_profile and emp_profile.location else "",
#                 "address": emp_profile.address if emp_profile and emp_profile.address else "",
#                 "skills": emp_profile.skills.split(',') if emp_profile and emp_profile.skills else [],
#                 "profileImage": emp_profile.profile_image if emp_profile and emp_profile.profile_image else ""
#             },
#             "education": {
#                 "institution": emp_profile.institution if emp_profile and emp_profile.institution else "",
#                 "startEndDate": edu_dates,
#                 "course": emp_profile.qualification if emp_profile and emp_profile.qualification else "",
#                 "specialization": emp_profile.specialization if emp_profile and emp_profile.specialization else ""
#             },
#             "experience": {
#                 "company": emp_profile.prev_company if emp_profile and emp_profile.prev_company else "",
#                 "jobTitle": emp_profile.prev_job_title if emp_profile and emp_profile.prev_job_title else "",
#                 "startDate": emp_profile.exp_start_date.strftime('%Y-%m-%d') if emp_profile and emp_profile.exp_start_date else "",
#                 "endDate": emp_profile.exp_end_date.strftime('%Y-%m-%d') if emp_profile and emp_profile.exp_end_date else "",
#                 "responsibilities": emp_profile.responsibilities if emp_profile and emp_profile.responsibilities else "",
#                 "totalYears": str(emp_profile.total_experience_years) if emp_profile and emp_profile.total_experience_years else ""
#             },
#             "bank": {
#                 "bankName": emp_profile.bank_name if emp_profile and emp_profile.bank_name else "",
#                 "branch": emp_profile.bank_branch if emp_profile and emp_profile.bank_branch else "",
#                 "accountNumber": emp_profile.account_number if emp_profile and emp_profile.account_number else "",
#                 "ifsc": emp_profile.ifsc_code if emp_profile and emp_profile.ifsc_code else "",
#                 "aadhaar": emp_profile.aadhaar_number if emp_profile and emp_profile.aadhaar_number else "",
#                 "pan": emp_profile.pan_number if emp_profile and emp_profile.pan_number else ""
#             },
#             "documents": []
#         }
        
#         return jsonify(profile_data), 200
        
#     except Exception as e:
#         print(f"Error in get_admin_profile: {str(e)}")
#         return jsonify({"message": f"Error: {str(e)}"}), 500
#     finally:
#         db.close()


# ============================================================================
# ADMIN PROFILE - UPDATE
# ============================================================================

@admin_bp.route('/admin_profile/<int:user_id>', methods=['PUT'])
@admin_required()
def update_admin_profile(user_id):
    db = SessionLocal()
    try:
        data = request.json

        user = db.query(User).filter(User.id == user_id).first()
        emp_profile = db.query(EmployeeProfile).filter(
            EmployeeProfile.user_id == user_id
        ).first()

        if not user or not emp_profile:
            return jsonify({"message": "User not found"}), 404

        profile = data.get("profile", {})
        education = data.get("education", {})
        experience = data.get("experience", {})
        bank = data.get("bank", {})

        # ================= USER =================
        user.email = profile.get("email", user.email)
        user.phone = profile.get("phone", user.phone)

        # ================= PROFILE =================
        emp_profile.position = profile.get("position")
        emp_profile.emp_type = profile.get("empType")
        emp_profile.department = profile.get("department")
        emp_profile.gender = profile.get("gender")
        emp_profile.marital_status = profile.get("maritalStatus")
        emp_profile.blood_group = profile.get("bloodGroup")
        emp_profile.location = profile.get("location")
        emp_profile.address = profile.get("address")
        emp_profile.portfolio = education.get("portfolio")
        emp_profile.status = profile.get("status")
        emp_profile.supervisor_id = profile.get("supervisor_id")
        emp_profile.hr_manager_id = profile.get("hr_manager_id")

        # DOB
        dob = profile.get("dob")
        if dob:
            emp_profile.dob = datetime.strptime(dob, "%Y-%m-%d").date()

        # ================= EDUCATION =================
        emp_profile.institution = education.get("institution")
        emp_profile.qualification = education.get("qualification")
        emp_profile.specialization = education.get("specialization")

        edu_start = education.get("eduStartDate")
        edu_end = education.get("eduEndDate")

        if edu_start:
            emp_profile.edu_start_date = datetime.strptime(edu_start, "%Y-%m-%d").date()
        if edu_end:
            emp_profile.edu_end_date = datetime.strptime(edu_end, "%Y-%m-%d").date()

        # ================= EXPERIENCE =================
        emp_profile.prev_company = experience.get("company")
        emp_profile.prev_job_title = experience.get("jobTitle")
        emp_profile.responsibilities = experience.get("responsibilities")

        exp_start = experience.get("expStartDate")
        exp_end = experience.get("expEndDate")

        if exp_start and exp_start != "0001-01-01":
            emp_profile.exp_start_date = datetime.strptime(exp_start, "%Y-%m-%d").date()

        if exp_end and exp_end != "0001-01-01":
            emp_profile.exp_end_date = datetime.strptime(exp_end, "%Y-%m-%d").date()

        # ================= BANK =================
        emp_profile.bank_name = bank.get("bankName")
        emp_profile.bank_branch = bank.get("branch")
        emp_profile.account_number = bank.get("accountNumber")
        emp_profile.ifsc_code = bank.get("ifsc")
        emp_profile.aadhaar_number = bank.get("aadhaar")
        emp_profile.pan_number = bank.get("pan")

        db.commit()

        return jsonify({"message": "Profile updated successfully"}), 200

    except Exception as e:
        db.rollback()
        print("❌ UPDATE ERROR:", str(e))
        return jsonify({"message": str(e)}), 500

    finally:
        db.close()

        

# ============================================================================
# ADMIN SETTINGS - GENERAL SETTINGS
# ============================================================================

@admin_bp.route('/api/settings/general', methods=['GET'])
@admin_required()
def get_general_settings():
    """
    Get all general system settings
    Tables Used: system_settings
    """
    from database import SystemSettings
    
    db = SessionLocal()
    try:
        # Default settings
        default_settings = {
            'system_language': 'english',
            'admin_theme': 'light',
            'user_theme': 'light',
            'system_font': 'default',
            'date_format': 'DD/MM/YYYY',
            'allow_signup': False,
            'allow_manager_edit': False
        }
        
        # Get saved settings from database
        settings = db.query(SystemSettings).all()
        
        for s in settings:
            if s.setting_key in default_settings:
                # Parse boolean values
                if s.setting_type == 'boolean':
                    default_settings[s.setting_key] = s.setting_value.lower() == 'true'
                else:
                    default_settings[s.setting_key] = s.setting_value
        
        return jsonify(default_settings), 200
        
    except Exception as e:
        print(f"Error in get_general_settings: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@admin_bp.route('/api/settings/general', methods=['PUT'])
@admin_required()
def update_general_settings():
    """
    Update general system settings
    Body: { system_language, admin_theme, user_theme, system_font, date_format, allow_signup, allow_manager_edit }
    Tables Used: system_settings
    """
    from database import SystemSettings
    
    data = request.get_json()
    db = SessionLocal()
    
    try:
        user_id = request.headers.get('X-User-ID', 1)
        
        settings_to_save = {
            'system_language': ('string', data.get('system_language', 'english')),
            'admin_theme': ('string', data.get('admin_theme', 'light')),
            'user_theme': ('string', data.get('user_theme', 'light')),
            'system_font': ('string', data.get('system_font', 'default')),
            'date_format': ('string', data.get('date_format', 'DD/MM/YYYY')),
            'allow_signup': ('boolean', str(data.get('allow_signup', False))),
            'allow_manager_edit': ('boolean', str(data.get('allow_manager_edit', False)))
        }
        
        for key, (setting_type, value) in settings_to_save.items():
            existing = db.query(SystemSettings).filter(SystemSettings.setting_key == key).first()
            
            if existing:
                existing.setting_value = value
                existing.setting_type = setting_type
                existing.updated_by = int(user_id)
                existing.updated_at = datetime.utcnow()
            else:
                new_setting = SystemSettings(
                    setting_key=key,
                    setting_value=value,
                    setting_type=setting_type,
                    updated_by=int(user_id)
                )
                db.add(new_setting)
        
        db.commit()
        return jsonify({"message": "General settings updated successfully"}), 200
        
    except Exception as e:
        db.rollback()
        print(f"Error in update_general_settings: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


# ============================================================================
# ADMIN SETTINGS - BREAK TIMES
# ============================================================================

@admin_bp.route('/api/settings/break_times', methods=['GET'])
@admin_required()
def get_break_times():
    """
    Get break time settings
    Tables Used: system_settings
    """
    from database import SystemSettings
    
    db = SessionLocal()
    try:
        # Default break times
        break_times = {
            'lunch_break': '1:00 PM - 2:00 PM',
            'coffee_break': '4:00 PM - 4:15 PM',
            'custom_breaks': []
        }
        
        # Get from database
        settings = db.query(SystemSettings).filter(
            SystemSettings.setting_key.in_(['lunch_break', 'coffee_break', 'custom_breaks'])
        ).all()
        
        for s in settings:
            if s.setting_key == 'custom_breaks' and s.setting_value:
                try:
                    break_times['custom_breaks'] = json.loads(s.setting_value)
                except:
                    break_times['custom_breaks'] = []
            elif s.setting_value:
                break_times[s.setting_key] = s.setting_value
        
        return jsonify(break_times), 200
        
    except Exception as e:
        print(f"Error in get_break_times: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@admin_bp.route('/api/settings/break_times', methods=['PUT'])
@admin_required()
def update_break_times():
    """
    Update break time settings
    Body: { lunch_break, coffee_break, custom_breaks }
    Tables Used: system_settings
    """
    from database import SystemSettings
    
    data = request.get_json()
    db = SessionLocal()
    
    try:
        user_id = request.headers.get('X-User-ID', 1)
        
        break_settings = {
            'lunch_break': data.get('lunch_break', '1:00 PM - 2:00 PM'),
            'coffee_break': data.get('coffee_break', '4:00 PM - 4:15 PM')
        }
        
        # Handle custom breaks as JSON
        if 'custom_breaks' in data:
            break_settings['custom_breaks'] = json.dumps(data.get('custom_breaks', []))
        
        for key, value in break_settings.items():
            existing = db.query(SystemSettings).filter(SystemSettings.setting_key == key).first()
            
            if existing:
                existing.setting_value = value
                existing.updated_by = int(user_id)
                existing.updated_at = datetime.utcnow()
            else:
                new_setting = SystemSettings(
                    setting_key=key,
                    setting_value=value,
                    setting_type='json' if key == 'custom_breaks' else 'string',
                    updated_by=int(user_id)
                )
                db.add(new_setting)
        
        db.commit()
        return jsonify({"message": "Break times updated successfully"}), 200
        
    except Exception as e:
        db.rollback()
        print(f"Error in update_break_times: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


# ============================================================================
# ADMIN SETTINGS - DEPARTMENTS CRUD
# ============================================================================

@admin_bp.route('/api/departments', methods=['POST'])
@admin_required()
def create_department():
    """
    Create a new department
    Body: { name, description, manager_id }
    Tables Used: departments
    """
    data = request.get_json()
    name = data.get('name')
    
    if not name:
        return jsonify({"message": "Department name is required"}), 400
    
    db = SessionLocal()
    try:
        # Check if department already exists
        existing = db.query(Department).filter(Department.name == name).first()
        if existing:
            return jsonify({"message": "Department already exists"}), 400
        
        new_dept = Department(
            name=name,
            description=data.get('description', ''),
            manager_id=data.get('manager_id')
        )
        db.add(new_dept)
        db.commit()
        
        return jsonify({
            "message": "Department created successfully",
            "id": new_dept.id,
            "name": new_dept.name
        }), 201
        
    except Exception as e:
        db.rollback()
        print(f"Error in create_department: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@admin_bp.route('/api/departments/<int:dept_id>', methods=['PUT'])
@admin_required()
def update_department(dept_id):
    """
    Update a department
    Body: { name, description, manager_id }
    Tables Used: departments
    """
    data = request.get_json()
    
    db = SessionLocal()
    try:
        dept = db.query(Department).filter(Department.id == dept_id).first()
        
        if not dept:
            return jsonify({"message": "Department not found"}), 404
        
        if 'name' in data:
            dept.name = data['name']
        if 'description' in data:
            dept.description = data['description']
        if 'manager_id' in data:
            dept.manager_id = data['manager_id']
        
        db.commit()
        return jsonify({"message": "Department updated successfully"}), 200
        
    except Exception as e:
        db.rollback()
        print(f"Error in update_department: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@admin_bp.route('/api/departments/<int:dept_id>', methods=['DELETE'])
@admin_required()
def delete_department(dept_id):
    """
    Delete a department
    Tables Used: departments
    """
    db = SessionLocal()
    try:
        dept = db.query(Department).filter(Department.id == dept_id).first()
        
        if not dept:
            return jsonify({"message": "Department not found"}), 404
        
        db.delete(dept)
        db.commit()
        return jsonify({"message": "Department deleted successfully"}), 200
        
    except Exception as e:
        db.rollback()
        print(f"Error in delete_department: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


# ============================================================================
# ADMIN SETTINGS - BASIC INFO (Admin Profile)
# ============================================================================

@admin_bp.route('/api/settings/basic_info', methods=['GET'])
@admin_required()
def get_admin_basic_info():
    """
    Get admin's basic info
    Tables Used: users
    """
    user_id = request.headers.get('X-User-ID')
    
    if not user_id:
        return jsonify({"message": "User ID required"}), 400
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == int(user_id)).first()
        
        if not user:
            return jsonify({"message": "User not found"}), 404
        
        # Get employee profile for position
        emp_profile = db.query(EmployeeProfile).filter(
            EmployeeProfile.user_id == int(user_id)
        ).first()
        
        return jsonify({
            "firstName": user.first_name or "",
            "lastName": user.last_name or "",
            "email": user.email or "",
            "phone": user.phone or "",
            "position": emp_profile.emp_type if emp_profile and emp_profile.emp_type else "",
            "role": user.role or "admin"
        }), 200
        
    except Exception as e:
        print(f"Error in get_admin_basic_info: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@admin_bp.route('/api/settings/basic_info', methods=['PUT'])
@admin_required()
def update_admin_basic_info():
    """
    Update admin's basic info
    Body: { firstName, lastName, email, phone, position, role }
    Tables Used: users, employee_profiles
    """
    data = request.get_json()
    user_id = request.headers.get('X-User-ID')
    
    if not user_id:
        return jsonify({"message": "User ID required"}), 400
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == int(user_id)).first()
        
        if not user:
            return jsonify({"message": "User not found"}), 404
        
        # Update user fields
        if 'firstName' in data:
            user.first_name = data['firstName']
        if 'lastName' in data:
            user.last_name = data['lastName']
        if 'email' in data:
            user.email = data['email']
        if 'phone' in data:
            user.phone = data['phone']
        if 'role' in data:
            user.role = data['role']
        
        # Update position in employee profile
        if 'position' in data:
            emp_profile = db.query(EmployeeProfile).filter(
                EmployeeProfile.user_id == int(user_id)
            ).first()
            
            if emp_profile:
                emp_profile.emp_type = data['position']
            else:
                new_profile = EmployeeProfile(
                    user_id=int(user_id),
                    emp_type=data['position']
                )
                db.add(new_profile)
        
        db.commit()
        return jsonify({"message": "Basic info updated successfully"}), 200
        
    except Exception as e:
        db.rollback()
        print(f"Error in update_admin_basic_info: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


# ============================================================================
# ADMIN SETTINGS - TEAM LIST WITH ROLES
# ============================================================================

@admin_bp.route('/api/settings/team', methods=['GET'])
@admin_required()
def get_settings_team():
    """
    Get all users with their roles for settings team tab
    Tables Used: users
    """
    db = SessionLocal()
    try:
        users = db.query(User).all()
        
        team_list = []
        for user in users:
            team_list.append({
                "id": user.id,
                "name": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
                "email": user.email,
                "role": user.role,
                "dateJoined": user.created_at.strftime('%b %d, %Y - %I:%M %p') if user.created_at else ""
            })
        
        return jsonify(team_list), 200
        
    except Exception as e:
        print(f"Error in get_settings_team: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@admin_bp.route('/api/settings/team/<int:user_id>', methods=['PUT'])
@admin_required()
def update_user_role(user_id):
    """
    Update a user's role
    Body: { role }
    Tables Used: users
    """
    data = request.get_json()
    new_role = data.get('role')
    
    if not new_role:
        return jsonify({"message": "Role is required"}), 400
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            return jsonify({"message": "User not found"}), 404
        
        user.role = new_role
        db.commit()
        
        return jsonify({"message": "User role updated successfully"}), 200
        
    except Exception as e:
        db.rollback()
        print(f"Error in update_user_role: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


# ============================================================================
# ADMIN SETTINGS - DEPARTMENTS WITH MEMBER COUNT
# ============================================================================

@admin_bp.route('/api/settings/departments', methods=['GET'])
@admin_required()
def get_settings_departments():
    """
    Get departments with member counts and heads for settings
    Tables Used: departments, users, employee_profiles
    """
    db = SessionLocal()
    try:
        departments = db.query(Department).all()
        
        dept_list = []
        for dept in departments:
            # Count members in this department
            member_count = db.query(EmployeeProfile).filter(
                EmployeeProfile.department == dept.name
            ).count()
            
            # Get department head name
            head_name = ""
            if dept.manager_id:
                manager = db.query(User).filter(User.id == dept.manager_id).first()
                if manager:
                    head_name = f"{manager.first_name or ''} {manager.last_name or ''}".strip() or manager.username
            
            dept_list.append({
                "id": dept.id,
                "name": dept.name,
                "description": dept.description or "",
                "memberCount": member_count,
                "headName": head_name,
                "managerId": dept.manager_id
            })
        
        return jsonify(dept_list), 200
        
    except Exception as e:
        print(f"Error in get_settings_departments: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()



# ============================================================================
# EMPLOYEE ADDITION WITH AUTO TEAM MEMBER SYNC
# ============================================================================

def sync_team_member_relationship(db, employee_user_id, supervisor_id):
    """
    Helper function to sync team_members table when employee has a supervisor
    - Creates or updates team_member entry
    - Removes old relationship if supervisor changes
    """
    if not supervisor_id:
        return
    
    try:
        # Check if employee already has a team relationship
        existing_tm = db.query(TeamMember).filter(
            TeamMember.member_id == employee_user_id
        ).first()
        
        if existing_tm:
            # If supervisor changed, update it
            if existing_tm.manager_id != supervisor_id:
                existing_tm.manager_id = supervisor_id
        else:
            # Create new team member relationship
            new_tm = TeamMember(
                manager_id=supervisor_id,
                member_id=employee_user_id
            )
            db.add(new_tm)
    except Exception as e:
        print(f"Error in sync_team_member_relationship: {str(e)}")
        raise


@admin_bp.route('/api/admin/add_employee', methods=['POST'])
@admin_required()
def add_employee():
    """
    Create a new employee with auto-generated employee_id
    Body: { first_name, last_name, email, phone, supervisor_id, hr_manager_id, 
            department, position, emp_type, status, joining_date, profile_image }
    Returns: Complete employee data including auto-generated employee_id
    """
    from werkzeug.security import generate_password_hash
    
    data = request.get_json()
    db = SessionLocal()
    
    try:
        # Validate required fields
        required_fields = ['first_name', 'last_name', 'email', 'phone']
        for field in required_fields:
            if not data.get(field):
                return jsonify({"message": f"{field} is required"}), 400
        
        # Create user account first (password will be email prefix or a default)
        default_password = data.get('email').split('@')[0] + "123"  # Default password
        hashed_password = generate_password_hash(default_password)
        
        new_user = User(
            username=data.get('email').split('@')[0],  # Use email prefix as username
            password_hash=hashed_password,
            email=data.get('email'),
            phone=data.get('phone'),
            first_name=data.get('first_name'),
            last_name=data.get('last_name'),
            role='employee'
        )
        db.add(new_user)
        db.flush()  # Get the user.id without committing
        
        # Auto-generate employee_id from user.id
        employee_id = str(new_user.id)
        
        # Parse joining date if provided
        joining_date = None
        if data.get('joining_date'):
            try:
                joining_date = datetime.strptime(data.get('joining_date'), '%Y-%m-%d').date()
            except:
                pass
        
        # Create employee profile
        new_profile = EmployeeProfile(
            user_id=new_user.id,
            emp_id=employee_id,
            emp_type=data.get('emp_type', 'Full Time'),
            department=data.get('department'),
            position=data.get('position'),
            supervisor_id=data.get('supervisor_id'),
            hr_manager_id=data.get('hr_manager_id'),
            status=data.get('status', 'Active'),
            profile_image=data.get('profile_image', '')
        )
        db.add(new_profile)
        
        # Auto-populate team_members if supervisor is assigned
        if data.get('supervisor_id'):
            sync_team_member_relationship(db, new_user.id, data.get('supervisor_id'))
        
        db.commit()
        db.refresh(new_user)
        db.refresh(new_profile)
        
        # Return complete employee data
        return jsonify({
            "message": "Employee added successfully",
            "employee": {
                "id": new_user.id,
                "employee_id": employee_id,
                "name": f"{new_user.first_name} {new_user.last_name}",
                "email": new_user.email,
                "phone": new_user.phone,
                "department": new_profile.department,
                "position": new_profile.position,
                "status": new_profile.status,
                "default_password": default_password  # Send to admin so they can inform employee
            }
        }), 201
        
    except IntegrityError as e:
        db.rollback()
        print(f"IntegrityError in add_employee: {str(e)}")
        return jsonify({"message": "Email or phone number already exists"}), 409
    except Exception as e:
        db.rollback()
        print(f"Error in add_employee: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


@admin_bp.route('/api/admin/supervisors', methods=['GET'])
@admin_required()
def get_supervisors():
    """
    Get list of all potential supervisors (admins and managers)
    Returns: List of users with id and name
    """
    db = SessionLocal()
    try:
        # Get all users who could be supervisors (admins and existing supervisors)
        supervisors = db.query(User).all()
        
        supervisor_list = []
        for user in supervisors:
            supervisor_list.append({
                "id": user.id,
                "name": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
                "email": user.email
            })
        
        return jsonify(supervisor_list), 200
        
    except Exception as e:
        print(f"Error in get_supervisors: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        db.close()


# ============================================================================
# REGISTER BLUEPRINT FUNCTION
# ============================================================================

def register_admin_endpoints(app):
    """Register the admin blueprint with the Flask app"""
    app.register_blueprint(admin_bp)
    print("Admin endpoints registered successfully")

