# Project 6: HR & Payroll Management System

**Stack:** Django 5 + DRF + Postgres + Redis + Celery + WeasyPrint + Docker
**Build Time:** 4-6 weeks
**Difficulty:** ⭐⭐⭐⭐ (Workflow + financial calculations + compliance)
**Resume Strength:** ⭐⭐⭐⭐⭐ (Indian SaaS sweet spot — Zoho People, Keka, Razorpay X)

---

## 1. Project Overview & Business Problem

### What it is
Complete HR system: employee onboarding, attendance, leave management, payroll calculation with tax computation, payslip generation, and statutory compliance reporting.

### Why build this
- **Indian SaaS market is huge** for this space ($100M+ companies: Zoho People, Keka, GreytHR).
- **Complex domain:** Tax rules, statutory deductions, leave cycles, approvals.
- **Workflow + financial:** Combines state machines with money calculations.
- **Compliance-heavy:** PF, ESIC, TDS — real laws to model.

### Real-world analogues
- Zoho People
- Keka
- GreytHR
- Razorpay X Payroll
- Workday (enterprise)
- BambooHR
- Gusto (US)

---

## 2. Requirements

### Functional
- **Employee management:** Personal, employment, salary structure.
- **Department hierarchy** (CEO → VP → Manager → IC).
- **Attendance:** Check-in/out via web or mobile (GPS optional).
- **Leave management:** Request → approval workflow.
- **Holiday calendar** (per location).
- **Payroll calculation:** Salary structure → gross → deductions → net.
- **Tax computation:** TDS (India), PF, ESIC, professional tax.
- **Payslip generation** (PDF).
- **Compliance reports:** Form 16, Form 24Q, PF ECR, etc.
- **Performance reviews / appraisals.**
- **Document management** (offer letters, ID proofs).
- **Loan/advance management.**
- **Reimbursements** (travel, food, etc.).
- **Asset allocation** (laptop, phone).
- **Employee self-service portal.**

### Non-Functional
- 10K employees per tenant (mid-market).
- Payroll for 10K employees: < 5 min.
- Statutory accuracy: 100%.
- Audit trail for every change (salary, role, etc.).
- Multi-tenant SaaS.
- Multi-country support (long-term: India + US + EU).

---

## 3. Scale Estimation

| Metric | Number |
|---|---|
| Tenants (companies) | 1K |
| Avg employees/tenant | 200 |
| Total employees | 200K |
| Monthly payroll runs | 1K |
| Payroll calculations/sec (during run) | 100-1000 (bulk) |
| Leave requests/day | 5K |
| Attendance entries/day | 400K (2/employee/day) |
| Payslips generated/month | 200K |
| Reports/month | 5K |
| Total storage | 50 GB (5 years) |

---

## 4. High-Level Architecture

```
                       ┌──────────────┐
                       │  Cloudflare  │
                       └──────┬───────┘
                              │
                       ┌──────▼───────┐
                       │     ALB      │
                       └──────┬───────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
        ┌─────▼─────┐   ┌─────▼─────┐   ┌────▼─────┐
        │ Django    │   │ Django    │   │ Django   │
        │ Web (UI)  │   │ DRF (API) │   │ Admin    │
        └─────┬─────┘   └─────┬─────┘   └────┬─────┘
              │               │               │
              └───────────────┼───────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
         ┌────▼─────┐    ┌────▼─────┐   ┌─────▼─────┐
         │ Postgres │    │  Redis   │   │  Celery   │
         │ + Replica│    │          │   │  Workers  │
         └──────────┘    └──────────┘   └────┬──────┘
                                              │
                                       ┌──────▼──────┐
                                       │  RabbitMQ   │
                                       └─────────────┘
                                              │
                                       ┌──────▼──────┐
                                       │     S3      │  (payslips, docs)
                                       └─────────────┘
```

Standard Django + Celery + Postgres stack.

---

## 5. Data Model

### Tenant + Company

```sql
CREATE TABLE companies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    legal_name      TEXT,
    country         CHAR(2) DEFAULT 'IN',
    pan             TEXT,
    gstin           TEXT,
    tan             TEXT,
    pf_code         TEXT,
    esic_code       TEXT,
    address         JSONB,
    settings        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE departments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      UUID NOT NULL REFERENCES companies(id),
    name            TEXT NOT NULL,
    parent_id       UUID REFERENCES departments(id),  -- hierarchy
    head_id         UUID,                              -- department head (FK to employees)
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE locations (
    id              UUID PRIMARY KEY,
    company_id      UUID NOT NULL,
    name            TEXT NOT NULL,
    address         JSONB,
    timezone        TEXT DEFAULT 'Asia/Kolkata'
);
```

### Employees

