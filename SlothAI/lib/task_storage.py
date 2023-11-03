from abc import ABC, abstractmethod
from typing import Dict
import datetime

from google.cloud import ndb

class AbstractTaskStore(ABC):
	@abstractmethod
	def create(cls, task_id, user_id, current_node_id, pipe_id, created_at, state, error, retries, split_status):
		pass

	@abstractmethod
	def update(cls, task_id: str, **kwargs: Dict[str, any]):
		pass

	@abstractmethod
	def fetch(cls, **kwargs: Dict[str, any]):
		pass

	@abstractmethod
	def delete_older_than(cls, hours=0, minutes=0, seconds=0):
		pass


# Create a context manager decorator for NDBTaskStore
def ndb_context_manager(func):
    def wrapper(*args, **kwargs):
        with ndb.Client().context():
            result = func(*args, **kwargs)
        return result  # Return the result outside the context
    return wrapper

class NDBTaskStore(ndb.Model):
    task_id = ndb.StringProperty()
    user_id = ndb.StringProperty()
    current_node_id = ndb.StringProperty()
    pipe_id = ndb.StringProperty()
    created_at = ndb.DateTimeProperty()
    state = ndb.StringProperty()
    error = ndb.StringProperty()
    retries = ndb.IntegerProperty()
    split_status = ndb.IntegerProperty()

    @classmethod
    def _get_kind(cls):
         return 'Task'

    @classmethod
    @ndb_context_manager
    def create(cls, task_id, user_id, current_node_id, pipe_id, created_at, state, error, retries, split_status):
        task = cls(
            task_id=task_id,
            user_id=user_id,
            current_node_id=current_node_id,
            pipe_id=pipe_id,
            created_at=created_at,
            state=state.value,
            error=error,
            retries=retries,
            split_status = split_status,
        )
        task.put()
        return task.to_dict()

    @classmethod
    @ndb_context_manager
    def delete_older_than(cls, hours=0, minutes=0, seconds=0):
        threshold = datetime.datetime.utcnow() - \
            datetime.timedelta(hours=hours, minutes=minutes, seconds=seconds)
        entities = cls.query(cls.created_at < threshold).fetch()
        if entities:
            for entity in entities:
                entity.key.delete()

    @classmethod
    @ndb_context_manager
    def fetch(cls, **kwargs):
        query_conditions = []

        if 'task_id' in kwargs:
            query_conditions.append(cls.task_id == kwargs['task_id'])
        if 'user_id' in kwargs:
            query_conditions.append(cls.user_id == kwargs['user_id'])
        if 'pipe_id' in kwargs:
            query_conditions.append(cls.pipe_id == kwargs['pipe_id'])
        if 'current_node_id' in kwargs:
            query_conditions.append(cls.current_node_id == kwargs['current_node_id'])

        if query_conditions:
            query = ndb.AND(*query_conditions)
            entities = cls.query(query).fetch()
        else:
            entities = []

        return [e.to_dict() for e in entities]

    @classmethod
    @ndb_context_manager
    def update(cls, task_id, **kwargs):
        task = cls.query(cls.task_id == task_id).get()
        if not task:
            raise Exception("task_id not found")

        if 'state' in kwargs:
            task.state = kwargs['state'].value
        if 'error' in kwargs:
            task.error = kwargs['error']
        if 'current_node_id' in kwargs:
            task.current_node_id = kwargs['current_node_id']
        if 'retries' in kwargs:
            task.retries = kwargs['retries']
        if 'split_status' in kwargs:
            task.split_status = kwargs['split_status']

        task.put()

        return task.to_dict()
