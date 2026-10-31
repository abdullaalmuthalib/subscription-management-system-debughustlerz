import os
import time
import uuid
from datetime import datetime, date, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, g

from models import get_db, validate_password
from werkzeug.security import generate_password_hash, check_password_hash
import billing_engine

app = Flask(__name__)
app.secret_key = os.urandom(24)

# -------------------------------------------------------------
# Middleware & Context Processors
# -------------------------------------------------------------
@app.before_request
def record_start_time():
    g.start_time = time.time()
    g.user = None
    if 'user_id' in session:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, role FROM users WHERE id = ?", (session['user_id'],))
        g.user = cursor.fetchone()
        conn.close()

@app.context_processor
def inject_global_data():
    elapsed = 0.0
    if hasattr(g, 'start_time'):
        elapsed = round((time.time() - g.start_time) * 1000, 2)
    return {
        'current_user': g.user,
        'today': date.today().strftime("%Y-%m-%d"),
        'response_time_ms': elapsed
    }

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not g.user:
            flash("Please log in to continue.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not g.user:
            return redirect(url_for('login'))
        if g.user['role'] != 'admin':
            flash("Access denied: Administrator privileges required.", "danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def staff_or_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not g.user:
            return redirect(url_for('login'))
        if g.user['role'] not in ('admin', 'staff'):
            flash("Access denied: Internal staff privileges required.", "danger")
            return redirect(url_for('portal'))
        return f(*args, **kwargs)
    return decorated_function

# -------------------------------------------------------------
# Authentication Routes
# -------------------------------------------------------------
@app.route('/')
def index():
    if g.user:
        if g.user['role'] == 'customer':
            return redirect(url_for('portal'))
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['user_role'] = user['role']
            session['user_name'] = user['name']
            flash(f"Welcome back, {user['name']}!", "success")
            if user['role'] == 'customer':
                return redirect(url_for('portal'))
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid email or password. Please try again.", "danger")

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Public customer signup:
    - Unique email
    - Password > 8 chars, 1 uppercase, 1 lowercase, 1 special char
    """
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not name or not email or not password:
            flash("All fields are required.", "danger")
            return render_template('register.html')

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template('register.html')

        is_valid, msg = validate_password(password)
        if not is_valid:
            flash(msg, "danger")
            return render_template('register.html')

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cursor.fetchone():
            conn.close()
            flash("An account with this email already exists.", "danger")
            return render_template('register.html')

        pwd_hash = generate_password_hash(password)
        cursor.execute("INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'customer')",
                       (name, email, pwd_hash))
        conn.commit()
        conn.close()

        flash("Account created successfully! Please log in.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        if user:
            token = str(uuid.uuid4())
            cursor.execute("INSERT INTO password_resets (email, token) VALUES (?, ?)", (email, token))
            conn.commit()
            conn.close()
            reset_url = url_for('reset_password', token=token, _external=True)
            flash(f"Password reset link generated! For demonstration: {reset_url}", "info")
            return redirect(url_for('login'))
        conn.close()
        flash("If that email is registered, a password reset link has been dispatched.", "info")
        return redirect(url_for('login'))

    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM password_resets WHERE token = ? AND is_used = 0", (token,))
    reset_entry = cursor.fetchone()

    if not reset_entry:
        conn.close()
        flash("Invalid or expired password reset link.", "danger")
        return redirect(url_for('login'))

    if request.method == 'POST':
        new_password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if new_password != confirm_password:
            flash("Passwords do not match.", "danger")
            conn.close()
            return render_template('reset_password.html', token=token)

        is_valid, msg = validate_password(new_password)
        if not is_valid:
            flash(msg, "danger")
            conn.close()
            return render_template('reset_password.html', token=token)

        pwd_hash = generate_password_hash(new_password)
        cursor.execute("UPDATE users SET password_hash = ? WHERE email = ?", (pwd_hash, reset_entry['email']))
        cursor.execute("UPDATE password_resets SET is_used = 1 WHERE id = ?", (reset_entry['id'],))
        conn.commit()
        conn.close()

        flash("Password updated successfully. You can now log in.", "success")
        return redirect(url_for('login'))

    conn.close()
    return render_template('reset_password.html', token=token)

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for('login'))

# -------------------------------------------------------------
# Staff Management (Admin Only)
# -------------------------------------------------------------
@app.route('/staff', methods=['GET', 'POST'])
@admin_required
def staff_management():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        is_valid, msg = validate_password(password)
        if not is_valid:
            flash(msg, "danger")
        else:
            cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
            if cursor.fetchone():
                flash("Email already registered.", "danger")
            else:
                cursor.execute("INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'staff')",
                               (name, email, generate_password_hash(password)))
                conn.commit()
                flash(f"Staff member {name} successfully added.", "success")

    cursor.execute("SELECT id, name, email, role, created_at FROM users WHERE role = 'staff' ORDER BY id DESC")
    staff_members = cursor.fetchall()
    conn.close()
    return render_template('staff.html', staff_members=staff_members)

# -------------------------------------------------------------
# Finance Lead Dashboard & Analytics
# -------------------------------------------------------------
@app.route('/dashboard')
@staff_or_admin_required
def dashboard():
    conn = get_db()
    cursor = conn.cursor()
    today_str = date.today().strftime("%Y-%m-%d")

    # 1. Total Active Subscriptions
    cursor.execute("SELECT COUNT(*) as count FROM subscriptions WHERE state = 'active'")
    active_subs_count = cursor.fetchone()['count']

    # 2. Total Revenue Collected (Paid Invoices)
    cursor.execute("SELECT COALESCE(SUM(amount), 0.0) as total FROM payments")
    total_revenue = cursor.fetchone()['total']

    # 3. Revenue Still Owed (Confirmed, unpaid invoices)
    cursor.execute("SELECT COALESCE(SUM(amount_total), 0.0) as owed FROM invoices WHERE state = 'confirmed'")
    total_owed = cursor.fetchone()['owed']

    # 4. Overdue Invoices
    cursor.execute("""
        SELECT COUNT(*) as count, COALESCE(SUM(amount_total), 0.0) as total
        FROM invoices
        WHERE state = 'confirmed' AND due_date < ?
    """, (today_str,))
    overdue_stat = cursor.fetchone()
    overdue_count = overdue_stat['count']
    overdue_amount = overdue_stat['total']

    # 5. Overdue Invoices List
    cursor.execute("""
        SELECT i.*, u.name as customer_name
        FROM invoices i
        JOIN users u ON i.customer_id = u.id
        WHERE i.state = 'confirmed' AND i.due_date < ?
        ORDER BY i.due_date ASC
    """, (today_str,))
    overdue_invoices = cursor.fetchall()

    # 6. Recent Invoices
    cursor.execute("""
        SELECT i.*, u.name as customer_name
        FROM invoices i
        JOIN users u ON i.customer_id = u.id
        ORDER BY i.id DESC LIMIT 5
    """)
    recent_invoices = cursor.fetchall()

    # 7. Recent Subscriptions
    cursor.execute("""
        SELECT s.*, u.name as customer_name, p.name as plan_name
        FROM subscriptions s
        JOIN users u ON s.customer_id = u.id
        JOIN plans p ON s.plan_id = p.id
        ORDER BY s.id DESC LIMIT 5
    """)
    recent_subs = cursor.fetchall()

    conn.close()
    return render_template('dashboard.html',
                           active_subs_count=active_subs_count,
                           total_revenue=total_revenue,
                           total_owed=total_owed,
                           overdue_count=overdue_count,
                           overdue_amount=overdue_amount,
                           overdue_invoices=overdue_invoices,
                           recent_invoices=recent_invoices,
                           recent_subs=recent_subs)

# -------------------------------------------------------------
# Products & Variants (Admin)
# -------------------------------------------------------------
@app.route('/products', methods=['GET', 'POST'])
@admin_required
def products():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        product_type = request.form.get('product_type', 'Software')
        sales_price = float(request.form.get('sales_price', 0.0) or 0.0)
        cost_price = float(request.form.get('cost_price', 0.0) or 0.0)
        notes = request.form.get('notes', '')

        cursor.execute("""
            INSERT INTO products (name, product_type, sales_price, cost_price, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (name, product_type, sales_price, cost_price, notes))
        conn.commit()
        flash(f"Product '{name}' created successfully.", "success")
        return redirect(url_for('products'))

    cursor.execute("SELECT * FROM products ORDER BY id DESC")
    products_list = cursor.fetchall()

    # Fetch variants for each product
    products_with_variants = []
    for prod in products_list:
        cursor.execute("SELECT * FROM product_variants WHERE product_id = ?", (prod['id'],))
        vars_list = cursor.fetchall()
        products_with_variants.append({'product': prod, 'variants': vars_list})

    conn.close()
    return render_template('products.html', products_with_variants=products_with_variants)

@app.route('/products/<int:product_id>/variant/new', methods=['POST'])
@admin_required
def add_product_variant(product_id):
    attribute_name = request.form.get('attribute_name', 'Brand').strip()
    attribute_value = request.form.get('attribute_value', '').strip()
    price_extra = float(request.form.get('price_extra', 0.0) or 0.0)

    if not attribute_value:
        flash("Variant value is required.", "danger")
        return redirect(url_for('products'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO product_variants (product_id, attribute_name, attribute_value, price_extra)
        VALUES (?, ?, ?, ?)
    """, (product_id, attribute_name, attribute_value, price_extra))
    conn.commit()
    conn.close()

    flash(f"Added variant '{attribute_value}' (+${price_extra:.2f}) to product.", "success")
    return redirect(url_for('products'))

# -------------------------------------------------------------
# Plans (Admin)
# -------------------------------------------------------------
@app.route('/plans', methods=['GET', 'POST'])
@admin_required
def plans():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        billing_interval = request.form.get('billing_interval', 'monthly')
        cost = float(request.form.get('cost', 0.0) or 0.0)
        min_quantity = int(request.form.get('min_quantity', 1) or 1)
        start_date = request.form.get('start_date') or date.today().strftime("%Y-%m-%d")
        end_date = request.form.get('end_date') or None
        auto_close = 1 if request.form.get('auto_close') else 0
        allow_pause = 1 if request.form.get('allow_pause') else 0
        allow_renew = 1 if request.form.get('allow_renew') else 0

        cursor.execute("""
            INSERT INTO plans (name, billing_interval, cost, min_quantity, start_date, end_date, auto_close, allow_pause, allow_renew)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, billing_interval, cost, min_quantity, start_date, end_date, auto_close, allow_pause, allow_renew))
        conn.commit()
        flash(f"Plan '{name}' created successfully.", "success")
        return redirect(url_for('plans'))

    cursor.execute("SELECT * FROM plans ORDER BY id DESC")
    plans_list = cursor.fetchall()
    conn.close()
    return render_template('plans.html', plans=plans_list)

# -------------------------------------------------------------
# Tax Rules (Admin)
# -------------------------------------------------------------
@app.route('/taxes', methods=['GET', 'POST'])
@admin_required
def taxes():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        rate = float(request.form.get('rate', 0.0) or 0.0)
        cursor.execute("INSERT INTO tax_rules (name, rate, is_active) VALUES (?, ?, 1)", (name, rate))
        conn.commit()
        flash(f"Tax rule '{name}' ({rate}%) created.", "success")
        return redirect(url_for('taxes'))

    cursor.execute("SELECT * FROM tax_rules ORDER BY id DESC")
    tax_rules = cursor.fetchall()
    conn.close()
    return render_template('taxes.html', tax_rules=tax_rules)

# -------------------------------------------------------------
# Discount Rules (Admin)
# -------------------------------------------------------------
@app.route('/discounts', methods=['GET', 'POST'])
@admin_required
def discounts():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        discount_type = request.form.get('discount_type', 'percentage')
        value = float(request.form.get('value', 0.0) or 0.0)
        min_purchase = float(request.form.get('min_purchase', 0.0) or 0.0)
        min_quantity = int(request.form.get('min_quantity', 0) or 0)
        start_date = request.form.get('start_date') or date.today().strftime("%Y-%m-%d")
        end_date = request.form.get('end_date') or None
        max_usage = int(request.form.get('max_usage')) if request.form.get('max_usage') else None
        scope = request.form.get('scope', 'subscription')
        product_id = int(request.form.get('product_id')) if (scope == 'product' and request.form.get('product_id')) else None

        cursor.execute("""
            INSERT INTO discount_rules (
                name, discount_type, value, min_purchase, min_quantity,
                start_date, end_date, max_usage, usage_count, scope, product_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """, (name, discount_type, value, min_purchase, min_quantity, start_date, end_date, max_usage, scope, product_id))
        conn.commit()
        flash(f"Discount rule '{name}' created.", "success")
        return redirect(url_for('discounts'))

    cursor.execute("""
        SELECT d.*, p.name as product_name
        FROM discount_rules d
        LEFT JOIN products p ON d.product_id = p.id
        ORDER BY d.id DESC
    """)
    discount_rules = cursor.fetchall()

    cursor.execute("SELECT id, name FROM products")
    products_list = cursor.fetchall()

    conn.close()
    return render_template('discounts.html', discount_rules=discount_rules, products=products_list)

# -------------------------------------------------------------
# Quotation Templates (Staff / Admin)
# -------------------------------------------------------------
@app.route('/quotation-templates', methods=['GET', 'POST'])
@staff_or_admin_required
def quotation_templates():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        plan_id = int(request.form.get('plan_id'))
        validity_days = int(request.form.get('validity_days', 30) or 30)
        notes = request.form.get('notes', '')

        cursor.execute("""
            INSERT INTO quotation_templates (name, plan_id, validity_days, notes)
            VALUES (?, ?, ?, ?)
        """, (name, plan_id, validity_days, notes))
        conn.commit()
        flash(f"Quotation Template '{name}' created.", "success")
        return redirect(url_for('quotation_templates'))

    cursor.execute("""
        SELECT qt.*, p.name as plan_name, p.billing_interval
        FROM quotation_templates qt
        JOIN plans p ON qt.plan_id = p.id
        ORDER BY qt.id DESC
    """)
    templates = cursor.fetchall()

    cursor.execute("SELECT id, name, billing_interval FROM plans")
    plans_list = cursor.fetchall()

    conn.close()
    return render_template('quotation_templates.html', templates=templates, plans=plans_list)

# -------------------------------------------------------------
# Subscriptions & Quotations
# -------------------------------------------------------------
@app.route('/subscriptions')
@staff_or_admin_required
def subscriptions():
    conn = get_db()
    cursor = conn.cursor()
    state_filter = request.args.get('state', '')

    query = """
        SELECT s.*, u.name as customer_name, p.name as plan_name, p.billing_interval,
               (SELECT COUNT(*) FROM subscription_lines sl WHERE sl.subscription_id = s.id) as line_count,
               (SELECT COALESCE(SUM(amount), 0.0) FROM subscription_lines sl WHERE sl.subscription_id = s.id) as total_amount
        FROM subscriptions s
        JOIN users u ON s.customer_id = u.id
        JOIN plans p ON s.plan_id = p.id
    """
    params = []
    if state_filter:
        query += " WHERE s.state = ?"
        params.append(state_filter)

    query += " ORDER BY s.id DESC"
    cursor.execute(query, tuple(params))
    subs_list = cursor.fetchall()
    conn.close()
    return render_template('subscriptions.html', subscriptions=subs_list, current_state=state_filter)

@app.route('/subscriptions/new', methods=['GET', 'POST'])
@staff_or_admin_required
def new_subscription():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        customer_id = int(request.form.get('customer_id'))
        plan_id = int(request.form.get('plan_id'))
        start_date = request.form.get('start_date') or date.today().strftime("%Y-%m-%d")
        expiry_date = request.form.get('expiry_date') or None
        payment_terms = request.form.get('payment_terms', 'Immediate')
        discount_rule_id = int(request.form.get('discount_rule_id')) if request.form.get('discount_rule_id') else None
        notes = request.form.get('notes', '')
        is_quote = request.form.get('is_quote') == '1'

        # Generate unique subscription number
        cursor.execute("SELECT COUNT(*) as cnt FROM subscriptions")
        cnt = cursor.fetchone()['cnt'] + 1
        sub_number = f"SUB-{date.today().year}-{cnt:04d}"

        initial_state = 'quotation' if is_quote else 'draft'

        cursor.execute("""
            INSERT INTO subscriptions (
                subscription_number, customer_id, plan_id, state, start_date, expiry_date,
                next_billing_date, payment_terms, discount_rule_id, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (sub_number, customer_id, plan_id, initial_state, start_date, expiry_date, start_date, payment_terms, discount_rule_id, notes))
        sub_id = cursor.lastrowid

        # Add initial lines if from template
        template_id = request.form.get('template_id')
        if template_id:
            cursor.execute("""
                SELECT qtl.*, p.sales_price, pv.price_extra
                FROM quotation_template_lines qtl
                JOIN products p ON qtl.product_id = p.id
                LEFT JOIN product_variants pv ON qtl.variant_id = pv.id
                WHERE qtl.template_id = ?
            """, (template_id,))
            tpl_lines = cursor.fetchall()
            for tl in tpl_lines:
                unit_price = tl['sales_price'] + (tl['price_extra'] or 0.0)
                amount = unit_price * tl['quantity']
                cursor.execute("""
                    INSERT INTO subscription_lines (subscription_id, product_id, variant_id, quantity, unit_price, tax_rule_id, amount)
                    VALUES (?, ?, ?, ?, ?, 1, ?)
                """, (sub_id, tl['product_id'], tl['variant_id'], tl['quantity'], unit_price, amount))

        conn.commit()
        conn.close()
        flash(f"Subscription {sub_number} created in '{initial_state}' state.", "success")
        return redirect(url_for('subscription_detail', sub_id=sub_id))

    # Options for form
    cursor.execute("SELECT id, name, email FROM users WHERE role = 'customer' ORDER BY name")
    customers = cursor.fetchall()

    cursor.execute("SELECT id, name, billing_interval, cost FROM plans ORDER BY name")
    plans_list = cursor.fetchall()

    cursor.execute("SELECT id, name, validity_days FROM quotation_templates ORDER BY name")
    templates = cursor.fetchall()

    cursor.execute("SELECT id, name, discount_type, value FROM discount_rules ORDER BY name")
    discounts_list = cursor.fetchall()

    conn.close()
    return render_template('subscription_new.html', customers=customers, plans=plans_list, templates=templates, discounts=discounts_list)

@app.route('/subscriptions/<int:sub_id>')
@login_required
def subscription_detail(sub_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.*, u.name as customer_name, u.email as customer_email,
               p.name as plan_name, p.billing_interval, p.allow_pause, p.allow_renew, p.auto_close,
               d.name as discount_name, d.discount_type, d.value as discount_value
        FROM subscriptions s
        JOIN users u ON s.customer_id = u.id
        JOIN plans p ON s.plan_id = p.id
        LEFT JOIN discount_rules d ON s.discount_rule_id = d.id
        WHERE s.id = ?
    """, (sub_id,))
    sub = cursor.fetchone()

    if not sub:
        conn.close()
        abort(404)

    # Customer security check: customers can only view their own subscriptions
    if g.user['role'] == 'customer' and sub['customer_id'] != g.user['id']:
        conn.close()
        abort(403)

    cursor.execute("""
        SELECT sl.*, p.name as product_name, pv.attribute_name, pv.attribute_value, pv.price_extra,
               tr.name as tax_name, tr.rate as tax_rate
        FROM subscription_lines sl
        JOIN products p ON sl.product_id = p.id
        LEFT JOIN product_variants pv ON sl.variant_id = pv.id
        LEFT JOIN tax_rules tr ON sl.tax_rule_id = tr.id
        WHERE sl.subscription_id = ?
    """, (sub_id,))
    lines = cursor.fetchall()

    # Invoices for this subscription
    cursor.execute("SELECT * FROM invoices WHERE subscription_id = ? ORDER BY id DESC", (sub_id,))
    sub_invoices = cursor.fetchall()

    # Available products and taxes for adding lines
    cursor.execute("SELECT id, name, sales_price FROM products")
    products_list = cursor.fetchall()

    cursor.execute("SELECT id, product_id, attribute_name, attribute_value, price_extra FROM product_variants")
    variants_list = cursor.fetchall()

    cursor.execute("SELECT id, name, rate FROM tax_rules WHERE is_active = 1")
    taxes_list = cursor.fetchall()

    conn.close()
    return render_template('subscription_detail.html',
                           sub=sub, lines=lines, invoices=sub_invoices,
                           products=products_list, variants=variants_list, taxes=taxes_list)

@app.route('/subscriptions/<int:sub_id>/line/add', methods=['POST'])
@staff_or_admin_required
def add_subscription_line(sub_id):
    product_id = int(request.form.get('product_id'))
    variant_id = int(request.form.get('variant_id')) if request.form.get('variant_id') else None
    quantity = int(request.form.get('quantity', 1) or 1)
    tax_rule_id = int(request.form.get('tax_rule_id')) if request.form.get('tax_rule_id') else None

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT sales_price FROM products WHERE id = ?", (product_id,))
    prod = cursor.fetchone()
    base_price = prod['sales_price']

    price_extra = 0.0
    if variant_id:
        cursor.execute("SELECT price_extra FROM product_variants WHERE id = ?", (variant_id,))
        var_row = cursor.fetchone()
        if var_row:
            price_extra = var_row['price_extra']

    unit_price = base_price + price_extra
    amount = unit_price * quantity

    cursor.execute("""
        INSERT INTO subscription_lines (subscription_id, product_id, variant_id, quantity, unit_price, tax_rule_id, amount)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (sub_id, product_id, variant_id, quantity, unit_price, tax_rule_id, amount))
    conn.commit()
    conn.close()

    flash("Item added to subscription.", "success")
    return redirect(url_for('subscription_detail', sub_id=sub_id))

@app.route('/subscriptions/<int:sub_id>/status/<target_state>', methods=['POST'])
@staff_or_admin_required
def change_subscription_status(sub_id, target_state):
    valid_states = ['draft', 'quotation', 'confirmed', 'active', 'paused', 'closed']
    if target_state not in valid_states:
        flash("Invalid target status.", "danger")
        return redirect(url_for('subscription_detail', sub_id=sub_id))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE subscriptions SET state = ? WHERE id = ?", (target_state, sub_id))
    conn.commit()
    conn.close()

    flash(f"Subscription status moved to '{target_state.upper()}'.", "success")
    return redirect(url_for('subscription_detail', sub_id=sub_id))

# -------------------------------------------------------------
# Billing Day & Invoices
# -------------------------------------------------------------
@app.route('/billing-run', methods=['GET', 'POST'])
@staff_or_admin_required
def billing_run():
    generated = []
    if request.method == 'POST':
        target_date_str = request.form.get('target_date') or date.today().strftime("%Y-%m-%d")
        generated = billing_engine.run_recurring_billing(target_date_str)
        if generated:
            flash(f"Billing completed! Generated {len(generated)} recurring invoice(s): {', '.join(generated)}", "success")
        else:
            flash("Billing cycle run. No active subscriptions were due on this date (or already billed).", "info")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.*, u.name as customer_name, p.name as plan_name, p.billing_interval
        FROM subscriptions s
        JOIN users u ON s.customer_id = u.id
        JOIN plans p ON s.plan_id = p.id
        WHERE s.state = 'active'
        ORDER BY s.next_billing_date ASC
    """)
    active_subs = cursor.fetchall()
    conn.close()
    return render_template('billing_run.html', active_subs=active_subs, generated=generated)

@app.route('/invoices')
@login_required
def invoices():
    conn = get_db()
    cursor = conn.cursor()
    state_filter = request.args.get('state', '')
    overdue_only = request.args.get('overdue') == '1'

    query = """
        SELECT i.*, u.name as customer_name, s.subscription_number
        FROM invoices i
        JOIN users u ON i.customer_id = u.id
        LEFT JOIN subscriptions s ON i.subscription_id = s.id
    """
    conditions = []
    params = []

    if g.user['role'] == 'customer':
        conditions.append("i.customer_id = ?")
        params.append(g.user['id'])

    if state_filter:
        conditions.append("i.state = ?")
        params.append(state_filter)

    if overdue_only:
        conditions.append("i.state = 'confirmed' AND i.due_date < ?")
        params.append(date.today().strftime("%Y-%m-%d"))

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY i.id DESC"
    cursor.execute(query, tuple(params))
    invoices_list = cursor.fetchall()
    conn.close()
    return render_template('invoices.html', invoices=invoices_list, state_filter=state_filter, overdue_only=overdue_only)

@app.route('/invoices/<int:inv_id>')
@login_required
def invoice_detail(inv_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT i.*, u.name as customer_name, u.email as customer_email, s.subscription_number
        FROM invoices i
        JOIN users u ON i.customer_id = u.id
        LEFT JOIN subscriptions s ON i.subscription_id = s.id
        WHERE i.id = ?
    """, (inv_id,))
    inv = cursor.fetchone()

    if not inv:
        conn.close()
        abort(404)

    if g.user['role'] == 'customer' and inv['customer_id'] != g.user['id']:
        conn.close()
        abort(403)

    cursor.execute("SELECT * FROM invoice_lines WHERE invoice_id = ?", (inv_id,))
    lines = cursor.fetchall()

    cursor.execute("SELECT * FROM payments WHERE invoice_id = ? ORDER BY id DESC", (inv_id,))
    payments = cursor.fetchall()

    cursor.execute("SELECT COALESCE(SUM(amount), 0.0) as paid FROM payments WHERE invoice_id = ?", (inv_id,))
    total_paid = cursor.fetchone()['paid']
    amount_remaining = max(0.0, inv['amount_total'] - total_paid)

    conn.close()
    return render_template('invoice_detail.html',
                           inv=inv, lines=lines, payments=payments,
                           total_paid=total_paid, amount_remaining=amount_remaining)

@app.route('/invoices/<int:inv_id>/status/<target_state>', methods=['POST'])
@staff_or_admin_required
def change_invoice_status(inv_id, target_state):
    valid_states = ['draft', 'confirmed', 'paid', 'cancelled']
    if target_state not in valid_states:
        flash("Invalid target invoice status.", "danger")
        return redirect(url_for('invoice_detail', inv_id=inv_id))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE invoices SET state = ? WHERE id = ?", (target_state, inv_id))
    conn.commit()
    conn.close()

    flash(f"Invoice marked as {target_state.upper()}.", "success")
    return redirect(url_for('invoice_detail', inv_id=inv_id))

@app.route('/invoices/<int:inv_id>/send', methods=['POST'])
@staff_or_admin_required
def send_invoice_email(inv_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT i.invoice_number, u.email FROM invoices i JOIN users u ON i.customer_id = u.id WHERE i.id = ?", (inv_id,))
    inv = cursor.fetchone()
    conn.close()
    flash(f"Invoice {inv['invoice_number']} sent electronically to {inv['email']}.", "info")
    return redirect(url_for('invoice_detail', inv_id=inv_id))

@app.route('/invoices/<int:inv_id>/print')
@login_required
def print_invoice(inv_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT i.*, u.name as customer_name, u.email as customer_email, s.subscription_number
        FROM invoices i
        JOIN users u ON i.customer_id = u.id
        LEFT JOIN subscriptions s ON i.subscription_id = s.id
        WHERE i.id = ?
    """, (inv_id,))
    inv = cursor.fetchone()
    if not inv:
        conn.close()
        abort(404)

    if g.user['role'] == 'customer' and inv['customer_id'] != g.user['id']:
        conn.close()
        abort(403)

    cursor.execute("SELECT * FROM invoice_lines WHERE invoice_id = ?", (inv_id,))
    lines = cursor.fetchall()
    conn.close()
    return render_template('invoice_print.html', inv=inv, lines=lines)

# -------------------------------------------------------------
# Payments Registration
# -------------------------------------------------------------
@app.route('/invoices/<int:inv_id>/payment/new', methods=['POST'])
@staff_or_admin_required
def record_payment(inv_id):
    payment_method = request.form.get('payment_method', 'Bank Transfer')
    amount = float(request.form.get('amount', 0.0) or 0.0)
    payment_date = request.form.get('payment_date') or date.today().strftime("%Y-%m-%d")
    notes = request.form.get('notes', '')

    if amount <= 0:
        flash("Payment amount must be greater than zero.", "danger")
        return redirect(url_for('invoice_detail', inv_id=inv_id))

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO payments (invoice_id, payment_method, amount, payment_date, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (inv_id, payment_method, amount, payment_date, notes))

    # Check total payments to see if invoice should automatically move to 'paid'
    cursor.execute("SELECT amount_total FROM invoices WHERE id = ?", (inv_id,))
    inv_total = cursor.fetchone()['amount_total']

    cursor.execute("SELECT COALESCE(SUM(amount), 0.0) as total_paid FROM payments WHERE invoice_id = ?", (inv_id,))
    total_paid = cursor.fetchone()['total_paid']

    if total_paid >= inv_total:
        cursor.execute("UPDATE invoices SET state = 'paid' WHERE id = ?", (inv_id,))

    conn.commit()
    conn.close()

    flash(f"Payment of ${amount:.2f} recorded successfully.", "success")
    return redirect(url_for('invoice_detail', inv_id=inv_id))

# -------------------------------------------------------------
# Customer Self-Service Portal
# -------------------------------------------------------------
@app.route('/portal')
@login_required
def portal():
    customer_id = g.user['id']
    conn = get_db()
    cursor = conn.cursor()

    # Customer Subscriptions
    cursor.execute("""
        SELECT s.*, p.name as plan_name, p.billing_interval,
               (SELECT COALESCE(SUM(amount), 0.0) FROM subscription_lines sl WHERE sl.subscription_id = s.id) as total_amount
        FROM subscriptions s
        JOIN plans p ON s.plan_id = p.id
        WHERE s.customer_id = ?
        ORDER BY s.id DESC
    """, (customer_id,))
    my_subs = cursor.fetchall()

    # Customer Invoices
    cursor.execute("""
        SELECT i.*, s.subscription_number
        FROM invoices i
        LEFT JOIN subscriptions s ON i.subscription_id = s.id
        WHERE i.customer_id = ?
        ORDER BY i.id DESC
    """, (customer_id,))
    my_invoices = cursor.fetchall()

    conn.close()
    return render_template('portal.html', subscriptions=my_subs, invoices=my_invoices)

if __name__ == '__main__':
    conn = get_db()
    conn.close()
    app.run(host='0.0.0.0', port=5000, debug=True)

