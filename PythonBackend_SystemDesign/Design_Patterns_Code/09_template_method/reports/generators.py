from abc import ABC, abstractmethod
from django.utils import timezone
import csv
import io
import json


class ReportGenerator(ABC):
    """
    Template Method Pattern -- fixed algorithm skeleton.
    Subclasses override specific steps but NOT the overall flow.

    This mirrors Youngman's ReportService.php which follows a fixed pipeline:
        run SQL query -> check empty -> format as CSV/Excel -> generate file -> send to recipients

    The generate() method is THE TEMPLATE METHOD -- its sequence is LOCKED.
    Subclasses customize behavior by overriding abstract and hook methods.
    """

    def generate(self, report) -> dict:
        """
        THE TEMPLATE METHOD -- this sequence is FIXED.
        Subclasses cannot change the order of these 9 steps.

        Steps:
            1. fetch_data      (ABSTRACT -- subclass MUST implement)
            2. check_empty     (FIXED -- cannot override)
            3. filter_data     (HOOK -- subclass CAN override, default is no-op)
            4. transform_data  (HOOK -- subclass CAN override, default is no-op)
            5. format_output   (ABSTRACT -- subclass MUST implement)
            6. get_recipients  (HOOK -- subclass CAN override)
            7. deliver         (FIXED -- cannot override)
            8. save_report     (FIXED -- cannot override)
            9. update_timestamp(FIXED -- cannot override)
        """
        # Step 1: Fetch data (ABSTRACT -- subclass MUST implement)
        data = self.fetch_data(report)

        # Step 2: Check if empty (FIXED)
        if not data:
            return {
                'status': 'empty',
                'message': 'No data found for this report',
                'rows': 0,
            }

        # Step 3: Filter data (HOOK -- subclass CAN override, default is no-op)
        filtered_data = self.filter_data(data)

        # Step 4: Transform data (HOOK -- subclass CAN override)
        transformed = self.transform_data(filtered_data)

        # Step 5: Format output (ABSTRACT -- subclass MUST implement)
        file_content, file_name = self.format_output(transformed, report)

        # Step 6: Get recipients (can be overridden)
        recipients = self.get_recipients(report)

        # Step 7: Deliver (FIXED)
        delivery_result = self.deliver(file_content, file_name, recipients)

        # Step 8: Save generated report (FIXED)
        from .models import GeneratedReport

        generated = GeneratedReport.objects.create(
            report=report,
            file_name=file_name,
            file_content=file_content,
            row_count=len(filtered_data),
            column_count=len(transformed[0]) if transformed else 0,
            sent_to=[r.email for r in recipients],
            status='sent' if delivery_result else 'generated',
        )

        # Step 9: Update last generated (FIXED)
        report.last_generated = timezone.now()
        report.save()

        return {
            'status': 'success',
            'report_id': generated.id,
            'file_name': file_name,
            'rows': len(filtered_data),
            'recipients': len(recipients),
            'steps_executed': [
                'fetch_data',
                'check_empty',
                'filter_data',
                'transform_data',
                'format_output',
                'get_recipients',
                'deliver',
                'save_report',
                'update_timestamp',
            ],
        }

    # -- ABSTRACT methods (subclass MUST implement) --

    @abstractmethod
    def fetch_data(self, report) -> list:
        """Fetch raw data for the report. Like the SQL query step."""
        pass

    @abstractmethod
    def format_output(self, data: list, report) -> tuple:
        """
        Format data into final output.
        Return (file_content_str, file_name_str).
        """
        pass

    # -- HOOK methods (subclass CAN override) --

    def filter_data(self, data) -> list:
        """Default: no filtering. Override to add filters."""
        return data

    def transform_data(self, data) -> list:
        """Default: return as-is. Override to reshape/enrich data."""
        return data

    def get_recipients(self, report) -> list:
        """Default: get from DB. Override for custom recipient logic."""
        return list(report.recipients.all())

    # -- FIXED methods (subclass should NOT override) --

    def deliver(self, content, file_name, recipients):
        """
        Simulated delivery -- in production this would send emails
        with the report file attached.
        """
        if not recipients:
            return False
        # In production: send email with attachment
        # for recipient in recipients:
        #     send_email(recipient.email, file_name, content)
        return True


