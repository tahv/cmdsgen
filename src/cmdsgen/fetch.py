from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from bs4 import BeautifulSoup
from bs4.element import NavigableString

from cmdsgen.utils import Session, fetch, fetch_batched, logger

if TYPE_CHECKING:
    from collections.abc import Iterable

    from aiohttp import ClientSession

IGNORE_CMD: tuple[str] = ("eval",)


@dataclass(frozen=True)
class FetchedCommand:
    """A raw fetched command."""

    name: str
    params: str | None
    """The parsed param name at the beginning of the synopsis."""
    flags: tuple[FetchedFlag, ...]
    return_types: list[str]
    modes: tuple[CommandMode, ...]

    def is_editable(self) -> bool:
        """Whether the command is editable."""
        return CommandMode.EDITABLE in self.modes

    def is_queryable(self) -> bool:
        """Whether the command is queryable."""
        return CommandMode.QUERYABLE in self.modes

    def iter_flags(self, mode: FlagMode) -> Iterable[FetchedFlag]:
        """Iter flags with given `mode`."""
        for flag in self.flags:
            if mode in flag.modes:
                yield flag


@dataclass(frozen=True)
class FetchedFlag:
    """A raw fetched command flag."""

    long_name: str
    short_name: str | None
    type_name: str
    """The native mel type, needs to be converted to Python type."""
    modes: tuple[FlagMode, ...]

    def names(self) -> tuple[str, ...]:
        """Return flag possible long and short names."""
        if self.short_name is None:
            return (self.long_name,)
        return (self.long_name, self.short_name)


class CommandMode(enum.Enum):
    """Function mode enum."""

    EDITABLE = enum.auto()
    QUERYABLE = enum.auto()

    @staticmethod
    def from_string(s: str) -> CommandMode:
        """Initialize `CommandMode` from parsed string."""
        match s:
            case "editable":
                return CommandMode.EDITABLE
            case "queryable":
                return CommandMode.QUERYABLE
            case _:
                raise ValueError(s)


class FlagMode(enum.Enum):
    """Flag mode enum."""

    CREATE = enum.auto()
    """Flag can appear in Create mode of command.

    When in this mode, the command creates the named object in the schene graph.
    """
    EDIT = enum.auto()
    """Flag can appear in Edit mode of command.

    This mode is activated with the `--edit/-e` flag
    and change one or more properties of the named object.
    """
    QUERY = enum.auto()
    """Flag can appear in Query mode of command.

    This mode is activated with the `--query/-q` flag
    and returns the value of a property of the named object.
    """
    MULTI_USE = enum.auto()
    """Flag can have multiple arguments, passed either as a tuple or a list."""

    @staticmethod
    def from_title(s: str) -> FlagMode:
        """Return `FlagProperty` from the tag's title attr."""
        match s:
            case "create":
                return FlagMode.CREATE
            case "edit":
                return FlagMode.EDIT
            case "query":
                return FlagMode.QUERY
            case "multiuse":
                return FlagMode.MULTI_USE
            case _:
                raise ValueError(s)


async def fetch_commands(
    *,
    root: str,
    cached: bool = True,
    filter_commands: list[str] | None = None,
) -> list[FetchedCommand]:
    """Fetch and parse maya commands."""
    async with Session(cached=cached) as session:
        commands = await _fetch_command_urls(session=session, root=root)

    commands = {k: commands[k] for k in commands if k not in IGNORE_CMD}

    if filter_commands:
        try:
            commands = {k: commands[k] for k in filter_commands}
        except KeyError:
            missing = ", ".join(set(filter_commands) - commands.keys())
            msg = f"Command not found: {missing}"
            raise ValueError(msg) from None

    parsed: list[FetchedCommand] = []
    async with Session(cached=cached) as session:
        async for _, text in fetch_batched(
            session=session,
            urls=commands.values(),
            n=10,
        ):
            page = BeautifulSoup(text, features="html.parser")
            maya_name = _parse_command_name(page)

            is_obsolete = "(obsolete)" in maya_name.lower()
            if is_obsolete:
                logger.info("Skipping obsolete command `%s`", maya_name)
                continue

            parsed.append(
                FetchedCommand(
                    name=maya_name,
                    flags=_parse_command_flags(page),
                    return_types=_parse_command_return(page),
                    modes=_parse_command_modes(page),
                    params=_parse_command_params(page),
                ),
            )

            logger.info("Parsed command `%s`", maya_name)

    return parsed


