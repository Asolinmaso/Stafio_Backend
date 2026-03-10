from database import engine, LeaveRequest, Notification
from sqlalchemy.orm import Session
from datetime import datetime

def fix_missing_notifications():
    with Session(engine) as session:
        # Find approved or rejected leaves
        leaves = session.query(LeaveRequest).filter(LeaveRequest.status.in_(['approved', 'rejected'])).all()
        print(f"Found {len(leaves)} approved/rejected leaves.")
        
        created_count = 0
        for l in leaves:
            # Check if a notification already exists for this specific leave event
            # (Simple heuristic: same user, similar title, recently? Or just create one if none exist for this user about this leave)
            # Actually, to be safe and simple, I'll just create notifications if the user has 0 notifications.
            existing_count = session.query(Notification).filter(Notification.user_id == l.user_id, Notification.notification_type == 'leave').count()
            
            if existing_count == 0:
                status_title = "Approved" if l.status == 'approved' else "Rejected"
                notif = Notification(
                    user_id=l.user_id,
                    title=f"Leave Request {status_title}",
                    message=f"Your leave request for {l.start_date} has been {l.status}.",
                    notification_type="leave",
                    link="/employee/leave-history",
                    created_at=datetime.utcnow()
                )
                session.add(notif)
                created_count += 1
        
        session.commit()
        print(f"Created {created_count} missing notifications.")

if __name__ == "__main__":
    fix_missing_notifications()
