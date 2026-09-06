# Razorpay IntentGuard

> **Real-Time Semantic Intent Verification Proxy & Policy Enforcement Gateway for Agentic Commerce**

[![Razorpay API](https://img.shields.io/badge/Razorpay-v1%2Forders-blue)](https://razorpay.com)
[![Python](https://img.shields.io/badge/Python-3.11-green)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)](https://fastapi.tiangolo.com)
[![Gemini API](https://img.shields.io/badge/AI-Gemini%202.5%20Flash-orange)](https://ai.google.dev)
[![Security](https://img.shields.io/badge/Security-HMAC%20SHA--256-red)](https://en.wikipedia.org/wiki/HMAC)

---

## Demo

**Demo Video:** [Watch the Razorpay IntentGuard Demo](https://youtu.be/u8gw1rCU4nk?si=c18reocTfbA0ZUWC)

## Executive Summary

Autonomous AI shopping agents frequently make purchases on behalf of consumers. However, standard payment gateway rails primarily enforce flat spending caps (e.g., total price ≤ ₹70,000). They cannot evaluate natural-language constraints or inspect individual cart line items to determine whether a transaction actually aligns with the user's original instructions.

**Razorpay IntentGuard** acts as an intelligent pre-authorization gateway proxy sitting in front of Razorpay's `POST /v1/orders` API.

It dynamically:

* Compiles natural-language user instructions into cryptographically signed JSON policy envelopes.
* Inspects individual cart line items for unauthorized products, accessories, warranties, and merchant upsells.
* Blocks transactions that violate explicit user intent.
* Introduces an asynchronous **Human-in-the-Loop (HITL)** `HOLD` state for ambiguous overages.
* Maintains an audit trail of policy decisions.

---

## Architecture & Protocol Alignment

Razorpay IntentGuard is designed around emerging standards for **verifiable intent and agentic commerce**, including **Google AP2 (Intent/Cart Mandates)** and **Mastercard Verifiable Intent Frameworks**, while integrating directly with the Razorpay API ecosystem.

```text
┌─────────────────────────┐
│ User Intent Prompt      │
│ "Buy laptop under ₹70k" │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Gemini LLM              │
│ Intent Compiler         │
└───────────┬─────────────┘
            │
            │ Generates HMAC Policy
            ▼
┌─────────────────────────┐      Checkout Payload
│ Signed Policy Envelope  │ ──────────────|
│ HMAC-SHA256             │               |
└─────────────────────────┘               |
                                          |
                                          ▼                              
                              ┌─────────────────────────┐
                              │ Razorpay IntentGuard    │
                              │ Proxy Interceptor       │
                              └───────────┬─────────────┘
                                          │
                 ┌────────────────────────┼────────────────────────┐
                 │                        │                        │
                 ▼                        ▼                        ▼
      ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
      │ STATUS: APPROVED    │  │ STATUS: BLOCKED     │  │ STATUS: HOLD        │
      ├─────────────────────┤  ├─────────────────────┤  ├─────────────────────┤
      │ Executes Razorpay   │  │ Prevents Order      │  │ Requests HITL       │
      │ Order               │  │ Creation            │  │ Approval            │
      └─────────────────────┘  └─────────────────────┘  └─────────────────────┘
```

### Decision Flow

| Status     | Condition                      | Action                  |
| ---------- | ------------------------------ | ----------------------- |
| `APPROVED` | Cart matches user intent       | Creates Razorpay order  |
| `BLOCKED`  | Policy violation detected      | Prevents order creation |
| `HOLD`     | Ambiguous or tolerated overage | Requests human approval |

---

## Key Features

### 1. Natural Language Intent Compiler

Converts unstructured user prompts into strict JSON policy bounds, including:

* Budget limits
* Required categories
* Prohibited categories
* Negative keywords
* Budget tolerance

The compiler uses **Gemini 2.5 Flash** to interpret the user's original intent.

### 2. Cryptographic Non-Repudiation

Compiled policies are signed using **HMAC-SHA256** to prevent unauthorized policy modification during multi-step agent shopping sessions.

### 3. Semantic Line-Item Inspection

Instead of checking only the total transaction value, IntentGuard evaluates individual cart items against the user's constraints.

**Example:**

```text
User Intent:
"Buy a laptop under ₹70,000. No warranty."

Cart:
Laptop       ₹65,000
Warranty      ₹9,000
--------------------
Total         ₹74,000

Result: BLOCKED
Reason: Warranty violates the user's explicit constraint.
```

### 4. Human-in-the-Loop (HITL) State Machine

Ambiguous transactions can enter a `HOLD` state instead of being immediately rejected.

For example:

```text
Policy Budget:    ₹70,000
Cart Total:       ₹71,400
Overage:              2%
Tolerance:            5%

Result: HOLD
```

The user receives an approval request through the application before the transaction is allowed to continue.

### 5. Containerized Microservice

Built and deployed using **Docker and Docker Compose** for consistent local development and deployment.

---

## Tech Stack

| **Component**              | **Technology**                         |
| -------------------------- | -------------------------------------- |
| Proxy Gateway              | Python 3.11, FastAPI, Uvicorn          |
| Intent Compiler            | Google GenAI SDK, Gemini 2.5 Flash     |
| Validation Engine          | Pydantic v2                             |
| Cryptographic Signing      | HMAC-SHA256                             |
| Payment Gateway Integration | Razorpay Python SDK                    |
| Escalation & HITL          | FastAPI, Streamlit                     |
| Containerization           | Docker, Docker Compose                 |
| Deployment                 | Render, Streamlit Cloud                |

---

## Directory Structure

```text
razorpay-intentguard/
├── apps/
│   ├── dashboard/
│   │   ├── Dockerfile
│   │   ├── app.py
│   │   └── requirements.txt
│   │
│   └── proxy/
│       ├── app/
│       │   ├── api/
│       │   │   ├── __init__.py
│       │   │   ├── escalation.py
│       │   │   └── routes.py
│       │   ├── compiler/
│       │   │   ├── __init__.py
│       │   │   └── intent_engine.py
│       │   ├── core/
│       │   │   ├── __init__.py
│       │   │   └── config.py
│       │   ├── evaluator/
│       │   │   ├── __init__.py
│       │   │   └── rules.py
│       │   ├── schemas/
│       │   │   ├── __init__.py
│       │   │   └── policy.py
│       │   ├── services/
│       │   │   ├── __init__.py
│       │   │   ├── audit.py
│       │   │   ├── escalation_store.py
│       │   │   └── notifier.py
│       │   ├── __init__.py
│       │   └── main.py
│       ├── .env.example
│       ├── .gitignore
│       ├── Dockerfile
│       ├── requirements.txt
│       ├── test_client.py
│       ├── test_full_suite.py
│       └── test_hitl.py
│
├── packages/
│   └── shared-types/
│       └── policy.schema.ts
│
├── .gitignore
├── README.md
└── docker-compose.yml
```

---

# Quick Start & Deployment Guide

## 1. Prerequisites

Make sure you have:

* Python 3.11+
* Docker
* Docker Compose
* Razorpay test API credentials
* Gemini API key

---

## 2. Environment Setup

Create a `.env` file in `apps/proxy/` or the project root:

```env
GEMINI_API_KEY="your-gemini-api-key"

RAZORPAY_KEY_ID="rzp_test_xxxxxxxxxxxx"
RAZORPAY_KEY_SECRET="xxxxxxxxxxxxxxxxxxxxxxxx"

POLICY_HMAC_SECRET="super-secret-hmac-key"
```

> **Security:** Never commit API keys or secrets to Git.

Add the following to `.gitignore`:

```gitignore
.env
*.env
__pycache__/
```

---

## 3. Launch the Containerized Proxy Backend

Build and run the stack using Docker Compose:

```bash
docker-compose up --build -d
```

Verify the running containers:

```bash
docker-compose ps
```

---

## 4. Verify Proxy Health

### Health Check

```text
http://localhost:8000/health
```

### Swagger API Documentation

```text
http://localhost:8000/docs
```

---

## 5. Run the Automated Test Suite

Run the HITL test suite:

```bash
python apps/proxy/test_hitl.py
```

---

# Verified Gateway Pathways

| Scenario               | Input Prompt                            | Cart Contents                        | Proxy Result   | Gateway Action                            |
| ---------------------- | --------------------------------------- | ------------------------------------ | -------------- | ----------------------------------------- |
| **Clean Match**        | "Buy laptop under ₹30,000"              | Laptop — ₹28,500                     | `200 APPROVED` | Executes `razorpay.Client.order.create()` |
| **Category Violation** | "Buy laptop under ₹70,000, no warranty" | Laptop — ₹65,000 + Warranty — ₹9,000 | `400 BLOCKED`  | Prevents checkout and logs violation      |
| **HITL Overage**       | "Buy laptop under ₹70,000"              | Upgraded Laptop — ₹71,400 (2% over)  | `200 HOLD`     | Pauses transaction until human approval   |

---

# API Reference

### `GET /health`

Service health check.

---

### `POST /v1/orders`

Interceptor endpoint that evaluates the checkout payload against the signed intent policy.

Possible outcomes:

* `APPROVED`
* `BLOCKED`
* `HOLD`

---

### `POST /v1/escalations/{escalation_id}/decision`

Decision endpoint used for human approval callbacks when a transaction is in the `HOLD` state.

---

### `GET /v1/audit-trail`

Fetches transaction and policy evaluation audit logs.

---

# Example Intent Policy

A natural-language request such as:

```text
Buy me a laptop under ₹70,000.
Do not purchase a warranty or accessories.
```

can be compiled into a structured policy similar to:

```json
{
  "max_budget": 70000,
  "required_categories": [
    "laptop"
  ],
  "prohibited_categories": [
    "warranty",
    "accessory"
  ],
  "negative_keywords": [
    "extended warranty",
    "protection plan"
  ],
  "tolerance_percent": 5
}
```

The policy is then signed using **HMAC-SHA256** before being passed to the transaction evaluation layer.

---

# Security Model

IntentGuard separates **intent compilation**, **policy signing**, and **transaction evaluation**:

```text
User Intent
     │
     ▼
Gemini Intent Compiler
     │
     ▼
Structured Policy
     │
     ▼
HMAC-SHA256 Signature
     │
     ▼
Cart Evaluation
     │
     ├──────────► APPROVED
     │
     ├──────────► BLOCKED
     │
     └──────────► HOLD
                    │
                    ▼
              Human Decision
```

This architecture helps prevent an agent from silently modifying the user's original purchasing constraints before checkout.

---

# Protocol & Standards Alignment

IntentGuard is designed around concepts from emerging **agentic commerce and verifiable intent** standards:

* **Intent-based authorization**
* **Cryptographically verifiable policies**
* **Cart-level verification**
* **Human-in-the-loop authorization**
* **Policy enforcement at payment boundaries**

The system is designed to complement payment infrastructure such as the Razorpay Orders API by adding a semantic intent verification layer before order creation.

---

# Future Enhancements

* Persistent database-backed audit logs
* WhatsApp-based HITL approval workflows
* Policy versioning and replay protection
* Agent identity verification
* Multi-agent transaction support
* Merchant-side policy metadata
* Advanced fraud and anomaly detection
* Dashboard analytics for policy violations
* Support for additional payment gateways

---

# Limitations

* **LLM Interpretation:** Gemini 2.5 Flash may occasionally misinterpret ambiguous or incomplete user instructions.
* **Semantic Matching:** Product names and categories vary across merchants, which can affect item-level verification.
* **External Dependencies:** The system depends on Gemini and Razorpay APIs, so outages or rate limits may affect transactions.
* **HITL Security:** The current approval flow is prototype-level and would require stronger authentication and replay protection for production.
* **Payment Integration:** The current implementation is focused on the Razorpay Orders API.
* **Production Scaling:** High-volume deployment would require persistent storage, distributed state management, monitoring, and additional fault tolerance.

---

## License

This project is a prototype / demonstration of **semantic intent verification for agentic commerce**.
