# Knowledge Base

For the MVP, this directory is the source of truth for static reviewed knowledge. PostgreSQL, a search index, or another derived representation may be added later, but it must be reproducible from the reviewed Git content and must not replace it as the canonical static knowledge source.

The architecture distinguishes three knowledge source classes. They have different authority, storage, and future read contracts and must not be blended silently.

## Knowledge Source Classes

### 1. Static Reviewed Knowledge

This class includes product articles, product documentation, terminology, capabilities, and limitations. Reviewed files in this Git repository are its source of truth.

Static evidence uses the source-document contract below. Structured assets and capabilities may be established only from supporting static source IDs with sufficient review status.

### 2. First-Party Editorial Corpus

This implemented class consists of historical and continuously synchronized Ethplorer and Binplorer X Posts, including replies, quotes, and reposts. It may later support style guidance, reaction-pattern analysis, and evidence of prior public positioning.

The corpus was not imported by Task 005A and does not belong in the static evidence layer merely because it is first-party content. Task 005C now stores it separately in PostgreSQL with X Post identity and URL, account, publication and retrieval dates, direct relationship context and availability, media metadata, and source provenance. Future readers must preserve the intended editorial use and must not promote corpus content into capability evidence.

An editorial item can show what Ethplorer or Binplorer previously said. It must not silently establish a product capability, limitation, current fact, or supported network. Any such capability claim still requires reviewed supporting evidence from the static knowledge class.

### 3. Dynamic Analytical Evidence

This future class includes current or comparative metrics produced outside this repository, especially by `ethereum-top-addresses-pipeline`. Its upstream repository and generated analytical state remain separate and are not copied into the static knowledge base.

A future analytics adapter must query the latest appropriate snapshot or comparison on demand. Every returned metric must preserve:

- as-of date;
- comparison dates when a comparison is used;
- metric name;
- scope, including the applicable network, asset, address set, or cohort;
- source provenance, including the upstream repository and snapshot, run, revision, or equivalent stable reference.

Dynamic evidence may support a time-bound analytical statement. It does not by itself establish that Ethplorer has a product capability. Missing dates, scope, or provenance make the analytical claim unresolved.

Task 005A documented these class contracts. Task 005C subsequently implemented first-party X corpus import and storage in PostgreSQL. The analytics adapter, snapshot query, and runtime knowledge integration remain unimplemented.

## Evidence and Capability Layers

Within static reviewed knowledge, the knowledge base contains two layers:

- A source document is evidence: public or explicitly approved material with stable source identity and provenance, represented as reliable machine-readable Markdown.
- An asset or capability record is a structured claim that the pipeline may use only when its `source_ids` point to supporting source documents.

## Structure

```text
knowledge/
  terminology/
    shared-analytics.md
    x-signal.md
  sources/
    posts/                   # Canonical Ethplorer Markdown articles
      assets/                # Shared local article images, flat namespace
    ethplorer/
    binplorer/
    analytics/
    other/
    _source-template.md
  assets_catalog.csv
  prefilter/
    README.md
    vocabulary.csv
  review_summary.md
  source_documents.md
  README.md
```

Current Git static-knowledge inventory: two terminology documents, 17 reviewed Ethplorer Markdown articles under `sources/posts/`, 11 deduplicated local article images directly under `sources/posts/assets/`, 11 reviewed capability rows, 12 canonical Ethplorer article routes carried by source metadata, one 91-row precision-reviewed derivative vocabulary, and zero dynamic analytical records. The separate PostgreSQL editorial corpus contains 378 operational first-party rows and remains outside the static Git inventory.

## Source Document Contract

Every imported static source is one Markdown file below `sources/`. Filenames and existing canonical locations are stable. Each file starts with TOML front matter between `+++` delimiters, followed by source content.

`knowledge/sources/posts/` is the canonical location for the 17 current Ethplorer articles. Do not move or rename these files merely to match product-oriented directory suggestions. Their `source_type` must be `ethplorer_article`, which distinguishes them from the PostgreSQL first-party X editorial corpus.

Required metadata:

- `source_id` - stable lowercase identifier using letters, numbers, dots, underscores, or short hyphens;
- `title` - source title;
- `source_type` - concise type such as `article`, `documentation`, `repository`, or `approved_note`;
- `products` - zero or more product identifiers;
- `networks` - zero or more network identifiers;
- `review_status` - `pending`, `reviewed`, or `deprecated`;
- `confirms` - explicit list of claims the source supports after review;
- `limitations` - known gaps, boundaries, or non-claims.

Provenance requires at least one non-empty field:

- `source_url` for public material; or
- `approved_provenance` for material explicitly approved for repository storage.

Optional dates are `published_date` and `retrieved_date` in `YYYY-MM-DD` form when known. Unknown dates remain omitted rather than guessed.

For a canonical public Ethplorer article, `source_url` is also the deterministic article identity. Offline normalization accepts harmless HTTP/HTTPS, `www`, trailing-slash, query, and fragment differences while preserving the `/posts/<slug>` identity. One active canonical URL can map to only one source ID. Approved derivative or interview documents without a canonical public route retain `approved_provenance` instead.

For a converted source whose original file is intentionally removed from the public repository, optional `source_file_sha256` records the original file digest without retaining the DOCX itself.

Managed article images use a flat namespace directly under `knowledge/sources/posts/assets/`. Markdown files reference them as `assets/<filename>`. Add a descriptive suffix when two distinct images would otherwise collide; do not create dated or temporary import subdirectories.

