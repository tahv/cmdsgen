from __future__ import annotations

import itertools
import string
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Final, Protocol, Self, overload

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from pathlib import Path


__all__ = [
    "DecodeError",
    "ParseError",
    "Peekable",
    "Scanner",
    "Token",
    "parse_ellipsis",
    "parse_ident",
    "parse_unsigned_int",
]


@dataclass(frozen=True)
class Token[E: Enum]:
    """Parsed Token."""

    kind: E
    literal: str
    start: int
    end: int


class Parser[R](Protocol):
    """Parser Protocol."""

    def __init__(self, s: str) -> None: ...
    def parse(self) -> R: ...


class Lexer[E: Enum](Protocol):
    """Lexer Protocol.

    If `infinite` is enabled,
    the `__next__` method should not raise `StopIteration`
    but return a sentinel value indefinitely,
    indicating end of file.
    """

    def __init__(self, s: str, *, infinite: bool = False) -> None: ...
    def __iter__(self) -> Self: ...
    def __next__(self) -> Token[E]: ...
    def pop(self) -> Token[E]: ...


class Scanner:
    """String scanner.

    Example:
        >>> scanner = Scanner("abc")
        >>> scanner.peek()
        'a'
        >>> scanner.pop()
        'a'
        >>> scanner.peek(1)
        'c'
        >>> scanner.pop()
        'b'
        >>> scanner.pop()
        'c'
        >>> scanner.pop()
        ''

        Skip whitespaces
        >>> scanner = Scanner("       a")
        >>> scanner.skip_whitespaces()
        >>> scanner.pop()
        'a'
    """

    def __init__(self, text: str) -> None:
        self._text: str = text
        self._cursor: int = 0

    @property
    def text(self) -> str:
        """The text being scanned."""
        return self._text

    @property
    def cursor(self) -> int:
        """Current position in string."""
        return self._cursor

    def skip_whitespaces(self) -> None:
        """Advance cursor until the next non-whitespace character."""
        while self.peek().isspace():
            self.pop()

    def peek(self, index: int = 0) -> str:
        """Return the next character without advancing the cursor.

        If no character is left, returns an empty string `''`.

        Args:
            index: Character index to lookahead from current cursor position.
              Default to 0, which correspond to the item that will be returned
              from `pop`.
        """
        assert index >= 0
        try:
            return self._text[self._cursor + index]
        except IndexError:
            return ""

    def pop(self) -> str:
        """Return the next character and advance the cursor.

        If no character is left, returns an empty string `''`
        and don't advances the cursor.
        """
        char = self.peek()
        if char != "":
            self._cursor += 1
        return char


def parse_ellipsis(scanner: Scanner) -> str:
    """Parse an ellispsis, 3 dots (`...`).

    Example:
        >>> scanner = Scanner("...foo")
        >>> parse_ellipsis(scanner)
        '...'
    """
    start = scanner.cursor
    for _ in range(1, 4):
        if (char := scanner.pop()) != ".":
            msg = f"Expected ellispsis `...`, found {char!r}"
            raise DecodeError(msg, doc=scanner.text, pos=start, end=scanner.cursor)
    return "..."


def parse_unsigned_int(scanner: Scanner) -> str:
    """Parse unsigned integer.

    Example:
        >>> scanner = Scanner("123foo")
        >>> parse_unsigned_int(scanner)
        '123'
    """
    if not scanner.peek().isdigit():
        msg = f"Expected digit, found {scanner.peek()!r}"
        raise DecodeError(msg, doc=scanner.text, pos=scanner.cursor, end=scanner.cursor)

    digits: list[str] = []
    while scanner.peek().isdigit():
        digits.append(scanner.pop())

    return "".join(digits)


def parse_ident(
    scanner: Scanner,
    begin: str = string.ascii_letters,
    inner: str = string.ascii_letters + string.digits,
    end: str | None = None,
) -> str:
    """Parse a sequence of chars.

    Example:
        >>> parse_ident(Scanner("int64, float"))
        'int64'
        >>> parse_ident(Scanner("foo123"), inner=string.ascii_letters)
        'foo'
    """
    end = end or inner

    if scanner.peek() not in begin:
        msg = f"Expected one of {begin!r}, found {scanner.peek()!r}"
        raise DecodeError(msg, doc=scanner.text, pos=scanner.cursor, end=scanner.cursor)

    sequence: list[str] = [scanner.pop()]

    while (peek := scanner.peek()) and peek in inner:
        sequence.append(scanner.pop())

    if (peek := scanner.peek()) and peek in end:
        sequence.append(scanner.pop())
    elif sequence[-1] not in end:
        msg = f"Expected one of {end!r}, found {sequence[-1]!r}"
        cursor = scanner.cursor - 1
        raise DecodeError(msg, doc=scanner.text, pos=cursor, end=cursor)

    return "".join(sequence)


