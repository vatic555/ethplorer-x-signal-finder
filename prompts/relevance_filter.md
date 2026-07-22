# Preliminary Relevance Filter

## Purpose

Identify source posts worth further analysis. Relevance is only a routing decision and is not proof of a Signal or Opportunity.

## Required Inputs

- Source post ID, text, author, timestamp, and available conversation references
- Supported products, networks, and permitted relevance boundaries
- Relevant reviewed terminology, if any

## Required Outputs

Return structured data containing `post_id`, `decision` (`keep`, `reject`, or `uncertain`), concise `reasons`, matched topics or networks, `evidence`, `inferences`, `uncertainties`, and context questions.

## Rejection Behavior

Reject generic crypto news, unrelated-network events without a permitted connection, empty engagement bait, and content with no plausible audience-relevant information question. Do not create an Opportunity or draft.

## Evidence and Uncertainty Rules

Quote or point to the exact input evidence behind each reason. Keep verified facts separate from inference. Use `uncertain` when missing context could materially change the decision; never fill gaps with assumed product capabilities.
