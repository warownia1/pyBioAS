from collections import defaultdict
from unittest import mock

from nose.tools import assert_list_equal, assert_equal, assert_is_none, raises

from slivka.utils.expression_parser import Token, Expression


def tokenize(exp): return list(Expression.tokenize(exp))


class TestTokenization:
    def test_int_numbers(self):
        tokens = tokenize("5 10 -3")
        expected = [
            Token('NUMBER', 5, 0),
            Token('NUMBER', 10, 2),
            Token('NUMBER', -3, 5)
        ]
        assert_list_equal(tokens, expected)

    def test_float_numbers(self):
        tokens = tokenize("3.5 0.001")
        expected = [
            Token('NUMBER', 3.5, 0),
            Token("NUMBER", 0.001, 4)
        ]
        assert_list_equal(tokens, expected)

    def test_sci_numbers(self):
        tokens = tokenize("1.25E-4 2.01e2")
        expected = [
            Token('NUMBER', 1.25e-4, 0),
            Token('NUMBER', 201.0, 8)
        ]
        assert_list_equal(tokens, expected)

    def test_strings(self):
        tokens = tokenize('"hello" "1.05" "and"')
        expected = [
            Token("STRING", "hello", 0),
            Token("STRING", "1.05", 8),
            Token("STRING", "and", 15)
        ]
        assert_list_equal(tokens, expected)

    def test_keywords(self):
        tokens = tokenize("and or xor not null")
        expected = [
            Token("OPERATOR", "and", 0),
            Token("OPERATOR", "or", 4),
            Token("OPERATOR", "xor", 7),
            Token("OPERATOR", "not", 11),
            Token("NULL", None, 15)
        ]
        assert_list_equal(tokens, expected)

    def test_identifiers(self):
        tokens = tokenize("foo_bar var with-dash")
        expected = [
            Token("IDENTIFIER", "foo_bar", 0),
            Token("IDENTIFIER", "var", 8),
            Token("IDENTIFIER", "with-dash", 12)
        ]
        assert_list_equal(tokens, expected)

    def test_not_identifiers(self):
        tokens = tokenize("not-op me_and_you orion")
        expected = [
            Token("IDENTIFIER", "not-op", 0),
            Token("IDENTIFIER", "me_and_you", 7),
            Token("IDENTIFIER", "orion", 18)
        ]
        assert_list_equal(tokens, expected)

    @raises(ValueError)
    def test_invalid(self):
        tokenize("valid !invalid")


class TestOperatorTokenization:
    def test_add_operator(self):
        tokens = tokenize("2 + 2")
        self.assert_token_equal(tokens[1], "+", 2)

    def test_sub_operator(self):
        tokens = tokenize("2 - 2")
        self.assert_token_equal(tokens[1], "-", 2)

    def test_neg_operator(self):
        tokens = tokenize("-x")
        self.assert_token_equal(tokens[0], "neg", 0)

    def test_mul_operator(self):
        tokens = tokenize("2 * 2")
        self.assert_token_equal(tokens[1], "*")

    def test_div_operator(self):
        tokens = tokenize("2 / 2")
        self.assert_token_equal(tokens[1], "/")

    def test_le_operator(self):
        tokens = tokenize("2 <= 2")
        self.assert_token_equal(tokens[1], "<=")

    def test_ge_operator(self):
        tokens = tokenize("2 >= 2")
        self.assert_token_equal(tokens[1], ">=")

    def test_lt_operator(self):
        tokens = tokenize("2 < 2")
        self.assert_token_equal(tokens[1], "<")

    def test_gt_operator(self):
        tokens = tokenize("2 > 2")
        self.assert_token_equal(tokens[1], ">")

    def test_ne_operator(self):
        tokens = tokenize("2 != 2")
        self.assert_token_equal(tokens[1], '!=')

    def test_eq_operator(self):
        tokens = tokenize("2 == 2")
        self.assert_token_equal(tokens[1], '==')

    def test_len_operator(self):
        tokens = tokenize("#2")
        self.assert_token_equal(tokens[0], '#', 0)

    @staticmethod
    def assert_token_equal(token, operator, position=2):
        assert_equal(token, Token("OPERATOR", operator, position))


class TestLiteralEvaluation:
    def test_int_literal(self):
        assert_equal(Expression("5").eval(), 5)

    def test_float_literal(self):
        assert_equal(Expression("2.45").eval(), 2.45)

    def test_sci_literal(self):
        assert_equal(Expression("1.1e2").eval(), 110.0)

    def test_string_literal(self):
        assert_equal(Expression("\"foobar\"").eval(), "foobar")

    def test_null_literal(self):
        assert_is_none(Expression("null").eval())

    def test_variable(self):
        sentinel = object()
        ctx = dict(value=sentinel)
        assert_equal(Expression("value").eval(ctx), sentinel)


