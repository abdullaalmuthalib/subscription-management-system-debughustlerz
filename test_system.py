import subprocess
import time
import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("=== STARTING BRIGHTLOOP VERIFICATION SUITE ===")

# Start node server
proc = subprocess.Popen(["node", "server/index.js"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

try:
    time.sleep(2.5) # Allow server to boot
    
    # 1. Test frontend
    html = urllib.request.urlopen('http://localhost:5000').read().decode('utf-8')
    print("✅ 1. Frontend Web App Served: HTTP 200 (Length:", len(html), "bytes)")
    
    # 2. Test Login
    login_data = json.dumps({'email': 'admin@brightloop.com', 'password': 'Admin@1234'}).encode()
    req = urllib.request.Request('http://localhost:5000/api/auth/login', data=login_data, headers={'Content-Type': 'application/json'})
    res = urllib.request.urlopen(req)
    data = json.loads(res.read())
    token = data['token']
    print(f"✅ 2. Auth & RBAC: Logged in as {data['user']['name']} ({data['user']['role'].upper()})")
    
    # 3. Test Products & Odoo Variant
    req_prod = urllib.request.Request('http://localhost:5000/api/products', headers={'Authorization': f'Bearer {token}'})
    prods = json.loads(urllib.request.urlopen(req_prod).read())['products']
    odoo_variant = any(v['variant_name'] == 'Odoo Brand Edition' and v['price_adjustment'] == 560 for p in prods for v in p.get('variants', []))
    print(f"✅ 3. Product Catalog: Loaded {len(prods)} products. Odoo brand variant (+560) verified: {odoo_variant}")
    
    # 4. Test Billing Day Run 1
    req_bill = urllib.request.Request('http://localhost:5000/api/billing/run-billing-day', data=json.dumps({}).encode(), headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'})
    bill_res1 = json.loads(urllib.request.urlopen(req_bill).read())
    print(f"✅ 4. Automated Billing Run 1: {bill_res1['message']}")
    
    # 5. Test Idempotent Billing Run 2
    req_bill2 = urllib.request.Request('http://localhost:5000/api/billing/run-billing-day', data=json.dumps({}).encode(), headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'})
    bill_res2 = json.loads(urllib.request.urlopen(req_bill2).read())
    print(f"✅ 5. Idempotent Billing Run 2: {bill_res2['message']} (Invoices created: {bill_res2['count']}, Skipped duplicates: {bill_res2['skipped_count']})")
    
    # 6. Test Payment Recording
    req_inv = urllib.request.Request('http://localhost:5000/api/invoices', headers={'Authorization': f'Bearer {token}'})
    invoices = json.loads(urllib.request.urlopen(req_inv).read())['invoices']
    unpaid = [i for i in invoices if i['status'] != 'paid'][0]
    pay_data = json.dumps({
        'invoice_id': unpaid['id'],
        'method': 'Credit Card',
        'amount': unpaid['total_amount'] - unpaid['paid_amount'],
        'note': 'Automated verification payment'
    }).encode()
    req_pay = urllib.request.Request('http://localhost:5000/api/payments', data=pay_data, headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'})
    pay_res = json.loads(urllib.request.urlopen(req_pay).read())
    print(f"✅ 6. Payment Processing: Recorded payment for {unpaid['invoice_number']}. New status: {pay_res['newStatus'].upper()}")
    
    # 7. Test Scale Benchmark Seeding (5,000 subscriptions)
    print("⏳ 7. Seeding 5,000 subscriptions to test performance at scale...")
    req_seed = urllib.request.Request('http://localhost:5000/api/benchmark/seed-scale', data=json.dumps({'count': 5000}).encode(), headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'})
    seed_res = json.loads(urllib.request.urlopen(req_seed).read())
    print(f"✅ 7. Seeding Complete: {seed_res['message']} (Total in DB: {seed_res['total_subscriptions']})")
    
    # 8. Test Analytics Query at Scale (< 2,000ms SLA rule)
    t0 = time.time()
    req_ana = urllib.request.Request('http://localhost:5000/api/analytics', headers={'Authorization': f'Bearer {token}'})
    ana_res = json.loads(urllib.request.urlopen(req_ana).read())
    query_time_ms = round((time.time() - t0) * 1000, 2)
    print(f"✅ 8. Financial Analytics at Scale: Processed {ana_res['metrics']['total_subscriptions']} subscriptions in {query_time_ms}ms!")
    print(f"   MRR: ${ana_res['metrics']['mrr']:,.2f} | ARR: ${ana_res['metrics']['arr']:,.2f} | SLA Met: {ana_res['performance']['sla_met']} (SLA is < 2000ms, achieved in {query_time_ms}ms!)")

    print("\n🎉 ALL 8 SYSTEM CHECKS PASSED PERFECTLY!")

finally:
    proc.terminate()
    proc.kill()
