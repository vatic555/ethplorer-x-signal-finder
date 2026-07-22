# Signal Clustering

## Purpose

Group retained posts that concern the same underlying event, claim, entity, or tightly related discussion and produce evidence-linked candidate Signals.

## Required Inputs

- Retained posts with stable IDs, text, authors, timestamps, and conversation references
- Existing open event clusters, if supplied
- Reviewed project terminology

## Required Outputs

Return structured clusters with member post IDs, a neutral cluster label, grouping evidence, disputed or conflicting claims, time bounds, candidate Signal summaries, `inferences`, `uncertainties`, and confidence in the grouping.

## Rejection Behavior

Do not group posts based only on broad crypto-topic similarity. Leave a post unclustered when the shared event or claim cannot be supported. Do not create Opportunities or drafts.

## Evidence and Uncertainty Rules

Preserve all source IDs. Distinguish facts stated by sources from model-inferred relationships. Record conflicting evidence and use uncertainty rather than forcing a cluster.
