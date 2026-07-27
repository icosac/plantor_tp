#!/usr/bin/env python3

"""Compatibility entrypoint for the TP profiler."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_profile_package() -> ModuleType:
    """
    Load TP/profile/ under an internal package name.

    Returns
    -------
    ModuleType
        Loaded implementation package.
    """
    package_name = "_tp_profile_impl"
    if package_name in sys.modules:
        return sys.modules[package_name]

    package_dir = Path(__file__).resolve().with_suffix("")
    init_path = package_dir / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        package_name,
        init_path,
        submodule_search_locations=[str(package_dir)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load profile package from {init_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = module
    spec.loader.exec_module(module)
    return module


_impl = _load_profile_package()
main = _impl.main
parse_args = _impl.parse_args


if __name__ == "__main__":
    raise SystemExit(main())
