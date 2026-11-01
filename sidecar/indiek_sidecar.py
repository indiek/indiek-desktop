"""Entry point of the frozen `indiek-sidecar` binary (DESKTOP:PACKAGING-TAURI P3).

    indiek-sidecar serve [ARGS]   the local API, as `python -m indiek_api [ARGS]`
    indiek-sidecar ik [ARGS]      the command line, as `ik [ARGS]`

One binary for both, so the app and the bundled `ik` are the same program for the OS
keychain's access list.
"""

from __future__ import annotations

import multiprocessing
import sys
from collections.abc import Sequence

USAGE = "usage: indiek-sidecar {serve,ik} [ARGS...]"


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] not in ("serve", "ik"):
        print(USAGE, file=sys.stderr)
        return 2
    command, rest = args[0], args[1:]
    if command == "serve":
        from indiek_api.app import main as serve

        serve(rest)
        return 0
    from indiek.cli import main as ik

    sys.argv = ["ik", *rest]
    ik()
    return 0


if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
