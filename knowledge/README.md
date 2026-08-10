# Knowledge Base

For the MVP, this directory is the source of truth for static reviewed knowledge. PostgreSQL, a search index, or another derived representation may be added later, but it must be reproducible from the reviewed Git content and must not replace it as the canonical static knowledge source.

The architecture distinguishes three knowledge source classes. They have different authority, storage, and future read contracts and must not be blended silently.

## Knowledge Source Classes

### 1. Static Reviewed Knowledge

This class includes product articles, product documentation, terminology, capabilities, and limitations. Reviewed files in this Git repository are its source of truth.

Static evidence uses the normalized source-document contract below. Structured assets and capabilities may be established only from supporting static source IDs with sufficient review status.

### 2. First-Party Editorial Corpus

This future class consists of historical Ethplorer and Binplorer X Posts and replies. It may later support style guidance, reaction-pattern analysis, and evidence of prior public positioning.

The corpus is not imported by Task 005A and does not belong in the static evidence layer merely because it is first-party content. Its future importer and compliant storage must preserve at least the X Post ID and URL, account, publication and retrieval dates, conversation or reply context when available, and source provenance. The future reader must expose why a corpus item was selected and its intended editorial use.

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

Task 005A documents these future contracts only. It does not implement the X corpus importer, corpus storage, analytics adapter, snapshot query, or runtime integration.

## Evidence and Capability Layers

Within static reviewed knowledge, the knowledge base contains two layers:

- A source document is evidence: normalized public or explicitly approved material with stable provenance.
- An asset or capability record is a structured claim that the pipeline may use only when its `source_ids` point to supporting source documents.

## Structure

```text
knowledge/
  terminology/
    shared-analytics.md
    x-signal.md
  sources/
    ethplorer/
    binplorer/
    analytics/
    other/
    _source-template.md
  assets_catalog.csv
  source_documents.md
  README.md
```

Current inventory: two terminology documents, zero normalized static evidence documents, zero editorial corpus items, zero dynamic analytical records, and zero asset or capability rows. Task 005A defines the structure and contracts only. Task 005B will import actual reviewed Ethplorer static sources.

## Source Document Contract

Every imported static source is one normalized Markdown file below `sources/`. Filenames should be stable and descriptive. Each file starts with TOML front matter between `+++` delimiters, followed by normalized source content.

Required metadata:

- `source_id` - stable lowercase identifier using letters, numbers, dots, underscores, or short hyphens;
- `title` - source title;
- `source_type` - concise type such as `article`, `documentation`, `repository`, or `approved_note`;
- `products` - zero or more product identifiers;
- `networks` - zero or more network identifiers;
- `review_status` - `pending`, `reviewed`, or `deprecated`;
- `confirms` - explicit list of claims the source supports;
- `limitations` - known gaps, boundaries, or non-claims.

Provenance requires at least one non-empty field:

- `source_url` for public material; or
- `approved_provenance` for material explicitly approved for repository storage.

Optional dates are `published_date` and `retrieved_date` in `YYYY-MM-DD` form when known. Unknown dates remain omitted rather than guessed.

The normalized content must preserve the source meaning and must not add inferred capabilities. Public or approved material may be normalized for headings and readability. Do not commit full private, internal, confidential, or licensed documents to this public repository.

Copy [`sources/_source-template.md`](sources/_source-template.md) when starting an import. The template itself is not a source and is ignored by validation.

## Asset Catalog Contract

[`assets_catalog.csv`](assets_catalog.csv) is the compact capability layer. It has no capability rows yet. Its columns are:

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

## Terminology

Shared analytics terminology and X Signal Finder terminology remain separate:

- [`terminology/shared-analytics.md`](terminology/shared-analytics.md) retains upstream provenance and review state for imported analytics definitions.
- [`terminology/x-signal.md`](terminology/x-signal.md) contains project-specific operational contracts.

Definitions must not be merged, reconstructed from general knowledge, or changed silently.

## Import Workflow

This workflow applies only to static reviewed knowledge:

1. Confirm that the material is public or explicitly approved for storage in this public repository.
2. Copy the source template into the appropriate product or topic directory.
3. Assign a stable `source_id`, complete metadata, and normalize the content without adding claims.
4. Add the source to [`source_documents.md`](source_documents.md).
5. Review the source and set its status accurately.
6. Add or update an asset row only when the source directly supports that capability.
7. Run the offline validator and default tests.

## Offline Validation

```sh
python -m x_signal_finder knowledge validate
```

Validation reads local Markdown and CSV only. It makes no network requests and performs no LLM calls. It checks required structure and metadata, unique IDs, review statuses, catalog-to-source references, reviewed-evidence rules, and local Markdown links.

The validator does not access or validate the future editorial corpus or dynamic analytical evidence. Those classes require separate task-specific adapters and tests before runtime use.
