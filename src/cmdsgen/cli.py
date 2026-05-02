from __future__ import annotations

import asyncio
import enum
import importlib.metadata
from io import StringIO
from typing import TYPE_CHECKING, Annotated, Final, Literal, cast

import cyclopts
from cyclopts import Parameter
from cyclopts.help import DefaultFormatter, PanelSpec
from cyclopts.types import StdioPath
from rich.box import MINIMAL
from rich.console import Console
from rich.table import Table

from cmdsgen.arguments import (
    ParsedCommand,
    creatable_command_overloads,
    editable_command_overloads,
    queryable_command_overloads,
)
from cmdsgen.fetch import FetchedCommand, fetch_commands
from cmdsgen.flag_parser import parse_flag
from cmdsgen.logging import setup_logging
from cmdsgen.rtype_parser import parse_rtype
from cmdsgen.utils import stderr_console

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

type Year = Literal[
    "2024",
    "2025",
    "2026",
    "2027",
]

MAYA_CMDS_ROOTS: Final[Mapping[Year, str]] = {
    "2024": "https://help.autodesk.com/cloudhelp/2024/ENU/Maya-Tech-Docs/CommandsPython/",
    "2025": "https://help.autodesk.com/cloudhelp/2025/ENU/Maya-Tech-Docs/CommandsPython/",
    "2026": "https://help.autodesk.com/cloudhelp/2026/ENU/Maya-Tech-Docs/CommandsPython/",
    "2027": "https://help.autodesk.com/cloudhelp/2027/ENU/Maya-Tech-Docs/CommandsPython/",
}

app = cyclopts.App(
    name="cmdsgen",
    version=lambda: importlib.metadata.version("cmdsgen"),
    version_flags=["--version", "-V"],
    error_console=stderr_console(),
    help_formatter=DefaultFormatter(
        panel_spec=PanelSpec(box=MINIMAL),
    ),
)


class Debug(enum.Enum):
    """Debug mode enumeration."""

    PARAMS = enum.auto()
    PARAMS_UNIQUE = enum.auto()
    RTYPE = enum.auto()
    RTYPE_UNIQUE = enum.auto()
    FLAGS = enum.auto()
    FLAGS_UNIQUE = enum.auto()


@app.default
def main(
    *,
    output: StdioPath = StdioPath("-"),  # noqa: B008
    cache: bool = False,
    verbose: Annotated[int, Parameter(name="-v", count=True)] = 0,
    commands: Annotated[
        list[str] | None,
        Parameter(name=("--command", "-c"), negative=""),
    ] = None,
    debug: Debug | None = None,
    year: Annotated[Year, Parameter(name=("--year", "-y"))] = "2026",
) -> None:
    """Build `maya.cmd` stubs from the Maya commands documentation.

    Args:
        output: Output file. If not specified, write output to stdout.
        cache: Cache fetched pages. Speed up subsequent runs and reduce network load.
        verbose: Use verbose output.
        commands: Include command, This option can be used multiple times.
            If not specified, all commands are scrapped.
        debug: Select an alternative output for debugging.
        year: Maya API release year.
    """
    setup_logging(verbose)

    url = MAYA_CMDS_ROOTS[year]
    parsed_commands = asyncio.run(
        fetch_commands(root=url, cached=cache, filter_commands=commands),
    )

    operation = {
        Debug.PARAMS: debug_params,
        Debug.PARAMS_UNIQUE: debug_params_unique,
        Debug.RTYPE: debug_rtype,
        Debug.RTYPE_UNIQUE: debug_rtype_unique,
        Debug.FLAGS: debug_flags,
        Debug.FLAGS_UNIQUE: debug_flags_unique,
        None: render_commands,
    }[debug]
    result = operation(parsed_commands)

    console = Console(file=StringIO(), highlight=False, markup=False, width=9000)
    console.print(result, no_wrap=False, soft_wrap=False)
    output.write_text(cast("StringIO", console.file).getvalue())


def render_commands(commands: Iterable[FetchedCommand]) -> str:
    """Render commands stubs."""
    lines: list[str] = [
        "from typing import Any, Literal, overload",
        "",
    ]
    for cmd in commands:
        lines.extend(o.to_string(overload=True) for o in render_command(cmd))
    return "\n".join(lines)


def render_command(command: FetchedCommand) -> list[ParsedCommand]:
    """Render commands overloads stubs."""
    overloads: list[ParsedCommand] = []
    overloads.extend(creatable_command_overloads(command))
    if command.is_queryable():
        overloads.extend(queryable_command_overloads(command))
    if command.is_editable():
        overloads.extend(editable_command_overloads(command))
    # TODO(tga): multiuse <- curve mel: -p 0 0 0 -p 1 1 1; py: p=[(0, 0, 0), (1, 1, 1)]
    return overloads


def debug_params(commands: Iterable[FetchedCommand]) -> Table:
    """Parse commands params."""
    table = Table.grid("command", "params", padding=(0, 2))
    for cmd in commands:
        if cmd.params:
            table.add_row(cmd.name, repr(cmd.params))
    return table


def debug_params_unique(commands: Iterable[FetchedCommand]) -> Table:
    """Parse commands unique params."""
    table = Table.grid("params")
    for row in {cmd.params for cmd in commands if cmd.params}:
        table.add_row(row)
    return table


def debug_rtype(commands: Iterable[FetchedCommand]) -> Table:
    """Parse commands return types."""
    table = Table.grid("command", "rtype", "python", padding=(0, 2))
    for cmd in commands:
        for rtype in cmd.return_types:
            parsed = parse_rtype(rtype)
            table.add_row(cmd.name, repr(rtype), repr(parsed))
    return table


def debug_rtype_unique(commands: Iterable[FetchedCommand]) -> Table:
    """Parse commands unique return types."""
    table = Table.grid("rtype", "python")
    for rtype in {rtype for cmd in commands for rtype in cmd.return_types}:
        parsed = parse_rtype(rtype)
        table.add_row(repr(rtype), repr(parsed))
    return table


def debug_flags(commands: Iterable[FetchedCommand]) -> Table:
    """Parse commands flags."""
    table = Table.grid("command", "flag", "type", "python", padding=(0, 2))
    for cmd in commands:
        for flag in cmd.flags:
            parsed = parse_flag(flag.type_name)
            table.add_row(cmd.name, flag.long_name, repr(flag.type_name), repr(parsed))
    return table


def debug_flags_unique(commands: Iterable[FetchedCommand]) -> Table:
    """Parse commands unique flags."""
    table = Table.grid("type", "python")
    for type_name in {flag.type_name for cmd in commands for flag in cmd.flags}:
        parsed = parse_flag(type_name)
        table.add_row(repr(type_name), repr(parsed))
    return table
