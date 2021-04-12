import itertools
import json
import typing
from collections import OrderedDict
from functools import partial
from tempfile import mkstemp

import pkg_resources
from werkzeug.datastructures import FileStorage, MultiDict

import slivka
import slivka.db
import slivka.server.forms.file_validators as validators
from slivka.utils import cached_property, class_property, expression_parser
from .file_proxy import FileProxy, _get_file_from_uuid
from .widgets import *

__all__ = [
    'BaseField',
    'IntegerField',
    'DecimalField',
    'TextField',
    'BooleanField',
    'FlagField',
    'ChoiceField',
    'FileField',
    'ValidationError'
]


def _get_schema(filename):
    return json.loads(
        pkg_resources.resource_string(
            "slivka.conf", filename
        ).decode()
    )


class BaseField:
    """ Base class for form fields providing validation and conversion

    Field objects are contained within the form and are used to
    retrieve data from the requests, validate and convent the values
    to python and convert them to strings.
    All form field classes must inherit from this class and call its
    constructor. The subclasses may override :py:meth:`run_validation`
    for custom value validation. The parameters for the fields are
    provided from the configuration file.

    :param name: the name of the field
    :param label: human readable name/label
    :param description: longer, human readable description
    :param default: default value for the field
    :param required: whether the field is required
    :param multiple: whether the field accepts multiple values
    """

    def __init__(self,
                 name,
                 label='',
                 description='',
                 default=None,
                 required=True,
                 multiple=False,
                 condition=None):
        self.name = name
        self.label = label
        self.description = description
        self.default = default
        self.required = required and default is None
        self.multiple = multiple
        self.condition = (None if condition is None
                          else expression_parser.Expression(condition))
        self._widget = None

    schema = class_property(lambda cls: {})
    """Json schema for the field item in the config file."""

    def fetch_value(self, data: MultiDict, files: MultiDict):
        """
        Retrieves value from the request data. This value will
        be further passed to the validation method. The deriving
        classes may need to override this method i.e. for file
        retrieval, see :py:method:`FileField.value_from_request_data`.

        :param data: request POST data
        :param files: request multipart-POST files
        :return: retrieved raw value
        """
        if self.multiple:
            return data.getlist(self.name)
        else:
            return data.get(self.name)

    def run_validation(self, value):
        """ Validates the value and converts to Python value.

        Checks whether the value meets the field type and constraints.
        Otherwise, raises :py:class:`ValidationError`.
        Subclasses may override this method with their implementation
        of validation, but the value should be converted with
        their superclass' :py:meth:`run_validation` method first.

        :param value: value to be validated and converted
        :return: converted value
        """
        if hasattr(value, '__len__') and len(value) == 0:
            return None
        else:
            return value

    def validate(self, value):
        """ Runs validation of the value.

        Used by form during :py:meth:`BaseForm.full_clean`to check
        and convert the data from the HTTP request.
        Performs the validation of the value obtained form
        :py:meth:`fetch_value` and returns the value
        converted to the appropriate Python type.
        It takes care of arrays by validating each value individually.

        This method is final and must not be overridden!

        :param value: the value or list of values to be validated
        :return: validated value
        :raise ValidationError: provided value is not valid
        """
        if not self.multiple:
            value = self.run_validation(value)
            if value is None and self.required:
                raise ValidationError("Field is required", 'required')
            return value
        else:
            if value is None or len(value) == 0:
                if self.required:
                    raise ValidationError("Field is required", 'required')
                else:
                    return None
            return [self.run_validation(v) for v in value]

    def _validate_default(self):
        """ Passes the default value through validation.

        It should be called at the end of `__init__` after all the
        validators and default value are set up.

        :raise RuntimeError: default value is invalid
        """
        if self.default is not None:
            try:
                self.run_validation(self.default)
            except ValidationError as e:
                raise RuntimeError("Invalid default value") from e

    def test_condition(self, values):
        if self.condition:
            return self.condition.evaluate({
                'self': values[self.name], **values
            })
        else:
            return True

    def serialize_value(self, value):
        if value is None:
            return None
        if self.multiple:
            return [self.to_cmd_parameter(val) for val in value]
        else:
            return self.to_cmd_parameter(value)

    def to_cmd_parameter(self, value):
        """ Converts the value to the command line parameter.

        The returned value should be a string that can be inserted
        into a command line argument directly.
        By default, it returns the ``value`` directly, but
        subclasses may implement different behaviour

        :param value: a value to be converted
        :return: value converted to the cmd argument
        """
        return value

    def __json__(self):
        """ Json representation of the field as shown to the client. """
        return {
            'type': 'undefined',
            'name': self.name,
            'label': self.label,
            'description': self.description or "",
            'required': self.required,
            'multiple': self.multiple,
            'default': self.default
        }

    @property
    def widget(self):
        raise NotImplementedError

    @property
    def input_tag(self):
        return self.widget.render()


