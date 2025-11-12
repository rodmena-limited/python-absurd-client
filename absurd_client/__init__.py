"""Python client for the Absurd SQL-based durable execution workflow system.

This module provides a client interface to interact with the Absurd workflow engine,
which is built on PostgreSQL. It allows you to spawn tasks, claim and process them,
handle events, manage checkpoints, and track workflow runs.
"""

__AUTHOR__ = "Farshid Ahouri"
__DESCRIPTION__ = "Python client for Absurd SQL-based durable execution workflow system"

import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg
from psycopg import sql


logger = logging.getLogger(__name__)


class AbsurdSleepError(Exception):
    """Raised when a run enters SLEEPING state to wait for an event.

    This signals to the orchestrator that the worker thread should be freed
    to process other tasks while this run waits.
    """

    def __init__(
        self,
        message: str,
        run_id: uuid.UUID | None = None,
        event_name: str | None = None,
        wake_at: datetime | None = None,
    ) -> None:
        super().__init__(message)
        self.run_id = run_id
        self.event_name = event_name
        self.wake_at = wake_at


class AbsurdClient:
    """Enhanced client for interacting with Absurd's SQL functions with full feature utilization."""

    def __init__(
        self,
        queue_name: str | None = None,
        worker_id: str | None = None,
    ):
        queue_name = queue_name or os.getenv("ABSURD_DEFAULT_QUEUE", "absurd_default")

        # CRITICAL SECURITY: Validate queue_name to prevent SQL injection
        # Queue names are used in table name construction (e.g., absurd.t_{queue_name})
        # Only allow alphanumeric characters and underscores
        if not queue_name or not self._is_valid_identifier(queue_name):
            msg = f"Invalid queue_name '{queue_name}'. Must contain only letters, numbers, and underscores."
            raise ValueError(
                msg,
            )

        self.queue_name = queue_name
        self.worker_id = worker_id or os.getenv("ABSURD_WORKER_ID", "absurd_worker_1")

    @staticmethod
    def _is_valid_identifier(name: str) -> bool:
        """Validate that a string is a safe SQL identifier.

        Args:
            name: String to validate

        Returns:
            True if safe to use as SQL identifier, False otherwise
        """
        # Allow only alphanumeric and underscores, must start with letter or underscore
        return bool(re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name))

    def create_queue(self, conn: psycopg.Connection) -> None:
        """Create the Absurd queue if it doesn't exist."""
        with conn.cursor() as cur:
            cur.execute(
                "SELECT absurd.create_queue(%(queue_name)s)",
                {"queue_name": self.queue_name},
            )

    def spawn_task(
        self,
        conn: psycopg.Connection,
        task_name: str,
        params: dict[str, Any],
        options: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
        retry_strategy: dict[str, Any] | None = None,
        max_attempts: int | None = None,
        cancellation: dict[str, Any] | None = None,
        workflow_run_id: uuid.UUID | None = None,
    ) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
        """Spawn a new task in the Absurd queue with full feature support.

        Args:
            conn: Database connection (psycopg3)
            task_name: Name of the task
            params: Task parameters
            options: Legacy options dict (for backward compatibility)
            headers: Task headers for metadata
            retry_strategy: Retry strategy configuration
            max_attempts: Maximum retry attempts
            cancellation: Cancellation rules (max_delay, max_duration)
            workflow_run_id: Optional workflow run ID for tracking

        Returns: (task_id, run_id, workflow_run_id)
        """
        # Ensure queue exists
        self.create_queue(conn)

        # Build comprehensive options dict
        task_options = options or {}

        # Add headers if provided (merge with workflow_run_id)
        task_headers = headers.copy() if headers else {}

        # Store workflow_run_id in headers if provided
        if workflow_run_id:
            task_headers["workflow_run_id"] = str(workflow_run_id)

        if task_headers:
            task_options["headers"] = task_headers

        # Add retry strategy if provided
        if retry_strategy:
            task_options["retry_strategy"] = retry_strategy

        # CRITICAL: ALWAYS set max_attempts (default to 1 = no retry if not provided)
        # Tasks should only retry if explicitly configured with retry_policy
        # Default = 1 attempt (0 retries) to prevent non-idempotent tasks from running twice
        task_options["max_attempts"] = max_attempts if max_attempts is not None else 1

        # Add cancellation rules if provided
        if cancellation:
            task_options["cancellation"] = cancellation

        logger.info(f"Spawning task '{task_name}' with options: {task_options}")

        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM absurd.spawn_task(%(queue_name)s, %(task_name)s, %(params)s, %(options)s)",
                {
                    "queue_name": self.queue_name,
                    "task_name": task_name,
                    "params": json.dumps(params),
                    "options": json.dumps(task_options),
                },
            )
            result = cur.fetchone()

        if result is None:
            msg = "Failed to spawn task"
            raise RuntimeError(msg)

        task_id, run_id = result[0], result[1]

        # Return workflow_run_id (either provided or default to run_id)
        actual_workflow_run_id = workflow_run_id or run_id

        return task_id, run_id, actual_workflow_run_id

    def claim_task(
        self,
        conn: psycopg.Connection,
        worker_id: str | None = None,
        claim_timeout: int = 30,
        qty: int = 1,
    ) -> list[tuple[Any, ...]]:
        """Claim tasks from the Absurd queue with advanced features.

        Args:
            conn: Database session
            worker_id: Worker identifier (defaults to instance worker_id)
            claim_timeout: Claim timeout in seconds (0 for no timeout)
            qty: Number of tasks to claim in batch (for high-throughput processing)

        Returns: List of (run_id, task_id, attempt, task_name, params, retry_strategy,
                          max_attempts, headers, wake_event, event_payload)
        """
        worker_id = worker_id or self.worker_id

        logger.info(
            f"Claiming {qty} task(s) from queue '{self.queue_name}' as worker '{worker_id}' with timeout {claim_timeout}s",
        )

        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM absurd.claim_task(%(queue_name)s, %(worker_id)s, %(claim_timeout)s, %(qty)s)",
                {
                    "queue_name": self.queue_name,
                    "worker_id": worker_id,
                    "claim_timeout": claim_timeout,
                    "qty": qty,
                },
            )
            result = cur.fetchall()

        logger.info(f"Claimed {len(result)} task(s)")
        return [tuple(row) for row in result]

    def complete_task(
        self,
        conn: psycopg.Connection,
        run_id: uuid.UUID,
        result: dict[str, Any] | None = None,
    ) -> None:
        """Mark a task as completed with state validation support."""
        logger.info(f"Completing task run {run_id}")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT absurd.complete_run(%(queue_name)s, %(run_id)s, %(result)s)",
                    {
                        "queue_name": self.queue_name,
                        "run_id": run_id,
                        "result": json.dumps(result or {}),
                    },
                )
            logger.info(f"Successfully completed task run {run_id}")
        except Exception as e:
            logger.error(f"Failed to complete task run {run_id}: {e}")
            # Re-raise to handle state validation errors
            raise

    def fail_task(
        self,
        conn: psycopg.Connection,
        run_id: uuid.UUID,
        reason: str | dict[str, Any],
        retry_at: datetime | None = None,
    ) -> None:
        """Mark a task as failed with detailed error information.

        Args:
            conn: Database session
            run_id: Task run ID
            reason: Failure reason (string or detailed dict)
            retry_at: Optional retry timestamp (for manual retry scheduling)
        """
        # Convert string reason to detailed error format
        if isinstance(reason, str):
            failure_reason = {
                "name": "TaskExecutionError",
                "message": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        else:
            failure_reason = reason

        logger.warning(f"Failing task run {run_id}: {failure_reason}")

        # Format retry_at as ISO string if provided
        retry_at_str = retry_at.isoformat() if retry_at else None

        with conn.cursor() as cur:
            cur.execute(
                "SELECT absurd.fail_run(%(queue_name)s, %(run_id)s, %(reason)s, %(retry_at)s)",
                {
                    "queue_name": self.queue_name,
                    "run_id": run_id,
                    "reason": json.dumps(failure_reason),
                    "retry_at": retry_at_str,
                },
            )

    def cancel_task(
        self,
        conn: psycopg.Connection,
        run_id: uuid.UUID,
    ) -> bool:
        """Manually cancel a pending or sleeping task.

        Args:
            conn: Database connection
            run_id: Task run ID to cancel

        Returns:
            True if task was cancelled, False if it couldn't be cancelled
            (already running, completed, or failed)

        Raises:
            Exception: If task not found or database error
        """
        logger.info(f"Cancelling task run {run_id}")

        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT absurd.cancel_task(%(queue_name)s, %(run_id)s)",
                    {
                        "queue_name": self.queue_name,
                        "run_id": run_id,
                    },
                )
                result = cur.fetchone()
                cancelled = result[0] if result else False

            if cancelled:
                logger.info(f"Successfully cancelled task run {run_id}")
            else:
                logger.warning(f"Could not cancel task run {run_id} (may already be running/completed)")

            return cancelled

        except Exception as e:
            logger.error(f"Failed to cancel task run {run_id}: {e}")
            raise

    def extend_claim(
        self,
        conn: psycopg.Connection,
        run_id: uuid.UUID,
        extend_by_seconds: int,
    ) -> None:
        """Extend the claim timeout for a long-running task.

        This is crucial for tasks that take longer than the initial claim timeout.
        """
        logger.info(f"Extending claim for run {run_id} by {extend_by_seconds} seconds")

        # Use set_checkpoint with extend_claim_by to extend the claim
        with conn.cursor() as cur:
            cur.execute(
                "SELECT absurd.set_task_checkpoint_state(%(queue_name)s, %(task_id)s, %(step_name)s, %(state)s, %(owner_run)s, %(extend_claim_by)s)",
                {
                    "queue_name": self.queue_name,
                    "task_id": run_id,  # Using run_id as task_id for claim extension
                    "step_name": "claim_extension",
                    "state": json.dumps(
                        {
                            "extended_at": datetime.now(timezone.utc).isoformat(),
                            "extend_by": extend_by_seconds,
                        },
                    ),
                    "owner_run": run_id,
                    "extend_claim_by": extend_by_seconds,
                },
            )

    def set_checkpoint(
        self,
        conn: psycopg.Connection,
        task_id: uuid.UUID,
        step_name: str,
        state: dict[str, Any],
        owner_run: uuid.UUID,
        extend_claim_by: int | None = None,
    ) -> None:
        """Set a checkpoint for a task with optional claim extension.

        Args:
            conn: Database session
            task_id: Task ID
            step_name: Checkpoint step name
            state: Checkpoint state data
            owner_run: Run ID that owns this checkpoint
            extend_claim_by: Optional claim extension in seconds
        """
        logger.info(f"Setting checkpoint '{step_name}' for task {task_id}")

        with conn.cursor() as cur:
            cur.execute(
                "SELECT absurd.set_task_checkpoint_state(%(queue_name)s, %(task_id)s, %(step_name)s, %(state)s, %(owner_run)s, %(extend_claim_by)s)",
                {
                    "queue_name": self.queue_name,
                    "task_id": task_id,
                    "step_name": step_name,
                    "state": json.dumps(state),
                    "owner_run": owner_run,
                    "extend_claim_by": extend_claim_by,
                },
            )

    def get_checkpoint(
        self,
        conn: psycopg.Connection,
        task_id: uuid.UUID,
        step_name: str,
        include_pending: bool = False,
    ) -> dict[str, Any] | None:
        """Get a checkpoint for a task."""
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM absurd.get_task_checkpoint_state(%(queue_name)s, %(task_id)s, %(step_name)s, %(include_pending)s)",
                {
                    "queue_name": self.queue_name,
                    "task_id": task_id,
                    "step_name": step_name,
                    "include_pending": include_pending,
                },
            )
            result = cur.fetchone()

        if result:
            return {
                "checkpoint_name": result[0],
                "state": result[1],
                "status": result[2],
                "owner_run_id": result[3],
                "updated_at": result[4],
            }
        return None

    def get_all_checkpoints(
        self,
        conn: psycopg.Connection,
        task_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """Get all checkpoints for a task."""
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM absurd.get_task_checkpoint_states(%(queue_name)s, %(task_id)s, %(run_id)s)",
                {"queue_name": self.queue_name, "task_id": task_id, "run_id": run_id},
            )
            results = cur.fetchall()

        checkpoints = []
        for result in results:
            checkpoints.append(
                {
                    "checkpoint_name": result[0],
                    "state": result[1],
                    "status": result[2],
                    "owner_run_id": result[3],
                    "updated_at": result[4],
                },
            )

        return checkpoints

    def await_event(
        self,
        conn: psycopg.Connection,
        task_id: uuid.UUID,
        run_id: uuid.UUID,
        step_name: str,
        event_name: str,
        timeout: int | None = None,
    ) -> tuple[bool, dict[str, Any] | None]:
        """Wait for an event with timeout support.

        Args:
            conn: Database session
            task_id: Task ID
            run_id: Run ID
            step_name: Step name
            event_name: Event name to wait for
            timeout: Timeout in seconds (None for no timeout)

        Returns: (should_suspend, payload)
        """
        logger.info(
            f"Task {task_id} awaiting event '{event_name}' with timeout {timeout}s",
        )

        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM absurd.await_event(%(queue_name)s, %(task_id)s, %(run_id)s, %(step_name)s, %(event_name)s, %(timeout)s)",
                {
                    "queue_name": self.queue_name,
                    "task_id": task_id,
                    "run_id": run_id,
                    "step_name": step_name,
                    "event_name": event_name,
                    "timeout": timeout,
                },
            )
            result = cur.fetchone()

        should_suspend = result[0] if result else True
        payload = result[1] if result and len(result) > 1 else None

        if should_suspend:
            logger.info(f"Task {task_id} suspended waiting for event '{event_name}'")
        else:
            logger.info(
                f"Task {task_id} received event '{event_name}' with payload: {payload}",
            )

        return should_suspend, payload

    def schedule_task(self, conn: psycopg.Connection, run_id: uuid.UUID, wake_at: datetime) -> None:
        """Schedule a task to run at a specific time.

        Useful for delayed execution or rate limiting.
        """
        logger.info(f"Scheduling task run {run_id} to wake at {wake_at}")

        with conn.cursor() as cur:
            cur.execute(
                "SELECT absurd.schedule_run(%(queue_name)s, %(run_id)s, %(wake_at)s)",
                {
                    "queue_name": self.queue_name,
                    "run_id": run_id,
                    "wake_at": wake_at.isoformat(),
                },
            )

    def cleanup_tasks(self, conn: psycopg.Connection, ttl_seconds: int, limit: int = 1000) -> int:
        """Clean up old completed tasks."""
        logger.info(
            f"Cleaning up tasks older than {ttl_seconds} seconds (limit: {limit})",
        )

        with conn.cursor() as cur:
            cur.execute(
                "SELECT absurd.cleanup_tasks(%(queue_name)s, %(ttl_seconds)s, %(limit)s)",
                {"queue_name": self.queue_name, "ttl_seconds": ttl_seconds, "limit": limit},
            )
            result = cur.fetchone()

        cleaned_count = result[0] if result else 0
        logger.info(f"Cleaned up {cleaned_count} tasks")
        return cleaned_count

    def cleanup_events(self, conn: psycopg.Connection, ttl_seconds: int, limit: int = 1000) -> int:
        """Clean up old events."""
        logger.info(
            f"Cleaning up events older than {ttl_seconds} seconds (limit: {limit})",
        )

        with conn.cursor() as cur:
            cur.execute(
                "SELECT absurd.cleanup_events(%(queue_name)s, %(ttl_seconds)s, %(limit)s)",
                {"queue_name": self.queue_name, "ttl_seconds": ttl_seconds, "limit": limit},
            )
            result = cur.fetchone()

        cleaned_count = result[0] if result else 0
        logger.info(f"Cleaned up {cleaned_count} events")
        return cleaned_count

    def get_task_status(
        self,
        conn: psycopg.Connection,
        task_id: uuid.UUID,
    ) -> dict[str, Any] | None:
        """Get detailed task status information.

        LOW PRIORITY FIX (Issue #16): Direct table query with locking.
        Absurd does not provide a stored procedure for retrieving task status,
        so we must query the tasks table directly. Using FOR SHARE lock to
        ensure we read committed data and prevent phantom reads.

        Note: This is a read-only operation with low impact on data consistency.
        """
        # SECURITY FIX: Use sql.Identifier to prevent SQL injection
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL(
                    "SELECT * FROM {schema}.{table} WHERE task_id = %(task_id)s FOR SHARE"
                ).format(
                    schema=sql.Identifier("absurd"),
                    table=sql.Identifier(f"t_{self.queue_name}"),
                ),
                {"task_id": task_id},
            )
            result = cur.fetchone()

        if not result:
            return None

        # Convert result to dict (column names would be needed for full mapping)
        # NOTE: tenant_id is at index 14 (last column, added in Phase 13)
        return {
            "task_id": result[0],
            "task_name": result[1],
            "params": result[2],
            "headers": result[3],
            "retry_strategy": result[4],
            "max_attempts": result[5],
            "cancellation": result[6],
            "enqueue_at": result[7],
            "first_started_at": result[8],
            "state": result[9],
            "attempts": result[10],
            "last_attempt_run": result[11],
            "completed_payload": result[12],
            "cancelled_at": result[13],
            "tenant_id": result[14],  # Phase 13: tenant_id added at end
        }

    def get_run_status(
        self,
        conn: psycopg.Connection,
        run_id: uuid.UUID,
    ) -> dict[str, Any] | None:
        """Get detailed run status information.

        LOW PRIORITY FIX (Issue #17): Direct table query with locking.
        Absurd does not provide a stored procedure for retrieving run status,
        so we must query the runs table directly. Using FOR SHARE lock to
        ensure we read committed data and prevent phantom reads.

        Note: This is a read-only operation with low impact on data consistency.
        """
        # SECURITY FIX: Use sql.Identifier to prevent SQL injection
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL(
                    "SELECT * FROM {schema}.{table} WHERE run_id = %(run_id)s FOR SHARE"
                ).format(
                    schema=sql.Identifier("absurd"),
                    table=sql.Identifier(f"r_{self.queue_name}"),
                ),
                {"run_id": run_id},
            )
            result = cur.fetchone()

        if not result:
            return None

        # Convert result to dict - runs table has different columns
        # NOTE: tenant_id is at index 16 (last column, added in Phase 13)
        # Actual columns: run_id, task_id, attempt, state, claimed_by, claim_expires_at,
        #                 available_at, wake_event, event_payload, started_at, completed_at, failed_at,
        #                 result, failure_reason, created_at, last_heartbeat, tenant_id
        return {
            "run_id": result[0],
            "task_id": result[1],
            "attempt": result[2],
            "state": result[3],
            "claimed_by": result[4],
            "claim_expires_at": result[5],
            "available_at": result[6],
            "wake_event": result[7],
            "event_payload": result[8],
            "started_at": result[9],
            "completed_at": result[10],
            "failed_at": result[11],
            "result": result[12],
            "failure_reason": result[13],
            "created_at": result[14],
            "last_heartbeat": result[15],
            "tenant_id": result[16],  # Phase 13: tenant_id added at end
        }

    def get_checkpoints_for_run(
        self, conn: psycopg.Connection, run_id: uuid.UUID
    ) -> dict[str, Any]:
        """Get all checkpoints for a specific run.

        LOW PRIORITY FIX (Issue #18): Direct table query with locking.
        While Absurd provides absurd.get_task_checkpoint_states(), it requires a task_id.
        This method is called with only run_id (from DurableContext initialization),
        so we must query the checkpoints table directly by owner_run_id.
        Using FOR SHARE lock to ensure we read committed data.

        Note: This is a read-only operation with low impact on data consistency.
        """
        # SECURITY FIX: Use sql.Identifier to prevent SQL injection
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL(
                    "SELECT checkpoint_name, state FROM {schema}.{table} WHERE owner_run_id = %(run_id)s FOR SHARE"
                ).format(
                    schema=sql.Identifier("absurd"),
                    table=sql.Identifier(f"c_{self.queue_name}"),
                ),
                {"run_id": run_id},
            )
            results = cur.fetchall()

        checkpoints = {}
        for row in results:
            checkpoint_name = row[0]
            state = row[1]
            checkpoints[checkpoint_name] = state

        return checkpoints

    def save_checkpoint_for_run(
        self,
        conn: psycopg.Connection,
        run_id: uuid.UUID,
        step_name: str,
        data: Any,
        task_id: uuid.UUID | None = None,
    ) -> None:
        """Set a checkpoint for a specific step (convenience wrapper for DurableContext)."""
        if task_id is None:
            # If no task_id provided, we need to find the current task for this run
            # This is a simplified approach - in practice you might want to track this better
            task_id = self._get_current_task_id(conn, run_id)

        if task_id:
            # Call the actual checkpoint method with proper parameters
            logger.info(f"Setting checkpoint '{step_name}' for task {task_id}")
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT absurd.set_task_checkpoint_state(%(queue_name)s, %(task_id)s, %(step_name)s, %(state)s, %(owner_run)s, %(extend_claim_by)s)",
                    {
                        "queue_name": self.queue_name,
                        "task_id": task_id,
                        "step_name": step_name,
                        "state": json.dumps(data),
                        "owner_run": run_id,
                        "extend_claim_by": None,
                    },
                )
        else:
            # If we can't find a task_id, we can't save the checkpoint
            # This might indicate we need to spawn a task first
            logger.warning(
                f"No task_id found for run {run_id}, cannot save checkpoint for step {step_name}",
            )

    def _get_current_task_id(
        self,
        conn: psycopg.Connection,
        run_id: uuid.UUID,
    ) -> uuid.UUID | None:
        """Get the current task ID for a run.

        LOW PRIORITY FIX (Issue #19): Direct table query with locking.
        Absurd does not provide a stored procedure for retrieving task_id from run_id,
        so we must query the runs table directly. Using FOR SHARE lock to
        ensure we read committed data.

        Note: This is a read-only operation with low impact on data consistency.
        """
        # SECURITY FIX: Use sql.Identifier to prevent SQL injection
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL(
                    "SELECT task_id FROM {schema}.{table} WHERE run_id = %(run_id)s ORDER BY started_at DESC LIMIT 1 FOR SHARE"
                ).format(
                    schema=sql.Identifier("absurd"),
                    table=sql.Identifier(f"r_{self.queue_name}"),
                ),
                {"run_id": run_id},
            )
            result = cur.fetchone()

        if result:
            return result[0]  # type: ignore[no-any-return]
        return None

    def sleep(self, conn: psycopg.Connection, run_id: uuid.UUID, duration_seconds: int) -> None:
        """Durable sleep that survives crashes and restarts."""
        # This would typically be implemented using Absurd's sleep functionality
        # For now, we'll create a simple implementation that sets a wake time
        wake_time = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)

        # Store the sleep information in a checkpoint
        self.set_checkpoint(
            conn,
            run_id,  # task_id
            f"sleep_{duration_seconds}",
            {
                "type": "sleep",
                "duration": duration_seconds,
                "wake_time": wake_time.isoformat(),
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
            run_id,  # owner_run
        )

        # In a real implementation, this would integrate with Absurd's sleep system
        # For now, we'll just log it
        logger.info(
            f"Sleep scheduled for {duration_seconds} seconds, waking at {wake_time}",
        )

    def wait_for_event(
        self,
        conn: psycopg.Connection,
        run_id: uuid.UUID,
        event_name: str,
        timeout_seconds: int | None = None,
        task_id: uuid.UUID | None = None,
        step_name: str | None = None,
    ) -> Any:
        """Wait for an event using Absurd's sleep/wake mechanism.

        This implements the proper Absurd pattern:
        1. Check if event already exists (fast path - return immediately)
        2. Check if this run has been woken with event payload
        3. If not, register wait and mark run as SLEEPING
        4. Orchestrator will free worker thread and process other tasks
        5. When event is emitted, run is woken and will resume here

        Args:
            conn: Database session
            run_id: The Absurd run ID (NOT workflow run ID!)
            event_name: Name of event to wait for
            timeout_seconds: Optional timeout (default 24 hours)
            task_id: The Absurd task ID (required for registering wait)
            step_name: The step name (required for registering wait)

        Returns:
            Event payload when event is received

        Raises:
            TimeoutError: If timeout expires before event received
        """
        # CRITICAL: No default timeout - user MUST specify or it will fail fast
        # DO NOT add a default here - forcing user to be explicit prevents hung workflows
        if timeout_seconds is None:
            msg = (
                f"timeout_seconds is required for wait_for_event (event: {event_name}). "
                "DO NOT rely on defaults - specify an explicit timeout to prevent hung workflows."
            )
            raise ValueError(
                msg,
            )

        logger.info(f"[wait_for_event] START: Waiting for event '{event_name}' for run {run_id}")

        # Check if event already exists in events table
        # SECURITY FIX: Use sql.Identifier to prevent SQL injection
        logger.info(f"[wait_for_event] Step 1: Checking events table for '{event_name}'")
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL(
                    "SELECT payload FROM {schema}.{table} WHERE event_name = %(event_name)s LIMIT 1"
                ).format(
                    schema=sql.Identifier("absurd"),
                    table=sql.Identifier(f"e_{self.queue_name}"),
                ),
                {"event_name": event_name},
            )
            result = cur.fetchone()

        if result:
            logger.info(
                f"[wait_for_event] FAST PATH: Found event '{event_name}' in events table, payload={result[0]}"
            )

            # Check if payload indicates timeout
            payload = result[0]
            if isinstance(payload, dict) and payload.get("timeout") is True:
                logger.warning(
                    "[wait_for_event] FAST PATH TIMEOUT: Event payload indicates timeout, raising TimeoutError"
                )
                raise TimeoutError(
                    f"Timeout waiting for event '{event_name}' after {timeout_seconds} seconds"
                )

            return payload
        logger.info(
            f"[wait_for_event] Event '{event_name}' not in events table, checking run payload"
        )

        # Check if this run has been woken with event payload
        # SECURITY FIX: Use sql.Identifier to prevent SQL injection
        logger.debug(f"[wait_for_event] Checking run's event_payload for run_id={run_id}")
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL(
                    "SELECT event_payload, state, wake_event FROM {schema}.{table} WHERE run_id = %(run_id)s"
                ).format(
                    schema=sql.Identifier("absurd"),
                    table=sql.Identifier(f"r_{self.queue_name}"),
                ),
                {"run_id": run_id},
            )
            run_result = cur.fetchone()

        if run_result:
            event_payload, _run_state, wake_event = run_result
            logger.info(
                f"[FAST PATH] Run found: event_payload={event_payload}, wake_event={wake_event}, run_state={_run_state}"
            )
            logger.info(
                f"[FAST PATH] Checking conditions: event_payload type={type(event_payload)}, wake_event matches={wake_event == event_name}"
            )

            # ALWAYS check for timeout payload first, regardless of wake_event value
            # Absurd sets event_payload={'timeout': True} on timeout, even if wake_event doesn't match
            if isinstance(event_payload, dict) and event_payload.get("timeout") is True:
                logger.warning(
                    "[FAST PATH] TIMEOUT: Detected timeout payload, raising TimeoutError"
                )
                raise TimeoutError(
                    f"Timeout waiting for event '{event_name}' after {timeout_seconds} seconds"
                )
            logger.info("[FAST PATH] No timeout payload detected, continuing checks")

            # Only consume event_payload if it matches the event we're waiting for
            if event_payload and wake_event == event_name:
                logger.info(
                    f"[FAST PATH] MATCH: wake_event matches event_name, returning event_payload={event_payload}"
                )
                return event_payload
            if event_payload and wake_event != event_name:
                # Ignore stale payload from a different event
                logger.info(
                    f"[FAST PATH] STALE: Ignoring stale payload for '{wake_event}' while waiting for '{event_name}'"
                )
            else:
                logger.info(
                    "[FAST PATH] NO PAYLOAD: event_payload is None or empty, continuing to timeout detection"
                )

        # Event doesn't exist yet - register wait and enter SLEEPING state
        if not task_id or not step_name:
            msg = "task_id and step_name required for registering event wait"
            raise ValueError(
                msg,
            )

        # TIMEOUT DETECTION: Check if we're resuming after a timeout
        logger.info(
            f"[TIMEOUT CHECK] Starting timeout detection for run={run_id}, step={step_name}"
        )

        # Check if a checkpoint exists for this wait step
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL(
                    "SELECT 1 FROM {schema}.{table} "
                    "WHERE task_id = %(task_id)s AND checkpoint_name = %(step_name)s LIMIT 1"
                ).format(
                    schema=sql.Identifier("absurd"),
                    table=sql.Identifier(f"c_{self.queue_name}"),
                ),
                {"task_id": task_id, "step_name": step_name},
            )
            checkpoint_exists = cur.fetchone() is not None

        logger.info(f"[TIMEOUT CHECK] Checkpoint exists: {checkpoint_exists}")

        # Check if wait registration exists
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL(
                    "SELECT 1 FROM {schema}.{table} "
                    "WHERE run_id = %(run_id)s AND step_name = %(step_name)s LIMIT 1"
                ).format(
                    schema=sql.Identifier("absurd"),
                    table=sql.Identifier(f"w_{self.queue_name}"),
                ),
                {"run_id": run_id, "step_name": step_name},
            )
            wait_exists = cur.fetchone() is not None

        logger.info(f"[TIMEOUT CHECK] Wait registration exists: {wait_exists}")

        if checkpoint_exists and not wait_exists:
            # Checkpoint exists but wait registration doesn't
            # → Absurd deleted it due to timeout (wait_cleanup CTE) → raise TimeoutError
            logger.warning(
                f"[TIMEOUT CHECK] TIMEOUT DETECTED! Raising TimeoutError for event '{event_name}' (run={run_id}, step={step_name})"
            )
            raise TimeoutError(
                f"Timeout waiting for event '{event_name}' after {timeout_seconds} seconds"
            )

        logger.info("[TIMEOUT CHECK] No timeout detected, proceeding to register wait")

        # First time waiting: Create checkpoint to mark that we've started waiting
        # This allows timeout detection on resume (checkpoint exists + no wait = timeout)
        if not checkpoint_exists:
            logger.info(f"Creating checkpoint for wait step: {step_name}")
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL(
                        "INSERT INTO {schema}.{table} (task_id, checkpoint_name, state, status, owner_run_id, updated_at) "
                        "VALUES (%(task_id)s, %(checkpoint_name)s, %(state)s, 'committed', %(run_id)s, %(updated_at)s) "
                        "ON CONFLICT (task_id, checkpoint_name) DO NOTHING"
                    ).format(
                        schema=sql.Identifier("absurd"),
                        table=sql.Identifier(f"c_{self.queue_name}"),
                    ),
                    {
                        "task_id": task_id,
                        "checkpoint_name": step_name,
                        "state": json.dumps(
                            {"event_name": event_name, "timeout_seconds": timeout_seconds}
                        ),
                        "run_id": run_id,
                        "updated_at": datetime.now(timezone.utc),
                    },
                )
            logger.info(f"Checkpoint created for wait step: {step_name}")

        timeout_at = datetime.now(timezone.utc) + timedelta(seconds=timeout_seconds)

        # Register wait in wait_registrations table
        # SECURITY FIX: Use sql.Identifier to prevent SQL injection
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL(
                    "INSERT INTO {schema}.{table} "
                    "(task_id, run_id, step_name, event_name, timeout_at) "
                    "VALUES (%(task_id)s, %(run_id)s, %(step_name)s, %(event_name)s, %(timeout_at)s)"
                ).format(
                    schema=sql.Identifier("absurd"),
                    table=sql.Identifier(f"w_{self.queue_name}"),
                ),
                {
                    "task_id": task_id,
                    "run_id": run_id,
                    "step_name": step_name,
                    "event_name": event_name,
                    "timeout_at": timeout_at,
                },
            )

        # Raise exception so orchestrator can mark run as SLEEPING
        # The orchestrator holds the run row lock, so we can't update it here
        msg = f"Run {run_id} sleeping, waiting for event '{event_name}'"
        raise AbsurdSleepError(
            msg,
            run_id=run_id,
            event_name=event_name,
        )

    def set_run_sleeping(
        self, conn: psycopg.Connection, run_id: uuid.UUID, event_name: str
    ) -> None:
        """Mark a run as SLEEPING waiting for an event.

        Called by orchestrator after catching AbsurdSleepException.

        CRITICAL: Must update available_at to timeout_at from wait registration
        to prevent sleeping runs from being immediately re-claimed!
        """
        # SECURITY FIX: Use sql.Identifier to prevent SQL injection
        # Get timeout_at from wait registration and use it to set available_at
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL(
                    "UPDATE {schema}.{runs_table} r "
                    "SET state = 'sleeping', "
                    "    wake_event = %(event_name)s, "
                    "    available_at = COALESCE("
                    "        (SELECT w.timeout_at FROM {schema}.{wait_table} w "
                    "         WHERE w.run_id = %(run_id)s LIMIT 1), "
                    "        NOW() + INTERVAL '24 hours'"  # Fallback for non-timeout waits
                    "    ) "
                    "WHERE r.run_id = %(run_id)s"
                ).format(
                    schema=sql.Identifier("absurd"),
                    runs_table=sql.Identifier(f"r_{self.queue_name}"),
                    wait_table=sql.Identifier(f"w_{self.queue_name}"),
                ),
                {"event_name": event_name, "run_id": run_id},
            )
        logger.debug(f"Run {run_id} marked as SLEEPING, waiting for '{event_name}'")

    def emit_event(
        self,
        conn: psycopg.Connection,
        event_name: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Emit an event and wake any runs waiting for it.

        This implements the Absurd waker pattern:
        1. Insert event into events table
        2. Find all runs waiting for this event (from wait_registrations)
        3. Wake them up by marking as available with event payload
        4. Delete wait registrations (fulfilled)
        """
        payload_dict = payload or {}

        # Insert into the events table
        # Use ON CONFLICT DO NOTHING since event_name is the primary key
        # (events can only be emitted once)
        # SECURITY FIX: Use sql.Identifier to prevent SQL injection
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL(
                    "INSERT INTO {schema}.{table} (event_name, payload, emitted_at) "
                    "VALUES (%(event_name)s, CAST(%(payload)s AS jsonb), %(emitted_at)s) "
                    "ON CONFLICT (event_name) DO NOTHING"
                ).format(
                    schema=sql.Identifier("absurd"),
                    table=sql.Identifier(f"e_{self.queue_name}"),
                ),
                {
                    "event_name": event_name,
                    "payload": json.dumps(payload_dict),  # Convert to JSON string for CAST
                    "emitted_at": datetime.now(timezone.utc),
                },
            )

        logger.debug(f"Event '{event_name}' emitted")

        # Find all runs waiting for this event
        # SECURITY FIX: Use sql.Identifier to prevent SQL injection
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL(
                    "SELECT DISTINCT run_id FROM {schema}.{table} WHERE event_name = %(event_name)s"
                ).format(
                    schema=sql.Identifier("absurd"),
                    table=sql.Identifier(f"w_{self.queue_name}"),
                ),
                {"event_name": event_name},
            )
            waiting_runs = cur.fetchall()

        if waiting_runs:
            logger.debug(f"Waking {len(waiting_runs)} run(s) for event '{event_name}'")

            # Wake each run by marking as available with event payload
            # SECURITY FIX: Use sql.Identifier to prevent SQL injection
            for (run_id_val,) in waiting_runs:
                with conn.cursor() as cur:
                    cur.execute(
                        sql.SQL(
                            "UPDATE {schema}.{table} "
                            "SET state = 'pending', "
                            "    available_at = %(now)s, "
                            "    wake_event = %(event_name)s, "
                            "    event_payload = CAST(%(payload)s AS jsonb) "
                            "WHERE run_id = %(run_id)s AND state = 'sleeping'"
                        ).format(
                            schema=sql.Identifier("absurd"),
                            table=sql.Identifier(f"r_{self.queue_name}"),
                        ),
                        {
                            "now": datetime.now(timezone.utc),
                            "event_name": event_name,
                            "payload": json.dumps(payload_dict),
                            "run_id": run_id_val,
                        },
                    )

            # Delete fulfilled wait registrations
            # SECURITY FIX: Use sql.Identifier to prevent SQL injection
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL(
                        "DELETE FROM {schema}.{table} WHERE event_name = %(event_name)s"
                    ).format(
                        schema=sql.Identifier("absurd"),
                        table=sql.Identifier(f"w_{self.queue_name}"),
                    ),
                    {"event_name": event_name},
                )

    def get_run_checkpoint(
        self, conn: psycopg.Connection, run_id: uuid.UUID, step_name: str
    ) -> Any:
        """Get a specific checkpoint for a run."""
        checkpoints = self.get_checkpoints_for_run(conn, run_id)
        return checkpoints.get(step_name)

    # =========================================================================
    # Workflow Run Tracking Methods (Phase 10)
    # =========================================================================

    def create_workflow_run(
        self,
        conn: psycopg.Connection,
        workflow_name: str,
        workflow_version: str,
        inputs: dict[str, Any] | None = None,
        absurd_run_id: uuid.UUID | None = None,
        created_by: str | None = None,
        tags: dict[str, Any] | None = None,
        workflow_hash: str | None = None,
    ) -> uuid.UUID:
        """Create a new workflow_run record to track workflow execution.

        Args:
            conn: Database connection (transaction-aware)
            workflow_name: Logical workflow name (must match ``^[a-z][a-z0-9_]*$``, no '__')
            workflow_version: Workflow version (must match ``^[a-zA-Z0-9._-]+$``, no '__')
            inputs: Workflow input parameters
            absurd_run_id: Optional root Absurd run_id
            created_by: Optional user/system identifier
            tags: Optional key-value tags for filtering
            workflow_hash: Optional SHA-256 hash of workflow definition

        Returns:
            workflow_run_id: UUID of the created workflow_run record
        """
        if "__" in workflow_name or "__" in workflow_version:
            msg = "Workflow name/version cannot contain '__' (reserved separator)"
            raise ValueError(msg)

        workflow_run_id = uuid.uuid4()

        logger.info(
            f"Creating workflow_run: {workflow_name} v{workflow_version} (id={workflow_run_id})"
        )

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO workflow_run (
                    workflow_run_id, workflow_name, workflow_version, workflow_hash,
                    status, absurd_run_id, absurd_queue, inputs, created_by, tags
                ) VALUES (
                    %(workflow_run_id)s, %(workflow_name)s, %(workflow_version)s, %(workflow_hash)s,
                    'pending', %(absurd_run_id)s, %(queue_name)s, %(inputs)s, %(created_by)s, %(tags)s
                )
                """,
                {
                    "workflow_run_id": workflow_run_id,
                    "workflow_name": workflow_name,
                    "workflow_version": workflow_version,
                    "workflow_hash": workflow_hash,
                    "absurd_run_id": absurd_run_id,
                    "queue_name": self.queue_name,
                    "inputs": json.dumps(inputs) if inputs else None,
                    "created_by": created_by,
                    "tags": json.dumps(tags) if tags else None,
                },
            )

        logger.debug(f"Created workflow_run: {workflow_run_id}")
        return workflow_run_id

    def update_workflow_run_status(
        self,
        conn: psycopg.Connection,
        workflow_run_id: uuid.UUID,
        status: str,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        task_count: int | None = None,
    ) -> None:
        """Update workflow_run status and metadata.

        Args:
            conn: Database connection
            workflow_run_id: UUID of workflow_run to update
            status: New status (pending, running, completed, failed, cancelled)
            result: Optional final result
            error: Optional error details
            started_at: Optional start timestamp
            completed_at: Optional completion timestamp
            task_count: Optional task count
        """
        logger.debug(f"Updating workflow_run {workflow_run_id} to '{status}'")

        update_fields = ["status = %(status)s"]
        params: dict[str, Any] = {"workflow_run_id": workflow_run_id, "status": status}

        if result is not None:
            update_fields.append("result = %(result)s")
            params["result"] = json.dumps(result)
        if error is not None:
            update_fields.append("error = %(error)s")
            params["error"] = json.dumps(error)
        if started_at is not None:
            update_fields.append("started_at = %(started_at)s")
            params["started_at"] = started_at
        if completed_at is not None:
            update_fields.append("completed_at = %(completed_at)s")
            params["completed_at"] = completed_at
        if task_count is not None:
            update_fields.append("task_count = %(task_count)s")
            params["task_count"] = task_count

        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE workflow_run SET {', '.join(update_fields)} "
                f"WHERE workflow_run_id = %(workflow_run_id)s",
                params,
            )
            if cur.rowcount == 0:
                logger.warning(f"No workflow_run found: {workflow_run_id}")

        logger.info(f"Updated workflow_run {workflow_run_id} to '{status}'")