async def _fetch_command_urls(session: ClientSession, root: str) -> dict[str, str]:
    root = root.removesuffix("/")
    _, text = await fetch(session, f"{root}/index_all.html")
    result: dict[str, str] = {}
    for tag in BeautifulSoup(text, features="html.parser").select("a"):
        href = tag.attrs["href"]
        assert isinstance(href, str)
        command, _, _ = href.partition(".")
        result[command] = f"{root}/{href}"
    return result


def _parse_command_params(page: BeautifulSoup) -> str | None:
    synopsis_tag = page.select_one("p#synopsis")
    assert synopsis_tag is not None

    synopsis_text = synopsis_tag.get_text(strip=True)
    args_match = re.search(r"\(([^=]+?)[,\)]", synopsis_text)
    if not args_match:
        return None

    return args_match.group(1).strip()


def _parse_command_modes(page: BeautifulSoup) -> tuple[CommandMode, ...]:
    tag = page.select_one("p#synopsis + p")
    assert tag is not None

    matches: list[str] = re.findall(
        r"(?<!NOT) (editable|queryable)",
        tag.get_text(strip=True),
    )
    result = [CommandMode.from_string(m) for m in matches]
    return tuple(result)


def _parse_command_name(page: BeautifulSoup) -> str:
    """Returns command name at the top of the page."""
    tag = page.select_one("div#banner h1")

    if tag is None:
        msg = "Name not found"
        raise RuntimeError(msg)

    text = tag.find(text=True)
    assert isinstance(text, NavigableString)
    return text.strip()


def _parse_command_return(page: BeautifulSoup) -> list[str]:
    result: list[str] = []

    # Most of the pages have a table of [return_type, return_desc]
    for tr_tag in page.select('h2:has(a[name="hReturn"]) + table tr'):
        columns = tr_tag.select("td")
        if len(columns) == 1:
            continue
        type_tag, _ = tr_tag.select("td")
        result.append(type_tag.get_text(strip=True))

    # Some pages, like addAttr, have 2 paragraph instead
    if not result:
        type_tag = page.select_one('h2:has(a[name="hReturn"]) + p')  # type: ignore[assignment]
        if not type_tag:
            msg = "Return type not found"
            raise RuntimeError(msg)
        result.append(type_tag.get_text(strip=True))

    return result


def _parse_command_flags(page: BeautifulSoup) -> tuple[FetchedFlag, ...]:
    """Parse the table describing the keyword arguments of the function."""
    result: list[FetchedFlag] = []

    for tr_tag in page.select("a ~ table tr:has(> td:first-child:nth-last-child(3))"):
        name_elem, type_elem, prop_elem = tr_tag.select("td")

        long_name, short_name = _match_flag_names(name_elem.get_text(strip=True))
        type_name = type_elem.get_text(strip=True)
        modes = tuple(
            FlagMode.from_title(cast("str", tag.attrs["title"]))
            for tag in prop_elem.select("img")
        )

        if short_name == long_name:
            short_name = None

        flag = FetchedFlag(
            long_name=long_name,
            short_name=short_name,
            type_name=type_name,
            modes=modes,
        )
        result.append(flag)

    return tuple(result)


def _match_flag_names(raw_name: str) -> tuple[str, str | None]:
    """Parse a str `'longName(shortName)'` into a tuple `('longName', 'shortName')`."""
    match = re.match(r"(\w+)\((\w+)?\)", raw_name)
    assert match is not None
    long_name = match.group(1)
    short_name = match.group(2)
    return long_name, short_name