class IntegerField(BaseField):
    """ Represents a field that takes an integer value.

    :param name: name of the field
    :param min: minimum value or None if unbound
    :param max: maximum value or None if unbound
    :param **kwargs: see arguments of :py:class:`BaseField`
    """
    # noinspection PyShadowingBuiltins
    def __init__(self,
                 name,
                 min=None,
                 max=None,
                 **kwargs):
        super().__init__(name, **kwargs)
        self.__validators = []
        self.min = min
        self.max = max
        if max is not None:
            self.__validators.append(partial(_max_value_validator, max))
        if min is not None:
            self.__validators.append(partial(_min_value_validator, min))
        self._validate_default()

    schema = class_property(lambda cls: _get_schema('int-field-schema.json'))

    @property
    def widget(self):
        if self._widget is None:
            widget = NumberInputWidget(self.name)
            widget['min'] = self.min
            widget['max'] = self.max
            widget['step'] = 1
            widget['value'] = self.default
            widget['required'] = self.required
            self._widget = widget
        return self._widget

    def run_validation(self, value):
        value = super().run_validation(value)
        if value is None:
            return None
        try:
            value = int(value)
        except (ValueError, TypeError):
            raise ValidationError("Invalid integer value", 'invalid')
        for validator in self.__validators:
            validator(value)
        return value

    def __json__(self):
        j = super().__json__()
        j['type'] = 'integer'
        if self.min is not None: j['min'] = self.min
        if self.max is not None: j['max'] = self.max
        return j


class DecimalField(BaseField):
    """ Represents a field that takes a floating point number.

    :param name: name of the field
    :param min: minimum value or None if unbound
    :param max: maximum value or None if unbound
    :param min_exclusive: whether min is excluded, default False
    :param max_exclusive: whether max is excluded, default False
    :param **kwargs: see arguments of :py:class`BaseClass`
    """
    # noinspection PyShadowingBuiltins
    def __init__(self,
                 name,
                 min=None,
                 max=None,
                 min_exclusive=False,
                 max_exclusive=False,
                 **kwargs):
        super().__init__(name, **kwargs)
        self.__validators = []
        self.min = min
        self.max = max
        self.min_exclusive = min_exclusive
        self.max_exclusive = max_exclusive
        if max is not None:
            validator = (_exclusive_max_value_validator
                         if max_exclusive else _max_value_validator)
            self.__validators.append(partial(validator, max))
        if min is not None:
            validator = (_exclusive_min_value_validator
                         if min_exclusive else _min_value_validator)
            self.__validators.append(partial(validator, min))
        self._validate_default()

    schema = class_property(lambda cls: _get_schema('decimal-field-schema.json'))

    @property
    def widget(self):
        if self._widget is None:
            widget = NumberInputWidget(self.name)
            widget['min'] = self.min
            widget['max'] = self.max
            widget['step'] = 'any'
            widget['value'] = self.default
            widget['required'] = self.required
            self._widget = widget
        return self._widget

    def run_validation(self, value):
        value = super().run_validation(value)
        if value is None:
            return None
        try:
            value = float(value)
        except (ValueError, TypeError):
            raise ValidationError("Invalid decimal number", 'invalid')
        for validator in self.__validators:
            validator(value)
        return value

    def __json__(self):
        j = super().__json__()
        j['type'] = 'decimal'
        if self.max is not None: j['max'] = self.max
        if self.min is not None: j['min'] = self.min
        if self.min_exclusive is not None: j['minExclusive'] = self.min_exclusive
        if self.max_exclusive is not None: j['maxExclusive'] = self.max_exclusive
        return j


