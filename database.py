"""
Database configuration and models for PostgreSQL using SQLAlchemy
"""
from sqlalchemy import create_engine, Column, Integer, String, Text, Date, DateTime, DECIMAL, ForeignKey, Enum, UniqueConstraint, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy import func, extract
from datetime import datetime, date, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()

# Database configuration from environment variables or defaults
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'root'),
    'database': os.getenv('DB_NAME', 'leave_management_db')
}

# Create database URL for SQLAlchemy
import urllib.parse

encoded_password = urllib.parse.quote(DB_CONFIG['password'])

DATABASE_URL = f"postgresql://{DB_CONFIG['user']}:{encoded_password}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"

# Create engine
engine = create_engine(DATABASE_URL, echo=False)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# SQLAlchemy Models
class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    first_name = Column(String(50))
    last_name = Column(String(50))
    role = Column(Enum('employee', 'admin', name='user_role'), default='employee')
    created_at = Column(DateTime, default=datetime.utcnow)
    phone = Column(String(20), unique=True)

    
    # Relationships
    leave_balances = relationship("LeaveBalance", back_populates="user", cascade="all, delete-orphan")


class LeaveType(Base):
    __tablename__ = 'leave_types'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    max_days_per_year = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    type = Column(String(20), default="All", nullable=False)
    
    # Relationships
    leave_balances = relationship("LeaveBalance", back_populates="leave_type", cascade="all, delete-orphan")
    leave_requests = relationship("LeaveRequest", back_populates="leave_type", cascade="all, delete-orphan")


class LeaveBalance(Base):
    __tablename__ = 'leave_balances'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    leave_type_id = Column(Integer, ForeignKey('leave_types.id', ondelete='CASCADE'), nullable=False)
    balance = Column(DECIMAL(5, 2), default=0.00)
    year = Column(Integer, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="leave_balances")
    leave_type = relationship("LeaveType", back_populates="leave_balances")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'leave_type_id', 'year', name='unique_balance'),
    )


class LeaveRequest(Base):
    __tablename__ = 'leave_requests'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    leave_type_id = Column(Integer, ForeignKey('leave_types.id', ondelete='CASCADE'), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    num_days = Column(Integer, nullable=False)
    reason = Column(Text)
    status = Column(Enum('pending', 'approved', 'rejected', name='request_status'), default='pending')
    applied_date = Column(DateTime, default=datetime.utcnow)
    approved_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    approval_date = Column(DateTime, nullable=True)
    approval_reason = Column(Text)
    rejection_reason = Column(Text)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    leave_type = relationship("LeaveType", back_populates="leave_requests")
    approver = relationship("User", foreign_keys=[approved_by])


class OTP(Base):
    __tablename__ = 'otps'

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(100), nullable=False)
    otp_code = Column(String(6), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Integer, default=0)  # 0 = not used, 1 = used


# Employee Extended Profile
class EmployeeProfile(Base):
    __tablename__ = 'employee_profiles'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    emp_id = Column(String(20), unique=True)  # Employee ID like "100849"
    gender = Column(String(10))
    dob = Column(Date)
    marital_status = Column(String(20))
    nationality = Column(String(50))
    blood_group = Column(String(5))
    address = Column(Text)
    emergency_contact = Column(String(20))
    emergency_relationship = Column(String(50))
    emp_type = Column(String(50))  # Full-time, Part-time, Contract
    department = Column(String(50))
    position = Column(String(50))
    location = Column(String(100))
    supervisor_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    hr_manager_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    status = Column(String(20), default='Active')
    profile_image = Column(String(255))
    
    # Education fields
    institution = Column(String(100))
    edu_location = Column(String(100))
    edu_start_date = Column(Date)
    edu_end_date = Column(Date)
    qualification = Column(String(100))
    specialization = Column(String(100))
    skills = Column(Text)  # JSON array as string
    portfolio = Column(String(255))
    
    # Experience fields
    prev_company = Column(String(100))
    prev_job_title = Column(String(100))
    exp_start_date = Column(Date)
    exp_end_date = Column(Date)
    responsibilities = Column(Text)
    total_experience_years = Column(DECIMAL(4, 1))
    
    # Bank details
    bank_name = Column(String(100))
    bank_branch = Column(String(100))
    account_number = Column(String(50))
    ifsc_code = Column(String(20))
    aadhaar_number = Column(String(20))
    pan_number = Column(String(20))
    
    user = relationship("User", foreign_keys=[user_id])
    supervisor = relationship("User", foreign_keys=[supervisor_id])
    hr_manager = relationship("User", foreign_keys=[hr_manager_id])


# Attendance Tracking
class Attendance(Base):
    __tablename__ = 'attendance'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    date = Column(Date, nullable=False)
    check_in = Column(DateTime)
    check_out = Column(DateTime)
    status = Column(String(20))  # 'On Time', 'Late Login', 'Absent', 'On Leave', 'Half Day'
    late_minutes = Column(Integer, default=0)
    overtime_minutes = Column(Integer, default=0)
    work_hours = Column(String(20))
    
    user = relationship("User")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'date', name='unique_attendance'),
    )
    
#Calculating breaks
class BreakSession(Base):
    __tablename__ = 'break_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    date = Column(Date, nullable=False)
    break_start = Column(DateTime, nullable=False)
    break_end = Column(DateTime)
    break_minutes = Column(Integer, default=0)

    user = relationship("User")

# Regularization Requests
class Regularization(Base):
    __tablename__ = 'regularizations'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    date = Column(Date, nullable=False)
    session_type = Column(String(20))  # Full Day, Half Day(AN), Half Day(FN)
    attendance_type = Column(String(20))  # Present, Absent
    reason = Column(Text)
    status = Column(String(20), default='pending')  # pending, approved, rejected
    request_date = Column(DateTime, default=datetime.utcnow)
    approved_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    approval_date = Column(DateTime)
    
    user = relationship("User", foreign_keys=[user_id])
    approver = relationship("User", foreign_keys=[approved_by])


