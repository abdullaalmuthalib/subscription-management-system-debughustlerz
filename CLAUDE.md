# CLAUDE.md — Subscription Management SaaS (Brightloop-style)

You are the lead engineer on a production-oriented, multi-tenant subscription management platform. Read this file at the start of every session. Work stage by stage. **Never move to the next stage until the current stage's checklist is green (code written, run, and tested).**

Source documents: `Subscription_Management_System.pdf` (business rules) and the master prompt. If they conflict, follow the decisions in "Resolved decisions" below.

---

## 1. Product summary

One platform that runs the whole subscription lifecycle for many independent businesses: products and variants, plans, customers, quotations, subscriptions, automated recurring billing, invoices, payments, taxes, discounts, analytics, real-time notifications, and a customer self-service portal.

Roles: **Super Admin** (platform), **Business Admin**, **Staff**, **Customer**.
Only Business Admin can add staff and create discount rules. Customers see only their own data.

## 2. Stack

- Next.js (App Router), React, TypeScript (strict), Tailwind CSS, shadcn/ui, lucide-react, Recharts
- Node.js, REST route handlers calling a separate domain layer
- PostgreSQL + Prisma (migrations committed), Redis, BullMQ
- Zod for validation (shared client/server), argon2id for passwords
- Vitest (unit/integration), Playwright (e2e), Docker + Docker Compose
- Payments: provider interface with Stripe, Razorpay, PayPal adapters

## 3. Resolved decisions (do not relitigate)

1. `User.email` is globally unique (PDF rule: one email, one account). `Customer` is a per-business record optionally linked to a `User`, so one person can be a customer of several businesses.
2. Password: more than 8 characters, at least one uppercase, one lowercase, one special character. One shared Zod schema, enforced server-side.
3. Money is stored as integer minor units plus ISO currency code. Tax rates are `NUMERIC(9,6)`. No floating-point arithmetic on money, ever. All math goes through `src/server/lib/money.ts`.
4. Variant pricing is data (`ProductVariant.priceAdjustmentMinor`), e.g. Odoo brand = +560. Nothing price-related is hardcoded.
5. Quotations and invoices snapshot prices, tax rates, and discounts at creation/issue time. Later catalog changes never alter them.
6. Super Admin never reads tenant financial data by default; any access is audited.
7. Real-time uses Server-Sent Events fed by Redis pub/sub, emitted from a transactional outbox so only committed events are broadcast.

## 4. Architecture rules

- Layers: `app/api/**` route handlers (thin) → `src/server/domain/**` (business logic) → `src/server/repos/**` (tenant-scoped data access). UI never touches Prisma.
- **Tenant isolation:** every tenant table has `businessId`. Repos require a `TenantContext`; a query without one must not compile. Add Postgres Row-Level Security as a second layer. Every endpoint needs a cross-tenant test.
- **Authorization:** server-side permission checks on every handler via a central `can(actor, action, resource)` function. Never trust client role claims.
- **State machines** live in one domain module each and are the only code allowed to change status fields:
  - Subscription: `DRAFT → QUOTATION → CONFIRMED → ACTIVE → CLOSED`, plus controlled `PAUSED`, `CANCELLED`, `EXPIRED`, `PAST_DUE`.
  - Invoice: `DRAFT → CONFIRMED → PAID`, plus `CANCELLED`, `OVERDUE`, `PARTIALLY_PAID`.
- **Billing engine invariants:**
  - Unique constraint on `(subscriptionId, periodStart, periodEnd)` on invoices.
  - Each job: one transaction, `SELECT … FOR UPDATE SKIP LOCKED` on the subscription, create invoice, redeem discounts, advance `nextBillingAt`, write audit log, enqueue notification.
  - Idempotent, retried with exponential backoff, dead-letter queue visible to Super Admin.
  - Billing dates computed in the business time zone.
  - Scheduler is automatic (repeatable BullMQ job); nobody triggers billing by hand.
