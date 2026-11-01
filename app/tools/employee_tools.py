from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Employee
from app.tools import ToolError

MAX_RESULTS = 100


def _serialize(employee: Employee) -> dict:
    return {
        "id": employee.id,
        "name": employee.name,
        "email": employee.email,
        "department": employee.department,
        "job_title": employee.job_title,
        "hire_date": employee.hire_date.isoformat(),
        "is_active": employee.is_active,
    }


def get_employee(db: Session, employee_id: int) -> dict:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise ToolError(f"No employee found with id {employee_id}.")
    return _serialize(employee)


def get_all_employees(db: Session) -> dict:
    total = db.scalar(select(func.count()).select_from(Employee)) or 0
    employees = db.scalars(select(Employee).order_by(Employee.id).limit(MAX_RESULTS)).all()
    return {
        "total": total,
        "returned": len(employees),
        "truncated": total > len(employees),
        "employees": [_serialize(e) for e in employees],
    }


def search_employee(db: Session, name: str) -> dict:
    query = (
        select(Employee)
        .where(Employee.name.icontains(name.strip(), autoescape=True))
        .order_by(Employee.name)
        .limit(MAX_RESULTS)
    )
    employees = db.scalars(query).all()
    return {"query": name, "count": len(employees), "employees": [_serialize(e) for e in employees]}