class TextField(BaseField):
    """ Represents a field taking an text value.

    :param name: name of the field
    :param min_length: minimum length of text
    :param max_length: maximum length of text
    :param **kwargs: see arguments of :py:class:`BaseField`
    """
    def __init__(self,
                 name,
                 min_length=None,
                 max_length=None,
                 **kwargs):
        super().__init__(name, **kwargs)
        self.__validators = []
        self.min_length = min_length
        self.max_length = max_length
        if min_length is not None:
            self.__validators.append(partial(
                _min_length_validator, min_length
            ))
        if max_length is not None:
            self.__validators.append(partial(
                _max_length_validator, max_length
            ))
        self._validate_default()

    schema = class_property(lambda cls: _get_schema('text-field-schema.json'))

    @property
    def widget(self):
        if self._widget is None:
            self._widget = TextInputWidget(self.name)
            self._widget['value'] = self.default
            self._widget['required'] = self.required
        return self._widget

    def run_validation(self, value):
        value = super().run_validation(value)
        if value is None:
            return None
        value = str(value)
        for validator in self.__validators:
            validator(value)
        return value

    def __json__(self):
        j = super().__json__()
        j['type'] = 'text'
        if self.min_length is not None: j['minLength'] = self.min_length
        if self.max_length is not None: j['maxLength'] = self.max_length
        return j


class BooleanField(BaseField):
    """ Represents a field taking a boolean value.

    The field interprets any string defined in a ``FALSE_STR`` set
    as well as anything that evaluates to False as False.

    :param name: field name
    :param **kwargs: see arguments of :py:class:`BaseField`
    """
    FALSE_STR = {'no', 'false', '0', 'n', 'f', 'none', 'null', 'off'}

    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self._validate_default()

    schema = class_property(lambda cls: _get_schema('boolean-field-schema.json'))

    @property
    def widget(self):
        if self._widget is None:
            self._widget = CheckboxInputWidget(self.name, value='true')
            self._widget['checked'] = bool(self.default)
            self._widget['required'] = self.required
        return self._widget

    def run_validation(self, value):
        value = super().run_validation(value)
        if isinstance(value, str) and value.lower() in self.FALSE_STR:
            value = False
        return True if value else None

    def __json__(self):
        j = super().__json__()
        j['type'] = 'boolean'
        return j


FlagField = BooleanField
""" An alias for the BooleanField """


class ChoiceField(BaseField):
    """ Represents a field taking one of the available options.

    The choices mapping is used to convert the value to the
    command line parameter.

    :param name: field name
    :param choices: a mapping of user choices to the cmd values
    :param **kwargs: see arguments of :py:class:`BaseField`
    """
    def __init__(self,
                 name,
                 choices=(),
                 **kwargs):
        super().__init__(name, **kwargs)
        self.__validators = []
        self.choices = OrderedDict(choices)
        self.__validators.append(partial(
            _choice_validator,
            list(itertools.chain(self.choices.keys(), self.choices.values()))
        ))
        self._validate_default()

    schema = class_property(lambda cls: _get_schema('choice-field-schema.json'))

    @property
    def widget(self):
        if self._widget is None:
            self._widget = SelectWidget(self.name, options=self.choices)
            self._widget['required'] = self.required
            self._widget['multiple'] = self.multiple
        return self._widget

    def run_validation(self, value):
        """
        Checks if the value is in either choices keys or values,
        validation fails otherwise
        """
        # FIXME: should also convert the value here
        value = super().run_validation(value)
        if value is None:
            return None
        if value not in self.choices.keys() and value not in self.choices.values():
            raise ValidationError(
                "Value \"%s\" is not one of the available choices." % value,
                'invalid'
            )
        return value

    def to_cmd_parameter(self, value):
        """ Converts value to the cmd argument using choices map"""
        return self.choices.get(value, value)

    def __json__(self):
        j = super().__json__()
        j['type'] = 'choice'
        j['choices'] = list(self.choices)
        return j


