"""
ShellApplication: renders a ycappuccino.ui.application.Application as one textual App -- the login screen,
then the menu, each entry's chained screens (prefilled from the previous one), the saved message and
sign-out. ui_web's WebApplication renders the same Application in a browser.
"""

from typing import Any, Awaitable, Callable

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Button, Footer, Header, Label

from ycappuccino.ui.application import Application, Step, prefill_values, with_defaults
from ycappuccino.ui.model import Screen
from ycappuccino.ui.transport import Transport
from ycappuccino.ui_shell.app import ScreenForm

Choice = Callable[[], Awaitable[None]]


class _Choices(Vertical):
    """a title or message, then one button per choice"""

    def __init__(self, text: str, text_id: str, choices: list[tuple[str, Choice]]) -> None:
        super().__init__()
        self._text = text
        self._text_id = text_id
        self._choices = {f"choice-{index}": choice for index, (_, choice) in enumerate(choices)}
        self._labels = [label for label, _ in choices]

    def compose(self) -> ComposeResult:
        yield Label(self._text, id=self._text_id)
        for index, label in enumerate(self._labels):
            yield Button(label, id=f"choice-{index}")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        await self._choices[event.button.id]()


class ShellApplication(App):

    def __init__(
        self,
        application: Application,
        screens: Callable[[str], Screen],
        transports: dict[str, Transport],
        on_signed_in: Callable[[Any], Awaitable[None]],
        on_signed_out: Callable[[], Awaitable[None]],
    ) -> None:
        """on_signed_in receives the login step's result (e.g. a token), on_signed_out runs on sign-out"""
        super().__init__()
        self.title = application.title
        self._application = application
        self._screens = screens
        self._transports = transports
        self._on_signed_in = on_signed_in
        self._on_signed_out = on_signed_out

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(id="main")
        yield Footer()

    async def on_mount(self) -> None:
        await self.show_login()

    async def show_login(self) -> None:
        login = self._application.login

        async def signed_in(result: Any) -> None:
            await self._on_signed_in(result)
            self._later(self.show_menu)

        await self._show(ScreenForm(self._screens(login.screen), self._transports[login.transport], signed_in))

    async def show_menu(self) -> None:
        choices = [(entry.label, self._runner(entry.steps)) for entry in self._application.menu]
        choices.append((self._application.sign_out, self._sign_out))
        await self._show(_Choices(self._application.title, "menu-title", choices))

    def _runner(self, steps: tuple[Step, ...]) -> Choice:
        async def run() -> None:
            self._later(self._show_step, steps, 0, {}, None)

        return run

    async def _show_step(self, steps: tuple[Step, ...], index: int, previous_values: dict, previous_result: Any) -> None:
        step = steps[index]
        screen = with_defaults(self._screens(step.screen), **prefill_values(step, previous_values, previous_result))

        async def done(result: Any) -> None:
            if index + 1 < len(steps):
                self._later(self._show_step, steps, index + 1, form.last_values, result)
            else:
                self._later(self._show_saved)

        form = ScreenForm(screen, self._transports[step.transport], done)
        await self._show(form)

    async def _show_saved(self) -> None:
        async def back() -> None:
            self._later(self.show_menu)

        await self._show(_Choices(self._application.saved, "message", [(self._application.back, back)]))

    async def _sign_out(self) -> None:
        await self._on_signed_out()
        self._later(self.show_login)

    def _later(self, show: Callable[..., Awaitable[None]], *args: Any) -> None:
        # never replace the widget whose button handler is still running
        self.call_later(show, *args)

    async def _show(self, widget: Widget) -> None:
        main = self.query_one("#main", Vertical)
        await main.remove_children()
        await main.mount(widget)
