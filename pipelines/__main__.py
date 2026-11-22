"""CLI de la cocina.

python -m pipelines build [--only macro_series ...]
python -m pipelines publish --target local --dir data/vitrina
python -m pipelines publish --target r2
python -m pipelines run --target local --dir data/vitrina   # build + publish
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from .build import build
from .common import ROOT_DIR
from .publish import LocalTarget, R2Target, Target, publish


def _load_dotenv(path: Path = ROOT_DIR / ".env") -> None:
    """Carga KEY=valor desde `.env` (no versionado) sin pisar variables ya definidas.

    Así las credenciales de R2 se guardan en un archivo local en vez de
    escribirlas en la terminal. En GitHub Actions vienen de Secrets.
    """
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _target(args: argparse.Namespace) -> Target:
    if args.target == "r2":
        return R2Target()
    if not args.dir:
        raise SystemExit("--target local necesita --dir")
    return LocalTarget(Path(args.dir))


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    _load_dotenv()
    parser = argparse.ArgumentParser(prog="python -m pipelines")
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="extrae, valida y escribe Parquet")
    p_build.add_argument("--only", nargs="+", help="solo estos datasets")

    for name in ("publish", "run"):
        p = sub.add_parser(
            name, help="publica en la vitrina" if name == "publish" else "build + publish"
        )
        p.add_argument("--target", choices=["local", "r2"], required=True)
        p.add_argument("--dir", help="carpeta de la vitrina (con --target local)")
        p.add_argument("--allow-fallback", action="store_true", help="solo para pruebas")
        if name == "run":
            p.add_argument("--only", nargs="+", help="solo estos datasets")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if args.command in ("build", "run"):
        catalog = build(only=args.only)
        if args.command == "build":
            return 1 if catalog["failed"] else 0
    publish(_target(args), allow_fallback=args.allow_fallback)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