```sql
CREATE TABLE employees (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      UUID NOT NULL,
    employee_code   TEXT NOT NULL,                   -- 'EMP001'
    user_id         UUID NOT NULL,                    -- FK to auth user
    department_id   UUID,
    location_id     UUID,
    manager_id      UUID REFERENCES employees(id),
    designation     TEXT,
    employment_type TEXT,                              -- 'fulltime', 'contractor', 'intern'
    join_date       DATE NOT NULL,
    confirmation_date DATE,
    relieving_date  DATE,
    status          TEXT DEFAULT 'active',             -- 'active', 'on_notice', 'separated'
    -- Personal
    date_of_birth   DATE,
    gender          TEXT,
    blood_group     TEXT,
    -- Contact
    phone_number    TEXT,
    personal_email  TEXT,
    -- IDs (encrypted at rest)
    pan             TEXT,                              -- india
    aadhaar         TEXT,                              -- india, encrypted
    uan             TEXT,                              -- universal PF account
    bank_account    JSONB,                              -- {account_number, ifsc, name}
    -- Address
    current_address JSONB,
    permanent_address JSONB,
    UNIQUE (company_id, employee_code)
);
```

### Salary Structure

```sql
-- One row per change in salary
CREATE TABLE salary_structures (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id     UUID NOT NULL REFERENCES employees(id),
    effective_from  DATE NOT NULL,
    effective_to    DATE,                              -- null = current
    annual_ctc      NUMERIC(12, 2) NOT NULL,           -- Cost to Company
    components      JSONB NOT NULL,                     -- breakdown
    /*
    components = {
        "basic":        50000,  (monthly)
        "hra":          25000,
        "special":      15000,
        "lta":          5000,
        "transport":    1600,
        "medical":      1250,
        "employer_pf":  3600,   (12% of basic)
    }
    */
    created_at      TIMESTAMPTZ DEFAULT now(),
    created_by      UUID
);
```

### Attendance & Leaves

```sql
CREATE TABLE attendance (
    id              BIGSERIAL PRIMARY KEY,
    employee_id     UUID NOT NULL,
    date            DATE NOT NULL,
    check_in        TIMESTAMPTZ,
    check_out       TIMESTAMPTZ,
    location_lat    NUMERIC,
    location_lon    NUMERIC,
    status          TEXT NOT NULL,                     -- 'present', 'absent', 'half_day', 'on_leave'
    UNIQUE (employee_id, date)
);

CREATE TABLE leave_types (
    id              UUID PRIMARY KEY,
    company_id      UUID NOT NULL,
    name            TEXT NOT NULL,                     -- 'casual', 'sick', 'earned', 'maternity'
    annual_quota    INT,                                -- 12 days/year
    carry_forward   BOOL DEFAULT false,
    paid            BOOL DEFAULT true,
    accrual_freq    TEXT                                -- 'monthly', 'quarterly', 'yearly'
);

CREATE TABLE leave_balances (
    employee_id     UUID,
    leave_type_id   UUID,
    year            INT,
    allocated       NUMERIC(4, 1) NOT NULL DEFAULT 0,
    used            NUMERIC(4, 1) NOT NULL DEFAULT 0,
    pending         NUMERIC(4, 1) NOT NULL DEFAULT 0,
    PRIMARY KEY (employee_id, leave_type_id, year)
);

CREATE TABLE leave_requests (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id     UUID NOT NULL,
    leave_type_id   UUID NOT NULL,
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    days            NUMERIC(4, 1) NOT NULL,
    reason          TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',  -- state machine
    manager_id      UUID,                              -- approver
    approved_at     TIMESTAMPTZ,
    rejection_reason TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE holidays (
    id              UUID PRIMARY KEY,
    company_id      UUID NOT NULL,
    location_id     UUID,                              -- null = company-wide
    name            TEXT NOT NULL,
    date            DATE NOT NULL,
    type            TEXT                                -- 'national', 'optional', 'religious'
);
```

### Payroll

