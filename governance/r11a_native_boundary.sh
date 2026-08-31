#!/usr/bin/env bash
set -euo pipefail

IFS=$' \t\n'
umask 077
unset CDPATH GLOBIGNORE

readonly SCHEMA="R11A_NATIVE_BOUNDARY_MODEL_B_V1"
readonly MODEL="B_FRESH_AUTHENTICATED_HEAD_SOURCE"
readonly REPOSITORY="Mathisve1/onchain-wallet-intelligence-lab"
readonly SOURCE_PATH="governance/r11a_bytecode_boundary.c"
readonly BUILDER_PATH="governance/r11a_native_boundary.sh"
readonly ARTIFACT_NAME="sitecustomize.abi3.so"
readonly REFERENCE_NAME="sitecustomize.reference.so"
readonly SETUP_PYTHON_VERSION="3.12.13"
readonly SETUP_PYTHON_ARCHITECTURE="x64"
readonly SETUP_PYTHON_ACTION_SHA="a26af69be951a213d495a4c3e4e4022e16d87065"

die() {
    printf 'R11A native boundary: %s\n' "$*" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || die "required command is unavailable: $1"
}

sha256_file() {
    sha256sum -- "$1" | awk '{print $1}'
}

sha256_stream() {
    sha256sum | awk '{print $1}'
}

safe_absolute_path() {
    local value=$1
    [[ "$value" =~ ^/[A-Za-z0-9._/-]+$ ]] || die "path is outside the supported absolute-path grammar: $value"
    [[ "$value" != *//* ]] || die "path is not canonical: $value"
    [[ "$value" != *:* ]] || die "path contains a PYTHONPATH separator: $value"
}

physical_path() {
    local value
    value=$(readlink -f -- "$1")
    safe_absolute_path "$value"
    printf '%s\n' "$value"
}

assert_literal_github_filesystem_root_observation() {
    local resolved=$1
    local ownership_mode=$2
    local writable=$3
    local identity=$4

    [[ "$resolved" = / ]] || die "GitHub filesystem root is not canonical and physical"
    [[ "$ownership_mode" = 0:0:755 ]] || \
        die "GitHub filesystem root does not match the trusted ownership/mode contract"
    case "$writable" in
        false)
            ;;
        true)
            die "GitHub filesystem root is writable by the runner identity"
            ;;
        *)
            die "GitHub filesystem root writability observation is invalid"
            ;;
    esac
    [[ "$identity" =~ ^[0-9]+:[0-9]+$ ]] || \
        die "GitHub filesystem root identity observation is invalid"
    printf '%s\n' "$identity"
}

assert_literal_github_filesystem_root() {
    local resolved ownership_mode writable identity

    [[ $# = 0 ]] || die "literal GitHub filesystem root validator does not accept path arguments"
    [[ -d / && ! -L / ]] || die "GitHub filesystem root is not a physical directory"
    if ! resolved=$(/usr/bin/readlink -f -- /); then
        die "GitHub filesystem root canonical resolution failed"
    fi
    if ! ownership_mode=$(/usr/bin/stat -c '%u:%g:%a' -- /); then
        die "GitHub filesystem root ownership/mode inspection failed"
    fi
    if ! identity=$(/usr/bin/stat -c '%d:%i' -- /); then
        die "GitHub filesystem root identity inspection failed"
    fi
    writable=false
    if [[ -w / ]]; then
        writable=true
    fi
    assert_literal_github_filesystem_root_observation \
        "$resolved" "$ownership_mode" "$writable" "$identity"
}

assert_github_opt_ancestor_observation() {
    local physical=$1
    local resolved=$2
    local root_identity=$3
    local opt_identity=$4
    local ownership_mode=$5
    local writable=$6
    local phase=$7

    [[ "$physical" = true ]] || die "GitHub /opt ancestor is not a physical directory"
    [[ "$resolved" = /opt ]] || die "GitHub /opt ancestor is not canonical and physical"
    [[ "$root_identity" =~ ^[0-9]+:[0-9]+$ && "$opt_identity" =~ ^[0-9]+:[0-9]+$ ]] || \
        die "GitHub /opt ancestor identity observation is invalid"
    [[ "${opt_identity%%:*}" = "${root_identity%%:*}" ]] || \
        die "GitHub /opt ancestor is not on the trusted root filesystem"
    case "$writable" in
        true|false)
            ;;
        *)
            die "GitHub /opt ancestor writability observation is invalid"
            ;;
    esac
    case "$phase" in
        bootstrap)
            case "$ownership_mode" in
                0:0:777|0:0:755)
                    ;;
                *)
                    die "GitHub /opt ancestor does not match the exact bootstrap contract: $ownership_mode"
                    ;;
            esac
            ;;
        sealed)
            [[ "$ownership_mode" = 0:0:755 ]] || \
                die "GitHub /opt ancestor is not sealed root:root mode 0755"
            [[ "$writable" = false ]] || \
                die "GitHub /opt ancestor remains writable by the runner identity"
            ;;
        *)
            die "GitHub /opt ancestor observation phase is invalid"
            ;;
    esac
}

assert_filesystem_identity_stable() {
    local label=$1
    local expected=$2
    local observed=$3

    [[ "$expected" =~ ^[0-9]+:[0-9]+$ && "$observed" =~ ^[0-9]+:[0-9]+$ ]] || \
        die "$label identity observation is invalid"
    [[ "$observed" = "$expected" ]] || die "$label identity changed during sealing"
}

assert_regular_owned_file() {
    local path=$1
    local expected_mode=$2
    [[ -f "$path" && ! -L "$path" ]] || die "expected a regular non-symlink file: $path"
    [[ $(stat -c '%u' -- "$path") = "$(id -u)" ]] || die "file is not owned by the effective user: $path"
    [[ $(stat -c '%h' -- "$path") = 1 ]] || die "file has an unsafe hard-link count: $path"
    [[ $(stat -c '%a' -- "$path") = "$expected_mode" ]] || die "file has unsafe mode (expected $expected_mode): $path"
}

assert_owned_directory() {
    local path=$1
    local expected_mode=$2
    [[ -d "$path" && ! -L "$path" ]] || die "expected a real directory: $path"
    [[ $(stat -c '%u' -- "$path") = "$(id -u)" ]] || die "directory is not owned by the effective user: $path"
    [[ $(stat -c '%a' -- "$path") = "$expected_mode" ]] || die "directory has unsafe mode (expected $expected_mode): $path"
}

reject_build_overrides() {
    local name
    for name in \
        CC CFLAGS CPPFLAGS CXXFLAGS LDFLAGS CPATH C_INCLUDE_PATH \
        CPLUS_INCLUDE_PATH OBJC_INCLUDE_PATH LIBRARY_PATH COMPILER_PATH \
        GCC_EXEC_PREFIX LD_AUDIT LD_PRELOAD LD_LIBRARY_PATH LD_RUN_PATH \
        COLLECT_GCC_OPTIONS SOURCE_DATE_EPOCH \
        R11A_NATIVE_TRUSTED_PYTHON_CONFIG; do
        [[ -z ${!name-} ]] || die "unapproved build override is set: $name"
    done
}

assert_loader_environment_absent() {
    local name
    for name in LD_AUDIT LD_LIBRARY_PATH LD_PRELOAD LD_RUN_PATH; do
        [[ ! -v $name ]] || die "loader variable survived sanitization: $name"
    done
}

