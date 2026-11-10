# Debian release packaging

This runbook covers the Debian repository work for a Foreman release. The generated [branching](branch.md.erb) and [release](release.md.erb) procedures remain the release checklists. For general packaging and build-system information, see the [Foreman infrastructure packaging documentation](https://theforeman.github.io/foreman-infra/packaging/).

## Branching for a release

Create the numbered production repository from nightly, then populate the staging repository used for builds. These repositories initially contain existing dependencies; creating them does not build or release the new Foreman version. Production and staging use separate Freight libraries and caches on `repo-deb01.osuosl.theforeman.org`.

1. Confirm the release version and supported Debian and Ubuntu suites with the current release CI configuration and release team. The examples below use `5.1`, `bookworm`, `jammy`, `noble`, and `trixie`; replace these values for the release being prepared. Include the shared plugins repository in production if it is part of the release.
2. Coordinate with other repository publishers. Check available space, that each nightly source exists, and that none of the destination components already exist. The operations below are not safe to rerun against a partial or existing destination. If any step fails, stop and inspect the affected libraries and caches before deciding how to resume.
3. Connect to `repo-deb01.osuosl.theforeman.org` and switch to the `freight` account:

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
     targets=()
     for suite in "${SUITES[@]}" plugins; do targets+=("apt/$suite"); done
     ((${#targets[@]} > 0)) || { echo 'No cache targets; refusing a global rebuild' >&2; exit 1; }
     freight cache -v -k -c "$HOME/freight.conf" "${targets[@]}"
   )
   ```

   Omit `plugins` if its library was not changed. A distribution argument rebuilds **all components** of that distribution, not only the new release. Do not run `freight cache` without distribution arguments: it rebuilds every distribution. The `-k` option skips pool-wide cleanup, even for unreferenced files; plan any necessary cleanup separately and monitor disk space.

6. Exit the `freight` shell, switch to `freightstage`, and set `RELEASE` and `SUITES` again:

   ```sh
   sudo -u freightstage -i
   ```

   ```bash
   RELEASE=5.1
   SUITES=(bookworm jammy noble trixie)
   ```

   Use the same reviewed release and OS suites as in production. The shared plugins repository is not imported by the historical staging procedure.

7. Add the production binary packages to the new staging components. This checks all staging destinations before starting and stops on an error:

   ```bash
   (
     set -euo pipefail
     shopt -s nullglob
     [[ "$RELEASE" =~ ^[0-9]+\.[0-9]+$ ]] || { echo 'Set a major.minor release' >&2; exit 1; }
     ((${#SUITES[@]} > 0)) || { echo 'No OS suites selected' >&2; exit 1; }
     for suite in "${SUITES[@]}"; do
       source_dir="/var/www/freight/apt/$suite/$RELEASE"
       target_dir="/var/www/freightstage/apt/$suite/theforeman-$RELEASE"
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
     targets=()
     for suite in "${SUITES[@]}"; do targets+=("apt/$suite"); done
     ((${#targets[@]} > 0)) || { echo 'No cache targets; refusing a global rebuild' >&2; exit 1; }
     freight cache -v -k -c "$HOME/freight.conf" "${targets[@]}"
   )
   ```

9. Verify both publications. Check the signatures and components in the production `InRelease` files at `https://deb.theforeman.org/dists/<suite>/InRelease` and the staging files at `https://stagingdeb.theforeman.org/dists/<suite>/InRelease`, using the trusted repository signing key. Production should list the numbered component; staging should list `theforeman-<release>`. Check package-index checksums and representative package URLs, and confirm existing components remain available. Allow for CDN propagation. A repository index does not by itself prove that the release packages can be installed.

10. Separately create `deb/<release>` in [foreman-packaging](https://github.com/theforeman/foreman-packaging) from a freshly fetched `deb/develop`, as directed by the generated branching procedure. Check that the remote branch does not already exist; never overwrite an existing release branch.

## Release candidates and stable releases

The numbered repository and `deb/<release>` packaging branch are used for release candidates, the stable release, and subsequent point releases. Nightly builds can provide preliminary evidence before branching, but they do not replace testing the release packages.

Follow the generated release procedure to update Debian packaging and changelogs, review and merge the required packaging changes, wait for package builds, and run the release pipeline. Ensure any missing dependencies are available in the numbered repository. Validate the packages and release pipeline before publication; Foreman, Smart Proxy, and the installer all follow the release packaging process.

The historical Debian Packaging wiki contains old manual job parameters, hosts, and stable-link instructions. Do not assume those instructions reflect the current Jenkins or repository workflow.
