from database import engine, User
from sqlalchemy.orm import Session

def check_user_3():
    with Session(engine) as session:
        u = session.query(User).filter(User.id == 3).first()
        if u:
            print(f"ID: {u.id}")
            print(f"Username: {u.username}")
            print(f"Name: {u.first_name} {u.last_name}")
            print(f"Role: {u.role}")
        else:
            print("User 3 not found")

if __name__ == "__main__":
    check_user_3()
