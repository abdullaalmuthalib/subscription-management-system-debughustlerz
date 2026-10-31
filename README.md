# ⚡ Brightloop — Subscription Management Platform

> A unified, standalone web platform built for **Brightloop Software** for the **Odoo Hackathon 2026**, adhering strictly to the problem statement and styled with the maker aesthetic of [TinkerHub.org](https://tinkerhub.org).

---

## 🎯 The Hard Parts — Solved & Tested

### 1. 🛡️ Idempotent Billing Engine (“Nothing billed twice or skipped”)
- The invoice generator scans all active/confirmed subscriptions due as of the target billing date.
- It enforces strict idempotency by inspecting existing records for the same `(subscription_id, billing_period_start)`.
- Re-running the billing run repeatedly returns `0 new invoices created` and reports the count of skipped cycles that were already billed.
- Accurately computes billing intervals (`daily`, `weekly`, `monthly`, `yearly`), advances `next_billing_date`, and auto-closes subscriptions if `auto_close = 1` and the expiry date is reached.

### 2. 👥 Multi-Role Access Control across 3 Portals
- **Admin**: Full control over products, Odoo variants, plans, discount rules, tax policies, and is the **only role permitted to onboard internal staff**.
- **Internal Staff**: Day-to-day operations — builds quotes, manages subscriptions, executes billing runs, records payments, and tracks overdue receivables.
- **Customer Portal**: Dedicated self-service view where customers see **only their own** subscriptions and invoices, review quotes, record payments, and pause/resume/renew eligible plans.
- Includes a 1-click **Persona Switcher** in the top navigation to test all roles.

### 3. 🔄 The Three State Machines
1. **Subscription State Machine**:
   - `Draft` &rarr; `Quotation` &rarr; `Confirmed` &rarr; `Active` &rarr; `Closed`.
   - Supports `Paused` &harr; `Active` and `Renew` (+1 year), strictly enforcing plan policy flags (`allow_pause`, `allow_close_early`, `allow_renew`).
2. **Invoice State Machine**:
   - `Draft` &rarr; `Confirmed` &rarr; `Paid` (with `Cancelled` and `Sent` email confirmation tracking).
   - Partially or fully paid reconciliation automatically updates status to `Paid`.
3. **Plan Policy Rules**:
   - Configures interval, auto-close behavior, early closure allowances, pause allowances, and renewal permissions.

### 4. 🏷️ Automatic Discount Rules Engine
- Only the Admin can create discount rules (fixed amount or percentage, minimum spend/quantity, start/end dates, and maximum usage limits).
- Target scope: applies to **whole subscriptions** or **specific products**.
- When applied, automatically deducts from the next invoice without manual calculation, updates the `times_used` counter, and automatically ceases once exhausted or expired.

### 5. ⚡ Performance & Reporting at Scale (< 2s SLA Rule)
- Problem requirement: *"With thousands of subscriptions on the books, every page should still respond in under two seconds."*
- Powered by a local SQLite engine running in **WAL mode** with compound indexes (`idx_subs_status_date`, `idx_invoices_sub_period`, etc.).
- Includes a dedicated **Scale Benchmark Suite** that seeds 5,000 realistic subscriptions in **~260ms** and aggregates MRR, ARR, and financial metrics in **~760ms** (far exceeding the 2,000ms SLA).

---

## 🎨 TinkerHub.org Design System
- **Maker Visual Ethos**: High-contrast neo-brutalist cards with crisp 2px dark borders (`border-2 border-zinc-900`), tactile press reactions (`neo-btn`), and elevated solid drop shadows (`shadow-[3px_3px_0px_#121316]`).
- **Signature Palette**:
  - 🟡 **Tinker Yellow** (`#F4C761`) — Primary interactive buttons and highlights.
  - 🟢 **Maker Lime** (`#C3FF16`) — Tags, sticker badges, and benchmark status.
  - 🟣 **Electric Purple** (`#5E1DB0` / `#884BD4`) — Operations chips and status indicators.
  - 🌿 **Mint Green** (`#3CD377`) — Paid status and revenue figures.
  - 🏛️ **Canvas Sand** (`#F8F7F4`) — Warm maker canvas with subtle dot grid.

---

## 🏃 Running the Application

### 1. Start the Web App Server
```bash
node server/index.js
```
The server serves both the Express REST API and the compiled React frontend at **`http://localhost:5000`**.

### 2. Run the Automated Verification Suite
We have included an end-to-end Python test script verifying all 8 requirements:
```bash
python test_system.py
```

### 3. Pre-Loaded Test Accounts
| Role | Email | Password |
|---|---|---|
| **Admin** | `admin@brightloop.com` | `Admin@1234` |
| **Internal Staff** | `staff@brightloop.com` | `Staff@1234` |
| **Customer** | `elena@novatech.co` | `Cust@1234` |
| **Customer** | `priya@tinkerlabs.org` | `Cust@1234` |

*(You can also switch personas instantly using the top right account dropdown!)*
