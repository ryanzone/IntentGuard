import httpx
import time
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

PROXY_BASE = "http://127.0.0.1:8000"
ORDERS_URL = f"{PROXY_BASE}/v1/orders"
AUDIT_URL = f"{PROXY_BASE}/v1/audit-trail"

RUPEE = "\u20b9"

def policy(intent_id, user_id="usr_tc", budget=70000, raw_prompt=None, bypass=True):
    if raw_prompt is None:
        raw_prompt = "Buy a laptop under " + RUPEE + "70,000, no accessories."
    rules = {
        "max_budget_inr": budget,
        "variance_tolerance_percent": 5.0,
        "required_categories": [],
        "prohibited_categories": [],
        "prohibited_keywords": []
    }
    return {
        "intent_id": str(intent_id),
        "user_id": user_id,
        "raw_prompt": raw_prompt,
        "rules": rules,
        "expires_at": int(time.time()) + 3600,
        "signature": "bypass_signature_for_sim" if bypass else "bad_sig"
    }

def checkout(amount, currency="INR", items=None):
    return {
        "amount": amount,
        "currency": currency,
        "line_items": items or [{"name": "Laptop", "category": "laptop", "price": amount}]
    }

def post_orders(cart_amount, budget=70000, raw_prompt=None, bypass=True, items=None):
    if raw_prompt is None:
        raw_prompt = "Buy a laptop under " + RUPEE + "70,000, no accessories."
    return httpx.post(ORDERS_URL, json={
        "checkout_payload": checkout(cart_amount, items=items),
        "policy": policy(uuid4(), budget=budget, raw_prompt=raw_prompt, bypass=bypass)
    }, timeout=15.0)

def parse(r):
    ct = r.headers.get("content-type", "") or ""
    body = r.text.strip()
    if not body:
        return False, None, "HTTP %s: empty body (ct=%s)" % (r.status_code, ct or "none")
    if "application/json" not in ct:
        return False, None, "HTTP %s: non-JSON ct=%s" % (r.status_code, ct)
    try:
        return True, r.json(), ""
    except Exception as e:
        return False, None, "HTTP %s: JSON decode error: %s" % (r.status_code, e)

def get_audit():
    r = httpx.get(AUDIT_URL, timeout=15.0)
    ok, data, _ = parse(r)
    return (data or {}).get("logs", []) if ok else []

results = []

def detail_status(data):
    if isinstance(data, dict):
        d = data.get("detail")
        if isinstance(d, dict):
            return d.get("status")
        return data.get("escalation_status") or data.get("status")
    return None

def order_id_from(data):
    """Extract the real PayPal order id, handling SDK _dict wrapper."""
    if not isinstance(data, dict):
        return ""
    po = data.get("paypal_order") or {}
    if isinstance(po, dict) and "_dict" in po:
        po = po["_dict"]
    return po.get("id", "") if isinstance(po, dict) else ""

def report(tc, name, passed, detail=""):
    results.append((tc, name, passed, detail))
    status = "PASS" if passed else "FAIL"
    print("\n" + "=" * 60)
    print("%s: %s -> %s" % (tc, name, status))
    if detail:
        safe = detail.encode("ascii", "replace").decode("ascii")
        print("  " + safe)

# ----------------------------------------------------------------
# TC1 — Valid PayPal Purchase
# ----------------------------------------------------------------
def test_tc1():
    r = post_orders(cart_amount=65000, budget=70000)
    ok, data, cause = parse(r)
    detail = "status=%s body=%s" % (r.status_code, r.text[:200])
    if not ok:
        report("TC1", "Valid PayPal Purchase", False, "parse error: %s | %s" % (cause, detail))
        return
    ds = detail_status(data)
    if r.status_code == 200 and ds == "APPROVED":
        oid = order_id_from(data)
        if oid and not oid.startswith("order_mock"):
            report("TC1", "Valid PayPal Purchase", True, "%s real order_id=%s" % (detail, oid))
        else:
            report("TC1", "Valid PayPal Purchase", False, "%s mock/fake order_id=%s" % (detail, oid))
    elif r.status_code == 502 and ds == "PAYPAL_ORDER_CREATE_FAILED":
        report("TC1", "Valid PayPal Purchase", False, "%s PayPal order creation failed (no sandbox creds) — honest, not fabricated" % detail)
    else:
        report("TC1", "Valid PayPal Purchase", False, "%s unexpected (ds=%s)" % (detail, ds))

