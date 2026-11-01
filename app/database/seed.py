"""Sample users and employees. Run with: python -m app.database.seed"""

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal, init_db
from app.database.models import Employee, User

logger = logging.getLogger(__name__)

SAMPLE_USERS = [
    {"name": "Aarav Sharma", "email": "aarav.sharma@example.com", "role": "admin"},
    {"name": "Priya Patel", "email": "priya.patel@example.com", "role": "customer"},
    {"name": "Rahul Verma", "email": "rahul.verma@example.com", "role": "customer"},
    {"name": "Sara Khan", "email": "sara.khan@example.com", "role": "manager"},
    {"name": "John Smith", "email": "john.smith@example.com", "role": "customer"},
    {"name": "Emily Johnson", "email": "emily.johnson@example.com", "role": "customer", "is_active": False},
]

SAMPLE_EMPLOYEES = [
    {"name": "Neha Gupta", "email": "neha.gupta@company.example", "department": "Engineering",
     "job_title": "Senior Backend Engineer", "hire_date": date(2021, 3, 15)},
    {"name": "Vikram Singh", "email": "vikram.singh@company.example", "department": "Engineering",
     "job_title": "Engineering Manager", "hire_date": date(2019, 7, 1)},
    {"name": "Ananya Iyer", "email": "ananya.iyer@company.example", "department": "Marketing",
     "job_title": "Marketing Lead", "hire_date": date(2022, 1, 10)},
    {"name": "Michael Brown", "email": "michael.brown@company.example", "department": "Sales",
     "job_title": "Account Executive", "hire_date": date(2023, 5, 22)},
    {"name": "Fatima Ali", "email": "fatima.ali@company.example", "department": "Finance",
     "job_title": "Financial Analyst", "hire_date": date(2020, 11, 2)},
    {"name": "David Wilson", "email": "david.wilson@company.example", "department": "Human Resources",
     "job_title": "HR Business Partner", "hire_date": date(2018, 9, 17)},
    {"name": "Rohan Mehta", "email": "rohan.mehta@company.example", "department": "Engineering",
     "job_title": "Frontend Engineer", "hire_date": date(2024, 2, 5)},
    {"name": "Sophia Martinez", "email": "sophia.martinez@company.example", "department": "Support",
     "job_title": "Customer Support Specialist", "hire_date": date(2023, 8, 14), "is_active": False},
]


def seed_database(db: Session) -> dict[str, int]:
    """Insert sample rows that are not already present (matched by email). Safe to run repeatedly."""
    existing_users = set(db.scalars(select(User.email)))
    existing_employees = set(db.scalars(select(Employee.email)))

    new_users = [User(**row) for row in SAMPLE_USERS if row["email"] not in existing_users]
    new_employees = [
        Employee(**row) for row in SAMPLE_EMPLOYEES if row["email"] not in existing_employees
    ]
    db.add_all([*new_users, *new_employees])
    db.commit()

    counts = {"users": len(new_users), "employees": len(new_employees)}
    if any(counts.values()):
        logger.info("Seeded database: %s", counts)
    return counts


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    init_db()
    with SessionLocal() as db:
        print(seed_database(db))


if __name__ == "__main__":
    main()
