"""
database.py provides function to interact with FeatureBase cloud. It wraps the
featurebase client library.
"""

import config
import featurebase
from urllib.error import HTTPError, URLError, ContentTooShortError

###############
# FeatureBase #
###############

def featurebase_query(document, debug=False):
	"""
    Execute a query against FeatureBase cloud and return the response and any query errors.

    Args:
    - document (dict): A dictionary containing the query information.
        - 'sql' (str): The SQL query to be executed.
        - 'dbid' (str): The database ID in FeatureBase cloud.
        - 'db_token' (str): The API key/token for authentication.

    - debug (bool, optional): If True, enables debug mode for additional logging (default is False).

    Returns:
    Tuple:
        - resp (object): The response from the Featurebase query.
        - query_error (str): Any error message from the query execution, or None if there were no errors.
    """
	sql = document.get("sql")
	dbid = document.get('dbid')
	db_token = document.get('db_token')

	fb_client = featurebase.client(
		hostport=config.featurebase_endpoint,
		database=dbid,
		apikey=db_token
	)

	if debug:
		print(f"dbid: {fb_client.database}")
		print(f"apikey: {fb_client.apikey}")
		print(f"hostport: {fb_client.hostport}")

	try:
		resp = fb_client.query(sql=sql)
		if resp.error:
			if len(sql) > 50:
				partial_query = sql[:50]
			else:
				partial_query = sql				
			return None, f"featurebase_query: {partial_query}... :{resp.error}"
		return resp, None
	except (HTTPError, URLError, ContentTooShortError)  as err:
		return None, f"featurebase_query: {err.reason}"
	except Exception as e:
		return None, f"featurebase_query: unhandled excpetion while running query"

def create_table(name, schema, auth):
	"""
    Create a table in Featurebase Cloud with the specified name and schema.

    Args:
    - name (str): The name of the table to be created.
    - schema (str): The schema definition for the table in SQL format.
    - auth (dict): A dictionary containing authentication information.
        - 'dbid' (str): The database ID in Featurebase.
        - 'db_token' (str): The API key/token for authentication.

    Returns:
    str or None: If an error occurs during table creation, it returns an error message. Otherwise, it returns None.
	"""

	_, err = featurebase_query(
		{
			"sql": f"CREATE TABLE {name} {schema};",
			"dbid": f"{auth.get('dbid')}",
			"db_token": f"{auth.get('db_token')}" 
		}
	)

	if err:
		print(f"Error creating table named {name}: {err}")
	else:
		print(f"Successfully created table `{name}` on FeatureBase Cloud.")
		
	return err

def drop_table(name, auth):
	"""
    Drop a table in Featurebase Cloud with the specified name.

    Args:
    - name (str): The name of the table to be dropped.
    - auth (dict): A dictionary containing authentication information.
        - 'dbid' (str): The database ID in Featurebase.
        - 'db_token' (str): The API key/token for authentication.

    Returns:
    str or None: If an error occurs while dropping the table, it returns an error message. Otherwise, it returns None.
	"""

	_, err = featurebase_query(
		{
			"sql": f"DROP TABLE {name};",
			"dbid": f"{auth.get('dbid')}",
			"db_token": f"{auth.get('db_token')}" 
		}
	)

	if err:
		print(f"Error dropping table {name} on FeatureBase Cloud: {err}")
	else:
		print(f"Successfully dropped table `{name}` on FeatureBase Cloud.")
		
	return err
	
def table_exists(name, auth):
	"""
    Check if a table with the given name exists in a database using a featurebase_query.

    Parameters:
    - name (str): The name of the table to check for existence.
    - auth (dict): A dictionary containing authentication information for the featurebase_query.

    Returns:
    - bool or None: If the table exists, returns True. If the table does not exist or an error occurs,
      returns False. If there's an error in the featurebase_query operation, returns None.
	"""

	resp, err = featurebase_query(
		{
			"sql": f"SHOW TABLES;",
			"dbid": f"{auth.get('dbid')}",
			"db_token": f"{auth.get('db_token')}" 
		}
	)
	if err:
		return None, err
	
	for tbl in resp.data:
		if tbl[0] == name:
			return True, None
	
	return False, None

def get_columns(table_name, auth):
	"""
    Retrieve column information for a specified table from a database using Featurebase.

    Args:
        table_name (str): The name of the table for which column information is needed.
        auth (dict): A dictionary containing authentication information for Featurebase, including:
            - 'dbid' (str): The database ID.
            - 'db_token' (str): The database access token.

    Returns:
        dict or None: A dictionary where keys are column names, and values are column data types.
            Returns None if there was an error during the retrieval process.
        
        str or None: An error message if an error occurred during the retrieval process.
            Returns None if the retrieval was successful.
	"""

	resp, err = featurebase_query(
		{
			"sql": f"SHOW COLUMNS FROM {table_name};",
			"dbid": f"{auth.get('dbid')}",
			"db_token": f"{auth.get('db_token')}" 
		}
	)
	if err:
		return None, err
	
	columns = {}
	for column in resp.data:
		columns[column[0]] = column[2]
		
	return columns, None

def add_column(table_name, column, auth):
	"""
    Add a new column to a specified table in a database using Featurebase.

    Args:
        table_name (str): The name of the table to which the column will be added.
        column (dict): A dictionary containing information about the column to be added, including:
            - 'name' (str): The name of the new column.
            - 'type' (str): The data type of the new column.
        auth (dict): A dictionary containing authentication information for Featurebase, including:
            - 'dbid' (str): The database ID.
            - 'db_token' (str): The database access token.

    Returns:
        str or None: An error message if an error occurred during the column addition process.
            Returns None if the column was added successfully.
	"""

	_, err = featurebase_query(
		{
			"sql": f"ALTER TABLE {table_name} ADD COLUMN {column['name']} {column['type']}",
			"dbid": f"{auth.get('dbid')}",
			"db_token": f"{auth.get('db_token')}" 
		}
	)
		
	return err