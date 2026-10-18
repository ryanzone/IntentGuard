import streamlit as st
import httpx
import json
import pandas as pd
import hmac
import hashlib
import time
import re
from uuid import uuid4

PROXY_URL = "https://intentguard-6tdh.onrender.com"
POLICY_HMAC_SECRET = "super-secret-hmac-key"

# -------------------------------------------------------------------
# PAGE CONFIGURATION & ENTERPRISE DESIGN SYSTEM
# -------------------------------------------------------------------
st.set_page_config(
    page_title="PayPal IntentGuard - Control Center",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling Injection (Shadcn Dark-Mode Theme Tokens)
st.markdown("""
<style>
    /* Metric Card Styling */
    div[data-testid="stMetric"] {
        background-color: #111827 !important;
        border: 1px solid #1F2937 !important;
        border-radius: 8px !important;
        padding: 16px !important;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1) !important;
    }
    div[data-testid="stMetric"] label {
        color: #9CA3AF !important;
        font-size: 0.85rem !important;
        font-weight: 500 !important;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #F9FAFB !important;
        font-size: 1.4rem !important;
        font-weight: 600 !important;
    }

    /* Container Card Enclosure */
    .stCard {
        background-color: #111827;
        border: 1px solid #1F2937;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 20px;
    }

    /* Tab Label Typography */
    button[data-baseweb="tab"] {
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        padding-top: 10px !important;
        padding-bottom: 10px !important;
    }

    /* JSON Code View Area */
    pre {
        background-color: #0B0F17 !important;
        border: 1px solid #1F2937 !important;
        border-radius: 6px !important;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------------
# SIDEBAR CONTROL PANEL
# -------------------------------------------------------------------
with st.sidebar:
    st.markdown("### **IntentGuard Gateway**")
    st.caption("v1.0.0 - Semantic Interceptor")
    st.markdown("---")
    
    st.markdown("#### **System Architecture**")
    st.markdown("""
    * **Proxy Target:** `127.0.0.1:8000`
    * **Security Layer:** `HMAC SHA-256`
* **Policy Engine:** `OpenRouter (Nemotron 3 120B)`
* **Gateway Target:** `PayPal /v2/orders`
    """)
    
    st.markdown("---")
    st.markdown("#### **Enforcement Parameters**")
    st.markdown("""
    * **Budget Variance:** `5.0% Max`
    * **Line-Item Guard:** `Active`
    * **Keyword Filter:** `Active`
    * **Non-Repudiation:** `Enabled`
    """)
    
    st.markdown("---")
    st.caption("PayPal Hackathon Reference Protocol")

# -------------------------------------------------------------------
# HEADER SECTION
# -------------------------------------------------------------------
st.title("PayPal IntentGuard - Agentic Gateway Control Center")
st.caption("Autonomous Agent Verification, Semantic Line-Item Inspection & Human-in-the-Loop Interceptor")

if "latest_decision" not in st.session_state:
    st.session_state["latest_decision"] = None

tab1, tab2 = st.tabs(["Agent Simulator & Interceptor", "Gateway System Metrics"])

# -------------------------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------------------------
def generate_policy_signature(payload_dict: dict, secret: str) -> str:
    canonical_bytes = json.dumps(payload_dict, sort_keys=True).encode('utf-8')
    return hmac.new(secret.encode('utf-8'), canonical_bytes, hashlib.sha256).hexdigest()

def extract_budget_from_prompt(prompt: str) -> float:
    numbers = re.findall(r'[\d,]+', prompt.replace("₹", "").replace("Rs", ""))
    for num in numbers:
        clean_num = float(num.replace(",", ""))
        if clean_num > 100:
            return clean_num
    return 70000.0

# -------------------------------------------------------------------
# TAB 1: INTERCEPTOR SIMULATOR & CONTROL PANEL
# -------------------------------------------------------------------
with tab1:
    st.markdown("### **1. Agent Execution & Intent Mandates**")
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.markdown("**User Intent Specification (Natural Language)**")
        user_prompt = st.text_area(
            "Natural Language User Prompt (Intent):",
            value="",
            placeholder="e.g., Buy me a college laptop under Rs. 70,000, absolutely no warranty or accessories.",
            height=110,
            key="ui_user_prompt_input",
            label_visibility="collapsed"
        )
        user_id = st.text_input(
            "User Identifier (UID):",
            value="",
            placeholder="e.g., usr_custom_demo",
            key="ui_user_id_input"
        )

    with col_b:
        st.markdown("**Intercepted Cart Payload (Agent Checkout)**")
        cart_amount = st.number_input(
            "Total Cart Amount (INR):", 
            value=0.0, 
            step=100.0,
            key="ui_cart_amount_input"
        )
        
        c_item1, c_item2 = st.columns(2)
        with c_item1:
            item_name = st.text_input(
                "Line Item Name:", 
                value="",
                placeholder="e.g., Dell XPS 13 Laptop",
                key="ui_item_name_input"
            )
        with c_item2:
            item_category = st.text_input(
                "Line Item Category:", 
                value="",
                placeholder="e.g., laptop",
                key="ui_item_cat_input"
            )

    st.markdown("---")
    
    if st.button("Intercept & Evaluate Checkout", type="primary", use_container_width=True, key="ui_submit_checkout_btn"):
        with st.spinner("Compiling Intent & Intercepting Cart Payload..."):
            try:
                checkout_payload = {
                    "amount": cart_amount,
                    "currency": "INR",
                    "line_items": [
                        {"name": item_name, "category": item_category, "price": cart_amount}
                    ]
                }

                dynamic_budget = extract_budget_from_prompt(user_prompt)
                
                prohibited_cats = []
                prohibited_kw = []
                prompt_lower = user_prompt.lower()
                
                if "no warranty" in prompt_lower or "protection" in prompt_lower:
                    prohibited_cats.extend(["warranty", "insurance"])
                    prohibited_kw.extend(["warranty", "extended", "protection", "guard"])
                if "no accessories" in prompt_lower or "no accessory" in prompt_lower:
                    prohibited_cats.extend(["accessories", "accessory"])
                    prohibited_kw.extend(["accessory", "accessories", "mat", "rest", "bag"])

                intent_id = str(uuid4())
                expires_at = int(time.time()) + 3600
                rules = {
                    "max_budget_inr": dynamic_budget,
                    "variance_tolerance_percent": 5.0,
                    "required_categories": [item_category] if item_category else [],
                    "prohibited_categories": prohibited_cats,
                    "prohibited_keywords": prohibited_kw
                }
                
                unsigned_payload = {
                    "intent_id": intent_id,
                    "user_id": user_id,
                    "rules": rules,
                    "expires_at": expires_at
                }
                signature = generate_policy_signature(unsigned_payload, POLICY_HMAC_SECRET)

                policy_payload = {
                    "intent_id": intent_id,
                    "user_id": user_id,
                    "raw_prompt": user_prompt,
                    "rules": rules,
                    "expires_at": expires_at,
                    "signature": signature
                }

                res = httpx.post(
                    f"{PROXY_URL}/v1/orders", 
                    json={
                        "checkout_payload": checkout_payload,
                        "policy": policy_payload
                    }, 
                    timeout=15.0
                )
                st.session_state["latest_decision"] = res.json()

            except Exception as e:
                st.error(f"Execution Error: {str(e)}")

    # -------------------------------------------------------------------
    # INTERCEPTOR DECISION OUTPUT & HITL CONTROLS
    # -------------------------------------------------------------------
    res_data = st.session_state.get("latest_decision")
    if res_data:
        st.markdown("### **2. Gateway Interception Output**")
        
        status = res_data.get("status")
        
        if status == "APPROVED":
            st.success("TRANSACTION APPROVED - Policy Cleared. PayPal Order Successfully Generated.")
            with st.expander("View Approved Gateway Payload Details", expanded=True):
                st.json(res_data)

        elif status == "HOLD":
            st.warning(f"TRANSACTION PLACED ON HOLD - {res_data.get('reason')}")
            
            with st.expander("View Hold Policy Breakdown", expanded=False):
                st.json(res_data)
            
            esc_id = str(res_data.get("escalation_id"))
            
            st.markdown("#### **Human-in-the-Loop (HITL) Override Controls**")
            st.info("Transaction variance falls within the 5.0% approval window. Select authorization action:")
            
            btn_c1, btn_c2 = st.columns(2)
            
            with btn_c1:
                if st.button("Approve Escalation & Create Order", use_container_width=True, type="primary", key=f"ui_btn_approve_{esc_id}"):
                    try:
                        dec = httpx.post(
                            f"{PROXY_URL}/v1/escalations/{esc_id}/decision?action=APPROVE",
                            timeout=30.0
                        )
                        st.session_state["latest_decision"] = dec.json()
                        st.rerun()
                    except httpx.ReadTimeout:
                        st.error("Connection timed out waiting for backend server. Please retry.")

            with btn_c2:
                if st.button("Reject Escalation & Cancel Cart", use_container_width=True, key=f"ui_btn_reject_{esc_id}"):
                    try:
                        dec = httpx.post(
                            f"{PROXY_URL}/v1/escalations/{esc_id}/decision?action=REJECT",
                            timeout=30.0
                        )
                        st.session_state["latest_decision"] = dec.json()
                        st.rerun()
                    except httpx.ReadTimeout:
                        st.error("Connection timed out waiting for proxy backend. Please try again.")

        elif res_data.get("escalation_status") == "APPROVED":
            st.success("ESCALATION APPROVED - Held Transaction Resumed & PayPal Order Generated.")
            with st.expander("View Resumed PayPal Order Payload", expanded=True):
                st.json(res_data)

        elif res_data.get("escalation_status") == "REJECTED":
            st.error("ESCALATION REJECTED - Transaction Canceled & Cart Dismissed.")
            with st.expander("View Rejection State Record", expanded=True):
                st.json(res_data)

        else:
            st.error("TRANSACTION BLOCKED - Intent Policy Violation Detected.")
            with st.expander("View Policy Violation Details", expanded=True):
                st.json(res_data)

# -------------------------------------------------------------------
# TAB 2: SYSTEM METRICS & ARCHITECTURE SPECIFICATIONS
# -------------------------------------------------------------------
with tab2:
    st.markdown("### **Gateway Telemetry & Enforcement Specifications**")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="Enforcement Mode", value="Strict Semantic")
    with col2:
        st.metric(label="Cryptographic Security", value="HMAC SHA-256")
    with col3:
        st.metric(label="Human-in-the-Loop", value="5.0% Tolerance")
    with col4:
        st.metric(label="PayPal API Target", value="/v2/orders")

    st.markdown("---")
    
    m_col1, m_col2 = st.columns(2)
    
    with m_col1:
        st.markdown("#### **Protocol Specifications**")
        st.markdown("""
        * **Google AP2 Alignment:** Implements dual-mandate architecture (Intent Policy Mandate & Cart Checkout Mandate)[cite: 7].
        * **Mastercard Agent Pay Compatibility:** Provides purchase intent validation data and non-repudiable transaction records[cite: 8].
        * **Cryptographic Signatures:** Generates SHA-256 HMAC envelopes across policy bounds (`intent_id`, `user_id`, `rules`, `expires_at`).
        * **Line-Item Inspection:** Inspects item names and category metadata against prohibited lists, catching sneaky upsells regardless of overall cart cost.
        """)
        
    with m_col2:
        st.markdown("#### **Gateway Execution Pipeline**")
        st.markdown("""
        * **APPROVED:** Cart matches intent bounds -> Forwards payload directly to PayPal Sandbox Order creation (`PayPalHttpClient.do_create_order`).
        * **BLOCKED:** Cart breaches negative constraints or hard budgets -> Prevents payment execution and raises HTTP 400.
        * **HOLD:** Minor budget overage within 5% tolerance -> Pauses execution and dispatches human escalation workflows.
        """)

    st.markdown("---")
st.caption("PayPal IntentGuard - Agentic Payment Gateway Verification Infrastructure")
