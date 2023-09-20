import datetime

class FBTypes():
    ID = "id"
    IDSET = "idset"
    IDSETQ = "idsetq"
    STRING = "string"
    STRINGSET = "stringset"
    STRINGSETQ = "stringsetq"
    INT = "int"
    DECIMAL = "decimal(4)"
    TIMESTAMP = "timestamp"
    BOOL = "bool"
    VARCHAR = "varchar"
    VECTOR = "vector"


class SchemarError(Exception):
    """
    Base class for schema errors
    """

class InvalidData(SchemarError):
    """
    Raised when data in the data attribute is invalid
    """

class UnhandledDataType(SchemarError):
    """
    Raised when data in the data attribute type is not handled
    """


class Schemar:
    
    def __init__(self, data=dict()):
        self.data = data

    def _get_data(self):
        return self.__data

    def _set_data(self, value):
        if not isinstance(value, dict):
            raise TypeError("data must be set to dict")
        self.__data = value

    data = property(_get_data, _set_data)

    def infer_schema(self):
        if not self.data:
            return None
        
        schema = {}
        for key, values in self.data.items():
            if not isinstance(values, list) or (isinstance(values, list) and len(values) == 0):
                raise InvalidData(f"value for all data keys must be a non-empty list")

            # list of bools
            if isinstance(values[0], bool):
                schema[key] = FBTypes.BOOL

            # list of ints
            elif isinstance(values[0], int):
                if any(value < 0 for value in values):
                    schema[key] = FBTypes.INT
                else:
                    schema[key] = FBTypes.INT

            # list of floats
            elif isinstance(values[0], float):
                schema[key] = FBTypes.DECIMAL

            # list of strs
            elif isinstance(values[0], str):
                schema[key] = FBTypes.STRING
                
            # list of lists
            elif isinstance(values[0], list):
                for value in values:
                    if len(value) > 0:
                        if isinstance(value[0], int): 
                            schema[key] = FBTypes.IDSET
                            break
                        elif isinstance(value[0], str):
                            schema[key] = FBTypes.STRINGSET
                            break
                        elif isinstance(value[0], float):
                            schema[key] = FBTypes.VECTOR + f"({len(value)})"
                            break
                        else:
                            raise UnhandledDataType()
                if not schema.get(key, None):
                    raise InvalidData("must have at least one non-empty list in value of lists")

            else:
                raise UnhandledDataType()
                

        return schema

            