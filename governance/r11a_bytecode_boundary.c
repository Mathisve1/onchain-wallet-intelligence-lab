#define _GNU_SOURCE
#define _XOPEN_SOURCE 700
#define Py_LIMITED_API 0x03080000
#include <Python.h>

#include <dlfcn.h>
#include <errno.h>
#include <ftw.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

/*
 * Source-built pre-import bytecode boundary for the pinned Linux/CPython job.
 *
 * governance/r11a_native_boundary.sh authenticates this exact HEAD blob,
 * builds it twice in a private directory outside the repository, requires
 * byte-for-byte equality, and verifies the promoted artifact immediately
 * before every supported Python command.  No native binary is tracked or
 * trusted.  PYTHONSAFEPATH and an artifact-only PYTHONPATH cause CPython to
 * import this module as sitecustomize before exposing the repository.
 *
 * This initializer creates a private external bytecode root, activates it in
 * both the interpreter and environment, and only then inserts the exact
 * physical working repository into sys.path.  Child interpreters inherit
 * the artifact-only PYTHONPATH and establish their own boundary at startup.
 */

static char active_cache_root[sizeof("/tmp/r11a-pycache-XXXXXX")];

static int remove_cache_entry(
    const char *path,
    const struct stat *entry,
    int type,
    struct FTW *state
) {
    (void)entry;
    (void)type;
    (void)state;
    return remove(path);
}

static void cleanup_cache_root(void) {
    if (active_cache_root[0] == '\0') {
        return;
    }
    (void)nftw(active_cache_root, remove_cache_entry, 32, FTW_DEPTH | FTW_PHYS);
    active_cache_root[0] = '\0';
}

static void write_error_fragment(const char *fragment, size_t length) {
    ssize_t written = write(STDERR_FILENO, fragment, length);
    (void)written;
}

static void fail_closed(const char *reason) {
    static const char prefix[] = "R11A native boundary failed closed: ";
    write_error_fragment(prefix, sizeof(prefix) - 1);
    write_error_fragment(reason, strlen(reason));
    write_error_fragment("\n", 1);
    cleanup_cache_root();
    _exit(78);
}

static unsigned long long parse_identity(const char *name) {
    const char *value = getenv(name);
    char *end = NULL;
    unsigned long long parsed;

    if (value == NULL || value[0] == '\0') {
        fail_closed("loaded-artifact identity is absent");
    }
    errno = 0;
    parsed = strtoull(value, &end, 10);
    if (errno != 0 || end == value || *end != '\0') {
        fail_closed("loaded-artifact identity is malformed");
    }
    return parsed;
}

static void verify_loaded_artifact(void) {
    const char *expected_path = getenv("R11A_NATIVE_BOUNDARY_BINARY");
    Dl_info loaded;
    char expected_real[PATH_MAX];
    char loaded_real[PATH_MAX];
    struct stat expected_stat;
    struct stat loaded_stat;

    if (expected_path == NULL || expected_path[0] != '/') {
        fail_closed("expected artifact path is absent or relative");
    }
    (void)memset(&loaded, 0, sizeof(loaded));
    if (dladdr((const void *)&verify_loaded_artifact, &loaded) == 0 || loaded.dli_fname == NULL) {
        fail_closed("cannot resolve loaded-artifact origin");
    }
    if (realpath(expected_path, expected_real) == NULL || strcmp(expected_path, expected_real) != 0) {
        fail_closed("expected artifact path is not physical");
    }
    if (realpath(loaded.dli_fname, loaded_real) == NULL || strcmp(expected_real, loaded_real) != 0) {
        fail_closed("loaded artifact is not the authenticated path");
    }
    if (lstat(expected_path, &expected_stat) != 0 || lstat(loaded_real, &loaded_stat) != 0) {
        fail_closed("cannot stat loaded artifact");
    }
    if (!S_ISREG(expected_stat.st_mode) || !S_ISREG(loaded_stat.st_mode) ||
        (expected_stat.st_mode & 07777) != 0500 || expected_stat.st_uid != geteuid() ||
        expected_stat.st_nlink != 1 || expected_stat.st_dev != loaded_stat.st_dev ||
        expected_stat.st_ino != loaded_stat.st_ino) {
        fail_closed("loaded-artifact filesystem identity is unsafe");
    }
    if ((unsigned long long)expected_stat.st_dev != parse_identity("R11A_NATIVE_ARTIFACT_DEV") ||
        (unsigned long long)expected_stat.st_ino != parse_identity("R11A_NATIVE_ARTIFACT_INO")) {
        fail_closed("loaded artifact differs from receipted identity");
    }
}

