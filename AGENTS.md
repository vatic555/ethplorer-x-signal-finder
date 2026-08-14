# Repository Instructions

- Read `HANDOFF.md` before starting work. Update it at the end of every completed task and whenever the current stage, next task, validated commit, architecture, operational commands, or major limitations change. `HANDOFF.md` is a current-state summary and must not override the canonical specification, roadmap, or decisions log.
- Read `docs/project-spec.md` before making architectural or product changes.
- Treat `docs/project-spec.md` as the canonical product and technical specification.
- Read `docs/roadmap.md` before implementation work and follow its canonical stage order.
- Preserve the roadmap's MVP boundary: Stages 0 through 7 are MVP, and Stage 8 is post-MVP.
- Update `docs/roadmap.md` and `README.md` whenever the current stage or stage status changes.
- Never mark a roadmap stage Completed until its task-specific validation passes.
- Record an accepted decision in `docs/decisions.md` before reordering or bypassing roadmap stages.
- Do not invent Ethplorer capabilities. Use only capabilities documented in the knowledge base.
- Clearly distinguish verified facts, model inference, and unresolved uncertainty.
- Reject weak Opportunities instead of producing generic drafts.
- Do not implement automatic publication without an explicit specification change.
- Do not commit secrets, credentials, local environment files, runtime databases, raw operational X content, or private or licensed runtime exports.
- Keep the system cross-platform across macOS, Windows, Linux, and future CI runners. The primary entry point must be platform-independent Python.
- Update `docs/decisions.md` for every meaningful architectural decision.
- Update `docs/project-spec.md` whenever implementation changes product behavior.
- Use short hyphens instead of em dashes in public-facing copy.
- Prefer auditable, structured outputs with explicit evidence and uncertainty fields.
- Do not silently change terminology definitions. Document and review every terminology change.
- Preserve the distinction between a Signal, an Opportunity, and a draft.
- Prefer no output over weak, forced, or unsupported promotional participation.

## External Cost Preflight Guardrail

- This rule is mandatory for X API, LLM APIs, TwitterAPI.io, SocialData, and every current or future external service with usage-based or potentially paid calls.
- Before any paid external call, perform a zero-cost preflight. Show the user the provider and endpoint, why the call is needed, expected request count, expected billable resources, known unit price, expected cost, conservative maximum cost, and the technical hard guard that prevents spending above that maximum. Then stop and wait for explicit approval.
- Approval applies only to the stated ceiling, for example: `Approved maximum external spend: $0.25`. A new or higher limit requires a new preflight and new explicit approval.
- The run must stop before exceeding the approved ceiling. Do not independently increase pages, time window, Post count, model tokens, retries, or provider calls when that can increase the approved maximum spend.
- If pricing is unknown or cannot be estimated reliably, do not make the paid call unless the user separately approves an experiment with a stated hard dollar cap and the run has a technical mechanism that enforces that cap.
- Do not buy data that is already available locally. Before proposing an external read, inventory suitable PostgreSQL records, ignored runtime artifacts, and other approved local evidence, and use them as the benchmark whenever they can answer the question.
- Start with the smallest sample that can test the hypothesis. Provider quality spikes begin with approximately 20 to 50 Posts or the smallest useful time window to verify schema, full text, quotes and replies, and pagination. A larger shadow run requires a separate proposal and approval.
- After every approved paid run, report the planned maximum, actual requests and billable resources, estimated or known actual spend, variance from plan, and whether the run produced enough evidence.
- Task 004D must not repeat an expensive Official X 24-hour collection automatically. It must first use the existing PostgreSQL corpus as the Official X benchmark where suitable, run only a small approved schema and content test for TwitterAPI.io and SocialData, and propose the cost of any larger comparison separately.