class FileField(BaseField):
    """ Represents a field taking a file.

    The file can be supplied as a uuid or :py:class:`werkzeug.FileStorage`.
    The values are converted to a :py:class:`FileProxy` convenience
    wrapper.

    :param name: field name
    :param media_type: accepted media (content) type; used in file
        content validation
    :param media_type_parameters: additional parameters regarding
        file content; used solely as a hint
    :param extensions: accepted file extensions; used solely as a hint
    :param **kwargs: see arguments of :py:class:`BaseField`
    """
    def __init__(self,
                 name,
                 media_type=None,
                 media_type_parameters=(),
                 extensions=(),
                 **kwargs):
        assert kwargs.get('default') is None
        super().__init__(name, **kwargs)
        self.__validators = []
        self.extensions = extensions
        self.media_type = media_type
        self.media_type_parameters = media_type_parameters or {}
        if media_type is not None:
            self.__validators.append(partial(
                _media_type_validator, media_type
            ))

    schema = class_property(lambda cls: _get_schema('file-field-schema.json'))

    save_location = cached_property(lambda self: slivka.settings.uploads_dir)

    def fetch_value(self, data: MultiDict, files: MultiDict):
        if self.multiple:
            return files.getlist(self.name) + data.getlist(self.name)
        else:
            return files.get(self.name) or data.get(self.name)

    @property
    def widget(self):
        if self._widget is None:
            widget = FileInputWidget(self.name)
            widget['accept'] = str.join(
                ',', ('.%s' % ext for ext in self.extensions)
            )
            self._widget = widget
        return self._widget

    def run_validation(self, value) -> typing.Optional['FileProxy']:
        """
        Validates and converts ``value`` to the :py:class:`FileProxy`
        object. The value can be a :py:class:`FileProxy` which will
        be returned directly, a :py:class:`werkzeug.FileStorage`
        object which will be wrapped in :py:class:`FileProxy`
        or a file id in which case a database lookup is performed
        to find the path that will be used to construct a
        :py:class:`FileProxy`.

        :param value: file from the request or file id
        :return: a wrapper around the file
        """
        value = super().run_validation(value)
        if value is None:
            return None
        elif isinstance(value, FileStorage):
            file = FileProxy(file=value)
        elif isinstance(value, str):
            file = _get_file_from_uuid(value, slivka.db.database)
            if file is None:
                raise ValidationError(
                    "A file with given uuid not found", 'not_found'
                )
        elif isinstance(value, FileProxy):
            file = value
        else:
            raise TypeError("Invalid type %s" % type(value))
        for validator in self.__validators:
            validator(file)
        return file

    def __json__(self):
        j = super().__json__()
        j['type'] = 'file'
        if self.media_type is not None:
            j['mimetype'] = self.media_type
            j['mediaType'] = self.media_type
            j['mediaTypeParameters'] = self.media_type_parameters
        if self.extensions: j['extensions'] = self.extensions
        return j

    def to_cmd_parameter(self, value: 'FileProxy'):
        """ Converts FileProxy to cmd argument.

        The file is written to teh disk if not saved already
        and its path is returned.
        """
        if not value: return None
        if value.path is None:
            (fd, path) = mkstemp(dir=self.save_location)
            with open(fd, 'wb') as fp:
                value.save_as(path=path, fp=fp)
        return value.path


# Helper methods that are used for value validation.

def _max_value_validator(limit, value):
    if value > limit:
        raise ValidationError(
            "Value must be less than or equal to %s" % limit, 'max_value'
        )


def _min_value_validator(limit, value):
    if value < limit:
        raise ValidationError(
            "Value must be greater than or equal to %s" % limit, 'min_value'
        )


def _exclusive_max_value_validator(limit, value):
    if value >= limit:
        raise ValidationError(
            "Value must be less than %s" % limit, 'max_value'
        )


def _exclusive_min_value_validator(limit, value):
    if value <= limit:
        raise ValidationError(
            "Value must be greater than %s" % limit, 'min_value'
        )


def _min_length_validator(limit, value):
    if len(value) < limit:
        raise ValidationError(
            "Value is too short. Min %d characters" % limit, 'min_length'
        )


def _max_length_validator(limit, value):
    if len(value) > limit:
        raise ValidationError(
            "Value is too long. Max %d characters" % limit, 'max_length'
        )


def _choice_validator(choices, value):
    if value not in choices:
        raise ValidationError(
            "Value \"%s\" is not one of the available choices." % value,
            'invalid'
        )


def _media_type_validator(media_type, file: FileProxy):
    file.reopen()
    if not validators.validate_file_content(file, media_type):
        raise ValidationError(
            "This media type is not accepted", 'media_type'
        )


class ValidationError(Exception):
    """ Exception raised in value validation fails. """
    def __init__(self, message, code=None):
        super().__init__(message, code)
        self.message = message
        self.code = code
