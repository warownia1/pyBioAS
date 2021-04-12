from nose.tools import assert_is_none, assert_equal, assert_list_equal, \
    assert_true, assert_false
from werkzeug.datastructures import MultiDict

from slivka.server.forms.fields import *
from slivka.server.forms.form import BaseForm


class TestCleanedValues:
    class DummyForm(BaseForm):
        field1 = IntegerField('int', min=0, max=10, default=1)
        field1a = IntegerField('int2', required=False, default=2)
        field1b = IntegerField('int3', required=False)
        field2 = IntegerField('m_int', multiple=True, required=False)
        field3 = IntegerField('m_int2', multiple=True, required=False)
        field4 = IntegerField('m_int3', multiple=True, required=False)
        field5 = DecimalField('float', min=0.0, max=10.0, required=False)
        field6 = TextField('text', required=False)
        field7 = BooleanField('bool')
        field8 = BooleanField('bool2', required=False)
        CHOICES = [('a', 'A'), ('b', 'B'), ('c', 'C')]
        field9 = ChoiceField('choice', choices=CHOICES)
        field10 = ChoiceField('m_choice', choices=CHOICES, multiple=True)

    def setup(self):
        self.form = TestCleanedValues.DummyForm(MultiDict([
            ('int', '5'),
            ('m_int', '10'), ('m_int', '15'), ('m_int', '0'),
            ('m_int2', '2'),
            ('float', '5.0'),
            ('text', 'foo bar baz'),
            ('bool', 'yes'),
            ('bool2', 'no'),
            ('choice', 'a'),
            ('m_choice', 'a'),
            ('m_choice', 'c')
        ]))
        assert self.form.is_valid()

    def test_cleaned_integer_field(self):
        assert_equal(self.form.cleaned_data['int'], 5)

    def test_cleaned_default_value(self):
        assert_equal(self.form.cleaned_data['int2'], 2)

    def test_cleaned_no_value(self):
        assert_is_none(self.form.cleaned_data['int3'])

    def test_cleaned_multiple(self):
        assert_list_equal(self.form.cleaned_data['m_int'], [10, 15, 0])

    def test_cleaned_multiple_one_value(self):
        assert_list_equal(self.form.cleaned_data['m_int2'], [2])

    def test_cleaned_multiple_no_value(self):
        assert_is_none(self.form.cleaned_data['m_int3'])

    def test_cleaned_decimal_field(self):
        assert_equal(self.form.cleaned_data['float'], 5.0)

    def test_cleaned_text_field(self):
        assert_equal(self.form.cleaned_data['text'], 'foo bar baz')

    def test_cleaned_bool_true_value(self):
        assert_true(self.form.cleaned_data['bool'])

    def test_cleaned_bool_false_value(self):
        assert_is_none(self.form.cleaned_data['bool2'])

    def test_cleaned_choice_field(self):
        assert_equal(self.form.cleaned_data['choice'], 'a')

    def test_cleaned_multiple_choice_field(self):
        assert_list_equal(self.form.cleaned_data['m_choice'], ['a', 'c'])


class TestConditionalValues:
    class DummyForm(BaseForm):
        field1 = IntegerField('int1')
        field2 = IntegerField('int2', default=0, condition="self > int1")
        field3 = IntegerField('int3', required=False, condition="self > int1")

    def test_valid_empty_value(self):
        form = self.create_form(int1=1)
        assert_true(form.is_valid())

    def test_valid_explicit_null(self):
        form = self.create_form(int1=1, int3=None)
        assert_true(form.is_valid())

    def test_valid_default(self):
        form = self.create_form(int1=-1)
        assert_true(form.is_valid())
        assert_equal(form.cleaned_data['int2'], 0)

    def test_invalid_default(self):
        form = self.create_form(int1=1)
        assert_true(form.is_valid())
        assert_is_none(form.cleaned_data['int2'])

    def test_valid_provided(self):
        form = self.create_form(int1=1, int3=2)
        assert_true(form.is_valid())
        assert_equal(form.cleaned_data['int3'], 2)

    def test_invalid_provided(self):
        form = self.create_form(int1=1, int3=0)
        assert_false(form.is_valid())

    @staticmethod
    def create_form(**kwargs):
        return TestConditionalValues.DummyForm(MultiDict(kwargs))
