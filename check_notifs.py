from database import engine, Notification
from sqlalchemy.orm import Session

def check_notifications():
    with Session(engine) as session:
        notifs = session.query(Notification).order_by(Notification.created_at.desc()).limit(10).all()
        print(f"Total notifications found: {len(notifs)}")
        for n in notifs:
            print(f"ID: {n.id}, UserID: {n.user_id}, Title: {n.title}, CreatedAt: {n.created_at}")

if __name__ == "__main__":
    check_notifications()
