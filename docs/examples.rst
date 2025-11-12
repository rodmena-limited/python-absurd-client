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

Event Coordination Example
--------------------------

Coordinate between tasks using events:

.. code-block:: python

    from absurd_client import AbsurdClient, AbsurdSleepError
    from datetime import datetime, timedelta

    client = AbsurdClient(queue_name="event_coordination_queue")

    def producer_task(conn, run_id, task_id):
        """Task that processes data and emits an event"""
        # Process the data
        result = {"processed_data": "some_value", "timestamp": datetime.now().isoformat()}

        # Emit an event that other tasks can wait for
        client.emit_event(
            conn=conn,
            event_name="data_processed",
            payload=result
        )

        return {"status": "event_emitted", "data": result}

    def consumer_task(conn, run_id, task_id):
        """Task that waits for an event before proceeding"""
        try:
            # Wait for the data_processed event
            payload = client.wait_for_event(
                conn=conn,
                run_id=run_id,
                event_name="data_processed",
                timeout_seconds=3600,  # 1 hour timeout
                task_id=task_id,
                step_name="waiting_for_data"
            )
            return {"status": "received", "payload": payload}
        except AbsurdSleepError:
            # This is expected - orchestrator handles this by marking task as sleeping
            raise

    def orchestrator_handle_event_task(conn, run_id, task_id):
        """Orchestrator function that handles event processing"""
        try:
            result = consumer_task(conn, run_id, task_id)
            client.complete_task(conn, run_id, result)
        except AbsurdSleepError as e:
            # Mark the run as sleeping until the event occurs
            client.set_run_sleeping(conn, e.run_id, e.event_name)
            # Return without completing - task will resume when event occurs

    # Example usage
    with psycopg.connect("your_connection_string") as conn:
        # Producer task runs first, emits event
        prod_task_id, prod_run_id, _ = client.spawn_task(
            conn=conn,
            task_name="produce_data",
            params={}
        )

        # Consumer task runs later, waits for event
        cons_task_id, cons_run_id, _ = client.spawn_task(
            conn=conn,
            task_name="consume_data",
            params={}
        )

Scheduling and Cleanup Example
------------------------------

Schedule tasks and clean up old data:

.. code-block:: python

    from absurd_client import AbsurdClient
    from datetime import datetime, timedelta

    client = AbsurdClient(queue_name="scheduled_queue")

    # Spawn a task
    with psycopg.connect("your_connection_string") as conn:
        task_id, run_id, workflow_run_id = client.spawn_task(
            conn=conn,
            task_name="scheduled_task",
            params={"message": "Run later"}
        )

        # Schedule the task to run in 30 minutes
        future_time = datetime.now() + timedelta(minutes=30)
        client.schedule_task(conn, run_id, future_time)

        # Cancel a task if needed (only works if task is pending or sleeping)
        # client.cancel_task(conn, run_id)

        # Clean up old completed tasks (older than 24 hours)
        old_task_count = client.cleanup_tasks(conn, ttl_seconds=86400, limit=1000)
        print(f"Cleaned up {old_task_count} old completed tasks")

        # Clean up old events (older than 7 days)
        old_event_count = client.cleanup_events(conn, ttl_seconds=604800, limit=1000)
        print(f"Cleaned up {old_event_count} old events")

Status and Monitoring Example
-----------------------------

Monitor task and run statuses:

.. code-block:: python

    from absurd_client import AbsurdClient

    client = AbsurdClient(queue_name="monitoring_queue")

    with psycopg.connect("your_connection_string") as conn:
        # Spawn a task
        task_id, run_id, workflow_run_id = client.spawn_task(
            conn=conn,
            task_name="monitoring_task",
            params={"data": "value"}
        )

        # Get detailed task status
        task_status = client.get_task_status(conn, task_id)
        if task_status:
            print(f"Task state: {task_status['state']}")
            print(f"Task attempts: {task_status['attempts']}")
            print(f"Current params: {task_status['params']}")

        # Get detailed run status
        run_status = client.get_run_status(conn, run_id)
        if run_status:
            print(f"Run state: {run_status['state']}")
            print(f"Claimed by: {run_status['claimed_by']}")
            print(f"Started at: {run_status['started_at']}")

        # Get all checkpoints for a run
        checkpoints = client.get_checkpoints_for_run(conn, run_id)
        print(f"Found {len(checkpoints)} checkpoints: {list(checkpoints.keys())}")

Checkpoint Management for Complex Tasks
---------------------------------------

Advanced checkpoint management for complex long-running tasks:

.. code-block:: python

    from absurd_client import AbsurdClient
    import time

    client = AbsurdClient(queue_name="complex_task_queue")

    def complex_task_with_checkpoints(conn, run_id, task_id):
        """A complex task with multiple steps and checkpoints"""
        # Check if we have a checkpoint for this run to resume from
        resume_checkpoint = client.get_run_checkpoint(conn, run_id, "current_step")
        start_step = resume_checkpoint if resume_checkpoint else 1

        total_steps = 5

        for step in range(start_step, total_steps + 1):
            # Simulate processing for this step
            print(f"Processing step {step}/{total_steps}")
            time.sleep(1)  # Simulate work

            # Save progress checkpoint for this step
            client.save_checkpoint_for_run(
                conn=conn,
                run_id=run_id,
                step_name="current_step",
                data=step
            )

            # Save step-specific data
            client.save_checkpoint_for_run(
                conn=conn,
                run_id=run_id,
                step_name=f"step_{step}_data",
                data={"step_number": step, "processed": f"step_{step}_data", "completed_at": datetime.now().isoformat()}
            )

            # Extend claim if needed for long operations
            client.extend_claim(conn, run_id, extend_by_seconds=60)

        return {"status": "completed", "total_steps": total_steps}

    # Example usage
    with psycopg.connect("your_connection_string") as conn:
        # Spawn the complex task
        task_id, run_id, workflow_run_id = client.spawn_task(
            conn=conn,
            task_name="complex_task",
            params={"steps": 5}
        )

        # Process the task (this may be done in a worker)
        claimed_tasks = client.claim_task(conn)
        for task_data in claimed_tasks:
            run_id, task_id, *_ = task_data
            try:
                result = complex_task_with_checkpoints(conn, run_id, task_id)
                client.complete_task(conn, run_id, result)
            except Exception as e:
                client.fail_task(conn, run_id, str(e))