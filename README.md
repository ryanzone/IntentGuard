# PayPal IntentGuard

> **Real-Time Semantic Intent Verification Proxy & Policy Enforcement Gateway for Agentic Commerce**

[![PayPal API](https://img.shields.io/badge/PayPal-v2%2Forders-blue)](https://developer.paypal.com)
[![Python](https://img.shields.io/badge/Python-3.11-green)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)](https://fastapi.tiangolo.com)
[![OpenRouter API](https://img.shields.io/badge/AI-OpenRouter%20Nemotron%20120B-orange)](https://openrouter.ai)
[![Security](https://img.shields.io/badge/Security-HMAC%20SHA--256-red)](https://en.wikipedia.org/wiki/HMAC)

---

## Executive Summary

Autonomous AI shopping agents frequently make purchases on behalf of consumers. However, standard payment gateway rails primarily enforce flat spending caps (e.g., total price ≤ ₹70,000). They cannot evaluate natural-language constraints or inspect individual cart line items to determine whether a transaction actually aligns with the user's original instructions.

**PayPal IntentGuard** acts as an intelligent pre-authorization gateway proxy sitting in front of PayPal's `POST /v2/orders` API.

It dynamically:

* Compiles natural-language user instructions into cryptographically signed JSON policy envelopes.
* Inspects individual cart line items for unauthorized products, accessories, warranties, and merchant upsells.
* Blocks transactions that violate explicit user intent.
* Introduces an asynchronous **Human-in-the-Loop (HITL)** `HOLD` state for ambiguous overages.
* Maintains an audit trail of policy decisions.

---

## Architecture & Protocol Alignment

PayPal IntentGuard is designed around emerging standards for **verifiable intent and agentic commerce**, including **Google AP2 (Intent/Cart Mandates)** and **Mastercard Verifiable Intent Frameworks**, while integrating directly with the PayPal API ecosystem.

```text
┌─────────────────────────┐
│ User Intent Prompt      │
│ "Buy laptop under ₹70k" │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ OpenRouter LLM (Nemotron) │
│ Intent Compiler         │
└───────────┬─────────────┘
            │
            │ Generates HMAC Policy
            ▼
┌─────────────────────────┐      Checkout Payload
│ Signed Policy Envelope  │ ─────────────────────────>
│ HMAC-SHA256             │
└─────────────────────────┘
                                                      
                              ┌─────────────────────────┐
                              │ PayPal IntentGuard    │
                              │ Proxy Interceptor       │
                              └───────────┬─────────────┘
                                          │
                 ┌────────────────────────┼────────────────────────┐
                 │                        │                        │
                 ▼                        ▼                        ▼
      ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
      │ STATUS: APPROVED    │  │ STATUS: BLOCKED     │  │ STATUS: HOLD        │
      ├─────────────────────┤  ├─────────────────────┤  ├─────────────────────┤
      │ Executes PayPal     │  │ Prevents Order      │  │ Dispatches WhatsApp │
      │ Order               │  │ Creation            │  │ Approval Link       │
      └─────────────────────┘  └─────────────────────┘  └─────────────────────┘
```

### Decision Flow

| Status     | Condition                      | Action                  |
| ---------- | ------------------------------ | ----------------------- |
| `APPROVED` | Cart matches user intent       | Creates PayPal order  |
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

The compiler uses **OpenRouter** with **Nemotron 3 Super 120B** to interpret the user's original intent.

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

The user receives an approval request before the transaction is allowed to continue.

### 5. Containerized Microservice

Built and deployed using **Docker and Docker Compose** for consistent local development and deployment.

---

## Tech Stack

| Component                   | Technology                         |
| --------------------------- | ---------------------------------- |
| Proxy Gateway               | Python 3.11, FastAPI, Uvicorn      |
| Intent Compiler             | OpenRouter API, Nemotron 3 120B  |
| Validation Engine           | Pydantic v2                        |
| Cryptographic Signing       | HMAC-SHA256                        |
| Payment Gateway Integration | PayPal Python SDK                |
| Escalation Service          | Twilio SDK, WhatsApp Webhooks      |
| Containerization            | Docker, Docker Compose             |

---

## Directory Structure

```text
├── apps
│   ├── dashboard
│   │   ├── Dockerfile
│   │   ├── app.py
│   │   └── requirements.txt
│   └── proxy
│       ├── app
│       │   ├── api
│       │   │   ├── __init__.py
│       │   │   ├── escalation.py
│       │   │   └── routes.py
│       │   ├── compiler
│       │   │   ├── __init__.py
│       │   │   └── intent_engine.py
│       │   ├── core
│       │   │   ├── __init__.py
│       │   │   └── config.py
│       │   ├── evaluator
│       │   │   ├── __init__.py
│       │   │   └── rules.py
│       │   ├── schemas
│       │   │   ├── __init__.py
│       │   │   └── policy.py
│       │   ├── services
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
├── packages
│   └── shared-types
│       └── policy.schema.ts
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
* PayPal test API credentials
* OpenRouter API key
* Twilio credentials if WhatsApp escalation is enabled

---

## 2. Environment Setup

Create a `.env` file in `apps/proxy/` or the project root:

```env
OPENROUTER_API_KEY="sk-or-v1-your-openrouter-key-here"

PAYPAL_CLIENT_ID="YOUR_PAYPAL_CLIENT_ID"
PAYPAL_CLIENT_SECRET="YOUR_PAYPAL_CLIENT_SECRET"

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

| Scenario               | Input Prompt                            | Cart Contents                        | Proxy Result   | Gateway Action                                   |
| ---------------------- | --------------------------------------- | ------------------------------------ | -------------- | ------------------------------------------------ |
| **Clean Match**        | "Buy laptop under ₹30,000"              | Laptop — ₹28,500                     | `200 APPROVED` | Executes `PayPalHttpClient.do_create_order()`        |
| **Category Violation** | "Buy laptop under ₹70,000, no warranty" | Laptop — ₹65,000 + Warranty — ₹9,000 | `400 BLOCKED`  | Prevents checkout and logs violation             |
| **HITL Overage**       | "Buy laptop under ₹70,000"              | Upgraded Laptop — ₹71,400 (2% over)  | `200 HOLD`     | Dispatches approval webhook; resumes on approval |

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
OpenRouter Intent Compiler
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

The system is designed to complement payment infrastructure such as the PayPal Orders API by adding a semantic intent verification layer before order creation.

---

# Future Enhancements

* Persistent database-backed audit logs
* Production-grade WhatsApp approval workflows
* Policy versioning and replay protection
* Agent identity verification
* Multi-agent transaction support
* Merchant-side policy metadata
* Advanced fraud and anomaly detection
* Dashboard analytics for policy violations
* Support for additional payment gateways

---

## License

This project is a prototype / demonstration of **semantic intent verification for agentic commerce**.
