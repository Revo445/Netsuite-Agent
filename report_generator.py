"""
Report Generator Module
Generates Excel, CSV, and JSON reports from customer analytics data.
"""

import os
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional
from pathlib import Path

import pandas as pd

from customer_analytics import CustomerActivity


class ReportGenerator:
    """Generates various report formats from customer activity data."""

    def __init__(self, output_path: str = "./reports"):
        self.output_path = Path(output_path)
        self.output_path.mkdir(parents=True, exist_ok=True)
        self.timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    def _get_filename(self, name: str, ext: str) -> str:
        """Generate a timestamped filename."""
        return f"{name}_{self.timestamp}.{ext}"

    def generate_excel_report(
        self,
        activities: List[CustomerActivity],
        summary: Dict,
        filename: Optional[str] = None,
    ) -> str:
        """
        Generate a comprehensive Excel report with multiple sheets.
        
        Args:
            activities: List of all customer activities
            summary: Summary statistics dictionary
            filename: Optional custom filename
            
        Returns:
            Path to generated Excel file
        """
        if filename is None:
            filename = self._get_filename("customer_activity_report", "xlsx")
        
        filepath = self.output_path / filename
        
        # Create DataFrames
        df_all = self._activities_to_dataframe(activities)
        df_inactive = df_all[df_all["status"] == "inactive"].copy()
        df_at_risk = df_all[df_all["status"] == "at_risk"].copy()
        df_summary = pd.DataFrame([summary])
        
        with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
            # Summary sheet
            df_summary.to_excel(writer, sheet_name="Summary", index=False)
            
            # All customers
            df_all.to_excel(writer, sheet_name="All Customers", index=False)
            
            # Inactive customers
            if not df_inactive.empty:
                df_inactive.to_excel(
                    writer, sheet_name="Inactive Customers", index=False
                )
            
            # At-risk customers
            if not df_at_risk.empty:
                df_at_risk.to_excel(
                    writer, sheet_name="At Risk Customers", index=False
                )
            
            # Status breakdown
            status_breakdown = df_all["status"].value_counts().reset_index()
            status_breakdown.columns = ["Status", "Count"]
            status_breakdown.to_excel(
                writer, sheet_name="Status Breakdown", index=False
            )

        print(f"Excel report saved: {filepath}")
        return str(filepath)

    def generate_csv_report(
        self,
        activities: List[CustomerActivity],
        filename: Optional[str] = None,
    ) -> str:
        """
        Generate a CSV report of all customer activities.
        
        Args:
            activities: List of customer activities
            filename: Optional custom filename
            
        Returns:
            Path to generated CSV file
        """
        if filename is None:
            filename = self._get_filename("customer_activity", "csv")
        
        filepath = self.output_path / filename
        df = self._activities_to_dataframe(activities)
        df.to_csv(filepath, index=False)
        
        print(f"CSV report saved: {filepath}")
        return str(filepath)

    def generate_inactive_csv(
        self,
        activities: List[CustomerActivity],
        filename: Optional[str] = None,
    ) -> str:
        """
        Generate a CSV report of only inactive customers.
        
        Args:
            activities: List of customer activities
            filename: Optional custom filename
            
        Returns:
            Path to generated CSV file
        """
        if filename is None:
            filename = self._get_filename("inactive_customers", "csv")
        
        filepath = self.output_path / filename
        df = self._activities_to_dataframe(activities)
        df_inactive = df[df["status"] == "inactive"].copy()
        df_inactive.to_csv(filepath, index=False)
        
        print(f"Inactive customers CSV saved: {filepath}")
        return str(filepath)

    def generate_json_report(
        self,
        activities: List[CustomerActivity],
        summary: Dict,
        filename: Optional[str] = None,
    ) -> str:
        """
        Generate a JSON report with full data and summary.
        
        Args:
            activities: List of customer activities
            summary: Summary statistics
            filename: Optional custom filename
            
        Returns:
            Path to generated JSON file
        """
        if filename is None:
            filename = self._get_filename("customer_activity_report", "json")
        
        filepath = self.output_path / filename
        
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "customers": [
                {
                    "customer_id": a.customer_id,
                    "entity_id": a.entity_id,
                    "company_name": a.company_name,
                    "email": a.email,
                    "phone": a.phone,
                    "status": a.status,
                    "days_since_last_order": a.days_since_last_order,
                    "last_order_date": (
                        a.last_order_date.isoformat() if a.last_order_date else None
                    ),
                    "total_orders": a.total_orders,
                    "total_revenue": a.total_revenue,
                    "date_created": (
                        a.date_created.isoformat() if a.date_created else None
                    ),
                }
                for a in activities
            ],
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"JSON report saved: {filepath}")
        return str(filepath)

    def generate_email_list(
        self,
        activities: List[CustomerActivity],
        statuses: List[str] = ["inactive"],
        filename: Optional[str] = None,
    ) -> str:
        """
        Generate a simple text file with email addresses for marketing campaigns.
        
        Args:
            activities: List of customer activities
            statuses: Which statuses to include
            filename: Optional custom filename
            
        Returns:
            Path to generated text file
        """
        if filename is None:
            status_str = "_".join(statuses)
            filename = self._get_filename(f"email_list_{status_str}", "txt")
        
        filepath = self.output_path / filename
        
        emails = [
            a.email for a in activities
            if a.status in statuses and a.email
        ]
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(sorted(set(emails))))
        
        print(f"Email list saved: {filepath} ({len(emails)} emails)")
        return str(filepath)

    def _activities_to_dataframe(
        self, activities: List[CustomerActivity]
    ) -> pd.DataFrame:
        """Convert activities to a formatted DataFrame."""
        data = []
        for a in activities:
            data.append({
                "customer_id": a.customer_id,
                "entity_id": a.entity_id,
                "company_name": a.company_name,
                "email": a.email,
                "phone": a.phone,
                "status": a.status,
                "days_since_last_order": a.days_since_last_order,
                "last_order_date": (
                    a.last_order_date.strftime("%Y-%m-%d")
                    if a.last_order_date else None
                ),
                "total_orders": a.total_orders,
                "total_revenue": round(a.total_revenue, 2),
                "date_created": (
                    a.date_created.strftime("%Y-%m-%d")
                    if a.date_created else None
                ),
            })
        
        df = pd.DataFrame(data)
        
        # Sort by status and days since last order
        status_order = {"inactive": 0, "at_risk": 1, "churned": 2, "new": 3, "active": 4, "unknown": 5}
        df["status_order"] = df["status"].map(status_order)
        df = df.sort_values(["status_order", "days_since_last_order"], ascending=[True, False])
        df = df.drop(columns=["status_order"])
        
        return df


if __name__ == "__main__":
    # Quick test
    gen = ReportGenerator()
    print(f"Report generator initialized. Output path: {gen.output_path}")
