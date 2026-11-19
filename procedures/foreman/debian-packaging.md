# Debian release packaging

This runbook covers the Debian repository work for a Foreman release. The generated [branching](branch.md.erb) and [release](release.md.erb) procedures remain the release checklists. For general packaging and build-system information, see the [Foreman infrastructure packaging documentation](https://theforeman.github.io/foreman-infra/packaging/).

## Branching for a release

Create the numbered production repository from nightly, then populate the staging repository used for builds. These repositories initially contain existing dependencies; creating them does not build or release the new Foreman version. Production and staging use separate Freight libraries and caches on `repo-deb01.osuosl.theforeman.org`.

1. Confirm the release version and supported Debian and Ubuntu suites with the current release CI configuration and release team. The examples below use `5.1`, `bookworm`, `jammy`, `noble`, and `trixie`; replace these values for the release being prepared. Include the shared plugins repository in production if it is part of the release.
2. Coordinate with other repository publishers and check available space. The operations below are not safe to rerun against a partial or existing destination. If any step fails, stop and inspect the affected libraries and caches before deciding how to resume.

   Before changing production, connect to `repo-deb01.osuosl.theforeman.org` and check staging as `freightstage`:

   ```sh
   sudo -u freightstage -i
   ```

   Set the release and OS suites for this release and check all staging destinations and eligible nightly binary packages. These commands require Bash:

   ```bash
   RELEASE=5.1
   SUITES=(bookworm jammy noble trixie)
   (
     set -euo pipefail
     [[ "$RELEASE" =~ ^[0-9]+\.[0-9]+$ ]] || { echo 'Set a major.minor release' >&2; exit 1; }
     ((${#SUITES[@]} > 0)) || { echo 'No OS suites selected' >&2; exit 1; }
     for suite in "${SUITES[@]}"; do
       [[ "$suite" =~ ^[a-z][a-z0-9-]*$ && "$suite" != plugins ]] || { echo "Invalid OS suite: $suite" >&2; exit 1; }
       source_dir="/var/www/freight/apt/$suite/nightly"
       target_dir="/var/www/freightstage/apt/$suite/theforeman-$RELEASE"
       test -d "$source_dir" || { echo "Missing source: $source_dir" >&2; exit 1; }
       if [[ -e "$target_dir" || -L "$target_dir" ]]; then
         echo "Staging destination already exists: $target_dir" >&2
         exit 1
       fi
       find "$source_dir" -maxdepth 1 -type f \
         \( -name '*.deb' -o -name '*.ddeb' \) ! -name '*9999*' -print -quit | grep -q . || {
           echo "No eligible binary packages in $source_dir" >&2; exit 1;
         }
     done
   )
   ```

   Exit the `freightstage` shell after the checks. If they fail, do not continue.
3. Switch to the `freight` account:

   ```sh
   sudo -u freight -i
   ```

   The following commands require Bash. Set the release and OS suite list **in this shell**, replacing the example values. Do not include `plugins` in `SUITES`; the production loops handle it separately:

   ```bash
   RELEASE=5.1
   SUITES=(bookworm jammy noble trixie)
   ```

4. Copy nightly into new production components. The historical release process excludes filenames containing `9999`, which identify nightly packages, from the copies. This example uses `rsync` to exclude them without deleting anything from the source:

   ```bash
   (
     set -euo pipefail
     [[ "$RELEASE" =~ ^[0-9]+\.[0-9]+$ ]] || { echo 'Set a major.minor release' >&2; exit 1; }
     ((${#SUITES[@]} > 0)) || { echo 'No OS suites selected' >&2; exit 1; }
     for suite in "${SUITES[@]}"; do
       [[ "$suite" =~ ^[a-z][a-z0-9-]*$ && "$suite" != plugins ]] || { echo "Invalid OS suite: $suite" >&2; exit 1; }
     done
     for suite in "${SUITES[@]}" plugins; do
       source_dir="/var/www/freight/apt/$suite/nightly"
       target_dir="/var/www/freight/apt/$suite/$RELEASE"
       test -d "$source_dir" || { echo "Missing source: $source_dir" >&2; exit 1; }
       if [[ -e "$target_dir" || -L "$target_dir" ]]; then
         echo "Destination already exists: $target_dir" >&2
         exit 1
       fi
     done
     for suite in "${SUITES[@]}" plugins; do
       source_dir="/var/www/freight/apt/$suite/nightly"
       target_dir="/var/www/freight/apt/$suite/$RELEASE"
       mkdir "$target_dir"
       rsync -a --exclude='/*9999*' "$source_dir/" "$target_dir/"
     done
   )
   ```

   Omit `plugins` from both loops if its production library is not being changed. Review the copied package names, versions, and architectures against the source, including the exclusions. The old instructions called for removing older duplicate versions; investigate duplicates and dependency requirements before removing anything. Do not blindly repeat the copy or delete files when recovering a partial run.

5. Rebuild the production cache for the changed distributions only:

   ```bash
   (
     set -euo pipefail
     [[ "$RELEASE" =~ ^[0-9]+\.[0-9]+$ ]] || { echo 'Set a major.minor release' >&2; exit 1; }
     ((${#SUITES[@]} > 0)) || { echo 'No OS suites selected' >&2; exit 1; }
     for suite in "${SUITES[@]}"; do
       [[ "$suite" =~ ^[a-z][a-z0-9-]*$ && "$suite" != plugins ]] || { echo "Invalid OS suite: $suite" >&2; exit 1; }
     done
     targets=()
     for suite in "${SUITES[@]}" plugins; do
       source_dir="/var/www/freight/apt/$suite/nightly"
       target_dir="/var/www/freight/apt/$suite/$RELEASE"
       test -d "$source_dir" && test -d "$target_dir" || { echo "Missing source or destination for $suite" >&2; exit 1; }
       differences=$(rsync -rlnic --delete --exclude='/*9999*' "$source_dir/" "$target_dir/")
       if [[ -n "$differences" ]]; then
         printf 'Copy differs for %s; do not publish:\n%s\n' "$suite" "$differences" >&2
         exit 1
       fi
       targets+=("apt/$suite")
     done
     ((${#targets[@]} > 0)) || { echo 'No cache targets; refusing a global rebuild' >&2; exit 1; }
     freight cache -v -k -c "$HOME/freight.conf" "${targets[@]}"
   )
   ```

   Omit `plugins` if its library was not changed. The `rsync -n` check is a dry run: it compares the copies, including extra files, without deleting anything. If nightly changed during the copy, review the differences before continuing. If an approved package removal intentionally makes the copy different, this guard will also stop the command; record and review the intended inventory before running a separately constructed, targeted cache command.

   A distribution argument rebuilds **all components** of that distribution, not only the new release. Do not run `freight cache` without distribution arguments: it rebuilds every distribution. The `-k` option skips pool-wide cleanup, even for unreferenced files; plan any necessary cleanup separately and monitor disk space.

6. Continue only if the production cache command completed successfully. If it failed, stop and resolve the failure before starting staging. Check the production signing key's fingerprint against the trusted repository key, then exit the `freight` shell, switch to `freightstage`, and set `RELEASE`, `SUITES`, and an architecture to verify:

   ```sh
   sudo -u freightstage -i
   ```

   ```bash
   RELEASE=5.1
   SUITES=(bookworm jammy noble trixie)
   VERIFY_ARCH=amd64
   ```

   Use the same reviewed release and OS suites as in production, and an architecture supported by the release. The historical staging procedure imports binary packages, not source packages or the shared plugins repository. If staging needs source packages, coordinate a separate source-package import and verify its source index; do not assume these commands provide one.

7. Add the production binary packages to the new staging components. This checks all staging destinations before starting and stops on an error:

   ```bash
   (
     set -euo pipefail
     shopt -s nullglob
     [[ "$RELEASE" =~ ^[0-9]+\.[0-9]+$ ]] || { echo 'Set a major.minor release' >&2; exit 1; }
     [[ "$VERIFY_ARCH" =~ ^[a-z0-9]+$ ]] || { echo 'Set a valid verification architecture' >&2; exit 1; }
     ((${#SUITES[@]} > 0)) || { echo 'No OS suites selected' >&2; exit 1; }
     production_cache=/var/www/vhosts/deb/htdocs
     for suite in "${SUITES[@]}"; do
       [[ "$suite" =~ ^[a-z][a-z0-9-]*$ && "$suite" != plugins ]] || { echo "Invalid OS suite: $suite" >&2; exit 1; }
       source_dir="/var/www/freight/apt/$suite/$RELEASE"
       target_dir="/var/www/freightstage/apt/$suite/theforeman-$RELEASE"
       release_file="$production_cache/dists/$suite/Release"
       index_path="$RELEASE/binary-$VERIFY_ARCH/Packages.gz"
       gpgv --keyring "$production_cache/keyring.gpg" "$release_file.gpg" "$release_file" || exit 1
       awk -v component="$RELEASE" '$1 == "Components:" { for (i = 2; i <= NF; i++) if ($i == component) found = 1 } END { exit !found }' "$release_file" || {
         echo "Production component missing for $suite" >&2; exit 1;
       }
       expected=$(awk -v path="$index_path" '$1 == "SHA256:" { section = 1; next } /^[^[:space:]]/ { section = 0 } section && $3 == path { print $1; exit }' "$release_file")
       test -n "$expected" || { echo "Production index missing from $release_file: $index_path" >&2; exit 1; }
       actual=$(sha256sum "$production_cache/dists/$suite/$index_path")
       [[ "${actual%% *}" == "$expected" ]] || { echo "Production index checksum mismatch for $suite" >&2; exit 1; }
       test -d "$source_dir" || { echo "Missing source: $source_dir" >&2; exit 1; }
       if [[ -e "$target_dir" || -L "$target_dir" ]]; then
         echo "Destination already exists: $target_dir" >&2
         exit 1
       fi
       packages=("$source_dir"/*.deb "$source_dir"/*.ddeb)
       ((${#packages[@]} > 0)) || { echo "No binary packages in $source_dir" >&2; exit 1; }
     done
     for suite in "${SUITES[@]}"; do
       packages=("/var/www/freight/apt/$suite/$RELEASE/"*.deb "/var/www/freight/apt/$suite/$RELEASE/"*.ddeb)
       for package in "${packages[@]}"; do
         freight-add -v -c "$HOME/freight.conf" "$package" "apt/$suite/theforeman-$RELEASE"
       done
     done
   )
   ```

   Inspect a partial import before retrying; do not assume `freight-add` is safe to repeat.

8. Rebuild only the staging distributions that changed:

   ```bash
   (
     set -euo pipefail
     [[ "$RELEASE" =~ ^[0-9]+\.[0-9]+$ ]] || { echo 'Set a major.minor release' >&2; exit 1; }
     ((${#SUITES[@]} > 0)) || { echo 'No OS suites selected' >&2; exit 1; }
     targets=()
     for suite in "${SUITES[@]}"; do
       [[ "$suite" =~ ^[a-z][a-z0-9-]*$ && "$suite" != plugins ]] || { echo "Invalid OS suite: $suite" >&2; exit 1; }
       source_dir="/var/www/freight/apt/$suite/$RELEASE"
       target_dir="/var/www/freightstage/apt/$suite/theforeman-$RELEASE"
       test -d "$source_dir" && test -d "$target_dir" || { echo "Missing source or destination for $suite" >&2; exit 1; }
       differences=$(rsync -rnic --delete --include='/*.deb' --include='/*.ddeb' --exclude='/*' "$source_dir/" "$target_dir/")
       if [[ -n "$differences" ]]; then
         printf 'Staging binaries differ for %s; do not publish:\n%s\n' "$suite" "$differences" >&2
         exit 1
       fi
       targets+=("apt/$suite")
     done
     ((${#targets[@]} > 0)) || { echo 'No cache targets; refusing a global rebuild' >&2; exit 1; }
     freight cache -v -k -c "$HOME/freight.conf" "${targets[@]}"
   )
   ```

   This `rsync -n` comparison is also a dry run. Investigate any missing, changed, or extra binary packages before publishing.

9. Verify both publications. Check the signatures and components in the production `InRelease` files at `https://deb.theforeman.org/dists/<suite>/InRelease` and the staging files at `https://stagingdeb.theforeman.org/dists/<suite>/InRelease`, using the trusted repository signing key. Production should list the numbered component; staging should list `theforeman-<release>`. Check package-index checksums and representative package URLs, and confirm existing components remain available. Allow for CDN propagation. A repository index does not by itself prove that the release packages can be installed.

10. Separately create `deb/<release>` in [foreman-packaging](https://github.com/theforeman/foreman-packaging) from a freshly fetched `deb/develop`, as directed by the generated branching procedure. Check that the remote branch does not already exist; never overwrite an existing release branch.

## Release candidates and stable releases

The numbered repository and `deb/<release>` packaging branch are used for release candidates, the stable release, and subsequent point releases. Nightly builds can provide preliminary evidence before branching, but they do not replace testing the release packages.

Follow the generated release procedure to update Debian packaging and changelogs, review and merge the required packaging changes, wait for package builds, and run the release pipeline. Ensure any missing dependencies are available in the numbered repository. Validate the packages and release pipeline before publication; Foreman, Smart Proxy, and the installer all follow the release packaging process.

The historical Debian Packaging wiki contains old manual job parameters, hosts, and stable-link instructions. Do not assume those instructions reflect the current Jenkins or repository workflow.
