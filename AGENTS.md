# Repository workflow

The user wants required GitHub Actions run after changes are applied to this
repository. Workflow updates needed for the change are authorized. Run and
review validation and IPA builds; investigate failures and fix them. Do not
add `[skip ci]` unless the user explicitly asks to skip a particular execution.

Preserve the three Tor routing modes and fail-closed Tor requests. Distinguish
source/model tests, macOS integration checks, actual Gecko runtime and iPhone
verification. Do not claim runtime/device success from preferences or mocks.

For long builds, report the run URL and arrange completion review rather than
claiming an IPA exists before artifact upload succeeds. Reuse compatible engine
assets, but include every engine-affecting source transformation in cache keys.
