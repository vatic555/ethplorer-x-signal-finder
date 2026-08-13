+++
source_id = "ethplorer.article.beincrypto-interview-questions-and-answers-altseason"
title = "Questions and answers - BeInCrypto Interview: Mathematically proven - Altseason Already Happened."
source_type = "ethplorer_article"
products = []
networks = []
approved_provenance = "User-provided DOCX import: Questions and answers - BeInCrypto Interview- Mathematically proven - Altseason Already Happened.docx"
source_file_sha256 = "84b6d5a4cab98bb3391b5d7ab0bfb3202f63add407388a20fdd7a1e6f8c1e284"
review_status = "pending"
confirms = []
limitations = []
+++

# Questions and answers - BeInCrypto Interview: Mathematically proven - Altseason Already Happened.

## 🔹 Block 1. Entry and framing

### 1. We saw at the conference that you discussed the new Ethereum Rating with the community - could you tell us more about it? What is the Aggregated Ethereum Rich List and why did you build it?

A: [Ethplorer.io](http://ethplorer.io/) rebuilt the Ethereum rich list by ranking addresses not by ETH alone, but by total USD value - including ETH, ERC-20 tokens and stablecoins. This [Aggregated Ranking of Ethereum addresses](https://ethplorer.io/rich-list) is based on totalBalanceUsd, unlike traditionally sorted addresses by ethBalanceUsd.

The goal was simple: ETH-only rankings no longer reflect real economic power on Ethereum.

### 2. What was fundamentally wrong with the traditional ETH-based rankings?

A: ETH-only rankings ignore the majority of capital. Today, about 66% of value sits outside ETH - mostly in tokens and stablecoins - so ETH-based lists give a distorted view of who actually controls liquidity and risk.

### 3. What was the biggest insight when you first rebuilt the ranking?

A: The biggest shift was that the entire hierarchy changes. The same Top-10,000 addresses hold almost 3× more capital when tokens are included, and many “invisible” players suddenly become dominant.

### 4. Vitalik Buterin envisioned Ethereum as a platform where code manages value. Do you think that vision has been realized?

A: Increasingly, it’s not individuals but systems. Smart contracts, exchanges and liquidity hubs now control a large share of capital, meaning Ethereum is no longer whale-centric - it’s entity-centric.

But what’s important is that we can now measure it. In ETH-based rankings, this shift was almost invisible. But once we look at aggregated balances, it becomes clear that a large share of capital is already controlled by smart contracts - DeFi, bridges, liquidity pools - roughly 28% of total capital. So it’s not just a vision anymore - it’s an observable structural reality.

## 🔹 Block 2. Altseason / main narrative

### 6. You say “altseason already happened” - what do you mean?

A: Altseason didn’t disappear - it shifted from price to balance sheets. Capital moved into tokens and protocols without explosive price growth, so the shift happened structurally, not visibly on charts.

### 7. Why didn’t the market notice this shift?

A: Because people watch prices, not balance composition. While charts were flat, capital was quietly redistributing across tokens, stablecoins and smart contracts.

### 8. So are we looking at a different kind of market cycle now?

A: Yes - we’re moving from price discovery to power discovery. The key question is no longer “what is the price”, but “who controls liquidity and risk”.

## 🔹 Block 3. What in practice.

### 9. What does this give to an investor in practice?

A: It changes how you evaluate risk. Instead of focusing on price or market cap, you look at what a balance consists of - whether it’s real external capital or self-issued tokens.

### 10. How should analysts rethink their approach using this data?

A: Analysts need to shift from narratives to composition analysis - looking at aggregated balances, capital sources and dependencies, not just TVL or token price.

### 11. Does this change how we should interpret TVL and market cap?

A: Yes. Both metrics can be distorted by self-issued tokens. Without understanding balance composition, you can overestimate real economic strength.

## 🔹 Block 4. PPI (Printing-Press Index)

### 12. What is PPI and why did you introduce it?

A: Printing-Press Index (PPI) measures how much of a portfolio consists of a project’s own token. It helps distinguish real capital from internally generated value. To separate real capital from self-minted tokens:

PPI = Own tokens (USD) by project / Total tokens (USD) by project - the share of a project’s own tokens in its portfolio.

### 13. What did PPI reveal about DeFi, CEX, bridges and L2s?

A: DeFi shows significantly higher reliance on self-issued tokens compared to centralized players - around 2× higher on average (14.7% vs 6.9%). Bridges and L2s showing even higher PPI (34.8% PPI), partly structural - they require staking native tokens for liquidity. But this shifts risk toward token price dependency rather than removing it.

### 14. At what point does PPI become risky?

A: Below ~20% it’s normal. Above ~40-50%, the system becomes fragile and exposed to reflexive collapse dynamics.

### 16. Can you give a real-world examples of high PPI risk?

A: The UST-LUNA collapse is the extreme case - where the system was almost entirely backed by its own token, leading to a death spiral.

Or FTX - even ~40% exposure to FTT was enough to trigger collapse under stress, showing that high PPI doesn’t need to be extreme to be dangerous.

## ➖ Block 6. Structural shifts

### 23. Does ETH still represent the core of Ethereum’s economy?

A: No. ETH is still important, but it’s no longer the dominant store of value within large portfolios. Only 34%. 66% of top-holder capital sits outside ETH - in tokens.

### 24. What surprised you the most in terms of address dynamics?

A: The generational shift - most large addresses in the Aggregated Ranking are significantly newer, reflecting capital entering through DeFi and tokens. In the ETH-Top about one-third of wallets are over five years old. In the Aggregated ranking almost 60% are under two years old.

And Aggregated addresses about 25% more active, show larger balance changes and higher volatility - because they reflect real liquidity flows, not passive ETH holding.

## 🔹 Block 7. Methodology

### 26. How do you deal with fake or inflated token balances?

A: We apply liquidity filters - excluding balances that cannot realistically be sold without impacting the market.

Because without filtering, low-liquidity tokens can artificially inflate rankings and misrepresent real economic power. In crypto, it’s relatively easy to mint a token, assign it a price through thin trading, and create the illusion of large balances.

To address this, we apply a set of validation checks. We look at minimum trading activity - not just current, but also historical - validate market capitalization consistency, and assess whether the balance could realistically be liquidated in the market.

The logic is simple: if you can’t realistically sell your full position within about two weeks, that balance doesn’t represent real, liquid capital - and shouldn’t distort the ranking.

### 28. Before this interview, we looked at traditional Ethereum Rich List from well-known platforms - and one thing immediately stood out. The Beacon Deposit Contract appears to hold nearly 70% of all ethereum network. So are we really analyzing the behavior of just the remaining 30% of the market?

A: That’s exactly the problem with ETH-only rankings - they create a misleading picture. The Beacon contract is not a real holder; it’s a technical deposit registry for staking. The ETH there isn’t controlled by a single entity and cannot even be withdrawn from that address.

So when it shows up as “70% of the market” - around 83M ETH - it doesn’t reflect actual economic power or behavior (it's just a technical figure). If you look at the real picture, Active Staking is closer to ~39M ETH. And when we move to an Aggregated view - including liquid tokens and stablecoins - Active Staking account for just over 10% of the total ecosystem capital.

So no - we’re not analyzing 30% of the market. It turns out: 10% sits in staking, the other ~90% is where the market actually operates - where capital moves, trades and redistributes across the ecosystem.

## 🔹 Block 8. Meta

### 29. How long did it take to develop this ranking?

A: There’s no single timeline, because this wasn’t built as a standalone project. Ethplorer has been working for years on processing token-level data, focusing on USD valuation and filtering out low-quality assets.

At some point, the data quality and coverage reached a level where building a full aggregated ranking became possible - and that’s when we turned it into a structured product.

### 30. What was the hardest part?

A: Cleaning the data - especially handling spam tokens, price inconsistencies and entity aggregation.

### 31. What kind of feedback have you received from the community?

A: Strong interest and debate - especially because the ranking challenges widely accepted assumptions about Ethereum.

### 32. Have you discussed this with industry players at PBW?

A: Yes, and reactions were mixed - from curiosity to skepticism - which is expected when you introduce a new analytical lens.

32.1. Question for BitOK?

32.2. Question for [https://l2beat.com](https://l2beat.com/) ?

32.3 Question for Dune?

## 🔹 Block 9. The final narrative.

### 34. What is the main takeaway from your research?

A: Ethereum’s rich list is no longer about wealth - it’s about capital flows and risk distribution.

### 35. If you had to summarize the shift in one sentence?

A: We moved from tracking balances to understanding capital structure.
