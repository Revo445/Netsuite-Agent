"""
NetSuite AI Agent - Web Application
Flask-based web UI for configuring and running the customer activity agent.
"""

import os
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from flask import Flask, render_template, request, jsonify, send_file, flash
from flask_cors import CORS
from dotenv import load_dotenv, set_key, find_dotenv

from netsuite_client import NetSuiteClient, NetSuiteAuth, NetSuiteAPIError
from customer_analytics import CustomerAnalytics
from report_generator import ReportGenerator

load_dotenv()

# Detect serverless environment (Vercel, AWS Lambda, etc.)
IS_SERVERLESS = bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "netsuite-agent-secret-key-change-me")
CORS(app)

# Global state for job tracking
job_status = {
    "running": False,
    "progress": 0,
    "message": "Ready",
    "last_result": None,
    "error": None,
}

# In serverless environments, only /tmp is writable
_default_reports = "/tmp/reports" if IS_SERVERLESS else "./reports"
REPORTS_DIR = Path(os.getenv("REPORT_OUTPUT_PATH", _default_reports))
try:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
except (OSError, PermissionError):
    # Fall back to /tmp if we can't write to the configured path
    REPORTS_DIR = Path("/tmp/reports")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# In serverless, .env file is not writable; config must come from env vars
try:
    ENV_PATH = find_dotenv() or ".env"
except Exception:
    ENV_PATH = ".env"


def get_env_config() -> Dict[str, str]:
    """Read current environment configuration."""
    return {
        "netsuite_account_id": os.getenv("NETSUITE_ACCOUNT_ID", ""),
        "netsuite_consumer_key": os.getenv("NETSUITE_CONSUMER_KEY", ""),
        "netsuite_consumer_secret": os.getenv("NETSUITE_CONSUMER_SECRET", ""),
        "netsuite_token_id": os.getenv("NETSUITE_TOKEN_ID", ""),
        "netsuite_token_secret": os.getenv("NETSUITE_TOKEN_SECRET", ""),
        "inactive_threshold": os.getenv("INACTIVE_DAYS_THRESHOLD", "90"),
        "output_path": os.getenv("REPORT_OUTPUT_PATH", str(REPORTS_DIR)),
    }


def save_env_config(config: Dict[str, str]) -> None:
    """Save configuration. In serverless, only updates process env vars."""
    mappings = {
        "netsuite_account_id": "NETSUITE_ACCOUNT_ID",
        "netsuite_consumer_key": "NETSUITE_CONSUMER_KEY",
        "netsuite_consumer_secret": "NETSUITE_CONSUMER_SECRET",
        "netsuite_token_id": "NETSUITE_TOKEN_ID",
        "netsuite_token_secret": "NETSUITE_TOKEN_SECRET",
        "inactive_threshold": "INACTIVE_DAYS_THRESHOLD",
        "output_path": "REPORT_OUTPUT_PATH",
    }
    for key, env_key in mappings.items():
        if key in config:
            # Always update in-memory env
            os.environ[env_key] = config[key]
            # Try to persist to .env file (won't work in serverless, that's fine)
            if not IS_SERVERLESS:
                try:
                    set_key(ENV_PATH, env_key, config[key])
                except Exception:
                    pass


def run_analysis_job(
    threshold: int,
    status_filter: Optional[str],
    export_formats: List[str],
) -> None:
    """Run the analysis in a background thread."""
    global job_status
    
    job_status["running"] = True
    job_status["progress"] = 10
    job_status["message"] = "Connecting to NetSuite..."
    job_status["error"] = None
    job_status["last_result"] = None

    try:
        # Initialize client
        client = NetSuiteClient()
        job_status["progress"] = 20
        job_status["message"] = "Fetching customer data..."

        # Run analytics
        analytics = CustomerAnalytics(
            client=client,
            inactive_threshold_days=threshold,
        )
        activities = analytics.analyze_customer_activity()
        
        job_status["progress"] = 60
        job_status["message"] = "Analyzing results..."

        if not activities:
            job_status["error"] = "No customers found or unable to fetch data."
            job_status["running"] = False
            job_status["progress"] = 0
            return

        summary = analytics.generate_summary(activities)

        # Filter if requested
        if status_filter:
            activities = [a for a in activities if a.status == status_filter]

        job_status["progress"] = 75
        job_status["message"] = "Generating reports..."

        # Generate reports
        reporter = ReportGenerator(output_path=str(REPORTS_DIR))
        generated_files = []

        if "excel" in export_formats:
            path = reporter.generate_excel_report(activities, summary)
            generated_files.append(path)
        if "csv" in export_formats:
            path = reporter.generate_csv_report(activities)
            generated_files.append(path)
            path = reporter.generate_inactive_csv(activities)
            generated_files.append(path)
        if "json" in export_formats:
            path = reporter.generate_json_report(activities, summary)
            generated_files.append(path)

        # Always generate email list
        email_path = reporter.generate_email_list(
            activities, statuses=["inactive", "at_risk"]
        )
        generated_files.append(email_path)

        # Build result
        result = {
            "success": True,
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
                        a.last_order_date.strftime("%Y-%m-%d")
                        if a.last_order_date else None
                    ),
                    "total_orders": a.total_orders,
                    "total_revenue": round(a.total_revenue, 2),
                    "date_created": (
                        a.date_created.strftime("%Y-%m-%d")
                        if a.date_created else None
                    ),
                }
                for a in activities
            ],
            "files": generated_files,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        job_status["last_result"] = result
        job_status["progress"] = 100
        job_status["message"] = "Analysis complete!"

    except NetSuiteAPIError as e:
        job_status["error"] = f"NetSuite API Error: {str(e)}"
        job_status["message"] = "Failed"
    except Exception as e:
        job_status["error"] = f"Unexpected error: {str(e)}"
        job_status["message"] = "Failed"
    finally:
        job_status["running"] = False


