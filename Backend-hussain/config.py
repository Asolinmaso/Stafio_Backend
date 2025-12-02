import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask Configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'change-this-in-production')
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = True
    
    # JWT Configuration
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'change-this-jwt-secret')
    JWT_EXPIRATION_HOURS = int(os.getenv('JWT_EXPIRATION_HOURS', 24))
    JWT_ALGORITHM = 'HS256'
    
    # Database Configuration
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_USER = os.getenv('DB_USER', 'postgres')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'Admin1910')
    DB_NAME = os.getenv('DB_NAME', 'leave_management_db')
    
    # Email Configuration
    EMAIL_USER = os.getenv('EMAIL_USER')
    EMAIL_PASS = os.getenv('EMAIL_PASS')
    EMAIL_FROM = os.getenv('EMAIL_FROM', 'noreply@company.com')
    SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
    
    # OTP Configuration
    OTP_EXPIRATION_MINUTES = int(os.getenv('OTP_EXPIRATION_MINUTES', 10))
    OTP_LENGTH = 6
    
    # CORS Configuration
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*').split(',')
    
    @staticmethod
    def validate():
        """Validate critical configuration"""
        if not Config.EMAIL_USER or not Config.EMAIL_PASS:
            print("WARNING: Email configuration not set. Email features will not work.")
        if Config.SECRET_KEY == 'change-this-in-production':
            print("WARNING: Using default SECRET_KEY. Change this in production!")
        if Config.JWT_SECRET_KEY == 'change-this-jwt-secret':
            print("WARNING: Using default JWT_SECRET_KEY. Change this in production!")