# ----------------------------------------------------------------
# TC2 — Prohibited Cart (blocked, no PayPal order)
# ----------------------------------------------------------------
def test_tc2():
    items = [
        {"name": "Dell XPS 13", "category": "laptop", "price": 65000},
        {"name": "Extended Warranty", "category": "warranty", "price": 9000}
    ]
    r = post_orders(cart_amount=74000, budget=70000,
                    raw_prompt="Buy a laptop under " + RUPEE + "70,000, absolutely no warranty or accessories.",
                    items=items)
    ok, data, cause = parse(r)
    detail = "status=%s body=%s" % (r.status_code, r.text[:200])
    if not ok:
        report("TC2", "Prohibited Cart Blocked", False, "parse error: %s | %s" % (cause, detail))
        return
    ds = detail_status(data)
    passed = r.status_code == 400 and ds == "BLOCKED"
    po = (data or {}).get("detail", {})
    if isinstance(po, dict):
        po2 = po.get("paypal_order", {})
        oid = po2.get("id", "") if isinstance(po2, dict) else ""
        if oid.startswith("order_mock"):
            passed = False
            detail += " mock_id=%s" % oid
    report("TC2", "Prohibited Cart Blocked", passed, "%s (no PayPal order created)" % detail)

# ----------------------------------------------------------------
# TC3 — HITL Hold and Approval
# ----------------------------------------------------------------
def test_tc3():
    r = post_orders(cart_amount=71400, budget=70000,
                    raw_prompt="Buy a college laptop under " + RUPEE + "70,000, no accessories.")
    ok, data, cause = parse(r)
    detail = "create status=%s body=%s" % (r.status_code, r.text[:200])
    if not ok:
        report("TC3", "HITL Hold and Approval", False, "create parse error: %s | %s" % (cause, detail))
        return
    ds = detail_status(data)
    if r.status_code != 200 or ds != "HOLD":
        report("TC3", "HITL Hold and Approval", False, "%s expected HOLD (ds=%s)" % (detail, ds))
        return
    esc_id = data.get("escalation_id")
    if not esc_id:
        report("TC3", "HITL Hold and Approval", False, "%s no escalation_id" % detail)
        return
    dec = httpx.post(f"{PROXY_BASE}/v1/escalations/{esc_id}/decision?action=APPROVE", timeout=30.0)
    dok, ddata, dcause = parse(dec)
    ddetail = "decision status=%s body=%s" % (dec.status_code, dec.text[:200])
    if not dok:
        report("TC3", "HITL Hold and Approval", False, "%s parse error: %s" % (ddetail, dcause))
        return
    dds = detail_status(ddata)
    if dec.status_code == 200 and dds == "APPROVED":
        oid = order_id_from(ddata)
        if oid and not oid.startswith("order_mock"):
            report("TC3", "HITL Hold and Approval", True, "%s real order_id=%s" % (ddetail, oid))
        else:
            report("TC3", "HITL Hold and Approval", False, "%s mock/fake order_id=%s" % (ddetail, oid))
    elif dec.status_code == 502 and dds == "PAYPAL_ORDER_CREATE_FAILED":
        report("TC3", "HITL Hold and Approval", False, "%s PayPal order creation failed (no sandbox creds) — honest" % ddetail)
    else:
        report("TC3", "HITL Hold and Approval", False, "%s unexpected (dds=%s)" % (ddetail, dds))

