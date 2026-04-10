import inspect
import types
from abc import ABC, abstractmethod

class MetaDataParseError(ValueError): pass
class InvalidMetadataType(ValueError): pass

class TypeParser(ABC):
    @abstractmethod
    def make_parse_fn(self): pass

class MetaDataHandlerMeta(type):
    def __init__(cls, name, bases, nmspc):
        handlers = {}
        for k in nmspc.keys():
            if not k.startswith('parse_') or k == 'parse_all':
                continue
            parser_key = k[len('parse_'):]
            parser = nmspc[k]
            if isinstance(parser, TypeParser):
                handlers[parser_key] = parser.make_parse_fn()
            else:
                handlers[parser_key] = parser

        # Check the signatures and remove the handler dummy values
        for k, handler in handlers.items():
            if isinstance(handler, types.FunctionType):
                sig = inspect.getargspec(handler)
                num_defaults = len(sig.defaults) if sig.defaults is not None else 0
                num_args = len(sig.args) - num_defaults
                assert num_args == 1, 'make_parse_fn must return a function that works with only 1 argument, but got {}'.format(sig)
            del nmspc['parse_'+k]
        setattr(cls, 'handlers', handlers)
        return super(MetaDataHandlerMeta, cls).__init__(name, bases, nmspc)

class BaseMetaDataHandler(metaclass=MetaDataHandlerMeta):
    def parse(self, type_, value):
        try:
            handler = self.handlers[type_]
        except KeyError as e:
            msg = '{} not supported. try one of {}'.format(type_, list(self.handlers.keys()))
            raise InvalidMetadataType(msg)
        try:
            return handler(value)
        except Exception as e:
            raise MetaDataParseError('Cannot parse {} as type {}'.format(value, type_)) from e

    def parse_all(self, specs, values):
        if len(specs) != len(values):
            err_frmt = 'Types and values must be same length but were {} and {}'
            raise MetaDataParseError(err_frmt.format(len(specs), len(values)))
        meta = {}
        for spec, value in zip(specs, values):
            if ':' in spec:
                k, type_ = spec.split(':')
                parsed_value = self.parse(type_, value)
            else:
                k, parsed_value = spec, value
            if isinstance(parsed_value, dict):
                meta.update(parsed_value)
            else:
                meta[k] = parsed_value
        return meta
        
class SimpleMetaDataHandler(BaseMetaDataHandler):
    parse_str = str
    parse_int = int
    parse_float = float
