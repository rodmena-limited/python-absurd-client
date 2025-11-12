Installation
============

Prerequisites
-------------

Before installing the Python Absurd client, you'll need:

- Python 3.10 or higher
- PostgreSQL with the Absurd extension installed
- Psycopg3 library for PostgreSQL connectivity

Installation via pip
--------------------

The easiest way to install the Absurd client is using pip:

.. code-block:: bash

    pip install absurd

From Source
-----------

Alternatively, you can install directly from the source code:

.. code-block:: bash

    git clone https://github.com/rodmena-limited/python-absurd-client.git
    cd python-absurd-client
    pip install .

Development Installation
--------------------------

For development purposes, you can install in editable mode with development dependencies:

.. code-block:: bash

    pip install -e ".[dev]"

Requirements
------------

The Absurd client requires the following Python packages:

- ``psycopg>=3.0`` - PostgreSQL database adapter
- ``typing-extensions`` (for older Python versions)

Optionally, for development and testing:

- ``pytest`` - Testing framework
- ``sphinx`` - Documentation generation
- ``sphinx-rtd-theme`` - Read the Docs theme for documentation
- ``psycopg_pool`` - Connection pooling for production applications

PostgreSQL Setup
----------------

To use the Absurd client effectively, you'll need to set up the Absurd extension in your PostgreSQL database. See the `Absurd documentation <https://github.com/earendil-works/absurd>`_ for setup instructions.

The Absurd extension will:

1. Create the ``absurd`` schema in your PostgreSQL database
2. Set up necessary extensions like ``uuid-ossp``
3. Create the required stored procedures and functions
4. Create the queue management infrastructure
5. Set up the table structures for tasks, runs, checkpoints, events, and wait registrations

Connection Requirements
-----------------------

The client requires PostgreSQL connection parameters, which can be provided as:

- Connection string
- Environment variables
- Connection pool configuration

For production applications, it's recommended to use connection pooling for better performance and resource management:

.. code-block:: python

    from psycopg_pool import ConnectionPool
    from absurd_client import AbsurdClient

    # Create a connection pool with appropriate settings
    pool = ConnectionPool(
        "postgresql://user:password@localhost:5432/database",
        min_size=2,
        max_size=10,
        timeout=30  # Connection timeout in seconds
    )

    client = AbsurdClient(queue_name="my_queue")

Environment Variables
---------------------

The client supports the following environment variables for configuration:

- ``ABSURD_DEFAULT_QUEUE``: Default queue name when not specified (default: ``absurd_default``)
- ``ABSURD_WORKER_ID``: Default worker ID (default: ``absurd_worker_1``)

Example:

.. code-block:: bash

    export ABSURD_DEFAULT_QUEUE="production_tasks"
    export ABSURD_WORKER_ID="worker-001"

Virtual Environment Setup
-------------------------

For best practices, set up a virtual environment before installing:

.. code-block:: bash

    # Create a virtual environment
    python -m venv absurd_env
    
    # Activate the virtual environment
    source absurd_env/bin/activate  # On Linux/Mac
    # or
    absurd_env\Scripts\activate  # On Windows
    
    # Install the package
    pip install absurd
    
    # For development
    pip install -e ".[dev]"

Upgrade Existing Installation
-----------------------------

To upgrade an existing installation:

.. code-block:: bash

    pip install --upgrade absurd

Verification
------------

After installation, verify that the package is correctly installed:

.. code-block:: bash

    python -c "from absurd_client import AbsurdClient; print('Installation successful!')"

This should run without error, confirming that the Absurd client is properly installed and accessible.