"""
ScreenApp: renders a ycappuccino.ui.model.Screen as a real textual.app.App -- one Input/Checkbox/
Select widget per Field (by Field.type), one Button per Action. ycappuccino.ui.validation
.validate_screen() runs before any Action fires; ycappuccino.ui.transport.perform_action() is the
one and only way an Action is called -- this module never invokes application code directly, only
the generic dispatch, with a Transport supplied by whoever deploys the screen.
"""

from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label, Select

from ycappuccino.ui.model import Field, Screen
from ycappuccino.ui.transport import Transport, perform_action
from ycappuccino.ui.validation import validate_screen

_FIELD_PREFIX = "field-"
_ERROR_PREFIX = "error-"
_ACTION_PREFIX = "action-"


class ScreenApp(App):

    def __init__(self, screen: Screen, transport: Transport):
        super().__init__()
        self._screen = screen
        self._transport = transport
        self.title = screen.title
        self.last_values: dict[str, Any] = {}
        self.last_errors: dict[str, str] = {}
        self.last_result: Any = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            for a_field in self._screen.fields:
                yield Label(a_field.label)
                yield _build_widget(a_field)
                yield Label("", id=f"{_ERROR_PREFIX}{a_field.name}")
            for action in self._screen.actions:
                yield Button(action.label, id=f"{_ACTION_PREFIX}{action.name}")
        yield Footer()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        action_name = event.button.id[len(_ACTION_PREFIX):]
        action = next(a for a in self._screen.actions if a.name == action_name)

        values = self._collect_values()
        errors = validate_screen(self._screen, values)
        self.last_values = values
        self.last_errors = errors
        self._render_errors(errors)
        if errors:
            return

        self.last_result = await perform_action(action, values, self._transport)

    def _collect_values(self) -> dict[str, Any]:
        values = {}
        for a_field in self._screen.fields:
            widget = self.query_one(f"#{_FIELD_PREFIX}{a_field.name}")
            values[a_field.name] = _widget_value(a_field, widget)
        return values

    def _render_errors(self, errors: dict[str, str]) -> None:
        for a_field in self._screen.fields:
            label = self.query_one(f"#{_ERROR_PREFIX}{a_field.name}", Label)
            label.update(errors.get(a_field.name, ""))


def _build_widget(a_field: Field):
    widget_id = f"{_FIELD_PREFIX}{a_field.name}"
    if a_field.type == "boolean":
        return Checkbox(value=bool(a_field.default), id=widget_id)
    if a_field.type == "choice":
        default = a_field.default if a_field.default in a_field.choices else Select.NULL
        return Select([(choice, choice) for choice in a_field.choices], value=default, id=widget_id)
    value = "" if a_field.default is None else str(a_field.default)
    return Input(value=value, password=a_field.type == "password", id=widget_id)


def _widget_value(a_field: Field, widget) -> Any:
    if a_field.type in ("boolean", "choice"):
        value = widget.value
        return None if value is Select.NULL else value
    if a_field.type == "number":
        return None if widget.value == "" else _to_number(widget.value)
    return widget.value


def _to_number(raw: str):
    try:
        return int(raw)
    except ValueError:
        return float(raw)


def run_screen(screen: Screen, transport: Transport) -> None:
    ScreenApp(screen, transport).run()
