"""
Customer Analytics Module
Analyzes NetSuite customer data to identify inactive customers
who haven't placed orders in a specified number of days.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

import pandas as pd
from dotenv import load_dotenv

from netsuite_client import NetSuiteClient

load_dotenv()


@dataclass
class CustomerActivity:
    """Represents a customer's activity summary."""
    customer_id: int
    entity_id: str
    company_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    date_created: Optional[datetime]
    last_order_date: Optional[datetime]
    days_since_last_order: Optional[int]
    total_orders: int
    total_revenue: float
    status: str  # 'active', 'inactive', 'at_risk', 'new'


class CustomerAnalytics:
    """
    Analyzes customer ordering patterns to identify inactive customers.
    """

    def __init__(
        self,
        client: Optional[NetSuiteClient] = None,
        inactive_threshold_days: int = 90,
    ):
        self.client = client or NetSuiteClient()
        self.inactive_threshold = inactive_threshold_days
        self.at_risk_threshold = max(1, inactive_threshold_days - 30)

    def _parse_netsuite_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse a NetSuite date string into a datetime object."""
        if not date_str:
            return None
        
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%SZ",
            "%m/%d/%Y",
            "%m/%d/%Y %H:%M:%S",
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.split(".")[0].replace("Z", ""), fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        
        return None

    def _calculate_days_since(self, date: Optional[datetime]) -> Optional[int]:
        """Calculate days since a given date."""
        if not date:
            return None
        now = datetime.now(timezone.utc)
        delta = now - date
        return delta.days

    def _determine_status(
        self, days_since: Optional[int], total_orders: int
    ) -> str:
        """
        Determine customer status based on activity.
        
        Statuses:
        - 'new': Customer with no orders yet
        - 'active': Ordered within at-risk threshold
        - 'at_risk': Between at-risk and inactive threshold
        - 'inactive': Exceeded inactive threshold
        - 'churned': No orders ever + old account
        """
        if total_orders == 0:
            if days_since is None:
                return "new"
            if days_since > 180:
                return "churned"
            return "new"
        
        if days_since is None:
            return "unknown"
        
        if days_since > self.inactive_threshold:
            return "inactive"
        elif days_since > self.at_risk_threshold:
            return "at_risk"
        else:
            return "active"

    def analyze_customer_activity(
        self, batch_size: int = 1000
    ) -> List[CustomerActivity]:
        """
        Fetch and analyze all customer activity from NetSuite.
        
        Args:
            batch_size: Number of records to fetch per API call
            
        Returns:
            List of CustomerActivity objects
        """
        print("Fetching customer data from NetSuite...")
        all_customers = []
        offset = 0
        
        while True:
            batch = self.client.get_all_customers_with_last_order(
                limit=batch_size, offset=offset
            )
            if not batch:
                break
            
            all_customers.extend(batch)
            print(f"  Fetched {len(all_customers)} customers so far...")
            
            if len(batch) < batch_size:
                break
            offset += batch_size

        print(f"Total customers fetched: {len(all_customers)}")
        
        # Process and analyze each customer
        activities = []
        for customer in all_customers:
            last_order = self._parse_netsuite_date(
                customer.get("last_order_date")
            )
            date_created = self._parse_netsuite_date(
                customer.get("datecreated")
            )
            days_since = self._calculate_days_since(last_order)
            total_orders = int(customer.get("totalorders", 0) or 0)
            
            activity = CustomerActivity(
                customer_id=int(customer.get("id", 0)),
                entity_id=customer.get("entityid", ""),
                company_name=customer.get("companyname"),
                email=customer.get("email"),
                phone=customer.get("phone"),
                date_created=date_created,
                last_order_date=last_order,
                days_since_last_order=days_since,
                total_orders=total_orders,
                total_revenue=float(customer.get("totalrevenue", 0) or 0),
                status=self._determine_status(days_since, total_orders),
            )
            activities.append(activity)

        return activities

    def get_inactive_customers(
        self, activities: Optional[List[CustomerActivity]] = None
    ) -> List[CustomerActivity]:
        """
        Get customers who haven't ordered in more than the threshold days.
        
        Args:
            activities: Pre-fetched activities (fetches if None)
            
        Returns:
            List of inactive CustomerActivity objects
        """
        if activities is None:
            activities = self.analyze_customer_activity()
        
        inactive = [
            a for a in activities
            if a.status == "inactive"
        ]
        
        # Sort by days since last order (descending)
        inactive.sort(
            key=lambda x: (x.days_since_last_order or 0),
            reverse=True,
        )
        
        return inactive

    def get_at_risk_customers(
        self, activities: Optional[List[CustomerActivity]] = None
    ) -> List[CustomerActivity]:
        """
        Get customers approaching the inactive threshold.
        
        Args:
            activities: Pre-fetched activities (fetches if None)
            
        Returns:
            List of at-risk CustomerActivity objects
        """
        if activities is None:
            activities = self.analyze_customer_activity()
        
        at_risk = [
            a for a in activities
            if a.status == "at_risk"
        ]
        
        at_risk.sort(
            key=lambda x: (x.days_since_last_order or 0),
            reverse=True,
        )
        
        return at_risk

    def generate_summary(
        self, activities: List[CustomerActivity]
    ) -> Dict[str, any]:
        """
        Generate a summary report of customer activity.
        
        Args:
            activities: List of CustomerActivity objects
            
        Returns:
            Dictionary with summary statistics
        """
        total = len(activities)
        if total == 0:
            return {"total_customers": 0}

        status_counts = {}
        total_revenue = 0
        total_orders = 0
        inactive_revenue = 0
        
        for a in activities:
            status_counts[a.status] = status_counts.get(a.status, 0) + 1
            total_revenue += a.total_revenue
            total_orders += a.total_orders
            if a.status == "inactive":
                inactive_revenue += a.total_revenue

        inactive = status_counts.get("inactive", 0)
        at_risk = status_counts.get("at_risk", 0)
        
        return {
            "total_customers": total,
            "active_customers": status_counts.get("active", 0),
            "at_risk_customers": at_risk,
            "inactive_customers": inactive,
            "new_customers": status_counts.get("new", 0),
            "churned_customers": status_counts.get("churned", 0),
            "inactive_percentage": round((inactive / total) * 100, 2) if total > 0 else 0,
            "at_risk_percentage": round((at_risk / total) * 100, 2) if total > 0 else 0,
            "total_revenue": round(total_revenue, 2),
            "total_orders": total_orders,
            "inactive_customer_revenue": round(inactive_revenue, 2),
            "analysis_date": datetime.now(timezone.utc).isoformat(),
            "inactive_threshold_days": self.inactive_threshold,
        }

    def to_dataframe(
        self, activities: List[CustomerActivity]
    ) -> pd.DataFrame:
        """
        Convert activities to a pandas DataFrame.
        
        Args:
            activities: List of CustomerActivity objects
            
        Returns:
            pandas DataFrame
        """
        data = []
        for a in activities:
            row = asdict(a)
            # Format dates for readability
            row["date_created"] = (
                row["date_created"].strftime("%Y-%m-%d") if row["date_created"] else None
            )
            row["last_order_date"] = (
                row["last_order_date"].strftime("%Y-%m-%d")
                if row["last_order_date"]
                else None
            )
            data.append(row)
        
        df = pd.DataFrame(data)
        
        # Reorder columns for better readability
        column_order = [
            "customer_id",
            "entity_id",
            "company_name",
            "email",
            "phone",
            "status",
            "days_since_last_order",
            "last_order_date",
            "total_orders",
            "total_revenue",
            "date_created",
        ]
        
        existing_cols = [c for c in column_order if c in df.columns]
        df = df[existing_cols]
        
        return df


if __name__ == "__main__":
    # Quick test
    analytics = CustomerAnalytics()
    print("Customer analytics module initialized.")
    print(f"Inactive threshold: {analytics.inactive_threshold} days")
