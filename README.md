# ⚡ Brightloop — Subscription Management System

> Built for the **Odoo Hackathon 2026** 🚀  
> A simple, unified platform to manage, buy, and track all your digital subscriptions in one place.

---

## 🌟 What is Brightloop?

Managing multiple recurring subscriptions—from streaming platforms to SaaS tools—often leads to fragmented billing and surprise charges. **Brightloop** fixes this by giving users a clean, centralized store to browse services, select plans (monthly, yearly, or lifetime), and manage all active subscriptions from a single dashboard.

---

## ✨ Key Features

* **Single Storefront:** Browse popular services like Netflix, Spotify, ChatGPT Plus, Canva Pro, and Adobe Creative Cloud with clear, transparent pricing.
* **Flexible Billing Plans:** Supports monthly, yearly, and lifetime recurring models.
* **Unified Shopping Cart:** Add multiple services to your cart, apply promo codes, and handle taxes seamlessly before checking out.
* **Smart Billing Dashboard:** View total pending balances, track detailed invoice histories (`#INV-1`, `#INV-2`, etc.), and handle payments with one click.
* **Mock Payment Gateway:** Fully simulated checkout flow—complete with card detail validation, bank communication processing, and instant subscription activation.
* **Real-time Status Updates:** Invoices transition instantly from `Due` to `Paid`, automatically putting new subscriptions into your active library.

---

## 🛠️ Tech Stack

* **Frontend / UI:** HTML5, CSS3, JavaScript (Clean & Responsive UI)
* **Backend:** Python (Flask / Odoo API integration layer)
* **Database:** PostgreSQL / SQLite
* **Deployment:** Render (`onrender.com`)

---

## 🔄 User Workflow

1. **Sign In:** Log in to your personal dashboard at `/login`.
2. **Explore & Select:** Browse the **Unified Subscription Store** and add desired services to your cart.
3. **Review Cart:** Check your subtotal, calculated taxes (18% GST), and apply any discount promo codes.
4. **Checkout:** Complete payment via the secure card processing pop-up.
5. **Manage & Track:** Once paid, your subscription activates immediately and displays under **Active Subscriptions** in your dashboard.

---

## 🚀 Live Demo

Check out the deployed application on Render:  
👉 **[https://subscription-management-system-b7bb.onrender.com](https://subscription-management-system-b7bb.onrender.com)**

## Demo Video Explanation 
👉 https://drive.google.com/file/d/1ueWLZMR81TRZsEtZRD3vPNTV-85XTp3q/view?usp=drivesdk

---

## 💻 Local Setup & Installation

If you'd like to run Brightloop locally:

```bash
# Clone the repository
git clone [https://github.com/your-username/subscription-management-system.git](https://github.com/your-username/subscription-management-system.git)

# Navigate into the project directory
cd subscription-management-system

# Install required dependencies
pip install -r requirements.txt

# Run the app
python app.py
