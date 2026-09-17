"""
ShellApplication: renders a ycappuccino.ui.application.Application as one textual App -- the login screen,
then a navigation bar (#nav: one Select dropdown per menu section, the signed-in user, sign-out) above the
content (#main): the welcome, each entry's chained screens (prefilled from the previous one), the saved
message. ui_web's WebApplication renders the same Application in a browser.
"""

from typing import Any, Awaitable, Callable

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Button, Footer, Header, Label, Select

from ycappuccino.ui.application import Application, Step, prefill_values, with_defaults
from ycappuccino.ui.model import Screen
from ycappuccino.ui.transport import Transport
from ycappuccino.ui_shell.app import ScreenForm

_MENU_PREFIX = "menu-"


class ShellApplication(App):

    # the bar holds two rows, as the web one wraps: the sections sharing the width, then the user and sign-out
    DEFAULT_CSS = """
    #nav {
        height: auto;
        padding: 0 1;
        background: $boost;
        border-bottom: solid $accent;
    }
    #menus, #session {
        height: auto;
    }
    #menus Select {
        margin-right: 2;
    }
    #menus SelectOverlay {
        constrain: inside inside;
    }
    #session {
        align-horizontal: right;
    }
    #user {
        margin-right: 2;
        color: $accent;
        text-style: bold;
    }
    #main {
        padding: 1 2;
    }
    """

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
        with Vertical(id="nav"):
            with Horizontal(id="menus"):
                for index, group in enumerate(self._application.menu):
                    menu = Select(
                        [(entry.label, entry_index) for entry_index, entry in enumerate(group.entries)],
                        prompt=group.label,
                        id=f"{_MENU_PREFIX}{index}",
                        compact=True,
                    )
                    # as wide as its label and arrow, like a menu of a site bar
                    menu.styles.width = len(group.label) + 4
                    yield menu
            with Horizontal(id="session"):
                yield Label("", id="user")
                yield Button(self._application.sign_out, id="sign-out", compact=True)
        yield VerticalScroll(id="main")
        yield Footer()

    async def on_mount(self) -> None:
        for index, group in enumerate(self._application.menu):
            # the open list as wide as its longest entry, each shown whole
            overlay = self.query_one(f"#{_MENU_PREFIX}{index}", Select).query_one("SelectOverlay")
            overlay.styles.width = max(len(text) for text in [group.label, *(entry.label for entry in group.entries)]) + 4
        await self.show_login()

    async def show_login(self) -> None:
        self.query_one("#nav").display = False
        login = self._application.login

        async def signed_in(result: Any) -> None:
            await self._on_signed_in(result)
            user = form.last_values.get(self._application.user_field) if self._application.user_field else None
            self._later(self.show_home, user)

        form = ScreenForm(self._screens(login.screen), self._transports[login.transport], signed_in)
        await self._show(form)

    async def show_home(self, user: str | None) -> None:
        self.query_one("#user", Label).update(user or "")
        self.query_one("#nav").display = True
        await self._show(Label(self._application.welcome_text(user), id="message"))

    async def on_select_changed(self, event: Select.Changed) -> None:
        select_id = event.select.id or ""
        if not select_id.startswith(_MENU_PREFIX) or event.select.is_blank():
            return
        entry = self._application.menu[int(select_id[len(_MENU_PREFIX):])].entries[event.value]
        event.select.clear()
        self._later(self._show_step, entry.steps, 0, {}, None)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "sign-out":
            await self._on_signed_out()
            self._later(self.show_login)

    async def _show_step(self, steps: tuple[Step, ...], index: int, previous_values: dict, previous_result: Any) -> None:
        step = steps[index]
        screen = with_defaults(self._screens(step.screen), **prefill_values(step, previous_values, previous_result))

        async def done(result: Any) -> None:
            if index + 1 < len(steps):
                self._later(self._show_step, steps, index + 1, form.last_values, result)
            else:
                self._later(self._show, Label(self._application.saved, id="message"))

        form = ScreenForm(screen, self._transports[step.transport], done)
        await self._show(form)

    def _later(self, show: Callable[..., Awaitable[None]], *args: Any) -> None:
        # never replace the widget whose button handler is still running
        self.call_later(show, *args)

    async def _show(self, widget: Widget) -> None:
        main = self.query_one("#main", VerticalScroll)
        await main.remove_children()
        await main.mount(widget)
