from SlothAI.web.models import Node
from SlothAI.lib.util import random_name
import enum

class NodeType(enum.Enum):
    EMBEDDING = "embedding"
    KEYTERM = "keyterm"
    QUESTION = "question"
    ANSWER = "answer"
    READ = "read"
    WRITE = "write"


init_nodes = [
    {
        'node_method': NodeType.EMBEDDING,
        'box_type': 't4',
        'model': 'instructor-large',
        'input_keys': [{'text': "string"}],
        'output_keys': [{'embedding': "vector", 'size': 768}],
        'template': 'text_embedding',
        'extras': ['box_type', 'model', 'template']
    },
    {
        'node_method': NodeType.EMBEDDING,
        'box_type': 't4',
        'model': 'instructor-xl',
        'input_keys': [{'text': "string"}],
        'output_keys': [{'embedding': "vector", 'size': 768}],
        'template': 'text_embedding',
        'extras': ['box_type', 'model', 'template']
    },
    {
        'node_method': NodeType.EMBEDDING,
        'box_type': 'service',
        'model': 'text-embedding-ada-002',
        'input_keys': [{'text': "string"}],
        'output_keys': [{'embedding': "vector", 'size': 1536}],
        'template': 'text_embedding',
        'extras': ['box_type', 'model', 'template']
    },
    {
        'node_method': NodeType.KEYTERM,
        'box_type': 't4',
        'model': 'sloth-extract',
        'input_keys': [{'text': "string"}],
        'output_keys': [{'keyterms': "stringset"}],
        'extras': ['model', 'box_type']
    },
    {
        'node_method': NodeType.KEYTERM,
        'box_type': 'service',
        'model': 'gpt-4',
        'input_keys': [{'text': "string"}],
        'output_keys': [{'keyterms': "stringset"}],
        'template': 'form_keyterms',
        'extras': ['box_type', 'model', 'openai_token', 'template']
    },
    {
        'node_method': NodeType.KEYTERM,
        'box_type': 'service',
        'model': 'gpt-3.5-turbo',
        'input_keys': [{'text': "string"}],
        'output_keys': [{'keyterms': "stringset"}],
        'template': 'form_keyterms',
        'extras': ['box_type', 'model', 'openai_token', 'template']
    },
    {
        'node_method': NodeType.QUESTION,
        'node_method': 'question',
        'box_type': 'service',
        'model': 'gpt-3.5-turbo',
        'input_keys': [{'text': "string", 'openai_token': "string"}],
        'output_keys': [{'question': "string"}],
        'template': 'form_question',
        'extras': ['box_type', 'model', 'openai_token', 'template']
    },
    {
        'node_method': NodeType.ANSWER,
        'box_type': 'service',
        'model': 'gpt-3.5-turbo',
        'input_keys': [{'question': "string", 'openai_token': "string"}],
        'output_keys': [{'answer': "string"}],
        'template': 'form_answer',
        'extras': ['box_type', 'model', 'openai_token', 'template']
    }
]


def initilize_nodes(uid):
    current_nodes = Node.get(uid=uid)

    if not current_nodes:
        for node in init_nodes:
            # Generate a random name with 2 characters
            name = random_name(2)

            # Create a new node and add it to the database
            extras = {}
            for extra_name in node['extras']:
                if extra_name in node:
                    extras[extra_name] = node[extra_name]
                else:
                    extras[extra_name] = None

            Node.create(
                name=name,
                uid=uid,
                extras=extras,
                input_keys=node['input_keys'],
                output_keys=node['output_keys'],
                method=node['node_method'].value
            )
