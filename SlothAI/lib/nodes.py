import enum
import os

from SlothAI.web.models import Node, Template
from SlothAI.lib.util import random_name

from flask import current_app

class NodeType(enum.Enum):
    EMBEDDING = "embedding"
    KEYTERMS = "keyterms"
    READ = "read"
    WRITE = "write"
    DATA_SOURCE = "datasource"
    # QUESTION = "question"
    # ANSWER = "answer"

init_nodes = [
    {
        'type': NodeType.DATA_SOURCE,
        'input_keys': [{'name': "data", 'type': "object"}],
        'output_keys': [{'name': "data", 'type': "object"}],
        'model': 'endpoint',
        'extras': {}
    },
    {
        'type': NodeType.EMBEDDING,
        'input_keys': [{'name': "data.text", 'type': "string"}],
        'output_keys': [{'name': "data.embedding", 'type': "vector", 'size': 768}],
        'model': 'instructor-large',
        'extras': {
            'box_type': 't4',
            'template': 'text_embedding',
        }
    },
    {
        'type': NodeType.EMBEDDING,
        'input_keys': [{'name': "text", 'type': "string"}],
        'output_keys': [{'name': "embedding", 'type': "vector", 'size': 768}],
        'model': 'instructor-xl',
        'extras': {
            'box_type': 't4',
            'template': 'text_embedding',
        }
    },
    {
        'type': NodeType.EMBEDDING,
        'input_keys': [{'name': "text", 'type': "string"}],
        'output_keys': [{'name': "embedding", 'type': "vector", 'size': 1536}],
        'model': 'text-embedding-ada-002',
        'extras': {
            'box_type': 'service',
            'template': 'text_embedding',
            'openai_token': True
        }    
    },
    {
        'type': NodeType.KEYTERMS,
        'input_keys': [{'name': "text", 'type': "string"}],
        'output_keys': [{'name': "keyterms", 'type': "stringset"}],
        'model': 'sloth-extract',
        'extras': {
            'box_type': 't4',
        },
    },
    {
        'type': NodeType.KEYTERMS,
        'input_keys': [{'name': "text", 'type': "string"}],
        'output_keys': [{'name': "keyterms", 'type': "stringset"}],
        'model': 'gpt-4',
        'extras': {
            'box_type': 'service',
            'template': 'form_keyterms',
            'openai_token': True,
        },
    },
    {
        'type': NodeType.KEYTERMS,
        'input_keys': [{'name': "text", 'type': "string"}],
        'output_keys': [{'name': "keyterms", 'type': "stringset"}],
        'model': 'gpt-3.5-turbo',
        'extras': {
            'box_type': 'service',
            'template': 'form_keyterms',
            'openai_token': True,
        },  
    },
    {
        'type': NodeType.WRITE,
        'model': 'featurebase',
        'input_keys': [{'name': "data", 'type': "object"}],
        'output_keys': [],
        'extras': {
            'database_id': True,
            'x-api-token': True,
        }, 
    },
    {
        'type': NodeType.READ,
        'input_keys': [{'name': 'sql', 'type': 'string'}],
        'output_keys': [],
        'model': 'featurebase',
        'extras': {
            'database_id': True,
            'x-api-token': True,
        }, 
    },
    # {
    #     'type': NodeType.QUESTION,
    #     'box_type': 'service',
    #     'model': 'gpt-3.5-turbo',
    #     'input_keys': [{'name': "text", 'type': "string"}],
    #     'output_keys': [{'name': "keyterms", 'type': "stringset"}],
    #     'template': 'form_question',
    #     'extras': ['box_type', 'model', 'openai_token', 'template']
    # },
    # {
    #     'type': NodeType.ANSWER,
    #     'box_type': 'service',
    #     'model': 'gpt-3.5-turbo',
    #     'input_keys': [{'name': "text", 'type': "string"}],
    #     'output_keys': [{'name': "keyterms", 'type': "stringset"}],
    #     'template': 'form_answer',
    #     'extras': ['box_type', 'model', 'openai_token', 'template']
    # },
]


def initilize_nodes(uid):
    current_nodes = Node.get(uid=uid)

    if not current_nodes:
        for node in init_nodes:
            # check the template
            template_name = node.get('extras').get('template')
            if template_name:
                template = Template.get(uid=uid, name=template_name)

                if not template:
                    import os
                    file_name = "%s.txt" % template_name
                    file_path = os.path.join(current_app.root_path, 'templates', 'prompts', file_name)
                    try:
                        with open(file_path, 'r') as file:
                            text = file.read()
                    except FileNotFoundError:
                        print("File not found.")
                        text = ""

                    template = Template.create(
                        name=template_name,
                        uid=uid,
                        text=text 
                    )

                node.get('extras')['template_id'] = template.get('template_id')
                node.get('extras').pop('template', None)

            Node.create(
                uid=uid,
                name=random_name(2),
                type=node['type'].value,
                extras=node.get('extras'),
                input_keys=node['input_keys'],
                output_keys=node['output_keys'],
                model = node['model']
            )
