# Billing Agent

Handles payment and financial inquiries for insurance policies.

## What it does
- Retrieves billing info (premium amounts, due dates, payment status)
- Updates payment information
- Requires policy number for privacy

## Quick Start
```bash
make start-billing
```

## Configuration
```bash
BILLING_LANGUAGE_MODEL=lm_studio/gemma-3-12b-it  # Or openai/gpt-4o-mini
```

## Tools
- `get_billing_info(policy_number)` - Returns premium, due date, status
- `update_billing_info(policy_number, field, value)` - Updates payment info

## Testing
```bash
make test-billing-agent
```