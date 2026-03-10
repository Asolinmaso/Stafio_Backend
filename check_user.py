from database import SessionLocal, User

db = SessionLocal()
try:
    u = db.query(User).filter((User.username == 'sherica') | (User.email == 'shericajoseph21@gmail.com') | (User.phone == '9788893245')).first()
    if u:
        print(f"User EXISTS: ID={u.id}, Username={u.username}, Email={u.email}, Phone={u.phone}")
    else:
        print("User does NOT exist.")
finally:
    db.close()
