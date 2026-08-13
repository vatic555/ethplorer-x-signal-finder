+++
source_id = "ethplorer.article.bulk-api-monitor"
title = "Ethplorer Bulk API Monitor: A Better Way of Tracing Ethereum Tokens"
source_type = "ethplorer_article"
products = []
networks = []
approved_provenance = "Canonical Ethplorer article archive supplied in knowledge/sources/posts/"
review_status = "pending"
confirms = []
limitations = []
+++

# Ethplorer Bulk API Monitor: A Better Way of Tracing Ethereum Tokens

Explorers are blockchain search engines which enable the tracking and gathering of on-chain details and statistics.

Because public chains are transparent, developers can use blockchain explorers to access and even extract different details related to wallets, transactions, rich lists, messages, and so forth. 

### The Ethplorer Bulk API Monitor

The Ethplorer team is introducing the [_Ethplorer Bulk API Monitor_](https://docs.ethplorer.io/monitor) an optimized tool for tracking an infinite number of Ethereum tokens and addresses, requiring minimal resources and coding. All that's needed is to add an address or a monitoring contract. Once the addresses are added to the tracking list, Bulk API returns all the operations related to them as they appear in the Ethereum blockchain.

[Image: ethplorer-api.jpg]![](ethplorer-api.jpg "=1327x")

The portal gives new powers to wallet developers, addresses monitoring services, exchanges, airdrops, and all platforms/service providers that deal with many Ethereum-based token addresses.

Compared to other solutions, Ethplorer's Bulk API Monitor addresses a chronic issue with address monitoring through its capacity for tracking addresses on a users list on the Ethereum blockchain in real-time - doing so efficiently and with minimal overhead. Developers are also given the flexibility to track Ether or ERC-20 transactions for specific addresses.

These results can then be easily filtered and exported, based on the customer's analytics needs. For instance, one can use Bulk API Monitor to track the flow of tokens to crypto exchanges to forecast sell-offs and price rallies. 

Using the Ethplorer Bulk API Monitor, one can track tokens or transactions for a list of addresses. This service targets developers, but Ethplorer also offers a Watching Service for regular crypto users, with automated alerts via email and Telegram. It's also based on the Bulk API.

### How it Works

To track transactions related to specific addresses, a user needs first to create a list (pool) of these addresses. Next, the developer can ask "getPoolLastOperations" every minute, setting the period for 3 to 5 minutes, to get a list of transactions for the whole pool. Each request can return up to 10,000 transactions for the address involved in the requested period, including details of each transaction and values in the tokens and balances for participating addresses. This way, there isn't a need to make additional requests. 

Alternatively, to track a limited number of tokens, the user can add their contract addresses to the pool. Once done, the Bulk API Monitor will return all the transactions with these tokens, regardless of which addresses involved. It is also possible to manually add addresses to the same pool and get all the transactions for these addresses (and any ERC20 tokens) in the same response, saving time.
[Image: monitor-lib.png]![](monitor-lib.png "=1327x")

Every API Key used is billed depending on the number of transactions tracked in every pool. Depending on the number of queries per month, a user can use the tool for free or subscribe to a premium plan.

### Billing Plans

The daily transaction count on the Ethereum blockchain is approximately 1 million, and the importance of transaction tracking for developers is vital. This importance is exactly why Ethplorer's Bulk API offers a flexible range of pricing plans, depending on developer needs. 

Depending on developer requirements, when it comes to data from transactions, subscription plans can range anywhere from $0-699 per month. These prices depend on the number of addresses and transactions the project needs to track. The free plan should sufficiently satisfy the needs of most smaller projects, while larger exchanges and wallets will appreciate the opportunity to monitor the entire Ethereum blockchain for a fixed fee.

Of course, Ethplorer isn't the only Ethereum tracking service out there. What makes it unique is its ability to track any number of addresses and transactions - millions if needed. This is possible with the introduction of Bulk API Monitor - a specialized developer tool that will fit the needs of crypto projects of any size.

[Cointelegraph](https://cointelegraph.com/press-releases/ethplorer-debuts-bulk-api-monitor-able-to-track-millions-of-addresses)
[Cryptodaily](https://cryptodaily.co.uk/2020/12/ethplorer-launches-bulk-api-monitor-the-first-tool-capable) 
[Coinmarketcap](https://coinmarketcap.com/headlines/news/ethplorer-launches-bulk-api-monitor-the-first-tool-capable/)
[Coinspeaker](https://www.coinspeaker.com/ethplorer-bulk-api-monitor/)
[Finance Yahoo](https://finance.yahoo.com/news/ethereum-token-browser-ethplorer-launches-163400942.html)

