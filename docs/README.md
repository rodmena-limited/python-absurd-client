# Documentation for Python Absurd Client

This directory contains the source files for the Sphinx-based documentation of the Python Absurd Client.

## Structure

- `index.rst` - Main documentation index
- `installation.rst` - Installation guide
- `quickstart.rst` - Quick start guide
- `api.rst` - API reference documentation
- `workflow_tracking.rst` - Workflow tracking features
- `error_handling.rst` - Error handling documentation
- `examples.rst` - Usage examples
- `conf.py` - Sphinx configuration file

## Building Documentation

To build the documentation, run:

```bash
pip install sphinx sphinx-rtd-theme
cd docs
python3 -m sphinx . _build
```

The HTML documentation will be generated in the `_build` directory.

## Viewing Documentation

After building, you can view the documentation by opening `_build/index.html` in your web browser:

```bash
xdg-open _build/index.html  # On Linux
open _build/index.html      # On macOS
```

## Documentation Coverage

The documentation includes:

- API reference for all classes and methods
- Installation and setup instructions
- Quick start examples
- Detailed usage examples for common scenarios
- Error handling patterns
- Workflow tracking features
- Best practices for production use