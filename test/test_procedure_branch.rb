# frozen_string_literal: true

require 'fileutils'
require 'minitest/autorun'
require 'open3'
require 'tmpdir'

class ProcedureBranchTest < Minitest::Test
  ROOT = File.expand_path('..', __dir__)
  BRANCH_ARGS = %w[branch --project foreman --release 5.1 --target-date 2026-11-10 --owner owner --engineer engineer].freeze

  def run_procedure(*args, root: ROOT)
    Open3.capture3('ruby', File.join(root, 'procedure'), *args, chdir: root)
  end

  def test_foreman_branch_uses_explicit_katello_version
    output, _error, status = run_procedure(*BRANCH_ARGS, '--katello-version', '4.99')
    assert status.success?
    assert_includes output, './branch-foreman 5.1 4.99'
    assert_includes output, "s/nightly/4.99/"
    assert_includes output, 'KATELLO_VERSION=4.99 ./branch_project'
    refute_includes output, 'KATELLO_VERSION_HERE'
    assert_operator output.index('Create a `deb/5.1` branch'), :<, output.index('DEB: verify automation')
  end

  def test_foreman_branch_rejects_missing_or_invalid_katello_version
    _output, _error, missing = run_procedure(*BRANCH_ARGS)
    refute missing.success?
    _output, _error, invalid = run_procedure(*BRANCH_ARGS, '--katello-version', 'nightly')
    refute invalid.success?
  end

  def test_foreman_release_does_not_require_a_katello_version
    _output, _error, status = run_procedure('release', '--project', 'foreman', '--version', '5.1.0-rc1', '--target-date', '2026-11-10', '--owner', 'owner')
    assert status.success?
  end

  def test_wrapper_passes_the_configured_katello_version
    Dir.mktmpdir('procedure-wrapper-test') do |dir|
      FileUtils.cp(File.join(ROOT, 'procedure_branch'), dir)
      File.write(File.join(dir, 'settings'), "PROJECT=foreman\nVERSION=5.1\n")
      File.write(File.join(dir, 'procedure'), "#!/bin/bash\nprintf '%s\\n' \"$@\"\n")
      FileUtils.chmod(0o755, File.join(dir, 'procedure'))
      output, _error, status = Open3.capture3({ 'KATELLO_VERSION' => '4.99' }, 'bash', './procedure_branch', '2026-11-10', 'owner', 'engineer', chdir: dir)
      assert status.success?
      assert_match(/--katello-version\n4\.99\n/, output)
    end
  end

  def test_dirty_template_warning_does_not_pollute_generated_output
    Dir.mktmpdir('procedure-test') do |dir|
      FileUtils.mkdir_p(File.join(dir, 'procedures', 'foreman'))
      FileUtils.cp(File.join(ROOT, 'procedure'), dir)
      template = File.join(dir, 'procedures', 'foreman', 'branch.md.erb')
      File.write(template, 'Test <%= katello_version %>')
      system('git', 'init', '-q', dir, out: File::NULL, err: File::NULL, exception: true)
      system('git', '-C', dir, 'add', 'procedure', 'procedures', exception: true)
      system('git', '-C', dir, '-c', 'user.name=Procedure Test', '-c', 'user.email=procedure@example.test', 'commit', '-qm', 'Initial', exception: true)

      clean_output, clean_error, clean_status = run_procedure(*BRANCH_ARGS, '--katello-version', '4.99', root: dir)
      assert clean_status.success?
      assert_equal '', clean_error
      assert_includes clean_output, 'Test 4.99'

      File.write(template, 'Changed <%= katello_version %>')
      output, error, status = run_procedure(*BRANCH_ARGS, '--katello-version', '4.99', root: dir)
      assert status.success?
      assert_includes output, 'Changed 4.99'
      assert_includes error, 'uncommitted changes or is untracked'
      refute_includes output, 'Warning:'

      system('git', '-C', dir, 'add', 'procedures/foreman/branch.md.erb', exception: true)
      _output, staged_error, staged_status = run_procedure(*BRANCH_ARGS, '--katello-version', '4.99', root: dir)
      assert staged_status.success?
      assert_includes staged_error, 'uncommitted changes or is untracked'
    end
  end
end
