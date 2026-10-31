import sqlite3
import os
import re
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), 'brightloop.db')

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn

def validate_password(password):
    """
    Password policy:
    - More than 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one special character
    """
    if len(password) <= 8:
        return False, "Password must be more than 8 characters long."
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r'[^a-zA-Z0-9]', password):
        return False, "Password must contain at least one special character."
    return True, "Valid"

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # 1. Users table (Admin, Staff, Customer)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin', 'staff', 'customer')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Password reset tokens
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS password_resets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        token TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_used INTEGER DEFAULT 0
    );
    """)

    # 3. Products
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        product_type TEXT NOT NULL,
        sales_price REAL NOT NULL DEFAULT 0.0,
        cost_price REAL NOT NULL DEFAULT 0.0,
        notes TEXT
    );
    """)

    # 4. Product Variants (e.g., Brand Odoo adds +560 to price)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS product_variants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        attribute_name TEXT NOT NULL,
        attribute_value TEXT NOT NULL,
        price_extra REAL NOT NULL DEFAULT 0.0,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
    );
    """)

    # 5. Plans (daily, weekly, monthly, yearly)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        billing_interval TEXT NOT NULL CHECK(billing_interval IN ('daily', 'weekly', 'monthly', 'yearly')),
        cost REAL NOT NULL DEFAULT 0.0,
        min_quantity INTEGER NOT NULL DEFAULT 1,
        start_date DATE NOT NULL,
        end_date DATE,
        auto_close INTEGER NOT NULL DEFAULT 0,
        allow_pause INTEGER NOT NULL DEFAULT 1,
        allow_renew INTEGER NOT NULL DEFAULT 1
    );
    """)

    # 6. Tax Rules
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tax_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        rate REAL NOT NULL,
        is_active INTEGER DEFAULT 1
    );
    """)

    # 7. Discount Rules
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS discount_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        discount_type TEXT NOT NULL CHECK(discount_type IN ('fixed', 'percentage')),
        value REAL NOT NULL,
        min_purchase REAL DEFAULT 0.0,
        min_quantity INTEGER DEFAULT 0,
        start_date DATE NOT NULL,
        end_date DATE,
        max_usage INTEGER,
        usage_count INTEGER DEFAULT 0,
        scope TEXT NOT NULL CHECK(scope IN ('subscription', 'product')),
        product_id INTEGER,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
    );
    """)

    # 8. Quotation Templates
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quotation_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        plan_id INTEGER NOT NULL,
        validity_days INTEGER NOT NULL DEFAULT 30,
        notes TEXT,
        FOREIGN KEY (plan_id) REFERENCES plans(id)
    );
    """)

    # 9. Quotation Template Lines
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quotation_template_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        variant_id INTEGER,
        quantity INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY (template_id) REFERENCES quotation_templates(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id),
        FOREIGN KEY (variant_id) REFERENCES product_variants(id)
    );
    """)

    # 10. Subscriptions
    # States: Draft, Quotation, Confirmed, Active, Paused, Closed
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subscription_number TEXT UNIQUE NOT NULL,
        customer_id INTEGER NOT NULL,
        plan_id INTEGER NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('draft', 'quotation', 'confirmed', 'active', 'paused', 'closed')),
        start_date DATE NOT NULL,
        expiry_date DATE,
        next_billing_date DATE NOT NULL,
        payment_terms TEXT NOT NULL DEFAULT 'Immediate',
        discount_rule_id INTEGER,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES users(id),
        FOREIGN KEY (plan_id) REFERENCES plans(id),
        FOREIGN KEY (discount_rule_id) REFERENCES discount_rules(id)
    );
    """)

    # 11. Subscription Lines
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS subscription_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subscription_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        variant_id INTEGER,
        quantity INTEGER NOT NULL DEFAULT 1,
        unit_price REAL NOT NULL,
        tax_rule_id INTEGER,
        amount REAL NOT NULL,
        FOREIGN KEY (subscription_id) REFERENCES subscriptions(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id),
        FOREIGN KEY (variant_id) REFERENCES product_variants(id),
        FOREIGN KEY (tax_rule_id) REFERENCES tax_rules(id)
    );
    """)

    # 12. Invoices
    # States: Draft, Confirmed, Paid, Cancelled
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_number TEXT UNIQUE NOT NULL,
        subscription_id INTEGER,
        customer_id INTEGER NOT NULL,
        invoice_date DATE NOT NULL,
        due_date DATE NOT NULL,
        amount_untaxed REAL NOT NULL DEFAULT 0.0,
        amount_tax REAL NOT NULL DEFAULT 0.0,
        amount_discount REAL NOT NULL DEFAULT 0.0,
        amount_total REAL NOT NULL DEFAULT 0.0,
        state TEXT NOT NULL CHECK(state IN ('draft', 'confirmed', 'paid', 'cancelled')),
        billing_cycle_date DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (subscription_id) REFERENCES subscriptions(id) ON DELETE SET NULL,
        FOREIGN KEY (customer_id) REFERENCES users(id)
    );
    """)

    # 13. Invoice Lines
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS invoice_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        variant_id INTEGER,
        description TEXT NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1,
        unit_price REAL NOT NULL,
        tax_rate REAL NOT NULL DEFAULT 0.0,
        discount_amount REAL NOT NULL DEFAULT 0.0,
        subtotal REAL NOT NULL,
        FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id),
        FOREIGN KEY (variant_id) REFERENCES product_variants(id)
    );
    """)

    # 14. Payments
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER NOT NULL,
        payment_method TEXT NOT NULL,
        amount REAL NOT NULL,
        payment_date DATE NOT NULL,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
    );
    """)

    # Indexes for fast response under 2 seconds
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sub_customer ON subscriptions(customer_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sub_state ON subscriptions(state);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sub_billing_date ON subscriptions(next_billing_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inv_customer ON invoices(customer_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inv_state ON invoices(state);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inv_due_date ON invoices(due_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments(invoice_id);")

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database schema successfully initialized.")
