import httpx
import asyncio
import json
from app.compiler.intent_engine import compile_user_intent

PROXY_URL = "http://127.0.0.1:8000/v1/orders"


def safe_parse_async_response(response: httpx.Response):
    """Safely parse an httpx response body as JSON.

    Returns (ok: bool, data: dict|None, cause: str).
    Identifies the actual cause when the body is empty or non-JSON.
    """
    content_type = response.headers.get("content-type", "") or ""
    is_json = "application/json" in content_type
    body = response.text.strip()

    if not body:
        cause = f"HTTP {response.status_code}: empty response body (content-type: {content_type or 'none'})"
        return False, None, cause
    if not is_json:
        cause = f"HTTP {response.status_code}: non-JSON content-type '{content_type}'"
        return False, None, cause
    try:
        data = response.json()
    except Exception as e:
        cause = f"HTTP {response.status_code}: failed to decode JSON body: {e}"
        return False, None, cause
    return True, data, ""


async def test_clean_approval():
    print("\n==================================================")
    print("TEST 1: CLEAN APPROVED CART")
    print("==================================================")
    prompt = "Buy a gaming monitor under ₹30,000, no extended warranty."
    policy = await compile_user_intent(user_id="usr_test_01", raw_prompt=prompt)
    
    payload = {
        "checkout_payload": {
            "amount": 28500,
            "currency": "INR",
            "line_items": [{"name": "27-inch 144Hz Monitor", "category": "electronics", "price": 28500}]
        },
        "policy": policy.model_dump(mode="json")
    }

    async with httpx.AsyncClient() as client:
        res = await client.post(PROXY_URL, json=payload)
        print("Status Code:", res.status_code)
        ok, data, cause = safe_parse_async_response(res)
        if not ok:
            print("Execution Error:", cause)
            print("Raw body:", res.text)
            raise AssertionError(cause)
        print("Response:", json.dumps(data, indent=2))
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {cause}"
        assert data["status"] == "APPROVED", f"Expected APPROVED, got {data.get('status')}"

async def test_prohibited_violation():
    print("\n==================================================")
    print("TEST 2: PROHIBITED CATEGORY VIOLATION")
    print("==================================================")
    prompt = "Buy me a college laptop under ₹70,000, absolutely no warranty or accessories."
    policy = await compile_user_intent(user_id="usr_test_02", raw_prompt=prompt)
    
    payload = {
        "checkout_payload": {
            "amount": 74000,
            "currency": "INR",
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
        print("Response:", json.dumps(res.json(), indent=2))
        assert res.status_code == 400
        assert res.json()["detail"]["status"] == "BLOCKED"

async def test_hitl_hold_and_approve():
    print("\n==================================================")
    print("TEST 3: AMBIGUOUS OVERAGE (HOLD -> APPROVE)")
    print("==================================================")
    prompt = "Buy me a college laptop under ₹70,000, no accessories."
    policy = await compile_user_intent(user_id="usr_test_03", raw_prompt=prompt)
    
    payload = {
        "checkout_payload": {
            "amount": 71400,
            "currency": "INR",
            "line_items": [{"name": "Dell XPS 13 Laptop (Upgraded CPU)", "category": "laptop", "price": 71400}]
        },
        "policy": policy.model_dump(mode="json")
    }

    async with httpx.AsyncClient() as client:
        # Step A: Trigger HOLD
        res = await client.post(PROXY_URL, json=payload)
        print("Hold Response Code:", res.status_code)
        ok, res_json, cause = safe_parse_async_response(res)
        if not ok:
            print("Execution Error:", cause)
            print("Raw body:", res.text)
            raise AssertionError(cause)
        print("Hold Response:", json.dumps(res_json, indent=2))
        assert res_json["status"] == "HOLD", f"Expected HOLD, got {res_json.get('status')}: {cause}"
        
        escalation_id = res_json["escalation_id"]

        # Step B: Approve Escalation
        approve_url = f"http://127.0.0.1:8000/v1/escalations/{escalation_id}/decision?action=APPROVE"
        decision_res = await client.post(approve_url)
        print("\nDecision Response Code:", decision_res.status_code)
        ok, decision_data, cause = safe_parse_async_response(decision_res)
        if not ok:
            print("Execution Error:", cause)
            print("Raw body:", decision_res.text)
            raise AssertionError(cause)
        print("Decision Response:", json.dumps(decision_data, indent=2))
        assert decision_res.status_code == 200, f"Expected 200, got {decision_res.status_code}: {cause}"
        assert decision_data["escalation_status"] == "APPROVED", f"Expected APPROVED, got {decision_data.get('escalation_status')}"

async def main():
    await test_clean_approval()
    await test_prohibited_violation()
    await test_hitl_hold_and_approve()
    print("\n✅ ALL END-TO-END SUITE TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(main())