import unittest
from schemar import FBTypes, Schemar, InvalidData, UnhandledDataType

class TestSchemar(unittest.TestCase):

    def test_set_data(self):
        """
        data must be set to a dict and will raise an exception otherwise.
        testing that here.
        """
        cases = [
            {
                "target": {"some": "good data"},
            },
            {
                "target": None,
                "exception_type": TypeError,
                "exception_str": "data must be set to dict"
            },
            {
                "target": 10,
                "exception_type": TypeError,
                "exception_str": "data must be set to dict"
            },
            {
                "target": "string",
                "exception_type": TypeError,
                "exception_str": "data must be set to dict"
            }
        ]

        for case in cases:
            schemar = Schemar()
            if not case.get('exception_type', None):
                schemar.data = case['target']
            else:
                with self.assertRaises(case['exception_type']) as cm:
                    schemar.data = case['target']
                self.assertEqual(str(cm.exception), str(case['exception_str']))

    def test_infer_schema(self):
        cases = [
            {
                "input": {
                    "str_attr": ["this is some test", "this is some text"],
                    "str_list_attr": [["list of test", "list of text"], ["list of text", "list of text"]],
                    "int_attr": [1, 2],
                    "int_list_attr": [[1, 2], [1, 2]],
                    "float_attr": [1.253, 1.256],
                    "bool_attr": [True, False],
                    "vect_attr": [[0.1565, 0.45654], [0.5465, 0.05654]],
                    "str_list_attr_empty": [[], ["some", "data"]],
                    "int_list_attr_empty": [[], [0, 1]],
                    "vec_list_attr_empty": [[], [0.5456, 1.5456, 5.456465, 0.04564]]
                },
                "output": {
                    "str_attr": FBTypes.STRING,
                    "str_list_attr": FBTypes.STRINGSET,
                    "int_attr": FBTypes.INT,
                    "int_list_attr": FBTypes.IDSET,
                    "float_attr": FBTypes.DECIMAL,
                    "bool_attr": FBTypes.BOOL,
                    "vect_attr": FBTypes.VECTOR + "(2)",
                    "str_list_attr_empty": FBTypes.STRINGSET,
                    "int_list_attr_empty": FBTypes.IDSET,
                    "vec_list_attr_empty": FBTypes.VECTOR + "(4)"
                }
            },
            {
                "input": {
                    "str": "str"
                },
                "exception_type": InvalidData,
                "exception_str": "value for all data keys must be a non-empty list"
            },
            {
                "input": {
                    "str": None
                },
                "exception_type": InvalidData,
                "exception_str": "value for all data keys must be a non-empty list"
            },
            {
                "input": {
                    "str": []
                },
                "exception_type": InvalidData,
                "exception_str": "value for all data keys must be a non-empty list"
            },
            {
                "input": {
                    "str": [[]]
                },
                "exception_type": InvalidData,
                "exception_str": "must have at least one non-empty list in value of lists"
            },
            {
                "input": {
                    "str": [{}]
                },
                "exception_type": UnhandledDataType,
                "exception_str": ""
            },
            {
                "input": {
                    "str": [set()]
                },
                "exception_type": UnhandledDataType,
                "exception_str": ""
            },
            {
                "input": {
                    "str": [None]
                },
                "exception_type": UnhandledDataType,
                "exception_str": ""
            },
            {
                "input": {
                    "str": [[{}]]
                },
                "exception_type": UnhandledDataType,
                "exception_str": ""
            }
        ]

        schemar = Schemar()
        for case in cases:
            if not case.get('exception_type', None):
                schemar.data = case['input']
                self.assertDictEqual(schemar.infer_schema(), case['output'])
            else:
                with self.assertRaises(case['exception_type']) as cm:
                    schemar.data = case['input']
                    schemar.infer_schema()
                self.assertEqual(str(cm.exception), str(case['exception_str']))

if __name__ == '__main__':
    unittest.main()