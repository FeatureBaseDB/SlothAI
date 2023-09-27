import unittest

# Import the modify_sql_query function from your code
from database import add_filters_to_sql

class TestAddFiltersToSql(unittest.TestCase):

    tests = [
        {
            "name": "test_add_where_clause",
            "original_sql_query": "SELECT * FROM my_table",
            "column_value_dict": {"column1": [1, 2, 3]},
            "expected_query": "SELECT * FROM my_table WHERE column1 IN (1, 2, 3)",
        },
        {
            "name": "test_append_to_existing_where_clause",
            "original_sql_query": "SELECT * FROM my_table WHERE category = 'A'",
            "column_value_dict": {"column1": [1, 2, 3]},
            "expected_query": "SELECT * FROM my_table WHERE column1 IN (1, 2, 3) AND category = 'A'",
        },
        {
            "name": "test_multiple_columns",
            "original_sql_query": "SELECT * FROM my_table WHERE category = 'A'",
            "column_value_dict": {
                "column1": [1, 2, 3],
                "column2": ["X", "Y"],
            },
            "expected_query": "SELECT * FROM my_table WHERE column1 IN (1, 2, 3) AND column2 IN ('X', 'Y') AND category = 'A'",
        },
        {
            "name": "test_append_to_existing_where_with_additional_clause",
            "original_sql_query": "SELECT * FROM my_table WHERE category = 'A' ORDER BY column3 DESC",
            "column_value_dict": {"column1": [1, 2, 3]},
            "expected_query": "SELECT * FROM my_table WHERE column1 IN (1, 2, 3) AND category = 'A' ORDER BY column3 DESC",
        },
    ]

    def test_add_filters_to_sql(self):
        for test in self.tests:
            modified_sql_query = add_filters_to_sql(test['original_sql_query'], test['column_value_dict'])
            self.assertEqual(modified_sql_query, test['expected_query'], f"test {test['name']} failed")

if __name__ == "__main__":
    unittest.main()