- **Discount redemption:** atomic `UPDATE … SET used = used + 1 WHERE used < max_uses` inside the invoice transaction. Expired or exhausted discounts stop applying automatically.
- **Payments:** verified webhooks only; unique `(provider, eventId)` on `WebhookEvent`; allocations via `PaymentAllocation`; never store card data; never simulate success outside test mode; test and live keys separated.
- **Analytics definitions:** MRR normalizes by frequency over ACTIVE subscriptions only (yearly ÷ 12, weekly × 52/12, daily × 365/12). Invoiced, collected, outstanding, MRR, ARR are separate, documented queries.
- **Security:** OWASP baseline, httpOnly + Secure + SameSite cookies, CSRF protection, Redis rate limiting, hashed single-use reset and verification tokens, audit log for sensitive actions, no secrets in client code, generic error responses.
- **Performance:** paginate every list, index every filter, cache dashboard aggregates with short TTL. Target under 2 seconds for normal pages with thousands of subscriptions; verify with a seeded load test.

## 5. Core data model

Identity: `User`, `Business`, `Membership(userId, businessId, role)`, `Customer`, `AuditLog`, `Notification`
Catalog: `Product`, `ProductVariant`, `Plan`, `PlanItem`, `Tax`, `Discount`, `DiscountUsage`
Sales: `QuotationTemplate` (+ lines, validityDays), `Quotation`, `Subscription` (number, status, startDate, expiryDate, paymentTerms, nextBillingAt), `SubscriptionItem`
Billing: `Invoice`, `InvoiceItem`, `BillingJob`
Money in: `Payment` (method, amount, date, note), `PaymentAllocation`, `Refund`, `WebhookEvent`

Plan fields: frequency (daily/weekly/monthly/yearly), minQty, availableFrom/To, autoClose, allowPause, allowEarlyClose, allowRenewal, status.
Key indexes: `(businessId, status, nextBillingAt)`, `(businessId, status, dueDate)`, `(businessId, customerId)` on all child tables.

## 6. UI standards

Stripe/Linear/Vercel-grade, minimal, enterprise. Sophisticated neutral palette plus one accent, light and dark mode, consistent design tokens, refined borders, subtle shadows, strong empty states, restrained motion.
Sidebar: Overview, Products, Plans, Customers, Subscriptions, Quotations, Invoices, Payments, Discounts, Analytics, Team, Settings. Top bar: global search, notifications, workspace selector, profile, quick actions.
Avoid: gradient overload, glassmorphism, emoji icons, fake AI widgets, placeholder buttons. **Every visible control must work against the real backend.** Seed data is development-only and lives under `prisma/seed`.

## 7. Working rules

1. At session start: read this file, `docs/PROGRESS.md`, and run the test suite to confirm the baseline.
2. Design the schema before the logic that uses it. Commit migrations.
3. Write tests alongside code, including failure cases (duplicate billing, concurrent redemption, replayed webhooks, cross-tenant access, invalid transitions).
4. Run lint, typecheck, and tests before declaring a stage done. Fix failures before moving on.
5. No TODO placeholders for important features, no mock arrays as a final data source.
6. Never claim an integration works unless it was configured and tested. Document required credentials in `.env.example`; never fabricate keys.
7. At the end of each stage, update `docs/PROGRESS.md` (done, verified how, known gaps, next step) and commit.
8. If context or time runs out, leave the repo in a working state and record exactly where to resume.

---

## 8. Stage checklist

Mark `[x]` only when code exists, runs, and its tests pass.

### Stage 1 — Foundation
- [ ] Repo scaffold (Next.js, TS strict, Tailwind, shadcn/ui, ESLint, Prettier)
- [ ] Docker Compose: Postgres, Redis, web, worker
- [ ] Prisma schema for all entities above, initial migration, constraints and indexes
- [ ] Env validation (Zod), `.env.example`
- [ ] `money.ts` with unit tests (rounding modes, currencies with 0/2/3 decimals)
- [ ] CI: lint, typecheck, test, migrate check
- [ ] `docs/PROGRESS.md` created

