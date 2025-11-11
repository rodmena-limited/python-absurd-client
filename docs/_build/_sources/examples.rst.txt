Usage Examples
==============

This section provides comprehensive examples showing how to use the Absurd client for various scenarios.

Basic Task Processing
---------------------

A simple example of spawning and processing tasks:

.. code-block:: python

    import psycopg
    from absurd_client import AbsurdClient

    def process_task(task_name, params):
        """Simulate task processing"""
        if task_name == "echo":
            return {"output": f"Processed: {params.get('message', '')}"}
        return {"result": "unknown"}

    # Create client
    client = AbsurdClient(queue_name="default_queue")

    # Connect to database
    with psycopg.connect("your_connection_string") as conn:
        # Spawn a task
        task_id, run_id, workflow_run_id = client.spawn_task(
            conn=conn,
            task_name="echo",
            params={"message": "Hello, World!"}
        )

        print(f"Spawned task: {task_id}")

        # Claim and process tasks
        claimed_tasks = client.claim_task(conn, qty=1)
        for task_data in claimed_tasks:
            run_id, task_id, attempt, task_name, params, *_ = task_data

            try:
                result = process_task(task_name, params)
                client.complete_task(conn, run_id, result)
                print(f"Completed task {task_id}")
            except Exception as e:
                client.fail_task(conn, run_id, str(e))
                print(f"Failed task {task_id}: {e}")

Long-Running Tasks with Checkpoints
-----------------------------------

For tasks that run for extended periods, use checkpoints:

.. code-block:: python

    import time
    from absurd_client import AbsurdClient

    client = AbsurdClient(queue_name="long_running_queue")

    def long_running_task(conn, run_id, task_id):
        """Simulate a long-running task with checkpoints"""
        # Check if we have a checkpoint from a previous attempt
        checkpoint = client.get_checkpoint(conn, task_id, "progress")
        
        start_step = 1
        if checkpoint and checkpoint.get("state"):
            start_step = checkpoint["state"].get("current_step", 1)
        
        for step in range(start_step, 6):  # 5 steps total
            # Simulate work
            time.sleep(2)  # Simulate processing
            
            # Save checkpoint
            client.set_checkpoint(
                conn=conn,
                task_id=task_id,
                step_name="progress",
                state={"current_step": step, "completed": f"step_{step}"},
                owner_run=run_id
            )
            
            # Extend claim if needed for long operations
            client.extend_claim(conn, run_id, extend_by_seconds=60)

        return {"status": "completed", "steps": 5}

    with psycopg.connect("your_connection_string") as conn:
        # Spawn the long-running task
        task_id, run_id, workflow_run_id = client.spawn_task(
            conn=conn,
            task_name="long_running_task",
            params={"work": "complex_job"}
        )

        # Claim and process
        claimed_tasks = client.claim_task(conn)
        for task_data in claimed_tasks:
            run_id, task_id, *_ = task_data
            try:
                result = long_running_task(conn, run_id, task_id)
                client.complete_task(conn, run_id, result)
            except Exception as e:
                client.fail_task(conn, run_id, str(e))

Event-Driven Workflows
----------------------

Use events to coordinate between tasks:

.. code-block:: python

    from absurd_client import AbsurdClient, AbsurdSleepError
    import datetime

    client = AbsurdClient(queue_name="event_driven_queue")

    def task_that_waits_for_event(conn, run_id, task_id):
        """A task that waits for an event"""
        try:
            payload = client.wait_for_event(
                conn=conn,
                run_id=run_id,
                event_name="data_ready",
                timeout_seconds=3600,  # 1 hour
                task_id=task_id,
                step_name="waiting_for_data"
            )
            return {"status": "received", "payload": payload}
        except AbsurdSleepError:
            # This is expected - the orchestrator should handle this
            # by marking the task as sleeping
            raise

    def task_that_emits_event(conn):
        """A task that processes data and emits an event"""
        # Simulate data processing
        result = {"processed_data": "some_value"}
        
        # Emit the event that other tasks are waiting for
        client.emit_event(
            conn=conn,
            event_name="data_ready",
            payload=result
        )
        
        return {"status": "event_emitted", "data": result}

    # In a real orchestrator, you would handle AbsurdSleepError like this:
    def process_task_with_event_handling(conn, run_id, task_id):
        try:
            return task_that_waits_for_event(conn, run_id, task_id)
        except AbsurdSleepError as e:
            # Mark the run as sleeping until the event occurs
            client.set_run_sleeping(conn, e.run_id, e.event_name)
            # Return without completing the task - it will resume when event occurs
            return None

Retry Strategies
----------------

Handle failures with retry strategies:

.. code-block:: python

    from absurd_client import AbsurdClient, spawn_retry_task

    client = AbsurdClient(queue_name="retry_queue")

    def unreliable_task():
        """A task that sometimes fails"""
        import random
        if random.random() < 0.7:  # 70% chance of failure
            raise Exception("Random failure for demonstration")
        return {"status": "success"}

    with psycopg.connect("your_connection_string") as conn:
        # Spawn with retry strategy
        task_id, run_id, workflow_run_id = spawn_retry_task(
            client=client,
            conn=conn,
            task_name="unreliable_task",
            params={},
            max_attempts=5,
            retry_kind="exponential",
            base_seconds=10,
            factor=2.0
        )

        # Process the task
        claimed_tasks = client.claim_task(conn)
        for task_data in claimed_tasks:
            run_id, task_id, *_ = task_data
            
            try:
                result = unreliable_task()
                client.complete_task(conn, run_id, result)
            except Exception as e:
                # The retry logic is handled by Absurd
                client.fail_task(conn, run_id, str(e))

Scheduling and Delayed Execution
--------------------------------

Schedule tasks for future execution:

.. code-block:: python

    from absurd_client import AbsurdClient
    from datetime import datetime, timedelta

    client = AbsurdClient(queue_name="scheduled_queue")

    with psycopg.connect("your_connection_string") as conn:
        # Schedule a task to run in 10 minutes
        task_id, run_id, workflow_run_id = client.spawn_task(
            conn=conn,
            task_name="delayed_task",
            params={"message": "This will run later"}
        )
        
        # Schedule the task to run 10 minutes from now
        future_time = datetime.now() + timedelta(minutes=10)
        client.schedule_task(conn, run_id, future_time)
        
        print(f"Task {task_id} scheduled to run at {future_time}")

Connection Pooling Example
--------------------------

For production applications, use connection pooling:

.. code-block:: python

    from psycopg_pool import ConnectionPool
    from absurd_client import AbsurdClient
    import psycopg

    # Create a connection pool
    pool = ConnectionPool("your_connection_string", min_size=2, max_size=10)

    client = AbsurdClient(queue_name="pooled_queue")

    def process_task_with_pooling():
        with pool.connection() as conn:
            # Spawn a task
            task_id, run_id, workflow_run_id = client.spawn_task(
                conn=conn,
                task_name="pooled_task",
                params={"data": "value"}
            )
            
            # Process any claimed tasks
            claimed_tasks = client.claim_task(conn, qty=5)
            for task_data in claimed_tasks:
                run_id, task_id, attempt, task_name, params, *_ = task_data
                
                try:
                    result = {"processed": params}
                    client.complete_task(conn, run_id, result)
                except Exception as e:
                    client.fail_task(conn, run_id, str(e))

Cancellable Tasks
-----------------

Create tasks with cancellation rules:

.. code-block:: python

    from absurd_client import AbsurdClient, spawn_cancellable_task

    client = AbsurdClient(queue_name="cancellable_queue")

    with psycopg.connect("your_connection_string") as conn:
        # Spawn a task that can be cancelled if it takes too long
        task_id, run_id, workflow_run_id = spawn_cancellable_task(
            client=client,
            conn=conn,
            task_name="potentially_long_task",
            params={"data": "value"},
            max_delay_seconds=3600,  # Max 1 hour of delay
            max_duration_seconds=7200  # Max 2 hours total duration
        )

        # Later, you can cancel the task if needed
        # client.cancel_task(conn, run_id)

Workflow Tracking Example
-------------------------

Track complex workflows across multiple tasks:

.. code-block:: python

    from absurd_client import AbsurdClient
    import uuid

    client = AbsurdClient(queue_name="workflow_tracking_queue")

    def run_data_pipeline():
        with psycopg.connect("your_connection_string") as conn:
            # Create a workflow run to track this pipeline
            workflow_run_id = client.create_workflow_run(
                conn=conn,
                workflow_name="data_pipeline",
                workflow_version="1.0.0",
                inputs={"source": "s3://bucket/data", "target": "warehouse"},
                created_by="pipeline_system"
            )

            # Update workflow status
            client.update_workflow_run_status(
                conn=conn,
                workflow_run_id=workflow_run_id,
                status="running",
                started_at=datetime.now()
            )

            # Spawn the extraction task
            extract_task_id, extract_run_id, _ = client.spawn_task(
                conn=conn,
                task_name="extract_data",
                params={"workflow_run_id": workflow_run_id, "source": "s3://bucket/data"},
                headers={"workflow_run_id": str(workflow_run_id)}
            )

            # In a real scenario, subsequent tasks would be spawned after previous ones complete
            # For this example, we'll just mark the workflow as completed
            client.update_workflow_run_status(
                conn=conn,
                workflow_run_id=workflow_run_id,
                status="completed",
                result={"output": "processed_data"},
                completed_at=datetime.now(),
                task_count=3  # Assuming 3 total tasks in the workflow
            )

    run_data_pipeline()