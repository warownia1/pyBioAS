import re
from collections import namedtuple

Token = namedtuple("Token", "type, value, position")

tokens = [
    ('LPAREN', r'\('),
    ('RPAREN', r'\)'),
    ('NUMBER', r'-?\d+(?:\.\d+)?(?:[eE]-?\d+)?'),
    ('STRING', r'"(?:[^"\\]|\\.)*"'),
    ('KEYWORD', r'(?:and|or|xor|not|null)(?:$|(?=[^\w\-]))'),
    ('IDENTIFIER', r'[A-Za-z_][\w\-]*'),
    ('OPERATOR', r'[#+*\/\-]|[<>]=?|[=!]='),
    ('SKIP', r'[ \t]'),
    ('INVALID', r'.')
]

token_regex = '|'.join('(?P<%s>%s)' % pair for pair in tokens)

OPERATOR_PRECEDENCE = {
    op: prec
    for prec, ops in
    enumerate([['('], ['or'], ['xor'], ['and'], ['!=', '=='],
               ['<', '>', '<=', '>='], ['+', '-'], ['*', '/'],
               ['neg', 'not', '#']])
    for op in ops
}

UNARY_OPERATORS = ['neg', 'not', '#']


class Expression:
    def __init__(self, expression):
        self.original_expression = expression
        expr = _tokenize(expression)
        expr = _infix_to_rpn(expr)
        _verify_rpn(expr)
        self.expression = expr

    @staticmethod
    def tokenize(string):
        return _tokenize(string)

    def eval(self, variables=None):
        return _evaluate_rpn(self.expression, variables or {})

    evaluate = eval


def _tokenize(string):
    expect_expression = True
    for match in re.finditer(token_regex, string):
        kind = match.lastgroup
        value = match.group()
        position = match.start()
        if kind == 'SKIP':
            continue
        if kind == 'INVALID':
            raise ValueError(f'Unexpected character {value!r}')
        if kind == 'KEYWORD':
            if value == 'null':
                kind = 'NULL'
                value = None
            elif value in ('and', 'or', 'xor', 'not'):
                kind = 'OPERATOR'
            else:
                raise ValueError(f"Invalid keyword {value!r}")
        elif kind == 'NUMBER':
            if any(ch in value for ch in '.eE'):
                value = float(value)
            else:
                value = int(value)
        elif kind == 'STRING':
            value = value[1:-1].replace(r'\"', r'"')
        elif expect_expression and kind == "OPERATOR" and value == '-':
            # if the expression is expected but - is encountered it's unary
            value = 'neg'
        # may want to test if the "expected expression" is satisfied here
        expect_expression = kind == 'LPAREN' or kind == 'OPERATOR'
        yield Token(type=kind, value=value, position=position)


def _infix_to_rpn(expression):
    rpn_stack = []
    operator_stack = []
    for token in expression:
        if token.type == 'LPAREN':
            operator_stack.append(token)
        elif token.type == 'RPAREN':
            try:
                while operator_stack[-1].type != 'LPAREN':
                    rpn_stack.append(operator_stack.pop())
            except IndexError:
                raise ValueError("mismatched parenthesis %r" % token) from None
            operator_stack.pop()
        elif token.type in ('NULL', 'IDENTIFIER', 'NUMBER', 'STRING'):
            rpn_stack.append(token)
        elif token.type == 'OPERATOR':
            if token.value in UNARY_OPERATORS:
                operator_stack.append(token)
            else:
                token_prec = OPERATOR_PRECEDENCE[token.value]
                stack_prec = (
                    0 if not operator_stack
                    else OPERATOR_PRECEDENCE[operator_stack[-1].value])
                while token_prec <= stack_prec:
                    rpn_stack.append(operator_stack.pop())
                    stack_prec = (
                        0 if not operator_stack
                        else OPERATOR_PRECEDENCE[operator_stack[-1].value])
                operator_stack.append(token)
        else:
            raise ValueError("invalid token type")
    rpn_stack.extend(reversed(operator_stack))
    return rpn_stack


def _verify_rpn(expression):
    # check for any mismatched parentheses
    mismatched_lparen = next(
        filter(lambda t: t.type == 'LPAREN', expression), None)
    if mismatched_lparen is not None:
        raise ValueError("mismatched parenthesis %r" % mismatched_lparen)

    # checks if every operator have an expression to act on
    expr_count = 0
    for token in expression:
        if token.type in ('NUMBER', 'STRING', 'IDENTIFIER', 'NULL'):
            expr_count += 1
        elif token.type == 'OPERATOR':
            consumed_expr = 2 if token.value not in UNARY_OPERATORS else 1
            if expr_count < consumed_expr:
                raise ValueError("unexpected operator %r" % token)
            expr_count -= consumed_expr - 1

    if expr_count != 1:
        raise ValueError("line contains multiple expressions")


def _evaluate_rpn(expression, variables):
    eval_stack = []
    for token in expression:
        if token.type in ('NUMBER', 'STRING', 'NULL'):
            eval_stack.append(token.value)
        elif token.type == 'IDENTIFIER':
            eval_stack.append(variables[token.value])
        elif token.type == 'OPERATOR':
            if token.value in UNARY_OPERATORS:
                a = eval_stack.pop()
                if token.value == 'neg':
                    r = -a
                elif token.value == 'not':
                    r = not bool(a)
                elif token.value == '#':
                    r = len(a)
                else:
                    raise ValueError("invalid operator %r" % token.value)
            else:
                b, a = eval_stack.pop(), eval_stack.pop()
                if token.value == 'or':
                    r = bool(a) or bool(b)
                elif token.value == 'xor':
                    r = bool(a) != bool(b)
                elif token.value == 'and':
                    r = bool(a) and bool(b)
                elif token.value == '!=':
                    r = a != b
                elif token.value == '==':
                    r = a == b
                elif token.value == '<':
                    r = a < b
                elif token.value == '>':
                    r = a > b
                elif token.value == '<=':
                    r = a <= b
                elif token.value == '>=':
                    r = a >= b
                elif token.value == '+':
                    r = a + b
                elif token.value == '-':
                    r = a - b
                elif token.value == '*':
                    r = a * b
                elif token.value == '/':
                    r = a / b
                else:
                    raise ValueError("invalid operator %r" % token.value)
            eval_stack.append(r)
        else:
            raise ValueError(f"invalid token {token!r}")
    if len(eval_stack) != 1:
        raise ValueError("too many tokens left on the stack")
    else:
        return eval_stack[0]
