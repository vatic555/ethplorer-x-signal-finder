# Source Documents Inventory

This index inventories the static knowledge reviewed by Task 005D. A canonical URL establishes source identity, while the source metadata and catalog links establish reviewed evidence. Static documents live under [`sources/`](sources/) and satisfy the identity, provenance, normalization, and metadata contract in [`README.md`](README.md).

## Current Inventory

- [`../docs/project-spec.md`](../docs/project-spec.md) - canonical local product and technical specification; it defines project behavior but is not capability evidence.
- [`terminology/shared-analytics.md`](terminology/shared-analytics.md) - shared terminology placeholders with upstream provenance and pending review.
- [`terminology/x-signal.md`](terminology/x-signal.md) - maintained project terminology contracts.
- [Shared analytics upstream terminology](https://github.com/vatic555/ethereum-top-addresses-pipeline/blob/main/docs/terminology.md) - pending upstream source; no definitions have yet been imported or reviewed locally.

## Canonical Ethplorer Article Sources

`sources/posts/` is the canonical location for the current 17-article archive. Task 005D read and double-checked every source and inspected all 11 managed informative images. Each source has one unique H1, a non-empty coherent body, a distinct content signature, and `source_type = ethplorer_article`. All 17 sources are substantively reviewed with explicit claims and limitations. Reviewed status confirms what the source says, not that historical values or product-status claims remain current.

| source_id | file | title | status |
|---|---|---|---|
| `ethplorer.article.bulk-api-monitor` | [`bulk-api-monitor.md`](sources/posts/bulk-api-monitor.md) | Ethplorer Bulk API Monitor: A Better Way of Tracing Ethereum Tokens | reviewed |
| `ethplorer.article.crypto-market-trends-analyze-tool` | [`crypto-market-trends-analyze-tool.md`](sources/posts/crypto-market-trends-analyze-tool.md) | What’s your go-to tool for analyzing crypto market trends? | reviewed |
| `ethplorer.article.dyor-like-a-pro-with-ethplorer-charts` | [`dyor-like-a-pro-with-ethplorer-charts.md`](sources/posts/dyor-like-a-pro-with-ethplorer-charts.md) | DYOR like a pro \| All you need with Ethplorer charts 🤓 | reviewed |
| `ethplorer.article.ethereum-rich-list-aggregated-usd-part-1` | [`ethereum-rich-list-by-aggregated-usd-holdings-part-1.md`](sources/posts/ethereum-rich-list-by-aggregated-usd-holdings-part-1.md) | Ethereum Rich List by Aggregated USD Holdings: Where Capital Really Resides | reviewed |
| `ethplorer.article.ethereum-rich-list-aggregated-usd-part-2` | [`ethereum-rich-list-by-aggregated-usd-holdings-part-2.md`](sources/posts/ethereum-rich-list-by-aggregated-usd-holdings-part-2.md) | Ethereum Rich List by Aggregated USD Holdings: How Capital Moves and Where Risks Emerge | reviewed |
| `ethplorer.article.ethereum-tokens-extended-search` | [`ethereum-tokens-extended-search.md`](sources/posts/ethereum-tokens-extended-search.md) | 🔍 Off the scale crypto explorer / Ethplorer extended search 🔎 | reviewed |
| `ethplorer.article.keep-your-deals-clean` | [`keep_your_deals_clean.md`](sources/posts/keep_your_deals_clean.md) | Keep your deals clean 😷  Ethplorer Features updates 📫 | reviewed |
| `ethplorer.article.lost-in-transactions` | [`lost_in_transactions.md`](sources/posts/lost_in_transactions.md) | Lost in transactions. Crypto accounting with Ethplorer. | reviewed |
| `ethplorer.article.shiny-new-api-panel` | [`shiny_new_api_panel.md`](sources/posts/shiny_new_api_panel.md) | Developers, this one’s for you 🚀 Shiny new API Panel 🤓 | reviewed |
| `ethplorer.article.the-2024-year-crypto-race` | [`the-2024-year-crypto-race.md`](sources/posts/the-2024-year-crypto-race.md) | Looking Back at 2024: The Year Crypto Raced Ahead 🚀 | reviewed |
| `ethplorer.article.watching-eth-addresses-service` | [`watching-eth-addresses-service.md`](sources/posts/watching-eth-addresses-service.md) | Watch your bag 👀 Ethplorer's watching service to make your life easier | reviewed |
| `ethplorer.article.what-are-erc-20-tokens` | [`what-are-erc-20-tokens.md`](sources/posts/what-are-erc-20-tokens.md) | What Are ERC-20 Tokens? Find Out Now as the Decentralized Finance Industry Takes Off | reviewed |
| `ethplorer.article.ethereum-capital-outside-eth-and-defi-self-issued` | [`ethereum-capital-outside-eth-and-defi-self-issued.md`](sources/posts/ethereum-capital-outside-eth-and-defi-self-issued.md) | 58% of Ethereum’s Capital Lives Outside ETH Balances - And Half of DeFi Capital Is Self-Issued | reviewed |
| `ethplorer.article.beincrypto-interview-ethereum-rich-list-altseason` | [`beincrypto-interview-ethereum-rich-list-altseason.md`](sources/posts/beincrypto-interview-ethereum-rich-list-altseason.md) | BeInCrypto Interview - Ethereum Rich List by Aggregated USD Holdings. Mathematically proven - Altseason Already Happened | reviewed |
| `ethplorer.article.cryptodaily-ethereum-rich-list-part-1` | [`cryptodaily-ethereum-rich-list-part-1.md`](sources/posts/cryptodaily-ethereum-rich-list-part-1.md) | CryptoDaily Part 1 - The Real Top You’ve Never Seen: Inside Ethereum Rich List by Aggregated USD Holdings | reviewed |
| `ethplorer.article.cryptodaily-ethereum-rich-list-part-2` | [`cryptodaily-ethereum-rich-list-part-2.md`](sources/posts/cryptodaily-ethereum-rich-list-part-2.md) | CryptoDaily - Ethereum Rich List by Aggregated USD Holdings (Part 2): How Capital Moves and Where Risk Emerges | reviewed |
| `ethplorer.article.beincrypto-interview-questions-and-answers-altseason` | [`beincrypto-interview-questions-and-answers-altseason.md`](sources/posts/beincrypto-interview-questions-and-answers-altseason.md) | Questions and answers - BeInCrypto Interview: Mathematically proven - Altseason Already Happened. | reviewed |

The five DOCX conversions preserve original filenames and SHA-256 digests in front matter. Sixteen meaningful image instances were consolidated into 11 unique local image assets stored directly in [`sources/posts/assets/`](sources/posts/assets/). The Q&A document's repeated two-pixel divider was omitted as a conversion artifact. Task 005D extracted 11 compact evidence-backed capability rows and the initial 76-row derivative vocabulary. Task 005D.1 refined the vocabulary to 91 precision-reviewed rows without changing those capabilities; see [`review_summary.md`](review_summary.md).

## Other Knowledge Classes

- First-party editorial corpus - implemented separately in PostgreSQL by Task 005C for historical and future Ethplorer and Binplorer X Posts; it may support style, reaction patterns, and prior public positioning only and is intentionally outside this static source inventory.
- Dynamic analytical evidence - not copied here; a future adapter may query dated, scoped, provenance-rich snapshots or comparisons from `ethereum-top-addresses-pipeline` on demand.

Neither class can silently establish a product capability. Capability records continue to require reviewed supporting static `source_id` values.

## Not Present in the Public Repository

- No private, internal, confidential, or licensed document text.
- No reviewed static Binplorer product evidence.
- No private operational first-party X content or per-Post mappings.
- No generated summaries presented as source material.

Future source documents must be added to this inventory by stable `source_id`. A heading, URL, TODO, or directory name never establishes a capability by itself.
