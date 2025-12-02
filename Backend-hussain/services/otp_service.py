import secrets
from datetime import datetime, timedelta
from database import SessionLocal, OTP, User
from services.email_service import EmailService
from config import Config


class OTPService:
    """Service for OTP generation and verification"""
    
    @staticmethod
    def generate_otp() -> str:
        """Generate random OTP code"""
        return "".join(secrets.choice("0123456789") for _ in range(Config.OTP_LENGTH))
    
    @staticmethod
    def create_otp(email: str) -> tuple[bool, str]:
        """Create and send OTP for email"""
        db = SessionLocal()
        try:
            # Check if email exists
            user = db.query(User).filter(User.email == email).first()
            if not user:
                return False, "Email not registered"
            
            # Generate OTP
            otp_code = OTPService.generate_otp()
            expires_at = datetime.utcnow() + timedelta(minutes=Config.OTP_EXPIRATION_MINUTES)
            
            # Save OTP to database
            new_otp = OTP(
                email=email,
                otp_code=otp_code,
                expires_at=expires_at
            )
            db.add(new_otp)
            db.commit()
            
            # Send OTP email
            email_sent = EmailService.send_otp_email(email, otp_code)
            
            if email_sent:
                return True, "OTP sent successfully"
            else:
                return False, "Failed to send OTP email"
            
        except Exception as e:
            db.rollback()
            print(f"Error creating OTP: {e}")
            return False, "Failed to generate OTP"
        finally:
            db.close()
    
    @staticmethod
    def verify_otp(email: str, otp_code: str) -> tuple[bool, str]:
        """Verify OTP code"""
        db = SessionLocal()
        try:
            otp_record = (
                db.query(OTP)
                .filter(
                    OTP.email == email,
                    OTP.otp_code == otp_code,
                    OTP.is_used == 0,
                    OTP.expires_at > datetime.utcnow()
                )
                .first()
            )
            
            if not otp_record:
                return False, "Invalid or expired OTP"
            
            # Mark OTP as used
            otp_record.is_used = 1
            db.commit()
            
            return True, "OTP verified successfully"
            
        except Exception as e:
            db.rollback()
            print(f"Error verifying OTP: {e}")
            return False, "Failed to verify OTP"
        finally:
            db.close()
    
    @staticmethod
    def cleanup_expired_otps():
        """Delete expired OTPs (call this periodically)"""
        db = SessionLocal()
        try:
            deleted = db.query(OTP).filter(
                OTP.expires_at < datetime.utcnow()
            ).delete()
            db.commit()
            print(f"Cleaned up {deleted} expired OTPs")
        except Exception as e:
            db.rollback()
            print(f"Error cleaning up OTPs: {e}")
        finally:
            db.close()
