"""
Beyond the corpus: shapes a hand-rolled resolver (A+) has to keep learning. Throwaway.

Run from the repository root:

    uv run --with griffe --with astroid python .planning/research/d9-prototypes/reexport_check.py

A+ and G tie on the corpus, so this checks three ordinary project layouts the corpus does
not contain, all still without importing anything:

1. the base class re-exported through a package ``__init__`` (``from app import Commerce``);
2. a relative import (``from .base import Commerce``);
3. the ``view=`` constant reached through a module attribute (``view=names.SALES_VIEW``).
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

BASE = (
    "from semolina import Dimension, SemanticView\n\n\n"
    "class Commerce(SemanticView, abstract=True):\n"
    "    region = Dimension[str]()\n"
)
CASES = {
    "re-export via __init__": {
        "app/__init__.py": "from app.base import Commerce\n",
        "app/base.py": BASE,
        "app/models.py": "from app import Commerce\n\n\n"
        'class Sales(Commerce, view="type_fidelity_view"):\n    pass\n',
    },
    "relative import": {
        "app/__init__.py": "",
        "app/base.py": BASE,
        "app/models.py": "from .base import Commerce\n\n\n"
        'class Sales(Commerce, view="type_fidelity_view"):\n    pass\n',
    },
    "view= via module attribute": {
        "app/__init__.py": "",
        "app/names.py": 'SALES_VIEW = "type_fidelity_view"\n',
        "app/models.py": "from semolina import Dimension, SemanticView\n\nfrom app import names\n\n\n"
        "class Sales(SemanticView, view=names.SALES_VIEW):\n    region = Dimension[str]()\n",
    },
}


def main() -> None:
    import reader_a
    import reader_astroid
    import reader_griffe

    readers = {
        "A+": reader_a.make_reader(follow_imports=True, normalise=True),
        "G griffe": reader_griffe.read_committed_model,
        "G astroid": reader_astroid.read_committed_model,
    }
    for case, files in CASES.items():
        for label, read in readers.items():
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                for rel, text in files.items():
                    (root / rel).parent.mkdir(parents=True, exist_ok=True)
                    (root / rel).write_text(text, encoding="utf-8")
                old = Path.cwd()
                os.chdir(root)
                try:
                    models = read(root / "app/models.py")
                    got = [(m.view_name, sorted(m.fields)) for m in models]
                except Exception as e:  # noqa: BLE001
                    got = f"error: {type(e).__name__}: {e}"
                finally:
                    os.chdir(old)
            ok = got == [("type_fidelity_view", ["region"])]
            print(f"{case:28} {label:10} {'ok' if ok else 'MISSED'}  {got}")


if __name__ == "__main__":
    main()