class CreditPipelineReportGenerator(ReportGenerator):
    """
    Credit Pipeline Report -- invoices at each collection stage with balances.

    Overrides:
        - fetch_data: returns invoice data with collection status
        - filter_data: only include invoices with balance > 0
        - transform_data: adds aging bucket classification
        - format_output: CSV format
    """

    def fetch_data(self, report):
        """
        Simulated data -- in production this would be a SQL query like:
        SELECT doc_number, customer, status, balance, days_overdue
        FROM invoices WHERE status IN ('BILL_OVERDUE', 'FIRST_PTP', ...)
        """
        return [
            {
                'doc_number': 'INV-001',
                'customer': 'Tata Steel',
                'status': 'BILL_OVERDUE',
                'balance': 150000,
                'days_overdue': 45,
            },
            {
                'doc_number': 'INV-002',
                'customer': 'L&T',
                'status': 'FIRST_PTP',
                'balance': 280000,
                'days_overdue': 60,
            },
            {
                'doc_number': 'INV-003',
                'customer': 'Godrej',
                'status': 'BILL_MADE',
                'balance': 95000,
                'days_overdue': 10,
            },
            {
                'doc_number': 'INV-004',
                'customer': 'Reliance',
                'status': 'BILL_BOOKED',
                'balance': 420000,
                'days_overdue': 30,
            },
            {
                'doc_number': 'INV-005',
                'customer': 'Adani',
                'status': 'LEGAL',
                'balance': 750000,
                'days_overdue': 120,
            },
        ]

    def filter_data(self, data):
        """Only include invoices with balance > 0."""
        return [row for row in data if row.get('balance', 0) > 0]

    def transform_data(self, data):
        """Add bucket classification based on days overdue."""
        for row in data:
            days = row.get('days_overdue', 0)
            if days <= 30:
                row['bucket'] = '0-30 days'
            elif days <= 60:
                row['bucket'] = '31-60 days'
            elif days <= 90:
                row['bucket'] = '61-90 days'
            else:
                row['bucket'] = '90+ days'
        return data

    def format_output(self, data, report):
        output = io.StringIO()
        if data:
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        file_name = f"credit_pipeline_{timezone.now().strftime('%Y%m%d')}.csv"
        return output.getvalue(), file_name


class ChallanTATReportGenerator(ReportGenerator):
    """
    Challan Turn-Around-Time Report.

    Overrides:
        - fetch_data: returns challan data with TAT hours
        - filter_data: includes all (no filtering)
        - transform_data: adds SLA compliance flag
        - format_output: CSV format
    """

    def fetch_data(self, report):
        return [
            {
                'challan_no': 'DC-000101',
                'type': 'Delivery',
                'godown': 'Mumbai',
                'tat_hours': 48,
                'status': 'DELIVERED',
            },
            {
                'challan_no': 'DC-000102',
                'type': 'Delivery',
                'godown': 'Delhi',
                'tat_hours': 72,
                'status': 'IN_TRANSIT',
            },
            {
                'challan_no': 'PC-000050',
                'type': 'Pickup',
                'godown': 'Chennai',
                'tat_hours': 96,
                'status': 'PENDING',
            },
            {
                'challan_no': 'DC-000103',
                'type': 'Delivery',
                'godown': 'Mumbai',
                'tat_hours': 24,
                'status': 'DELIVERED',
            },
        ]

    def filter_data(self, data):
        """Include all -- no filter for TAT report."""
        return data

    def transform_data(self, data):
        """Add SLA compliance flag."""
        for row in data:
            sla_limit = 48 if row['type'] == 'Delivery' else 72
            row['sla_met'] = 'Yes' if row['tat_hours'] <= sla_limit else 'No'
            row['sla_limit_hours'] = sla_limit
        return data

    def format_output(self, data, report):
        output = io.StringIO()
        if data:
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        file_name = f"challan_tat_{timezone.now().strftime('%Y%m%d')}.csv"
        return output.getvalue(), file_name


