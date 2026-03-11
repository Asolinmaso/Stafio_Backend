from database import SessionLocal, Attendance
db = SessionLocal()
records = db.query(Attendance.id, Attendance.user_id, Attendance.date, Attendance.check_in).all()
print('Total records:', len(records))
for r in records:
    print(r)
db.close()
