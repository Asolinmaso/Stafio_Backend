#hi

from sqlalchemy import create_engine, Column, Integer, String, Text, Date, DateTime, DECIMAL, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import urllib.parse
from config import Config
import os

Base = declarative_base()

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'Admin1910'),
    'database': os.getenv('DB_NAME', 'leave_management_db')
}

# Create database URL
encoded_password = urllib.parse.quote(Config.DB_PASSWORD)
DATABASE_URL = f"postgresql://{Config.DB_USER}:{encoded_password}@{Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}"

# Create engine
engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Database dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# class User(Base):
#     __tablename__ = 'users'
    
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     username = Column(String(50), unique=True, nullable=False)
#     password_hash = Column(String(255), nullable=False)
#     email = Column(String(100), unique=True, nullable=False)
#     phone = Column(String(20), unique=True)
#     first_name = Column(String(50))
#     last_name = Column(String(50))
#     role = Column(Enum('employee', 'admin', name='user_role'), default='employee')
#     created_at = Column(DateTime, default=datetime.utcnow)
    
#     # Relationships
#     leave_balances = relationship("LeaveBalance", back_populates="user", cascade="all, delete-orphan")
#     employee_profile = relationship("EmployeeProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
#     bank_details = relationship("BankDetails", back_populates="user", uselist=False, cascade="all, delete-orphan")

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    phone = Column(String(20), unique=True)
    first_name = Column(String(50))
    last_name = Column(String(50))
    role = Column(Enum('employee', 'admin', name='user_role'), default='employee')
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    leave_balances = relationship("LeaveBalance", back_populates="user", cascade="all, delete-orphan")
    employee_profile = relationship("EmployeeProfile", back_populates="user", uselist=False, cascade="all, delete-orphan", foreign_keys="[EmployeeProfile.user_id]")  # ← ADD foreign_keys HERE
    bank_details = relationship("BankDetails", back_populates="user", uselist=False, cascade="all, delete-orphan")

class LeaveType(Base):
    __tablename__ = 'leave_types'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    max_days_per_year = Column(Integer, nullable=False)
    
    leave_balances = relationship("LeaveBalance", back_populates="leave_type", cascade="all, delete-orphan")
    leave_requests = relationship("LeaveRequest", back_populates="leave_type", cascade="all, delete-orphan")


class LeaveBalance(Base):
    __tablename__ = 'leave_balances'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    leave_type_id = Column(Integer, ForeignKey('leave_types.id', ondelete='CASCADE'), nullable=False)
    balance = Column(DECIMAL(5, 2), default=0.00)
    year = Column(Integer, nullable=False)
    
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
    num_days = Column(DECIMAL(3, 1), nullable=False)
    reason = Column(Text)
    status = Column(Enum('pending', 'approved', 'declined', name='request_status'), default='pending')
    applied_date = Column(DateTime, default=datetime.utcnow)
    approved_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    approval_date = Column(DateTime)
    
    user = relationship("User", foreign_keys=[user_id])
    leave_type = relationship("LeaveType", back_populates="leave_requests")
    approver = relationship("User", foreign_keys=[approved_by])


class Attendance(Base):
    __tablename__ = 'attendance'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    date = Column(Date, nullable=False)
    check_in = Column(DateTime)
    check_out = Column(DateTime)
    status = Column(Enum('on_time', 'late', 'absent', 'half_day', name='attendance_status'))
    work_hours = Column(DECIMAL(5, 2))
    late_minutes = Column(Integer, default=0)
    overtime_minutes = Column(Integer, default=0)
    
    user = relationship("User")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'date', name='unique_attendance_per_day'),
    )


class Regularization(Base):
    __tablename__ = 'regularizations'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    attendance_id = Column(Integer, ForeignKey('attendance.id', ondelete='CASCADE'))
    date = Column(Date, nullable=False)
    attendance_type = Column(String(50))
    reason = Column(Text, nullable=False)
    status = Column(Enum('pending', 'approved', 'rejected', name='regularization_status'), default='pending')
    applied_date = Column(DateTime, default=datetime.utcnow)
    approved_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    approval_date = Column(DateTime)
    
    user = relationship("User", foreign_keys=[user_id])
    attendance = relationship("Attendance")
    approver = relationship("User", foreign_keys=[approved_by])


class Holiday(Base):
    __tablename__ = 'holidays'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True)
    title = Column(String(100), nullable=False)
    description = Column(Text)
    is_mandatory = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)


class Department(Base):
    __tablename__ = 'departments'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


# class EmployeeProfile(Base):
#     __tablename__ = 'employee_profiles'
    
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
#     employee_id = Column(String(50), unique=True)
#     department_id = Column(Integer, ForeignKey('departments.id'))
#     position = Column(String(100))
#     date_of_birth = Column(Date)
#     gender = Column(Enum('male', 'female', 'other', name='gender_type'))
#     marital_status = Column(String(20))
#     nationality = Column(String(50))
#     blood_group = Column(String(10))
#     address = Column(Text)
#     emergency_contact = Column(String(20))
#     emergency_relationship = Column(String(50))
#     date_joined = Column(Date)
#     employment_type = Column(String(50))
#     supervisor_id = Column(Integer, ForeignKey('users.id'))
#     hr_manager_id = Column(Integer, ForeignKey('users.id'))
#     location = Column(String(100))
#     status = Column(Enum('active', 'inactive', 'terminated', name='employee_status'), default='active')
    
#     user = relationship("User", foreign_keys=[user_id], back_populates="employee_profile")
#     department = relationship("Department")
#     supervisor = relationship("User", foreign_keys=[supervisor_id])
#     hr_manager = relationship("User", foreign_keys=[hr_manager_id])

class EmployeeProfile(Base):
    __tablename__ = 'employee_profiles'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    employee_id = Column(String(50), unique=True)
    department_id = Column(Integer, ForeignKey('departments.id'))
    position = Column(String(100))
    date_of_birth = Column(Date)
    gender = Column(Enum('male', 'female', 'other', name='gender_type'))
    marital_status = Column(String(20))
    nationality = Column(String(50))
    blood_group = Column(String(10))
    address = Column(Text)
    emergency_contact = Column(String(20))
    emergency_relationship = Column(String(50))
    date_joined = Column(Date)
    employment_type = Column(String(50))
    supervisor_id = Column(Integer, ForeignKey('users.id'))
    hr_manager_id = Column(Integer, ForeignKey('users.id'))
    location = Column(String(100))
    status = Column(Enum('active', 'inactive', 'terminated', name='employee_status'), default='active')
    
    user = relationship("User", foreign_keys=[user_id], back_populates="employee_profile")
    department = relationship("Department")
    supervisor = relationship("User", foreign_keys=[supervisor_id], overlaps="employee_profile")  # ← ADD overlaps
    hr_manager = relationship("User", foreign_keys=[hr_manager_id], overlaps="employee_profile")  # ← ADD overlaps

class BankDetails(Base):
    __tablename__ = 'bank_details'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    bank_name = Column(String(100))
    branch = Column(String(100))
    account_number = Column(String(50))
    ifsc_code = Column(String(20))
    aadhaar_number = Column(String(20))
    pan_number = Column(String(20))
    
    user = relationship("User", back_populates="bank_details")


class OTP(Base):
    __tablename__ = 'otps'

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(100), nullable=False)
    otp_code = Column(String(6), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Integer, default=0)


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    print("✓ Database tables initialized successfully!")