static const char *BOOTSTRAP =
    "import os as _r11a_os\n"
    "import stat as _r11a_stat\n"
    "import sys as _r11a_sys\n"
    "_r11a_os.environ['PYTHONPYCACHEPREFIX'] = _r11a_sys.pycache_prefix\n"
    "_r11a_os.environ['R11A_PYCACHE_BOUNDARY_ACTIVE'] = _r11a_sys.pycache_prefix\n"
    "_r11a_native = _r11a_os.environ.get('R11A_NATIVE_IMPORT_ROOT')\n"
    "_r11a_repository = _r11a_os.environ.get('R11A_REPOSITORY_ROOT')\n"
    "_r11a_working = _r11a_os.path.realpath(_r11a_os.getcwd())\n"
    "if not _r11a_sys.flags.safe_path: raise RuntimeError('PYTHONSAFEPATH is not active')\n"
    "if not _r11a_sys.flags.no_user_site: raise RuntimeError('PYTHONNOUSERSITE is not active')\n"
    "if not _r11a_native or _r11a_os.environ.get('PYTHONPATH') != _r11a_native: raise RuntimeError('artifact-only PYTHONPATH is not active')\n"
    "if not _r11a_repository or not _r11a_os.path.isabs(_r11a_repository): raise RuntimeError('repository root is not absolute')\n"
    "if _r11a_os.path.realpath(_r11a_repository) != _r11a_repository: raise RuntimeError('repository root is not physical')\n"
    "_r11a_native_stat = _r11a_os.lstat(_r11a_native)\n"
    "_r11a_repository_stat = _r11a_os.lstat(_r11a_repository)\n"
    "if not _r11a_stat.S_ISDIR(_r11a_native_stat.st_mode) or _r11a_stat.S_IMODE(_r11a_native_stat.st_mode) != 0o500 or _r11a_native_stat.st_uid != _r11a_os.geteuid(): raise RuntimeError('unsafe native import root')\n"
    "if not _r11a_stat.S_ISDIR(_r11a_repository_stat.st_mode): raise RuntimeError('repository root is not a directory')\n"
    "if any(_r11a_os.path.realpath(_r11a_item or _r11a_os.curdir) == _r11a_working for _r11a_item in _r11a_sys.path): raise RuntimeError('working repository was exposed before boundary activation')\n"
    "_r11a_sys.path.insert(0, _r11a_working)\n"
    "del _r11a_native, _r11a_repository, _r11a_working, _r11a_native_stat, _r11a_repository_stat\n"
    "del _r11a_os, _r11a_stat, _r11a_sys\n";

static struct PyModuleDef module_definition = {
    PyModuleDef_HEAD_INIT,
    "sitecustomize",
    "R11A authenticated source-built pre-import bytecode boundary.",
    -1,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
};

PyMODINIT_FUNC PyInit_sitecustomize(void) {
    char cache_template[] = "/tmp/r11a-pycache-XXXXXX";
    char *cache_root;
    PyObject *module;
    PyObject *prefix;
    PyObject *builtins;
    PyObject *exec_function;
    PyObject *bootstrap_source;
    PyObject *executed;

    verify_loaded_artifact();
    cache_root = mkdtemp(cache_template);
    if (cache_root == NULL) {
        fail_closed("cannot create external bytecode root");
    }
    if (strlen(cache_root) >= sizeof(active_cache_root)) {
        fail_closed("external bytecode root is unexpectedly long");
    }
    (void)strcpy(active_cache_root, cache_root);
    if (chmod(active_cache_root, 0700) != 0) {
        fail_closed("cannot privatize external bytecode root");
    }
    if (atexit(cleanup_cache_root) != 0) {
        fail_closed("cannot register bytecode-root cleanup");
    }
    if (setenv("PYTHONPYCACHEPREFIX", active_cache_root, 1) != 0 ||
        setenv("R11A_PYCACHE_BOUNDARY_ACTIVE", active_cache_root, 1) != 0) {
        fail_closed("cannot export external bytecode root");
    }

    prefix = PyUnicode_FromString(active_cache_root);
    if (prefix == NULL || PySys_SetObject("pycache_prefix", prefix) != 0) {
        Py_XDECREF(prefix);
        fail_closed("cannot activate interpreter bytecode root");
    }
    Py_DECREF(prefix);

    module = PyModule_Create(&module_definition);
    if (module == NULL) {
        fail_closed("cannot create boundary module");
    }
    builtins = PyImport_ImportModule("builtins");
    if (builtins == NULL) {
        Py_DECREF(module);
        fail_closed("cannot load bootstrap builtins");
    }
    exec_function = PyObject_GetAttrString(builtins, "exec");
    Py_DECREF(builtins);
    if (exec_function == NULL) {
        Py_DECREF(module);
        fail_closed("cannot load bootstrap executor");
    }
    bootstrap_source = PyUnicode_FromString(BOOTSTRAP);
    if (bootstrap_source == NULL) {
        Py_DECREF(exec_function);
        Py_DECREF(module);
        fail_closed("cannot materialize bootstrap source");
    }
    executed = PyObject_CallFunctionObjArgs(
        exec_function,
        bootstrap_source,
        PyModule_GetDict(module),
        PyModule_GetDict(module),
        NULL
    );
    Py_DECREF(bootstrap_source);
    Py_DECREF(exec_function);
    if (executed == NULL) {
        Py_DECREF(module);
        fail_closed("bootstrap validation failed");
    }
    Py_DECREF(executed);
    return module;
}
