# Documentation for python-absurd-client

This directory contains the Sphinx-based documentation for the python-absurd-client library.

## Building the Documentation

To build the documentation locally, run:

```bash
pip install sphinx sphinx-rtd-theme
sphinx-build -b html docs docs/_build
```

Or using the Python module:

```bash
python -m sphinx -b html docs docs/_build
```

The HTML documentation will be generated in the `docs/_build` directory.