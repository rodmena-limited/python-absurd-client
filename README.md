# Absurd Python Client

A Python client for the [Absurd SQL-based durable execution workflow system](https://github.com/earendil-works/absurd). This library provides a Python interface to interact with Absurd's PostgreSQL-based task queue and workflow engine.

## About Absurd

Absurd is a SQL workflow system that implements durable execution using PostgreSQL as the backend. It provides features such as:

- Task queuing and processing
- Durable task execution that survives crashes
- Event-driven workflow coordination
- Checkpoint-based state management
- Retry strategies and failure handling
- Workflow run tracking

## Installation

```bash
pip install absurd
```

## Requirements

- Python 3.8+
- PostgreSQL with the Absurd extension installed

## Quick Start

```python
import psycopg
from absurd_client import AbsurdClient

# Create a client instance
client = AbsurdClient(queue_name="my_queue")

# Connect to your PostgreSQL database
with psycopg.connect("your_connection_string") as conn:
    # Spawn a new task
    task_id, run_id, workflow_run_id = client.spawn_task(
        conn=conn,
        task_name="process_data",
        params={"input": "data"},
        options={"headers": {"priority": "high"}}
    )
    
    print(f"Spawned task: {task_id}, run: {run_id}, workflow: {workflow_run_id}")
    
    # Claim and process tasks
    claimed_tasks = client.claim_task(conn, qty=1)
    for task_data in claimed_tasks:
        run_id, task_id, attempt, task_name, params, *_ = task_data
        
        try:
            # Process the task
            result = process_task(task_name, params)
            
            # Mark as completed
            client.complete_task(conn, run_id, result)
        except Exception as e:
            # Mark as failed
            client.fail_task(conn, run_id, str(e))
```

## Features

### Task Management
- `spawn_task()`: Create new tasks with parameters, options, headers, retry strategies
- `claim_task()`: Claim tasks for processing
- `complete_task()`: Mark tasks as completed
- `fail_task()`: Mark tasks as failed with error information
- `cancel_task()`: Cancel pending or sleeping tasks

### Event Handling
- `await_event()`: Wait for specific events
- `emit_event()`: Emit events to wake sleeping tasks

### Checkpoint Management
- `set_checkpoint()`: Set checkpoints for long-running tasks
- `get_checkpoint()`: Retrieve checkpoint data

### Workflow Tracking
- `create_workflow_run()`: Track workflow execution
- `update_workflow_run_status()`: Update workflow status

### Helper Functions
- `spawn_retry_task()`: Convenience function for tasks with retry strategies
- `spawn_cancellable_task()`: Convenience function for tasks with cancellation rules
- `get_absurd_client()`: Singleton client instance

## Connection Management

The client works with psycopg3 connections. It's recommended to use connection pooling for production applications:

```python
from psycopg_pool import ConnectionPool
from absurd_client import AbsurdClient

pool = ConnectionPool("your_connection_string")
client = AbsurdClient(queue_name="my_queue")

with pool.connection() as conn:
    task_id, run_id, workflow_run_id = client.spawn_task(
        conn=conn,
        task_name="example_task",
        params={"data": "value"}
    )
```

## Error Handling

The client includes proper error handling for various scenarios:

- `AbsurdSleepError`: Raised when a run enters SLEEPING state waiting for an event
- Standard exception handling for database operations

## License

This project is licensed under the terms specified in the LICENSE file.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request on GitHub.

## Highway DSL Integration

The [highway-dsl](https://github.com/rodmena-limited/highway_dsl) package is a Python-based domain-specific language for defining complex workflows that fully supports Absurd. Highway DSL provides a fluent API for building workflows with features such as:

- **Rich Operators**: Task, Condition (if/else), Parallel, ForEach, While, Wait, Switch, EmitEvent, and WaitForEvent operators
- **Scheduling**: Built-in support for cron-based schedules, start dates, and catchup configuration
- **Event-Driven Features**: First-class support for event emission and waiting for cross-workflow coordination
- **Error Handling**: Retry policies, timeout policies, and callback hooks for production-grade workflows
- **YAML/JSON Interoperability**: Workflows can be defined in Python and exported to YAML or JSON
- **Mermaid Diagram Generation**: Visualize workflows with generated Mermaid diagrams

Example of defining a workflow with Highway DSL:

```python
from highway_dsl import WorkflowBuilder

workflow = (
    WorkflowBuilder("simple_etl")
    .task("extract", "etl.extract_data", result_key="raw_data")
    .task("transform", "etl.transform_data", args=["{{raw_data}}"], result_key="transformed_data")
    .task("load", "etl.load_data", args=["{{transformed_data}}"])
    .build()
)

# Export to YAML for use with Absurd
print(workflow.to_yaml())
```

With highway-dsl, you can define complex workflow patterns using a clear, fluent syntax and export them in formats compatible with Absurd's PostgreSQL-based workflow engine.

## Support

For support, please open an issue in the [GitHub repository](https://github.com/rodmena-limited/python-absurd-client).