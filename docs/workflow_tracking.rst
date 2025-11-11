Workflow Tracking
=================

The Absurd client provides comprehensive workflow tracking capabilities that allow you to monitor and manage complex workflow executions. This feature was introduced in Phase 10 of the development.

Overview
--------

Workflow tracking enables you to:

- Create and monitor workflow runs
- Track workflow execution status across multiple tasks
- Store workflow inputs, outputs, and metadata
- Link multiple tasks to a single workflow run
- Monitor workflow progress and completion
- Support for complex workflow patterns with error handling

Creating Workflow Runs
----------------------

Use the ``create_workflow_run`` method to create a new workflow tracking record:

.. code-block:: python

    from absurd_client import AbsurdClient
    import uuid
    from datetime import datetime

    client = AbsurdClient(queue_name="workflow_queue")

    # Create a new workflow run
    workflow_run_id = client.create_workflow_run(
        conn=conn,
        workflow_name="data_pipeline",  # Must match ^[a-z][a-z0-9_]*$ and not contain '__'
        workflow_version="1.0.0",       # Must match ^[a-zA-Z0-9._-]+$ and not contain '__'
        inputs={"source": "s3://bucket/data", "target": "warehouse"},
        created_by="pipeline_system",
        tags={"environment": "production", "priority": "high"},
        workflow_hash="sha256_hash_of_definition"
    )

    print(f"Created workflow run: {workflow_run_id}")

Parameters for Workflow Creation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- ``conn``: Database connection (transaction-aware)
- ``workflow_name``: Logical workflow name (must match ``^[a-z][a-z0-9_]*$``, no '__')
- ``workflow_version``: Workflow version (must match ``^[a-zA-Z0-9._-]+$``, no '__')
- ``inputs``: Workflow input parameters (optional)
- ``absurd_run_id``: Optional root Absurd run_id (optional)
- ``created_by``: Optional user/system identifier (optional)
- ``tags``: Optional key-value tags for filtering (optional)
- ``workflow_hash``: Optional SHA-256 hash of workflow definition (optional)

.. note::
   Both ``workflow_name`` and ``workflow_version`` must not contain double underscores ('__')
   as this is reserved as a separator for display purposes: ``{workflow_name}__{version}__{step_name}``
   
   Workflow names must match: ``^[a-z][a-z0-9_]*$`` (lowercase, alphanumeric, single underscore)
   Workflow versions must match: ``^[a-zA-Z0-9._-]+$`` (semver compatible)

Updating Workflow Status
------------------------

Use the ``update_workflow_run_status`` method to update the status of a workflow run:

.. code-block:: python

    from datetime import datetime

    # Update workflow status to running
    client.update_workflow_run_status(
        conn=conn,
        workflow_run_id=workflow_run_id,
        status="running",
        started_at=datetime.now()
    )

    # Update workflow status to completed
    client.update_workflow_run_status(
        conn=conn,
        workflow_run_id=workflow_run_id,
        status="completed",
        result={"output": "final_result", "metrics": {"processed_records": 1000, "duration": "5min"}},
        completed_at=datetime.now(),
        task_count=10  # Number of tasks in the workflow
    )

    # Update workflow status to failed with detailed error information
    client.update_workflow_run_status(
        conn=conn,
        workflow_run_id=workflow_run_id,
        status="failed",
        error={
            "type": "ProcessingError",
            "message": "Data source unavailable",
            "details": {
                "source_url": "s3://bucket/data",
                "attempted_at": datetime.now().isoformat(),
                "retries_attempted": 3
            },
            "timestamp": datetime.now().isoformat()
        }
    )

Parameters for Status Updates
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- ``conn``: Database connection
- ``workflow_run_id``: UUID of workflow_run to update
- ``status``: New status (pending, running, completed, failed, cancelled)
- ``result``: Optional final result (optional)
- ``error``: Optional error details (optional)
- ``started_at``: Optional start timestamp (optional)
- ``completed_at``: Optional completion timestamp (optional)
- ``task_count``: Optional task count (optional)

Status Values
^^^^^^^^^^^^^

- ``pending``: Workflow has been created but not yet started
- ``running``: Workflow is currently executing
- ``completed``: Workflow has completed successfully
- ``failed``: Workflow has failed
- ``cancelled``: Workflow has been cancelled

