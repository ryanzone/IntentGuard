import httpx
import asyncio
import json
from app.compiler.intent_engine import compile_user_intent

PROXY_URL = "http://127.0.0.1:8000/v1/orders"


async def test_clean_approval():
    print("\n==================================================")
    print("TEST 1: CLEAN APPROVED CART")
    print("==================================================")
    prompt = "Buy a gaming monitor under Rs. 30,000, no extended warranty."
    policy = await compile_user_intent(user_id="usr_test_01", raw_prompt=prompt)

    payload = {
        "checkout_payload": {
            "amount": 28500,
            "currency": "USD",
            "line_items": [{"name": "27-inch 144Hz Monitor", "category": "electronics", "price": 28500}]
        },
        "policy": policy.model_dump(mode="json")
    }

    async with httpx.AsyncClient() as client:
        res = await client.post(PROXY_URL, json=payload)
        print("Status Code:", res.status_code)
        print("Response:", json.dumps(res.json(), indent=2, default=str))
        assert res.status_code == 200
        assert res.json()["status"] == "APPROVED"
        assert "paypal_order" in res.json()
        assert "capture" in res.json()["paypal_order"]


async def test_prohibited_violation():
    print("\n==================================================")
    print("TEST 2: PROHIBITED CATEGORY VIOLATION")
    print("==================================================")
    prompt = "Buy me a college laptop under Rs. 70,000, absolutely no warranty or accessories."
    policy = await compile_user_intent(user_id="usr_test_02", raw_prompt=prompt)

    payload = {
        "checkout_payload": {
            "amount": 74000,
            "currency": "USD",
            "line_items": [
                {"name": "Dell XPS 13 College Laptop", "category": "laptop", "price": 65000},
                {"name": "3-Year Extended Warranty", "category": "warranty", "price": 9000}
            ]
        },
        "policy": policy.model_dump(mode="json")
    }

    async with httpx.AsyncClient() as client:
        res = await client.post(PROXY_URL, json=payload)
        print("Status Code:", res.status_code)
        print("Response:", json.dumps(res.json(), indent=2, default=str))
        assert res.status_code == 400
        assert res.json()["detail"]["status"] == "BLOCKED"


async def test_hitl_hold_and_approve():
    print("\n==================================================")
    print("TEST 3: AMBIGUOUS OVERAGE (HOLD -> APPROVE)")
    print("==================================================")
    prompt = "Buy me a college laptop under Rs. 70,000, no accessories."
    policy = await compile_user_intent(user_id="usr_test_03", raw_prompt=prompt)

    payload = {
        "checkout_payload": {
            "amount": 71400,
            "currency": "USD",
            "line_items": [{"name": "Dell XPS 13 Laptop (Upgraded CPU)", "category": "laptop", "price": 71400}]
        },
        "policy": policy.model_dump(mode="json")
    }

    async with httpx.AsyncClient() as client:
        res = await client.post(PROXY_URL, json=payload)
        print("Hold Response Code:", res.status_code)
        res_json = res.json()
        print("Hold Response:", json.dumps(res_json, indent=2, default=str))
        assert res_json["status"] == "HOLD"

        escalation_id = res_json["escalation_id"]

        # Approve escalation
        approve_url = f"http://127.0.0.1:8000/v1/escalations/{escalation_id}/decision?action=APPROVE"
        decision_res = await client.post(approve_url)
        print("\nDecision Response Code:", decision_res.status_code)
        print("Decision Response:", json.dumps(decision_res.json(), indent=2, default=str))
        assert decision_res.status_code == 200
        assert decision_res.json()["escalation_status"] == "APPROVED"
        assert "paypal_order" in decision_res.json()
        assert "capture" in decision_res.json()["paypal_order"]


async def test_duplicate_escalation_decision():
    print("\n==================================================")
    print("TEST 4: DUPLICATE ESCALATION DECISION (IDEMPOTENCY)")
    print("==================================================")
    prompt = "Buy a gaming monitor under Rs. 30,000, no extended warranty."
    policy = await compile_user_intent(user_id="usr_test_04", raw_prompt=prompt)

    payload = {
        "checkout_payload": {
            "amount": 30600,
            "currency": "USD",
            "line_items": [{"name": "UltraWide 4K Monitor", "category": "electronics", "price": 30600}]
        },
        "policy": policy.model_dump(mode="json")
    }

    async with httpx.AsyncClient() as client:
        # Trigger HOLD
        res = await client.post(PROXY_URL, json=payload)
        res_json = res.json()
        assert res_json["status"] == "HOLD"
        escalation_id = res_json["escalation_id"]

        # First approval
        approve_url = f"http://127.0.0.1:8000/v1/escalations/{escalation_id}/decision?action=APPROVE"
        first = await client.post(approve_url)
        assert first.status_code == 200
        assert first.json()["escalation_status"] == "APPROVED"

        # Second approval (duplicate - should be rejected as already processed)
        second = await client.post(approve_url)
        print("Second response:", json.dumps(second.json(), indent=2, default=str))
        assert second.status_code == 200
        assert "already been processed" in second.json().get("message", "")


async def test_audit_trail():
    print("\n==================================================")
    print("TEST 5: AUDIT TRAIL RECORDING")
    print("==================================================")
    async with httpx.AsyncClient() as client:
        res = await client.get("http://127.0.0.1:8000/v1/audit-trail")
        print("Status Code:", res.status_code)
        data = res.json()
        print("Response:", json.dumps(data, indent=2, default=str))
        assert res.status_code == 200
        assert data["total"] > 0
        statuses = set(log["status"] for log in data["logs"])
        print(f"Statuses recorded: {statuses}")
        assert "APPROVED" in statuses or "BLOCKED" in statuses or "ESCALATED_APPROVED" in statuses


async def main():
    await test_clean_approval()
    await test_prohibited_violation()
    await test_hitl_hold_and_approve()
    await test_duplicate_escalation_decision()
    await test_audit_trail()
    print("\nALL TARGETED TESTS PASSED!")


if __name__ == "__main__":
    asyncio.run(main())