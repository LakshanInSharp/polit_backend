# utils/initialize_roles.py
from sqlalchemy.orm import Session
from models import Role  # adjust import according to your structure

def initialize_roles(db: Session):
    default_roles = ["admin", "system_admin", "user"]

    for role_name in default_roles:
        # Check if the role already exists
        existing_role = db.query(Role).filter_by(name=role_name).first()
        if not existing_role:
            new_role = Role(name=role_name)
            db.add(new_role)
    db.commit()
