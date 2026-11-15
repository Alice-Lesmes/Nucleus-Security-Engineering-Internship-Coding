"""
Calculator: tokenise -> validate -> build precedence tree -> evaluate.

Follows the pseudo logic:
  1. Tokenise into nodes (number / operation / parentheses)
  2. Validate mathematical soundness (parens, operands, unary minus)
  3. Build a tree by repeatedly picking the lowest-precedence operator
  4. Evaluate the tree recursively

Precedence (lower number binds tighter):
  0 parentheses, 1 exponent (^), 2 * and /, 3 + and -
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Union

Number = Union[int, float]


class CalcError(Exception):
    """Raised for any syntax, validation, or evaluation problem."""


# --------------------------------------------------------------------------
# Tokens
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Token:
    kind: str          # 'num', 'op', 'lparen', 'rparen'
    value: object      # int/float for 'num', str for others
    pos: int = -1      # position in the original text (for error messages)


PRECEDENCE = {"^": 1, "*": 2, "/": 2, "+": 3, "-": 3}
NUM_RE = re.compile(r"\d+\.\d+|\.\d+|\d+")


def tokenize(text: str) -> list[Token]:
    """Step 1: turn raw text into tokens, rejecting anything outside the language."""
    tokens: list[Token] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            i += 1
        elif ch.isdigit() or ch == ".":
            m = NUM_RE.match(text, i)
            if not m:
                raise CalcError(f"Malformed number at position {i}")
            raw = m.group()
            tokens.append(Token("num", float(raw) if "." in raw else int(raw), i))
            i = m.end()
        elif ch in PRECEDENCE:
            tokens.append(Token("op", ch, i))
            i += 1
        elif ch == "(":
            tokens.append(Token("lparen", ch, i))
            i += 1
        elif ch == ")":
            tokens.append(Token("rparen", ch, i))
            i += 1
        else:
            raise CalcError(f"Unexpected character {ch!r} at position {i}")
    if not tokens:
        raise CalcError("Empty expression")
    return tokens


# --------------------------------------------------------------------------
# Validation helpers
# --------------------------------------------------------------------------
def check_parentheses(tokens: list[Token]) -> None:
    """Equal counts, and every ')' must close a previously opened '('."""
    depth = 0
    for t in tokens:
        if t.kind == "lparen":
            depth += 1
        elif t.kind == "rparen":
            depth -= 1
            if depth < 0:
                raise CalcError(f"')' at position {t.pos} has no matching '('")
    if depth != 0:
        raise CalcError("Unbalanced parentheses: more '(' than ')'")


def _matching_paren(tokens: list[Token], start: int) -> int:
    """Index of the ')' that closes the '(' at `start`."""
    depth = 0
    for i in range(start, len(tokens)):
        if tokens[i].kind == "lparen":
            depth += 1
        elif tokens[i].kind == "rparen":
            depth -= 1
            if depth == 0:
                return i
    raise CalcError("Unbalanced parentheses")


def rewrite_negatives(tokens: list[Token]) -> list[Token]:
    """
    A '-' with nothing to its left (start of expression, after '(' or after
    another operator) is a negative sign. Replace `-X` with `(0 - X)` so the
    ordering is preserved. X is the following number, parenthesised group, or
    another negative (so `--3` becomes `(0 - (0 - 3))`).
    """
    out: list[Token] = []

    def operand(i: int) -> int:
        """Emit the operand starting at i (with negatives rewritten); return next index."""
        if i >= len(tokens):
            raise CalcError("Expected a value after '-' but the expression ended")
        t = tokens[i]
        if t.kind == "num":
            out.append(t)
            return i + 1
        if t.kind == "op" and t.value == "-":
            return negative(i)
        if t.kind == "lparen":
            end = _matching_paren(tokens, i)
            out.append(t)
            out.extend(rewrite_negatives(tokens[i + 1:end]))
            out.append(tokens[end])
            return end + 1
        raise CalcError(f"Expected a value after '-' at position {tokens[i - 1].pos}")

    def negative(i: int) -> int:
        out.append(Token("lparen", "(", tokens[i].pos))
        out.append(Token("num", 0, tokens[i].pos))
        out.append(Token("op", "-", tokens[i].pos))
        nxt = operand(i + 1)
        out.append(Token("rparen", ")", tokens[i].pos))
        return nxt

    i = 0
    prev: Token | None = None
    while i < len(tokens):
        t = tokens[i]
        unary = (
            t.kind == "op"
            and t.value == "-"
            and (prev is None or prev.kind in ("op", "lparen"))
        )
        if unary:
            i = negative(i)
            prev = Token("rparen", ")")  # the rewritten group acts like a value
        elif t.kind == "lparen":
            end = _matching_paren(tokens, i)
            out.append(t)
            out.extend(rewrite_negatives(tokens[i + 1:end]))
            out.append(tokens[end])
            i = end + 1
            prev = tokens[end]
        else:
            out.append(t)
            prev = t
            i += 1
    return out


def check_adjacency(tokens: list[Token]) -> None:
    """
    - Binary operators need a value on both sides.
    - Parentheses may not be empty (this also rejects '(((...)))' with nothing inside).
    - Two values may not touch ('2 3', '2(3)'): implicit multiplication isn't supported.
    """
    def ends_value(t: Token) -> bool:
        return t.kind in ("num", "rparen")

    def starts_value(t: Token) -> bool:
        return t.kind in ("num", "lparen")

    first, last = tokens[0], tokens[-1]
    if first.kind == "op":
        raise CalcError(f"Operator {first.value!r} at position {first.pos} has nothing to its left")
    if last.kind == "op":
        raise CalcError(f"Operator {last.value!r} at position {last.pos} has nothing to its right")

    for a, b in zip(tokens, tokens[1:]):
        if a.kind == "lparen" and b.kind == "rparen":
            raise CalcError(f"Empty parentheses at position {a.pos}")
        if a.kind == "lparen" and b.kind == "op":
            raise CalcError(f"Operator {b.value!r} at position {b.pos} has nothing to its left")
        if a.kind == "op" and b.kind == "rparen":
            raise CalcError(f"Operator {a.value!r} at position {a.pos} has nothing to its right")
        if a.kind == "op" and b.kind == "op":
            raise CalcError(f"Operators {a.value!r} and {b.value!r} are adjacent at position {a.pos}")
        if ends_value(a) and starts_value(b):
            raise CalcError(f"Missing operator between tokens at position {b.pos}")


# --------------------------------------------------------------------------
# Tree nodes
# --------------------------------------------------------------------------
@dataclass
class NumberNode:
    value: Number


@dataclass
class ParenNode:
    child: "Node"


@dataclass
class BinaryNode:
    op: str            # one of ^ * / + -
    left: "Node"
    right: "Node"


Node = Union[NumberNode, ParenNode, BinaryNode]


def build_tree(tokens: list[Token], lo: int = 0, hi: int | None = None) -> Node:
    """
    Step 3: pick the root as the lowest-precedence (highest number) operator that
    is NOT inside parentheses, then recurse on the left and right sections.

    Tie-breaking (this differs from "always leftmost", which would make
    1 - 2 - 3 come out as 1 - (2 - 3) = 2 instead of -4):
      * + - * /  are left-associative  -> choose the RIGHTMOST one as root
      * ^        is right-associative  -> choose the LEFTMOST one as root
    """
    if hi is None:
        hi = len(tokens)

    best_idx = -1
    best_prec = 0
    depth = 0
    for i in range(lo, hi):
        t = tokens[i]
        if t.kind == "lparen":
            depth += 1
        elif t.kind == "rparen":
            depth -= 1
        elif t.kind == "op" and depth == 0:
            prec = PRECEDENCE[t.value]
            if prec > best_prec:
                best_idx, best_prec = i, prec
            elif prec == best_prec and prec != PRECEDENCE["^"]:
                best_idx = i  # later one wins for left-associative operators
            # for '^' keep the first (leftmost) one found

    if best_idx != -1:
        return BinaryNode(
            tokens[best_idx].value,
            build_tree(tokens, lo, best_idx),
            build_tree(tokens, best_idx + 1, hi),
        )

    # No top-level operator: this is a single number or a parenthesised group.
    if hi - lo == 1 and tokens[lo].kind == "num":
        return NumberNode(tokens[lo].value)  # type: ignore[arg-type]
    if tokens[lo].kind == "lparen" and tokens[hi - 1].kind == "rparen":
        return ParenNode(build_tree(tokens, lo + 1, hi - 1))
    raise CalcError("Could not build expression tree")  # unreachable after validation


# --------------------------------------------------------------------------
# Evaluation
# --------------------------------------------------------------------------
def eval_node(node: Node) -> Number:
    """Step 4: recursively evaluate the tree."""
    match node:
        case NumberNode(value=v):
            return v
        case ParenNode(child=c):
            return eval_node(c)
        case BinaryNode(op=op, left=l, right=r):
            lv, rv = eval_node(l), eval_node(r)
            match op:
                case "+":
                    return lv + rv
                case "-":
                    return lv - rv
                case "*":
                    return lv * rv
                case "/":
                    if rv == 0:
                        raise CalcError("Division by zero")
                    result = lv / rv
                    if isinstance(lv, int) and isinstance(rv, int) and lv % rv == 0:
                        return lv // rv  # keep exact integer results as ints
                    return result
                case "^":
                    if lv == 0 and rv < 0:
                        raise CalcError("Division by zero (0 raised to a negative power)")
                    if lv < 0 and isinstance(rv, float) and not rv.is_integer():
                        raise CalcError("Negative base with a fractional exponent is not real")
                    try:
                        return lv ** rv
                    except OverflowError:
                        raise CalcError("Result too large") from None
                case _:
                    raise CalcError(f"Unknown operator {op!r}")
        case _:
            raise CalcError(f"Unknown node type {type(node).__name__}")


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
def parse(text: str) -> Node:
    tokens = tokenize(text)
    check_parentheses(tokens)
    tokens = rewrite_negatives(tokens)
    check_adjacency(tokens)
    return build_tree(tokens)


def calculate(text: str) -> Number:
    return eval_node(parse(text))


def tree_str(node: Node, indent: int = 0) -> str:
    """Small helper to print the tree for debugging."""
    pad = "    " * indent
    match node:
        case NumberNode(value=v):
            return f"{pad}{v}\n"
        case ParenNode(child=c):
            return f"{pad}()\n" + tree_str(c, indent + 1)
        case BinaryNode(op=op, left=l, right=r):
            return f"{pad}{op}\n" + tree_str(l, indent + 1) + tree_str(r, indent + 1)
    return ""


# --------------------------------------------------------------------------
# Tests / REPL
# --------------------------------------------------------------------------
def _run_tests() -> None:
    good = {
        "1 - 2 - (3 * 3) + 2": -8,
        "1+2*3": 7,
        "(1+2)*3": 9,
        "((1+2)+3)": 6,
        "((1+2))": 3,
        "2^3^2": 512,            # right-associative: 2^(3^2)
        "2*3^2": 18,
        "10/4": 2.5,
        "10/5": 2,
        "100/10/5": 2,           # left-associative
        "8-3-2": 3,
        "-5 + 3": -2,
        "2 * -3": -6,
        "2^-1": 0.5,
        "-(2+3)": -5,
        "(-2)*(-3)": 6,
        "--4": 4,
        "1.5 + 2.5": 4.0,
        ".5 * 4": 2.0,
    }
    for expr, expected in good.items():
        got = calculate(expr)
        assert got == expected, f"{expr!r}: expected {expected}, got {got}"

    bad = ["", "()", "((()))", "(1+2", "1+2)", ")(", "1+", "*2", "2**3",
           "(*2)", "(2+)", "2 3", "2(3)", "1/0", "0^-1", "abc", "1..2", "-"]
    for expr in bad:
        try:
            calculate(expr)
        except CalcError:
            continue
        raise AssertionError(f"{expr!r} should have raised CalcError")
    print(f"All {len(good)} valid and {len(bad)} invalid cases passed.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        _run_tests()
    else:
        print("Calculator. Type an expression, 'tree <expr>' to see the tree, or 'q' to quit.")
        while True:
            try:
                line = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if line.lower() in ("q", "quit", "exit"):
                break
            if not line:
                continue
            try:
                if line.startswith("tree "):
                    print(tree_str(parse(line[5:])), end="")
                else:
                    print(calculate(line))
            except CalcError as e:
                print(f"Error: {e}")
