"""
One-time migration script to populate team_members table from employee_profiles
Run this script once to migrate existing manager-employee relationships
"""
from database import SessionLocal, EmployeeProfile, TeamMember, User

def migrate_team_members():
    """
    Populate team_members table based on existing supervisor_id in employee_profiles
    """
    db = SessionLocal()
    
    try:
        # Get all employee profiles with a supervisor assigned
        profiles = db.query(EmployeeProfile).filter(
            EmployeeProfile.supervisor_id.isnot(None)
        ).all()
        
        print(f"Found {len(profiles)} employees with supervisors")
        
        created_count = 0
        skipped_count = 0
        
        for profile in profiles:
            # Check if team member relationship already exists
            existing = db.query(TeamMember).filter(
                TeamMember.manager_id == profile.supervisor_id,
                TeamMember.member_id == profile.user_id
            ).first()
            
            if existing:
                print(f"  Skipped: Employee {profile.user_id} already has team relationship")
                skipped_count += 1
                continue
            
            # Create new team member entry
            new_tm = TeamMember(
                manager_id=profile.supervisor_id,
                member_id=profile.user_id
            )
            db.add(new_tm)
            created_count += 1
            
            # Get names for logging
            supervisor = db.query(User).filter(User.id == profile.supervisor_id).first()
            employee = db.query(User).filter(User.id == profile.user_id).first()
            
            if supervisor and employee:
                print(f"  Created: {employee.username} → {supervisor.username}")
        
        db.commit()
        
        print(f"\n✅ Migration complete!")
        print(f"   Created: {created_count} new team relationships")
        print(f"   Skipped: {skipped_count} existing relationships")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error during migration: {str(e)}")
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("TEAM MEMBERS MIGRATION SCRIPT")
    print("=" * 60)
    print("This will populate the team_members table from employee_profiles")
    print()
    
    response = input("Do you want to proceed? (yes/no): ")
    
    if response.lower() == 'yes':
        migrate_team_members()
    else:
        print("Migration cancelled")
