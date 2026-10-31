import unittest
import time
from datetime import date, timedelta
from app import app
from models import get_db, validate_password
from seed_data import seed_database
import billing_engine

class BrightloopSystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_database()
        cls.client = app.test_client()
        cls.client.testing = True

    def test_01_password_policy(self):
        # Must be > 8 characters, 1 uppercase, 1 lowercase, 1 special character
        self.assertFalse(validate_password("Short1!")[0])
        self.assertFalse(validate_password("alllowercase123!")[0])
        self.assertFalse(validate_password("ALLUPPERCASE123!")[0])
        self.assertFalse(validate_password("NoSpecialCharacter123")[0])
        self.assertTrue(validate_password("ValidPassword@2026")[0])

    def test_02_authentication_and_rbac(self):
        # 1. Admin login
        res = self.client.post('/login', data={
            'email': 'admin@brightloop.com',
            'password': 'Admin@123456'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Finance & Billing Overview", res.data)

        # 2. Admin can access staff management
        res_staff = self.client.get('/staff')
        self.assertEqual(res_staff.status_code, 200)
        self.assertIn(b"Internal Staff Accounts", res_staff.data)

        # 3. Customer login
        self.client.get('/logout')
        res_cust = self.client.post('/login', data={
            'email': 'billing@acmeretail.com',
            'password': 'Customer@123456'
        }, follow_redirects=True)
        self.assertEqual(res_cust.status_code, 200)
        self.assertIn(b"Customer Self-Service Portal", res_cust.data)

        # 4. Customer blocked from admin staff management
        res_blocked = self.client.get('/staff', follow_redirects=True)
        self.assertIn(b"Access denied", res_blocked.data)

    def test_03_customer_signup_and_portal(self):
        signup_res = self.client.post('/register', data={
            'name': 'New Startup Co',
            'email': 'startup@newco.com',
            'password': 'Startup@2026!',
            'confirm_password': 'Startup@2026!'
        }, follow_redirects=True)
        self.assertEqual(signup_res.status_code, 200)
        self.assertIn(b"Account created successfully", signup_res.data)

    def test_04_product_variants_pricing(self):
        # Verify Odoo brand adds +560 to price
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.sales_price, pv.price_extra
            FROM products p
            JOIN product_variants pv ON pv.product_id = p.id
            WHERE p.name LIKE '%Core ERP%' AND pv.attribute_value LIKE '%Odoo%'
        """)
        row = cursor.fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row['price_extra'], 560.00)
        total_unit_price = row['sales_price'] + row['price_extra']
        self.assertEqual(total_unit_price, 680.00)

    def test_05_automated_billing_and_idempotency(self):
        today_str = date.today().strftime("%Y-%m-%d")
        
        # First billing run: should bill any due active subscription
        invoices_1 = billing_engine.run_recurring_billing(today_str)
        
        # Second billing run on the same date: MUST NOT bill twice (Idempotency guarantee)
        invoices_2 = billing_engine.run_recurring_billing(today_str)
        self.assertEqual(len(invoices_2), 0)

    def test_06_finance_dashboard_performance(self):
        # Must respond in under 2 seconds (2000ms) with full metrics
        self.client.post('/login', data={
            'email': 'admin@brightloop.com',
            'password': 'Admin@123456'
        })
        start_time = time.time()
        res = self.client.get('/dashboard')
        elapsed_sec = time.time() - start_time
        
        self.assertEqual(res.status_code, 200)
        self.assertLess(elapsed_sec, 2.0, "Dashboard must load in under 2 seconds")
        self.assertIn(b"Active Subscriptions", res.data)
        self.assertIn(b"Collected Revenue", res.data)
        self.assertIn(b"Overdue Receivables", res.data)

    def test_07_payment_registration(self):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, amount_total FROM invoices WHERE state = 'confirmed' LIMIT 1")
        inv = cursor.fetchone()
        conn.close()
        
        if inv:
            inv_id = inv['id']
            pay_res = self.client.post(f'/invoices/{inv_id}/payment/new', data={
                'payment_method': 'Bank Transfer',
                'amount': inv['amount_total'],
                'payment_date': date.today().strftime("%Y-%m-%d"),
                'notes': 'Wire ref: TEST-SETTLEMENT-01'
            }, follow_redirects=True)
            self.assertEqual(pay_res.status_code, 200)
            
            # Check invoice is now marked paid
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT state FROM invoices WHERE id = ?", (inv_id,))
            updated_state = cursor.fetchone()['state']
            conn.close()
            self.assertEqual(updated_state, 'paid')

if __name__ == '__main__':
    unittest.main()