```sql
CREATE TABLE payroll_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      UUID NOT NULL,
    month           INT NOT NULL,
    year            INT NOT NULL,
    status          TEXT NOT NULL,                     -- 'draft', 'processing', 'completed', 'reverted'
    initiated_by    UUID,
    completed_at    TIMESTAMPTZ,
    total_gross     NUMERIC(15, 2),
    total_deductions NUMERIC(15, 2),
    total_net       NUMERIC(15, 2),
    UNIQUE (company_id, month, year)
);

CREATE TABLE payslips (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payroll_run_id  UUID NOT NULL,
    employee_id     UUID NOT NULL,
    month           INT NOT NULL,
    year            INT NOT NULL,
    components      JSONB NOT NULL,                     -- earnings breakdown
    deductions      JSONB NOT NULL,                     -- TDS, PF, etc.
    gross           NUMERIC(12, 2) NOT NULL,
    deductions_total NUMERIC(12, 2) NOT NULL,
    net             NUMERIC(12, 2) NOT NULL,
    pdf_url         TEXT,                                -- S3 URL
    paid_at         TIMESTAMPTZ,
    UNIQUE (employee_id, month, year)
);

CREATE TABLE reimbursements (
    id              UUID PRIMARY KEY,
    employee_id     UUID NOT NULL,
    category        TEXT,                                -- 'travel', 'food', 'medical'
    amount          NUMERIC(10, 2) NOT NULL,
    bill_url        TEXT,                                -- S3 URL of receipt
    status          TEXT DEFAULT 'pending',              -- workflow
    approved_by     UUID,
    submitted_at    TIMESTAMPTZ,
    paid_at         TIMESTAMPTZ
);

CREATE TABLE loans (
    id              UUID PRIMARY KEY,
    employee_id     UUID NOT NULL,
    principal       NUMERIC(12, 2) NOT NULL,
    interest_rate   NUMERIC(5, 2),                      -- % per annum
    tenure_months   INT NOT NULL,
    monthly_emi     NUMERIC(12, 2) NOT NULL,
    start_date      DATE NOT NULL,
    status          TEXT,                                -- 'active', 'closed', 'defaulted'
    outstanding     NUMERIC(12, 2)
);
```

---

## 6. Leave Approval Workflow (State Machine)

```python
from django_fsm import FSMField, transition

class LeaveRequest(models.Model):
    STATES = ["draft", "pending", "manager_approved", "hr_approved", "approved", "rejected", "cancelled"]

    status = FSMField(default="draft")

    @transition(field=status, source="draft", target="pending")
    def submit(self):
        # Check balance
        balance = LeaveBalance.objects.get(...)
        if balance.allocated - balance.used - balance.pending < self.days:
            raise InsufficientLeaveBalanceError()
        balance.pending += self.days
        balance.save()
        # Notify manager
        send_leave_notification.delay(self.manager_id, "leave_pending", self.id)

    @transition(field=status, source="pending", target="manager_approved")
    def manager_approve(self, manager):
        # Manager-level approval
        # If > X days, need HR approval too
        if self.days > 5:
            return  # stays in flow; HR will approve next
        else:
            self.status = "approved"
            self.confirm_leave()

    @transition(field=status, source="manager_approved", target="approved")
    def hr_approve(self, hr):
        self.confirm_leave()

    @transition(field=status, source=["pending", "manager_approved"], target="rejected")
    def reject(self, by_user, reason):
        balance = LeaveBalance.objects.get(...)
        balance.pending -= self.days
        balance.save()
        self.rejection_reason = reason
        send_leave_notification.delay(self.employee_id, "leave_rejected", self.id)

    def confirm_leave(self):
        balance = LeaveBalance.objects.get(...)
        balance.pending -= self.days
        balance.used += self.days
        balance.save()
        # Mark attendance dates as 'on_leave'
        for date in date_range(self.start_date, self.end_date):
            Attendance.objects.update_or_create(
                employee_id=self.employee_id, date=date,
                defaults={"status": "on_leave"}
            )
        send_leave_notification.delay(self.employee_id, "leave_approved", self.id)
```

---

## 7. Payroll Calculation Engine

The most complex part. Let me show the Indian tax calculation.

### Salary breakdown
```
Gross = sum(earnings)
Deductions:
  - Employee PF (12% of basic, capped at 1800/month)
  - ESIC (0.75% of gross if < ₹21K)
  - Professional Tax (₹200/month in most states)
  - TDS (income tax)
  - Loan EMIs
Net = Gross - Deductions
```

### TDS calculation (simplified)