Integration with Tasks
----------------------

Link tasks to workflow runs during task creation:

.. code-block:: python

    # Spawn a task that's part of a workflow
    task_id, run_id, actual_workflow_run_id = client.spawn_task(
        conn=conn,
        task_name="extract_data",
        params={"workflow_run_id": workflow_run_id},  # Link to workflow in parameters
        headers={"workflow_run_id": str(workflow_run_id)}  # Also store in headers
    )

This creates a connection between the Absurd task and the workflow run, allowing you to track the relationship between individual tasks and the overall workflow.

Full Workflow Execution Example
-------------------------------

Here's a complete example of a workflow using tracking:

.. code-block:: python

    from absurd_client import AbsurdClient
    from datetime import datetime

    def execute_data_pipeline():
        client = AbsurdClient(queue_name="pipeline_queue")
        
        with psycopg.connect("your_connection_string") as conn:
            # Create workflow run
            workflow_run_id = client.create_workflow_run(
                conn=conn,
                workflow_name="data_pipeline",
                workflow_version="1.0.0",
                inputs={"source": "s3://bucket/data", "target": "warehouse"},
                created_by="etl_system",
                tags={"environment": "production", "team": "data-eng"}
            )
            
            # Update status to running
            client.update_workflow_run_status(
                conn=conn,
                workflow_run_id=workflow_run_id,
                status="running",
                started_at=datetime.now()
            )
            
            try:
                # Spawn extraction task
                extract_task_id, extract_run_id, _ = client.spawn_task(
                    conn=conn,
                    task_name="extract_data",
                    params={"workflow_run_id": workflow_run_id, "source": "s3://bucket/data"},
                    headers={"workflow_run_id": str(workflow_run_id)}
                )
                
                # Process the extraction task
                # ... task processing logic ...
                
                # Spawn transformation task after extraction completes
                transform_task_id, transform_run_id, _ = client.spawn_task(
                    conn=conn,
                    task_name="transform_data",
                    params={"workflow_run_id": workflow_run_id, "input_format": "raw"},
                    headers={"workflow_run_id": str(workflow_run_id)}
                )
                
                # Process the transformation task
                # ... task processing logic ...
                
                # Update workflow status to completed
                client.update_workflow_run_status(
                    conn=conn,
                    workflow_run_id=workflow_run_id,
                    status="completed",
                    result={"output": "warehouse", "records_processed": 10000},
                    completed_at=datetime.now(),
                    task_count=2
                )
                
            except Exception as e:
                # Update workflow status to failed
                client.update_workflow_run_status(
                    conn=conn,
                    workflow_run_id=workflow_run_id,
                    status="failed",
                    error={
                        "type": type(e).__name__,
                        "message": str(e),
                        "timestamp": datetime.now().isoformat()
                    }
                )
                raise

Using with Highway DSL
----------------------

The workflow tracking features integrate well with the `highway-dsl <https://github.com/rodmena-limited/highway_dsl>`_ package, which provides a Python-based domain-specific language for defining complex workflows:

.. code-block:: python

    from highway_dsl import WorkflowBuilder, RetryPolicy
    from datetime import timedelta

    # Create a complex ETL workflow with Highway DSL
    workflow = (
        WorkflowBuilder("data_pipeline")
        .set_schedule("0 2 * * *")  # Daily at 2 AM
        .set_start_date(datetime.now())
        .add_tags("etl", "production")
        .set_max_active_runs(1)
        .set_default_retry_policy(RetryPolicy(
            max_retries=3,
            delay=timedelta(seconds=30),
            backoff_factor=2.0
        ))
        .task("extract", "etl.extract_data", result_key="raw_data")
        .task("transform", "etl.transform_data", args=["{{raw_data}}"], result_key="transformed_data")
        .parallel("process_branches", {
            "branch_a": lambda w: w.task("process_a", "etl.process_part_a", args=["{{transformed_data}}"]),
            "branch_b": lambda w: w.task("process_b", "etl.process_part_b", args=["{{transformed_data}}"])
        })
        .task("load", "etl.load_data", args=["{{transformed_data}}"])
        .build()
    )

    # Export to YAML for use with Absurd
    print(workflow.to_yaml())

    # This workflow can be executed using the Absurd client
    # with proper workflow run tracking