import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.append(project_root)

from SlothAI.lib.util import handle_quotes

class TestSchemar(unittest.TestCase):

    def test_handle_quote(self):
        cases = [
            {
                "input": "featurebase's data",
                "output": "featurebase''s data",
            },
            {
                "input": ["featurebase's data", "other data", "other's data"],
                "output": ["featurebase''s data", "other data", "other''s data"],
            },
            {
                "input": 100,
                "output": 100,
            },
            {
                "input": [1, 2, 3],
                "output": [1, 2, 3],
            },
            {
                "input": "'featurebase's data'",
                "output": "''featurebase''s data''",
            },
            {
                "input": "featurebase''s data",
                "output": "featurebase''s data",
            },
        ]

        for case in cases:
            out = handle_quotes(case['input'])
            self.assertEqual(case['output'], out)


if __name__ == '__main__':
    unittest.main()