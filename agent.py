"""
NetSuite AI Agent - Main Orchestrator
Identifies customers who haven't ordered in 90+ days and generates reports.

Usage:
    python agent.py                    # Run once and generate reports
    python agent.py --schedule         # Run on a daily schedule
    python agent.py --status inactive  # Show only inactive customers
    python agent.py --export excel     # Export only Excel format
"""

import os
import sys
import argparse
import time
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv

from netsuite_client import NetSuiteClient, NetSuiteAPIError
from customer_analytics import CustomerAnalytics
from report_generator import ReportGenerator

load_dotenv()


class NetSuiteAgent:
    """
    AI Agent that monitors NetSuite customer activity and identifies
    customers who haven't placed orders in a specified timeframe.
    """

    def __init__(
        self,
        inactive_threshold_days: Optional[int] = None,
        output_path: Optional[str] = None,
    ):
        self.threshold = inactive_threshold_days or int(
            os.getenv("INACTIVE_DAYS_THRESHOLD", "90")
        )
        self.output_path = output_path or os.getenv(
            "REPORT_OUTPUT_PATH", "./reports"
        )
        
        self.client = NetSuiteClient()
        self.analytics = CustomerAnalytics(
            client=self.client,
            inactive_threshold_days=self.threshold,
        )
        self.reporter = ReportGenerator(output_path=self.output_path)

    def run(
        self,
        export_formats: Optional[list] = None,
        status_filter: Optional[str] = None,
        verbose: bool = True,
    ) -> dict:
        """
        Execute the full analysis pipeline.
        
        Args:
            export_formats: List of formats to export ('excel', 'csv', 'json')
            status_filter: Only show customers with this status
            verbose: Print progress information
            
        Returns:
            Dictionary with results and file paths
        """
        if verbose:
            print("=" * 60)
            print("NetSuite Customer Activity Agent")
            print("=" * 60)
            print(f"Analysis started: {datetime.now(timezone.utc).isoformat()}")
            print(f"Inactive threshold: {self.threshold} days")
            print()

        try:
            # Step 1: Fetch and analyze all customer data
            if verbose:
                print("[1/3] Analyzing customer activity...")
            
            activities = self.analytics.analyze_customer_activity()
            
            if not activities:
                print("No customers found or unable to fetch data.")
                return {"success": False, "error": "No data"}

            # Step 2: Generate summary
            if verbose:
                print("[2/3] Generating summary...")
            
            summary = self.analytics.generate_summary(activities)
            
            if verbose:
                self._print_summary(summary)

            # Step 3: Filter if requested
            if status_filter:
                activities = [
                    a for a in activities if a.status == status_filter
                ]
                if verbose:
                    print(f"\nFiltered to {len(activities)} {status_filter} customers.")

            # Step 4: Generate reports
            if verbose:
                print("[3/3] Generating reports...")
            
            generated_files = []
            
            if export_formats is None or "excel" in export_formats:
                excel_path = self.reporter.generate_excel_report(activities, summary)
                generated_files.append(excel_path)
            
            if export_formats is None or "csv" in export_formats:
                csv_path = self.reporter.generate_csv_report(activities)
                generated_files.append(csv_path)
                
                # Also generate inactive-only CSV
                inactive_csv = self.reporter.generate_inactive_csv(activities)
                generated_files.append(inactive_csv)
            
            if export_formats is None or "json" in export_formats:
                json_path = self.reporter.generate_json_report(activities, summary)
                generated_files.append(json_path)
            
            # Generate email list for inactive customers
            email_path = self.reporter.generate_email_list(
                activities, statuses=["inactive", "at_risk"]
            )
            generated_files.append(email_path)

            if verbose:
                print(f"\nGenerated {len(generated_files)} report files.")
                print(f"Reports saved to: {self.output_path}")
                print("\nAnalysis complete!")

            return {
                "success": True,
                "summary": summary,
                "activities": activities,
                "files": generated_files,
            }

        except NetSuiteAPIError as e:
            error_msg = f"NetSuite API Error: {e}"
            print(f"\nERROR: {error_msg}")
            print("\nTroubleshooting tips:")
            print("  - Verify your .env file has correct credentials")
            print("  - Ensure Token-Based Authentication is enabled in NetSuite")
            print("  - Check that the REST API feature is enabled in your account")
            return {"success": False, "error": error_msg}
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            print(f"\nERROR: {error_msg}")
            return {"success": False, "error": error_msg}

    def _print_summary(self, summary: dict):
        """Print a formatted summary to the console."""
        print("\n" + "-" * 40)
        print("CUSTOMER ACTIVITY SUMMARY")
        print("-" * 40)
        print(f"Total Customers:      {summary['total_customers']}")
        print(f"Active:               {summary['active_customers']}")
        print(f"At Risk (60-90 days): {summary['at_risk_customers']}")
        print(f"Inactive (90+ days):  {summary['inactive_customers']}")
        print(f"New (no orders):      {summary['new_customers']}")
        print(f"Churned (no orders, 180+ days): {summary['churned_customers']}")
        print("-" * 40)
        print(f"Inactive %:           {summary['inactive_percentage']}%")
        print(f"At Risk %:            {summary['at_risk_percentage']}%")
        print("-" * 40)
        print(f"Total Revenue:        ${summary['total_revenue']:,.2f}")
        print(f"Total Orders:         {summary['total_orders']}")
        print(f"Inactive Revenue:     ${summary['inactive_customer_revenue']:,.2f}")
        print("-" * 40)

    def run_scheduled(self, run_time: str = "08:00"):
        """
        Run the agent on a daily schedule.
        
        Args:
            run_time: Time to run daily (HH:MM format)
        """
        import schedule

        print(f"Agent scheduled to run daily at {run_time}")
        print("Press Ctrl+C to stop")

        schedule.every().day.at(run_time).do(self.run)

        while True:
            schedule.run_pending()
            time.sleep(60)


def main():
    parser = argparse.ArgumentParser(
        description="NetSuite AI Agent - Find inactive customers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python agent.py                          # Run full analysis
  python agent.py --status inactive        # Show only inactive customers
  python agent.py --export excel csv       # Export only Excel and CSV
  python agent.py --threshold 60           # Use 60-day threshold instead of 90
  python agent.py --schedule               # Run daily at scheduled time
        """,
    )
    
    parser.add_argument(
        "--status",
        choices=["active", "inactive", "at_risk", "new", "churned"],
        help="Filter customers by status",
    )
    parser.add_argument(
        "--export",
        nargs="+",
        choices=["excel", "csv", "json"],
        help="Export formats to generate",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=int(os.getenv("INACTIVE_DAYS_THRESHOLD", "90")),
        help="Days since last order to consider inactive (default: 90)",
    )
    parser.add_argument(
        "--output",
        default=os.getenv("REPORT_OUTPUT_PATH", "./reports"),
        help="Output directory for reports",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run on a daily schedule",
    )
    parser.add_argument(
        "--schedule-time",
        default=os.getenv("SCHEDULE_TIME", "08:00"),
        help="Time to run scheduled job (HH:MM format)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )

    args = parser.parse_args()

    agent = NetSuiteAgent(
        inactive_threshold_days=args.threshold,
        output_path=args.output,
    )

    if args.schedule:
        agent.run_scheduled(run_time=args.schedule_time)
    else:
        result = agent.run(
            export_formats=args.export,
            status_filter=args.status,
            verbose=not args.quiet,
        )
        
        if not result["success"]:
            sys.exit(1)


if __name__ == "__main__":
    main()