Pending sources may leave `products`, `networks`, `confirms`, and `limitations` empty until substantive review. A source cannot become `reviewed` while `confirms` is empty. Reviewed means the source reliably establishes what it says, not that every historical figure, product state, price, or limit remains current.

Source content must preserve the source identity, provenance, claims, and substantive meaning. Byte-for-byte equality with imported Markdown is not required. The corpus should be structurally reliable and machine-readable.

Allowed normalization includes:

- removing trailing whitespace and redundant blank lines;
- repairing clearly broken Markdown;
- normalizing a damaged heading hierarchy;
- normalizing lists and tables;
- repairing malformed local or internal links when the intended target is unambiguous;
- normalizing image references and captions;
- removing obvious conversion or export artifacts;
- splitting unstructured text into sections when this does not change meaning.

Normalization must not:

- rewrite claims merely for style;
- silently update historical facts, prices, limits, dates, or capabilities;
- add information absent from the source;
- change substantive meaning;
- present an inferred capability as a source claim.

Do not commit full private, internal, confidential, or licensed documents to this public repository. Task 005A did not bulk-reformat the first 12 inventoried articles. Five later DOCX inputs were converted with meaning-preserving structural normalization and their source files removed after verification. Task 005D reviewed all 17 sources without cosmetic body rewrites; future edits remain limited to meaning-preserving repairs.

Copy [`sources/_source-template.md`](sources/_source-template.md) when starting an import. The template itself is not a source and is ignored by validation.

## Asset Catalog Contract

[`assets_catalog.csv`](assets_catalog.csv) is the compact capability layer. It contains 11 reviewed reusable capabilities rather than one row per article. Its columns are:

- `asset_id` - stable unique identifier;
- `name`;
- `asset_type`;
- `product`;
- `networks` - semicolon-separated identifiers;
- `topics` - semicolon-separated topics;
- `what_it_can_answer`;
- `what_it_cannot_prove`;
- `unique_value`;
- `source_ids` - semicolon-separated supporting source IDs;
- `review_status` - `pending`, `reviewed`, or `deprecated`;
- `last_reviewed` - `YYYY-MM-DD` when reviewed or updated.

Every row must reference at least one existing source. A reviewed capability must reference at least one reviewed source; pending or missing evidence can never support a reviewed capability. A URL is not a substitute for `source_ids`.

Historical article findings are not current capability values. The catalog may preserve a stable method such as aggregated holdings or balance-composition analysis while its limitations defer current numbers to dated dynamic evidence.

## Unified Prefilter Vocabulary

[`prefilter/vocabulary.csv`](prefilter/vocabulary.csv) is a derivative routing layer built from reviewed static evidence, non-repost first-party authored wording, separate referenced or audience context, and exact stored article links. It does not replace the source documents or capability catalog and does not implement runtime filtering.

The vocabulary uses exact tokens, phrases, and entities with reviewed or candidate status, qualitative strength, evidence links, and aggregate local-corpus counts. Generic noise and historical numerical values are excluded. First-party X wording may inform routing but never proves a capability. See [`prefilter/README.md`](prefilter/README.md) and [`review_summary.md`](review_summary.md).

## Terminology

Shared analytics terminology and X Signal Finder terminology remain separate:

- [`terminology/shared-analytics.md`](terminology/shared-analytics.md) retains upstream provenance and review state for imported analytics definitions.
- [`terminology/x-signal.md`](terminology/x-signal.md) contains project-specific operational contracts.

Definitions must not be merged, reconstructed from general knowledge, or changed silently.

## Import Workflow

This workflow applies only to static reviewed knowledge:

1. Confirm that the material is public or explicitly approved for storage in this public repository.
2. Keep an existing approved canonical location. For a new source without one, copy the source template into the appropriate directory.
3. Assign a stable `source_id`, complete metadata, and make only meaning-preserving normalization needed for reliable machine use.
4. Add the source to [`source_documents.md`](source_documents.md).
5. Review the source and set its status accurately.
6. Add or update an asset row only when the source directly supports that capability.
7. Update derivative routing terms only when their evidence and authority are explicit.
8. Run the offline validator and default tests.

## Offline Validation

```sh
python -m x_signal_finder knowledge validate
```

Validation reads local Markdown and CSV only. It makes no PostgreSQL, network, or LLM calls. It checks required structure and metadata, unique IDs, review statuses, canonical article routes, catalog-to-source references, reviewed-evidence rules, vocabulary schema and references, normalized term duplicates, and local Markdown links.

For `sources/posts/`, it also requires `source_type = ethplorer_article`, one H1 matching metadata title, a substantial non-empty body, closed fenced blocks, and no duplicate body after whitespace normalization for comparison only. Source-site routes and legacy article media references are not treated as missing repository files. Managed local image references below `assets/` must resolve to non-empty files.

Validation targets metadata integrity and semantic or structural usability. It does not enforce byte identity with an imported Markdown file. Duplicate detection may fold whitespace and case for comparison without changing stored content.

The validator intentionally does not access or reproduce the implemented PostgreSQL editorial corpus or dynamic analytical evidence. The committed first-party counts are a reviewed snapshot, while raw corpus data remains operational. Those non-static classes use separate task-specific storage, readers, and tests; offline Git validation remains independent of PostgreSQL.
