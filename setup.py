"""KM-1 packaging boundary for legacy product-module dependencies."""

from __future__ import annotations

from setuptools import setup
from setuptools.command.build_py import build_py


_KM1_PRODUCT_MODULES = {
    "api_key_lifecycle_v070",
    "controlled_alpha_api_v071",
    "hosted_backend_foundation_v069",
    "self_serve_accounts_v092",
    "self_serve_api_keys_v092",
    "self_serve_dashboard_v092",
    "self_serve_plans_v092",
    "self_serve_repository_postgres_v0941",
    "self_serve_repository_v093",
}


class KM1BuildPy(build_py):
    """Exclude unrelated hosted-product modules from KM-1 artifacts."""

    def find_package_modules(self, package: str, package_dir: str):
        modules = super().find_package_modules(package, package_dir)
        if package == "prmr.integrations":
            return []
        if package == "prmr.product":
            return [item for item in modules if item[1] in _KM1_PRODUCT_MODULES]
        return modules


setup(cmdclass={"build_py": KM1BuildPy})