# Convenience functions for common patterns
def spawn_retry_task(
    client: AbsurdClient,
    conn: psycopg.Connection,
    task_name: str,
    params: dict[str, Any],
    max_attempts: int = 3,
    retry_kind: str = "exponential",
    base_seconds: int = 30,
    factor: float = 2.0,
    max_seconds: int | None = None,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Spawn a task with retry strategy."""
    retry_strategy = {
        "kind": retry_kind,
        "base_seconds": base_seconds,
        "factor": factor,
    }

    if max_seconds:
        retry_strategy["max_seconds"] = max_seconds

    return client.spawn_task(
        conn=conn,
        task_name=task_name,
        params=params,
        max_attempts=max_attempts,
        retry_strategy=retry_strategy,
    )


def spawn_cancellable_task(
    client: AbsurdClient,
    conn: psycopg.Connection,
    task_name: str,
    params: dict[str, Any],
    max_delay_seconds: int | None = None,
    max_duration_seconds: int | None = None,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Spawn a task with cancellation rules."""
    cancellation = {}

    if max_delay_seconds:
        cancellation["max_delay"] = max_delay_seconds

    if max_duration_seconds:
        cancellation["max_duration"] = max_duration_seconds

    return client.spawn_task(
        conn=conn,
        task_name=task_name,
        params=params,
        cancellation=cancellation,
    )


# Singleton instance
_absurd_client_singleton: AbsurdClient | None = None


def get_absurd_client(
    queue_name: str | None = None,
    worker_id: str | None = None,
) -> AbsurdClient:
    """Get the singleton AbsurdClient instance.

    Args:
        queue_name: Optional queue name (only used on first call)
        worker_id: Optional worker ID (only used on first call)

    Returns:
        Shared AbsurdClient instance
    """
    global _absurd_client_singleton  # noqa: PLW0603

    if _absurd_client_singleton is None:
        _absurd_client_singleton = AbsurdClient(
            queue_name=queue_name,
            worker_id=worker_id,
        )
        logger.info(
            f"Created AbsurdClient singleton with queue '{_absurd_client_singleton.queue_name}' "
            f"and worker '{_absurd_client_singleton.worker_id}'",
        )

    return _absurd_client_singleton
