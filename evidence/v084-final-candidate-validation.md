# Praval 0.8.4 candidate validation

Checked on 2026-10-08 against `release/v0.8.4` at `c48e3fa`.
Updated on 2026-10-09 after the newly supplied provider keys enabled more tests.
Publication remains on hold. No merge to main, upload, tag or deployment was performed.

The tests used the wheel downloaded from successful [CI run 37818460828](https://github.com/aiexplorations/praval/actions/runs/37818460828).
All sixteen CI checks passed. The artifact records PR merge commit
`5326776d4294723e4d7e98e1ef57e634182b7047`; this is a candidate artifact,
not the eventual `main` CI wheel required for publication.

Wheel: `praval-0.8.4-py3-none-any.whl`.
SHA256: `0495cd3ce19fb266f5397dc33484ee1b2b6d745b6d2714d62c5c7575f9aea811`.
The downloaded checksum was verified, and every packaged Praval Python source
matched the release branch. Distribution validation, release metadata validation
and `twine check` passed.

The later Cohere checks found two defects in that CI wheel. Both were corrected
on `codex/cohere-request-timeout` and tested with a local wheel. That wheel's
SHA256 is `0f9d62aa34c2bee25db439da92103806531fcafe4c5ad2a5b36a6dcf2049495d`;
its packaged Python sources match the corrected checkout. It is local validation
evidence. A new successful CI artifact is required for the corrected candidate.

## Results

| Check | Result |
| --- | --- |
| Registered JSON Schema provider matrix against installed wheel | 54 passed |
| Praval Code unit and integration checks | 441 passed |
| Praval Code brand checks | 10 passed |
| PravalClaw full isolated suite | 2,762 passed, 30 skipped |
| PravalClaw socket checks rerun with local socket permission | 10 passed |
| OpenAI GPT-5.4 Mini, Chat Completions and Responses | Both passed |
| OpenAI GPT-6 Luna, automatic Responses and explicit Responses with low reasoning | Both passed |
| Gemini 3.1 Flash-Lite dependent tools | Passed |
| Gemini 3.1 Flash-Lite with newly supplied key | Passed on original CI wheel |
| Gemini 3.5 Flash with newly supplied key | First tool call succeeded; quota blocked continuation |
| Anthropic Claude Sonnet 5 with newly supplied key | API reached; insufficient account credit blocked inference |
| Cohere Command A, v1 and v2 | Both passed on corrected local wheel |
| Focused provider regressions after Cohere fixes | 434 passed |
| Installed corrected wheel, schema and real-SDK edge contracts with Cohere 7.2.0 | 64 passed |
| Full suite after Cohere corrections, CI timeout flags | 4,062 passed, 144 skipped; 93.61% coverage; all floors passed |
| Formatting, lint, Python 3.13/3.10 typing, API surface and metadata | Passed |
| Documentation contracts and installed-wheel Sphinx warnings-as-errors build | 16 contracts passed; Sphinx passed |
| Corrected local wheel distribution validation and Twine check | Passed |
| Ollama Qwen 3.5 2B dependent tools | First attempt hit round limit; traced rerun passed |
| Ollama Qwen 3.5 9B dependent tools | Passed |
| Praval Code live file-tool task, GPT-6 Luna | Passed; three generated tests independently passed |
| Praval Code live file-tool task, Gemini 3.1 Flash-Lite | Passed; three generated tests independently passed |

Each passing provider certificate required three dependent tool executions across
four requests, tools registered through `add_tool_spec`, integer and boolean
arguments, and reconciled per-request usage. The installed-wheel deterministic
matrix covers the other provider declarations and public entry points too.

Both coding tasks used the real CLI, `read_file`, `write_file`, `edit_file` and
`run_shell`. Effect records confirmed the file tools executed, the edit carried
distinct old and new text for diff presentation, and shell calls only ran pytest.
Each task reported eight model calls with no failed or unreported model requests.
Gemini also ran pytest before correcting the deliberate subtraction bug, observed
the test failure, edited the module and successfully reran pytest.

The PravalClaw full suite and socket rerun are separate executions. The remaining
twenty skips concern unavailable critic replay cache entries or artifact bytes.
Tests exercised fake connectors and local webhook servers, with no real outbound
messages. Live deployment and connector delivery remain unverified.

## Initial attempts and limits

Cohere's first live attempt failed before dispatch because v1 received the
unsupported SDK keyword `timeout`. The timeout-only correction then reached the
API, but the first tool call had empty arguments and runtime validation rejected
it. The v1 tool definition used `parameters`, which does not declare arguments to
that endpoint. The corrected formatter uses native `parameter_definitions`,
Python type names and required flags. Full JSON Schema constraints remain in
the tool description and runtime validation; v2 retains native JSON Schema.
After both corrections, each endpoint passed all dependent calls with complete
per-request usage. The original failures and request traces remain in the evidence.

Offline contracts use the actual Cohere SDK with a fake HTTP transport. They
verify initial and continued requests, transmitted argument declarations and
actual HTTP timeout settings. These contracts passed with SDK 5.17.0 and 7.2.0.

The first Ollama 2B attempt raised `ToolRoundLimitError` after four tool rounds.
The same certificate passed when rerun with request tracing; the 9B model passed
as well. No adapter change was made. The first attempt had no request trace, so
its cause remains unverified and its failure is retained in the evidence.

The first CLI launches used `--trust`, which trusts the workspace but leaves shell
approval pending. In print mode, pytest was rejected. The verifier also initially
looked for the older turn-record file instead of the current effect history.
Corrected runs used `--auto-approve` within the temporary workspace and checked
the effect records. These were test-harness corrections, not application fixes.

Tests used temporary source snapshots and isolated virtual environments. Existing
downstream dependency libraries were reused; PravalClaw's candidate framework
dependencies were freshly resolved. The existing Praval Code native harness was
copied into its temporary snapshot. The active installations and runtime data
were unchanged. Framework checks used Python 3.13, Praval Code Python 3.12 and
PravalClaw Python 3.14. Temporary PravalClaw home defaults kept test state isolated.

Anthropic successful inference remains unverified because the account needs
credit. OpenRouter live inference remains unverified without a key. Gemini
evidence applies to Flash-Lite. Gemini 3.5 Flash hit its free-tier request quota
after one successful tool call, so its dependent-tool certificate is incomplete.
Praval Code token accounting was complete; prices were not configured, so its
estimated monetary cost remained unavailable.

## Remaining release steps

Obtain a new successful CI artifact containing the Cohere corrections. Complete
Anthropic's live check once account credit is available, and optionally check
OpenRouter when a key is supplied, or explicitly record their unverified status
in the release decision. After candidate approval,
merge and obtain a fresh successful `main` CI wheel. Follow `RELEASE.md` to verify
and publish that exact artifact. The tests here do not authorize publication.

Structured results, tool records, skip reasons and artifact provenance are in
[the validation evidence](v084-final-candidate-validation.json). Temporary test
logs and workspaces are under `/private/tmp/praval-v084-final-cert`.
