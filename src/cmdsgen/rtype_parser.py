from __future__ import annotations

import enum
import string
from typing import Final, Self

from cmdsgen.scanner import (
    DecodeError,
    Lexer,
    ParseError,
    Parser,
    Peekable,
    Scanner,
    Token,
    parse_ident,
    parse_unsigned_int,
)

__all__ = ["parse_rtype"]


def parse_rtype(s: str) -> str:
    """Parse Maya return type and returns union items.

    Raise:
        DecodeError: Failed to parse `s`.

    Example:
        >>> parse_rtype("string")
        'str'
        >>> parse_rtype("double[]")
        'list[float]'
        >>> parse_rtype("string[]|double")
        'list[str] | float'
        >>> parse_rtype("boolean")
        'bool'
    """
    parser = ReturnTypeParser(s)
    try:
        return parser.parse()
    except ParseError as exc:
        raise DecodeError.from_parse_error(exc, s) from exc


class ReturnTypeToken(enum.Enum):
    """Return type token kinds."""

    EOF = enum.auto()
    LBRACKET = enum.auto()  # [
    RBRACKET = enum.auto()  # ]
    VBAR = enum.auto()  # |
    IDENT = enum.auto()  # foo, bar, x
    UINT = enum.auto()  # 1, 2, 10


class ReturnTypeLexer(Lexer[ReturnTypeToken]):
    """Maya Return Type lexer."""

    def __init__(self, s: str, *, infinite: bool = False) -> None:
        self._scanner: Final[Scanner] = Scanner(s)
        self._infinite: Final[bool] = infinite

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> Token[ReturnTypeToken]:
        token = self.pop()
        if not self._infinite and token.kind == ReturnTypeToken.EOF:
            raise StopIteration
        return token

    def pop(self) -> Token[ReturnTypeToken]:
        """Return next `Token`.

        If no token is left, return `Token[ReturnTypeToken.EOF]`.
        """
        self._scanner.skip_whitespaces()
        peek = self._scanner.peek()
        start = self._scanner.cursor

        if (
            kind := {
                "[": ReturnTypeToken.LBRACKET,
                "]": ReturnTypeToken.RBRACKET,
                "|": ReturnTypeToken.VBAR,
                "": ReturnTypeToken.EOF,
            }.get(peek)
        ) is not None:
            literal = self._scanner.pop()
            end = start + len(literal)  # EOF has no len
            return Token(kind, literal, start, end)

        if peek.isdigit():
            literal = parse_unsigned_int(self._scanner)
            end = self._scanner.cursor
            return Token(ReturnTypeToken.UINT, literal, start, end)

        if peek.isalpha():
            literal = parse_ident(
                self._scanner,
                begin=string.ascii_letters,
                inner=string.ascii_letters,
            )
            end = self._scanner.cursor
            return Token(ReturnTypeToken.IDENT, literal, start, end)

        msg = f"Unexpected token {peek!r}"
        raise DecodeError(msg, doc=self._scanner.text, pos=start, end=start + 1)


class ReturnTypeParser(Parser[str]):
    """Maya Return Type parser."""

    def __init__(self, s: str) -> None:
        lexer = ReturnTypeLexer(s, infinite=True)
        self._tokens: Final = Peekable[Token[ReturnTypeToken]](lexer)

    def parse(self) -> str:
        """Parse tokens."""
        if (peek := self._tokens.peek()).kind == ReturnTypeToken.EOF:
            msg = "Empty string"
            raise ParseError(msg, token=peek)

        union: list[str] = []
        while (peek := self._tokens.peek()).kind != ReturnTypeToken.EOF:
            match peek.kind:
                case ReturnTypeToken.IDENT:
                    union.append(self._parse_identifier())
                case ReturnTypeToken.VBAR:
                    next(self._tokens)
                case _:
                    msg = "Unexpected token {kind}"
                    raise ParseError(msg, token=peek)

        return " | ".join(union)

    def _parse_identifier(self) -> str:
        if (token := next(self._tokens)).kind != ReturnTypeToken.IDENT:
            msg = "Expected identifier, got {kind}"
            raise ParseError(msg, token=token)

        try:
            value = self._parse_literal(token.literal)
        except ValueError as exc:
            msg = "Unexpected literal {literal!r}"
            raise ParseError(msg, token=token) from exc

        peek = self._tokens.peek(default=None)
        if not peek or peek.kind != ReturnTypeToken.LBRACKET:
            return value

        # token is an array, e.g., `int[]`, `float[3]`
        next(self._tokens)
        token = next(self._tokens)

        # skip length indicator, e.g., `float[3]`, `int[2]`
        if token.kind == ReturnTypeToken.UINT:
            token = next(self._tokens)

        if token.kind != ReturnTypeToken.RBRACKET:
            msg = "Expected closing bracket ']', got {literal!r}"
            raise ParseError(msg, token=token)

        return f"list[{value}]"

    def _parse_literal(self, literal: str) -> str:
        match literal:
            case "None":
                return "None"
            case "STRING" | "string" | "selectionItem":
                return "str"
            case "Any":
                return "Any"
            case "Boolean" | "boolean":
                return "bool"
            case "float" | "double":
                return "float"
            case "int" | "Int" | "time":
                return "int"
            case _:
                raise ValueError(literal)
