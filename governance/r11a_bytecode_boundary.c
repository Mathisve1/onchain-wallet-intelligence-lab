#define Py_LIMITED_API 0x03080000
#include <Python.h>

#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

/*
 * Cacheless pre-import boundary for the pinned Linux/CPython validation job.
 *
 * ``python -m unittest`` imports the standard-library difflib module before
 * importing any requested repository test.  The tracked extension built from
 * this source therefore shadows only that first difflib import, creates a
 * private external bytecode root, and then executes the pinned interpreter's
 * own stdlib difflib.py in this module namespace.  No repository source module
 * is loaded before the prefix is active, and no repository cache material is
 * removed or ignored.
 *
 * Reproducible local build for CPython 3.12 on the pinned Ubuntu runner:
 *
 *   cc -std=c11 -O2 -fPIC -fno-ident -DPy_LIMITED_API=0x03080000 \
 *      $(python3-config --includes) -shared -Wl,--build-id=none \
 *      -o difflib.abi3.so governance/r11a_bytecode_boundary.c
 */

static const char *BOOTSTRAP =
    "import atexit as _r11a_atexit\n"
    "import os as _r11a_os\n"
    "import pathlib as _r11a_pathlib\n"
    "import shutil as _r11a_shutil\n"
    "import sys as _r11a_sys\n"
    "import sysconfig as _r11a_sysconfig\n"
    "_r11a_root = _r11a_sys.pycache_prefix\n"
    "_r11a_os.environ['PYTHONPYCACHEPREFIX'] = _r11a_root\n"
    "_r11a_os.environ['R11A_PYCACHE_BOUNDARY_ACTIVE'] = _r11a_root\n"
    "_r11a_atexit.register(_r11a_shutil.rmtree, _r11a_root, ignore_errors=True)\n"
    "_r11a_hook = _r11a_pathlib.Path(_r11a_root) / 'sitecustomize.py'\n"
    "_r11a_hook.write_text(\"import os as _o, sys as _s\\n\"\n"
    "    \"_r = _o.path.dirname(_o.path.abspath(__file__))\\n\"\n"
    "    \"_d = _o.lstat(_r)\\n\"\n"
    "    \"_f = _o.lstat(__file__)\\n\"\n"
    "    \"if (_d.st_mode & 0o170000) != 0o040000 or (_d.st_mode & 0o777) != 0o700 or _d.st_uid != _o.geteuid(): raise RuntimeError('unsafe R11A bytecode root')\\n\"\n"
    "    \"if (_f.st_mode & 0o170000) != 0o100000 or _f.st_nlink != 1 or _f.st_uid != _o.geteuid(): raise RuntimeError('unsafe R11A bytecode hook')\\n\"\n"
    "    \"_s.pycache_prefix = _r\\n\"\n"
    "    \"_o.environ['PYTHONPYCACHEPREFIX'] = _r\\n\"\n"
    "    \"_o.environ['R11A_PYCACHE_BOUNDARY_ACTIVE'] = _r\\n\",\n"
    "    encoding='ascii')\n"
    "_r11a_hook.chmod(0o600)\n"
    "_r11a_prior_pythonpath = _r11a_os.environ.get('PYTHONPATH')\n"
    "_r11a_os.environ['PYTHONPATH'] = (_r11a_root if not _r11a_prior_pythonpath else _r11a_root + _r11a_os.pathsep + _r11a_prior_pythonpath)\n"
    "_r11a_source = _r11a_pathlib.Path(_r11a_sysconfig.get_path('stdlib')) / 'difflib.py'\n"
    "_r11a_raw = _r11a_source.read_bytes()\n"
    "exec(compile(_r11a_raw, str(_r11a_source), 'exec', dont_inherit=True), globals(), globals())\n"
    "del _r11a_atexit, _r11a_os, _r11a_pathlib, _r11a_shutil, _r11a_sys, _r11a_sysconfig\n"
    "del _r11a_root, _r11a_hook, _r11a_prior_pythonpath, _r11a_source, _r11a_raw\n";

static struct PyModuleDef module_definition = {
    PyModuleDef_HEAD_INIT,
    "difflib",
    "R11A external-bytecode bootstrap plus the trusted stdlib difflib module.",
    -1,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
};

PyMODINIT_FUNC PyInit_difflib(void) {
    char cache_template[] = "/tmp/r11a-pycache-XXXXXX";
    char *cache_root;
    PyObject *module;
    PyObject *prefix;
    PyObject *builtins;
    PyObject *exec_function;
    PyObject *bootstrap_source;
    PyObject *executed;

    cache_root = mkdtemp(cache_template);
    if (cache_root == NULL) {
        PyErr_Format(PyExc_RuntimeError, "cannot create external bytecode root: %s", strerror(errno));
        return NULL;
    }
    if (chmod(cache_root, 0700) != 0) {
        PyErr_Format(PyExc_RuntimeError, "cannot privatize external bytecode root: %s", strerror(errno));
        return NULL;
    }
    if (setenv("PYTHONPYCACHEPREFIX", cache_root, 1) != 0 ||
        setenv("R11A_PYCACHE_BOUNDARY_ACTIVE", cache_root, 1) != 0) {
        PyErr_Format(PyExc_RuntimeError, "cannot export external bytecode root: %s", strerror(errno));
        return NULL;
    }

    prefix = PyUnicode_FromString(cache_root);
    if (prefix == NULL) {
        return NULL;
    }
    if (PySys_SetObject("pycache_prefix", prefix) != 0) {
        Py_DECREF(prefix);
        return NULL;
    }
    Py_DECREF(prefix);

    module = PyModule_Create(&module_definition);
    if (module == NULL) {
        return NULL;
    }
    builtins = PyImport_ImportModule("builtins");
    if (builtins == NULL) {
        Py_DECREF(module);
        return NULL;
    }
    exec_function = PyObject_GetAttrString(builtins, "exec");
    Py_DECREF(builtins);
    if (exec_function == NULL) {
        Py_DECREF(module);
        return NULL;
    }
    bootstrap_source = PyUnicode_FromString(BOOTSTRAP);
    if (bootstrap_source == NULL) {
        Py_DECREF(exec_function);
        Py_DECREF(module);
        return NULL;
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
        return NULL;
    }
    Py_DECREF(executed);
    return module;
}
