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
* Belong to the `releases` group on [Discourse](https://community.theforeman.org/)
* IRC: permission to change the topic in [#theforeman on Libera.Chat](ircs://irc.libera.chat/theforeman). See [Libera.Chat permissions](https://libera.chat/guides/creatingchannels#setting-up-permissions) on how channel owners can grant this.
* Redmine access: be added to the [Developers group](https://projects.theforeman.org/groups/44213/edit?tab=users)
* Transifex account (unclear on the exact permissions to extract translations)

#### Foreman release engineer

* Belong to the [Foreman GitHub release-engineering team](https://github.com/orgs/theforeman/teams/release-engineering)
* [Foreman infrastructure access](https://theforeman.github.io/foreman-infra/#access) including [secrets](https://theforeman.github.io/foreman-infra/secrets/)
* [Jenkins access](https://theforeman.github.io/foreman-infra/jenkins/#access)
* [Koji access](https://theforeman.github.io/foreman-infra/koji/#using-koji-as-a-user)

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
gopass edit theforeman/jenkins-token --create
```

#### Release engineers

For commands on the Foreman infrastructure, add your personal `sudo` password:

```
gopass edit theforeman/unix --create
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
./download_rpms
./sign_rpms
./upload_rpm_signatures
./upload_rpms
./process_rpms
```

When handling non-Foreman releases (currently supported: Katello and Client), set `PROJECT` to the lowercase name of the project and `VERSION` to the version of the project (if it differs from the Foreman one).

```bash
PROJECT=client ./download_rpms
PROJECT=katello VERSION=3.13 ./download_rpms
```

### Generating a new GPG Key for a X.Y release

When starting a new release, the following scripts can be used to generate a new key:

```bash
generate_gpg
export_gpg_private
export_gpg_public
sign_gpg
upload_gpg
```

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
KOJI_CMD=koji # Invoke koji. Change this if you also have Koji set up for Fedora development
PACKAGING_PR=true # Create a PR in bump_{deb,rpm}_packaging
```
