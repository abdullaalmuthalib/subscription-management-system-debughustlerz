from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import re

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super_secret_hackathon_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///brightloop.db'
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ==========================================
# DATABASE MODELS
# ==========================================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='customer')

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    sales_price = db.Column(db.Float, nullable=False)
    cost_price = db.Column(db.Float, nullable=False)

class Plan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    billing_period = db.Column(db.String(20), nullable=False) # monthly, yearly, lifetime
    price = db.Column(db.Float, nullable=False)
    product = db.relationship('Product', backref='plans')

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('plan.id'), nullable=False)
    status = db.Column(db.String(20), default='Active')
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    expiry_date = db.Column(db.DateTime, nullable=True) # Nullable for lifetime
    plan = db.relationship('Plan', backref='subscriptions')

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscription.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    tax = db.Column(db.Float, default=0.0)
    discount_applied = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='Confirmed')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_hidden = db.Column(db.Boolean, default=False)

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('plan.id'), nullable=False)
    plan = db.relationship('Plan', backref='cart_items')

# ==========================================
# AUTHENTICATION ROUTES
# ==========================================
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if len(password) < 8 or not re.search(r"[A-Z]", password) or not re.search(r"[a-z]", password) or not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            flash('Password must be 8+ chars with uppercase, lowercase, and a special character.', 'danger')
            return redirect(url_for('register'))
            
        if User.query.filter_by(email=email).first():
            flash('Email already exists.', 'danger')
            return redirect(url_for('register'))
            
        new_user = User(email=email, password_hash=generate_password_hash(password), role='customer')
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials. Please try again.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ==========================================
# DASHBOARD & STORE ROUTES
# ==========================================
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/store')
@login_required
def store():
    plans = Plan.query.all()
    return render_template('store.html', plans=plans)

@app.route('/dashboard')
@login_required
def dashboard():
    plans = Plan.query.all() 
    
    if current_user.role == 'admin':
        subs = Subscription.query.all()
        invoices = Invoice.query.all()
        paid_invoices = [i for i in invoices if i.status == 'Paid']
        total_revenue = sum((i.amount + i.tax) for i in paid_invoices)
        return render_template('admin_dashboard.html', subs=subs, invoices=invoices, plans=plans, revenue=total_revenue)
    else:
        subs = Subscription.query.filter_by(customer_id=current_user.id).all()
        sub_ids = [s.id for s in subs]
        invoices = Invoice.query.filter(Invoice.subscription_id.in_(sub_ids), Invoice.is_hidden == False).order_by(Invoice.created_at.desc()).all()
        unpaid_invoices = [i for i in invoices if i.status == 'Confirmed']
        pending_balance = sum((i.amount + i.tax) for i in unpaid_invoices)
        cart_count = CartItem.query.filter_by(user_id=current_user.id).count()
        return render_template('customer_dashboard.html', subs=subs, invoices=invoices, plans=plans, pending_balance=pending_balance, cart_count=cart_count)

# ==========================================
# CART & SUBSCRIPTION ROUTES
# ==========================================
@app.route('/add_to_cart/<int:plan_id>', methods=['POST'])
@login_required
def add_to_cart(plan_id):
    if current_user.role == 'admin':
        flash('Admins cannot buy subscriptions.', 'warning')
        return redirect(url_for('store'))
        
    existing = CartItem.query.filter_by(user_id=current_user.id, plan_id=plan_id).first()
    if existing:
        flash('Item is already in your cart.', 'info')
    else:
        item = CartItem(user_id=current_user.id, plan_id=plan_id)
        db.session.add(item)
        db.session.commit()
        flash('Added to cart successfully!', 'success')
    return redirect(url_for('store'))

@app.route('/cart')
@login_required
def view_cart():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = sum(item.plan.price for item in cart_items)
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/remove_from_cart/<int:item_id>', methods=['POST'])
@login_required
def remove_from_cart(item_id):
    item = CartItem.query.get_or_404(item_id)
    if item.user_id == current_user.id:
        db.session.delete(item)
        db.session.commit()
        flash('Item removed from cart.', 'success')
    return redirect(url_for('view_cart'))

@app.route('/checkout_cart', methods=['POST'])
@login_required
def checkout_cart():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not cart_items:
        return redirect(url_for('view_cart'))

    promo_code = request.form.get('promo_code', '').strip().upper()
    discount_rate = 0.0
    if promo_code == 'SAVE20': discount_rate = 0.20
    elif promo_code == 'SUPER70': discount_rate = 0.70
    elif promo_code != '': flash('Invalid promo code. Ignored.', 'warning')

    for item in cart_items:
        # Handle Expiry Logic
        if item.plan.billing_period == 'lifetime':
            expiry = None # No expiry for lifetime
        elif item.plan.billing_period == 'yearly':
            expiry = datetime.utcnow() + timedelta(days=365)
        else:
            expiry = datetime.utcnow() + timedelta(days=30)

        sub = Subscription(customer_id=current_user.id, plan_id=item.plan_id, status='Active', expiry_date=expiry)
        db.session.add(sub)
        db.session.commit()
        
        discount_amount = item.plan.price * discount_rate
        final_price = item.plan.price - discount_amount
        tax_amount = final_price * 0.18
        
        inv = Invoice(subscription_id=sub.id, amount=final_price, tax=tax_amount, discount_applied=discount_amount, status='Confirmed')
        db.session.add(inv)
        db.session.delete(item)

    db.session.commit()
    flash('Subscriptions activated! Please pay your invoices.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/renew/<int:sub_id>', methods=['POST'])
