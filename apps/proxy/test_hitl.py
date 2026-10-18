import httpx
import asyncio
import json
import sys
from uuid import uuid4
from app.compiler.intent_engine import compile_user_intent

async def run_dynamic_hitl_test(
    user_prompt: str, 
    cart_amount: float, 
    item_name: str, 
    user_id: str = None
):
    proxy_url = "http://127.0.0.1:8000/v1/orders"
    user_id = user_id or f"usr_{uuid4().hex[:8]}"

    # 1. Compile User Intent Policy dynamically via OpenRouter
    print(f"\n[Step 1] Dynamically Compiling User Intent for '{user_id}':\n Prompt: '{user_prompt}'")
    policy = await compile_user_intent(user_id=user_id, raw_prompt=user_prompt)

    # Convert Pydantic model to JSON-serializable dict
    serialized_policy = policy.model_dump(mode="json")

    # 2. Construct Dynamic Cart Payload
    print(f"\n--- [Step 2] Sending Dynamic Checkout Cart (₹{cart_amount:,}) ---")
    hold_payload = {
        "checkout_payload": {
            "amount": cart_amount,
            "currency": "INR",
            "line_items": [
                {"name": item_name, "category": "general", "price": cart_amount}
            ]
        },
        "policy": serialized_policy
    }

    async with httpx.AsyncClient() as client:
        res = await client.post(proxy_url, json=hold_payload)
        res_json = res.json()
        print("Proxy Interceptor Response:\n", json.dumps(res_json, indent=2))
        
        escalation_id = res_json.get("escalation_id")
        if res_json.get("status") != "HOLD" or not escalation_id:
            print("\nOutcome: Transaction did not result in a HOLD state.")
            return

        # 3. Simulate Human Decision Call
        print(f"\n--- [Step 3] Approving Escalation ID: '{escalation_id}' ---")
        approve_url = f"http://127.0.0.1:8000/v1/escalations/{escalation_id}/decision?action=APPROVE"
        decision_res = await client.post(approve_url)
        print("Resumption Response:\n", json.dumps(decision_res.json(), indent=2))

if __name__ == "__main__":
    # Allows passing dynamic prompts from command line arguments
    if len(sys.argv) > 3:
        prompt = sys.argv[1]
        amount = float(sys.argv[2])
        item = sys.argv[3]
    else:
        # Default dynamic test values
        prompt = "Buy me a gaming monitor under ₹30,000, no extended warranty."
        amount = 30600  # 2% over budget (30,600 vs 30,000)
        item = "UltraWide 4K Gaming Monitor"

    asyncio.run(run_dynamic_hitl_test(user_prompt=prompt, cart_amount=amount, item_name=item))