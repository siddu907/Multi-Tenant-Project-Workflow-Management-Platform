import os

from app.database import SessionLocal
from app.models.role import Role
from app.models.user import User
from app.core.security import hash_password


def create_super_admin(email: str, name: str, password: str) -> None:
    db = SessionLocal()

    try:
        existing_super_admin = (
            db.query(User)
            .join(Role, Role.id == User.role_id)
            .filter(Role.name == "super_admin")
            .first()
        )

        if existing_super_admin:
            raise ValueError(
                "A super admin already exists. Only one super admin is allowed."
            )

        existing_user = db.query(User).filter(User.email == email).first()

        if existing_user:
            raise ValueError(
                f"User with email '{email}' already exists."
            )

        super_admin_role = (
            db.query(Role)
            .filter(Role.name == "super_admin")
            .first()
        )

        if super_admin_role is None:
            super_admin_role = Role(name="super_admin")
            db.add(super_admin_role)
            db.flush()

        super_admin = User(
            name=name,
            email=email,
            hashed_password=hash_password(password),
            role_id=super_admin_role.id,
            is_active=True,
        )

        db.add(super_admin)
        db.commit()
        db.refresh(super_admin)

        print(f"Super admin created successfully: {super_admin.email}")
        print(f"Super Admin ID: {super_admin.id}")
        print(f"Role ID: {super_admin.role_id}")

    except Exception as exc:
        db.rollback()
        raise exc

    finally:
        db.close()


if __name__ == "__main__":
    admin_name = os.getenv("SUPER_ADMIN_NAME", "").strip() or input("Enter super admin full name: ").strip()
    admin_email = os.getenv("SUPER_ADMIN_EMAIL", "").strip().lower() or input("Enter super admin email: ").strip().lower()
    admin_password = os.getenv("SUPER_ADMIN_PASSWORD", "") or input("Enter super admin password: ").strip()

    if not admin_name or not admin_email or not admin_password:
        raise SystemExit("SUPER_ADMIN_NAME, SUPER_ADMIN_EMAIL, and SUPER_ADMIN_PASSWORD must be provided.")

    create_super_admin(
        admin_email,
        admin_name,
        admin_password
    )