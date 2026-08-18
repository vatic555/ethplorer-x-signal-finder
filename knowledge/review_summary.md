# Task 005D Knowledge Review Summary

Review date: 2026-08-17

This public-safe summary records aggregate review results only. It contains no first-party X Post bodies, referenced Post bodies, raw JSON, or per-Post mappings.

## Static review

- Sources discovered, read completely, and double-checked: 17
- Managed informative images inspected: 11
- Review statuses: 17 reviewed, 0 pending, 0 deprecated
- Canonical Ethplorer article routes: 12
- Approved derivative or interview sources without a canonical Ethplorer article route: 5

`reviewed` means the source is reliable evidence of what that source says. It does not make every statement current. Historical figures and product-status statements remain limited by their source date and wording.

## Reviewed capabilities

The compact catalog contains 11 capabilities:

| Capability | Supporting source IDs | Important limitation |
|---|---|---|
| Address portfolio inspection | `ethplorer.article.what-are-erc-20-tokens`; `ethplorer.article.dyor-like-a-pro-with-ethplorer-charts` | Does not prove ownership, identity, price accuracy, tax treatment, or current availability. |
| Token and address search | `ethplorer.article.ethereum-tokens-extended-search` | Search ranking and labels do not prove safety or completeness. |
| Token and address charts | `ethplorer.article.dyor-like-a-pro-with-ethplorer-charts`; `ethplorer.article.crypto-market-trends-analyze-tool` | Charts do not predict prices; current metric coverage requires verification. |
| Token activity and holder analytics | `ethplorer.article.crypto-market-trends-analyze-tool`; `ethplorer.article.the-2024-year-crypto-race` | Does not establish legitimacy, liquidity, adoption, or an investment score. |
| Address and transaction tags and notes | `ethplorer.article.keep-your-deals-clean`; `ethplorer.article.ethereum-tokens-extended-search` | Does not prove identity, completeness, permanence, or comprehensive fraud detection. |
| Transaction and annotation export | `ethplorer.article.keep-your-deals-clean`; `ethplorer.article.lost-in-transactions` | Formats and current availability require verification; not a tax or accounting guarantee. |
| Watching Service | `ethplorer.article.watching-eth-addresses-service`; `ethplorer.article.bulk-api-monitor` | Delivery, channels, event coverage, limits, and availability are historical claims. |
| API Panel | `ethplorer.article.shiny-new-api-panel` | Current endpoints, quotas, pricing, authentication, and service levels are not established. |
| Bulk API Monitor | `ethplorer.article.bulk-api-monitor`; `ethplorer.article.shiny-new-api-panel` | Current capacity, latency, contract, pricing, and scale claims require current documentation. |
| Aggregated Ethereum Rich List | `ethplorer.article.ethereum-rich-list-aggregated-usd-part-1`; `ethplorer.article.ethereum-rich-list-aggregated-usd-part-2`; `ethplorer.article.cryptodaily-ethereum-rich-list-part-1` | Historical snapshot values are not current; filters and entity coverage are not fully reproducible from the articles alone. |
| Balance composition and PPI analysis | `ethplorer.article.ethereum-rich-list-aggregated-usd-part-2`; `ethplorer.article.ethereum-capital-outside-eth-and-defi-self-issued`; `ethplorer.article.beincrypto-interview-questions-and-answers-altseason` | Not a generic risk score or AML capability; current values require Task 005E dynamic evidence. |

No generic DeFi liquidity, AML, fraud scoring, price prediction, or generic risk-scoring capability was created.

## First-party corpus analysis

The complete local PostgreSQL corpus was analysed without an X or web request:

- First-party Posts: 378 rows and 378 distinct IDs
- Ethplorer: 156 originals, 121 replies, 24 quotes, 38 reposts
- Binplorer: 14 originals, 11 replies, 2 quotes, 12 reposts
- Combined: 170 originals, 132 replies, 26 quotes, 50 reposts
- Direct referenced context: 187 available, 17 unavailable
- Exact stored X-to-canonical-article links: 8 Posts across 5 reviewed static source IDs

Originals, replies, and quote commentary contributed authored language. Reposts were inspected only for topic interest and were excluded from authored-style counts. Available reply, quote, and repost references contributed separate audience or context language. The 17 unavailable contexts remain unknown and were not interpreted as irrelevant.

## Task 005D vocabulary baseline

- Total triggers: 76
- By category: 27 capability, 12 analytics concept, 7 network, 5 contextual, 4 user problem, 4 user intent, 4 project entity, 4 BizDev integration, 4 exclusion context, 3 infrastructure, 2 product
- By role: 59 positive trigger, 13 context only, 4 negative context
- By review status: 46 reviewed, 30 candidate, 0 deprecated
- With reviewed static basis: 65
- Informed by non-repost first-party authored text: 38
- Informed by available referenced or audience context: 28
- With exact linked-article basis: 9

The counts above indicate whether a vocabulary row has each provenance class. They are not frequencies added together, and frequency did not determine inclusion or review status.

Exact article linkage joins a stored resolved URL to normalized source metadata. It is provenance for public wording, while the reviewed static source remains capability authority. No per-Post mapping is committed.

## Task 005D.1 precision correction

The precision review reduced broad standalone routing evidence while preserving all 11 reviewed capabilities:

- Current triggers: 91
- By category: 27 capability, 21 exclusion context, 12 analytics concept, 7 network, 4 contextual, 4 user problem, 4 user intent, 4 project entity, 3 BizDev integration, 3 infrastructure, 2 product
- By role: 53 positive trigger, 17 context only, 21 negative context
- By review status: 47 reviewed, 44 candidate, 0 deprecated
- With reviewed static basis: 64
- Informed by non-repost first-party authored text: 38
- Informed by available referenced or audience context: 27
- With exact linked-article basis: 9

The standalone rows `on-chain` and `exchange integration` were removed. `tags and notes`, `private tags`, `trade volume`, `market cap`, and `candlestick chart` were demoted to weak context-only evidence. `moving average` became normal negative context while remaining reviewed historical product evidence. The precise reviewed phrase `address tags` was added as a positive capability trigger.

Sixteen compact candidate negative-context rows were added for Solana and trader analysis, signal, execution, derivatives, and education language. Negative context is neither authoritative nor a hard reject, and it cannot override a strong positive capability or integration need. One or many context-only terms are insufficient for a future PASS. Task 005D.1 implements no runtime combination logic.

The read-only local precision check found one first-party occurrence of `address tags`. The other suggested tags, stablecoin, whale, and on-chain compounds had no exact occurrence in either inspected Post table, so they were not added mechanically. `candlestick chart` appeared in first-party wording but was still demoted because it is too trading-oriented to route a Post alone. No Post body or database export is included here.

## Deliberate exclusions and unresolved gaps

Generic high-frequency words such as `crypto`, `market`, `today`, `new`, `big`, `data`, `price`, `token`, and bare `API` were excluded because they would create excessive false positives. Historical numbers such as `$342B`, `$426B`, `$189B`, `$116.5B`, `58%`, `66%`, historical ranks, and historical PPI values were not made triggers.

Potentially useful but broad terms such as `BSC`, `EVM`, `DeFi`, `total supply`, and `whale` remain candidate or context-only language. Generic standalone `on-chain` is omitted. Negative-context terms do not override positive product, capability, integration, or user-problem evidence.

The largest unresolved gap is reviewed static Binplorer evidence. Binplorer first-party language supports candidate BNB Chain terminology and product wording, but it does not support a reviewed Binplorer capability row. Current Aggregated Rich List and PPI measurements are also unresolved until Task 005E reads dated structured upstream evidence.
