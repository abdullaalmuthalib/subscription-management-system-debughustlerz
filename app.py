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
    billing_period = db.Column(db.String(20), nullable=False) 
    price = db.Column(db.Float, nullable=False)
    product = db.relationship('Product', backref='plans')

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('plan.id'), nullable=False)
    status = db.Column(db.String(20), default='Active')
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    expiry_date = db.Column(db.DateTime)
    plan = db.relationship('Plan', backref='subscriptions')

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscription.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    tax = db.Column(db.Float, default=0.0)
    discount_applied = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='Confirmed')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
# DASHBOARD & CORE LOGIC
# ==========================================
@app.route('/')
def home():
    return redirect(url_for('login'))

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
        invoices = Invoice.query.filter(Invoice.subscription_id.in_(sub_ids)).all()
        
        unpaid_invoices = [i for i in invoices if i.status == 'Confirmed']
        pending_balance = sum((i.amount + i.tax) for i in unpaid_invoices)
        
        return render_template('customer_dashboard.html', subs=subs, invoices=invoices, plans=plans, pending_balance=pending_balance)

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

@app.route('/subscribe/<int:plan_id>', methods=['POST'])
@login_required
def subscribe(plan_id):
    plan = Plan.query.get_or_404(plan_id)
    promo_code = request.form.get('promo_code', '').strip().upper()
    
    discount_amount = 0.0
    if promo_code == 'SAVE20':
        discount_amount = plan.price * 0.20
        flash('Promo code SAVE20 applied! You got 20% off.', 'success')
    elif promo_code == 'SUPER70':
        discount_amount = plan.price * 0.70
        flash('VIP Promo code SUPER70 applied! You got 70% off.', 'success')
    elif promo_code != '':
        flash('Invalid promo code.', 'danger')

    expiry = datetime.utcnow() + timedelta(days=30) 
    sub = Subscription(customer_id=current_user.id, plan_id=plan.id, status='Active', expiry_date=expiry)
    db.session.add(sub)
    db.session.commit()
    
    final_price = plan.price - discount_amount
    tax_amount = final_price * 0.18 
    inv = Invoice(subscription_id=sub.id, amount=final_price, tax=tax_amount, discount_applied=discount_amount, status='Confirmed')
    db.session.add(inv)
    db.session.commit()
    
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
    # Here you would normally integrate Stripe/Razorpay. 
    # For the hackathon MVP, we simulate a successful payment.
    inv.status = 'Paid'
    db.session.commit()
    flash('Payment Successful! Thank you for your business.', 'success')
    return redirect(url_for('dashboard'))

# Initialize Database
with app.app_context():
    db.create_all()
    if not User.query.filter_by(email='admin@brightloop.com').first():
        admin = User(email='admin@brightloop.com', password_hash=generate_password_hash('Admin@1234'), role='admin')
        db.session.add(admin)
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True)