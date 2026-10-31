from datetime import date, timedelta
from werkzeug.security import generate_password_hash
from models import init_db, get_db

def seed_database():
    init_db()
    conn = get_db()
    conn.execute("PRAGMA foreign_keys = OFF;")
    cursor = conn.cursor()

    # Clear existing data for fresh seed
    tables = [
        'payments', 'invoice_lines', 'invoices', 'subscription_lines',
        'subscriptions', 'quotation_template_lines', 'quotation_templates',
        'discount_rules', 'tax_rules', 'plans', 'product_variants',
        'products', 'password_resets', 'users'
    ]
    for tbl in tables:
        cursor.execute(f"DELETE FROM {tbl};")
    cursor.execute("DELETE FROM sqlite_sequence;")

    # 1. Users
    cursor.execute("INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                   ("Brightloop Administrator", "admin@brightloop.com", generate_password_hash("Admin@123456"), "admin"))
    admin_id = cursor.lastrowid

    cursor.execute("INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                   ("Sarah Jenkins (Staff)", "sarah.staff@brightloop.com", generate_password_hash("Staff@123456"), "staff"))
    staff_id = cursor.lastrowid

    cursor.execute("INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                   ("Acme Retail Corp", "billing@acmeretail.com", generate_password_hash("Customer@123456"), "customer"))
    acme_id = cursor.lastrowid

    cursor.execute("INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                   ("Global Tech Industries", "finance@globaltech.com", generate_password_hash("Customer@123456"), "customer"))
    global_tech_id = cursor.lastrowid

    cursor.execute("INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                   ("Apex Creative Studio", "hello@apexstudio.io", generate_password_hash("Customer@123456"), "customer"))
    apex_id = cursor.lastrowid

    # 2. Products
    cursor.execute("""
        INSERT INTO products (name, product_type, sales_price, cost_price, notes)
        VALUES ('Brightloop Core ERP', 'Software License', 120.00, 30.00, 'Main business management seat')
    """)
    prod_erp = cursor.lastrowid

    cursor.execute("""
        INSERT INTO products (name, product_type, sales_price, cost_price, notes)
        VALUES ('AI Business Analytics Add-on', 'Add-on', 50.00, 10.00, 'Predictive revenue and pipeline insights')
    """)
    prod_ai = cursor.lastrowid

    cursor.execute("""
        INSERT INTO products (name, product_type, sales_price, cost_price, notes)
        VALUES ('24/7 Dedicated Support', 'Service', 250.00, 80.00, 'SLA with 1-hour response time')
    """)
    prod_support = cursor.lastrowid

    # 3. Product Variants (Brand Odoo adds 560 to price - from PDF requirement)
    cursor.execute("""
        INSERT INTO product_variants (product_id, attribute_name, attribute_value, price_extra)
        VALUES (?, 'Brand', 'Standard Edition', 0.00)
    """, (prod_erp,))
    var_erp_std = cursor.lastrowid

    cursor.execute("""
        INSERT INTO product_variants (product_id, attribute_name, attribute_value, price_extra)
        VALUES (?, 'Brand', 'Odoo Edition', 560.00)
    """, (prod_erp,))
    var_erp_odoo = cursor.lastrowid

    cursor.execute("""
        INSERT INTO product_variants (product_id, attribute_name, attribute_value, price_extra)
        VALUES (?, 'Tier', 'Standard Analytics', 0.00)
    """, (prod_ai,))
    var_ai_std = cursor.lastrowid

    # 4. Plans
    today = date.today()
    cursor.execute("""
        INSERT INTO plans (name, billing_interval, cost, min_quantity, start_date, end_date, auto_close, allow_pause, allow_renew)
        VALUES ('Monthly Growth Plan', 'monthly', 120.00, 1, ?, NULL, 0, 1, 1)
    """, (today.strftime("%Y-%m-%d"),))
    plan_monthly = cursor.lastrowid

    cursor.execute("""
        INSERT INTO plans (name, billing_interval, cost, min_quantity, start_date, end_date, auto_close, allow_pause, allow_renew)
        VALUES ('Yearly Enterprise Contract', 'yearly', 1200.00, 5, ?, NULL, 0, 1, 1)
    """, (today.strftime("%Y-%m-%d"),))
    plan_yearly = cursor.lastrowid

    cursor.execute("""
        INSERT INTO plans (name, billing_interval, cost, min_quantity, start_date, end_date, auto_close, allow_pause, allow_renew)
        VALUES ('Weekly Sprint Pass', 'weekly', 45.00, 1, ?, NULL, 0, 1, 1)
    """, (today.strftime("%Y-%m-%d"),))
    plan_weekly = cursor.lastrowid

    cursor.execute("""
        INSERT INTO plans (name, billing_interval, cost, min_quantity, start_date, end_date, auto_close, allow_pause, allow_renew)
        VALUES ('14-Day Fixed Trial', 'daily', 5.00, 1, ?, ?, 1, 0, 0)
    """, (today.strftime("%Y-%m-%d"), (today + timedelta(days=14)).strftime("%Y-%m-%d")))
    plan_trial = cursor.lastrowid

    # 5. Tax Rules
    cursor.execute("INSERT INTO tax_rules (name, rate, is_active) VALUES ('VAT 10%', 10.0, 1)")
    tax_vat10 = cursor.lastrowid

    cursor.execute("INSERT INTO tax_rules (name, rate, is_active) VALUES ('Sales Tax 8%', 8.0, 1)")
    tax_sales8 = cursor.lastrowid

    cursor.execute("INSERT INTO tax_rules (name, rate, is_active) VALUES ('Zero Tax / Exempt', 0.0, 1)")
    tax_zero = cursor.lastrowid

    # 6. Discount Rules
    cursor.execute("""
        INSERT INTO discount_rules (
            name, discount_type, value, min_purchase, min_quantity,
            start_date, end_date, max_usage, usage_count, scope, product_id
        ) VALUES (
            'Enterprise High-Seat 10% Discount', 'percentage', 10.0, 0.0, 5,
            ?, NULL, 100, 4, 'subscription', NULL
        )
    """, (today.strftime("%Y-%m-%d"),))
    discount_volume = cursor.lastrowid

    cursor.execute("""
        INSERT INTO discount_rules (
            name, discount_type, value, min_purchase, min_quantity,
            start_date, end_date, max_usage, usage_count, scope, product_id
        ) VALUES (
            'Odoo Brand Launch $50 Credit', 'fixed', 50.0, 100.0, 0,
            ?, NULL, 50, 1, 'product', ?
        )
    """, (today.strftime("%Y-%m-%d"), prod_erp))
    discount_odoo = cursor.lastrowid

    # 7. Quotation Templates
    cursor.execute("""
        INSERT INTO quotation_templates (name, plan_id, validity_days, notes)
        VALUES ('Enterprise Starter Package', ?, 30, 'Includes 5 Core ERP seats and 1 AI Analytics Add-on')
    """, (plan_yearly,))
    template_enterprise = cursor.lastrowid

    cursor.execute("""
        INSERT INTO quotation_template_lines (template_id, product_id, variant_id, quantity)
        VALUES (?, ?, ?, 5)
    """, (template_enterprise, prod_erp, var_erp_odoo))

    cursor.execute("""
        INSERT INTO quotation_template_lines (template_id, product_id, variant_id, quantity)
        VALUES (?, ?, ?, 1)
    """, (template_enterprise, prod_ai, var_ai_std))

    # 8. Subscriptions
    # SUB 1: Active Monthly Acme Corp (Due Today for automated billing!)
    cursor.execute("""
        INSERT INTO subscriptions (
            subscription_number, customer_id, plan_id, state, start_date, expiry_date,
            next_billing_date, payment_terms, discount_rule_id, notes
        ) VALUES (
            'SUB-2026-0001', ?, ?, 'active', ?, ?, ?, 'Immediate', NULL, 'Small retail shop on monthly billing'
        )
    """, (acme_id, plan_monthly, (today - timedelta(days=30)).strftime("%Y-%m-%d"),
          (today + timedelta(days=335)).strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")))
    sub1_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO subscription_lines (subscription_id, product_id, variant_id, quantity, unit_price, tax_rule_id, amount)
        VALUES (?, ?, ?, 2, 120.00, ?, 240.00)
    """, (sub1_id, prod_erp, var_erp_std, tax_vat10))

    # SUB 2: Active Yearly Global Tech with Odoo Edition (+560) and 10% volume discount
    cursor.execute("""
        INSERT INTO subscriptions (
            subscription_number, customer_id, plan_id, state, start_date, expiry_date,
            next_billing_date, payment_terms, discount_rule_id, notes
        ) VALUES (
            'SUB-2026-0002', ?, ?, 'active', ?, ?, ?, '15 Days', ?, 'Corporate account with Odoo brand variant'
        )
    """, (global_tech_id, plan_yearly, (today - timedelta(days=90)).strftime("%Y-%m-%d"),
          (today + timedelta(days=275)).strftime("%Y-%m-%d"), (today + timedelta(days=275)).strftime("%Y-%m-%d"),
          discount_volume))
    sub2_id = cursor.lastrowid

    # 120 base + 560 extra = 680 per unit * 10 seats = 6800.00
    cursor.execute("""
        INSERT INTO subscription_lines (subscription_id, product_id, variant_id, quantity, unit_price, tax_rule_id, amount)
        VALUES (?, ?, ?, 10, 680.00, ?, 6800.00)
    """, (sub2_id, prod_erp, var_erp_odoo, tax_vat10))

    cursor.execute("""
        INSERT INTO subscription_lines (subscription_id, product_id, variant_id, quantity, unit_price, tax_rule_id, amount)
        VALUES (?, ?, ?, 1, 250.00, ?, 250.00)
    """, (sub2_id, prod_support, None, tax_zero))

    # SUB 3: Quotation for Apex Creative Studio
    cursor.execute("""
        INSERT INTO subscriptions (
            subscription_number, customer_id, plan_id, state, start_date, expiry_date,
            next_billing_date, payment_terms, discount_rule_id, notes
        ) VALUES (
            'SUB-2026-0003', ?, ?, 'quotation', ?, ?, ?, '30 Days', NULL, 'Pending customer quote approval'
        )
    """, (apex_id, plan_monthly, today.strftime("%Y-%m-%d"),
          (today + timedelta(days=365)).strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")))
    sub3_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO subscription_lines (subscription_id, product_id, variant_id, quantity, unit_price, tax_rule_id, amount)
        VALUES (?, ?, ?, 3, 120.00, ?, 360.00)
    """, (sub3_id, prod_erp, var_erp_std, tax_sales8))

    # SUB 4: Draft Subscription
    cursor.execute("""
        INSERT INTO subscriptions (
            subscription_number, customer_id, plan_id, state, start_date, expiry_date,
            next_billing_date, payment_terms, discount_rule_id, notes
        ) VALUES (
            'SUB-2026-0004', ?, ?, 'draft', ?, NULL, ?, 'Immediate', NULL, 'Draft created by sales staff'
        )
    """, (acme_id, plan_weekly, today.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")))

    # 9. Invoices & Payments (to test Finance Lead Dashboard: Paid, Confirmed, Overdue)
    # Invoice 1: Paid invoice
    cursor.execute("""
        INSERT INTO invoices (
            invoice_number, subscription_id, customer_id, invoice_date, due_date,
            amount_untaxed, amount_tax, amount_discount, amount_total, state, billing_cycle_date
        ) VALUES (
            'INV-2026-0001', ?, ?, ?, ?, 240.00, 24.00, 0.00, 264.00, 'paid', ?
        )
    """, (sub1_id, acme_id, (today - timedelta(days=30)).strftime("%Y-%m-%d"),
          (today - timedelta(days=15)).strftime("%Y-%m-%d"), (today - timedelta(days=30)).strftime("%Y-%m-%d")))
    inv1_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO invoice_lines (invoice_id, product_id, variant_id, description, quantity, unit_price, tax_rate, discount_amount, subtotal)
        VALUES (?, ?, ?, 'Brightloop Core ERP (Brand: Standard Edition)', 2, 120.00, 10.0, 0.00, 264.00)
    """, (inv1_id, prod_erp, var_erp_std))

    cursor.execute("""
        INSERT INTO payments (invoice_id, payment_method, amount, payment_date, notes)
        VALUES (?, 'Credit Card (Stripe)', 264.00, ?, 'Payment verified and settled')
    """, (inv1_id, (today - timedelta(days=20)).strftime("%Y-%m-%d")))

    # Invoice 2: Confirmed but unpaid (Current, not overdue yet)
    cursor.execute("""
        INSERT INTO invoices (
            invoice_number, subscription_id, customer_id, invoice_date, due_date,
            amount_untaxed, amount_tax, amount_discount, amount_total, state, billing_cycle_date
        ) VALUES (
            'INV-2026-0002', ?, ?, ?, ?, 6345.00, 634.50, 705.00, 6979.50, 'confirmed', ?
        )
    """, (sub2_id, global_tech_id, today.strftime("%Y-%m-%d"),
          (today + timedelta(days=15)).strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")))
    inv2_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO invoice_lines (invoice_id, product_id, variant_id, description, quantity, unit_price, tax_rate, discount_amount, subtotal)
        VALUES (?, ?, ?, 'Brightloop Core ERP (Brand: Odoo Edition)', 10, 680.00, 10.0, 680.00, 6732.00)
    """, (inv2_id, prod_erp, var_erp_odoo))

    cursor.execute("""
        INSERT INTO invoice_lines (invoice_id, product_id, variant_id, description, quantity, unit_price, tax_rate, discount_amount, subtotal)
        VALUES (?, ?, ?, '24/7 Dedicated Support', 1, 250.00, 0.0, 25.00, 247.50)
    """, (inv2_id, prod_support, None))

    # Invoice 3: OVERDUE Invoice (Due date was 10 days ago, state is confirmed)
    cursor.execute("""
        INSERT INTO invoices (
            invoice_number, subscription_id, customer_id, invoice_date, due_date,
            amount_untaxed, amount_tax, amount_discount, amount_total, state, billing_cycle_date
        ) VALUES (
            'INV-2026-0003', ?, ?, ?, ?, 360.00, 28.80, 0.00, 388.80, 'confirmed', ?
        )
    """, (sub3_id, apex_id, (today - timedelta(days=25)).strftime("%Y-%m-%d"),
          (today - timedelta(days=10)).strftime("%Y-%m-%d"), (today - timedelta(days=25)).strftime("%Y-%m-%d")))
    inv3_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO invoice_lines (invoice_id, product_id, variant_id, description, quantity, unit_price, tax_rate, discount_amount, subtotal)
        VALUES (?, ?, ?, 'Brightloop Core ERP (Brand: Standard Edition)', 3, 120.00, 8.0, 0.00, 388.80)
    """, (inv3_id, prod_erp, var_erp_std))

    conn.commit()
    conn.close()
    print("Seed data successfully inserted.")

if __name__ == '__main__':
    seed_database()