_marker: Final[object] = object()


class Peekable[T]:
    """Wrap an iterator to support lookahead.

    Example:
        Wrap an iterable.
        >>> list(Peekable("abc"))
        ['a', 'b', 'c']

        Supports `bool` for end of string reached.
        >>> peekable = Peekable("a")
        >>> bool(peekable)
        True
        >>> _ = next(peekable)
        >>> bool(peekable)
        False
    """

    def __init__(self, iterable: Iterable[T]) -> None:
        self._it: Iterator[T] = iter(iterable)
        self._cache: deque[T] = deque()

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> T:
        if self._cache:
            return self._cache.popleft()
        return next(self._it)

    def is_empty(self) -> bool:
        """Returns `True` if the `Peekable` is empty."""
        try:
            self.peek()
        except IndexError:
            return True
        return False

    def __bool__(self) -> bool:
        return not self.is_empty()

    @overload
    def peek(self) -> T: ...

    @overload
    def peek(self, index: int) -> T: ...

    @overload
    def peek[D](self, *, default: D) -> T | D: ...

    @overload
    def peek[D](self, index: int, *, default: D) -> T | D: ...

    def peek[D](self, index: int = 0, *, default: D = _marker) -> T | D:  # type:ignore[assignment]  # ty:ignore[invalid-parameter-default]
        """Return the next item without advancing the iterator.

        Args:
            index: Item index to lookahead from current position in iterable.
                Default to 0, which correspond to the item that will be returned
                from ``next()``
            default: Value to return if ``index `` is out of range.

        Raise:
            IndexError: Item at ``index`` is out of range and no ``default``
                specified.

        Example:
            Return next item.
            >>> peekable = Peekable("abc")
            >>> peekable.peek()
            'a'
            >>> _ = next(peekable)
            >>> peekable.peek()
            'b'

            Or the next item as `index`.
            >>> peekable = Peekable("abc")
            >>> peekable.peek(2)
            'c'
            >>> peekable.peek(1)
            'b'

            Raise an exception if out of range.
            >>> Peekable("abc").peek(10)
            Traceback (most recent call last):
                ...
            IndexError: Peekable index out of range

            Or fallback to `default`.
            >>> Peekable("abc").peek(10, default="x")
            'x'
        """
        assert index >= 0, "expected `index >= 0`"

        cache_len = len(self._cache)
        if index >= cache_len:
            self._cache.extend(itertools.islice(self._it, index + 1 - cache_len))

        try:
            return self._cache[index]
        except IndexError:
            if default is _marker:
                msg = "Peekable index out of range"
                raise IndexError(msg) from None
            return default


class DecodeError(Exception):
    """Raised when decoding of document failed.

    Attributes:
        msg: The unformatted error message.
        doc: The document being parsed.
        pos: The start index of string where parsing failed.
        end: The (optional) end index where parsing failed.
            For example when an invalid token caused the error.
        lineno: The line corresponding to pos
        colno: The column corresponding to pos
        file: The (optional) path to the file being parsed.
    """

    def __init__(
        self,
        msg: str,
        /,
        *,
        doc: str,
        pos: int,
        end: int | None = None,
        file: Path | None = None,
    ) -> None:
        self.msg: str = msg
        self.lineno: int = doc.count("\n", 0, pos) + 1
        self.colno: int = pos - doc.rfind("\n", 0, pos)
        self.end: int | None = end
        self.file: Path | None = file
        super().__init__(
            f"{file.name}:{self.lineno}:{self.colno}: {self.msg}"
            if file
            else f"{self.lineno}:{self.colno}: {self.msg}",
        )

    @classmethod
    def from_parse_error[E: Enum](cls, err: ParseError[E], doc: str) -> Self:
        """Initialize from `ParseError`."""
        return cls(err.msg, doc=doc, pos=err.token.start, end=err.token.end)


class ParseError[E: Enum](Exception):
    """Raised when parsing of document failed.

    This exception can be re-raised with `DecodeError.from_parse_error`
    to provide more context.

    Attributes:
        msg: The unformatted error message.
            Accepts the `{kind}` and `{literal}` placeholders.
        token: The token that raised the error.
    """

    def __init__(self, msg: str, /, token: Token[E]) -> None:
        self.token: Token[E] = token
        msg = msg.format(kind=self.token.kind, literal=self.token.literal)
        super().__init__(self, msg)

    @classmethod
    def unexpected(cls, token: Token[E]) -> Self:
        """Unexpected token."""
        return cls("Unexpected token: {kind}", token=token)
