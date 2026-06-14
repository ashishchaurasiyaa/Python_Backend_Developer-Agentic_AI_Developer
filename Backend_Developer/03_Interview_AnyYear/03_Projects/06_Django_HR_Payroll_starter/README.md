# HR & Payroll Management System — Starter

Spec: [../06_Django_HR_Payroll.md](../06_Django_HR_Payroll.md)

## What to build

Multi-tenant HR system for Indian companies: employee onboarding, attendance, leave approval workflows, bulk payroll calculation (TDS, PF, ESIC, PT), payslip PDF generation, and statutory compliance reports (Form 16, Form 24Q, PF ECR).  Target: 200K employees across 1K tenants; payroll for 10K employees in < 5 min.

## How to run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Infrastructure
docker run -d --name pg -e POSTGRES_PASSWORD=dev -p 5432:5432 postgres:16
docker run -d --name redis -p 6379:6379 redis:7
docker run -d --name rabbit -p 5672:5672 rabbitmq:3

# Django project setup (run once)
django-admin startproject hr .
python manage.py startapp employees
python manage.py startapp attendance
python manage.py startapp leaves
python manage.py startapp payroll
python manage.py startapp compliance

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver

# Celery worker (separate terminal)
celery -A hr worker --concurrency=8
celery -A hr beat
```

## Milestones (from spec)

- **Week 1** — Company + Department + Employee models, SalaryStructure (versioned), JWT auth + roles
- **Week 2** — Attendance check-in/out (GPS radius check), LeaveType + LeaveBalance, leave FSMField workflow
- **Week 3** — `calculate_payslip()` (pro-rata + TDS old/new regime + HRA exemption + PF + ESIC + PT), bulk payroll via Celery group
- **Week 4** — WeasyPrint payslip PDFs, Form 16, Form 24Q CSV, PF ECR
- **Week 5** — Employee self-service portal, email notifications
- **Week 6** — django-tenants (schema-per-tenant), django-simple-history audit, column-level encryption (Aadhaar/PAN)

## Key patterns to implement

1. `calculate_tds()`: annualise salary → subtract deductions (80C, 80D, HRA exempt, standard deduction) → apply tax slabs → divide remaining tax over remaining months.
2. Leave state machine: balance.pending incremented on submit; decremented + balance.used incremented on approval.
3. `run_payroll` Celery group: split employees into chunks of 100; parallel `process_payslip_chunk` tasks.
4. All monetary values use `Decimal`, never `float`; DB columns are `NUMERIC(12, 2)`.
5. `SalaryStructure.effective_from / effective_to` allows mid-month salary revisions with correct pro-rata.