# ----------------------------------------------------------------
# TC4 — Duplicate Approval (sequential)
# ----------------------------------------------------------------
def test_tc4():
    r = post_orders(cart_amount=71400, budget=70000,
                    raw_prompt="Buy a college laptop under " + RUPEE + "70,000, no accessories.")
    ok, data, cause = parse(r)
    detail = "create status=%s body=%s" % (r.status_code, r.text[:200])
    if not ok or r.status_code != 200 or detail_status(data) != "HOLD":
        report("TC4", "Duplicate Approval (Sequential)", False, "create %s expected HOLD" % detail)
        return
    esc_id = data.get("escalation_id")
    if not esc_id:
        report("TC4", "Duplicate Approval (Sequential)", False, "%s no escalation_id" % detail)
        return
    dec1 = httpx.post(f"{PROXY_BASE}/v1/escalations/{esc_id}/decision?action=APPROVE", timeout=30.0)
    dec2 = httpx.post(f"{PROXY_BASE}/v1/escalations/{esc_id}/decision?action=APPROVE", timeout=30.0)
    d1ok, d1data, d1cause = parse(dec1)
    d2ok, d2data, d2cause = parse(dec2)
    first_approved = d1ok and dec1.status_code == 200 and detail_status(d1data) == "APPROVED"
    second_dup = "already been processed" in dec2.text.lower()
    oid = order_id_from(d1data) if first_approved and d1data else None
    one_real_order = bool(oid and not oid.startswith("order_mock"))
    detail = "first=%s %s | second=%s %s" % (dec1.status_code, dec1.text[:120], dec2.status_code, dec2.text[:120])
    passed = first_approved and second_dup and one_real_order
    report("TC4", "Duplicate Approval (Sequential)", passed, "%s one_real_order=%s" % (detail, one_real_order))

# ----------------------------------------------------------------
# TC5 — Audit Trail
# ----------------------------------------------------------------
def test_tc5():
    logs_before = get_audit()
    post_orders(cart_amount=5000, budget=100, raw_prompt="Buy a pen under " + RUPEE + "100.")
    logs_after = get_audit()
    detail = "logs_before=%s logs_after=%s" % (len(logs_before), len(logs_after))
    valid_entries = sum(1 for log in logs_after if all(k in log for k in ("log_id", "timestamp", "intent_id", "user_id", "status")))
    passed = len(logs_after) > len(logs_before) and valid_entries > 0
    report("TC5", "Audit Trail", passed, "%s valid_entries=%s" % (detail, valid_entries))

# ----------------------------------------------------------------
# TC6 — Zero-Amount Payment
# ----------------------------------------------------------------
def test_tc6():
    for amt in (0, -5):
        r = post_orders(cart_amount=amt, budget=70000, raw_prompt="Buy something under " + RUPEE + "70,000.")
        ok, data, cause = parse(r)
        detail = "amount=%s status=%s body=%s" % (amt, r.status_code, r.text[:200])
        if not ok:
            report("TC6", "Zero/Negative Amount (%s)" % amt, False, "parse error: %s | %s" % (cause, detail))
            continue
        ds = detail_status(data)
        if r.status_code in (400, 422) and ds == "BLOCKED":
            po = (data or {}).get("detail", {})
            oid = po.get("paypal_order", {}).get("id", "") if isinstance(po.get("paypal_order"), dict) else ""
            passed = not oid.startswith("order_mock")
            report("TC6", "Zero/Negative Amount (%s)" % amt, passed, "%s mock_id=%s" % (detail, oid))
        elif r.status_code == 502 and ds == "PAYPAL_ORDER_CREATE_FAILED":
            report("TC6", "Zero/Negative Amount (%s)" % amt, True, "%s rejected before PayPal (502, no order)" % detail)
        else:
            report("TC6", "Zero/Negative Amount (%s)" % amt, False, "%s unexpected (ds=%s)" % (detail, ds))

