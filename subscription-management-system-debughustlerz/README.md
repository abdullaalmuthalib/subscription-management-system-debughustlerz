# Brightloop Software - Subscription Management & Recurring Billing Platform
> Built for Odoo Hackathon 2026

A unified, full-lifecycle subscription management and recurring billing web application designed to run the digital backbone of **Brightloop Software**.

---

## 🚀 Key Features & Implementation Overview

### 1. User Roles & Security (RBAC)
* **Administrator**: Full system authority — configures products, variants, billing plans, tax rules, discount rules, and creates internal staff accounts.
* **Internal Staff**: Day-to-day operations — builds quotations, manages active customer subscriptions, reviews invoices, and registers payments. Restricted from creating other staff members.
* **Customer Self-Service Portal**: Customers register online, log in, view only their own subscriptions, review invoice history, and print/download invoices without needing to email support.
* **Password Policy**: Strict validation ensuring passwords have more than 8 characters, with at least one uppercase letter, one lowercase letter, and one special character.
* **Password Reset**: Automated secure reset link dispatch mechanism for forgotten credentials.

### 2. Product Catalog & Attribute Variants
* Base products with Name, Type, Sales Price, Cost Price, and Notes.
* **Dynamic Variant Surcharges**: Full support for attribute adjustments (e.g. choosing the **Odoo Brand** variant automatically adds **+$560.00** to the price).

### 3. Flexible Billing Plans & Recurrence Engine
* **Frequencies**: Daily, Weekly, Monthly, and Yearly intervals.
* **Minimum Quantity Constraints**: Minimum purchase/seat requirements per plan.
* **Lifecycle Policies**: Per-plan toggles for Auto-Close on expiration, Allow Pause / Resume, and Allow Renewal.

### 4. Quotations & Subscription Lifecycle
* **Quotation Templates**: Pre-configured plans and line items with validity expiration days (e.g. valid for 30 days) to eliminate repetitive quotation drafting.
* **Full State Machine**:
  `Draft` &rarr; `Quotation` &rarr; `Confirmed` &rarr; `Active` &rarr; `Closed` (with `Paused` state support).

### 5. Automated Recurring Billing ("Billing Day")
* **Zero Manual Invoicing**: Automated batch engine scans active subscriptions due on or before billing day and generates fully populated draft/confirmed invoices.
* **Automatic Tax Engine**: Calculates line taxes according to admin-defined rates (e.g. VAT 10%, Sales Tax 8%).
* **Idempotency Guarantee**: Subscriptions are never billed twice for the same billing cycle date, and no due subscriptions are skipped.
* **Invoice Actions**: Confirm, Cancel, Send via email, and Print clean PDF-ready statements.

### 6. Discount & Promotional Rules Engine
* Admin-controlled rules with Fixed Amount ($) or Percentage (%) discounts.
* Threshold conditions: Minimum quantity of seats or minimum purchase value.
* Validity date ranges and usage caps (`usage_count` automatically decremented per application).
* Scope: Applied to a specific product or the whole subscription.

### 7. Payments & Collections Tracking
* Payment logging against specific invoices: Payment Method, Date, Amount, and Bank Statement Memo/Reference.
* Tracks settled receipts and flags overdue invoices for collection follow-up.

### 8. Finance Lead Real-Time Dashboard
* Real-time metrics: Active Subscriptions count, Total Revenue Collected, Amount Still Owed, and Overdue Invoices requiring action.
* High performance: Sub-second response time (&lt; 20ms) fulfilling the &lt; 2-second constraint.

---

## 🔑 Demo Accounts & Credentials

| Role | Email | Password | Access Scope |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin@brightloop.com` | `Admin@123456` | Full system control |
| **Internal Staff** | `sarah.staff@brightloop.com` | `Staff@123456` | Operations & Billing |
| **Customer 1 (Acme)** | `billing@acmeretail.com` | `Customer@123456` | Customer Portal |
| **Customer 2 (Global Tech)** | `finance@globaltech.com` | `Customer@123456` | Customer Portal |

---

## 🛠️ How to Run

### 1. Launch the Application
Run the Python script directly or double-click `run.bat`:
```powershell
python run.py
```
Open your web browser and navigate to:
```
http://127.0.0.1:5000
```

### 2. Run Automated Verification Tests
A full test suite is included covering RBAC, password policies, variant pricing, recurring billing idempotency, and finance performance:
```powershell
python test_system.py
```