```python
def calculate_tds(employee, payroll_month_year):
    """
    Compute monthly TDS based on annualized salary - investments.
    India: Old vs New tax regime.
    """
    # Get current salary structure
    salary = SalaryStructure.objects.filter(
        employee=employee,
        effective_from__lte=payroll_month_year,
        effective_to__gte=payroll_month_year
    ).order_by("-effective_from").first()

    # Annual gross
    annual_gross = salary.annual_ctc - get_employer_pf_annual(salary)

    # Deductions
    sec_80c = min(employee.declared_80c, 150000)   # max 1.5L
    sec_80d = min(employee.declared_80d, 50000)     # health insurance
    hra_exempt = calculate_hra_exemption(employee, salary)
    standard_deduction = 50000

    # Old regime taxable income
    taxable_income_old = (
        annual_gross
        - sec_80c
        - sec_80d
        - hra_exempt
        - standard_deduction
    )
    tax_old = compute_tax_old_regime(taxable_income_old)

    # New regime taxable income (less deductions allowed)
    taxable_income_new = annual_gross - standard_deduction
    tax_new = compute_tax_new_regime(taxable_income_new)

    # Pick the one employee opted for (or auto-default)
    annual_tax = tax_old if employee.tax_regime == "old" else tax_new

    # Monthly TDS
    monthly_tds = annual_tax / 12

    # Already deducted YTD
    ytd_deducted = Payslip.objects.filter(
        employee=employee,
        year=payroll_month_year.year,
        month__lt=payroll_month_year.month
    ).aggregate(total=Sum("deductions__tds"))["total"] or Decimal(0)

    # Adjustment for remaining months
    remaining_months = 12 - payroll_month_year.month + 1
    remaining_tax = annual_tax - ytd_deducted
    monthly_tds = remaining_tax / remaining_months

    return max(monthly_tds, Decimal(0))


def compute_tax_old_regime(income):
    """India FY 2024-25 old regime slabs."""
    if income <= 250000:
        return Decimal(0)

    tax = Decimal(0)
    if income > 1000000:
        tax += (income - 1000000) * Decimal("0.30")
        income = 1000000
    if income > 500000:
        tax += (income - 500000) * Decimal("0.20")
        income = 500000
    if income > 250000:
        tax += (income - 250000) * Decimal("0.05")

    # Cess 4%
    tax = tax * Decimal("1.04")
    return tax


def compute_tax_new_regime(income):
    """India FY 2024-25 new regime slabs (post 2023 budget)."""
    if income <= 700000:
        return Decimal(0)  # rebate up to 7L

    tax = Decimal(0)
    if income > 1500000:
        tax += (income - 1500000) * Decimal("0.30")
        income = 1500000
    if income > 1200000:
        tax += (income - 1200000) * Decimal("0.20")
        income = 1200000
    if income > 900000:
        tax += (income - 900000) * Decimal("0.15")
        income = 900000
    if income > 600000:
        tax += (income - 600000) * Decimal("0.10")
        income = 600000
    if income > 300000:
        tax += (income - 300000) * Decimal("0.05")

    tax = tax * Decimal("1.04")
    return tax
```

### HRA exemption

```python
def calculate_hra_exemption(employee, salary):
    """
    HRA exemption = MIN(
        actual HRA received,
        rent paid - 10% of basic,
        50% of basic (metro) / 40% (non-metro)
    )
    """
    basic = salary.components["basic"] * 12
    hra = salary.components.get("hra", 0) * 12
    rent_paid = employee.declared_rent_annual

    metro_cities = {"Mumbai", "Delhi", "Kolkata", "Chennai"}
    multiplier = Decimal("0.5") if employee.city in metro_cities else Decimal("0.4")

    exempt_options = [
        hra,
        max(rent_paid - Decimal("0.10") * basic, Decimal(0)),
        multiplier * basic,
    ]
    return min(exempt_options)
```

### Monthly payroll calculation

```python
def calculate_payslip(employee, payroll_run):
    salary = get_current_salary(employee)
    days_in_month = monthrange(payroll_run.year, payroll_run.month)[1]
    days_present = get_attendance_days(employee, payroll_run.month, payroll_run.year)

    # Pro-rata if employee didn't work full month
    proration = Decimal(days_present) / Decimal(days_in_month)

    # Earnings (monthly)
    basic = salary.components["basic"] * proration
    hra = salary.components.get("hra", 0) * proration
    special = salary.components.get("special", 0) * proration
    lta = salary.components.get("lta", 0) * proration

    gross = basic + hra + special + lta

    # Deductions
    employee_pf = min(basic * Decimal("0.12"), Decimal("1800"))
    esic = gross * Decimal("0.0075") if gross < Decimal("21000") else Decimal(0)
    pt = Decimal("200")
    tds = calculate_tds(employee, payroll_run.year, payroll_run.month)

    # Loan EMI
    active_loans = Loan.objects.filter(employee=employee, status="active")
    loan_emi = sum(l.monthly_emi for l in active_loans)

    deductions = {
        "pf": employee_pf,
        "esic": esic,
        "pt": pt,
        "tds": tds,
        "loan_emi": loan_emi,
    }
    deductions_total = sum(deductions.values())
    net = gross - deductions_total

    payslip = Payslip.objects.create(
        payroll_run=payroll_run,
        employee=employee,
        month=payroll_run.month,
        year=payroll_run.year,
        components={
            "basic": float(basic),
            "hra": float(hra),
            "special": float(special),
            "lta": float(lta),
        },
        deductions={k: float(v) for k, v in deductions.items()},
        gross=gross,
        deductions_total=deductions_total,
        net=net,
    )

    return payslip
```

---

## 8. Bulk Payroll Run (Celery)

