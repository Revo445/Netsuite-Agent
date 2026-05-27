# NetSuite AI Agent - Customer Activity Monitor

An intelligent agent that connects to NetSuite via REST API to identify customers who haven't placed orders in more than 90 days (configurable). It generates comprehensive reports in Excel, CSV, and JSON formats for sales and marketing follow-up.

## Features

- **Automated Customer Analysis**: Fetches all customers and their last order dates via SuiteQL
- **Smart Segmentation**: Categorizes customers as:
  - `active` — Ordered within 60 days
  - `at_risk` — Last order 60-90 days ago
  - `inactive` — No orders in 90+ days (default threshold)
  - `new` — Customer with no orders yet
  - `churned` — No orders ever, account older than 180 days
- **Multi-Format Reports**: Excel (multi-sheet), CSV, JSON, and email lists
- **Scheduled Execution**: Run daily at a specified time
- **Configurable Thresholds**: Adjust inactive days via CLI or environment variables

## Project Structure

```
Netsuite Agent/
├── web_app.py               # Flask web application
├── agent.py                 # Main orchestrator & CLI entry point
├── netsuite_client.py       # NetSuite REST API client with TBA auth
├── customer_analytics.py    # Customer activity analysis engine
├── report_generator.py      # Excel/CSV/JSON report generation
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variable template
├── templates/
│   └── index.html           # Web dashboard UI
├── static/
│   ├── css/style.css        # Web UI styles
│   └── js/app.js            # Web UI frontend logic
└── README.md                # This file
```
REPLACE


## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure NetSuite API Access

You need **Token-Based Authentication (TBA)** credentials from NetSuite:

1. In NetSuite, go to **Setup > Integration > Web Services Preferences**
2. Enable **REST API** and **SuiteQL**
3. Go to **Setup > Integration > Manage Integrations > New**
   - Create an integration with **Token-Based Authentication** enabled
   - Save the **Consumer Key** and **Consumer Secret**
4. Go to **Setup > Users/Roles > Access Tokens > New**
   - Select your user and the integration you just created
   - Save the **Token ID** and **Token Secret**
5. Note your **Account ID** (found in Setup > Company > Company Information)

### 3. Create Environment File

Copy the example file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your actual values:

```env
NETSUITE_ACCOUNT_ID=your_account_id
NETSUITE_CONSUMER_KEY=your_consumer_key
NETSUITE_CONSUMER_SECRET=your_consumer_secret
NETSUITE_TOKEN_ID=your_token_id
NETSUITE_TOKEN_SECRET=your_token_secret

# Agent Configuration
INACTIVE_DAYS_THRESHOLD=90
REPORT_OUTPUT_PATH=./reports
SCHEDULE_ENABLED=false
SCHEDULE_TIME=08:00
```

## Usage

### Web Dashboard (Recommended)

Launch the web UI for an interactive experience:

```bash
python web_app.py
```

Then open your browser to `http://localhost:5000`

The web dashboard provides:
- **Settings Panel** — Configure NetSuite credentials and thresholds
- **Connection Test** — Verify API connectivity before running
- **Run Analysis** — Select filters and export formats, then execute
- **Live Progress** — Real-time progress bar and status updates
- **Results View** — Summary cards and sortable customer table
- **Reports Manager** — Download or delete generated reports

#### Web UI Options

| Setting | Description |
|---------|-------------|
| NetSuite Account ID | Your NetSuite account identifier |
| Consumer Key / Secret | Integration credentials |
| Token ID / Secret | Access token credentials |
| Inactive Threshold | Days since last order (default: 90) |
| Filter by Status | Show all, inactive, at-risk, active, new, or churned |
| Export Formats | Excel, CSV, JSON checkboxes |

### Command Line Interface

#### Basic Run (Full Analysis)

```bash
python agent.py
```

This will:
1. Fetch all customers and their order history from NetSuite
2. Analyze activity and segment customers
3. Generate reports in `./reports/`

#### Show Only Inactive Customers

```bash
python agent.py --status inactive
```

#### Export Specific Formats

```bash
python agent.py --export excel csv
```

#### Use a Different Threshold (e.g., 60 days)

```bash
python agent.py --threshold 60
```

#### Run on a Daily Schedule

```bash
python agent.py --schedule --schedule-time 09:00
```

