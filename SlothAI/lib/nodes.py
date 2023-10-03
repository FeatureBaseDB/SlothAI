nodes = [
    {
        'node_method': 'embedding',
        'box_type': 't4',
        'model': 'instructor-large',
        'input_keys': [{'text': "string"}],
        'output_keys': [{'embedding': "vector", 'size': 768}],
        'template': 'text_embedding',
        'extras': ['box_type', 'model', 'template']
    },
    {
        'node_method': 'embedding',
        'box_type': 't4',
        'model': 'instructor-xl',
        'input_keys': [{'text': "string"}],
        'output_keys': [{'embedding': "vector", 'size': 768}],
        'template': 'text_embedding',
        'extras': ['box_type', 'model', 'template']
    },
    {
        'node_method': 'embedding',
        'box_type': 'service',
        'model': 'text-embedding-ada-002',
        'input_keys': [{'text': "string"}],
        'output_keys': [{'embedding': "vector", 'size': 1536}],
        'template': 'text_embedding',
        'extras': ['box_type', 'model', 'template']
    },
    {
        'node_method': 'keyterm',
        'box_type': 't4',
        'model': 'sloth-extract',
        'input_keys': [{'text': "string"}],
        'output_keys': [{'keyterms': "stringset"}],
        'extras': ['model', 'box_type']
    },
    {
        'node_method': 'keyterm',
        'box_type': 'service',
        'model': 'gpt-4',
        'input_keys': [{'text': "string"}],
        'output_keys': [{'keyterms': "stringset"}],
        'template': 'form_keyterms',
        'extras': ['box_type', 'model', 'openai_token', 'template']
    },
    {
        'node_method': 'keyterm',
        'box_type': 'service',
        'model': 'gpt-3.5-turbo',
        'input_keys': [{'question': "string"}],
        'output_keys': [{'answer': "string"}],
        'template': 'form_answer',
        'extras': ['box_type', 'model', 'openai_token', 'template']
    },
    {
        'node_method': 'question',
        'box_type': 'service',
        'model': 'gpt-3.5-turbo',
        'input_keys': [{'text': "string", 'openai_token': "string"}],
        'output_keys': [{'question': "string"}],
        'template': 'form_question',
        'extras': ['box_type', 'model', 'openai_token', 'template']
    },
    {
        'node_method': 'answer',
        'box_type': 'service',
        'model': 'gpt-3.5-turbo',
        'input_keys': [{'question': "string", 'openai_token': "string"}],
        'output_keys': [{'answer': "string"}],
        'template': 'form_answer',
        'extras': ['box_type', 'model', 'openai_token', 'template']
    }
]
