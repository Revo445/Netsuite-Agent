"""
NetSuite API Client using Token-Based Authentication (TBA)
Supports REST API and SuiteQL queries for customer and transaction data.
"""

import os
import base64
import hashlib
import hmac
import random
import string
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

import requests
from dotenv import load_dotenv

load_dotenv()


class NetSuiteAuth:
    """Handles NetSuite Token-Based Authentication (TBA) for REST API requests."""

    def __init__(
        self,
        account_id: str,
        consumer_key: str,
        consumer_secret: str,
        token_id: str,
        token_secret: str,
    ):
        self.account_id = account_id
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.token_id = token_id
        self.token_secret = token_secret
        self.realm = account_id.upper().replace("_", "-")
        self.base_url = (
            f"https://{self.realm.lower().replace('-', '')}.suitetalk.api.netsuite.com"
        )

    def _generate_nonce(self, length: int = 20) -> str:
        """Generate a random nonce string."""
        return "".join(
            random.choices(string.ascii_letters + string.digits, k=length)
        )

    def _get_timestamp(self) -> str:
        """Get current timestamp in seconds."""
        return str(int(time.time()))

    def _encode(self, value: str) -> str:
        """URL encode a string."""
        return urllib.parse.quote(value, safe="")

    def generate_auth_header(self, method: str, url: str) -> str:
        """
        Generate OAuth 1.0a authorization header for NetSuite TBA.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full request URL
            
        Returns:
            Authorization header string
        """
        nonce = self._generate_nonce()
        timestamp = self._get_timestamp()

        params = {
            "oauth_consumer_key": self.consumer_key,
            "oauth_token": self.token_id,
            "oauth_signature_method": "HMAC-SHA256",
            "oauth_timestamp": timestamp,
            "oauth_nonce": nonce,
            "oauth_version": "1.0",
        }

        # Create parameter string (sorted by key)
        encoded_params = []
        for key in sorted(params.keys()):
            encoded_params.append(f"{self._encode(key)}={self._encode(params[key])}")
        param_string = "&".join(encoded_params)

        # Create signature base string
        parsed_url = urllib.parse.urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        signature_base = f"{method.upper()}&{self._encode(base_url)}&{self._encode(param_string)}"

        # Create signing key
        signing_key = f"{self._encode(self.consumer_secret)}&{self._encode(self.token_secret)}"

        # Generate signature
        signature = base64.b64encode(
            hmac.new(
                signing_key.encode("utf-8"),
                signature_base.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        ).decode("utf-8")

        # Build authorization header
        auth_params = {**params, "oauth_signature": signature}
        auth_header = "OAuth " + ", ".join(
            [f'{self._encode(k)}="{self._encode(v)}"' for k, v in auth_params.items()]
        )

        return auth_header


class NetSuiteClient:
    """NetSuite REST API Client for querying customers and transactions."""

    def __init__(self, auth: Optional[NetSuiteAuth] = None):
        if auth is None:
            auth = NetSuiteAuth(
                account_id=os.getenv("NETSUITE_ACCOUNT_ID", ""),
                consumer_key=os.getenv("NETSUITE_CONSUMER_KEY", ""),
                consumer_secret=os.getenv("NETSUITE_CONSUMER_SECRET", ""),
                token_id=os.getenv("NETSUITE_TOKEN_ID", ""),
                token_secret=os.getenv("NETSUITE_TOKEN_SECRET", ""),
            )
        self.auth = auth
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Prefer": "transient",
        })

    def _make_request(
        self, method: str, endpoint: str, payload: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make an authenticated request to NetSuite REST API."""
        url = f"{self.auth.base_url}{endpoint}"
        auth_header = self.auth.generate_auth_header(method, url)

        headers = {"Authorization": auth_header}
        if payload:
            headers["Content-Type"] = "application/json"

        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
            return response.json() if response.text else {}
        except requests.exceptions.HTTPError as e:
            error_detail = ""
            try:
                error_detail = response.text
            except:
                pass
            raise NetSuiteAPIError(
                f"NetSuite API error: {e}. Details: {error_detail}"
            ) from e
        except requests.exceptions.RequestException as e:
            raise NetSuiteAPIError(f"Request failed: {e}") from e

    def execute_suiteql(self, query: str, limit: int = 1000, offset: int = 0) -> List[Dict]:
        """
        Execute a SuiteQL query via the REST API.
        
        Args:
            query: SuiteQL query string
            limit: Maximum records to return
            offset: Pagination offset
            
        Returns:
            List of result rows
        """
        endpoint = "/services/rest/query/v1/suiteql"
        payload = {
            "q": query,
            "limit": limit,
            "offset": offset,
        }

        result = self._make_request("POST", endpoint, payload)
        return result.get("items", [])

    def get_customer_sales_orders(self, customer_id: int, limit: int = 100) -> List[Dict]:
        """
        Get sales orders for a specific customer.
        
        Args:
            customer_id: Internal ID of the customer
            limit: Maximum records to return
            
        Returns:
            List of sales order records
        """
        query = f"""
            SELECT 
                id,
                tranid,
                trandate,
                status,
                totalamount
            FROM transaction
            WHERE type = 'SalesOrd'
            AND entity = {customer_id}
            ORDER BY trandate DESC
        """
        return self.execute_suiteql(query, limit=limit)

    def get_all_customers_with_last_order(
        self, limit: int = 1000, offset: int = 0
    ) -> List[Dict]:
        """
        Get all customers with their most recent sales order date.
        Uses SuiteQL to efficiently retrieve customer and last order info.
        
        Returns:
            List of customers with last order date and total order count
        """
        query = """
            SELECT 
                c.id,
                c.entityid,
                c.companyname,
                c.email,
                c.phone,
                c.datecreated,
                c.lastmodifieddate,
                MAX(t.trandate) as last_order_date,
                COUNT(t.id) as total_orders,
                SUM(CASE WHEN t.type = 'SalesOrd' THEN t.totalamount ELSE 0 END) as total_revenue
            FROM customer c
            LEFT JOIN transaction t ON t.entity = c.id AND t.type = 'SalesOrd'
            WHERE c.isinactive = 'F'
            GROUP BY 
                c.id,
                c.entityid,
                c.companyname,
                c.email,
                c.phone,
                c.datecreated,
                c.lastmodifieddate
            ORDER BY c.id
        """
        return self.execute_suiteql(query, limit=limit, offset=offset)

    def get_customer_list(self, limit: int = 1000, offset: int = 0) -> List[Dict]:
        """
        Get a basic list of all active customers.
        
        Returns:
            List of customer records
        """
        query = """
            SELECT 
                id,
                entityid,
                companyname,
                email,
                phone,
                datecreated,
                lastmodifieddate
            FROM customer
            WHERE isinactive = 'F'
            ORDER BY id
        """
        return self.execute_suiteql(query, limit=limit, offset=offset)


class NetSuiteAPIError(Exception):
    """Custom exception for NetSuite API errors."""
    pass


if __name__ == "__main__":
    # Quick test
    client = NetSuiteClient()
    print("NetSuite client initialized successfully.")
    print(f"Base URL: {client.auth.base_url}")