### Stage 2 — Auth and tenancy
- [ ] Register with the password rule, unique email, email verification
- [ ] Login, logout, session management, password reset (hashed, single-use, expiring tokens)
- [ ] Roles and `can()` permission layer, Business Admin-only staff creation
- [ ] TenantContext and tenant-scoped repos, RLS policies
- [ ] Rate limiting on auth endpoints
- [ ] Tests: auth flows, authorization matrix, tenant isolation, brute-force limits

### Stage 3 — Catalog
- [ ] Products and variants CRUD (archive, price adjustment as data)
- [ ] Taxes (inclusive/exclusive, jurisdiction, effective dates)
- [ ] Plans with all lifecycle flags and plan items
- [ ] Discounts (fixed/percent, min amount/qty, dates, max usage, product or subscription scope), admin-only
- [ ] UI pages for each, with search, filter, pagination
- [ ] Tests for each module

### Stage 4 — Customers and sales
- [ ] Customer CRM with search, filters, detail page
- [ ] Quotation templates (validity days), quotations with price snapshot
- [ ] Subscription state machine with backend-validated transitions and per-business numbering
- [ ] Quotation → subscription conversion
- [ ] Tests: every valid and invalid transition, snapshot immutability

### Stage 5 — Billing engine
- [ ] Scheduler and per-subscription jobs, row locking, idempotency
- [ ] Period calculation across frequencies and time zones
- [ ] Invoice generation with tax, discounts, atomic redemption
- [ ] Proration for upgrades and downgrades
- [ ] Retry, dead-letter queue, audit trail
- [ ] Tests: duplicate prevention under concurrency, no skipped cycles, retry safety, discount over-redemption race
- [ ] Load test: 5,000+ due subscriptions

### Stage 6 — Invoices and payments
- [ ] Invoice lifecycle, manual invoices, cancel, confirm, send email, PDF download, print
- [ ] Manual payment recording with allocations and balance updates
- [ ] Provider interface, Stripe/Razorpay/PayPal adapters, verified idempotent webhooks, refunds, partial payments
- [ ] Overdue detection job
- [ ] Tests: webhook replay, signature failure, partial and over-payment, refund

### Stage 7 — Analytics and real-time
- [ ] Dashboard cards, charts, date filters, recent transactions, renewals, overdue, failed payments
- [ ] Correct MRR/ARR/collected/invoiced/outstanding queries with tests against known fixtures
- [ ] CSV exports for customers, subscriptions, invoices, payments
- [ ] Outbox + SSE + notification center
- [ ] Tests: metric accuracy, event delivery

### Stage 8 — Customer portal
- [ ] Subscriptions, history, invoices (PDF), payments, profile, billing info
- [ ] Cancellation requests, plan upgrade/downgrade where the plan allows
- [ ] Tests: a customer can never read another customer's data (every endpoint)

### Stage 9 — Super Admin
- [ ] Business list, suspend/reactivate, platform usage, system health
- [ ] Billing job monitor with failures and retry
- [ ] Audited access rules

### Stage 10 — Hardening and deployment
- [ ] Security review against OWASP checklist, dependency audit
- [ ] Performance pass: verify under 2 seconds on seeded thousands-of-subscriptions data
- [ ] Playwright e2e: signup → plan → quote → subscription → billing → payment → report
- [ ] Health endpoints, structured logging, error monitoring hooks
- [ ] Dockerfiles, worker deployment, migration commands, backup guidance
- [ ] API documentation (OpenAPI), setup guide, deployment guide, env variable docs

---

## 9. Definition of done (whole project)

Renewals never missed, no double charges, invoices accurate and immutable once issued, payments reconciled to invoices, discounts correct and bounded, tenant data private, customers confined to their own data, reports derived from real records, every UI control functional, all tests green.
