# Praval 0.8.4 documentation review

Reviewed on October 9, 2026, before publication. The framework and website remain
unreleased for the owner's morning review. This work changes documentation and
its regression checks; it does not change provider or model-runtime behavior.

## Findings and corrections

| Finding | Correction and developer impact |
| --- | --- |
| Getting-started examples reused an agent after closing its provider client. | Each of the first three model examples now owns its agent with a context manager. A regression test executes the published snippets through the actual OpenAI adapter with a fake SDK and checks requests and client closure. |
| Structured-output guidance said streaming skipped local validation. | The guide now explains that `validate_locally=True` validates the final answer before `final` and history commit. Earlier deltas are provisional. Invalid output raises `ProviderInvalidResponseError`. The quickstart explicitly enables validation. |
| Streaming guidance implied incremental tool execution and text. | Turns offering client tools buffer the tool loop, then emit completed tool/result events and the final text. Native no-tool streaming is distinct. This prevents applications from treating buffered events as live progress. |
| Constructor configuration and call options were easy to confuse. | The runtime guide now gives a complete `config` example and identifies supported call overrides. Temperature and output bounds are constructor defaults; timeout and provider options can be overridden per call. The typed TOML schema resolves settings but does not construct or reconfigure agents. |
| Cohere's capability table excluded supported reasoning and emulated streaming, and tool schema wording described only one endpoint. | The provider and tool guides now distinguish default Command A from the reasoning profile, v1 `parameter_definitions` from v2 JSON Schema, and emulated streaming from native streaming. |
| Continuation wording said every request resends the whole transcript. | The provider guide now distinguishes preserved context from OpenAI Responses response-ID chaining. |
| HITL CLI examples opened a different default database and omitted agent registration on resume. | Commands now select the example's SQLite database with the global option and supply the registration module on resume. The tutorial distinguishes simulated approval from a real reviewer's decision. |
| MCP examples left the agent open and did not explain the first expected approval exception. | The main example closes its agent and explains that approval/resume must occur while the client session remains open. Async-only execution and unsupported result types remain explicit. |
| Spores were described as immutable objects. | The core guide now explains immutability by convention. The dataclass does not enforce freezing. |
| Current install, evaluation, observability and certification examples retained 0.8.3 labels. | Current examples now use 0.8.4 and Python 3.10 or newer. Historical migration pages remain historical. The changelog marks 0.8.4 as unreleased instead of asserting a publication date. |
| OpenRouter was missing from the provider API index and some provider inventories. | The generated API index, README, runtime migration and core/streaming guides include it. Migration guidance preserves full vendor/model IDs and explains discovery and Ollama limits. |
| Generated documentation contained one missing local file and six broken source-reference anchors. | The Docker README points to its repository source. Sphinx source links now stay on defining modules instead of composing invalid imported-alias links. |
| Website instructions described rebuilding/copying local docs and pushing main. | The prepared website branch documents verified CI artifact staging through `scripts/deploy-docs.sh`, draft PR review, final main-CI provenance and the PyPI gate before deployment. `CLAUDE.md` and `AGENTS.md` agree. |
| The website quickstart omitted completion/cleanup, and its install description listed only three providers. | The prepared website branch waits for Reef completion and shuts it down, and lists current adapters. Version labels and registry are aligned with the candidate. |

The new coding-agent section directs callers to the installed version, versioned
manual, plain-text `_sources/`, public signatures, typed failures, capability
discovery, async MCP execution, resource ownership and observable tool outcomes.
It also distinguishes fake-client verification from paid model checks.

## Validation

- The complete local suite passed with CI exclusions and 60-second thread
  timeouts: **4,064 passed, 144 skipped**, with **93.62% coverage**. All focused
  coverage floors passed. The new test accounts for the increase from 4,063.
- Black, isort and flake8 passed over the full CI source/test/script/example
  surfaces. Python 3.13 strict typing and Python 3.10 compatibility typing passed.
- Release metadata agrees on 0.8.4. All **102 public exports** are documented on
  their declared API surfaces, giving **100% export coverage**.
- A source audit parsed **91 complete Python blocks**, checked **144 imported
  public names**, and
  checked constructor keywords against installed signatures. It found no errors.
  An intentional bare-decorator fragment is excluded from standalone syntax
  claims. Snippets requiring a project, server or surrounding async function are
  examples of those contexts, not independently executable programs.
- Corrected Sphinx sources build with `-W --keep-going` against the installed
  candidate CI wheel in an isolated environment. Imports resolve to that wheel,
  not editable framework source. No provider inference is used for this build.
- The corrected local build has **173 HTML pages** and **159,867 local
  references**, with no missing local files or anchors.
- Search, version switching, migration navigation and website version labels
  were checked through the local preview. Artifact staging checks compare both
  generated trees byte for byte, validate provenance and retain previous versions.

The preceding candidate CI run
[37833138900](https://github.com/aiexplorations/praval/actions/runs/37833138900)
passed all 16 jobs at release head `294971e`. Its documentation artifact records
the PR merge commit `db0bad66307d58c1e4b91353633e2cb0c73f0b66` and wheel SHA256
`d6645ef3c8eed1c490595838b2a260ce7c80a4dc52d2a615dbbd79843ba37cef`.
These are candidate artifacts, not publication artifacts. The documentation
corrections are subsequent work and require fresh CI; use
[framework PR #26](https://github.com/aiexplorations/praval/pull/26) for their
latest checks. The website draft's manifests identify the artifact actually
staged for review.

## Remaining limitations and release gates

The review found one minor framework diagnostic gap: `praval doctor` omits
OpenRouter credential-presence reporting. The adapter and its paid tool checks
work. The guide states the limitation, and the roadmap tracks the diagnostic
addition for 0.8.5. No new provider execution defect was identified in this
documentation review.

Direct Anthropic inference remains unverified because account credit blocked the
earlier attempt and the owner deferred further spending. Schema/continuation
contracts are tested offline. Claude Haiku 4.5 through OpenRouter passed its live
dependent-tool check. Gemini 3.5 remains quota-limited on the checked account.
Model availability and catalogue prices may change; registry profiles do not
guarantee account access. No additional paid model calls were made for this review.

Ollama's per-request native context setting, interruption of an in-flight model
call and text between tool rounds remain 0.8.5 work. The seven reported Praval
Code safety issues belong to that application; they are not framework fixes.

The review covers maintained release documentation, executable examples, API
contracts and the staged website. It does not claim live execution of every
tutorial, every external link or archived manual. Earlier live checks and their
initial failures remain in `evidence/v084-final-candidate-validation.json`.

Before release:

1. Review the corrections and fresh candidate CI, then approve the framework PR.
2. Merge to framework main and wait for successful main CI. Download and certify
   that exact wheel and its matching documentation artifact as `RELEASE.md` requires.
3. Set the actual publication date/status in release materials before that final
   main-CI build. Upload only the approved named CI wheel, verify its PyPI hash,
   then tag the exact commit.
4. Refresh the website draft from the matching final main-CI documentation
   artifact, verify its wheel hash against PyPI, approve/merge the website PR and
   verify pravalagents.com after deployment.

Neither repository's main branch is merged by this review, and no wheel, tag or
website deployment is published.
