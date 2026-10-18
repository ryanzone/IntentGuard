import httpx
import asyncio
import json
from app.compiler.intent_engine import compile_user_intent

async def run_e2e_test():
    proxy_url = "http://127.0.0.1:8000/v1/orders"
    
    # 1. Compile User Intent Policy via OpenRouter (Nemotron 3 120B)
    user_prompt = "Buy me a college laptop under ₹70,000, absolutely no warranty or accessories."
    print(f"\n[Step 1] Compiling User Intent: '{user_prompt}'")
    policy = await compile_user_intent(user_id="usr_test_99", raw_prompt=user_prompt)
    
    # mode="json" converts UUIDs and timestamps to standard JSON strings
    serialized_policy = policy.model_dump(mode="json")
    
    # 2. Scenario A: VALID Cart (₹65,000 Laptop)
    print("\n--- Scenario A: Clean Cart (Laptop ₹65,000) ---")
    valid_payload = {
        "checkout_payload": {
            "amount": 65000,
            "currency": "INR",
            "line_items": [
                {"name": "Dell XPS 13 College Laptop", "category": "laptop", "price": 65000}
            ]
        },
        "policy": serialized_policy
    }
    
    async with httpx.AsyncClient() as client:
        res = await client.post(proxy_url, json=valid_payload)
        print(f"Status Code: {res.status_code}")
        print("Response:", json.dumps(res.json(), indent=2, default=str))

    # 3. Scenario B: VIOLATION Cart (Includes Hidden ₹9,000 Extended Warranty)
    print("\n--- Scenario B: Violation Cart (Laptop + ₹9,000 Warranty) ---")
    violation_payload = {
        "checkout_payload": {
            "amount": 74000,
            "currency": "INR",
            "line_items": [
                {"name": "Dell XPS 13 College Laptop", "category": "laptop", "price": 65000},
                {"name": "3-Year Extended Warranty", "category": "warranty", "price": 9000}
            ]
        },
        "policy": serialized_policy
    }
    
    async with httpx.AsyncClient() as client:
        res = await client.post(proxy_url, json=violation_payload)
        print(f"Status Code: {res.status_code}")
        print("Response:", json.dumps(res.json(), indent=2, default=str))

if __name__ == "__main__":
    asyncio.run(run_e2e_test())