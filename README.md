# Core Banking Simulator

A hands-on learning project implementing core banking concepts including
double-entry ledger, account management, card issuing, and payment processing.

## Setup
```bash
# Clone the repository
git clone <repo-url>
cd core-banking-simulator

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env

# Run the application
uvicorn core_banking.main:app --host 0.0.0.0 --port 8000 --reload
```

## Technology Stack

- **Language:** Python 3.12 with FastAPI
- **Database:** PostgreSQL 15 (AWS RDS)
- **Testing:** pytest
- **Deployment:** AWS EC2 with Nginx, Gunicorn
