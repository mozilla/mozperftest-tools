from types import MappingProxyType
from perftestnotebook.transformer import get_transformers


class Constant(object):
    """
    A singleton class to store all constants.
    """

    __instance = None

    def __new__(cls, *args, **kw):
        if cls.__instance is None:
            cls.__instance = object.__new__(cls, *args, **kw)
        return cls.__instance

    def __init__(self):
        self.__predefined_transformers = get_transformers()

    @property
    def predefined_transformers(self):
        return MappingProxyType(self.__predefined_transformers).copy()
