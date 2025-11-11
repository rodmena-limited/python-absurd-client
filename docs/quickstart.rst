Quick Start
===========

This guide will help you get started with the Python Absurd client quickly. It covers the basic usage patterns and common operations.

Installation
------------

First, install the client:

.. code-block:: bash

    pip install absurd

Prerequisites
-------------

Before installing and using the Python Absurd client, you'll need:

- Python 3.8 or higher
- PostgreSQL with the Absurd extension installed
- Psycopg3 library for PostgreSQL connectivity

Basic Usage
-----------

Here's a comprehensive example that demonstrates the core functionality:

.. code-block:: python

    import psycopg
    from absurd_client import AbsurdClient

    # Create a client instance
    client = AbsurdClient(queue_name="my_queue")

    # Connect to your PostgreSQL database
    with psycopg.connect("your_connection_string") as conn:
        # Create the queue (optional - done automatically when spawning tasks)
        client.create_queue(conn)
        
        # Spawn a new task with comprehensive options
        task_id, run_id, workflow_run_id = client.spawn_task(
            conn=conn,
            task_name="process_data",
            params={"input": "data", "options": {"verbose": True}},
            headers={"priority": "high", "region": "us-east-1"},
            retry_strategy={
                "kind": "exponential",
                "base_seconds": 30,
                "factor": 2.0,
                "max_seconds": 3600
            },
            max_attempts=3,
            cancellation={
                "max_delay": 3600,      # Max 1 hour delay before starting
                "max_duration": 7200    # Max 2 hours total execution time
            }
        )

        print(f"Spawned task: {task_id}, run: {run_id}, workflow run: {workflow_run_id}")

        # Claim and process tasks
        claimed_tasks = client.claim_task(conn, qty=1, claim_timeout=60)
        for task_data in claimed_tasks:
            run_id, task_id, attempt, task_name, params, retry_strategy, max_attempts, headers, *_ = task_data

            try:
                # Process the task
                result = process_task(task_name, params)

                # Mark as completed
                client.complete_task(conn, run_id, result)
                print(f"Task {task_id} completed successfully")
            except Exception as e:
                # Mark as failed
                client.fail_task(conn, run_id, str(e))
                print(f"Task {task_id} failed: {e}")

Connection Management
---------------------

For production applications, use connection pooling for better resource management and performance:

.. code-block:: python

    from psycopg_pool import ConnectionPool
    from absurd_client import AbsurdClient

    # Create a connection pool
    pool = ConnectionPool("your_connection_string", min_size=2, max_size=10)
    client = AbsurdClient(queue_name="my_queue")

    # Use connection from pool
    with pool.connection() as conn:
        task_id, run_id, workflow_run_id = client.spawn_task(
            conn=conn,
            task_name="example_task",
            params={"data": "value"}
        )

Advanced Task Spawning
----------------------

Spawn tasks with retry strategies using convenience functions:

.. code-block:: python

    from absurd_client import spawn_retry_task

    # Using convenience function for retry tasks
    task_id, run_id, workflow_run_id = spawn_retry_task(
        client=client,
        conn=conn,
        task_name="reliable_task",
        params={"data": "value"},
        max_attempts=5,
        retry_kind="exponential",
        base_seconds=10,
        factor=2.0,
        max_seconds=3600  # Max 1 hour between retries
    )

Or spawn with cancellation rules:

.. code-block:: python

    from absurd_client import spawn_cancellable_task

    task_id, run_id, workflow_run_id = spawn_cancellable_task(
        client=client,
        conn=conn,
        task_name="long_running_task",
        params={"data": "value"},
        max_delay_seconds=3600,      # Max 1 hour of delay before starting
        max_duration_seconds=7200    # Max 2 hours total execution time
    )

Event-Driven Workflows
----------------------

Use events for cross-workflow coordination:

.. code-block:: python

    from absurd_client import AbsurdClient, AbsurdSleepError

    client = AbsurdClient(queue_name="event_queue")

    # Emit an event to signal completion
    client.emit_event(
        conn=conn,
        event_name="data_ready",
        payload={"processed_data": "result", "timestamp": "2025-01-01T00:00:00Z"}
    )

    # Wait for an event (in a task) - this requires error handling
    try:
        payload = client.wait_for_event(
            conn=conn,
            run_id=run_id,
            event_name="data_ready",
            timeout_seconds=3600,  # 1 hour
            task_id=task_id,
            step_name="waiting_step"
        )
        print(f"Received event payload: {payload}")
    except TimeoutError:
        print("Event not received within timeout")
    except AbsurdSleepError:
        # This exception is expected when using wait_for_event
        # The orchestrator will handle it and put the task to sleep
        pass

Checkpoint Management
---------------------

For long-running tasks, use checkpoints to save state and resume:

.. code-block:: python

    # Set a checkpoint for state persistence
    client.set_checkpoint(
        conn=conn,
        task_id=task_id,
        step_name="progress",
        state={"current_step": 5, "total_steps": 10, "data": "intermediate_result"},
        owner_run=run_id,
        extend_claim_by=60  # Extend claim by 60 seconds
    )

    # Retrieve a checkpoint
    checkpoint = client.get_checkpoint(conn, task_id, "progress")
    if checkpoint:
        print(f"Retrieved checkpoint: {checkpoint}")

Workflow Tracking
-----------------

Track complex workflows across multiple tasks:

.. code-block:: python

    from absurd_client import AbsurdClient
    from datetime import datetime

    client = AbsurdClient(queue_name="workflow_queue")

    # Create a workflow run to track execution
    workflow_run_id = client.create_workflow_run(
        conn=conn,
        workflow_name="data_pipeline",
        workflow_version="1.0.0",
        inputs={"source": "s3://bucket/data", "target": "warehouse"},
        created_by="pipeline_system",
        tags={"environment": "production", "priority": "high"}
    )

    # Spawn the first task in the workflow
    task_id, run_id, _ = client.spawn_task(
        conn=conn,
        task_name="extract_data",
        params={"workflow_run_id": workflow_run_id}  # Link to workflow
    )

    # Update workflow status
    client.update_workflow_run_status(
        conn=conn,
        workflow_run_id=workflow_run_id,
        status="running",
        started_at=datetime.now()
    )

    # Mark workflow as completed when finished
    client.update_workflow_run_status(
        conn=conn,
        workflow_run_id=workflow_run_id,
        status="completed",
        result={"output": "final_data"},
        completed_at=datetime.now()
    )

Singleton Pattern
-----------------

Use the singleton client instance for consistent configuration across your application:

.. code-block:: python

    from absurd_client import get_absurd_client

    # Get the shared client instance
    client = get_absurd_client(queue_name="my_queue")

    # Use the client throughout your application
    # It maintains consistent configuration across the application
    with psycopg.connect("your_connection_string") as conn:
        task_id, run_id, workflow_run_id = client.spawn_task(
            conn=conn,
            task_name="example_task",
            params={"data": "value"}
        )