```python
@shared_task
def run_payroll(company_id, month, year):
    company = Company.objects.get(id=company_id)

    # Create payroll run
    run = PayrollRun.objects.create(
        company=company, month=month, year=year, status="processing"
    )

    # Get all active employees
    employees = Employee.objects.filter(
        company=company, status="active",
        join_date__lte=date(year, month, monthrange(year, month)[1])
    )

    # Process in parallel chunks
    chunk_size = 100
    employee_ids = list(employees.values_list("id", flat=True))
    chunks = [employee_ids[i:i+chunk_size] for i in range(0, len(employee_ids), chunk_size)]

    # Use Celery group for parallel processing
    from celery import group
    job = group(
        process_payslip_chunk.s(chunk_ids, run.id) for chunk_ids in chunks
    )
    result = job.apply_async()

    # Wait for completion
    result.get()  # Blocks until done

    # Aggregate totals
    totals = Payslip.objects.filter(payroll_run=run).aggregate(
        total_gross=Sum("gross"),
        total_deductions=Sum("deductions_total"),
        total_net=Sum("net"),
    )
    run.total_gross = totals["total_gross"]
    run.total_deductions = totals["total_deductions"]
    run.total_net = totals["total_net"]
    run.status = "completed"
    run.completed_at = timezone.now()
    run.save()

    # Generate PDFs async
    generate_payslip_pdfs.delay(run.id)

    # Notifications
    notify_payroll_completed.delay(run.id)


@shared_task
def process_payslip_chunk(employee_ids, run_id):
    run = PayrollRun.objects.get(id=run_id)
    for emp_id in employee_ids:
        try:
            employee = Employee.objects.get(id=emp_id)
            calculate_payslip(employee, run)
        except Exception as e:
            logger.exception(f"Failed to process {emp_id}: {e}")
```

10K employees / 100 per chunk × parallel workers = ~3-5 min total.

---

## 9. Payslip PDF Generation

```python
@shared_task
def generate_payslip_pdfs(run_id):
    payslips = Payslip.objects.filter(payroll_run_id=run_id)
    for payslip in payslips:
        generate_single_payslip.delay(payslip.id)

@shared_task(autoretry_for=(Exception,), max_retries=3)
def generate_single_payslip(payslip_id):
    payslip = Payslip.objects.get(id=payslip_id)
    employee = payslip.employee
    company = employee.company

    context = {
        "employee": employee,
        "payslip": payslip,
        "company": company,
        "month_year": f"{payslip.month}-{payslip.year}",
        "components": payslip.components,
        "deductions": payslip.deductions,
    }

    html = render_to_string("payslip.html", context)
    from weasyprint import HTML
    pdf = HTML(string=html).write_pdf()

    # Upload to S3
    s3_key = f"payslips/{employee.id}/{payslip.year}-{payslip.month:02d}.pdf"
    s3.put_object(
        Bucket="hr-documents", Key=s3_key, Body=pdf,
        ServerSideEncryption="AES256"
    )

    payslip.pdf_url = s3_key
    payslip.save(update_fields=["pdf_url"])

    # Email
    send_payslip_email.delay(payslip.id)
```

### Payslip HTML template

```html
<!DOCTYPE html>
<html>
<head>
    <style>
        @page { size: A4; margin: 1cm; }
        body { font-family: Arial; }
        .header { display: flex; justify-content: space-between; border-bottom: 2px solid; padding-bottom: 10px; }
        .header img { height: 50px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { padding: 8px; border: 1px solid #ddd; text-align: left; }
        .total { font-weight: bold; background: #f0f0f0; }
        .net-pay { font-size: 18px; color: #28a745; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <img src="{{ company.logo_url }}" />
        <div>
            <h2>{{ company.name }}</h2>
            <small>{{ company.address.line1 }}, {{ company.address.city }}</small>
        </div>
    </div>
    <h3>Payslip — {{ month_year }}</h3>

    <table>
        <tr><th>Employee Code</th><td>{{ employee.employee_code }}</td>
            <th>Designation</th><td>{{ employee.designation }}</td></tr>
        <tr><th>Name</th><td colspan="3">{{ employee.user.full_name }}</td></tr>
        <tr><th>UAN</th><td>{{ employee.uan }}</td>
            <th>PAN</th><td>{{ employee.pan }}</td></tr>
        <tr><th>Bank</th><td colspan="3">{{ employee.bank_account.account_number }} / {{ employee.bank_account.ifsc }}</td></tr>
    </table>

    <table>
        <tr><th colspan="2">Earnings</th><th colspan="2">Deductions</th></tr>
        <tr>
            <td>Basic</td><td>₹{{ components.basic|floatformat:2 }}</td>
            <td>PF</td><td>₹{{ deductions.pf|floatformat:2 }}</td>
        </tr>
        <tr>
            <td>HRA</td><td>₹{{ components.hra|floatformat:2 }}</td>
            <td>ESIC</td><td>₹{{ deductions.esic|floatformat:2 }}</td>
        </tr>
        <tr>
            <td>Special Allowance</td><td>₹{{ components.special|floatformat:2 }}</td>
            <td>PT</td><td>₹{{ deductions.pt|floatformat:2 }}</td>
        </tr>
        <tr>
            <td>LTA</td><td>₹{{ components.lta|floatformat:2 }}</td>
            <td>TDS</td><td>₹{{ deductions.tds|floatformat:2 }}</td>
        </tr>
        <tr class="total">
            <td>Gross</td><td>₹{{ payslip.gross|floatformat:2 }}</td>
            <td>Total Deductions</td><td>₹{{ payslip.deductions_total|floatformat:2 }}</td>
        </tr>
    </table>

    <div class="net-pay">Net Pay: ₹{{ payslip.net|floatformat:2 }}</div>
</body>
</html>
```

