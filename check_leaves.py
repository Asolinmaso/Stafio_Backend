from database import engine, LeaveRequest
from sqlalchemy.orm import Session

def check_leaves():
    with Session(engine) as session:
        leaves = session.query(LeaveRequest).order_by(LeaveRequest.applied_date.desc()).limit(10).all()
        print(f"Latest 10 leave requests:")
        for l in leaves:
            print(f"ID: {l.id}, UserID: {l.user_id}, Status: {l.status}, NumDays: {l.num_days}")

if __name__ == "__main__":
    check_leaves()
