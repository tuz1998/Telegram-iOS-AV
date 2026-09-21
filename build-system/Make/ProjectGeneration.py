import json
import os
import shutil

from BuildEnvironment import is_apple_silicon, call_executable, BuildEnvironment


def remove_directory(path):
    if os.path.isdir(path):
        shutil.rmtree(path)


def apply_xcode_27_framework_workaround(xcodeproj_path):
    script_path = os.path.join(xcodeproj_path, 'rules_xcodeproj/bazel/copy_outputs.sh')
    if not os.path.isfile(script_path):
        return

    with open(script_path, 'r') as file:
        contents = file.read()

    marker = '      if [[ -n "${TEST_HOST:-}" ]]; then\n'
    if marker not in contents or 'Xcode 27 copies the placeholder Swift module' in contents:
        return

    workaround = '''      # Some macOS system rsync versions ignore `--chmod` for directories
      # copied from Bazel's read-only output tree. Xcode subsequently updates
      # the proxy framework's Info.plist, so guarantee owner write access.
      if [[ -n "${WRAPPER_NAME:-}" ]]; then
        chmod -R u+w "$TARGET_BUILD_DIR/$WRAPPER_NAME"
      fi

      # Xcode 27 copies the placeholder Swift module emitted for Bazel-mode
      # proxy framework targets. Bazel framework outputs intentionally do not
      # include that Xcode-only directory, so create its destination first.
      if [[ "${WRAPPER_EXTENSION:-}" == "framework" && \\
            -n "${PRODUCT_MODULE_NAME:-}" ]]; then
        mkdir -p "$TARGET_BUILD_DIR/$WRAPPER_NAME/Modules/$PRODUCT_MODULE_NAME.swiftmodule"
      fi

'''
    with open(script_path, 'w') as file:
        file.write(contents.replace(marker, workaround + marker))


def generate_xcodeproj(build_environment: BuildEnvironment, disable_extensions, disable_provisioning_profiles, include_release, generate_dsym, bazel_app_arguments, target_name):
    if '/' in target_name:
        app_target_spec = target_name.split('/')[0] + '/' + target_name.split('/')[1] + ':' + target_name.split('/')[1]
        app_target = target_name
        app_target_clean = app_target.replace('/', '_')
    else:
        app_target_spec = '{target}:{target}'.format(target=target_name)
        app_target = target_name
        app_target_clean = app_target.replace('/', '_')

    bazel_generate_arguments = [build_environment.bazel_path]

    bazel_generate_arguments += ['run', '//{}_xcodeproj'.format(app_target_spec)]

    if target_name == 'Telegram':
        if disable_extensions:
            bazel_generate_arguments += ['--//{}:disableExtensions'.format(app_target)]
        bazel_generate_arguments += ['--//{}:disableStripping'.format(app_target)]

    project_bazel_arguments = []
    for argument in bazel_app_arguments:
        project_bazel_arguments.append(argument)

    if target_name == 'Telegram':
        if disable_extensions:
            project_bazel_arguments += ['--//{}:disableExtensions'.format(app_target)]
        project_bazel_arguments += ['--//{}:disableStripping'.format(app_target)]

    project_bazel_arguments += ['--features=-swift.debug_prefix_map']
    project_bazel_arguments += ['--features=swift.emit_swiftsourceinfo']
    
    xcodeproj_bazelrc = os.path.join(build_environment.base_path, 'xcodeproj.bazelrc')
    if os.path.isfile(xcodeproj_bazelrc):
        os.unlink(xcodeproj_bazelrc)
    with open(xcodeproj_bazelrc, 'w') as file:
        for argument in project_bazel_arguments:
            file.write('build ' + argument + '\n')

    call_executable(bazel_generate_arguments)

    xcodeproj_path = '{}.xcodeproj'.format(app_target_spec.replace(':', '/'))
    apply_xcode_27_framework_workaround(xcodeproj_path)
    return xcodeproj_path


def generate(build_environment: BuildEnvironment, disable_extensions, disable_provisioning_profiles, include_release, generate_dsym, bazel_app_arguments, target_name) -> str:
    return generate_xcodeproj(build_environment, disable_extensions, disable_provisioning_profiles, include_release, generate_dsym, bazel_app_arguments, target_name)