---

## 10. Compliance Reports

### Form 24Q (TDS quarterly return — India)

```python
@shared_task
def generate_form_24q(company_id, quarter, year):
    company = Company.objects.get(id=company_id)
    employees = Employee.objects.filter(company=company)

    rows = []
    for emp in employees:
        payslips = Payslip.objects.filter(
            employee=emp,
            year=year,
            month__in=quarter_months(quarter)
        )

        row = {
            "TAN": company.tan,
            "PAN": emp.pan,
            "employee_name": emp.user.full_name,
            "amount_paid": payslips.aggregate(Sum("gross"))["gross__sum"] or 0,
            "tds_deducted": payslips.aggregate(Sum("deductions__tds"))["sum"] or 0,
        }
        rows.append(row)

    # Generate CSV / FVU file
    csv = generate_csv(rows)
    s3_key = f"compliance/24Q/{company.id}/{year}_Q{quarter}.csv"
    s3.put_object(Bucket="hr-documents", Key=s3_key, Body=csv)

    return s3_key
```

### Form 16 (annual TDS certificate — India)

```python
@shared_task
def generate_form_16(employee_id, financial_year):
    employee = Employee.objects.get(id=employee_id)
    payslips = Payslip.objects.filter(
        employee=employee,
        # FY in India: April to March
        ...
    )

    total_gross = payslips.aggregate(Sum("gross"))["gross__sum"]
    total_tds = payslips.aggregate(Sum("deductions__tds"))["sum"]

    context = {
        "employee": employee,
        "company": employee.company,
        "financial_year": financial_year,
        "total_gross": total_gross,
        "total_tds": total_tds,
        "payslips": payslips,
    }
    html = render_to_string("form_16.html", context)
    pdf = HTML(string=html).write_pdf()
    s3_key = f"form16/{employee.id}/{financial_year}.pdf"
    s3.put_object(Bucket="hr-documents", Key=s3_key, Body=pdf)
    return s3_key
```

### Other reports
- **PF ECR**: Monthly PF challan + employee details to EPFO.
- **ESIC return**: Monthly to ESIC.
- **Profession Tax**: State-specific monthly.
- **Provident Fund statement**: Per-employee accumulation.

All can be auto-generated from payroll data.

---

## 11. Attendance with GPS

```python
from geopy.distance import geodesic

@api_view(["POST"])
def check_in(request):
    employee = request.user.employee
    today = date.today()

    # Check if office location set
    if employee.location:
        emp_location = (request.data["lat"], request.data["lon"])
        office = (employee.location.lat, employee.location.lon)
        distance_m = geodesic(emp_location, office).meters
        if distance_m > 500:    # 500m radius
            return Response({"error": "Not at office location"}, 400)

    attendance, created = Attendance.objects.get_or_create(
        employee=employee, date=today,
        defaults={
            "check_in": timezone.now(),
            "location_lat": request.data["lat"],
            "location_lon": request.data["lon"],
            "status": "present"
        }
    )

    if not created:
        return Response({"error": "Already checked in"}, 409)

    return Response(model_to_dict(attendance))
```

---

## 12. APIs

```
# Auth
POST  /auth/login
POST  /auth/refresh

# Employee
GET   /employees                 (list, paginated, filtered)
POST  /employees                 (create — HR only)
GET   /employees/{id}
PATCH /employees/{id}
DELETE /employees/{id}           (offboard)

# Self-service
GET   /me                        (current employee)
PATCH /me                        (limited fields)
GET   /me/payslips
GET   /me/leave-balances
GET   /me/attendance

# Salary
GET   /employees/{id}/salary     (current structure)
POST  /employees/{id}/salary    (create new — HR)
GET   /employees/{id}/salary/history

# Attendance
POST  /attendance/check-in
POST  /attendance/check-out
GET   /attendance?employee=&from=&to=
PATCH /attendance/{id}           (HR override)

# Leaves
GET   /leaves                    (filtered by status, employee)
POST  /leaves                    (request)
PATCH /leaves/{id}/approve      (manager)
PATCH /leaves/{id}/reject       (manager)
PATCH /leaves/{id}/cancel       (employee)

# Payroll
GET   /payroll-runs
POST  /payroll-runs              (initiate)
GET   /payroll-runs/{id}/payslips
POST  /payroll-runs/{id}/revert  (rollback)

# Payslips
GET   /payslips/{id}
GET   /payslips/{id}/download

# Reports
GET   /reports/form-16/{employee_id}/{fy}
GET   /reports/form-24q/{quarter}/{year}
GET   /reports/pf-ecr/{month}/{year}
GET   /reports/headcount

# Loans
GET   /loans
POST  /loans                     (request)
PATCH /loans/{id}/approve

# Reimbursements
GET   /reimbursements
POST  /reimbursements
PATCH /reimbursements/{id}/approve
```

