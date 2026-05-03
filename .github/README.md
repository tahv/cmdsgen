> [!IMPORTANT]
> Development takes place on GitLab:
> [gitlab.com/tahv/cmdsgen](https://gitlab.com/tahv/cmdsgen).

# cmdsgen

[![Source](https://img.shields.io/badge/source-%23fc6d25?logo=gitlab&logoColor=white)](https://gitlab.com/tahv/cmdsgen)

Generate stubs for `maya.cmds` from the official
[Maya Commands Documentation](https://help.autodesk.com/cloudhelp/2027/ENU/Maya-Tech-Docs/CommandsPython/).
Used by [types-maya](https://pypi.org/project/types-maya/).

## Usage

Generate stubs for all commands and output to a `cmds.pyi` file.

```console
cmdsgen > cmds.pyi
```

> [!NOTE]
> This package is not published to PyPI.
> It can be installed directly from GitLab
> using [uvx](https://docs.astral.sh/uv/guides/tools/#requesting-different-sources).
>
> ```console
> uvx --from git+https://gitlab.com/tahv/cmdsgen@main cmdsgen > cmds.pyi
> ```

## Contributing

Contributions of any kind are welcome.
Please [open an issue](https://gitlab.com/tahv/cmdsgen/-/issues),
or open a [merge request](https://gitlab.com/tahv/cmdsgen/-/merge_requests).

### Local development environment

The project virtual environment can be created
with [uv](https://docs.astral.sh/uv/).

```console
uv sync
```

Or with pip 25.1 (that added support for
[PEP 735](https://peps.python.org/pep-0735/) Dependency Groups)
or newer and install the dependencies manually.

```console
pip install --editable . --group dev
```
