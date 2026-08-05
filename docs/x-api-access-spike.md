# X API Access Spike

Investigation date: 2026-08-04

## 1. Executive conclusion

Decision: `blocked pending credentials`

Official documentation indicates that both MVP sources are technically available through X API v2:

- the reverse chronological home timeline through `GET /2/users/{id}/timelines/reverse_chronological`, using user context for the same authenticated user;
- `@Ethplorer` mentions through `GET /2/users/{id}/mentions`, using app-only or user-context authentication for a visible account.

The documented request limits are sufficient for one or two manually started runs per day. However, no X credentials or completed owner authorization were available on the investigation date. Authentication, endpoint responses, pagination, refresh behavior, history sufficiency, checkpoint behavior, and billing have therefore not been validated live. Stage 2 remains In Progress and Stage 3 must not start.

The documentation-only evidence suggests a possible future `constrained-go`, primarily because the home timeline is limited to the most recent 3,200 Posts or seven days and the mentions timeline to 800 Posts. That is not the final spike decision.

## 2. Investigation date and sources

All sources below are official X documentation and were checked on 2026-08-04.

| Official source | What it supports |
|---|---|
| [Timelines overview](https://docs.x.com/x-api/posts/timelines/introduction) | Endpoint identities, home user-context requirement, OAuth options, and documented home and mentions history windows |
| [Timeline integration guide](https://docs.x.com/x-api/posts/timelines/integrate) | App-only versus user-context support, fields, 100-result pages, pagination procedure, filtering parameters, and volume limits |
| [Get Timeline reference](https://docs.x.com/x-api/users/get-timeline) | Exact home endpoint, authenticated-ID equality requirement, query parameters, response shape, and OAuth 2.0 access token requirement |
| [Get mentions reference](https://docs.x.com/x-api/users/get-mentions) | Exact mentions endpoint, parameters, fields, expansions, response metadata, and error shape |
| [X API v2 authentication mapping](https://docs.x.com/fundamentals/authentication/guides/v2-authentication-mapping) | Supported authentication modes and `tweet.read` plus `users.read` scopes |
| [OAuth 2.0 Authorization Code Flow with PKCE](https://docs.x.com/fundamentals/authentication/oauth-2-0/authorization-code) | PKCE configuration, two-hour access tokens, `offline.access`, token exchange, and refresh flow |
| [Pagination](https://docs.x.com/x-api/fundamentals/pagination) | Opaque tokens, reverse chronological order, partial-page behavior, and continuing until `next_token` is absent |
| [Fields](https://docs.x.com/x-api/fundamentals/fields) | Default Post fields and optional field behavior |
| [Expansions](https://docs.x.com/x-api/fundamentals/expansions) | Author, referenced Post, reply target, media, and mention expansions |
| [Response Codes and Errors](https://docs.x.com/x-api/fundamentals/response-codes-and-errors) | 401, 403, 404, 429, 5xx, partial errors, and rate-limit headers |
| [X API rate limits](https://docs.x.com/x-api/fundamentals/rate-limits) | Per-app and per-user request limits and 429 handling |
| [Pay-per-usage pricing](https://docs.x.com/x-api/getting-started/pricing) | Credit model, current public resource prices, Owned Reads, daily billing deduplication, and spending limits |
| [Usage and billing](https://docs.x.com/x-api/fundamentals/post-cap) | Two-million monthly Post-read cap and relationship between usage and billing |
| [Recent Search](https://docs.x.com/x-api/posts/search-recent-posts) | Seven-day recent-search alternative and checkpoint parameters |
| [Search operators](https://docs.x.com/x-api/posts/search/integrate/operators) | Official `@username` mention operator and distinction from `to:username` replies |
| [X Developer Agreement](https://docs.x.com/developer-terms/agreement) | Licensed-material restrictions, removal duties, termination deletion, commercial scope, and model-training restriction |
| [X Developer Policy](https://docs.x.com/developer-terms/policy) | Use-case disclosure, credential security, content compliance, privacy, display, and redistribution rules |
| [Developer Guidelines](https://docs.x.com/developer-guidelines) | Practical deletion deadlines, sensitive-data restrictions, redistribution limits, and AI/ML training warning |
| [Compliance event streams](https://docs.x.com/x-api/compliance/streams/introduction) | Offline-content freshness expectations and Enterprise compliance-event availability |

Prices and access conditions can change. The Developer Console remains authoritative for the specific app at the time of live testing.

## 3. Endpoint matrix

| Source | Endpoint | Authentication | Required scopes | Pagination | History window | Rate limit | Pricing | Live tested |
|---|---|---|---|---|---|---|---|---|
| Aleksandr home | `GET /2/users/{id}/timelines/reverse_chronological` | OAuth 2.0 Authorization Code with PKCE or OAuth 1.0a user context; `{id}` must equal authenticated user | `tweet.read`, `users.read`; `offline.access` for refresh token | `pagination_token` from `meta.next_token`; 1-100 per page | Most recent 3,200 Posts or seven days | 180 requests per user per 15 minutes; no app-only limit because app-only is unsupported | Public resource price is $0.005 per Post read; home is not listed as an Owned Read | No - credentials absent |
| `@Ethplorer` mentions | `GET /2/users/{id}/mentions` | OAuth 2.0 app-only bearer token, OAuth 2.0 PKCE user context, or OAuth 1.0a user context for visible content | App-only has no user scopes; PKCE uses `tweet.read`, `users.read` | `pagination_token`; 5-100 per page | Most recent 800 mentions | 450 requests per app or 300 per user per 15 minutes | $0.005 per Post read normally; $0.001 only when the documented Owned Read ownership and authenticated-ID conditions are met | No - credentials absent |
| Mentions fallback | `GET /2/tweets/search/recent?query=@Ethplorer` | App-only or supported user context | `tweet.read`, `users.read` for PKCE | `next_token`; up to 100 per page | Last seven days | Current app-specific limit must be verified in the Developer Console before adoption | $0.005 per Post read under current public pricing | No - direct endpoint must be tested first |

The recent-search fallback is not equivalent to the mentions timeline. It has a seven-day time boundary, query semantics rather than a user timeline contract, separate rate limits and billing behavior, and potential differences around protected, unavailable, edited, indexed, or delayed content. `@Ethplorer` is the official mention operator; `to:Ethplorer` matches replies only and is not a complete substitute.

## 4. Authentication findings

### Selected flow

Use OAuth 2.0 Authorization Code with PKCE for Aleksandr's home timeline. It provides documented fine-grained scopes, is supported by the home endpoint, and can issue a refresh token through `offline.access`. OAuth 1.0a is supported but adds signature and credential handling without a documented benefit for this spike.

Required scopes:

- `tweet.read`
- `users.read`
- `offline.access`

The access token lasts two hours by default. `offline.access` is required to receive a refresh token and operate one or two times per day without repeated interactive consent.

### App setup and one-time authorization

1. Create or select one approved app in the X Developer Console and ensure its disclosed use case includes internal X intelligence, human-reviewed draft assistance, and the intended storage behavior.
2. Enable OAuth 2.0.
3. Configure the app as a public/native PKCE client for this local diagnostic workflow.
4. Add the exact callback URI `http://127.0.0.1:8765/callback`, or set the same localhost URI in `X_REDIRECT_URI` and the Developer Console.
5. Enable read access and request only `tweet.read users.read offline.access`.
6. Put only `X_CLIENT_ID`, `X_HOME_USER_ID`, and optionally `X_ETHPLORER_USER_ID` in the ignored local `.env`. Do not commit values.
7. Sign in as Aleksandr and run:

   ```text
   python -m x_signal_finder x-api oauth-probe --source both --max-pages 2 --repeat-first-page
   ```

8. The command opens the official X authorization URL, starts one localhost callback for at most three minutes, validates state and S256 PKCE, exchanges the code, validates one refresh in memory, runs the requested probes, then closes the callback server and discards tokens and responses.

For the in-memory checkpoint experiment, record `oldest_post_id` from a successful probe and repeat the same command with `--checkpoint-id ID`. The probe paginates without writing the ID to PostgreSQL and reports whether it was reached, not reached within the probe page limit, or outside the exposed API window.

The helper never prints or persists access tokens, refresh tokens, response bodies, or Post text. For a token obtained outside the helper, set `X_ACCESS_TOKEN` locally and use `x-api probe`.

### Account boundaries

The home endpoint path ID must be the authenticated Aleksandr user ID. An Ethplorer token cannot retrieve Aleksandr's personalized home feed, and an Aleksandr token cannot retrieve a different user's home feed.

The direct mentions endpoint supports app-only authentication, so a separate `@Ethplorer` OAuth authorization is not documented as mandatory for public mentions. A separate Ethplorer authorization can still affect visibility, account-owned pricing, and access to protected content. These differences require live validation with the actual app and account configuration.

### Current blocker

No `X_CLIENT_ID`, `X_ACCESS_TOKEN`, `X_REFRESH_TOKEN`, `X_BEARER_TOKEN`, `X_HOME_USER_ID`, or `X_ETHPLORER_USER_ID` was available on 2026-08-04. No authorization URL was opened and no X endpoint was called.

## 5. Home timeline findings

- Availability: documented and supported in X API v2.
- Endpoint: `GET /2/users/{id}/timelines/reverse_chronological`.
- Account context: user context is mandatory and `{id}` must equal the authenticated user.
- Order: reverse chronological and not algorithmically ranked.
- Page size: 1-100.
- Pagination: pass `meta.next_token` back as `pagination_token` until no token remains.
- Stopping parameters: `since_id`, `until_id`, `start_time`, and `end_time` are documented. ID parameters take precedence over time parameters.
- Available window: most recent 3,200 Posts or seven days according to the current timeline documentation.
- Rate limit: 180 user-context requests per 15 minutes.
- Expected request feasibility: a full exposed window needs at most 32 pages at 100 Posts per page, below the request limit. This does not guarantee that the API window contains every Post since the previous run.
- Live result: not tested because owner authorization and credentials are absent.

## 6. Ethplorer mentions findings

- Availability: documented and supported in X API v2.
- Endpoint: `GET /2/users/{id}/mentions`.
- Authentication: app-only and user context are documented. For visible public mentions, OAuth by `@Ethplorer` is not documented as mandatory.
- Page size: 5-100.
- Pagination: `meta.next_token` becomes `pagination_token`.
- Stopping parameters: `since_id`, `until_id`, `start_time`, and `end_time`.
- Available window: most recent 800 mentions.
- Rate limit: 450 requests per app or 300 per user per 15 minutes.
- Deduplication: Post ID is the stable application key. Repeated resources are also normally deduplicated for billing within one UTC day, but X describes billing deduplication as a soft guarantee.
- Checkpoint feasibility: all pages newer than a stored Post ID can be requested, but the API does not document a positive signal that an older checkpoint fell outside the 800-Post window.
- Fallback: recent search with `query=@Ethplorer` is official but limited to seven days and must be independently evaluated for completeness, latency, access, cost, and indexing behavior.
- Live result: neither the direct endpoint nor search fallback was tested because credentials are absent.

## 7. Returned fields

### Requested diagnostic fields

By default X returns `id`, `text`, and `edit_history_tweet_ids`. The probe requests:

- Post fields: `attachments`, `author_id`, `conversation_id`, `created_at`, `entities`, `in_reply_to_user_id`, `lang`, `possibly_sensitive`, `public_metrics`, `referenced_tweets`, and `withheld`;
- expansions: `author_id`, `in_reply_to_user_id`, `referenced_tweets.id`, `referenced_tweets.id.author_id`, and `attachments.media_keys`;
- user fields: `id`, `name`, `username`, `created_at`, `protected`, and `verified`;
- media fields: `media_key`, `type`, `url`, `preview_image_url`, and `alt_text`.

`referenced_tweets` distinguishes `replied_to`, `quoted`, and `retweeted` relationships. `conversation_id` identifies the conversation root. Links and mentions are available through `entities`; media references are available through `attachments` and expansions. Response `meta` can contain `result_count`, `newest_id`, `oldest_id`, `next_token`, and `previous_token`. A 200 response may include partial `errors`; 401, 403, 404, 429, and 5xx responses require distinct handling.

Timeline responses do not provide a complete deletion feed. Missing, deleted, protected, suspended, or withheld resources can surface as absence, partial errors, lookup errors, or compliance events depending on endpoint and access.

### Mapping to the current `posts` table

| X field or derived value | Existing storage | Gap analysis |
|---|---|---|
| `id` | `post_id` | Direct mapping and deduplication key |
| `author_id` | `author_id` | Direct mapping |
| expanded `users.username` | `author_username` | Requires `author_id` expansion and ID join |
| `created_at` | `created_at` | Direct mapping when explicitly requested |
| `conversation_id` | `conversation_id` | Direct mapping |
| one referenced Post ID | `referenced_post_id` | X may return multiple references; the scalar column cannot represent all relationships |
| reference type | `post_type` | Derivable, but multiple simultaneous relationships need Stage 3 rules |
| source identity | `source_key` | Application-derived as home or mentions source |
| `text` | `text` | Direct mapping, subject to X retention and removal obligations |
| complete Post object and selected includes | `raw_json` | Can preserve extra fields technically; legal scope and compliance deletion must be confirmed |
| public metrics, language, entities, edit history, attachments, media, user metadata | `raw_json` | No dedicated columns; query and retention needs must be reviewed before any schema proposal |
| collection/run fields | existing run and collection columns | Application-derived during Stage 3 |
| deleted, protected, withheld, unavailable state | availability and deletion columns | Stage 3 needs revalidation and event-to-status semantics |

No database migration is proposed or created by this spike. Potential Stage 3 questions are whether multiple references need normalization, which expanded objects belong inside per-Post `raw_json`, and which compliance state requires dedicated structured storage.

## 8. Cost estimate

### Verified pricing facts

- X API v2 currently uses prepaid, credit-based pay-per-use pricing without a subscription minimum.
- Public Post reads are listed at $0.005 per returned resource.
- A documented Owned Read is $0.001 per resource only when the endpoint is listed and `{id}` matches the authenticated user who owns the developer app. Mentions is listed; home timeline is not.
- The same resource is normally not billed twice inside one UTC day, but X calls this a soft guarantee.
- Pay-per-use plans have a two-million Post-read monthly cap. Enterprise pricing is custom above that boundary.
- Exhausted credit or a configured spending cap blocks requests. Rate limits and billing limits are separate.

### Scenario assumptions

The scenarios assume 30 days, one or two manual runs per day, maximum-page pagination to the previous checkpoint, no real-time monitoring, no user lookups after IDs are configured, and the public $0.005 Post-read price. They count unique returned Posts per day after the documented daily billing deduplication. They exclude future LLM and database costs.

| Scenario | Unique home Posts/day | Unique mentions/day | Monthly Post reads | Estimated monthly X cost | If mentions qualify as Owned Reads |
|---|---:|---:|---:|---:|---:|
| Low | 100 | 10 | 3,300 | $16.50 | $15.30 |
| Expected MVP | 500 | 25 | 15,750 | $78.75 | $75.75 |
| High | 2,000 | 100 | 63,000 | $315.00 | $303.00 |

These are arithmetic scenarios, not observed usage. Actual volume, app ownership, credit availability, endpoint-specific Developer Console prices, daily deduplication behavior, and whether expanded resources create additional charges must be validated live. Configure a low spending cap for the spike.

## 9. Storage and compliance

### Verified requirements

- API credentials must remain private and cannot be shared or committed.
- The app's declared use case is binding and substantive changes require disclosure and approval.
- Offline X Content must reflect deletion, edit, protection, suspension, withholding, and other availability changes as soon as reasonably possible and within the applicable request deadlines.
- X or account-owner removal requests require action within 24 hours. Termination requires deletion of licensed material; current official guidance states ten business days for evidence and deletion handling.
- Public display must preserve attribution, content integrity, timestamp, and availability requirements.
- Redistribution is restricted. The policy permits limited Post-ID distribution and tightly limits hydrated object distribution.
- Protected or blocked content cannot be served to people who are not authorized to view it.
- Sensitive personal attributes must not be derived or stored.
- The Developer Agreement prohibits using X Content to fine-tune or train a foundation or frontier model. Current Developer Guidelines also state an AI/ML training prohibition except for Grok.
- Scraping is not an alternative. The official API must be used.

### Engineering implications

- Post IDs may be stored as internal operational identifiers, but public or third-party redistribution must remain within policy limits.
- Full Post text and raw JSON should be treated as licensed X Content, kept in protected PostgreSQL rather than Git, tied to availability state, and removable or updateable by Post ID.
- Stage 3 needs periodic revalidation or an approved compliance mechanism. Enterprise compliance streams provide deletion and account-state events, but are not documented as available to the self-serve spike.
- Author metadata is also X Content and needs the same access, removal, protection, and redistribution controls.
- AI-assisted filtering must be inference-only, must not train or fine-tune a model on X Content, and must not derive prohibited sensitive attributes.
- Any third-party model provider must be evaluated as a data recipient and processor before X Content is sent to it.
- Raw API responses must never be committed or used as fixtures. Synthetic fixtures are sufficient for default tests.

### Unresolved legal and compliance questions

- Whether the approved app use-case description explicitly covers AI-assisted filtering and external model processing.
- Whether sending full Post text to the selected model provider is allowed under the applicable X agreement and provider retention or training terms.
- Whether full raw JSON is necessary and permitted for the intended retention period, rather than retaining a narrower field set.
- The required revalidation cadence for a self-serve application without Enterprise compliance streams.
- Whether any home-timeline content is non-public from the perspective of internal storage or downstream reviewers.
- Whether expanded media URLs and author metadata should be retained or rehydrated on demand.
- The exact deletion workflow when no proactive self-serve deletion feed is available.

This document is an engineering compliance analysis, not legal advice.

## 10. Checkpoint and completeness analysis

### What can be guaranteed

Within the window exposed by an endpoint, the client can follow every opaque `next_token` in reverse chronological order until no token remains. A short final page does not prove completion by itself. Completion is indicated by the absence of `next_token` after every successful page has been processed.

Stage 3 may advance a source checkpoint only after:

1. every available page for that source succeeds;
2. no partial error remains unresolved;
3. every fetched Post has been durably committed and deduplicated by Post ID;
4. response ordering, duplicate checks, and configured boundary checks pass;
5. no possible-window-truncation condition is active;
6. the run transaction and source status are committed successfully.

Home and mentions need independent checkpoints and independent success states.

### What cannot be guaranteed

The API does not document a flag that says an older saved checkpoint was lost beyond the 3,200/seven-day home window or the 800-mention window. Exhausting pagination proves only that the exposed API window was exhausted. It does not prove that no older Posts were omitted.

### Recommended Stage 3 semantics

- Store the highest successfully observed Post ID per source only after complete success.
- Use `since_id` for efficient incremental retrieval, but retain independent elapsed-time and volume diagnostics because `since_id` cannot prove that an old checkpoint remained inside the window.
- For initial validation and suspicious gaps, optionally paginate an unfiltered diagnostic request until the exact synthetic or saved checkpoint is encountered.
- Record `checkpoint_reached`, `checkpoint_not_reached`, `api_window_exhausted`, `pagination_unavailable`, or `request_failed` explicitly.
- Emit `possible_timeline_truncation` when the previous success is older than the documented window, the result volume approaches the endpoint cap, the exact checkpoint cannot be encountered in an unfiltered diagnostic, pagination metadata is missing, or a gap in observed IDs or time remains unexplained.
- Detect missed collections from elapsed time since `last_successful_at`, failed runs, checkpoint non-advancement, cap saturation, and gap diagnostics.
- Never advance the checkpoint after a 401, 403, 429, 5xx, timeout, unexpected shape, partial error, or incomplete page loop.

The diagnostic probe performs these classifications only in memory and never writes `sync_state`.

## 11. Risks

- API access changes can invalidate endpoint or account assumptions.
- Pay-per-use prices and app-specific access can change.
- The 3,200/seven-day home limit can hide a missed window.
- The 800-mention limit can hide bursts between runs.
- Rate limits, credit exhaustion, or spending caps can interrupt pagination.
- Aleksandr must complete and maintain user authorization for home access.
- Ethplorer app ownership or separate authorization can change price and content visibility.
- Retention, update, deletion, and redistribution duties require an operational compliance process.
- A self-serve app may lack proactive deletion events available through Enterprise compliance streams.
- Tokens can expire or be revoked; refresh behavior and rotation must be validated.
- Endpoint response fields and pagination tokens can change or be deprecated.
- The two sources can fail independently and must never share checkpoint advancement.
- Recent search can miss or delay content and is not automatically equivalent to direct mentions.
- External model processing may require additional approval or contractual controls.

## 12. Final recommendation

Do not start Stage 3 yet. Keep Stage 2 In Progress with `blocked pending credentials`.

To unblock the final decision:

1. Configure an approved X app with the disclosed MVP use case and a small spending cap.
2. Complete OAuth 2.0 PKCE as Aleksandr and validate access-token refresh.
3. Run live home and mentions probes for at least two pages when data volume permits.
4. Repeat page one, verify reverse chronological IDs and duplicates, and run the synthetic checkpoint experiment.
5. Confirm the direct mentions endpoint with app-only or user-context auth and determine whether separate Ethplorer authorization is needed for visibility or Owned Read pricing.
6. Record actual rate-limit headers, Developer Console charges, returned fields, partial errors, and endpoint access restrictions without storing Post content in Git.
7. Resolve whether the app approval and X terms permit the planned AI-assisted inference and third-party model handling.

If live validation succeeds, Stage 3 must account for independent source transactions, maximum-page pagination, window-cap warnings, no checkpoint advancement on partial failure, refresh-token handling, cost accounting, and X Content revalidation and deletion. Stage 3 remains Planned and is not implemented by this spike.
