"""KM-1 packaging boundary for legacy product-module dependencies."""

from __future__ import annotations

import gzip
import os
from pathlib import Path
import tarfile

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist


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


class KM1Sdist(sdist):
    """Create byte-reproducible gzip source archives when an epoch is set."""

    def make_archive(
        self,
        base_name: str,
        format: str,
        root_dir: str | None = None,
        base_dir: str | None = None,
        owner: str | None = None,
        group: str | None = None,
    ) -> str:
        epoch_value = os.getenv("SOURCE_DATE_EPOCH", "").strip()
        if format != "gztar" or not epoch_value:
            return super().make_archive(
                base_name,
                format,
                root_dir=root_dir,
                base_dir=base_dir,
                owner=owner,
                group=group,
            )

        epoch = int(epoch_value)
        archive_path = Path(f"{base_name}.tar.gz")
        archive_path.parent.mkdir(parents=True, exist_ok=True)

        def normalize(info: tarfile.TarInfo) -> tarfile.TarInfo:
            info.mtime = epoch
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mode = 0o755 if info.isdir() else 0o644
            info.pax_headers = {}
            return info

        source_root = Path(root_dir or ".") / str(base_dir)
        with archive_path.open("wb") as raw_archive:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                fileobj=raw_archive,
                mtime=epoch,
            ) as compressed:
                with tarfile.open(
                    fileobj=compressed,
                    mode="w",
                    format=tarfile.PAX_FORMAT,
                ) as archive:
                    archive.add(
                        source_root,
                        arcname=str(base_dir),
                        recursive=True,
                        filter=normalize,
                    )
        return str(archive_path)


setup(cmdclass={"build_py": KM1BuildPy, "sdist": KM1Sdist})
