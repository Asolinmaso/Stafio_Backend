from database import engine
from sqlalchemy import text

def check_raw_status():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id, status FROM leave_requests WHERE id IN (1, 10);"))
        for row in result:
            print(f"ID: {row[0]}, Status: |{row[1]}|")

if __name__ == "__main__":
    check_raw_status()