@login_required
def renew_subscription(sub_id):
    sub = Subscription.query.get_or_404(sub_id)
    if sub.customer_id != current_user.id and current_user.role != 'admin':
        return "Unauthorized", 403
    
    if sub.plan.billing_period == 'lifetime':
        flash('Lifetime plans do not need renewal.', 'info')
        return redirect(url_for('dashboard'))

    # Calculate Renewal Period
    if sub.plan.billing_period == 'yearly':
        sub.expiry_date = sub.expiry_date + timedelta(days=365)
    else:
        sub.expiry_date = sub.expiry_date + timedelta(days=30)
        
    sub.status = 'Active'
    
    tax_amount = sub.plan.price * 0.18
    inv = Invoice(subscription_id=sub.id, amount=sub.plan.price, tax=tax_amount, status='Confirmed')
    db.session.add(inv)
    db.session.commit()
    
    flash(f'Subscription for {sub.plan.product.name} renewed!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/cancel_subscription/<int:sub_id>', methods=['POST'])
@login_required
def cancel_subscription(sub_id):
    sub = Subscription.query.get_or_404(sub_id)
    
    # Security check: ensure the user owns this subscription
    if sub.customer_id != current_user.id:
        return "Unauthorized", 403
        
    # Change status to 'Cancelled'. The dashboard query only looks for 'Active', so it will disappear.
    sub.status = 'Cancelled'
    db.session.commit()
    
    flash(f'Subscription for {sub.plan.product.name} has been cancelled.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/clear_history', methods=['POST'])
@login_required
def clear_history():
    subs = Subscription.query.filter_by(customer_id=current_user.id).all()
    sub_ids = [s.id for s in subs]
    invoices = Invoice.query.filter(Invoice.subscription_id.in_(sub_ids)).all()
    for inv in invoices:
        inv.is_hidden = True
    db.session.commit()
    flash('Billing history cleared from your view.', 'success')
    return redirect(url_for('dashboard'))

# ==========================================
# ADMIN & PAYMENT ROUTES
# ==========================================
@app.route('/admin/create_plan', methods=['POST'])
@login_required
def create_plan():
    if current_user.role != 'admin': return "Unauthorized", 403
    name = request.form.get('name')
    price = float(request.form.get('price'))
    billing = request.form.get('billing')
    
    prod = Product(name=name, sales_price=price, cost_price=price*0.4)
    db.session.add(prod)
    db.session.commit()
    
    plan = Plan(product_id=prod.id, billing_period=billing, price=price)
    db.session.add(plan)
    db.session.commit()
    flash('New Plan Created Successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/checkout/<int:invoice_id>')
@login_required
def checkout(invoice_id):
    inv = Invoice.query.get_or_404(invoice_id)
    if inv.status == 'Paid':
        flash('This invoice is already paid.', 'info')
        return redirect(url_for('dashboard'))
    return render_template('checkout.html', inv=inv)

@app.route('/process_payment/<int:invoice_id>', methods=['POST'])
@login_required
def process_payment(invoice_id):
    inv = Invoice.query.get_or_404(invoice_id)
    inv.status = 'Paid'
    db.session.commit()
    flash('Payment Successful! Thank you for your business.', 'success')
    return redirect(url_for('dashboard'))

# ==========================================
# DATABASE SEEDING
# ==========================================
with app.app_context():
    db.create_all()
    if not User.query.filter_by(email='admin@brightloop.com').first():
        admin = User(email='admin@brightloop.com', password_hash=generate_password_hash('Admin@1234'), role='admin')
        db.session.add(admin)
        db.session.commit()
    
    if not Product.query.first():
        # Seeding with mixed billing periods
        mock_plans = [
            {"name": "Netflix Premium", "price": 649.0, "period": "monthly"},
            {"name": "Spotify Premium", "price": 119.0, "period": "monthly"},
            {"name": "YouTube Premium", "price": 129.0, "period": "monthly"},
            {"name": "Meta Verified", "price": 699.0, "period": "monthly"},
            {"name": "Amazon Prime", "price": 1499.0, "period": "yearly"},
            {"name": "Disney+ Hotstar", "price": 1499.0, "period": "yearly"},
            {"name": "Adobe Creative Cloud", "price": 1675.0, "period": "monthly"},
            {"name": "Canva Pro", "price": 3999.0, "period": "yearly"},
            {"name": "ChatGPT Plus", "price": 1999.0, "period": "monthly"},
            {"name": "Microsoft 365", "price": 4899.0, "period": "yearly"},
            {"name": "Apple Music", "price": 99.0, "period": "monthly"},
            {"name": "LinkedIn Premium", "price": 1200.0, "period": "monthly"},
            {"name": "Lifetime VPN Access", "price": 4999.0, "period": "lifetime"},
            {"name": "Lifetime Cloud Storage", "price": 9999.0, "period": "lifetime"},
            {"name": "Coursera Plus", "price": 4000.0, "period": "yearly"}
        ]
        for mp in mock_plans:
            prod = Product(name=mp["name"], sales_price=mp["price"], cost_price=mp["price"]*0.6)
            db.session.add(prod)
            db.session.commit()
            plan = Plan(product_id=prod.id, billing_period=mp["period"], price=mp["price"])
            db.session.add(plan)
            db.session.commit()

if __name__ == '__main__':
    app.run(debug=True)