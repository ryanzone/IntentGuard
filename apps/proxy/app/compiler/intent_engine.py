import hmac
import hashlib
import json
import time
import asyncio
from uuid import uuid4
from openai import OpenAI, APIError

from app.schemas.policy import IntentPolicy, IntentRules
from app.core.config import settings

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=settings.OPENROUTER_API_KEY,
)

SYSTEM_INSTRUCTION = """
You are a financial policy engine for an agentic payment gateway.
Your task is to convert a user's natural language shopping instruction into a strict JSON policy schema.

Rules:
1. max_budget_inr: Extract the maximum spending limit in INR.
2. required_categories: Categories/items explicitly requested (e.g., 'laptop', 'shoes').
3. prohibited_categories: Categories explicitly forbidden (e.g., 'warranty', 'accessories', 'insurance').
4. prohibited_keywords: Specific negative keywords to block in line-item names (e.g., 'extended', '3-year', 'bag').
5. variance_tolerance_percent: Default to 5.0 unless user explicitly specifies budget flexibility.
"""

def generate_policy_signature(payload_dict: dict, secret: str) -> str:
    canonical_bytes = json.dumps(payload_dict, sort_keys=True).encode('utf-8')
    return hmac.new(secret.encode('utf-8'), canonical_bytes, hashlib.sha256).hexdigest()

async def compile_user_intent(user_id: str, raw_prompt: str, ttl_seconds: int = 3600) -> IntentPolicy:
    max_retries = 3
    response = None

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="nvidia/nemotron-3-super-120b-a12b:free",
                messages=[
                    {"role": "system", "content": SYSTEM_INSTRUCTION},
                    {"role": "user", "content": raw_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            break
        except APIError as e:
            if attempt == max_retries - 1:
                # Fallback to a different model via OpenRouter
                response = client.chat.completions.create(
                    model="google/gemma-4-26b-a4b:free",
                    messages=[
                        {"role": "system", "content": SYSTEM_INSTRUCTION},
                        {"role": "user", "content": raw_prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                )
            else:
                await asyncio.sleep(2 ** attempt)

    parsed_rules: IntentRules = IntentRules.model_validate_json(response.choices[0].message.content)
    intent_id = uuid4()
    expires_at = int(time.time()) + ttl_seconds

    unsigned_payload = {
        "intent_id": str(intent_id),
        "user_id": user_id,
        "rules": parsed_rules.model_dump(),
        "expires_at": expires_at
    }

    signature = generate_policy_signature(unsigned_payload, settings.POLICY_HMAC_SECRET)

    return IntentPolicy(
        intent_id=intent_id,
        user_id=user_id,
        raw_prompt=raw_prompt,
        rules=parsed_rules,
        expires_at=expires_at,
        signature=signature
    )