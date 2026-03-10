from database import engine, User
from sqlalchemy.orm import Session

def list_users():
    with Session(engine) as session:
        users = session.query(User).all()
        for u in users:
            print(f"ID: {u.id}, Username: {u.username}, Name: {u.first_name} {u.last_name}, Role: {u.role}")

if __name__ == "__main__":
    list_users()
