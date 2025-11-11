# Absurd Python Client

A Python client for the [Absurd SQL-based durable execution workflow system](https://github.com/earendil-works/absurd). This library provides a Python interface to interact with Absurd's PostgreSQL-based task queue and workflow engine.

## About Absurd

Absurd is a SQL-based durable execution workflow system that uses PostgreSQL as the backend. It provides features such as:

- Task queuing and processing
- Durable task execution that survives crashes
- Event-driven workflow coordination
- Checkpoint-based state management
- Retry strategies and failure handling
- Workflow run tracking
- Support for complex workflow patterns
- Multi-tenant support (Phase 13)

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage Examples](#usage-examples)
  - [Basic Task Processing](#basic-task-processing)
  - [Task Management](#task-management)
  - [Event Handling](#event-handling)
  - [Checkpoint Management](#checkpoint-management)
  - [Workflow Tracking](#workflow-tracking)
  - [Connection Management](#connection-management)
  - [Retry Strategies](#retry-strategies)
  - [Cancellation Rules](#cancellation-rules)
  - [Long-Running Tasks](#long-running-tasks)
- [Error Handling](#error-handling)
- [Configuration](#configuration)
- [Highway DSL Integration](#highway-dsl-integration)
- [API Reference](#api-reference)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

## Features

### Core Functionality
- **Task Management**: Spawn, claim, complete, and fail tasks with comprehensive options
- **Event Handling**: Emit and wait for events for cross-workflow coordination
- **Checkpoint Management**: Save and restore state for long-running tasks
- **Retry Strategies**: Configure exponential and fixed retry backoff
- **Cancellation Rules**: Set time limits to automatically cancel tasks
- **Workflow Tracking**: Monitor complex workflow executions (Phase 10)
- **Connection Pooling**: Built-in support for efficient database connection management
- **Security**: SQL injection protected queue names and table identifiers

### Advanced Features
- **Multi-tenancy**: Tenant-aware operations (Phase 13)
- **Run Status Management**: Detailed tracking of task run states
- **Claim Extension**: Extend worker claims for long-running operations
- **Scheduling**: Delayed task execution and rate limiting
- **Cleanup**: Automated cleanup of completed tasks and events

## Installation

### Prerequisites
Before installing the Python Absurd client, you'll need:
- Python 3.8 or higher
- PostgreSQL with the Absurd extension installed
- Psycopg3 library for PostgreSQL connectivity

### Install from PyPI
```bash
pip install absurd
```

### Install from Source
```bash
git clone https://github.com/rodmena-limited/python-absurd-client.git
cd python-absurd-client
pip install .
```

### Development Installation
```bash
pip install -e ".[dev]"
```

## Quick Start

Here's a simple example that demonstrates the core functionality:

```python
import psycopg
from absurd_client import AbsurdClient

# Create a client instance
client = AbsurdClient(queue_name="my_queue")

# Connect to your PostgreSQL database
with psycopg.connect("your_connection_string") as conn:
    # Create the queue (optional - done automatically when spawning tasks)
    client.create_queue(conn)
    
    # Spawn a new task
    task_id, run_id, workflow_run_id = client.spawn_task(
        conn=conn,
        task_name="process_data",
        params={"input": "data"},
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
```

## Usage Examples

### Basic Task Processing

```python
import psycopg
from absurd_client import AbsurdClient

def process_task(task_name, params):
    """Simulate task processing"""
    if task_name == "echo":
        return {"output": f"Processed: {params.get('message', '')}", "status": "success"}
    return {"result": "unknown", "status": "error"}

# Create client
client = AbsurdClient(queue_name="default_queue")

# Connect to database and process tasks
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
```

### Task Management

The client provides comprehensive task management capabilities:

```python
from absurd_client import AbsurdClient

client = AbsurdClient(queue_name="task_queue")

with psycopg.connect("your_connection_string") as conn:
    # Spawn a task
    task_id, run_id, workflow_run_id = client.spawn_task(
        conn=conn,
        task_name="complex_task",
        params={"data": "value", "options": {"verbose": True}}
    )

    # Get detailed task status
    task_status = client.get_task_status(conn, task_id)
    print(f"Task state: {task_status['state']}")
    
    # Get detailed run status
    run_status = client.get_run_status(conn, run_id)
    print(f"Run state: {run_status['state']}")
    
    # Schedule the task for future execution
    from datetime import datetime, timedelta
    future_time = datetime.now() + timedelta(minutes=10)
    client.schedule_task(conn, run_id, future_time)
    
    # Cancel a task if needed
    # client.cancel_task(conn, run_id)  # Only works if task is pending or sleeping
```

### Event Handling

Use events for cross-workflow coordination:

```python
from absurd_client import AbsurdClient, AbsurdSleepError

client = AbsurdClient(queue_name="event_queue")

def task_that_waits_for_event(conn, run_id, task_id):
    """A task that waits for an event"""
    try:
        payload = client.wait_for_event(
            conn=conn,
            run_id=run_id,
            event_name="data_ready",
            timeout_seconds=3600,  # 1 hour timeout
            task_id=task_id,
            step_name="waiting_step"
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
```

### Checkpoint Management

For long-running tasks that need to save state:

```python
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
```

### Workflow Tracking

Track complex workflows across multiple tasks:

```python
from absurd_client import AbsurdClient
import uuid
from datetime import datetime

client = AbsurdClient(queue_name="workflow_tracking_queue")

def run_data_pipeline():
    with psycopg.connect("your_connection_string") as conn:
        # Create a workflow run to track this pipeline
        workflow_run_id = client.create_workflow_run(
            conn=conn,
            workflow_name="data_pipeline",
            workflow_version="1.0.0",
            inputs={"source": "s3://bucket/data", "target": "warehouse"},
            created_by="pipeline_system",
            tags={"environment": "production", "priority": "high"}
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

        # Process tasks (in real app, this would be a separate worker loop)
        claimed_tasks = client.claim_task(conn)
        for task_data in claimed_tasks:
            run_id, task_id, attempt, task_name, params, *_ = task_data
            
            try:
                # Simulate processing
                result = {"processed": f"Data from {params.get('source')}"}
                
                # Complete the task
                client.complete_task(conn, run_id, result)
                
                # Update workflow status when needed
                client.update_workflow_run_status(
                    conn=conn,
                    workflow_run_id=workflow_run_id,
                    status="completed",
                    result=result,
                    completed_at=datetime.now(),
                    task_count=1
                )
            except Exception as e:
                client.fail_task(conn, run_id, str(e))
                
                # Update workflow status to failed
                client.update_workflow_run_status(
                    conn=conn,
                    workflow_run_id=workflow_run_id,
                    status="failed",
                    error={
                        "type": "ProcessingError",
                        "message": str(e),
                        "timestamp": datetime.now().isoformat()
                    }
                )

run_data_pipeline()
```

### Connection Management

For production applications, use connection pooling:

```python
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

# Example with context manager for safety
def process_task_safely():
    try:
        with pool.connection() as conn:
            task_id, run_id, workflow_run_id = client.spawn_task(
                conn=conn,
                task_name="safe_task",
                params={"data": "value"}
            )
            # Process the task...
    except psycopg.OperationalError as e:
        print(f"Database connection error: {e}")
    except psycopg.Error as e:
        print(f"PostgreSQL error: {e}")
```

### Retry Strategies

Handle failures with configurable retry strategies:

```python
from absurd_client import AbsurdClient, spawn_retry_task

client = AbsurdClient(queue_name="retry_queue")

def unreliable_task():
    """A task that sometimes fails"""
    import random
    if random.random() < 0.7:  # 70% chance of failure
        raise Exception("Random failure for demonstration")
    return {"status": "success"}

with psycopg.connect("your_connection_string") as conn:
    # Spawn with retry strategy using convenience function
    task_id, run_id, workflow_run_id = spawn_retry_task(
        client=client,
        conn=conn,
        task_name="unreliable_task",
        params={},
        max_attempts=5,
        retry_kind="exponential",
        base_seconds=10,
        factor=2.0,
        max_seconds=3600  # Max 1 hour between retries
    )

    # Or spawn directly with retry strategy
    task_id, run_id, workflow_run_id = client.spawn_task(
        conn=conn,
        task_name="another_unreliable_task",
        params={},
        max_attempts=3,
        retry_strategy={
            "kind": "fixed",
            "base_seconds": 60  # Fixed 1 minute between retries
        }
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
```

### Cancellation Rules

Create tasks with automatic cancellation:

```python
from absurd_client import AbsurdClient, spawn_cancellable_task

client = AbsurdClient(queue_name="cancellable_queue")

with psycopg.connect("your_connection_string") as conn:
    # Spawn a task that can be cancelled if it takes too long
    task_id, run_id, workflow_run_id = spawn_cancellable_task(
        client=client,
        conn=conn,
        task_name="potentially_long_task",
        params={"data": "value"},
        max_delay_seconds=3600,      # Max 1 hour of delay before starting
        max_duration_seconds=7200    # Max 2 hours total duration
    )

    # Or spawn directly with cancellation rules
    task_id, run_id, workflow_run_id = client.spawn_task(
        conn=conn,
        task_name="another_long_task",
        params={"data": "value"},
        cancellation={
            "max_delay": 1800,      # Max 30 minutes of delay
            "max_duration": 3600    # Max 1 hour total execution time
        }
    )

    # Manually cancel a task if needed
    # client.cancel_task(conn, run_id)  # Only works for pending/sleeping tasks
```

### Long-Running Tasks

For tasks that need to extend their processing time:

```python
from absurd_client import AbsurdClient
import time

client = AbsurdClient(queue_name="long_task_queue")

def long_processing_task(conn, run_id, task_id):
    """A task that extends its claim as needed"""
    for i in range(10):  # 10 steps of processing
        time.sleep(10)  # Simulate work
        
        # Extend the claim by 60 seconds for each chunk of work
        client.extend_claim(conn, run_id, extend_by_seconds=60)
        
        # Save progress checkpoint
        client.set_checkpoint(
            conn=conn,
            task_id=task_id,
            step_name="progress",
            state={"step": i, "total": 10},
            owner_run=run_id
        )
    
    return {"status": "completed", "steps": 10}

with psycopg.connect("your_connection_string") as conn:
    task_id, run_id, workflow_run_id = client.spawn_task(
        conn=conn,
        task_name="long_processing",
        params={}
    )
    
    claimed_tasks = client.claim_task(conn)
    for task_data in claimed_tasks:
        run_id, task_id, *_ = task_data
        result = long_processing_task(conn, run_id, task_id)
        client.complete_task(conn, run_id, result)
```

## Error Handling

The client includes comprehensive error handling for various scenarios:

### AbsurdSleepError
The `AbsurdSleepError` is a special exception that signals when a run enters SLEEPING state to wait for an event:

```python
from absurd_client import AbsurdClient, AbsurdSleepError

client = AbsurdClient(queue_name="error_handling_queue")

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
```

### Database Errors
The client handles database errors appropriately:

```python
from absurd_client import AbsurdClient

client = AbsurdClient(queue_name="my_queue")

try:
    # Attempt to complete a task
    client.complete_task(conn, run_id, result)
except Exception as e:
    # Handle database errors or other issues
    print(f"Failed to complete task: {e}")
    # Handle appropriately based on your application needs
```

### Validation Errors
Queue names are validated to prevent SQL injection:

```python
try:
    # This will raise ValueError if queue_name is invalid
    client = AbsurdClient(queue_name="invalid-queue-name!")  # Invalid character
except ValueError as e:
    print(f"Invalid queue name: {e}")

# Valid queue names contain only letters, numbers, and underscores
# and must start with a letter or underscore
client = AbsurdClient(queue_name="valid_queue_name")  # Valid
```

## Configuration

### Environment Variables
The client supports the following environment variables:

- `ABSURD_DEFAULT_QUEUE`: Default queue name when not specified (default: `absurd_default`)
- `ABSURD_WORKER_ID`: Default worker ID (default: `absurd_worker_1`)

### Queue Name Validation
Queue names must follow these rules to prevent SQL injection:
- Must contain only letters, numbers, and underscores
- Must start with a letter or underscore
- Should not be overly long (recommendation: under 30 characters)

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
from highway_dsl import WorkflowBuilder, RetryPolicy
from datetime import timedelta

# Create a complex ETL workflow
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

# Generate Mermaid diagram
print(workflow.to_mermaid())
```

With highway-dsl, you can define complex workflow patterns using a clear, fluent syntax and export them in formats compatible with Absurd's PostgreSQL-based workflow engine.

## API Reference

### AbsurdClient Class

#### Constructor
`AbsurdClient(queue_name: str | None = None, worker_id: str | None = None)`

Creates a new AbsurdClient instance.

Parameters:
- `queue_name`: Name of the queue to use (defaults to environment variable `ABSURD_DEFAULT_QUEUE` or "absurd_default")
- `worker_id`: ID of the worker (defaults to environment variable `ABSURD_WORKER_ID` or "absurd_worker_1")

#### Core Methods

`create_queue(conn: psycopg.Connection) -> None`
Creates the Absurd queue if it doesn't exist.

`spawn_task(conn: psycopg.Connection, task_name: str, params: dict, options: dict | None = None, headers: dict | None = None, retry_strategy: dict | None = None, max_attempts: int | None = None, cancellation: dict | None = None, workflow_run_id: uuid.UUID | None = None) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]`
Spawns a new task in the Absurd queue.

Returns: (task_id, run_id, workflow_run_id)

`claim_task(conn: psycopg.Connection, worker_id: str | None = None, claim_timeout: int = 30, qty: int = 1) -> list[tuple[Any, ...]]`
Claims tasks from the Absurd queue.

`complete_task(conn: psycopg.Connection, run_id: uuid.UUID, result: dict[str, Any] | None = None) -> None`
Marks a task as completed.

`fail_task(conn: psycopg.Connection, run_id: uuid.UUID, reason: str | dict[str, Any], retry_at: datetime | None = None) -> None`
Marks a task as failed.

`cancel_task(conn: psycopg.Connection, run_id: uuid.UUID) -> bool`
Manually cancels a pending or sleeping task.

#### Event Handling Methods

`emit_event(conn: psycopg.Connection, event_name: str, payload: dict[str, Any] | None = None) -> None`
Emits an event and wakes any runs waiting for it.

`wait_for_event(conn: psycopg.Connection, run_id: uuid.UUID, event_name: str, timeout_seconds: int | None = None, task_id: uuid.UUID | None = None, step_name: str | None = None) -> Any`
Waits for an event using Absurd's sleep/wake mechanism.

`set_run_sleeping(conn: psycopg.Connection, run_id: uuid.UUID, event_name: str) -> None`
Marks a run as SLEEPING waiting for an event.

#### Checkpoint Management Methods

`set_checkpoint(conn: psycopg.Connection, task_id: uuid.UUID, step_name: str, state: dict[str, Any], owner_run: uuid.UUID, extend_claim_by: int | None = None) -> None`
Sets a checkpoint for a task with optional claim extension.

`get_checkpoint(conn: psycopg.Connection, task_id: uuid.UUID, step_name: str, include_pending: bool = False) -> dict[str, Any] | None`
Gets a checkpoint for a task.

`get_all_checkpoints(conn: psycopg.Connection, task_id: uuid.UUID, run_id: uuid.UUID) -> list[dict[str, Any]]`
Gets all checkpoints for a task.

`extend_claim(conn: psycopg.Connection, run_id: uuid.UUID, extend_by_seconds: int) -> None`
Extends the claim timeout for a long-running task.

#### Workflow Tracking Methods

`create_workflow_run(conn: psycopg.Connection, workflow_name: str, workflow_version: str, inputs: dict[str, Any] | None = None, absurd_run_id: uuid.UUID | None = None, created_by: str | None = None, tags: dict[str, Any] | None = None, workflow_hash: str | None = None) -> uuid.UUID`
Creates a new workflow_run record to track workflow execution.

`update_workflow_run_status(conn: psycopg.Connection, workflow_run_id: uuid.UUID, status: str, result: dict[str, Any] | None = None, error: dict[str, Any] | None = None, started_at: datetime | None = None, completed_at: datetime | None = None, task_count: int | None = None) -> None`
Updates workflow_run status and metadata.

#### Status and Utility Methods

`get_task_status(conn: psycopg.Connection, task_id: uuid.UUID) -> dict[str, Any] | None`
Gets detailed task status information.

`get_run_status(conn: psycopg.Connection, run_id: uuid.UUID) -> dict[str, Any] | None`
Gets detailed run status information.

`get_checkpoints_for_run(conn: psycopg.Connection, run_id: uuid.UUID) -> dict[str, Any]`
Gets all checkpoints for a specific run.

`save_checkpoint_for_run(conn: psycopg.Connection, run_id: uuid.UUID, step_name: str, data: Any, task_id: uuid.UUID | None = None) -> None`
Sets a checkpoint for a specific step.

`get_run_checkpoint(conn: psycopg.Connection, run_id: uuid.UUID, step_name: str) -> Any`
Gets a specific checkpoint for a run.

#### Scheduling and Management Methods

`schedule_task(conn: psycopg.Connection, run_id: uuid.UUID, wake_at: datetime) -> None`
Schedules a task to run at a specific time.

`cleanup_tasks(conn: psycopg.Connection, ttl_seconds: int, limit: int = 1000) -> int`
Cleans up old completed tasks.

`cleanup_events(conn: psycopg.Connection, ttl_seconds: int, limit: int = 1000) -> int`
Cleans up old events.

### Helper Functions

`spawn_retry_task(client: AbsurdClient, conn: psycopg.Connection, task_name: str, params: dict[str, Any], max_attempts: int = 3, retry_kind: str = "exponential", base_seconds: int = 30, factor: float = 2.0, max_seconds: int | None = None) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]`
Convenience function to spawn a task with retry strategy.

`spawn_cancellable_task(client: AbsurdClient, conn: psycopg.Connection, task_name: str, params: dict[str, Any], max_delay_seconds: int | None = None, max_duration_seconds: int | None = None) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]`
Convenience function to spawn a task with cancellation rules.

`get_absurd_client(queue_name: str | None = None, worker_id: str | None = None) -> AbsurdClient`
Returns the singleton AbsurdClient instance.

## Contributing

Contributions are welcome! Here's how you can help:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for your changes
5. Run the test suite (`pytest`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

Please make sure your code follows the project's coding standards and includes appropriate documentation and tests.

## License

This project is licensed under the terms specified in the LICENSE file.

## Support

For support, please open an issue in the [GitHub repository](https://github.com/rodmena-limited/python-absurd-client). For questions about usage or integration, feel free to create a discussion topic.

For commercial support or enterprise features, please contact the maintainers through the GitHub repository.