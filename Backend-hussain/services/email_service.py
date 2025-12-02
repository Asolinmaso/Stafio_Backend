import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import Config


class EmailService:
    """Service for sending emails"""
    
    @staticmethod
    def send_email(to_email: str, subject: str, body: str, is_html: bool = True) -> bool:
        """Send email using SMTP"""
        if not Config.EMAIL_USER or not Config.EMAIL_PASS:
            print("ERROR: Email configuration not set")
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = Config.EMAIL_FROM
            msg['To'] = to_email
            msg['Subject'] = subject
            
            content_type = 'html' if is_html else 'plain'
            msg.attach(MIMEText(body, content_type))

            server = smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT)
            server.starttls()
            server.login(Config.EMAIL_USER, Config.EMAIL_PASS.strip())
            server.sendmail(Config.EMAIL_FROM, to_email, msg.as_string())
            server.quit()
            
            print(f"✓ Email sent successfully to {to_email}")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            print(f"✗ Email authentication failed: {e}")
            return False
        except smtplib.SMTPException as e:
            print(f"✗ SMTP error: {e}")
            return False
        except Exception as e:
            print(f"✗ Email sending failed: {e}")
            return False
    
    @staticmethod
    def send_otp_email(to_email: str, otp_code: str) -> bool:
        """Send OTP email"""
        subject = "Your Password Reset OTP"
        body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <h2 style="color: #333;">Password Reset Request</h2>
                <p>You have requested to reset your password.</p>
                <p>Your OTP code is:</p>
                <h1 style="color: #4CAF50; letter-spacing: 5px;">{otp_code}</h1>
                <p>This OTP will expire in {Config.OTP_EXPIRATION_MINUTES} minutes.</p>
                <p>If you did not request this, please ignore this email.</p>
                <hr>
                <p style="color: #666; font-size: 12px;">This is an automated email. Please do not reply.</p>
            </body>
        </html>
        """
        return EmailService.send_email(to_email, subject, body, is_html=True)
    
    @staticmethod
    def send_welcome_email(to_email: str, username: str) -> bool:
        """Send welcome email to new users"""
        subject = "Welcome to Stafio!"
        body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <h2 style="color: #333;">Welcome to Stafio, {username}!</h2>
                <p>Your account has been successfully created.</p>
                <p>You can now log in and start using our leave management system.</p>
                <hr>
                <p style="color: #666; font-size: 12px;">This is an automated email. Please do not reply.</p>
            </body>
        </html>
        """
        return EmailService.send_email(to_email, subject, body, is_html=True)