#### All CLI Options

```bash
python agent.py --help
```

| Option | Description |
|--------|-------------|
| `--status` | Filter by status: active, inactive, at_risk, new, churned |
| `--export` | Export formats: excel, csv, json |
| `--threshold` | Days since last order to consider inactive (default: 90) |
| `--output` | Output directory for reports (default: ./reports) |
| `--schedule` | Run daily at scheduled time |
| `--schedule-time` | Time to run (HH:MM format, default: 08:00) |
| `--quiet` | Suppress progress output |
REPLACE


## Report Outputs

After each run, the following files are generated in `./reports/`:

| File | Description |
|------|-------------|
| `customer_activity_report_YYYYMMDD_HHMMSS.xlsx` | Multi-sheet Excel workbook |
| `customer_activity_YYYYMMDD_HHMMSS.csv` | All customers (CSV) |
| `inactive_customers_YYYYMMDD_HHMMSS.csv` | Only inactive customers (CSV) |
| `customer_activity_report_YYYYMMDD_HHMMSS.json` | Full data + summary (JSON) |
| `email_list_inactive_at_risk_YYYYMMDD_HHMMSS.txt` | Emails for re-engagement campaigns |

### Excel Workbook Sheets

1. **Summary** — Key metrics and statistics
2. **All Customers** — Complete customer list with status
3. **Inactive Customers** — Customers with 90+ days since last order
4. **At Risk Customers** — Customers with 60-90 days since last order
5. **Status Breakdown** — Count by status category

## Example Output

```
============================================================
NetSuite Customer Activity Agent
============================================================
Analysis started: 2026-05-27T13:30:00+00:00
Inactive threshold: 90 days

[1/3] Analyzing customer activity...
  Fetched 1000 customers so far...
  Fetched 1500 customers so far...
Total customers fetched: 1542

[2/3] Generating summary...

----------------------------------------
CUSTOMER ACTIVITY SUMMARY
----------------------------------------
Total Customers:      1542
Active:               890
At Risk (60-90 days): 234
Inactive (90+ days):  312
New (no orders):      106
Churned (no orders, 180+ days): 0
----------------------------------------
Inactive %:           20.23%
At Risk %:            15.18%
----------------------------------------
Total Revenue:        $12,450,000.00
Total Orders:         45,230
Inactive Revenue:     $2,100,000.00
----------------------------------------

[3/3] Generating reports...
Excel report saved: ./reports/customer_activity_report_20260527_133045.xlsx
CSV report saved: ./reports/customer_activity_20260527_133045.csv
Inactive customers CSV saved: ./reports/inactive_customers_20260527_133045.csv
JSON report saved: ./reports/customer_activity_report_20260527_133045.json
Email list saved: ./reports/email_list_inactive_at_risk_20260527_133045.txt (412 emails)

Generated 5 report files.
Reports saved to: ./reports

Analysis complete!
```

## Troubleshooting

### "NetSuite API Error"

- Verify your `.env` credentials are correct
- Ensure Token-Based Authentication is enabled for your integration
- Confirm the REST API feature is enabled in your NetSuite account
- Check that your user role has permission to view customers and transactions

### "No customers found"

- Verify your SuiteQL permissions in NetSuite
- Check that you have active customers in your account
- Ensure the `customer` and `transaction` records are accessible via REST API

### SSL/TLS Errors

If you encounter SSL certificate errors, your system may need updated CA certificates:

```bash
pip install --upgrade certifi
```

## Web Deployment

### Environment Variables for Web Mode

```env
FLASK_SECRET_KEY=your-random-secret-key-here
PORT=5000
FLASK_DEBUG=false
```

### Production Deployment

For production, use a WSGI server like Gunicorn:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 web_app:app
```

### Docker Deployment

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "web_app:app"]
```

Build and run:

```bash
docker build -t netsuite-agent .
docker run -p 5000:5000 --env-file .env netsuite-agent
```

## Security Notes

- **Never commit your `.env` file** to version control
- Store credentials securely; rotate tokens periodically
- Use a dedicated integration user with minimal required permissions
- The agent uses HMAC-SHA256 OAuth 1.0a signatures for secure authentication
- Change the default `FLASK_SECRET_KEY` in production
REPLACE


## License

MIT License — feel free to modify and distribute.
