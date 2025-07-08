# Claims Agent

Manages insurance claim inquiries, status checks, and new claim filing.

## What it does
- Files new insurance claims
- Checks claim status by claim number
- Provides claim history for policies

## Quick Start
```bash
make start-claims
```

## Configuration
```bash
CLAIMS_LANGUAGE_MODEL=lm_studio/gemma-3-12b-it  # Or openai/gpt-4o-mini
```

## Tools
- `get_claim_status(claim_number)` - Returns status and next steps
- `file_new_claim(policy_number, incident_details)` - Creates new claim
- `get_claim_history(policy_number)` - Lists all claims for a policy

## Testing
```bash
make test-claims-agent
```