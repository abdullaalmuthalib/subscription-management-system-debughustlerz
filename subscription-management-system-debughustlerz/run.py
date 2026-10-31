from app import app
from models import init_db

if __name__ == '__main__':
    init_db()
    print("=" * 65)
    print(" Brightloop Software - Subscription & Recurring Billing System")
    print(" Built for Odoo Hackathon 2026")
    print(" Access Web App at: http://127.0.0.1:5000")
    print("=" * 65)
    app.run(host='0.0.0.0', port=5000, debug=True)