---

## 13. Role-Based Permissions

```python
class Role(models.Model):
    name = models.CharField()    # 'admin', 'hr_manager', 'manager', 'employee'

class Permission(models.Model):
    role = models.ForeignKey(Role)
    resource = models.CharField()    # 'employee', 'payroll'
    action = models.CharField()      # 'read', 'write', 'admin'
```

### Field-level permissions
Employees see their own salary; HR sees everyone's.

```python
class EmployeeSerializer(serializers.ModelSerializer):
    salary = serializers.SerializerMethodField()

    def get_salary(self, obj):
        user = self.context["request"].user
        if user.is_hr or user.id == obj.user_id:
            return SalaryStructureSerializer(obj.current_salary).data
        return None    # hidden
```

---

## 14. Multi-Tenant Setup

Using `django-tenants` (schema-per-tenant):

```python
INSTALLED_APPS = [
    "django_tenants",
    ...
]

DATABASE_ROUTERS = ["django_tenants.routers.TenantSyncRouter"]

TENANT_MODEL = "companies.Company"
TENANT_DOMAIN_MODEL = "companies.Domain"
```

Each company gets its own Postgres schema. Switching to schema on request:
```python
# Tenant resolved by subdomain (acme.hr.com)
# Middleware sets current schema → all queries scoped
```

Trade-off: more schemas to manage, but strict isolation.

For SMB: shared-schema is simpler.

---

## 15. Audit Logging

```python
from simple_history.models import HistoricalRecords

class Employee(models.Model):
    # ...
    history = HistoricalRecords()

class SalaryStructure(models.Model):
    # ...
    history = HistoricalRecords()
```

Every field change captured automatically. Required for compliance.

```python
# Query history
employee.history.all()  # all changes
employee.history.filter(history_date__lt=last_month)
```

---

## 16. Deployment

### Docker Compose (dev)

```yaml
services:
  django:
    build: .
    command: gunicorn project.wsgi --workers 4
    environment:
      DATABASE_URL: postgres://...

  celery:
    build: .
    command: celery -A project worker --concurrency=4

  celery-beat:
    build: .
    command: celery -A project beat

  postgres:
    image: postgres:16

  redis:
    image: redis:7
```

### Production (AWS)

```
ALB → ECS Django pods (4+ replicas)
       ↓
   RDS Postgres (Multi-AZ + Read Replica)
       ↓
   ElastiCache Redis
       ↓
   ECS Celery workers (auto-scaled by queue depth)
       ↓
   S3 (payslips, KYC, docs)
```

---

## 17. Senior-Level Showcases

### A. State machine workflows (`django-fsm`)
Multi-step approvals with valid-transition enforcement.

### B. Bulk parallel payroll via Celery group
10K employees in 3-5 minutes.

### C. Real Indian tax calculation
Old vs new regime; HRA exemption; rebates.

### D. Schema-per-tenant via `django-tenants`
Strict data isolation per company.

### E. Audit log via `django-simple-history`
Every change tracked; required for HR compliance.

### F. Complex ORM aggregations
Monthly attendance summaries, leave usage by department.

### G. PDF generation via WeasyPrint
Industry-standard payslips, Form 16, statements.

### H. Multi-format reports
CSV (Form 24Q FVU), PDF (Form 16), Excel exports.

### I. Loan EMI scheduler
Recurring deductions via Celery beat.

### J. Field-level permissions
Salary visible only to self + HR.

---

## 18. Implementation Roadmap

### Week 1: Core models + admin
- [ ] Tenant + Company + Department setup.
- [ ] Employee model + admin.
- [ ] Salary structure (one-time setup).
- [ ] Auth + role management.

### Week 2: Attendance + Leaves
- [ ] Attendance check-in/out.
- [ ] Leave types + balances.
- [ ] Leave request workflow (state machine).
- [ ] Approval interfaces.

### Week 3: Payroll calculation
- [ ] Single employee payslip calc.
- [ ] Tax calculation (old + new regime).
- [ ] Bulk payroll via Celery.
- [ ] Payslip generation (PDF).

