"""CLI interface for pyknic-todo."""

# TODO: refactor this
# TODO: docs!
# TODO: tests!
# TODO: fields description

import asyncio
import sys
import typing

import pydantic
import pydantic_settings

from pyknic.lib.bellboy.console import BellboyConsole

from pyknic_todo.bellboy import ToDoCommandModel, BellBoyToDoCommand


class _ToDoCLISettings(
    ToDoCommandModel,
    pydantic_settings.BaseSettings,
    cli_parse_args=True,
    cli_use_class_docs_for_groups=True,
    cli_exit_on_error=True
):
    json_mode: pydantic_settings.CliImplicitFlag[bool] = pydantic.Field(
        default=False, description='!!!', validation_alias=pydantic.AliasChoices('json-mode')
    )


def main(
    argv: typing.Optional[typing.Sequence[str]] = None,
) -> int:

    class CustomCLISettings(
        _ToDoCLISettings,
        cli_parse_args=(argv if argv else True)
    ):
        pass

    cli_args = CustomCLISettings()  # type: ignore[call-arg]

    cmd_handler = BellBoyToDoCommand(cli_args)

    loop = asyncio.new_event_loop()

    result = loop.run_until_complete(cmd_handler.exec())

    if cli_args.json_mode:
        print(result.model_dump_json())
    else:
        console = BellboyConsole()
        console.process_result(result)

    return 0


if __name__ == "__main__":
    sys.exit(main())
