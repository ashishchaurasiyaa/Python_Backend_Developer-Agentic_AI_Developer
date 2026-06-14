#!/usr/bin/env python
"""
Django entry point for HR & Payroll Management System.
Spec: ../06_Django_HR_Payroll.md

Run:
    python manage.py runserver        # development
    gunicorn hr.wsgi                  # production

Setup:
    python manage.py migrate
    python manage.py createsuperuser
"""

import os
import sys

# TODO: Rename 'hr' to your actual project name and run:
#       django-admin startproject hr .
#       python manage.py startapp employees
#       python manage.py startapp attendance
#       python manage.py startapp leaves
#       python manage.py startapp payroll
#       python manage.py startapp compliance


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hr.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Could not import Django. "
            "Install requirements: pip install -r requirements.txt"
        ) from exc
    execute_from_command_line(sys.argv)


# ---------------------------------------------------------------------------
# MILESTONE OVERVIEW
# ---------------------------------------------------------------------------
# Week 1: Core models + admin
#   TODO: apps/employees/models.py  — Company, Department, Employee, SalaryStructure
#       - SalaryStructure.effective_from / effective_to (versioned salary)
#   TODO: Auth + role management (admin, hr_manager, manager, employee)
#
# Week 2: Attendance + Leaves
#   TODO: apps/attendance/models.py  — Attendance, LeaveType, LeaveBalance
#   TODO: apps/leaves/models.py      — LeaveRequest (FSMField via django-fsm)
#       States: draft -> pending -> manager_approved -> approved | rejected
#       on submit: check LeaveBalance; increment balance.pending atomically
#       on confirm: decrement pending, increment used; mark Attendance rows
#   TODO: GPS check-in endpoint (geopy.distance.geodesic for 500m radius)
#
# Week 3: Payroll calculation engine
#   TODO: apps/payroll/services.py  — calculate_payslip(employee, payroll_run)
#       - Pro-rata = days_present / days_in_month
#       - Employee PF: min(basic * 0.12, 1800)
#       - ESIC: gross * 0.0075 if gross < 21000
#       - Professional Tax: ₹200/month
#       - TDS: calculate_tds(employee, year, month) — old vs new regime
#       - HRA exemption: min(hra, rent-10%basic, 50%basic metro/40%non-metro)
#   TODO: apps/payroll/tasks.py     — run_payroll(company_id, month, year)
#       - Celery group: process_payslip_chunk(employee_ids, run_id) in parallel
#
# Week 4: PDF generation + reports
#   TODO: generate_single_payslip(payslip_id)  — WeasyPrint HTML -> PDF -> S3
#   TODO: generate_form_24q(company_id, quarter, year)  — CSV for TRACES
#   TODO: generate_form_16(employee_id, financial_year)  — PDF via WeasyPrint
#   TODO: PF ECR, ESIC return CSV generators
#
# Week 5: Self-service portal
#   TODO: /me endpoints — payslips, leave balances, attendance summary
#   TODO: Email notifications (payslip delivered, leave approved/rejected)
#
# Week 6: Multi-tenant + audit
#   TODO: django-tenants setup (schema-per-tenant via subdomain)
#   TODO: django-simple-history on Employee, SalaryStructure models
#   TODO: Column-level encryption (django-cryptography) for Aadhaar, PAN


if __name__ == "__main__":
    main()
