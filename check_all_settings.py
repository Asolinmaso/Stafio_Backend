from database import SessionLocal, SystemSettings

db = SessionLocal()
try:
    settings = db.query(SystemSettings).all()
    for s in settings:
        print(f"Key: {s.setting_key}, Value: {s.setting_value}, Type: {s.setting_type}")
finally:
    db.close()
