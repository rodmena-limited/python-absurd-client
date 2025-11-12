API Reference
=============

This section provides detailed documentation for all classes, methods, and functions in the Absurd client.

AbsurdClient Class
------------------

.. autoclass:: absurd_client.AbsurdClient
   :members:
   :undoc-members:
   :show-inheritance:

   .. automethod:: absurd_client.AbsurdClient.wait_for_event
   .. automethod:: absurd_client.AbsurdClient.emit_event
   .. automethod:: absurd_client.AbsurdClient.set_run_sleeping
   .. automethod:: absurd_client.AbsurdClient.schedule_task
   .. automethod:: absurd_client.AbsurdClient.cleanup_tasks
   .. automethod:: absurd_client.AbsurdClient.cleanup_events
   .. automethod:: absurd_client.AbsurdClient.get_task_status
   .. automethod:: absurd_client.AbsurdClient.get_run_status
   .. automethod:: absurd_client.AbsurdClient.get_checkpoints_for_run
   .. automethod:: absurd_client.AbsurdClient.save_checkpoint_for_run
   .. automethod:: absurd_client.AbsurdClient.get_run_checkpoint
   .. automethod:: absurd_client.AbsurdClient.sleep
   .. automethod:: absurd_client.AbsurdClient.extend_claim
   .. automethod:: absurd_client.AbsurdClient.cancel_task
   .. automethod:: absurd_client.AbsurdClient.await_event

Exception Classes
-----------------

.. autoclass:: absurd_client.AbsurdSleepError
   :members:
   :undoc-members:
   :show-inheritance:

Helper Functions
----------------

.. autofunction:: absurd_client.spawn_retry_task

.. autofunction:: absurd_client.spawn_cancellable_task

.. autofunction:: absurd_client.get_absurd_client