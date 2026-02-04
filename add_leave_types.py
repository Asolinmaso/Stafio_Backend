"""
Script to add default leave types to the database
Run this once to initialize leave types
"""
from database import SessionLocal, LeaveType

def add_default_leave_types():
    db = SessionLocal()
    
    # Default leave types
    leave_types = [
        {"name": "Casual Leave", "description": "For personal matters and emergencies", "max_days_per_year": 12},
        {"name": "Sick Leave", "description": "For illness and medical appointments", "max_days_per_year": 12},
        {"name": "Annual Leave", "description": "Yearly vacation leave", "max_days_per_year": 15},
        {"name": "Maternity Leave", "description": "For expecting mothers", "max_days_per_year": 180},
        {"name": "Paternity Leave", "description": "For new fathers", "max_days_per_year": 15},
    ]
    
    try:
        for lt in leave_types:
            # Check if already exists
            existing = db.query(LeaveType).filter(LeaveType.name == lt["name"]).first()
            if not existing:
                new_type = LeaveType(
                    name=lt["name"],
                    description=lt["description"],
                    max_days_per_year=lt["max_days_per_year"]
                )
                db.add(new_type)
                print(f"Added: {lt['name']}")
            else:
                print(f"Already exists: {lt['name']}")
        
        db.commit()
        print("\nDefault leave types added successfully!")
        
        # Show all leave types
        all_types = db.query(LeaveType).all()
        print("\nAvailable leave types:")
        for lt in all_types:
            print(f"  ID: {lt.id} - {lt.name} ({lt.max_days_per_year} days/year)")
            
    except Exception as e:
        db.rollback()
        print(f"Error: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    add_default_leave_types()
