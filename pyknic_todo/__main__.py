"""Entry point for running pyknic-todo via python -m pyknic_todo."""

# TODO: refactor this

import sys
from pyknic_todo.cli import main

if __name__ == "__main__":
    sys.exit(main())
