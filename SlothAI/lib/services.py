
from SlothAI.lib.tasks import Task, TaskState
from SlothAI.lib.storage import AbstractTaskStore
from SlothAI.lib.queue import AbstractTaskQueue

from typing import Dict, List

class TaskService:

    def __init__(self, task_store: AbstractTaskStore, task_queue: AbstractTaskQueue):
        self.task_store = task_store
        self.task_queue = task_queue

    def create_task(self, task: Task):
        self.task_store.create(
            task_id=task.id,
            user_id=task.user_id,
            current_node_id=task.next_node(),
            pipe_id = task.pipe_id,
            created_at=task.created_at,
            state=task.state,
            error=task.error,
            retries=task.retries,
            split_status=task.split_status
        )
        self.queue_task(task)

    def update_task(self, task_id, **kwargs):
        self.task_store.update(task_id, **kwargs)

    def fetch_tasks(self, **kwargs) -> Dict[str, any]:
        return self.task_store.fetch(**kwargs)

    def delete_older_than(self, hours=0, minutes=0, seconds=0):
        self.task_store.delete_older_than(hours=hours, minutes=minutes, seconds=seconds)

    def drop_task(self, task: Task):
        self.task_store.update(
                    task_id=task.id,
                    error=task.error,
                    retries=task.retries,
                    current_node_id=task.next_node(),
                    state=TaskState.FAILDED
                )

    def queue_task(self, task: Task):
        self.task_queue.queue(task)
        self.update_task(
			task_id=task.id,
			state=task.state,
			retries=task.retries,
			error=task.error,
			current_node_id=task.next_node(),
			split_status=task.split_status,
		)

    def retry_task(self, task: Task):
        if self._is_retriable(self, task):
            task.retries += 1
            self.queue_task(task)
        else:
            self.drop_task(task)

    def _is_retriable(self, task: Task):
        if task.retries >= 5:
            return False
        return True
    
    def is_valid_state_for_delete(self, state: str):
        '''
        at this point, we will say you cannot delete a task until it's in a
        non-running state
        '''
        if state == TaskState.CANCELED.value:
            return True
        if state == TaskState.FAILDED.value:
            return True
        if state == TaskState.COMPLETED.value:
            return True
        return False
    
    def delete_tasks_by_states(self, user_id: str = "", states: List[str]= []):
        for state in states:
            if not self.is_valid_state_for_delete(state):
                return False
        if user_id != "":
            return self.task_store.delete(states=states, user_id=user_id)
        
        return self.task_store.delete(states=states)

    def delete_task_by_id(self, task_id):
        return self.task_store.delete(task_id=task_id)