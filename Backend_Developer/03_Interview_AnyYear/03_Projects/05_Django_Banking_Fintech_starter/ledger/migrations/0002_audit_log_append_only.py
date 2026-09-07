"""A Python-level guard (e.g. overriding save()) isn't enough for a
compliance-grade audit trail — anyone with a DB shell or a raw SQL query
could still mutate history. This pushes the append-only guarantee down to
Postgres itself (spec section 12's "tamper-evident" requirement): a trigger
that raises on any UPDATE or DELETE against ledger_auditlog.
"""

from django.db import migrations

CREATE_TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION reject_audit_log_mutation()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only: % is not permitted', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_log_append_only
BEFORE UPDATE OR DELETE ON ledger_auditlog
FOR EACH ROW EXECUTE FUNCTION reject_audit_log_mutation();
"""

DROP_TRIGGER_SQL = """
DROP TRIGGER IF EXISTS audit_log_append_only ON ledger_auditlog;
DROP FUNCTION IF EXISTS reject_audit_log_mutation();
"""


class Migration(migrations.Migration):
    dependencies = [("ledger", "0001_initial")]

    operations = [
        migrations.RunSQL(sql=CREATE_TRIGGER_SQL, reverse_sql=DROP_TRIGGER_SQL),
    ]
