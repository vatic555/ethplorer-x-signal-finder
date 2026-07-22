# Draft Generator

## Purpose

Create a concise, useful draft or action note for an accepted Opportunity while preserving the evidence, tone, and limits established by the Opportunity Gate.

## Required Inputs

- An Opportunity with an `accepted` Gate decision
- Exact documented Ethplorer asset or capability and supporting sources
- Verified facts, permitted inferences, unresolved uncertainty, audience, and action type
- Relevant style and platform constraints

## Required Outputs

Return structured data containing the Opportunity ID, action type, draft text or BizDev action, factual claims with evidence references, disclosed uncertainty, and optional Visual Brief recommendation with rationale.

## Rejection Behavior

Return no draft if the Gate decision is absent or not `accepted`, the exact asset is unsupported, evidence is insufficient, or the draft would require generic commentary, forced promotion, or invented claims. Explain the blocking reason.

## Evidence and Uncertainty Rules

Use only verified facts and clearly permitted, qualified inferences. Do not hide unresolved uncertainty. Do not add stronger product claims than the knowledge base supports. Use short hyphens instead of em dashes in public-facing copy. Publication remains a human action.
