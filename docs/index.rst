Python Absurd Client Documentation
===================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   installation
   quickstart
   api
   workflow_tracking
   error_handling
   examples

About Absurd
============

Absurd is a SQL-based durable execution workflow system that uses PostgreSQL as the backend. This Python client provides a convenient interface to interact with Absurd's PostgreSQL-based task queue and workflow engine.

Key Features
------------

- Task queuing and processing
- Durable task execution that survives crashes
- Event-driven workflow coordination
- Checkpoint-based state management
- Retry strategies and failure handling
- Workflow run tracking
- Support for complex workflow patterns
- Multi-tenant support (Phase 13)
- Connection pooling for production environments
- Comprehensive error handling

Getting Started
---------------

If you're new to the Absurd client, start with the :doc:`installation` guide to set up your environment, then follow the :doc:`quickstart` to learn the basics.

For advanced use cases and complex workflows, check out the :doc:`examples` section which provides comprehensive code samples for various scenarios.

Core Concepts
-------------

- **Queues**: Isolated task processing environments that separate different types of work
- **Tasks**: Logical units of work that need to be executed
- **Runs**: Individual execution attempts of a task
- **Events**: Coordination signals between tasks and workflows
- **Checkpoints**: Persistent state saved during long-running operations
- **Workflows**: Orchestrated sequences of related tasks

Architecture
------------

The Absurd client provides a Python interface to PostgreSQL-stored procedures that manage:

- Task queueing and execution scheduling
- Worker claim management with configurable timeouts
- Event-driven coordination between tasks
- State persistence and checkpoint management
- Retry logic with configurable backoff strategies
- Workflow execution tracking across multiple tasks

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
