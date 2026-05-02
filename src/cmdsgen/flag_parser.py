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
)


def parse_flag(s: str) -> str:
    """Parse Maya Flag.

    Raise:
        DecodeError: Failed to parse `s`.

    Example:
        >>> parse_flag("boolean")
        'bool'
        >>> parse_flag("[string, int, float]")
        'tuple[str, int, float]'
        >>> parse_flag("string[]")
        'list[str]'
        >>> parse_flag("[int, name]")
        'tuple[int, str]'
    """
    # TODO(tga): example "[[, boolean, float, ]]" (mel "[ boolean float ]")
    # TODO(tga): example "[int, [, string, ]]" (mel "int [ string ]")
    parser = FlagParser(s)
    try:
        return parser.parse()
    except ParseError as exc:
        raise DecodeError.from_parse_error(exc, s) from exc


class FlagToken(enum.Enum):
    """Maya Flag token kinds."""

    EOF = enum.auto()
    LBRACKET = enum.auto()  # [
    RBRACKET = enum.auto()  # ]
    COMMA = enum.auto()  # ,
    IDENT = enum.auto()  # boolean, int64, uint


class FlagLexer(Lexer[FlagToken]):
    """Maya Flag lexer."""

    def __init__(self, s: str, *, infinite: bool = False) -> None:
        self._scanner: Final[Scanner] = Scanner(s)
        self._infinite: Final[bool] = infinite

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> Token[FlagToken]:
        token = self.pop()
        if not self._infinite and token.kind == FlagToken.EOF:
            raise StopIteration
        return token

    def pop(self) -> Token[FlagToken]:
        """Return next `Token`.

        If no token is left, return `Token[FlagToken.EOF]`.
        """
        self._scanner.skip_whitespaces()
        peek = self._scanner.peek()
        start = self._scanner.cursor

        if (
            kind := {
                "[": FlagToken.LBRACKET,
                "]": FlagToken.RBRACKET,
                ",": FlagToken.COMMA,
                "": FlagToken.EOF,
            }.get(peek)
        ) is not None:
            literal = self._scanner.pop()
            end = start + len(literal)  # EOF has no len
            return Token(kind, literal, start, end)

        if peek.isalpha():
            literal = parse_ident(
                self._scanner,
                begin=string.ascii_letters,
                inner=string.ascii_letters + string.digits,
            )
            end = self._scanner.cursor
            return Token(FlagToken.IDENT, literal, start, end)

        msg = f"Unexpected token {peek!r}"
        raise DecodeError(msg, doc=self._scanner.text, pos=start, end=start + 1)


class FlagParser(Parser[str]):
    """Maya Flag parser."""

    def __init__(self, s: str) -> None:
        lexer = FlagLexer(s, infinite=True)
        self._tokens: Final = Peekable[Token[FlagToken]](lexer)

    def parse(self) -> str:
        """Parse tokens."""
        if (peek := self._tokens.peek()).kind == FlagToken.EOF:
            msg = "Empty string"
            raise ParseError(msg, token=peek)

        value: str
        match peek.kind:
            case FlagToken.IDENT:
                value = self._parse_identifier()
            case FlagToken.LBRACKET:
                value = self._parse_array()
            case _:
                msg = "Expected identifier or open bracked '[', got {literal!r}"
                raise ParseError(msg, token=peek)

        if (peek := self._tokens.peek()).kind != FlagToken.EOF:
            msg = "Expected end of string, got {literal!r}"
            raise ParseError(msg, token=peek)

        return value

    def _parse_array(self) -> str:
        if (token := next(self._tokens)).kind != FlagToken.LBRACKET:
            msg = "Expected opening bracket '[', got {literal!r}"
            raise ParseError(msg, token=token)

        items: list[str] = []
        while (peek := self._tokens.peek()).kind != FlagToken.EOF:
            match peek.kind:
                case FlagToken.IDENT:
                    items.append(self._parse_identifier())
                case FlagToken.COMMA:
                    next(self._tokens)
                case FlagToken.LBRACKET:
                    items.append(self._parse_array())
                case FlagToken.RBRACKET:
                    next(self._tokens)
                    return f"tuple[{', '.join(items)}]"
                case _:
                    msg = "Unexpected token {kind}"
                    raise ParseError(msg, token=peek)

        msg = "Reached end of string before end of list"
        raise ParseError(msg, token=peek)

    def _parse_identifier(self) -> str:
        if (token := next(self._tokens)).kind != FlagToken.IDENT:
            msg = "Expected identifier, got {kind}"
            raise ParseError(msg, token=token)

        try:
            value = self._parse_literal(token.literal)
        except ValueError as exc:
            msg = "Unexpected literal {literal!r}"
            raise ParseError(msg, token=token) from exc

        peek = self._tokens.peek(default=None)
        if not peek or peek.kind != FlagToken.LBRACKET:
            return value

        # token is an array, e.g., `string[]`, `int[]`
        next(self._tokens)
        token = next(self._tokens)

        if token.kind != FlagToken.RBRACKET:
            msg = "Expected closing bracket ']', got {literal!r}"
            raise ParseError(msg, token=token)

        return f"list[{value}]"

    def _parse_literal(self, literal: str) -> str:  # noqa: PLR0911
        match literal:
            case "boolean":
                return "bool"
            case "string" | "name" | "angle":
                return "str"
            case "script":
                return "Any"  # either a Callable or a str depending on flag
            case "int" | "uint" | "int64":
                return "int"
            case "float" | "linear":
                return "float"
            case "time":
                return "float"
            case "timerange":
                return "Any"
            case "floatrange":
                return "Any"
            case _:
                raise ValueError(literal)
