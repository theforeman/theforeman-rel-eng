# The Foreman Release Engineering scripts

A collection of small scripts, adhering to the [Unix philosophy](https://en.wikipedia.org/wiki/Unix_philosophy), used to release [The Foreman](https://theforeman.org).
They automate parts of the [branch](https://github.com/theforeman/theforeman-rel-eng/blob/master/procedures/foreman/branch.md.erb) and [release](https://github.com/theforeman/theforeman-rel-eng/blob/master/procedures/foreman/release.md.erb) processes.
It is also used for the [Katello](https://theforeman.org/plugins/katello/) [branch](https://github.com/theforeman/theforeman-rel-eng/blob/master/procedures/katello/branch.md.erb) and [release](https://github.com/theforeman/theforeman-rel-eng/blob/master/procedures/katello/release.md.erb) processes.

The most important environment variables are `PROJECT` and `VERSION`.

## Procedures

Procedures are kept in the `procedures` directory.

### Roles

Both the branch and release procedures defines two roles: an owner and an engineer.
Someone can be both owner and engineer at the same time, and it is preferable for a fast process.
Having both in (very) different timezones can lengthen the process.
Sometimes it's just not possible and multiple people perform the procedures.
Below is a listing of access used.

#### Foreman release owner

* Belong to the [Foreman GitHub release-managers team](https://github.com/orgs/theforeman/teams/release-managers)
* Belong to the [releases](https://community.theforeman.org/g/releases) group on [Discourse](https://community.theforeman.org/)
* Matrix: permission to change the topic in [#theforeman on matrix.org](https://matrix.to/#/#theforeman:matrix.org). See [Matrix moderation](https://matrix.org/docs/communities/moderation/) on how channel admins can grant this.
* Redmine access: be added to the [Developers group](https://projects.theforeman.org/groups/44213/edit?tab=users)
* Transifex account (unclear on the exact permissions to extract translations)

#### Foreman release engineer

* Belong to the [Foreman GitHub release-engineering team](https://github.com/orgs/theforeman/teams/release-engineering)
* [Foreman infrastructure access](https://theforeman.github.io/foreman-infra/#access) including [secrets](https://theforeman.github.io/foreman-infra/secrets/)
* [Jenkins access](https://theforeman.github.io/foreman-infra/jenkins/#access)
* [stagingyum access](https://github.com/theforeman/foreman-infra/blob/master/puppet/data/common.yaml#L8)
* [theforeman Fedora group member](https://copr.fedorainfracloud.org/groups/g/theforeman/coprs/) which can be viewed [through Fedora Account System](https://accounts.fedoraproject.org/?next=/group/theforeman/%3F)

#### Katello release owner

* Write permission to [Katello/katello](https://github.com/Katello/katello)
* Push access to the [Katello gem](https://rubygems.org/gems/katello)
* Belong to the [Foreman GitHub katello-release-owners team](https://github.com/orgs/theforeman/teams/katello-release-owners)
* Belong to the `releases` group on [Discourse](https://community.theforeman.org/)
* Redmine access: be added to the [Developers group](https://projects.theforeman.org/groups/44213/edit?tab=users)

#### Katello release engineer

These are the same as Foreman's release engineer.

### Branching

Use `procedure_branch` to display the steps. Modify `PROJECT` and `VERSION` as needed.

```sh
PROJECT=foreman VERSION=3.7 ./procedure_branch
```

It will have created `releases/${PROJECT}/${VERSION}/settings`, which should be submitted as a pull request.

A more advanced invocation is to specify the parameters directly and copy the output.
This uses `wl-copy` for Wayland; `xclip` achieves the same for Xorg.

```
PROJECT=foreman VERSION=3.7 ./procedure_branch 2023-05-23 TheOwner TheEngineer | wl-copy
```

Now post this to [Discourse Development/Releases](https://community.theforeman.org/c/development/releases/20) as `$PROJECT $VERSION branching process`.
Follow the process as instructed.

### Release

First make sure you have fetched, pulled in the latest commits and rebased your fork. Secondly ensure `releases/${PROJECT}/${VERSION}/settings` contains the correct `FULLVERSION`. Modify as needed and submit as a pull request.
Then generate the procedure, similar to the branching process:

```sh
PROJECT=foreman VERSION=3.7 ./procedure_release
```

Or the complete version:
```
PROJECT=foreman VERSION=3.7 ./procedure_release 2023-05-23 TheOwner TheEngineer | wl-copy
```

Now post this to [Discourse Development/Releases](https://community.theforeman.org/c/development/releases/20) as `$PROJECT $FULLVERSION release process`.
Follow the process as instructed.

## Setup

Python and [python-jenkins](https://pypi.org/project/python-jenkins/) are needed.
On Fedora this can be installed:

```sh
dnf install python3-jenkins
```

GitHub CLI is required for creating pull requests during packaging updates. See the [installation instructions](https://cli.github.com/) for your platform.

For Redmine integration, python-redmine needs to be installed:

```sh
pip install python-redmine
```

Or, alternatively, there is a [Fedora build](https://copr.fedorainfracloud.org/coprs/ekohl/python-redmine).


Foreman requires GPG signed git tags. Configure git with your personal gpg key id as your signing key:

```
git config --global user.signingKey <YOUR_PUB_KEY_HASH>
```

### Gopass

For storing secrets, [gopass](https://github.com/gopasspw/gopass) is used.
On Fedora it can be installed:

```sh
dnf install gopass
```

Then make sure you have a GPG key on your system and initialize gopass with your key:

```
gopass init <YOUR-PUB-KEY-HASH>
```

For running jobs in Jenkins, make sure you have [access](https://theforeman.github.io/foreman-infra/jenkins/#access) and add your Jenkins password or API token:

```
gopass edit --create theforeman/jenkins-token
```

### Copr

Copr is where all packages are built and the stage repositories are generated from for releases. API access is needed in order to perform release activities. To ensure you have Copr access setup:

 1. Go to https://copr.fedorainfracloud.org/api/
 2. Login if you are not already
 3. Follow the directions

#### Release engineers

For commands on the Foreman infrastructure, add your personal `sudo` password:

```
gopass edit --create theforeman/unix
```

The releases store from the [shared secret storage](https://theforeman.github.io/foreman-infra/secrets/) is also needed:

```
gopass clone secrets.theforeman.org:/srv/secretsgit/theforeman-release.git theforeman/releases
```

### Importing an existing release

When a GPG key has already been generated, it can be imported from the backups:

```bash
import_gpg_private
```

## Typical release flow

Make sure `VERSION` is correct in `settings` and `FULLVERSION` in `releases/$PROJECT/$VERSION/settings`. This assumes a GPG key is already present.

```bash
./tag_project
./release_tarballs
./download_tarballs
./inspect_tarballs
./sign_tarballs
./bump_deb_packaging
./bump_rpm_packaging
./release_packages
# These steps can happen during the build after RPMs have been built but DEBs are still running
./generate_stage_repository
./sign_stage_rpms
./upload_stage_rpms
```

When handling non-Foreman releases (currently supported: Katello and Client), set `PROJECT` to the lowercase name of the project and `VERSION` to the version of the project (if it differs from the Foreman one).

```bash
PROJECT=client ./generate_stage_repository
PROJECT=katello VERSION=3.13 ./generate_stage_repository
```

### Generating a new GPG Key for a X.Y release

When starting a new release, the following scripts can be used to generate a new key:

```bash
generate_gpg           # Generate new GPG key in isolated keydir
export_gpg_private     # Backup private key to gopass
export_gpg_public      # Export clean public key for website
sign_gpg               # Sign key for web-of-trust
upload_gpg             # Upload to keyserver
```

**IMPORTANT:** The published key must contain only the self-signature. Third-party signatures break RPM imports. See [community discussion](https://community.theforeman.org/t/unable-to-register-an-almalinux-8-client-into-foreman-3-17-server-key-import-failed-code-2-failing-package-is-katello-host-tools-4-5-0-2-el8-noarch/45374) for technical details.

**About `sign_gpg`:**
The `sign_gpg` script is for web-of-trust use only. It exports the key to your main GPG keyring and allows signing with your personal key. The signed version must **never** be re-imported to the isolated keydir. Both `export_gpg_private` and `export_gpg_public` include automatic verification to prevent accidentally exporting keys with third-party signatures.

### Generating a new GPG Key for signing the Debian repository

Our Debian repository doesn't rotate keys based on releases, but on a time basis.

To generate a new key:

```bash
export PROJECT=foreman-debian
export VERSION="$(date '+%Y')"
generate_gpg
export_gpg_private
export_gpg_public
sign_gpg
upload_gpg
```

## Settings and customizing them

Settings can be customized in `settings.local`. The following settings are supported:

```sh
GIT_DIR=$HOME/dev # Projects are cloned here
GIT_REMOTE=upstream # Git remote for cloned projects
PACKAGING_PR=true # Create a PR in bump_{deb,rpm}_packaging
PACKAGING_FORK_REMOTE=origin # Git remote name for your foreman-packaging fork (defaults to your GitHub username)
GITHUB_USER=yourusername # Your GitHub username (defaults to your shell's username)
```

## Generating Stage Repository

The `build_stage_repository` script generates a stage repository locally that can then be uploaded to the staging repository server or used locally for testing. This is done for RPMs and SRPMs. The workflow for each is:

For releases (executed by release owner):

    1. Uses reposync to copy all RPMs from production (yum.theforeman.org) to a local repository
    2. Run repodiff comparing the local copy of production and Copr for the release
    3. Download the new packages from Copr
    4. Filter all packages through comps file, removing anything not in the comps file
    5. Runs createrepo
    6. Generates a new module metadata file based upon the local repository
    7. Generate list of unsigned RPMs
    8. Sign the unsigned RPMs
    9. Update the repository metadata

For nightly (executed by Jenkins):

    1. Copy all RPMs from Copr for the given repository to local
    2. Filter the downloaded RPMs through comps file, removing anything not in the comps file
    3. Runs createrepo
    4. Generates a new module metadata file based upon the local repository

The local repository can then be uploaded to the server backing stagingyum.theforeman.org using rsync. Where any RPM found locally already in staging is kept, and any RPM found in staging not in the local repository is removed.

### Performing the release workflow

The release workflow is execute using the following actions:

```
generate_stage_repository
sign_stage_repository
upload_stage_repository
```
