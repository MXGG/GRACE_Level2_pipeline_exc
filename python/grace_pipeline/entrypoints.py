"""Compatibility module for the canonical command-line entrypoint.

The canonical CLI is defined in :mod:`grace_pipeline.cli`. This module is kept
because packaged executables and older editable installs may still reference
``grace_pipeline.entrypoints:main``.
"""

from grace_pipeline.cli import main


if __name__ == "__main__":
    main()