# ============== ROUTES ==============

@app.route("/")
def index():
    """Render the main dashboard page."""
    config = get_env_config()
    return render_template("index.html", config=config)


@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "serverless": IS_SERVERLESS,
        "reports_dir": str(REPORTS_DIR),
    })


@app.route("/api/config", methods=["GET"])
def get_config():
    """Get current configuration."""
    config = get_env_config()
    # Mask sensitive values
    masked = config.copy()
    for key in ["netsuite_consumer_secret", "netsuite_token_secret"]:
        if masked.get(key):
            masked[key] = "*" * min(len(masked[key]), 20)
    return jsonify(masked)


@app.route("/api/config", methods=["POST"])
def update_config():
    """Update configuration."""
    data = request.get_json() or {}
    save_env_config(data)
    msg = "Configuration saved"
    if IS_SERVERLESS:
        msg += " (note: in serverless mode, set credentials as environment variables in your Vercel project settings for persistence)"
    return jsonify({"success": True, "message": msg})


@app.route("/api/test-connection", methods=["POST"])
def test_connection():
    """Test NetSuite API connection."""
    try:
        client = NetSuiteClient()
        # Try a simple query
        result = client.execute_suiteql("SELECT COUNT(*) as count FROM customer", limit=1)
        count = result[0].get("count", 0) if result else 0
        return jsonify({
            "success": True,
            "message": f"Connection successful! Found {count} customers in NetSuite.",
        })
    except NetSuiteAPIError as e:
        return jsonify({
            "success": False,
            "message": f"Connection failed: {str(e)}",
        }), 400
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error: {str(e)}",
        }), 500


@app.route("/api/run", methods=["POST"])
def run_analysis():
    """Start analysis job."""
    global job_status

    if job_status["running"]:
        return jsonify({"success": False, "message": "Analysis already running"}), 409

    data = request.get_json() or {}
    threshold = int(data.get("threshold", 90))
    status_filter = data.get("status_filter") or None
    export_formats = data.get("export_formats", ["excel", "csv", "json"])

    if IS_SERVERLESS:
        # In serverless, run synchronously to avoid background-thread issues
        run_analysis_job(threshold, status_filter, export_formats)
        return jsonify({"success": True, "message": "Analysis complete"})

    # Start background thread
    thread = threading.Thread(
        target=run_analysis_job,
        args=(threshold, status_filter, export_formats),
    )
    thread.daemon = True
    thread.start()

    return jsonify({"success": True, "message": "Analysis started"})


@app.route("/api/status", methods=["GET"])
def get_status():
    """Get current job status."""
    return jsonify(job_status)


@app.route("/api/results", methods=["GET"])
def get_results():
    """Get last analysis results."""
    if job_status["last_result"]:
        return jsonify(job_status["last_result"])
    return jsonify({"success": False, "message": "No results available"}), 404


@app.route("/api/reports", methods=["GET"])
def list_reports():
    """List available report files."""
    files = []
    try:
        if REPORTS_DIR.exists():
            for f in sorted(REPORTS_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
                if f.is_file():
                    stat = f.stat()
                    files.append({
                        "name": f.name,
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                        "path": str(f),
                    })
    except Exception:
        pass
    return jsonify(files)


@app.route("/api/reports/<path:filename>", methods=["GET"])
def download_report(filename):
    """Download a report file."""
    file_path = REPORTS_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        return jsonify({"success": False, "message": "File not found"}), 404
    
    return send_file(
        file_path,
        as_attachment=True,
        download_name=filename,
    )


@app.route("/api/reports/<path:filename>", methods=["DELETE"])
def delete_report(filename):
    """Delete a report file."""
    file_path = REPORTS_DIR / filename
    if file_path.exists() and file_path.is_file():
        file_path.unlink()
        return jsonify({"success": True, "message": "File deleted"})
    return jsonify({"success": False, "message": "File not found"}), 404


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