class RevenueReportGenerator(ReportGenerator):
    """
    Revenue prediction report.

    Overrides:
        - fetch_data: returns job order data with predicted revenue
        - format_output: JSON format (not CSV) with totals
    Uses default filter_data and transform_data (no-op hooks).
    """

    def fetch_data(self, report):
        return [
            {
                'job_order': 'JO-2024-001',
                'customer': 'Tata Steel',
                'monthly_rental': 250000,
                'active_months': 6,
                'predicted_revenue': 1500000,
            },
            {
                'job_order': 'JO-2024-002',
                'customer': 'L&T',
                'monthly_rental': 180000,
                'active_months': 3,
                'predicted_revenue': 540000,
            },
            {
                'job_order': 'JO-2024-003',
                'customer': 'Godrej',
                'monthly_rental': 95000,
                'active_months': 12,
                'predicted_revenue': 1140000,
            },
        ]

    def format_output(self, data, report):
        """Format as JSON for revenue report."""
        total_predicted = sum(row['predicted_revenue'] for row in data)
        result = {
            'report_date': timezone.now().strftime('%Y-%m-%d'),
            'total_predicted_revenue': total_predicted,
            'orders': data,
        }
        file_name = f"revenue_{timezone.now().strftime('%Y%m%d')}.json"
        return json.dumps(result, indent=2), file_name


class UtilizationReportGenerator(ReportGenerator):
    """
    Inventory utilization report.

    Overrides:
        - fetch_data: returns inventory data with quantities
        - transform_data: calculates utilization percentage and status
        - format_output: CSV format
    Uses default filter_data (no-op hook).
    """

    def fetch_data(self, report):
        return [
            {
                'item_code': 'SCAFFOLD-01',
                'item_name': 'Standard Frame',
                'total_qty': 5000,
                'deployed_qty': 3500,
                'available_qty': 1500,
            },
            {
                'item_code': 'SCAFFOLD-02',
                'item_name': 'Walk Board',
                'total_qty': 8000,
                'deployed_qty': 6200,
                'available_qty': 1800,
            },
            {
                'item_code': 'SCAFFOLD-03',
                'item_name': 'Base Jack',
                'total_qty': 10000,
                'deployed_qty': 4500,
                'available_qty': 5500,
            },
        ]

    def transform_data(self, data):
        """Calculate utilization percentage and classify status."""
        for row in data:
            row['utilization_pct'] = round(
                (row['deployed_qty'] / row['total_qty']) * 100, 1
            )
            if row['utilization_pct'] > 70:
                row['status'] = 'HIGH'
            elif row['utilization_pct'] > 40:
                row['status'] = 'MEDIUM'
            else:
                row['status'] = 'LOW'
        return data

    def format_output(self, data, report):
        output = io.StringIO()
        if data:
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        file_name = f"utilization_{timezone.now().strftime('%Y%m%d')}.csv"
        return output.getvalue(), file_name


# -- Registry --

REPORT_GENERATORS = {
    'credit_pipeline': CreditPipelineReportGenerator,
    'challan_tat': ChallanTATReportGenerator,
    'revenue': RevenueReportGenerator,
    'utilization': UtilizationReportGenerator,
}


def get_generator(report_type: str) -> ReportGenerator:
    """Factory function to get the appropriate generator for a report type."""
    gen_class = REPORT_GENERATORS.get(report_type)
    if not gen_class:
        raise ValueError(f"Unknown report type: {report_type}")
    return gen_class()