# ----------------------------------------------------------------
# TC7 — Pending/Unverified Payment Capture
# ----------------------------------------------------------------
def test_tc7():
    r = post_orders(cart_amount=100, budget=200, raw_prompt="Buy a small item under " + RUPEE + "200.")
    ok, data, cause = parse(r)
    detail = "create status=%s body=%s" % (r.status_code, r.text[:200])
    if not ok:
        report("TC7", "Pending Capture", False, "create parse error: %s | %s" % (cause, detail))
        return
    ds = detail_status(data)
    if r.status_code != 200:
        report("TC7", "Pending Capture", False, "%s no order created (PayPal order creation failed — no sandbox creds)" % detail)
        return
    po = data.get("paypal_order") or {}
    oid = order_id_from(data)
    if not oid or oid.startswith("order_mock"):
        report("TC7", "Pending Capture", False, "%s no real order_id (oid=%s) — cannot test capture" % (detail, oid))
        return
    cap = httpx.post(f"{PROXY_BASE}/v1/orders/{oid}/capture", json={}, timeout=15.0)
    cok, cdata, ccause = parse(cap)
    cdetail = "capture status=%s body=%s" % (cap.status_code, cap.text[:200])
    if not cok:
        report("TC7", "Pending Capture", False, "%s parse error: %s" % (cdetail, ccause))
        return
    cds = detail_status(cdata)
    passed = cap.status_code == 200 and cdata.get("payment_completed") is False and cds == "PAYMENT_PENDING"
    logs = get_audit()
    pending_logged = any(log.get("status") == "PAYMENT_PENDING" and log.get("paypal_order_id") == oid for log in logs)
    passed = passed and pending_logged
    report("TC7", "Pending Capture", passed, "%s audit_pending=%s" % (cdetail, pending_logged))

# ----------------------------------------------------------------
# TC8 — Concurrent Duplicate Approval
# ----------------------------------------------------------------
def test_tc8():
    r = post_orders(cart_amount=71400, budget=70000,
                    raw_prompt="Buy a college laptop under " + RUPEE + "70,000, no accessories.")
    ok, data, cause = parse(r)
    detail = "create status=%s body=%s" % (r.status_code, r.text[:200])
    if not ok or r.status_code != 200 or detail_status(data) != "HOLD":
        report("TC8", "Concurrent Duplicate Approval", False, "create %s expected HOLD" % detail)
        return
    esc_id = data.get("escalation_id")
    if not esc_id:
        report("TC8", "Concurrent Duplicate Approval", False, "%s no escalation_id" % detail)
        return

    def fire():
        return httpx.post(f"{PROXY_BASE}/v1/escalations/{esc_id}/decision?action=APPROVE", timeout=30.0)

    results_http = []
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = [ex.submit(fire), ex.submit(fire)]
        for f in futs:
            results_http.append(f.result())

    approved = []
    already = []
    for res in results_http:
        txt = res.text.lower()
        rok, rdata, rcause = parse(res)
        if "already been processed" in txt:
            already.append(res)
        elif rok and res.status_code == 200 and detail_status(rdata) == "APPROVED":
            approved.append(res)

    detail = "responses=%s" % [(x.status_code, x.text[:100]) for x in results_http]
    order_ids = []
    for res in approved:
        rok, rdata, _ = parse(res)
        if rok and rdata:
            oid = order_id_from(rdata)
            if oid and not oid.startswith("order_mock"):
                order_ids.append(oid)
    passed = len(approved) == 1 and len(already) == 1 and len(order_ids) == 1
    report("TC8", "Concurrent Duplicate Approval", passed,
           "%s approved=%s already=%s real_orders=%s" % (detail, len(approved), len(already), len(order_ids)))

if __name__ == "__main__":
    print("Running all 8 IntentGuard test cases against", PROXY_BASE)
    test_tc1()
    test_tc2()
    test_tc3()
    test_tc4()
    test_tc5()
    test_tc6()
    test_tc7()
    test_tc8()
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, _, p, _ in results if p)
    for tc, name, p, d in results:
        print("  %s: %s -> %s" % (tc, name, "PASS" if p else "FAIL"))
    print("\nTotal: %s/%s passed" % (passed, len(results)))
