"""Renders a Screen as a textual widget (ScreenForm) or a whole App (ScreenApp): one widget per Field,
one Button per Action, validated then dispatched through perform_action()."""

from typing import Any, Awaitable, Callable

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label, Select

from ycappuccino.ui.model import Field, Screen
from ycappuccino.ui.transport import Transport, perform_action
from ycappuccino.ui.validation import validate_screen

_FIELD_PREFIX = "field-"
_ERROR_PREFIX = "error-"
_ACTION_PREFIX = "action-"

OnResult = Callable[[Any], Awaitable[None]]


class ScreenForm(Vertical):
    """One Screen as a widget: title, one widget per Field, one Button per Action, a status line. A valid
    action goes through perform_action(); a refused call shows its message in the status line, a
    successful one is handed to on_result."""

    def __init__(self, screen: Screen, transport: Transport, on_result: OnResult | None = None) -> None:
        super().__init__()
        self._screen = screen
        self._transport = transport
        self._on_result = on_result
        self.last_values: dict[str, Any] = {}
        self.last_errors: dict[str, str] = {}
        self.last_result: Any = None
        self.last_error: str | None = None

    def compose(self) -> ComposeResult:
        yield Label(self._screen.title, id="screen-title")
        for a_field in self._screen.fields:
            yield Label(a_field.label)
            yield _build_widget(a_field)
            yield Label("", id=f"{_ERROR_PREFIX}{a_field.name}")
        for action in self._screen.actions:
            yield Button(action.label, id=f"{_ACTION_PREFIX}{action.name}")
        yield Label("", id="status")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if not (event.button.id or "").startswith(_ACTION_PREFIX):
            return
        event.stop()
        action_name = event.button.id[len(_ACTION_PREFIX):]
        action = next(a for a in self._screen.actions if a.name == action_name)

        values = self._collect_values()
        errors = validate_screen(self._screen, values)
        self.last_values = values
        self.last_errors = errors
        self._render_errors(errors)
        if errors:
            return

        try:
            result = await perform_action(action, values, self._transport)
        except Exception as error:
            self._show_status(str(error) or type(error).__name__)
            return
        self._show_status(None)
        self.last_result = result
        if self._on_result is not None:
            await self._on_result(result)

    def _show_status(self, message: str | None) -> None:
        self.last_error = message
        self.query_one("#status", Label).update(message or "")

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


class ScreenApp(App):
    """a single Screen as a whole textual App"""

    def __init__(self, screen: Screen, transport: Transport) -> None:
        super().__init__()
        self.title = screen.title
        self._form = ScreenForm(screen, transport)

    def compose(self) -> ComposeResult:
        yield Header()
        yield self._form
        yield Footer()

    @property
    def last_values(self) -> dict[str, Any]:
        return self._form.last_values

    @property
    def last_errors(self) -> dict[str, str]:
        return self._form.last_errors

    @property
    def last_result(self) -> Any:
        return self._form.last_result


def _build_widget(a_field: Field) -> Widget:
    widget_id = f"{_FIELD_PREFIX}{a_field.name}"
    if a_field.type == "boolean":
        return Checkbox(value=bool(a_field.default), id=widget_id)
    if a_field.type == "choice":
        default = a_field.default if a_field.default in a_field.choices else Select.NULL
        return Select([(choice, choice) for choice in a_field.choices], value=default, id=widget_id)
    value = "" if a_field.default is None else str(a_field.default)
    return Input(value=value, password=a_field.type == "password", id=widget_id)


def _widget_value(a_field: Field, widget: Widget) -> Any:
    if a_field.type in ("boolean", "choice"):
        value = widget.value
        return None if value is Select.NULL else value
    if a_field.type == "number":
        return None if widget.value == "" else _to_number(widget.value)
    if a_field.type == "list":
        return [item.strip() for item in widget.value.split(",") if item.strip()]
    return widget.value


def _to_number(raw: str) -> int | float:
    try:
        return int(raw)
    except ValueError:
        return float(raw)


def run_screen(screen: Screen, transport: Transport) -> None:
    ScreenApp(screen, transport).run()