# Holidays
class Holiday(Base):
    __tablename__ = 'holidays'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True)
    title = Column(String(100), nullable=False)
    description = Column(Text)
    is_optional = Column(Boolean, default=False)
    year = Column(Integer, nullable=False)


# Department
class Department(Base):
    __tablename__ = 'departments'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    manager_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    
    manager = relationship("User")


# Team (for My Team features)
class TeamMember(Base):
    __tablename__ = 'team_members'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    manager_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    member_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    manager = relationship("User", foreign_keys=[manager_id])
    member = relationship("User", foreign_keys=[member_id])
    
    __table_args__ = (
        UniqueConstraint('manager_id', 'member_id', name='unique_team_member'),
    )


# =============================================================================
# PAYROLL MODULE
# =============================================================================

class SalaryStructure(Base):
    """Salary structure for each employee"""
    __tablename__ = 'salary_structures'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    basic_salary = Column(DECIMAL(12, 2), nullable=False)
    hra = Column(DECIMAL(10, 2), default=0)  # House Rent Allowance
    conveyance = Column(DECIMAL(10, 2), default=0)
    medical_allowance = Column(DECIMAL(10, 2), default=0)
    special_allowance = Column(DECIMAL(10, 2), default=0)
    other_allowances = Column(DECIMAL(10, 2), default=0)
    pf_deduction = Column(DECIMAL(10, 2), default=0)  # Provident Fund
    tax_deduction = Column(DECIMAL(10, 2), default=0)
    other_deductions = Column(DECIMAL(10, 2), default=0)
    effective_from = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User")


class Payroll(Base):
    """Monthly payroll records"""
    __tablename__ = 'payroll'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    month = Column(Integer, nullable=False)  # 1-12
    year = Column(Integer, nullable=False)
    basic_salary = Column(DECIMAL(12, 2), nullable=False)
    total_allowances = Column(DECIMAL(12, 2), default=0)
    total_deductions = Column(DECIMAL(12, 2), default=0)
    net_salary = Column(DECIMAL(12, 2), nullable=False)
    working_days = Column(Integer, default=0)
    days_worked = Column(Integer, default=0)
    leave_days = Column(Integer, default=0)
    status = Column(String(20), default='pending')  # pending, processed, paid
    payment_date = Column(DateTime, nullable=True)
    processed_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", foreign_keys=[user_id])
    processor = relationship("User", foreign_keys=[processed_by])
    
    __table_args__ = (
        UniqueConstraint('user_id', 'month', 'year', name='unique_payroll'),
    )


# =============================================================================
# PERFORMANCE TRACKING MODULE
# =============================================================================

class Task(Base):
    """Employee tasks for performance tracking"""
    __tablename__ = 'tasks'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    priority = Column(String(20), default='medium')  # low, medium, high
    status = Column(String(20), default='pending')  # pending, in_progress, completed
    due_date = Column(Date)
    completed_date = Column(Date)
    assigned_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    project_name = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", foreign_keys=[user_id])
    assigner = relationship("User", foreign_keys=[assigned_by])


class PerformanceReview(Base):
    """Performance review records"""
    __tablename__ = 'performance_reviews'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    reviewer_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    review_period_month = Column(Integer, nullable=False)  # 1-12
    review_period_year = Column(Integer, nullable=False)
    tasks_completed = Column(Integer, default=0)
    projects_completed = Column(Integer, default=0)
    feedback_score = Column(DECIMAL(3, 1))  # 0.0 - 5.0
    strengths = Column(Text)
    improvements = Column(Text)
    comments = Column(Text)
    status = Column(String(20), default='draft')  # draft, submitted, acknowledged
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", foreign_keys=[user_id])
    reviewer = relationship("User", foreign_keys=[reviewer_id])
    
    __table_args__ = (
        UniqueConstraint('user_id', 'review_period_month', 'review_period_year', name='unique_review'),
    )


# =============================================================================
# DOCUMENT MANAGEMENT MODULE
# =============================================================================

class Document(Base):
    """Employee documents storage"""
    __tablename__ = 'documents'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    document_type = Column(String(50), nullable=False)  # offer_letter, payslip, id_proof, etc.
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)  # in bytes
    mime_type = Column(String(100))
    uploaded_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    description = Column(Text)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", foreign_keys=[user_id])
    uploader = relationship("User", foreign_keys=[uploaded_by])


# =============================================================================
# SYSTEM SETTINGS & NOTIFICATIONS
# =============================================================================

class SystemSettings(Base):
    """System-wide settings"""
    __tablename__ = 'system_settings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    setting_key = Column(String(100), unique=True, nullable=False)
    setting_value = Column(Text)
    setting_type = Column(String(20), default='string')  # string, boolean, number, json
    description = Column(Text)
    updated_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    updater = relationship("User")


class Notification(Base):
    """User notifications"""
    __tablename__ = 'notifications'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(Text)
    notification_type = Column(String(50))  # leave, attendance, payroll, broadcast, etc.
    is_read = Column(Boolean, default=False)
    link = Column(String(255))  # Optional link to redirect
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User")


class Broadcast(Base):
    """Admin broadcast messages"""
    __tablename__ = 'broadcasts'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    sent_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    target_audience = Column(String(50), default='all')  # all, employees, admins
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    
    sender = relationship("User")


# Create all tables
def init_db():
    """Initialize database tables for leave management"""
    Base.metadata.create_all(bind=engine)

