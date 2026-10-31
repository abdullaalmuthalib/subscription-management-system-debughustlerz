from datetime import datetime, date, timedelta
import calendar
from models import get_db

def add_interval(orig_date, interval):
    """
    Compute next billing date based on plan interval:
    daily, weekly, monthly, yearly
    """
    if isinstance(orig_date, str):
        orig_date = datetime.strptime(orig_date, "%Y-%m-%d").date()

    if interval == 'daily':
        return orig_date + timedelta(days=1)
    elif interval == 'weekly':
        return orig_date + timedelta(weeks=1)
    elif interval == 'monthly':
        # Add 1 month preserving day where possible
        year = orig_date.year
        month = orig_date.month + 1
        if month > 12:
            month = 1
            year += 1
        max_days = calendar.monthrange(year, month)[1]
        day = min(orig_date.day, max_days)
        return date(year, month, day)
    elif interval == 'yearly':
        try:
            return orig_date.replace(year=orig_date.year + 1)
        except ValueError:
            # Leap year handling for Feb 29
            return orig_date + (date(orig_date.year + 1, 3, 1) - date(orig_date.year, 3, 1))
    return orig_date + timedelta(days=30)

def generate_invoice_number(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM invoices;")
    count = cursor.fetchone()['count'] + 1
    current_year = date.today().year
    return f"INV-{current_year}-{count:04d}"

def is_discount_applicable(discount, total_untaxed, total_quantity, product_id=None):
    today = date.today()
    start_d = datetime.strptime(discount['start_date'], "%Y-%m-%d").date()
    if today < start_d:
        return False
    if discount['end_date']:
        end_d = datetime.strptime(discount['end_date'], "%Y-%m-%d").date()
        if today > end_d:
            return False
    if discount['max_usage'] is not None and discount['usage_count'] >= discount['max_usage']:
        return False
    if discount['min_purchase'] and total_untaxed < discount['min_purchase']:
        return False
    if discount['min_quantity'] and total_quantity < discount['min_quantity']:
        return False
    if discount['scope'] == 'product':
        if product_id is None or discount['product_id'] != product_id:
            return False
    return True

def run_recurring_billing(target_date=None):
    """
    Executes automated recurring billing cycle.
    Idempotent: Never bills twice for the same billing cycle date, never skips.
    """
    if target_date is None:
        target_date = date.today()
    elif isinstance(target_date, str):
        target_date = datetime.strptime(target_date, "%Y-%m-%d").date()

    conn = get_db()
    cursor = conn.cursor()

    # Find all active subscriptions due on or before target_date
    cursor.execute("""
        SELECT s.*, p.billing_interval, p.auto_close
        FROM subscriptions s
        JOIN plans p ON s.plan_id = p.id
        WHERE s.state = 'active' AND s.next_billing_date <= ?
    """, (target_date.strftime("%Y-%m-%d"),))
    subscriptions_due = cursor.fetchall()

    invoices_generated = []

    for sub in subscriptions_due:
        sub_id = sub['id']
        sub_num = sub['subscription_number']
        customer_id = sub['customer_id']
        cycle_date = sub['next_billing_date']

        # Idempotency check: has an invoice already been generated for this subscription on this cycle date?
        cursor.execute("""
            SELECT id FROM invoices 
            WHERE subscription_id = ? AND billing_cycle_date = ?
        """, (sub_id, cycle_date))
        existing_invoice = cursor.fetchone()
        if existing_invoice:
            # Advance billing date if stuck
            next_date = add_interval(cycle_date, sub['billing_interval'])
            cursor.execute("UPDATE subscriptions SET next_billing_date = ? WHERE id = ?", 
                           (next_date.strftime("%Y-%m-%d"), sub_id))
            conn.commit()
            continue

        # Check expiry date for auto-close plans
        if sub['expiry_date']:
            exp_d = datetime.strptime(sub['expiry_date'], "%Y-%m-%d").date()
            if target_date >= exp_d and sub['auto_close']:
                cursor.execute("UPDATE subscriptions SET state = 'closed' WHERE id = ?", (sub_id,))
                conn.commit()
                continue

        # Fetch subscription lines
        cursor.execute("""
            SELECT sl.*, p.name as product_name, pv.attribute_name, pv.attribute_value,
                   pv.price_extra, tr.rate as tax_rate, tr.name as tax_name
            FROM subscription_lines sl
            JOIN products p ON sl.product_id = p.id
            LEFT JOIN product_variants pv ON sl.variant_id = pv.id
            LEFT JOIN tax_rules tr ON sl.tax_rule_id = tr.id
            WHERE sl.subscription_id = ?
        """, (sub_id,))
        lines = cursor.fetchall()
        if not lines:
            continue

        # Check discount rule linked to subscription
        discount = None
        if sub['discount_rule_id']:
            cursor.execute("SELECT * FROM discount_rules WHERE id = ?", (sub['discount_rule_id'],))
            discount = cursor.fetchone()

        # Calculate totals
        sub_total_qty = sum(line['quantity'] for line in lines)
        raw_untaxed = sum(line['unit_price'] * line['quantity'] for line in lines)

        # Calculate line items & line-level discounts
        invoice_lines_data = []
        accumulated_untaxed = 0.0
        accumulated_tax = 0.0
        total_discount = 0.0

        for line in lines:
            line_base_total = line['unit_price'] * line['quantity']
            line_disc = 0.0

            # Line-level discount if discount rule scope is 'product'
            if discount and discount['scope'] == 'product' and is_discount_applicable(discount, raw_untaxed, sub_total_qty, line['product_id']):
                if discount['discount_type'] == 'percentage':
                    line_disc = (line_base_total * discount['value']) / 100.0
                else:
                    line_disc = min(discount['value'], line_base_total)

            effective_line_untaxed = max(0.0, line_base_total - line_disc)
            tax_rate = line['tax_rate'] or 0.0
            tax_for_line = (effective_line_untaxed * tax_rate) / 100.0
            line_final_subtotal = effective_line_untaxed + tax_for_line

            desc = line['product_name']
            if line['attribute_name'] and line['attribute_value']:
                desc += f" ({line['attribute_name']}: {line['attribute_value']})"

            invoice_lines_data.append({
                'product_id': line['product_id'],
                'variant_id': line['variant_id'],
                'description': desc,
                'quantity': line['quantity'],
                'unit_price': line['unit_price'],
                'tax_rate': tax_rate,
                'discount_amount': line_disc,
                'subtotal': line_final_subtotal
            })

            accumulated_untaxed += effective_line_untaxed
            accumulated_tax += tax_for_line
            total_discount += line_disc

        # Whole-subscription level discount
        if discount and discount['scope'] == 'subscription' and is_discount_applicable(discount, raw_untaxed, sub_total_qty):
            if discount['discount_type'] == 'percentage':
                sub_disc = (accumulated_untaxed * discount['value']) / 100.0
            else:
                sub_disc = min(discount['value'], accumulated_untaxed)
            total_discount += sub_disc
            accumulated_untaxed = max(0.0, accumulated_untaxed - sub_disc)
            # Recompute tax proportionally
            if raw_untaxed > 0:
                accumulated_tax = (accumulated_untaxed * (accumulated_tax / raw_untaxed))

        total_amount = accumulated_untaxed + accumulated_tax

        # Generate unique invoice reference
        inv_num = generate_invoice_number(conn)

        # Payment terms mapping
        due_days = 0
        if sub['payment_terms'] == '15 Days':
            due_days = 15
        elif sub['payment_terms'] == '30 Days':
            due_days = 30
        due_d = target_date + timedelta(days=due_days)

        # Insert Invoice header
        cursor.execute("""
            INSERT INTO invoices (
                invoice_number, subscription_id, customer_id, invoice_date, due_date,
                amount_untaxed, amount_tax, amount_discount, amount_total, state, billing_cycle_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?)
        """, (
            inv_num, sub_id, customer_id, target_date.strftime("%Y-%m-%d"),
            due_d.strftime("%Y-%m-%d"), accumulated_untaxed, accumulated_tax,
            total_discount, total_amount, cycle_date
        ))
        invoice_id = cursor.lastrowid

        # Insert Invoice Lines
        for il in invoice_lines_data:
            cursor.execute("""
                INSERT INTO invoice_lines (
                    invoice_id, product_id, variant_id, description, quantity,
                    unit_price, tax_rate, discount_amount, subtotal
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                invoice_id, il['product_id'], il['variant_id'], il['description'],
                il['quantity'], il['unit_price'], il['tax_rate'], il['discount_amount'],
                il['subtotal']
            ))

        # If discount was used, increment usage_count
        if discount and (total_discount > 0):
            cursor.execute("UPDATE discount_rules SET usage_count = usage_count + 1 WHERE id = ?", (discount['id'],))

        # Advance next billing date
        next_billing = add_interval(cycle_date, sub['billing_interval'])
        cursor.execute("UPDATE subscriptions SET next_billing_date = ? WHERE id = ?",
                       (next_billing.strftime("%Y-%m-%d"), sub_id))

        invoices_generated.append(inv_num)

    conn.commit()
    conn.close()
    return invoices_generated