class TestExpressionEvaluation:
    def setup(self):
        self.values = defaultdict(mock.MagicMock)
        self.a = self.values['a']
        self.b = self.values['b']
        self.c = self.values['c']

    def test_add(self):
        self.a.__add__.return_value = 0
        val = Expression("a + b").eval(self.values)
        assert_equal(val, 0)
        self.a.__add__.assert_called_with(self.b)

    def test_sub(self):
        self.a.__sub__.return_value = 5
        val = Expression("a - b").eval(self.values)
        assert_equal(val, 5)
        self.a.__sub__.assert_called_with(self.b)

    def test_mul(self):
        self.a.__mul__.return_value = 8
        val = Expression("a * b").eval(self.values)
        assert_equal(val, 8)
        self.a.__mul__.assert_called_with(self.b)

    def test_div(self):
        self.a.__truediv__.return_value = mock.sentinel.retval
        val = Expression("a / b").eval(self.values)
        assert_equal(val, mock.sentinel.retval)
        self.a.__truediv__.assert_called_with(self.b)

    def test_neg(self):
        self.a.__neg__.return_value = mock.sentinel.retval
        val = Expression("-a").eval(self.values)
        assert_equal(val, mock.sentinel.retval)
        self.a.__neg__.assert_called_with()

    def test_le(self):
        self.a.__le__.return_value = mock.sentinel.retval
        val = Expression("a <= b").eval(self.values)
        assert_equal(val, mock.sentinel.retval)
        self.a.__le__.assert_called_with(self.b)

    def test_lt(self):
        self.a.__lt__.return_value = mock.sentinel.retval
        val = Expression("a < b").eval(self.values)
        assert_equal(val, mock.sentinel.retval)
        self.a.__lt__.assert_called_with(self.b)

    def test_ge(self):
        self.a.__ge__.return_value = mock.sentinel.retval
        val = Expression("a >= b").eval(self.values)
        assert_equal(val, mock.sentinel.retval)
        self.a.__ge__.assert_called_with(self.b)

    def test_gt(self):
        self.a.__gt__.return_value = mock.sentinel.retval
        val = Expression("a > b").eval(self.values)
        assert_equal(val, mock.sentinel.retval)
        self.a.__gt__.assert_called_with(self.b)

    def test_eq(self):
        self.a.__eq__.return_value = mock.sentinel.retval
        val = Expression("a == b").eval(self.values)
        assert_equal(val, mock.sentinel.retval)
        self.a.__eq__.assert_called_with(self.b)

    def test_ne(self):
        self.a.__ne__.return_value = mock.sentinel.retval
        val = Expression("a != b").eval(self.values)
        assert_equal(val, mock.sentinel.retval)
        self.a.__ne__.assert_called_with(self.b)

    def test_len(self):
        self.a.__len__.return_value = 10
        val = Expression("#a").eval(self.values)
        assert_equal(val, 10)
        self.a.__len__.assert_called_with()

    def test_add_then_add(self):
        self.a.__add__.return_value = self.c
        self.c.__add__.return_value = mock.sentinel.retval
        val = Expression("a + b + d").eval(self.values)
        self.a.__add__.assert_called_with(self.values['b'])
        self.c.__add__.assert_called_with(self.values['d'])
        assert_equal(val, mock.sentinel.retval)

    def test_mul_before_add(self):
        self.a.__add__.return_value = mock.sentinel.retval
        self.b.__mul__.return_value = mock.sentinel.prod
        val = Expression("a + b * c").eval(self.values)
        assert_equal(val, mock.sentinel.retval)
        self.b.__mul__.assert_called_with(self.c)
        self.a.__add__.assert_called_with(mock.sentinel.prod)

    def test_add_before_cmp(self):
        self.a.__le__.return_value = mock.sentinel.retval
        self.b.__add__.return_value = mock.sentinel.sum
        val = Expression("a <= b + c").eval(self.values)
        assert_equal(val, mock.sentinel.retval)
        self.b.__add__.assert_called_with(self.c)
        self.a.__le__.assert_called_with(mock.sentinel.sum)

    def test_paren_priority(self):
        self.values['c'].__eq__.return_value = mock.sentinel.x
        self.values['b'].__add__.return_value = mock.sentinel.y
        val = Expression("a * (b + (c == d))").eval(self.values)
        self.c.__eq__.assert_called_with(self.values['d'])
        self.b.__add__.assert_called_with(mock.sentinel.x)
        self.a.__mul__.assert_called_with(mock.sentinel.y)
