# Praval 0.8.1 quality release design

## Purpose

Praval 0.8.1 is the first supported release in the 0.8 line. An initial 0.8.0
package was uploaded briefly and then withdrawn because it did not follow the
project's wheel-only publication policy. PyPI does not allow a deleted filename
to be reused, so the supported release moves to 0.8.1.

This is a quality patch. It does not change Agent, Reef, Spore, ModelRuntime,
MCP, HITL, memory, storage, provider behavior, or the public runtime API.

## User diagnostics

The command line interface will add these commands:

```text
praval --version
praval doctor
praval doctor --json
```

The doctor command will report the Praval version, Python version, installed
package path, optional feature availability, and provider configuration
presence. It will never print a credential value. Missing provider keys are
informational because Praval does not require every provider.

The JSON form will use a stable, documented object shape so bug reports and
support scripts can collect the same facts without parsing terminal prose.

## Wheel-only publishing

The publication bundle will contain exactly one universal wheel. The release
workflow will reject source distributions, JSON files placed beside the wheel,
multiple wheels, or a wheel whose version and hash do not match the tag and CI
manifest.

Manual publishing instructions will name the wheel explicitly. They will not
use a wildcard. The tag workflow will verify that PyPI contains the same wheel
hash before it creates the GitHub release. The GitHub release will attach the
wheel, its checksum, the build manifest, and the documentation manifest.

GitHub creates source archives for every public tag. Those automatic archives
are separate from Praval's uploaded release assets and cannot be disabled.

## Optional live demos

Paid provider, multimodal, HITL, STT, and TTS demos will remain available
through a manually dispatched workflow and the local demo runner. They will not
run on a push or pull request, and they will not block publication.

Documentation will list the required environment variable names, model
configuration, local commands, and GitHub environment setup. It will warn
developers not to commit keys. A selected live demo will still fail clearly if
its own required configuration is missing.

Offline and service-backed exact-wheel demos remain required release checks.

## Documentation and version history

The README will explain why 0.8.0 is absent and why 0.8.1 is the first supported
0.8 release. The changelog and release notes will use the same explanation.
They will describe 0.8.1 as the tested 0.8 framework plus packaging,
diagnostic, documentation, and release improvements.

The prepared praval-ai documentation will move from v0.8.0 to v0.8.1. The
website badge, versions index, latest documentation, and versioned
documentation must agree after publication.

The old example issues will be checked against the current examples. Resolved
issues will be closed with evidence. Any remaining defect will be fixed without
changing the public runtime API.

## Validation

Tests will cover command line text and JSON output, package path reporting,
optional feature checks, provider configuration presence, and secret
redaction. Packaging tests will require one wheel and no source distribution in
the publication bundle.

The release candidate must pass Python 3.9 through 3.13 tests, complete-package
coverage, focused coverage floors, typing, formatting, lint, MCP contracts,
warning-free documentation, wheel reproducibility, clean installation, platform
smoke tests, and exact-wheel offline and service demos.

## Release sequence

1. Implement and validate the quality patch on a branch from main.
2. Merge the green release candidate to main.
3. Download and verify the exact main-CI wheel.
4. Upload only that wheel to PyPI with Twine.
5. Verify the PyPI filename, version, size, and SHA-256 value.
6. Create v0.8.1 on the exact tested commit.
7. Let the tag workflow verify PyPI and create the GitHub release.
8. Publish and verify the matching praval-ai documentation.

## Exclusions

This patch will not add runtime APIs, provider capabilities, realtime sessions,
MCP resources or server hosting, provider dependency restructuring, branch
coverage enforcement, or broad internal module changes.
