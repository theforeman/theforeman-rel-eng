# Hammer CLI release

The Foreman release team maintains [hammer-cli](https://github.com/theforeman/hammer-cli)
(core) and [hammer-cli-foreman](https://github.com/theforeman/hammer-cli-foreman)
(the plugin). When a release is needed, follow these steps separately for each
gem, including patch releases. Foreman's generic branch, version-bump, and tag
scripts do not cover them.

## Choose versions and prepare branches

1. Compare each stable or development branch with its last published tag.
   Review user-facing changes, compatibility, release notes, packaging needs,
   and the plugin gemspec's core dependency.
2. Decide and record a version for each gem. A new Foreman version does not
   automatically require a new core release. Confirm that the chosen core
   version satisfies the plugin and stable packaging dependencies.
3. For a new series, create each `<series>-stable` branch from its reviewed
   source and verify the branch. Prepare version and release-note changes on
   the appropriate stable branch. After branching, prepare the next-development
   version bumps on master separately. Use each repository's review and
   branch-protection process.

## Test the release candidates

1. Run the repository test suites and CI matrix for the candidate commits.
   Test the selected core and plugin together against the target Foreman
   version.
2. Exercise populated parameters in human, JSON, YAML, and CSV output. Compare
   keys and fields, including undeclared fields such as `is_property`. Check
   that CSV flattening is intentional.
3. Check for the known 5.1.0 plugin regression affecting human, JSON, and YAML
   output and omitted fields (see the [release notes](https://github.com/theforeman/hammer-cli-foreman/blob/5.1.0/doc/release_notes.md)).
   The subsequent [fix #671](https://github.com/theforeman/hammer-cli-foreman/pull/671)
   was later [reverted in #673](https://github.com/theforeman/hammer-cli-foreman/pull/673).
   Check whether the version being released contains a working fix. A commit
   in the history is not enough if it was later reverted.
4. Resolve regressions or obtain an explicit release-owner exception. Document
   any exception's user impact and follow-up. A passing unit suite alone is
   not enough.

## Check translations and compiled catalogs

1. Before updating translations, inspect the candidate's `gettext:find_new`
   implementation. The [5.1.0 implementation](https://github.com/theforeman/hammer-cli/blob/5.1.0/lib/hammer_cli/i18n/find_task.rb)
   can overwrite existing PO catalogs, and `tx:update` invokes it.
2. Do not run it against valuable catalogs until a reviewed safeguard is
   present and tested. Keep a recoverable clean checkout and review the locale
   diff. The [catalog safeguard](https://github.com/theforeman/hammer-cli/pull/411)
   is a reference, not proof that a particular stable branch contains it.
3. Check the candidate gem's compiled MO catalogs against their PO sources and
   the intended translation update. Presence or file count alone is not enough.
   For example, unpack a locally built candidate with `gem unpack`, inspect
   the locale files, and use `msgunfmt` and `msgfmt` to compare compiled
   messages with the reviewed PO files.
4. Investigate stale headers and unchanged content. The 5.1.0 gems included
   compiled catalogs, but their freshness was not established. Record any
   accepted translation limitation.

## Authorize publication

Publishing requires permission to push to the upstream repositories and access
to the configured GitHub Actions `release` environment and RubyGems trusted
publisher.

1. Before any tag push, inspect the workflow **at the candidate commit**.
   Confirm the intended tag and whether pushing it will publish. Obtain release
   authorization.
2. Check for an existing tag and gem version. Do not move or reuse a published
   tag.
3. Inspect the current workflow and any action it calls. Do not assume their
   behavior is unchanged. For reference, the historical 5.1.0 core
   [workflow](https://github.com/theforeman/hammer-cli/blob/5.1.0/.github/workflows/release.yml)
   triggers on every pushed tag, builds a gem and man page, checks that the gem
   filename matches the tag, and publishes via trusted credentials. The 5.1.0
   [plugin workflow](https://github.com/theforeman/hammer-cli-foreman/blob/5.1.0/.github/workflows/release.yml)
   delegates publication to `voxpupuli/ruby-release`.

Trusted publishing uses OIDC for authorization; it is not proof of gem
signing. Do not run a second manual `gem push` alongside the workflow.

## Tag and publish

1. Verify the exact version in each gemspec/version file, the stable commit,
   release notes, and local and remote tag state.
2. Confirm the current repository tag policy and workflow, then create the
   exact version tag. The 5.1.0 Hammer tags were lightweight and named exactly
   `5.1.0`. Foreman's generic script creates signed annotated tags; do not
   assume Foreman's signing policy applies to Hammer.
3. Push the approved tag. Watch the corresponding upstream Actions run,
   including build, release, environment approval, and propagation steps as
   applicable.
4. If the run fails or its outcome is ambiguous, stop. Inspect Actions and
   RubyGems before retrying, and coordinate recovery with maintainers:
   publication may already have occurred. Do not blindly push a replacement
   tag or gem.

## Verify artifacts and update packaging

1. For each release, record the repository, exact tag and commit, Actions run
   URL and outcome, RubyGems version URL, and SHA-256.
2. Download the published gem and compare its SHA-256 with RubyGems metadata.
   Also compare the built artifact if the workflow retains it. Verify the gem's
   version, dependencies, executables, and locales.
3. If the evidence differs or the built artifact has expired, investigate and
   record the limitation before packaging.
4. Update stable RPM and Debian packaging to the chosen published versions,
   including dependencies. Verify the final release builds and staging contents.
   A published gem or successful build alone does not prove package installability.
