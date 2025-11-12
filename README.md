# Absurd Python Client

A Python client for the [Absurd SQL-based durable execution workflow system](https://github.com/earendil-works/absurd). This library provides a Python interface to interact with Absurd's PostgreSQL-based task queue and workflow engine.

## Installation

```bash
pip install absurd
```

## Quick Start

```python
import psycopg
from absurd_client import AbsurdClient

# Create a client instance
client = AbsurdClient(queue_name="my_queue")

# Connect to your PostgreSQL database and spawn a task
with psycopg.connect("your_connection_string") as conn:
    # Spawn a new task
    task_id, run_id, workflow_run_id = client.spawn_task(
        conn=conn,
        task_name="process_data",
        params={"input": "data"}
    )

    print(f"Spawned task: {task_id}")

    # Claim and process tasks
    claimed_tasks = client.claim_task(conn)
    for task_data in claimed_tasks:
        run_id, task_id, attempt, task_name, params, *_ = task_data

        try:
            # Process the task
            result = {"processed": params}
            
            # Mark as completed
            client.complete_task(conn, run_id, result)
            print(f"Task {task_id} completed successfully")
        except Exception as e:
            # Mark as failed
            client.fail_task(conn, run_id, str(e))
            print(f"Task {task_id} failed: {e}")
```

## Highway DSL Integration

The [highway-dsl](https://github.com/rodmena-limited/highway_dsl) package provides a Python-based domain-specific language for defining complex workflows that fully supports Absurd:

```python
from highway_dsl import WorkflowBuilder, RetryPolicy
from datetime import timedelta

# Create a workflow with Highway DSL
workflow = (
    WorkflowBuilder("data_pipeline")
    .task("extract", "etl.extract_data", result_key="raw_data")
    .task("transform", "etl.transform_data", args=["{{raw_data}}"], result_key="transformed_data")
    .task("load", "etl.load_data", args=["{{transformed_data}}"])
    .build()
)

# Export to YAML for use with Absurd
print(workflow.to_yaml())
```

## Features

- Task queuing and processing
- Event-driven workflow coordination
- Checkpoint-based state management
- Retry strategies and failure handling
- Workflow run tracking
- Connection pooling for production environments
- Support for complex workflow patterns

## Configuration

The client supports the following environment variables:

- `ABSURD_DEFAULT_QUEUE`: Default queue name (default: `absurd_default`)
- `ABSURD_WORKER_ID`: Default worker ID (default: `absurd_worker_1`)

## Support

For support, please open an issue in the [GitHub repository](https://github.com/rodmena-limited/python-absurd-client).