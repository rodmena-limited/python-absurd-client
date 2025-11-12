Error Handling
==============

The Absurd client includes comprehensive error handling for various scenarios. Understanding these error patterns is crucial for building robust applications.

AbsurdSleepError
----------------

The ``AbsurdSleepError`` is a special exception that signals when a run enters SLEEPING state to wait for an event. This is used by the orchestrator to free worker threads while tasks wait for events.

.. code-block:: python

    from absurd_client import AbsurdClient, AbsurdSleepError

    client = AbsurdClient(queue_name="my_queue")

    try:
        payload = client.wait_for_event(
            conn=conn,
            run_id=run_id,
            event_name="data_ready",
            timeout_seconds=3600,
            task_id=task_id,
            step_name="waiting_step"
        )
    except AbsurdSleepError as e:
        # The orchestrator should catch this and mark the run as sleeping
        print(f"Run {e.run_id} sleeping, waiting for event '{e.event_name}'")
        # In a real orchestrator, this would mark the run as sleeping
        # and free the worker thread to process other tasks

    # In the orchestrator, you would typically handle it like this:
    def handle_task_processing():
        try:
            # Process task here
            pass
        except AbsurdSleepError as e:
            # Mark the run as sleeping
            client.set_run_sleeping(conn, e.run_id, e.event_name)
            # Free worker thread - return from function without completing task
            return

Database Errors
---------------

The client handles database errors appropriately:

.. code-block:: python

    from absurd_client import AbsurdClient

    client = AbsurdClient(queue_name="my_queue")

    try:
        # Attempt to complete a task
        client.complete_task(conn, run_id, result)
    except Exception as e:
        # Handle database errors or other issues
        print(f"Failed to complete task: {e}")
        # Handle appropriately based on your application needs

Validation Errors
-----------------

Queue names are validated to prevent SQL injection:

.. code-block:: python

    try:
        # This will raise ValueError if queue_name is invalid
        client = AbsurdClient(queue_name="invalid-queue-name!")  # Invalid character
    except ValueError as e:
        print(f"Invalid queue name: {e}")

    # Valid queue names contain only letters, numbers, and underscores
    # and must start with a letter or underscore
    client = AbsurdClient(queue_name="valid_queue_name")  # Valid

Event Wait Errors
-----------------

When using ``wait_for_event``, you must specify a timeout to prevent hung workflows:

.. code-block:: python

    from absurd_client import AbsurdClient

    client = AbsurdClient(queue_name="my_queue")

    try:
        # This will raise ValueError because no timeout is specified
        payload = client.wait_for_event(
            conn=conn,
            run_id=run_id,
            event_name="data_ready",
            # Missing timeout_seconds parameter
            task_id=task_id,
            step_name="waiting_step"
        )
    except ValueError as e:
        print(f"Timeout required: {e}")

    # Correct usage with timeout
    try:
        payload = client.wait_for_event(
            conn=conn,
            run_id=run_id,
            event_name="data_ready",
            timeout_seconds=3600,  # 1 hour timeout
            task_id=task_id,
            step_name="waiting_step"
        )
    except TimeoutError:
        print("Event not received within timeout period")
    except AbsurdSleepError:
        # Expected when waiting for events - orchestrator handles this
        pass

Timeout Handling for Events
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The client has sophisticated timeout detection for events:

.. code-block:: python

    from absurd_client import AbsurdClient, AbsurdSleepError

    client = AbsurdClient(queue_name="timeout_queue")

    try:
        # Wait for an event with timeout
        payload = client.wait_for_event(
            conn=conn,
            run_id=run_id,
            event_name="data_ready",
            timeout_seconds=1800,  # 30 minutes
            task_id=task_id,
            step_name="waiting_step"
        )
    except TimeoutError:
        print("Event timed out")
    except AbsurdSleepError:
        # When this exception is caught, the orchestrator should call:
        client.set_run_sleeping(conn, run_id, "data_ready")

Task Cancellation Errors
^^^^^^^^^^^^^^^^^^^^^^^^

When attempting to cancel tasks, consider their state:

.. code-block:: python

    from absurd_client import AbsurdClient

    client = AbsurdClient(queue_name="cancellation_queue")

    try:
        # Attempt to cancel a task
        cancelled = client.cancel_task(conn, run_id)
        if cancelled:
            print("Task was successfully cancelled")
        else:
            print("Task could not be cancelled (may already be running/completed)")
    except Exception as e:
        print(f"Error cancelling task: {e}")

Retry and Failure Handling
--------------------------

When tasks fail, you can specify detailed error information:

.. code-block:: python

    from absurd_client import AbsurdClient, spawn_retry_task
    from datetime import datetime

    client = AbsurdClient(queue_name="my_queue")

    # Spawn a task with retry strategy
    retry_strategy = {
        "kind": "exponential",
        "base_seconds": 30,
        "factor": 2.0,
        "max_seconds": 3600
    }

    task_id, run_id, workflow_run_id = client.spawn_task(
        conn=conn,
        task_name="reliable_task",
        params={"data": "value"},
        max_attempts=3,  # Will attempt up to 3 times
        retry_strategy=retry_strategy
    )

    # Fail a task with detailed error information
    try:
        # Process task and it fails
        raise Exception("Processing failed")
    except Exception as e:
        client.fail_task(
            conn=conn,
            run_id=run_id,
            reason={
                "name": "ProcessingError",
                "message": str(e),
                "timestamp": datetime.now().isoformat(),
                "details": {"input": "data_value", "step": "processing", "attempt": 1}
            }
        )

Connection Errors
-----------------

Always ensure proper connection management:

.. code-block:: python

    import psycopg
    from absurd_client import AbsurdClient

    client = AbsurdClient(queue_name="my_queue")

    # Use connection context managers to ensure proper cleanup
    try:
        with psycopg.connect("your_connection_string") as conn:
            task_id, run_id, workflow_run_id = client.spawn_task(
                conn=conn,
                task_name="example_task",
                params={"data": "value"}
            )
    except psycopg.OperationalError as e:
        print(f"Database connection error: {e}")
    except psycopg.Error as e:
        print(f"PostgreSQL error: {e}")

Exception Handling in Task Processing
-------------------------------------

Properly handle exceptions when processing tasks:

.. code-block:: python

    from absurd_client import AbsurdClient, AbsurdSleepError
    import logging

    client = AbsurdClient(queue_name="error_handling_queue")
    logger = logging.getLogger(__name__)

    def process_task_with_error_handling(conn, run_id, task_id, task_name, params):
        try:
            # Process the task
            result = execute_task_logic(task_name, params)
            client.complete_task(conn, run_id, result)
            logger.info(f"Task {task_id} completed successfully")
        except AbsurdSleepError as e:
            # Handle sleep error - this is expected for event-driven tasks
            client.set_run_sleeping(conn, e.run_id, e.event_name)
            logger.info(f"Task {task_id} sleeping, waiting for event {e.event_name}")
        except Exception as e:
            # Handle any other errors by failing the task
            error_info = {
                "name": type(e).__name__,
                "message": str(e),
                "timestamp": datetime.now().isoformat(),
                "traceback": str(e.__traceback__) if e.__traceback__ else None,
                "task_id": task_id,
                "run_id": run_id
            }
            client.fail_task(conn, run_id, error_info)
            logger.error(f"Task {task_id} failed: {error_info}")

Advanced Error Handling Patterns
--------------------------------

For complex workflows, consider implementing sophisticated error handling:

.. code-block:: python

    def process_with_retry_logic(conn, run_id, task_id, task_name, params):
        try:
            # Process the task with custom business logic
            result = custom_task_processor(task_name, params)
            client.complete_task(conn, run_id, result)
        except AbsurdSleepError:
            # Handle event wait (expected behavior)
            client.set_run_sleeping(conn, run_id, "expected_event")
        except TemporaryError as e:
            # For temporary errors, fail with retry
            client.fail_task(
                conn=conn,
                run_id=run_id,
                reason={
                    "name": "TemporaryError",
                    "message": str(e),
                    "is_retryable": True,
                    "timestamp": datetime.now().isoformat()
                }
            )
        except FatalError as e:
            # For fatal errors, fail without retry
            client.fail_task(
                conn=conn,
                run_id=run_id,
                reason={
                    "name": "FatalError",
                    "message": str(e),
                    "is_retryable": False,
                    "timestamp": datetime.now().isoformat()
                }
            )
        except Exception as e:
            # For unexpected errors, log and fail
            logger.error(f"Unexpected error processing task {task_id}: {e}", exc_info=True)
            client.fail_task(
                conn=conn,
                run_id=run_id,
                reason={
                    "name": "UnexpectedError",
                    "message": str(e),
                    "is_retryable": True,  # Retry for unknown errors
                    "timestamp": datetime.now().isoformat()
                }
            )

Best Practices
--------------

1. Always specify timeouts when using ``wait_for_event``
2. Use try-catch blocks around all client operations
3. Handle ``AbsurdSleepError`` appropriately in your orchestrator
4. Validate inputs before passing to client methods
5. Use connection pooling for production applications
6. Implement proper logging for error diagnosis
7. Test error handling paths in your application
8. Use detailed error messages that help with debugging
9. Distinguish between retryable and non-retryable errors
10. Implement circuit breaker patterns for external dependencies