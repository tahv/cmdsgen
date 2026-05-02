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
    parse_ellipsis,
    parse_ident,
)

__all__ = ["parse_param"]


def parse_param(s: str) -> str:
    """Parse Maya Parameter.

    Raise:
        DecodeError: Failed to parse `s`.
    """
    parser = ParamParser(s)
    try:
        return parser.parse()
    except ParseError as exc:
        raise DecodeError.from_parse_error(exc, s) from exc


class ParamToken(enum.Enum):
    """Maya Param token kinds."""

    EOF = enum.auto()
    ILLEGAL = enum.auto()
    LBRACKET = enum.auto()  # [
    RBRACKET = enum.auto()  # ]
    VBAR = enum.auto()  # |
    ELLIPSIS = enum.auto()  # ...
    IDENTIFIER = enum.auto()  # foo, bar, x


class ParamLexer(Lexer[ParamToken]):
    """Maya Param lexer, from the synopsis."""

    def __init__(self, s: str, *, infinite: bool = False) -> None:
        self._scanner: Final[Scanner] = Scanner(s)
        self._infinite: Final[bool] = infinite

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> Token[ParamToken]:
        token = self.pop()
        if not self._infinite and token.kind == ParamToken.EOF:
            raise StopIteration
        return token

    def pop(self) -> Token[ParamToken]:
        """Return next `Token`.

        If no token is left, return `Token[ParamToken.EOF]`.
        """
        self._scanner.skip_whitespaces()
        peek = self._scanner.peek()
        start = self._scanner.cursor

        if (
            kind := {
                "[": ParamToken.LBRACKET,
                "]": ParamToken.RBRACKET,
                "|": ParamToken.VBAR,
                "": ParamToken.EOF,
            }.get(peek)
        ) is not None:
            literal = self._scanner.pop()
            end = start + len(literal)  # EOF has no len
            return Token(kind, literal, start, end)

        if peek == ".":
            literal = parse_ellipsis(self._scanner)
            end = self._scanner.cursor
            return Token(ParamToken.ELLIPSIS, literal, start, end)

        if peek.isalpha():
            literal = parse_ident(
                self._scanner,
                begin=string.ascii_letters,
                inner=string.ascii_letters,
            )
            end = self._scanner.cursor
            return Token(ParamToken.IDENTIFIER, literal, start, end)

        msg = f"Unexpected token {peek!r}"
        raise DecodeError(msg, doc=self._scanner.text, pos=start, end=start + 1)


class ParamParser(Parser[str]):
    """Maya Param parser, from the synopsis."""

    def __init__(self, s: str) -> None:
        lexer = ParamLexer(s, infinite=True)
        self._tokens: Final = Peekable[Token[ParamToken]](lexer)

    def parse(self) -> str:
        """Parse tokens."""
        if (peek := self._tokens.peek()).kind == ParamToken.EOF:
            msg = "Empty string"
            raise ParseError(msg, token=peek)
        # TODO(tga): Parse positional arguments
        return "Any"
