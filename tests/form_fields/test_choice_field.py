import math

import nose
from nose.tools import assert_equal, assert_list_equal, assert_is_none

from slivka.server.forms.fields import ChoiceField, ValidationError

CHOICES = [
    ('foo', 'FOO'),
    ('bar', 'BAR'),
    ('baz', 'BAZ'),
    ('void', None)
]


# default value
@nose.tools.raises(RuntimeError)
def test_invalid_default():
    ChoiceField('name', choices=CHOICES, default='qux')


# choice validation

class TestChoices:
    def setup(self):
        self.field = ChoiceField('name', choices=CHOICES)

    def test_valid_key(self):
        assert_equal(self.field.validate('foo'), 'foo')

    def test_valid_value(self):
        assert_equal(self.field.validate('BAZ'), 'BAZ')

    @nose.tools.raises(ValidationError)
    def test_invalid(self):
        self.field.validate('quz')


class TestNumericalChoices:
    def setup(self):
        self.field = ChoiceField('name', choices=[(1, -5), (0.33, math.pi)])

    def test_integer(self):
        assert_equal(self.field.validate(1), 1)

    def test_float(self):
        assert_equal(self.field.validate(0.33), 0.33)

    def test_long_float(self):
        assert self.field.validate(math.pi)

    @nose.tools.raises(ValidationError)
    def test_invalid(self):
        self.field.validate(0.34)


# empty value validation

@nose.tools.raises(ValidationError)
def test_validate_none():
    field = ChoiceField('name', choices=CHOICES)
    field.validate(None)


@nose.tools.raises(ValidationError)
def test_validate_empty_required():
    field = ChoiceField('name', required=True)
    field.validate(None)


def test_validate_empty_not_required():
    field = ChoiceField(ValidationError, required=False)
    assert_is_none(field.validate(None))


# validation with default

def test_validate_none_with_default():
    field = ChoiceField('name', choices=CHOICES, default='foo')
    assert_equal(field.validate(None), 'foo')


def test_validate_empty_with_default():
    field = ChoiceField('name', choices=CHOICES, default='FOO')
    assert_equal(field.validate(()), 'FOO')
    assert_equal(field.validate([]), 'FOO')


def test_valid_value_with_default():
    field = ChoiceField('name', choices=CHOICES, default='bar')
    assert_equal(field.validate('foo'), 'foo')
    assert_equal(field.validate('bar'), 'bar')


@nose.tools.raises(ValidationError)
def test_invalid_value_with_default():
    field = ChoiceField('name', choices=CHOICES, default='bar')
    field.validate('QUX')


def test_multiple_valid_values():
    field = ChoiceField('name', choices=CHOICES, multiple=True)
    assert_list_equal(
        field.validate(['foo', 'BAR']), ['foo', 'BAR']
    )


# command line parameter conversion

def test_to_cmd_parameter():
    field = ChoiceField('name', choices=CHOICES)
    assert_equal(field.to_cmd_parameter('foo'), 'FOO')
    assert_equal(field.to_cmd_parameter('BAZ'), 'BAZ')
    assert_equal(field.to_cmd_parameter('missing'), 'missing')
    assert_is_none(field.to_cmd_parameter('void'))


def test_serialize_multiple():
    field = ChoiceField('name', choices=CHOICES, multiple=True)
    assert_list_equal(
        field.serialize_value(['foo', 'BAR', 'baz']),
        ['FOO', 'BAR', 'BAZ']
    )
