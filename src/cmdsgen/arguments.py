from __future__ import annotations

import enum
import itertools
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, cast, get_args

from cmdsgen.fetch import FetchedCommand, FlagMode
from cmdsgen.flag_parser import parse_flag
from cmdsgen.rtype_parser import parse_rtypes

if TYPE_CHECKING:
    from collections.abc import Iterable

    from _typeshed import SupportsRichComparison


type QueryFlag = Literal["query", "q"]
type EditFlag = Literal["edit", "e"]


@dataclass(frozen=True)
class ParsedCommand:
    """A parsed command signature."""

    name: str
    args: tuple[Argument, ...]
    rtype: str

    def to_string(self, *, overload: bool = False) -> str:
        """Returns command as stub."""
        args = ", ".join(str(arg) for arg in sorted(self.args, key=sort_argument))
        text = f"def {self.name}({args}) -> {self.rtype}: ..."
        if overload:
            text = f"@overload\n{text}"
        return text


def queryable_command_overloads(command: FetchedCommand) -> Iterable[ParsedCommand]:
    """Parse 'query' mode overloads."""
    for flag in command.iter_flags(FlagMode.QUERY):
        for flag_name, query in itertools.product(
            flag.names(),
            cast("tuple[str, ...]", get_args(QueryFlag.__value__)),
        ):
            yield ParsedCommand(
                name=command.name,
                args=(
                    Argument("args", "Any", ArgumentKind.VAR_ARG),
                    Argument(query, "Literal[True]", ArgumentKind.KW_ONLY_ARG),
                    Argument(flag_name, "Literal[True]", ArgumentKind.KW_ONLY_ARG),
                ),
                rtype=parse_flag(flag.type_name),
            )


def editable_command_overloads(command: FetchedCommand) -> Iterable[ParsedCommand]:
    """Parse 'edit' mode overloads."""
    args = [
        Argument(
            name,
            parse_flag(flag.type_name, multiuse=FlagMode.MULTI_USE in flag.modes),
            ArgumentKind.KW_ONLY_ARG,
            default="...",
        )
        for flag in command.iter_flags(FlagMode.EDIT)
        for name in flag.names()
        if name != "e"
    ]
    if not args:
        return

    for edit in cast("tuple[str, ...]", get_args(EditFlag.__value__)):
        yield ParsedCommand(
            name=command.name,
            args=(
                Argument("args", "Any", ArgumentKind.VAR_ARG),
                Argument(edit, "Literal[True]", ArgumentKind.KW_ONLY_ARG),
                *args,
            ),
            rtype=" | ".join(parse_rtypes(*command.return_types)),
        )


def creatable_command_overloads(command: FetchedCommand) -> Iterable[ParsedCommand]:
    """Parse 'create' mode overloads."""
    args = [
        Argument(
            name,
            parse_flag(flag.type_name, multiuse=FlagMode.MULTI_USE in flag.modes),
            ArgumentKind.KW_ONLY_ARG,
            default="...",
        )
        for flag in command.iter_flags(FlagMode.CREATE)
        for name in flag.names()
    ]
    if not args:
        return

    yield ParsedCommand(
        name=command.name,
        args=(Argument("args", "Any", ArgumentKind.VAR_ARG), *args),
        rtype=" | ".join(parse_rtypes(*command.return_types)),
    )


class ArgumentKind(enum.Enum):
    """Python Argument kinds."""

    ARG = enum.auto()  # `arg: str`
    VAR_ARG = enum.auto()  # `*arg: str`, can't have default
    KW_ONLY_ARG = enum.auto()  # `*_, arg: str`
    KWARG = enum.auto()  # `**arg: str`, can't have default


@dataclass(frozen=True)
class Argument:
    """A Python argument."""

    name: str
    annotation: str
    kind: ArgumentKind
    default: str | None = None

    def validate(self) -> None:
        """Raise exception if instance is invalid."""
        if (
            self.kind in {ArgumentKind.VAR_ARG, ArgumentKind.KW_ONLY_ARG}
            and self.default is not None
        ):
            msg = f"{self.kind} can't have default"
            raise ValueError(msg)

    def __str__(self) -> str:
        prefix: str = {
            ArgumentKind.VAR_ARG: "*",
            ArgumentKind.KWARG: "**",
        }.get(self.kind, "")
        default = f" = {self.default}" if self.default else ""
        return f"{prefix}{self.name}: {self.annotation}{default}"


def sort_argument(argument: Argument) -> SupportsRichComparison:
    """Argument sort key."""
    kind = {
        ArgumentKind.ARG: 0,
        ArgumentKind.VAR_ARG: 1,
        ArgumentKind.KW_ONLY_ARG: 2,
        ArgumentKind.KWARG: 3,
    }[argument.kind]

    mode = (
        0
        if argument.kind == ArgumentKind.KW_ONLY_ARG
        and argument.name in {"query", "q", "edit", "e"}
        else 1
    )

    return (kind, mode, argument.name)
