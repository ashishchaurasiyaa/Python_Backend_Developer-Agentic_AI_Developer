#!/usr/bin/env python
"""
Django entry point for Banking / Fintech Backend.
Spec: ../05_Django_Banking_Fintech.md

Run:
    python manage.py runserver        # development
    gunicorn banking.wsgi             # production

Setup:
    python manage.py migrate
    python manage.py createsuperuser
"""

import os
import sys

# TODO: Rename 'banking' to your actual project name and run:
#       django-admin startproject banking .
#       python manage.py startapp accounts
#       python manage.py startapp ledger
#       python manage.py startapp kyc
#       python manage.py startapp compliance


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "banking.settings")
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
# Week 1: Django project + User + Account models + basic auth (JWT)
#   TODO: apps/accounts/models.py — User, Account (savings/current/escrow)
#   TODO: apps/accounts/views.py  — signup, login, account creation
#
# Week 2: Double-entry ledger + idempotency
#   TODO: apps/ledger/models.py   — Transaction, LedgerEntry, Balance
#   TODO: apps/ledger/services.py — TransferService.transfer()
#       - SELECT FOR UPDATE on source + dest Balance rows
#       - LedgerEntry.objects.bulk_create([debit, credit])
#       - Balance.objects.filter(...).update(current_balance=F(...) - amount)
#       - Mark txn.status = 'success'
#   TODO: apps/ledger/middleware.py — IdempotencyMiddleware (Stripe pattern)
#   TODO: management/commands/reconcile.py — daily reconcile_balances task
#
# Week 3: KYC + workflows
#   TODO: apps/kyc/models.py  — KYCSubmission with FSMField (django-fsm)
#   TODO: apps/kyc/views.py   — submit docs (S3 upload), approve, reject
#   TODO: OTP verification for transfers > ₹10K
#
# Week 4: Statements + reporting
#   TODO: apps/compliance/tasks.py — generate_monthly_statement(account_id, year, month)
#       - WeasyPrint HTML -> PDF
#       - Upload to S3 (server-side encryption)
#       - Email via Celery task
#   TODO: apps/compliance/views.py — download statement (signed S3 URL)
#
# Week 5: External integrations
#   TODO: apps/payments/services.py — UPIService, NEFT/IMPS stubs
#   TODO: POST /billing/webhook — verify signature, update txn status
#
# Week 6: Production
#   TODO: Celery beat schedule:
#       daily_reconciliation     cron: 02:00
#       monthly_statements       cron: 01st 01:00
#       standing_instruction_runner  every hour
#       detect_suspicious_activity   every 15 min


if __name__ == "__main__":
    main()