### Week 4: Reports
- [ ] Form 16, Form 24Q, PF ECR.
- [ ] Employee history reports.
- [ ] Department summaries.
- [ ] Excel exports.

### Week 5: Self-service + UX
- [ ] Employee self-service portal.
- [ ] Mobile-friendly UI.
- [ ] Email notifications.
- [ ] Payslip email delivery.

### Week 6: Production
- [ ] Multi-tenant via django-tenants.
- [ ] Audit logging.
- [ ] Encryption at rest (Aadhaar, PAN).
- [ ] Performance test 10K employees.
- [ ] Compliance documentation.

---

## 19. Common Pitfalls & Solutions

### Pitfall 1: Tax calc wrong by ₹1
**Solution:** Use `Decimal`, not `float`. Test against published tax tables.

### Pitfall 2: Race condition during payroll run
**Solution:** Lock payroll run; reject duplicate triggers.

### Pitfall 3: Mid-month salary change
**Solution:** Salary structures with `effective_from` / `effective_to`; pro-rate calculation.

### Pitfall 4: Leave balance going negative
**Solution:** Atomic check + update; reject if would go negative.

### Pitfall 5: PDF generation slow at scale
**Solution:** Celery group with parallel workers; pre-generate PDFs over time, not all on payroll-completion.

### Pitfall 6: Lost audit log on schema change
**Solution:** `django-simple-history` migration alongside.

### Pitfall 7: Aadhaar leaked
**Solution:** Column-level encryption with separate KMS key.

---

## 20. Performance Benchmarks

| Metric | Target |
|---|---|
| Single payslip calculation | < 100ms |
| 10K employee payroll run | < 5 min |
| PDF generation | < 2s/payslip |
| Report generation (Form 16 for 200 emp) | < 30s |
| Read API p99 | < 200ms |
| Concurrent users | 1K |

---

## 21. Resume Bullets

- Built a multi-tenant HR/Payroll system in Django/DRF for 1K+ companies and 200K+ employees with Indian tax compliance (TDS, PF, ESIC) and bulk payroll processing in under 5 minutes for 10K employees.
- Designed state-machine-driven leave approval workflows via django-fsm, role-based field permissions, and immutable audit log via django-simple-history.
- Automated compliance report generation (Form 16, Form 24Q, PF ECR) and payslip PDFs via WeasyPrint + Celery, delivered via email and S3.

---

## 22. Interview Talking Points

- **"Tax computation logic?"** → Old vs new regime, HRA exemption, slabs, rebates, cess.
- **"How do you handle 10K employees in payroll?"** → Celery group with parallel chunks; ~3-5 min.
- **"Mid-month salary increase?"** → Salary versioning with effective dates; pro-rate.
- **"How to ensure audit-proof?"** → django-simple-history + immutable audit log + every transition logged.
- **"Multi-tenancy choice?"** → Schema-per-tenant for compliance (data isolation); shared schema for SMB.

---

## 23. Stretch Goals

- **Performance reviews (360-degree feedback).**
- **Goal setting (OKRs).**
- **Employee surveys + sentiment analysis.**
- **Org chart visualization.**
- **Asset management** (laptop, phone tracking).
- **Document e-signature** (DigiLocker / Aadhaar e-sign).
- **AI chatbot for HR queries** (LLM-based).
- **Pre-built integrations:** Slack, Microsoft Teams, Google Calendar.
- **Multi-country payroll** (UK PAYE, US W-2).
- **Predictive attrition** (ML model).

---

## 24. Tech Stack Summary

| Layer | Choice | Why |
|---|---|---|
| **Framework** | Django + DRF | Mature, ORM, admin, batteries |
| **DB** | Postgres | ACID, NUMERIC type |
| **Cache** | Redis | Sessions, rate limit |
| **Queue** | Celery + RabbitMQ | Async payroll |
| **PDF** | WeasyPrint | HTML → PDF |
| **Excel** | openpyxl | Reports |
| **State machine** | django-fsm | Workflows |
| **History** | django-simple-history | Audit |
| **Multi-tenant** | django-tenants | Schema-per-tenant |
| **Encryption** | django-cryptography | Aadhaar at column-level |
| **Storage** | S3 (encrypted) | Documents |
| **Email** | AWS SES | Cheapest |
| **Monitoring** | Sentry + Prometheus | Errors + metrics |

---

## TL;DR

- Multi-tenant HR/Payroll for Indian + global compliance.
- Bulk payroll calculation in 3-5 min for 10K employees.
- State-machine workflows for leaves; tax engine for TDS/PF/ESIC.
- Compliance: Form 16, Form 24Q, PF ECR auto-generated.
- Field-level permissions (salary visible only to self + HR).
- 4-6 weeks build time.
- **Indian SaaS niche: huge market, complex domain, premium pay.**
