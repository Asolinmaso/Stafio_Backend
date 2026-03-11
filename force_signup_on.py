from database import SessionLocal, SystemSettings

db = SessionLocal()
try:
    existing = db.query(SystemSettings).filter(SystemSettings.setting_key == 'allow_signup').first()
    if existing:
        existing.setting_value = 'True'
        existing.setting_type = 'boolean'
        print("Updated allow_signup to True")
    else:
        new_setting = SystemSettings(setting_key='allow_signup', setting_value='True', setting_type='boolean')
        db.add(new_setting)
        print("Created allow_signup as True")
    db.commit()
finally:
    db.close()
