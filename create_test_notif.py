from database import engine, Notification, User
from sqlalchemy.orm import Session
from datetime import datetime

def create_test_notif():
    with Session(engine) as session:
        # Get first employee
        user = session.query(User).filter(User.role == 'employee').first()
        if not user:
            print("No employee found")
            return
        
        notif = Notification(
            user_id=user.id,
            title="Test Notification",
            message="This is a test notification created at " + str(datetime.now()),
            notification_type="test",
            link="/",
            is_read=False,
            created_at=datetime.utcnow()
        )
        session.add(notif)
        session.commit()
        print(f"Created notification for user {user.username} (ID: {user.id})")

if __name__ == "__main__":
    create_test_notif()