assert_setup_python_path() {
    local path=$1
    local kind=$2
    local label=$3
    local expected_uid=$4
    local mode uid numeric_mode

    case "$kind" in
        directory)
            [[ -d "$path" && ! -L "$path" ]] || die "setup-python $label is not a physical directory: $path"
            ;;
        file)
            [[ -f "$path" && ! -L "$path" ]] || die "setup-python $label is not a physical regular file: $path"
            ;;
        *)
            die "internal setup-python path kind is invalid: $kind"
            ;;
    esac
    [[ $(physical_path "$path") = "$path" ]] || die "setup-python $label is not canonical and physical: $path"
    if [[ "$kind" = file ]]; then
        [[ $(stat -c '%h' -- "$path") = 1 ]] || die "setup-python $label has an unsafe hard-link count: $path"
    fi
    uid=$(stat -c '%u' -- "$path")
    [[ "$uid" = "$expected_uid" ]] || die "setup-python $label owner differs from installation owner: $path"
    mode=$(stat -c '%a' -- "$path")
    numeric_mode=$((8#$mode))
    (( (numeric_mode & 8#022) == 0 )) || die "setup-python $label is group/world writable: $path"
    (( (numeric_mode & 8#7000) == 0 )) || die "setup-python $label has special permission bits: $path"
    if [[ "$uid" = "$(id -u)" ]]; then
        (( (numeric_mode & 8#200) == 0 )) || \
            die "setup-python $label is writable by the effective user: $path"
    fi
}

assert_setup_python_system_helper() {
    local path=$1
    local expected_mode=$2
    local label=$3
    [[ -f "$path" && ! -L "$path" ]] || die "setup-python $label is not a physical regular file: $path"
    [[ $(physical_path "$path") = "$path" ]] || die "setup-python $label is not canonical and physical: $path"
    [[ $(stat -c '%u:%g' -- "$path") = 0:0 ]] || die "setup-python $label is not root-owned: $path"
    [[ $(stat -c '%h' -- "$path") = 1 ]] || die "setup-python $label has an unsafe hard-link count: $path"
    [[ $(stat -c '%a' -- "$path") = "$expected_mode" ]] || \
        die "setup-python $label has an unexpected mode: $path"
}

assert_setup_python_tree_shape() {
    local root=$1
    local unsafe target mount_target mount_table link_targets

    if ! mount_table=$(
        /usr/bin/env -i PATH=/usr/bin:/bin \
            /usr/bin/findmnt -k -r -n -o TARGET
    ); then
        die "setup-python mount-table inspection failed"
    fi
    [[ -n "$mount_table" ]] || die "setup-python mount-table inspection returned no mounts"
    while IFS= read -r mount_target; do
        [[ "$mount_target" != "$root" && "$mount_target" != "$root/"* ]] || \
            die "setup-python installation contains a nested mount: $mount_target"
    done <<<"$mount_table"

    unsafe=$(find -P "$root" -xdev ! \( -type d -o -type f -o -type l \) -print -quit)
    [[ -z "$unsafe" ]] || die "setup-python installation contains a special file: $unsafe"
    unsafe=$(find -P "$root" -xdev -type f -links +1 -print -quit)
    [[ -z "$unsafe" ]] || die "setup-python installation contains a multiply linked file: $unsafe"
    if ! link_targets=$(
        find -P "$root" -xdev -type l -exec /usr/bin/readlink -f -- '{}' +
    ); then
        die "setup-python installation symlink inspection failed"
    fi
    if [[ -n "$link_targets" ]]; then
        while IFS= read -r target; do
            [[ "$target" = "$root"/* ]] || \
                die "setup-python installation symlink escapes the installation: $target"
        done <<<"$link_targets"
    fi
}

assert_frozen_setup_python_tree() {
    local root=$1
    local unsafe

    assert_setup_python_tree_shape "$root"
    unsafe=$(find -P "$root" -xdev ! -uid 0 -print -quit)
    [[ -z "$unsafe" ]] || die "setup-python installation contains a non-root-owned path: $unsafe"
    unsafe=$(find -P "$root" -xdev ! -type l -perm /022 -print -quit)
    [[ -z "$unsafe" ]] || die "setup-python installation contains a group/world-writable path: $unsafe"
    unsafe=$(find -P "$root" -xdev ! -type l -perm /7000 -print -quit)
    [[ -z "$unsafe" ]] || die "setup-python installation contains a path with special permission bits: $unsafe"
}

assert_github_opt_ancestor_sealed() {
    local root_identity opt_resolved opt_identity opt_contract opt_writable
    local opt_physical=false

    root_identity=$(assert_literal_github_filesystem_root)
    opt_resolved=
    opt_identity=
    opt_contract=
    opt_writable=unknown
    if [[ -d /opt && ! -L /opt ]]; then
        opt_physical=true
        opt_resolved=$(physical_path /opt)
        opt_identity=$(stat -c '%d:%i' -- /opt)
        opt_contract=$(stat -c '%u:%g:%a' -- /opt)
        opt_writable=false
        if [[ -w /opt ]]; then
            opt_writable=true
        fi
    fi
    assert_github_opt_ancestor_observation \
        "$opt_physical" "$opt_resolved" "$root_identity" "$opt_identity" \
        "$opt_contract" "$opt_writable" sealed
}

seal_github_opt_ancestor() {
    local root_identity opt_resolved opt_identity opt_contract opt_writable
    local observed_root_identity observed_opt_identity
    local opt_physical=false

    root_identity=$(assert_literal_github_filesystem_root)
    opt_resolved=
    opt_identity=
    opt_contract=
    opt_writable=unknown
    if [[ -d /opt && ! -L /opt ]]; then
        opt_physical=true
        opt_resolved=$(physical_path /opt)
        opt_identity=$(stat -c '%d:%i' -- /opt)
        opt_contract=$(stat -c '%u:%g:%a' -- /opt)
        opt_writable=false
        if [[ -w /opt ]]; then
            opt_writable=true
        fi
    fi
    assert_github_opt_ancestor_observation \
        "$opt_physical" "$opt_resolved" "$root_identity" "$opt_identity" \
        "$opt_contract" "$opt_writable" bootstrap

    # The exact Ubuntu hosted-runner image deliberately provisions /opt as
    # root:root 0777.  Seal that literal name-binding ancestor before any
    # hosted-toolcache descendant is inspected; never repair wrong ownership.
    /usr/bin/env -i PATH=/usr/bin:/bin \
        /usr/bin/sudo -n /usr/bin/chmod 0755 -- /opt

    observed_root_identity=$(assert_literal_github_filesystem_root)
    observed_opt_identity=$(stat -c '%d:%i' -- /opt)
    assert_filesystem_identity_stable \
        "GitHub filesystem root" "$root_identity" "$observed_root_identity"
    assert_filesystem_identity_stable \
        "GitHub /opt ancestor" "$opt_identity" "$observed_opt_identity"
    assert_github_opt_ancestor_sealed
}

assert_github_frozen_setup_python_tree() {
    local root=$1
    local runner_tool_cache=$2
    local path
    local -a chain=(
        /opt
        "$runner_tool_cache"
        "$runner_tool_cache/Python"
        "$runner_tool_cache/Python/$SETUP_PYTHON_VERSION"
        "$root"
    )

    assert_github_opt_ancestor_sealed
    for path in "${chain[@]}"; do
        assert_setup_python_path "$path" directory "trust-chain component" 0
    done
    assert_frozen_setup_python_tree "$root"
}

freeze_github_setup_python_tree() {
    local root=$1
    local runner_tool_cache=$2
    local path observed
    local -a chain=(
        /opt
        "$runner_tool_cache"
        "$runner_tool_cache/Python"
        "$runner_tool_cache/Python/$SETUP_PYTHON_VERSION"
        "$root"
    )
    local -a identities=()

    [[ $(id -u) != 0 ]] || die "GitHub setup-python trust bootstrap must run as the unprivileged runner identity"
    assert_setup_python_system_helper /usr/bin/env 755 "environment scrubber"
    assert_setup_python_system_helper /usr/bin/sudo 4755 "privilege boundary"
    assert_setup_python_system_helper /usr/bin/chown 755 "ownership helper"
    assert_setup_python_system_helper /usr/bin/chmod 755 "mode helper"
    assert_setup_python_system_helper /usr/bin/find 755 "tree-walk helper"
    assert_setup_python_system_helper /usr/bin/findmnt 755 "mount-table helper"
    assert_setup_python_system_helper /usr/bin/readlink 755 "symlink-resolution helper"

    seal_github_opt_ancestor

    for path in "${chain[@]}"; do
        [[ -d "$path" && ! -L "$path" ]] || die "setup-python trust-chain component is not a physical directory: $path"
        [[ $(physical_path "$path") = "$path" ]] || die "setup-python trust-chain component is not canonical and physical: $path"
        identities+=("$(stat -c '%d:%i' -- "$path")")
    done
    assert_setup_python_tree_shape "$root"

    # The pinned action runs before repository code.  Freeze its exact hosted
    # tool-cache path from the already scrubbed environment so the runner user
    # cannot mutate or rename loader, header, interpreter, or helper bytes.
    for path in "${chain[@]:1:3}"; do
        /usr/bin/env -i PATH=/usr/bin:/bin \
            /usr/bin/sudo -n /usr/bin/chown 0:0 -- "$path"
        /usr/bin/env -i PATH=/usr/bin:/bin \
            /usr/bin/sudo -n /usr/bin/chmod go-w -- "$path"
    done
    /usr/bin/env -i PATH=/usr/bin:/bin \
        /usr/bin/sudo -n /usr/bin/find -P "$root" -xdev \
        -exec /usr/bin/chown -h 0:0 -- '{}' +
    /usr/bin/env -i PATH=/usr/bin:/bin \
        /usr/bin/sudo -n /usr/bin/find -P "$root" -xdev ! -type l \
        -exec /usr/bin/chmod go-w -- '{}' +

    for path in "${!chain[@]}"; do
        observed=$(stat -c '%d:%i' -- "${chain[$path]}")
        [[ "$observed" = "${identities[$path]}" ]] || \
            die "setup-python trust-chain identity changed during freeze: ${chain[$path]}"
    done
    assert_github_frozen_setup_python_tree "$root" "$runner_tool_cache"
}

check_required_commands() {
    local name
    for name in \
        awk basename chmod cmp cp cut dirname env file find git grep id install \
        mkdir mktemp nm objdump od readelf readlink rm rmdir sed sha256sum \
        sort stat strings tail tr wc xargs; do
        require_command "$name"
    done
    require_command cc
}

bind_repository_file() {
    local path=$1
    local prefix=$2
    local expected_git_mode=$3
    local expected_worktree_mode=$4
    local index_entry tree_entry mode oid stage indexed_path tree_mode tree_type tree_oid tree_path debug flag

    index_entry=$(git ls-files --stage -- "$path")
    [[ $(printf '%s\n' "$index_entry" | wc -l) = 1 ]] || die "path does not have exactly one index entry: $path"
    read -r mode oid stage indexed_path <<<"$index_entry"
    [[ "$mode" = "$expected_git_mode" && "$stage" = 0 && "$indexed_path" = "$path" ]] || die "path has an unexpected index entry: $path"

    tree_entry=$(git ls-tree HEAD -- "$path")
    read -r tree_mode tree_type tree_oid tree_path <<<"$tree_entry"
    [[ "$tree_mode" = "$expected_git_mode" && "$tree_type" = blob && "$tree_oid" = "$oid" && "$tree_path" = "$path" ]] || die "HEAD/index mismatch for $path"

    [[ -f "$path" && ! -L "$path" ]] || die "worktree path is not a regular file: $path"
    [[ $(stat -c '%a' -- "$path") = "$expected_worktree_mode" ]] || die "worktree mode is not $expected_worktree_mode: $path"
    [[ $(stat -c '%h' -- "$path") = 1 ]] || die "worktree source has an unsafe hard-link count: $path"
    [[ $(git hash-object --no-filters -- "$path") = "$oid" ]] || die "worktree bytes differ from HEAD: $path"

    debug=$(git ls-files --debug -- "$path")
    [[ "$debug" == *$'flags: 0' ]] || die "index flags are not zero for $path"
    flag=$(git ls-files -v -- "$path")
    [[ ${flag:0:1} = H ]] || die "path has skip-worktree or assume-unchanged state: $path"

    printf -v "${prefix}_MODE" '%s' "$mode"
    printf -v "${prefix}_OID" '%s' "$oid"
    printf -v "${prefix}_SHA256" '%s' "$(sha256_file "$path")"
}

collect_repository_contract() {
    local status
    REPOSITORY_ROOT=$(physical_path "$(git rev-parse --show-toplevel)")
    cd "$REPOSITORY_ROOT"
    HEAD_COMMIT=$(git rev-parse --verify HEAD^{commit})
    [[ "$HEAD_COMMIT" =~ ^[0-9a-f]{40}$ ]] || die "HEAD is not a full commit ID"
    if [[ -n ${EXACT_CI_COMMIT-} ]]; then
        [[ "$EXACT_CI_COMMIT" =~ ^[0-9a-f]{40}$ ]] || die "EXACT_CI_COMMIT is malformed"
        [[ "$HEAD_COMMIT" = "$EXACT_CI_COMMIT" ]] || die "HEAD differs from EXACT_CI_COMMIT"
    fi
    HEAD_TREE=$(git rev-parse --verify HEAD^{tree})
    [[ $(git write-tree) = "$HEAD_TREE" ]] || die "index tree differs from HEAD"
    git diff --quiet --ignore-submodules=none -- || die "worktree differs from index"
    git diff --cached --quiet --ignore-submodules=none -- || die "index differs from HEAD"
    status=$(git status --porcelain=v1 --untracked-files=all --ignored=matching)
    [[ -z "$status" ]] || die "repository contains untracked, ignored, or modified material"
    if git ls-files --stage | awk '$3 != "0" {found=1} END {exit !found}'; then
        die "repository index contains a non-stage-zero entry"
    fi
    bind_repository_file "$SOURCE_PATH" SOURCE 100644 644
    bind_repository_file "$BUILDER_PATH" BUILDER 100755 755
}

header_inventory_sha256() {
    local include_root=$1
    (
        cd "$include_root"
        find . -type f -print0 | LC_ALL=C sort -z | xargs -0 -r sha256sum
    ) | sha256_stream
}

resolve_compiler_program() {
    local reported=$1
    local resolved
    if [[ "$reported" == */* ]]; then
        resolved=$(readlink -f -- "$reported")
    else
        resolved=$(command -v "$reported")
        resolved=$(readlink -f -- "$resolved")
    fi
    safe_absolute_path "$resolved"
    [[ -f "$resolved" && ! -L "$resolved" ]] || die "compiler subprogram is not a regular resolved file: $reported"
    printf '%s\n' "$resolved"
}

command_output_sha256() {
    "$@" 2>&1 | sha256_stream
}

collect_toolchain_contract() {
    local includes include_argument candidate python_version requested_python_config
    local -a include_arguments=()
    local -a unique_includes=()

    requested_python_config=${R11A_NATIVE_TRUSTED_PYTHON_CONFIG-}
    if [[ -n "$requested_python_config" ]]; then
        PYTHON_CONFIG_REALPATH=$(physical_path "$requested_python_config")
    else
        require_command python3-config
        PYTHON_CONFIG_REALPATH=$(physical_path "$(command -v python3-config)")
    fi
    [[ -f "$PYTHON_CONFIG_REALPATH" ]] || die "python3-config is not a regular file"
    PYTHON_CONFIG_SHA256=$(sha256_file "$PYTHON_CONFIG_REALPATH")
    includes=$("$PYTHON_CONFIG_REALPATH" --includes)
    read -r -a include_arguments <<<"$includes"
    (( ${#include_arguments[@]} > 0 )) || die "python3-config returned no include directory"
    for include_argument in "${include_arguments[@]}"; do
        [[ "$include_argument" == -I/* ]] || die "python3-config returned an unapproved include token: $include_argument"
        candidate=$(physical_path "${include_argument#-I}")
        [[ -d "$candidate" ]] || die "Python include directory does not exist: $candidate"
        if (( ${#unique_includes[@]} == 0 )); then
            unique_includes+=("$candidate")
        elif [[ "$candidate" != "${unique_includes[0]}" ]]; then
            die "python3-config returned multiple distinct include directories"
        fi
    done
    PYTHON_INCLUDE_REALPATH=${unique_includes[0]}
    python_version=$(awk '/^#define PY_VERSION / {gsub(/"/, "", $3); print $3; exit}' "$PYTHON_INCLUDE_REALPATH/patchlevel.h")
    [[ "$python_version" = 3.12.13 ]] || die "unsupported Python headers: $python_version"
    PYTHON_VERSION=$python_version
    PYTHON_HEADERS_SHA256=$(header_inventory_sha256 "$PYTHON_INCLUDE_REALPATH")

    CC_REALPATH=$(physical_path "$(command -v cc)")
    [[ -f "$CC_REALPATH" ]] || die "compiler is not a regular file"
    CC_SHA256=$(sha256_file "$CC_REALPATH")
    CC_VERSION_SHA256=$(command_output_sha256 "$CC_REALPATH" --version)
    CC_TARGET=$("$CC_REALPATH" -dumpmachine)
    [[ "$CC_TARGET" = x86_64-linux-gnu ]] || die "unsupported compiler target: $CC_TARGET"
    CC_SPECS_SHA256=$(command_output_sha256 "$CC_REALPATH" -dumpspecs)

    CC1_REALPATH=$(resolve_compiler_program "$("$CC_REALPATH" -print-prog-name=cc1)")
    CC1_SHA256=$(sha256_file "$CC1_REALPATH")
    COLLECT2_REALPATH=$(resolve_compiler_program "$("$CC_REALPATH" -print-prog-name=collect2)")
    COLLECT2_SHA256=$(sha256_file "$COLLECT2_REALPATH")
    ASSEMBLER_REALPATH=$(resolve_compiler_program "$("$CC_REALPATH" -print-prog-name=as)")
    ASSEMBLER_SHA256=$(sha256_file "$ASSEMBLER_REALPATH")
    ASSEMBLER_VERSION_SHA256=$(command_output_sha256 "$ASSEMBLER_REALPATH" --version)
    LD_REALPATH=$(resolve_compiler_program "$("$CC_REALPATH" -print-prog-name=ld)")
    LD_SHA256=$(sha256_file "$LD_REALPATH")
    LD_VERSION_SHA256=$(command_output_sha256 "$LD_REALPATH" --version)

    COMPILE_ARGUMENTS=(
        "$CC_REALPATH"
        -std=c11
        -O2
        -fPIC
        -fno-ident
        -fno-record-gcc-switches
        -fvisibility=hidden
        -Werror
        -Wdate-time
        -Werror=date-time
        -DPy_LIMITED_API=0x03080000
        "-I$PYTHON_INCLUDE_REALPATH"
        -shared
        -Wl,--build-id=none
        -Wl,-z,relro,-z,now
        -Wl,-z,noexecstack
        -o
        "$ARTIFACT_NAME"
        source.c
    )
    COMPILE_ARGV_SHA256=$(printf '%s\0' "${COMPILE_ARGUMENTS[@]}" | sha256_stream)
}

setup_python_adapter() {
    local operation=$1
    local env_file=$2
    local saved_python_location=${pythonLocation-}
    local saved_pkg_config_path=${PKG_CONFIG_PATH-}
    local saved_python_root=${Python_ROOT_DIR-}
    local saved_python2_root=${Python2_ROOT_DIR-}
    local saved_python3_root=${Python3_ROOT_DIR-}
    local saved_ld_audit=${LD_AUDIT-}
    local saved_loader_path=${LD_LIBRARY_PATH-}
    local saved_ld_preload=${LD_PRELOAD-}
    local saved_ld_run_path=${LD_RUN_PATH-}
    local saved_action_version=${R11A_SETUP_PYTHON_VERSION-}
    local saved_action_python_path=${R11A_SETUP_PYTHON_PATH-}
    local saved_internal_python_config=${R11A_NATIVE_TRUSTED_PYTHON_CONFIG-}
    local root loader bin_root include_root pkgconfig_root python_real config_prefix
    local installation_uid effective_uid runner_tool_cache runner_temp
    local scrubbed_probe
    local -a probe_lines=()

    case "$operation" in
        prepare|verify|cleanup)
            ;;
        *)
            die "unsupported setup-python adapter operation: $operation"
            ;;
    esac

    # Capture only with shell builtins, then remove every loader/setup hint
    # before the first repository, toolchain, hash, or inspection subprocess.
    unset \
        LD_AUDIT LD_LIBRARY_PATH LD_PRELOAD LD_RUN_PATH PKG_CONFIG_PATH \
        Python_ROOT_DIR Python2_ROOT_DIR Python3_ROOT_DIR pythonLocation \
        R11A_SETUP_PYTHON_VERSION R11A_SETUP_PYTHON_PATH \
        R11A_NATIVE_TRUSTED_PYTHON_CONFIG
    PATH=/usr/bin:/bin
    export PATH
    assert_loader_environment_absent

    [[ -z "$saved_internal_python_config" ]] || \
        die "unapproved build override is set: R11A_NATIVE_TRUSTED_PYTHON_CONFIG"
    [[ -z "$saved_ld_audit" ]] || die "unapproved build override is set: LD_AUDIT"
    [[ -z "$saved_ld_preload" ]] || die "unapproved build override is set: LD_PRELOAD"
    [[ -z "$saved_ld_run_path" ]] || die "unapproved build override is set: LD_RUN_PATH"
    [[ -n "$saved_python_location" ]] || die "setup-python pythonLocation is absent"
    [[ -n "$saved_loader_path" ]] || die "setup-python LD_LIBRARY_PATH is absent"
    [[ "$saved_python_location" != *:* ]] || die "setup-python pythonLocation contains a separator"
    [[ "$saved_loader_path" != *:* ]] || die "setup-python LD_LIBRARY_PATH must contain exactly one component"
    safe_absolute_path "$saved_python_location"
    safe_absolute_path "$saved_loader_path"
    [[ "$saved_python_location" != /tmp && "$saved_python_location" != /tmp/* ]] || \
        die "setup-python installation is under a temporary attacker-controlled path"
    [[ "$saved_loader_path" = "$saved_python_location/lib" ]] || \
        die "setup-python LD_LIBRARY_PATH does not exactly match pythonLocation/lib"
    [[ "$saved_pkg_config_path" = "$saved_python_location/lib/pkgconfig" ]] || \
        die "setup-python PKG_CONFIG_PATH does not exactly match pythonLocation/lib/pkgconfig"
    [[ "$saved_python_root" = "$saved_python_location" ]] || \
        die "setup-python Python_ROOT_DIR does not match pythonLocation"
    [[ "$saved_python2_root" = "$saved_python_location" ]] || \
        die "setup-python Python2_ROOT_DIR does not match pythonLocation"
    [[ "$saved_python3_root" = "$saved_python_location" ]] || \
        die "setup-python Python3_ROOT_DIR does not match pythonLocation"
    [[ "$saved_action_version" = "$SETUP_PYTHON_VERSION" ]] || \
        die "setup-python action output version is not $SETUP_PYTHON_VERSION"
    [[ "$saved_action_python_path" = "$saved_python_location/bin/python" ]] || \
        die "setup-python action output path does not exactly match pythonLocation/bin/python"

    check_required_commands
    reject_build_overrides
    collect_repository_contract
    assert_loader_environment_absent

    [[ "$saved_python_location" != "$REPOSITORY_ROOT" && \
       "$saved_python_location" != "$REPOSITORY_ROOT/"* ]] || \
        die "setup-python installation is inside the repository"
    if [[ -n ${RUNNER_TEMP-} ]]; then
        runner_temp=$(physical_path "$RUNNER_TEMP")
        [[ "$saved_python_location" != "$runner_temp" && \
           "$saved_python_location" != "$runner_temp/"* ]] || \
            die "setup-python installation is inside RUNNER_TEMP"
    fi

    root=$(physical_path "$saved_python_location")
    [[ "$root" = "$saved_python_location" ]] || die "setup-python pythonLocation is not canonical and physical"
    loader=$(physical_path "$saved_loader_path")
    [[ "$loader" = "$saved_loader_path" && "$loader" = "$root/lib" ]] || \
        die "setup-python loader directory is not the exact physical pythonLocation/lib"
    bin_root="$root/bin"
    include_root="$root/include"
    pkgconfig_root="$root/lib/pkgconfig"

    if [[ ${GITHUB_ACTIONS-} = true ]]; then
        [[ -n ${RUNNER_TOOL_CACHE-} ]] || die "RUNNER_TOOL_CACHE is absent in GitHub Actions"
        safe_absolute_path "$RUNNER_TOOL_CACHE"
        runner_tool_cache=$(physical_path "$RUNNER_TOOL_CACHE")
        [[ "$runner_tool_cache" = "$RUNNER_TOOL_CACHE" ]] || \
            die "RUNNER_TOOL_CACHE is not canonical and physical"
        [[ "$runner_tool_cache" = /opt/hostedtoolcache ]] || \
            die "RUNNER_TOOL_CACHE is not the GitHub-hosted Linux tool-cache root"
        [[ "$root" = "$runner_tool_cache/Python/$SETUP_PYTHON_VERSION/$SETUP_PYTHON_ARCHITECTURE" ]] || \
            die "setup-python installation does not match the exact runner tool-cache identity"
        if [[ "$operation" = prepare ]]; then
            freeze_github_setup_python_tree "$root" "$runner_tool_cache"
        fi
        assert_github_frozen_setup_python_tree "$root" "$runner_tool_cache"
    fi

    installation_uid=$(stat -c '%u' -- "$root")
    effective_uid=$(id -u)
    if [[ ${GITHUB_ACTIONS-} = true ]]; then
        [[ "$effective_uid" != 0 ]] || die "GitHub setup-python adapter is running as root"
        [[ "$installation_uid" = 0 ]] || die "setup-python installation is not frozen under root ownership"
    fi

    assert_setup_python_path "$root" directory "installation root" "$installation_uid"
    assert_setup_python_path "$bin_root" directory "bin directory" "$installation_uid"
    assert_setup_python_path "$loader" directory "loader directory" "$installation_uid"
    assert_setup_python_path "$include_root" directory "include directory" "$installation_uid"
    assert_setup_python_path "$pkgconfig_root" directory "pkg-config directory" "$installation_uid"

    python_real=$(physical_path "$saved_action_python_path")
    [[ "$python_real" = "$root/bin/python3.12" ]] || \
        die "active Python executable is outside the exact setup-python installation"
    [[ $(physical_path "$saved_action_python_path") = "$python_real" ]] || \
        die "setup-python action output does not resolve to the active Python executable"
    assert_setup_python_path "$python_real" file "Python executable" "$installation_uid"

    readonly R11A_NATIVE_TRUSTED_PYTHON_CONFIG="$root/bin/python3-config"
    collect_toolchain_contract
    assert_loader_environment_absent
    [[ "$PYTHON_VERSION" = "$SETUP_PYTHON_VERSION" ]] || die "setup-python headers have the wrong version"
    [[ "$PYTHON_CONFIG_REALPATH" = "$root/bin/python3.12-config" ]] || \
        die "python3-config is outside the exact setup-python installation"
    [[ "$PYTHON_INCLUDE_REALPATH" = "$root/include/python3.12" ]] || \
        die "Python headers are outside the exact setup-python installation"
    assert_setup_python_path "$PYTHON_CONFIG_REALPATH" file "python3-config target" "$installation_uid"
    assert_setup_python_path "$PYTHON_INCLUDE_REALPATH" directory "versioned include directory" "$installation_uid"
    assert_setup_python_path "$PYTHON_INCLUDE_REALPATH/patchlevel.h" file "patchlevel header" "$installation_uid"
    config_prefix=$(physical_path "$("$PYTHON_CONFIG_REALPATH" --prefix)")
    [[ "$config_prefix" = "$root" ]] || die "python3-config prefix differs from pythonLocation"

    if ! scrubbed_probe=$(
        env -i \
            PATH="$root/bin:/usr/bin:/bin" \
            PYTHONSAFEPATH=1 \
            PYTHONNOUSERSITE=1 \
            LANG=C \
            LC_ALL=C \
            "$python_real" -I -S -c \
            'import os, sys, sysconfig
print(".".join(map(str, sys.version_info[:3])))
print(os.path.realpath(sys.executable))
print(os.path.realpath(sys.prefix))
print(os.path.realpath(sys.base_prefix))
print(os.path.realpath(sysconfig.get_path("include")))
print(os.path.realpath(str(sysconfig.get_config_var("LIBDIR"))))
print("present" if any(name in os.environ for name in ("LD_AUDIT", "LD_LIBRARY_PATH", "LD_PRELOAD", "LD_RUN_PATH")) else "absent")'
    ); then
        die "setup-python interpreter failed with the loader environment scrubbed"
    fi
    mapfile -t probe_lines <<<"$scrubbed_probe"
    [[ ${#probe_lines[@]} = 7 ]] || die "setup-python interpreter identity probe has an invalid shape"
    [[ ${probe_lines[0]} = "$SETUP_PYTHON_VERSION" ]] || die "setup-python interpreter version mismatch"
    [[ ${probe_lines[1]} = "$python_real" ]] || die "setup-python interpreter executable mismatch"
    [[ ${probe_lines[2]} = "$root" && ${probe_lines[3]} = "$root" ]] || \
        die "setup-python interpreter prefix mismatch"
    [[ ${probe_lines[4]} = "$PYTHON_INCLUDE_REALPATH" ]] || die "setup-python interpreter include mismatch"
    [[ ${probe_lines[6]} = absent ]] || die "setup-python interpreter retained a loader variable"
    if [[ ${GITHUB_ACTIONS-} = true ]]; then
        [[ ${probe_lines[5]} = "$loader" ]] || die "setup-python interpreter LIBDIR mismatch"
    fi
    assert_loader_environment_absent

    printf 'R11A setup-python loader attested and scrubbed: action=%s python=%s loader=%s owner_uid=%s\n' \
        "$SETUP_PYTHON_ACTION_SHA" "$root" "$loader" "$installation_uid"

    run_boundary_operation "$operation" "$env_file"
}

validate_elf() {
    local artifact=$1
    local description exports needed stack
    description=$(file -b -- "$artifact")
    [[ "$description" == ELF\ 64-bit\ LSB\ shared\ object,*x86-64* ]] || die "artifact is not an ELF64 x86-64 shared object: $description"
    readelf -h -- "$artifact" | grep -Eq 'Class:[[:space:]]+ELF64' || die "artifact ELF class is not ELF64"
    readelf -h -- "$artifact" | grep -Eq 'Type:[[:space:]]+DYN' || die "artifact ELF type is not DYN"
    readelf -h -- "$artifact" | grep -Eq 'Machine:[[:space:]]+Advanced Micro Devices X86-64' || die "artifact ELF machine is not x86-64"
    if readelf -n -- "$artifact" | grep -q 'Build ID'; then
        die "artifact unexpectedly contains a build ID"
    fi
    if readelf -d -- "$artifact" | grep -Eq 'RPATH|RUNPATH|TEXTREL'; then
        die "artifact contains a prohibited dynamic tag"
    fi
    readelf -W -l -- "$artifact" | grep -q 'GNU_RELRO' || die "artifact lacks GNU_RELRO"
    readelf -d -- "$artifact" | grep -Eq 'BIND_NOW|FLAGS.*NOW' || die "artifact lacks immediate binding"
    stack=$(readelf -W -l -- "$artifact" | awk '$1 == "GNU_STACK" {print}')
    [[ -n "$stack" && "$stack" != *RWE* ]] || die "artifact has an executable stack"
    exports=$(nm -D --defined-only -- "$artifact" | awk '{print $3}')
    [[ "$exports" = PyInit_sitecustomize ]] || die "artifact exports an unexpected symbol set: $exports"
    needed=$(readelf -d -- "$artifact" | sed -n 's/.*Shared library: \[\(.*\)\]/\1/p')
    [[ "$needed" = libc.so.6 ]] || die "artifact has an unexpected dependency set: $needed"
}

print_binary_diagnostics() {
    local label=$1
    local artifact=$2
    printf -- '--- %s: %s ---\n' "$label" "$artifact" >&2
    set +e
    if [[ -e "$artifact" ]]; then
        sha256sum -- "$artifact" >&2
        stat -- "$artifact" >&2
        file -- "$artifact" >&2
        readelf -h -- "$artifact" >&2
        readelf -S -- "$artifact" >&2
        readelf -n -- "$artifact" >&2
        readelf -d -- "$artifact" >&2
        readelf -s -- "$artifact" >&2
        readelf -r -- "$artifact" >&2
        objdump -h -- "$artifact" >&2
        objdump -x -- "$artifact" >&2
        objdump -T -- "$artifact" >&2
        nm -D -- "$artifact" >&2
        strings -- "$artifact" >&2
    else
        printf 'missing artifact\n' >&2
    fi
    set -e
}

require_binary_sha256() {
    local label=$1
    local artifact=$2
    local expected=$3
    local observed
    observed=$(sha256_file "$artifact")
    if [[ "$observed" = "$expected" ]]; then
        return
    fi
    printf 'R11A native boundary SHA-256 mismatch: %s\n' "$label" >&2
    printf 'expected_sha256=%s\nobserved_sha256=%s\n' "$expected" "$observed" >&2
    print_binary_diagnostics observed "$artifact"
    exit 1
}

compare_full_files() {
    local label=$1
    local expected=$2
    local observed=$3
    local comparison_rc
    set +e
    cmp -- "$expected" "$observed"
    comparison_rc=$?
    set -e
    if (( comparison_rc == 0 )); then
        return
    fi
    printf 'R11A native boundary full-file mismatch: %s (cmp rc=%s)\n' "$label" "$comparison_rc" >&2
    if [[ -f "$expected" && -f "$observed" ]]; then
        printf 'expected_sha256=%s\nobserved_sha256=%s\n' \
            "$(sha256_file "$expected")" "$(sha256_file "$observed")" >&2
    fi
    print_binary_diagnostics expected "$expected"
    print_binary_diagnostics observed "$observed"
    if [[ -f "$expected" && -f "$observed" ]]; then
        printf '%s\n' '--- first 64 differing bytes ---' >&2
        set +e
        cmp -l -- "$expected" "$observed" | sed -n '1,64p' >&2
        set -e
    fi
    exit 1
}

compile_once() {
    local build_root=$1
    local home_root=$2
    local temporary_root=$3
    (
        cd "$build_root"
        env -i \
            PATH=/usr/bin:/bin \
            HOME="$home_root" \
            TMPDIR="$temporary_root" \
            LANG=C \
            LC_ALL=C \
            TZ=UTC \
            SOURCE_DATE_EPOCH=0 \
            "${COMPILE_ARGUMENTS[@]}"
    )
}

build_pair() {
    local build_root=$1
    local home_root=$2
    local temporary_root=$3
    local first="$build_root/build-1.so"
    local output="$build_root/$ARTIFACT_NAME"

    [[ ! -e "$build_root" ]] || die "build root already exists: $build_root"
    mkdir -m 700 -- "$build_root"
    git cat-file blob "$SOURCE_OID" >"$build_root/source.c"
    chmod 400 -- "$build_root/source.c"
    [[ $(git hash-object --no-filters -- "$build_root/source.c") = "$SOURCE_OID" ]] || die "extracted source Git hash mismatch"
    [[ $(sha256_file "$build_root/source.c") = "$SOURCE_SHA256" ]] || die "extracted source SHA-256 mismatch"

    compile_once "$build_root" "$home_root" "$temporary_root"
    validate_elf "$output"
    cp -- "$output" "$first"
    rm -- "$output"
    compile_once "$build_root" "$home_root" "$temporary_root"
    validate_elf "$output"

    BUILD_1_SHA256=$(sha256_file "$first")
    BUILD_2_SHA256=$(sha256_file "$output")
    compare_full_files "repeat build" "$first" "$output"
}

remove_build_root() {
    local build_root=$1
    chmod 700 -- "$build_root"
    rm -f -- \
        "$build_root/source.c" \
        "$build_root/build-1.so" \
        "$build_root/$ARTIFACT_NAME"
    rmdir -- "$build_root"
}

remove_verify_transients() {
    local root=$1
    local path
    for path in "$root/verify" "$root/verify-home" "$root/verify-tmp"; do
        [[ "$path" = "$root/"* && "$path" != "$root" ]] || return 1
        if [[ -e "$path" ]]; then
            [[ -d "$path" && ! -L "$path" ]] || return 1
            [[ $(stat -c '%u' -- "$path") = "$(id -u)" ]] || return 1
            chmod 700 -- "$path" || return 1
            rm -rf --one-file-system -- "$path" || return 1
        fi
    done
}

readonly -a RECEIPT_KEYS=(
    schema model repository head tree repository_root temp_parent
    source_path source_mode source_oid_sha1 source_sha256
    builder_path builder_mode builder_oid_sha1 builder_sha256
    python_version python_config_realpath python_config_sha256
    python_include_realpath python_headers_inventory_sha256
    cc_realpath cc_sha256 cc_version_sha256 cc_target cc_specs_sha256
    cc1_realpath cc1_sha256 collect2_realpath collect2_sha256
    assembler_realpath assembler_sha256 assembler_version_sha256
    ld_realpath ld_sha256 ld_version_sha256 compile_argv_sha256
    build_1_sha256 build_2_sha256 artifact_sha256 artifact_size
    reference_realpath reference_sha256 reference_size reference_dev
    reference_ino reference_mode reference_uid reference_nlink
    boundary_root import_root artifact_realpath artifact_dev artifact_ino
    artifact_mode artifact_uid artifact_nlink root_mode root_uid
    import_root_mode import_root_uid elf_class elf_type elf_machine
    defined_export needed_library build_count
)

declare -A RECEIPT=()

populate_receipt() {
    local root=$1
    local import_root=$2
    local artifact=$3
    local reference=$4
    local temp_parent=$5
    RECEIPT=(
        [schema]="$SCHEMA"
        [model]="$MODEL"
        [repository]="$REPOSITORY"
        [head]="$HEAD_COMMIT"
        [tree]="$HEAD_TREE"
        [repository_root]="$REPOSITORY_ROOT"
        [temp_parent]="$temp_parent"
        [source_path]="$SOURCE_PATH"
        [source_mode]="$SOURCE_MODE"
        [source_oid_sha1]="$SOURCE_OID"
        [source_sha256]="$SOURCE_SHA256"
        [builder_path]="$BUILDER_PATH"
        [builder_mode]="$BUILDER_MODE"
        [builder_oid_sha1]="$BUILDER_OID"
        [builder_sha256]="$BUILDER_SHA256"
        [python_version]="$PYTHON_VERSION"
        [python_config_realpath]="$PYTHON_CONFIG_REALPATH"
        [python_config_sha256]="$PYTHON_CONFIG_SHA256"
        [python_include_realpath]="$PYTHON_INCLUDE_REALPATH"
        [python_headers_inventory_sha256]="$PYTHON_HEADERS_SHA256"
        [cc_realpath]="$CC_REALPATH"
        [cc_sha256]="$CC_SHA256"
        [cc_version_sha256]="$CC_VERSION_SHA256"
        [cc_target]="$CC_TARGET"
        [cc_specs_sha256]="$CC_SPECS_SHA256"
        [cc1_realpath]="$CC1_REALPATH"
        [cc1_sha256]="$CC1_SHA256"
        [collect2_realpath]="$COLLECT2_REALPATH"
        [collect2_sha256]="$COLLECT2_SHA256"
        [assembler_realpath]="$ASSEMBLER_REALPATH"
        [assembler_sha256]="$ASSEMBLER_SHA256"
        [assembler_version_sha256]="$ASSEMBLER_VERSION_SHA256"
        [ld_realpath]="$LD_REALPATH"
        [ld_sha256]="$LD_SHA256"
        [ld_version_sha256]="$LD_VERSION_SHA256"
        [compile_argv_sha256]="$COMPILE_ARGV_SHA256"
        [build_1_sha256]="$BUILD_1_SHA256"
        [build_2_sha256]="$BUILD_2_SHA256"
        [artifact_sha256]="$(sha256_file "$artifact")"
        [artifact_size]="$(stat -c '%s' -- "$artifact")"
        [reference_realpath]="$reference"
        [reference_sha256]="$(sha256_file "$reference")"
        [reference_size]="$(stat -c '%s' -- "$reference")"
        [reference_dev]="$(stat -c '%d' -- "$reference")"
        [reference_ino]="$(stat -c '%i' -- "$reference")"
        [reference_mode]="$(stat -c '%a' -- "$reference")"
        [reference_uid]="$(stat -c '%u' -- "$reference")"
        [reference_nlink]="$(stat -c '%h' -- "$reference")"
        [boundary_root]="$root"
        [import_root]="$import_root"
        [artifact_realpath]="$artifact"
        [artifact_dev]="$(stat -c '%d' -- "$artifact")"
        [artifact_ino]="$(stat -c '%i' -- "$artifact")"
        [artifact_mode]="$(stat -c '%a' -- "$artifact")"
        [artifact_uid]="$(stat -c '%u' -- "$artifact")"
        [artifact_nlink]="$(stat -c '%h' -- "$artifact")"
        [root_mode]="$(stat -c '%a' -- "$root")"
        [root_uid]="$(stat -c '%u' -- "$root")"
        [import_root_mode]="$(stat -c '%a' -- "$import_root")"
        [import_root_uid]="$(stat -c '%u' -- "$import_root")"
        [elf_class]="ELF64"
        [elf_type]="DYN"
        [elf_machine]="Advanced Micro Devices X86-64"
        [defined_export]="PyInit_sitecustomize"
        [needed_library]="libc.so.6"
        [build_count]="2"
    )
}

write_receipt() {
    local receipt_path=$1
    local key
    : >"$receipt_path"
    for key in "${RECEIPT_KEYS[@]}"; do
        [[ -v "RECEIPT[$key]" ]] || die "internal receipt value is missing: $key"
        [[ ${RECEIPT[$key]} != *$'\n'* && ${RECEIPT[$key]} != *$'\r'* ]] || die "receipt value contains a line break: $key"
        printf '%s=%s\n' "$key" "${RECEIPT[$key]}" >>"$receipt_path"
    done
    chmod 400 -- "$receipt_path"
}

readonly -a ENV_KEYS=(
    PYTHONSAFEPATH PYTHONNOUSERSITE PYTHONPATH R11A_NATIVE_BOUNDARY_ROOT
    R11A_NATIVE_IMPORT_ROOT R11A_NATIVE_BOUNDARY_BINARY
    R11A_NATIVE_BOUNDARY_RECEIPT R11A_NATIVE_BOUNDARY_RECEIPT_SHA256
    R11A_NATIVE_ARTIFACT_SHA256 R11A_NATIVE_ARTIFACT_DEV
    R11A_NATIVE_ARTIFACT_INO R11A_REPOSITORY_ROOT R11A_NATIVE_ENV_FILE
)

write_environment_file() {
    local env_file=$1
    local root=$2
    local import_root=$3
    local artifact=$4
    local receipt=$5
    local receipt_sha=$6
    local artifact_sha=$7
    local value
    local -a values=(
        1 1 "$import_root" "$root" "$import_root" "$artifact" "$receipt"
        "$receipt_sha" "$artifact_sha" "$(stat -c '%d' -- "$artifact")"
        "$(stat -c '%i' -- "$artifact")" "$REPOSITORY_ROOT" "$env_file"
    )
    : >"$env_file"
    local index
    for index in "${!ENV_KEYS[@]}"; do
        value=${values[$index]}
        [[ "$value" =~ ^[A-Za-z0-9._/-]+$ ]] || die "environment value is outside the safe grammar: ${ENV_KEYS[$index]}"
        printf 'export %s=%s\n' "${ENV_KEYS[$index]}" "$value" >>"$env_file"
    done
    chmod 600 -- "$env_file"
}

load_environment_file() {
    local env_file=$1
    local require_current=$2
    local line expected key value index
    local -a lines=()
    declare -gA ENV_RECORD=()

    env_file=$(physical_path "$env_file")
    assert_regular_owned_file "$env_file" 600
    mapfile -t lines <"$env_file"
    [[ ${#lines[@]} = ${#ENV_KEYS[@]} ]] || die "environment file has an unexpected line count"
    for index in "${!ENV_KEYS[@]}"; do
        line=${lines[$index]}
        expected=${ENV_KEYS[$index]}
        [[ "$line" == "export $expected="* ]] || die "environment file key order is invalid at $expected"
        key=${line%%=*}
        key=${key#export }
        value=${line#*=}
        [[ "$key" = "$expected" && "$value" =~ ^[A-Za-z0-9._/-]+$ ]] || die "environment file value is malformed: $expected"
        ENV_RECORD[$key]=$value
        if [[ "$require_current" = yes ]]; then
            [[ ${!key-} = "$value" ]] || die "current environment differs from boundary file: $key"
        fi
    done
    [[ ${ENV_RECORD[R11A_NATIVE_ENV_FILE]} = "$env_file" ]] || die "environment file does not bind its own path"
}

load_receipt() {
    local receipt_path=$1
    local line key value expected index final_byte
    local -a lines=()
    declare -gA LOADED_RECEIPT=()

    assert_regular_owned_file "$receipt_path" 400
    final_byte=$(tail -c 1 -- "$receipt_path" | od -An -t x1 | tr -d ' \n')
    [[ "$final_byte" = 0a ]] || die "receipt lacks a canonical final newline"
    mapfile -t lines <"$receipt_path"
    [[ ${#lines[@]} = ${#RECEIPT_KEYS[@]} ]] || die "receipt has an unexpected line count"
    for index in "${!RECEIPT_KEYS[@]}"; do
        line=${lines[$index]}
        expected=${RECEIPT_KEYS[$index]}
        [[ "$line" == "$expected="* ]] || die "receipt key order is invalid at $expected"
        key=${line%%=*}
        value=${line#*=}
        [[ "$key" = "$expected" && "$value" != *$'\r'* ]] || die "receipt value is malformed: $expected"
        LOADED_RECEIPT[$key]=$value
    done
}

compare_receipt_contract() {
    local key expected
    declare -A current=(
        [schema]="$SCHEMA" [model]="$MODEL" [repository]="$REPOSITORY"
        [head]="$HEAD_COMMIT" [tree]="$HEAD_TREE" [repository_root]="$REPOSITORY_ROOT"
        [source_path]="$SOURCE_PATH" [source_mode]="$SOURCE_MODE"
        [source_oid_sha1]="$SOURCE_OID" [source_sha256]="$SOURCE_SHA256"
        [builder_path]="$BUILDER_PATH" [builder_mode]="$BUILDER_MODE"
        [builder_oid_sha1]="$BUILDER_OID" [builder_sha256]="$BUILDER_SHA256"
        [python_version]="$PYTHON_VERSION" [python_config_realpath]="$PYTHON_CONFIG_REALPATH"
        [python_config_sha256]="$PYTHON_CONFIG_SHA256" [python_include_realpath]="$PYTHON_INCLUDE_REALPATH"
        [python_headers_inventory_sha256]="$PYTHON_HEADERS_SHA256"
        [cc_realpath]="$CC_REALPATH" [cc_sha256]="$CC_SHA256"
        [cc_version_sha256]="$CC_VERSION_SHA256" [cc_target]="$CC_TARGET"
        [cc_specs_sha256]="$CC_SPECS_SHA256" [cc1_realpath]="$CC1_REALPATH"
        [cc1_sha256]="$CC1_SHA256" [collect2_realpath]="$COLLECT2_REALPATH"
        [collect2_sha256]="$COLLECT2_SHA256" [assembler_realpath]="$ASSEMBLER_REALPATH"
        [assembler_sha256]="$ASSEMBLER_SHA256" [assembler_version_sha256]="$ASSEMBLER_VERSION_SHA256"
        [ld_realpath]="$LD_REALPATH" [ld_sha256]="$LD_SHA256"
        [ld_version_sha256]="$LD_VERSION_SHA256" [compile_argv_sha256]="$COMPILE_ARGV_SHA256"
    )
    for key in "${!current[@]}"; do
        expected=${current[$key]}
        [[ ${LOADED_RECEIPT[$key]-} = "$expected" ]] || die "receipt contract mismatch: $key"
    done
}

validate_root_layout() {
    local root=${ENV_RECORD[R11A_NATIVE_BOUNDARY_ROOT]}
    local import_root=${ENV_RECORD[R11A_NATIVE_IMPORT_ROOT]}
    local artifact=${ENV_RECORD[R11A_NATIVE_BOUNDARY_BINARY]}
    local receipt=${ENV_RECORD[R11A_NATIVE_BOUNDARY_RECEIPT]}
    local reference="$root/$REFERENCE_NAME"
    local -a root_entries=()
    local -a import_entries=()

    safe_absolute_path "$root"
    [[ $(basename -- "$root") =~ ^r11a-native-boundary\.[A-Za-z0-9]+$ ]] || die "boundary root basename is invalid"
    [[ "$import_root" = "$root/import" ]] || die "import root is outside the boundary root"
    [[ "$artifact" = "$import_root/$ARTIFACT_NAME" ]] || die "artifact path is outside the import root"
    [[ "$receipt" = "$root/receipt.txt" ]] || die "receipt path is outside the boundary root"
    assert_owned_directory "$root" 700
    assert_owned_directory "$import_root" 500
    assert_regular_owned_file "$artifact" 500
    assert_regular_owned_file "$receipt" 400
    assert_regular_owned_file "$reference" 400
    [[ $(physical_path "$root") = "$root" ]] || die "boundary root is not physical"
    [[ $(physical_path "$import_root") = "$import_root" ]] || die "import root is not physical"
    [[ $(physical_path "$artifact") = "$artifact" ]] || die "artifact is not physical"
    [[ $(physical_path "$receipt") = "$receipt" ]] || die "receipt is not physical"
    [[ $(physical_path "$reference") = "$reference" ]] || die "reference artifact is not physical"
    mapfile -d '' -t root_entries < <(find "$root" -mindepth 1 -maxdepth 1 -printf '%f\0' | LC_ALL=C sort -z)
    [[ ${#root_entries[@]} = 3 ]] || die "boundary root inventory is not exact"
    [[ ${root_entries[0]} = import && ${root_entries[1]} = receipt.txt && ${root_entries[2]} = "$REFERENCE_NAME" ]] || die "boundary root inventory is not exact"
    mapfile -d '' -t import_entries < <(find "$import_root" -mindepth 1 -maxdepth 1 -printf '%f\0' | LC_ALL=C sort -z)
    [[ ${#import_entries[@]} = 1 && ${import_entries[0]} = "$ARTIFACT_NAME" ]] || die "import root inventory is not exact"
}

prepare_boundary() {
    local env_file=$1
    local temp_parent root import_root artifact reference receipt build_root home_root temporary_root
    local receipt_sha artifact_sha prepare_cleanup_trap

    [[ "$env_file" = /* ]] || die "environment-file path must be absolute"
    safe_absolute_path "$env_file"
    [[ ! -e "$env_file" ]] || die "environment file already exists: $env_file"
    temp_parent=${RUNNER_TEMP:-/tmp}
    temp_parent=$(physical_path "$temp_parent")
    [[ -d "$temp_parent" ]] || die "temporary parent does not exist: $temp_parent"
    [[ "$temp_parent" != / && "$temp_parent" != "$REPOSITORY_ROOT" ]] || die "unsafe temporary parent"

    root=$(mktemp -d "$temp_parent/r11a-native-boundary.XXXXXXXX")
    root=$(physical_path "$root")
    chmod 700 -- "$root"
    import_root="$root/import"
    artifact="$import_root/$ARTIFACT_NAME"
    reference="$root/$REFERENCE_NAME"
    receipt="$root/receipt.txt"
    build_root="$root/prepare"
    home_root="$root/home"
    temporary_root="$root/tmp"
    mkdir -m 700 -- "$import_root" "$home_root" "$temporary_root"

    prepare_exit_handler() {
        local primary_rc=$?
        local cleanup_root=$1
        local cleanup_env_file=$2
        local cleanup_rc=0
        trap - EXIT
        if [[ -d "$cleanup_root" && ! -L "$cleanup_root" ]]; then
            chmod 700 -- "$cleanup_root" || cleanup_rc=$?
            if [[ -d "$cleanup_root/import" && ! -L "$cleanup_root/import" ]]; then
                chmod 700 -- "$cleanup_root/import" || cleanup_rc=$?
            fi
            rm -rf --one-file-system -- "$cleanup_root" || cleanup_rc=$?
        fi
        if [[ -f "$cleanup_env_file" && ! -L "$cleanup_env_file" ]]; then
            rm -f -- "$cleanup_env_file" || cleanup_rc=$?
        fi
        if (( primary_rc == 0 && cleanup_rc != 0 )); then
            primary_rc=$cleanup_rc
        fi
        exit "$primary_rc"
    }
    printf -v prepare_cleanup_trap \
        'prepare_exit_handler %q %q' "$root" "$env_file"
    trap "$prepare_cleanup_trap" EXIT

    build_pair "$build_root" "$home_root" "$temporary_root"
    install -m 500 -- "$build_root/$ARTIFACT_NAME" "$artifact"
    install -m 400 -- "$build_root/$ARTIFACT_NAME" "$reference"
    validate_elf "$artifact"
    remove_build_root "$build_root"
    rmdir -- "$home_root" "$temporary_root"
    chmod 500 -- "$import_root"

    collect_repository_contract
    collect_toolchain_contract
    populate_receipt "$root" "$import_root" "$artifact" "$reference" "$temp_parent"
    write_receipt "$receipt"
    receipt_sha=$(sha256_file "$receipt")
    artifact_sha=$(sha256_file "$artifact")
    write_environment_file "$env_file" "$root" "$import_root" "$artifact" "$receipt" "$receipt_sha" "$artifact_sha"

    trap - EXIT
    printf 'R11A native boundary prepared: head=%s tree=%s artifact_sha256=%s\n' \
        "$HEAD_COMMIT" "$HEAD_TREE" "$artifact_sha"
}

verify_boundary() {
    local env_file=$1
    local root import_root artifact reference receipt verify_root home_root temporary_root
    local artifact_sha reference_sha receipt_sha verify_cleanup_trap

    load_environment_file "$env_file" yes
    validate_root_layout
    root=${ENV_RECORD[R11A_NATIVE_BOUNDARY_ROOT]}
    import_root=${ENV_RECORD[R11A_NATIVE_IMPORT_ROOT]}
    artifact=${ENV_RECORD[R11A_NATIVE_BOUNDARY_BINARY]}
    reference="$root/$REFERENCE_NAME"
    receipt=${ENV_RECORD[R11A_NATIVE_BOUNDARY_RECEIPT]}
    load_receipt "$receipt"
    receipt_sha=$(sha256_file "$receipt")
    [[ "$receipt_sha" = "${ENV_RECORD[R11A_NATIVE_BOUNDARY_RECEIPT_SHA256]}" ]] || die "receipt SHA-256 mismatch"
    [[ ${LOADED_RECEIPT[boundary_root]} = "$root" ]] || die "receipt boundary-root mismatch"
    [[ ${LOADED_RECEIPT[import_root]} = "$import_root" ]] || die "receipt import-root mismatch"
    [[ ${LOADED_RECEIPT[artifact_realpath]} = "$artifact" ]] || die "receipt artifact-path mismatch"
    [[ ${LOADED_RECEIPT[reference_realpath]} = "$reference" ]] || die "receipt reference-path mismatch"
    [[ $(dirname -- "$root") = "${LOADED_RECEIPT[temp_parent]}" ]] || die "receipt temporary-parent mismatch"

    collect_repository_contract
    collect_toolchain_contract
    compare_receipt_contract

    compare_full_files "sealed reference versus promoted artifact" "$reference" "$artifact"
    require_binary_sha256 "promoted artifact versus receipt" "$artifact" "${LOADED_RECEIPT[artifact_sha256]}"
    require_binary_sha256 "promoted artifact versus environment" "$artifact" "${ENV_RECORD[R11A_NATIVE_ARTIFACT_SHA256]}"
    require_binary_sha256 "sealed reference versus receipt" "$reference" "${LOADED_RECEIPT[reference_sha256]}"
    artifact_sha=$(sha256_file "$artifact")
    reference_sha=$(sha256_file "$reference")
    [[ $(stat -c '%s' -- "$artifact") = "${LOADED_RECEIPT[artifact_size]}" ]] || die "live artifact size differs from receipt"
    [[ $(stat -c '%d' -- "$artifact") = "${LOADED_RECEIPT[artifact_dev]}" ]] || die "live artifact device differs from receipt"
    [[ $(stat -c '%i' -- "$artifact") = "${LOADED_RECEIPT[artifact_ino]}" ]] || die "live artifact inode differs from receipt"
    [[ $(stat -c '%a' -- "$artifact") = "${LOADED_RECEIPT[artifact_mode]}" ]] || die "live artifact mode differs from receipt"
    [[ $(stat -c '%u' -- "$artifact") = "${LOADED_RECEIPT[artifact_uid]}" ]] || die "live artifact owner differs from receipt"
    [[ $(stat -c '%h' -- "$artifact") = "${LOADED_RECEIPT[artifact_nlink]}" ]] || die "live artifact link count differs from receipt"
    [[ $(stat -c '%s' -- "$reference") = "${LOADED_RECEIPT[reference_size]}" ]] || die "reference artifact size differs from receipt"
    [[ $(stat -c '%d' -- "$reference") = "${LOADED_RECEIPT[reference_dev]}" ]] || die "reference artifact device differs from receipt"
    [[ $(stat -c '%i' -- "$reference") = "${LOADED_RECEIPT[reference_ino]}" ]] || die "reference artifact inode differs from receipt"
    [[ $(stat -c '%a' -- "$reference") = "${LOADED_RECEIPT[reference_mode]}" ]] || die "reference artifact mode differs from receipt"
    [[ $(stat -c '%u' -- "$reference") = "${LOADED_RECEIPT[reference_uid]}" ]] || die "reference artifact owner differs from receipt"
    [[ $(stat -c '%h' -- "$reference") = "${LOADED_RECEIPT[reference_nlink]}" ]] || die "reference artifact link count differs from receipt"
    validate_elf "$artifact"
    validate_elf "$reference"

    verify_root="$root/verify"
    home_root="$root/verify-home"
    temporary_root="$root/verify-tmp"
    verify_exit_handler() {
        local primary_rc=$?
        local cleanup_root=$1
        local cleanup_rc=0
        trap - EXIT
        remove_verify_transients "$cleanup_root" || cleanup_rc=$?
        if (( primary_rc == 0 && cleanup_rc != 0 )); then
            primary_rc=$cleanup_rc
        fi
        exit "$primary_rc"
    }
    printf -v verify_cleanup_trap 'verify_exit_handler %q' "$root"
    trap "$verify_cleanup_trap" EXIT
    mkdir -m 700 -- "$home_root" "$temporary_root"
    build_pair "$verify_root" "$home_root" "$temporary_root"
    compare_full_files "fresh rebuild versus promoted artifact" "$verify_root/$ARTIFACT_NAME" "$artifact"
    require_binary_sha256 "fresh build 1 versus receipt" "$verify_root/build-1.so" "${LOADED_RECEIPT[build_1_sha256]}"
    require_binary_sha256 "fresh build 2 versus receipt" "$verify_root/$ARTIFACT_NAME" "${LOADED_RECEIPT[build_2_sha256]}"
    remove_verify_transients "$root"
    trap - EXIT

    collect_repository_contract
    collect_toolchain_contract
    compare_receipt_contract
    require_binary_sha256 "promoted artifact final race check" "$artifact" "$artifact_sha"
    require_binary_sha256 "sealed reference final race check" "$reference" "$reference_sha"
    [[ $(sha256_file "$receipt") = "$receipt_sha" ]] || die "receipt changed during verification"
    validate_root_layout
    printf 'R11A native boundary verified: head=%s artifact_sha256=%s\n' "$HEAD_COMMIT" "$artifact_sha"
}

cleanup_boundary() {
    local env_file=$1
    local root receipt receipt_sha temp_parent

    load_environment_file "$env_file" no
    root=${ENV_RECORD[R11A_NATIVE_BOUNDARY_ROOT]}
    receipt=${ENV_RECORD[R11A_NATIVE_BOUNDARY_RECEIPT]}
    validate_root_layout
    load_receipt "$receipt"
    receipt_sha=$(sha256_file "$receipt")
    [[ "$receipt_sha" = "${ENV_RECORD[R11A_NATIVE_BOUNDARY_RECEIPT_SHA256]}" ]] || die "cleanup receipt SHA-256 mismatch"
    [[ ${LOADED_RECEIPT[schema]} = "$SCHEMA" && ${LOADED_RECEIPT[repository]} = "$REPOSITORY" ]] || die "cleanup receipt identity mismatch"
    [[ ${LOADED_RECEIPT[boundary_root]} = "$root" ]] || die "cleanup root mismatch"
    temp_parent=${LOADED_RECEIPT[temp_parent]}
    safe_absolute_path "$temp_parent"
    [[ $(dirname -- "$root") = "$temp_parent" ]] || die "cleanup root is outside its bound temporary parent"
    [[ "$root" != / && "$root" != "$temp_parent" && "$root" != "${ENV_RECORD[R11A_REPOSITORY_ROOT]}" ]] || die "refusing unsafe cleanup target"
    chmod 700 -- "$root" "${ENV_RECORD[R11A_NATIVE_IMPORT_ROOT]}"
    chmod 600 -- "${ENV_RECORD[R11A_NATIVE_BOUNDARY_BINARY]}" "$root/$REFERENCE_NAME" "$receipt"
    rm -rf --one-file-system -- "$root"
    rm -- "$env_file"
    printf 'R11A native boundary cleaned: %s\n' "$root"
}

run_boundary_operation() {
    local operation=$1
    local env_file=$2
    assert_loader_environment_absent
    case "$operation" in
        prepare)
            prepare_boundary "$env_file"
            ;;
        verify)
            verify_boundary "$env_file"
            ;;
        cleanup)
            cleanup_boundary "$env_file"
            ;;
        *)
            die "unsupported operation: $operation"
            ;;
    esac
}

main() {
    local operation=${1-}
    local env_file=${2-}
    if [[ "$operation" = setup-python ]]; then
        [[ $# = 3 ]] || die "usage: $BUILDER_PATH setup-python {prepare|verify|cleanup} ABSOLUTE_ENV_FILE"
        setup_python_adapter "$2" "$3"
        return
    fi
    [[ $# = 2 ]] || die "usage: $BUILDER_PATH {prepare|verify|cleanup} ABSOLUTE_ENV_FILE"
    check_required_commands
    reject_build_overrides
    collect_repository_contract
    collect_toolchain_contract
    run_boundary_operation "$operation" "$env_file"
}

main "$@"
