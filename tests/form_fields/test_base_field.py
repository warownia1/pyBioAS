from nose.tools import assert_equal, raises, assert_is_none, assert_true, \
    assert_false, assert_list_equal
from werkzeug.datastructures import MultiDict

from slivka.server.forms.fields import BaseField, ValidationError


class BaseFieldStub(BaseField):
    def run_validation(self, value):
        value = super().run_validation(value)
        if value == 'FAIL':
            raise ValidationError("MESSAGE", 'code')
        return value


def test_field_name():
    field = BaseField('foobar')
    assert_equal(field.name, 'foobar')


def test_field_description():
    field = BaseField('name', description='example description')
    assert_equal(field.description, 'example description')


def test_get_value_from_data():
    field = BaseField('myfield')
    data = MultiDict({
        'alpha': 1,
        'beta': -0.53,
        'myfield': 'myvalue',
        'gamma': 'foobar'
    })
    assert_equal(field.fetch_value(data, {}), 'myvalue')


def test_get_missing_value_from_data():
    field = BaseField('myfield')
    data = MultiDict({
        'alpha': 1,
        'beta': -0.53,
        'gamma': 'foobar'
    })
    assert_is_none(field.fetch_value(data, {}))


def test_validate_valid_value():
    field = BaseFieldStub('name')
    assert_equal(field.validate('value'), 'value')


@raises(ValidationError)
def test_validate_invalid_value():
    field = BaseFieldStub('name')
    field.validate('FAIL')


@raises(ValidationError)
def test_validate_missing_required_value():
    field = BaseFieldStub('name')
    field.validate(None)


def test_validate_missing_not_required_value():
    field = BaseFieldStub('name', required=False)
    assert_is_none(field.validate(None))
    assert_is_none(field.validate(''))


def test_validate_with_default_value():
    field = BaseFieldStub('name', default='value')
    assert_equal(field.validate(None), None)
    assert_equal(field.validate('other value'), 'other value')


def test_int_to_cmd_parameter():
    field = BaseField('myfield')
    assert_equal(field.to_cmd_parameter(1), 1)


def test_str_to_cmd_parameter():
    field = BaseField('myfield')
    assert_equal(field.to_cmd_parameter('foo'), 'foo')


def test_none_to_cmd_parameter():
    field = BaseField('myfield')
    assert_is_none(field.to_cmd_parameter(None))


def test_true_to_cmd_parameter():
    field = BaseField('myfield')
    assert_true(bool(field.to_cmd_parameter(True)))


def test_false_to_cmd_parameter():
    field = BaseField('myfield')
    assert_false(bool(field.to_cmd_parameter(False)))


def test_get_multiple_value_from_data():
    field = BaseField('name', multiple=True)
    data = MultiDict([('name', 'a'), ('name', 'b')])
    assert_list_equal(field.fetch_value(data, MultiDict()), ['a', 'b'])


def test_multiple_missing_value_from_data():
    field = BaseField('name', multiple=True)
    assert_list_equal(field.fetch_value(MultiDict(), MultiDict()), [])


def test_validate_multiple_valid_values():
    field = BaseFieldStub('name', multiple=True)
    assert_list_equal(field.validate(['foo', 'bar']), ['foo', 'bar'])


@raises(ValidationError)
def test_validate_multiple_no_values():
    field = BaseFieldStub('name', multiple=True)
    field.validate([])


def test_validate_multiple_with_default():
    field = BaseFieldStub('name', multiple=True, default='default')
    assert_equal(field.validate(None), None)
    assert_equal(field.validate([]), None)


@raises(ValidationError)
def test_validate_multiple_containing_invalid():
    field = BaseFieldStub('name', multiple=True)
    field.validate(['x', 'y', 'FAIL', 'z'])
