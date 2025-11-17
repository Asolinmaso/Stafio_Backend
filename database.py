"""
Database configuration and models for PostgreSQL using SQLAlchemy
"""
from sqlalchemy import create_engine, Column, Integer, String, Text, Date, DateTime, DECIMAL, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()

# Database configuration from environment variables or defaults
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres'),
    'database': os.getenv('DB_NAME', 'leave_management_db')
}

# Create database URL for SQLAlchemy
DATABASE_URL = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"

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
    
    # Relationships
    leave_balances = relationship("LeaveBalance", back_populates="user", cascade="all, delete-orphan")


class LeaveType(Base):
    __tablename__ = 'leave_types'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    max_days_per_year = Column(Integer, nullable=False)
    
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
    status = Column(Enum('pending', 'approved', 'declined', name='request_status'), default='pending')
    applied_date = Column(DateTime, default=datetime.utcnow)
    approved_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    approval_date = Column(DateTime, nullable=True)
    
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


# Create all tables
def init_db():
    """Initialize database tables for leave management"""
    Base.metadata.create_all(bind=engine)

