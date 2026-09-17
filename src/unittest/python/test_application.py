import unittest

from textual.widgets import Button, Label, Select

from ycappuccino.ui.application import load_application_yaml
from ycappuccino.ui.model import Action, Endpoint, Field, Screen
from ycappuccino.ui_shell.application import ShellApplication

APPLICATION = load_application_yaml("""
title: Administration
login: {screen: login, transport: auth, user: user}
menu:
  - label: Rôles
    entries:
      - label: Créer un rôle
        steps:
          - {screen: role, transport: data}
  - label: Utilisateurs
    entries:
      - label: Créer un utilisateur
        steps:
          - {screen: credentials, transport: data}
          - {screen: profile, transport: data, prefill: {login: values.login, id: result._id}}
""")


def _screen(title, *names):
    return Screen(
        title=title,
        fields=tuple(Field(name=name, label=name) for name in names),
        actions=(Action(name="submit", label="Valider", endpoint=Endpoint(service=title)),),
    )


SCREENS = {
    "login": _screen("login", "user"),
    "role": _screen("role", "name"),
    "credentials": _screen("credentials", "login"),
    "profile": _screen("profile", "login", "id", "name"),
}


class Transport:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    async def call(self, service, method, path, params, body):
        if self.fail:
            raise ValueError("refused")
        self.calls.append((service, body))
        return {"_id": f"{service}-1"}


class TestShellApplication(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.auth = Transport()
        self.data = Transport()
        self.events = []

        async def signed_in(result):
            self.events.append(("in", result))

        async def signed_out():
            self.events.append(("out",))

        self.app = ShellApplication(
            APPLICATION, SCREENS.__getitem__, {"auth": self.auth, "data": self.data}, signed_in, signed_out
        )

    async def _submit(self, pilot, **values):
        for name, value in values.items():
            self.app.query_one(f"#field-{name}").value = value
        self.app.query_one("#action-submit").scroll_visible(animate=False)
        await pilot.pause()
        await pilot.click("#action-submit")
        await pilot.pause()

    async def _choose(self, pilot, section, entry):
        menu = next(select for select in self.app.query(Select) if select.prompt == section)
        group = next(group for group in APPLICATION.menu if group.label == section)
        menu.value = [menu_entry.label for menu_entry in group.entries].index(entry)
        await pilot.pause()

    def _text(self, selector):
        return str(self.app.query_one(selector, Label).content)

    async def test_before_login_the_bar_is_hidden(self):
        async with self.app.run_test() as pilot:
            await pilot.pause()

            self.assertFalse(self.app.query_one("#nav").display)
            self.assertEqual(len(self.app.query("#field-user")), 1)

    async def test_login_shows_the_bar_with_one_dropdown_per_section_the_user_and_the_welcome(self):
        async with self.app.run_test() as pilot:
            await pilot.pause()
            await self._submit(pilot, user="alice")

            self.assertEqual(self.events, [("in", {"_id": "login-1"})])
            self.assertTrue(self.app.query_one("#nav").display)
            self.assertEqual([select.prompt for select in self.app.query(Select)], ["Rôles", "Utilisateurs"])
            self.assertEqual(self._text("#user"), "alice")
            self.assertEqual(str(self.app.query_one("#sign-out", Button).label), "Se déconnecter")
            self.assertEqual(self._text("#message"), "Bienvenue alice.")

    async def test_a_refused_login_stays_on_the_login_screen(self):
        self.auth.fail = True
        async with self.app.run_test() as pilot:
            await pilot.pause()
            await self._submit(pilot, user="alice")

            self.assertEqual(self.events, [])
            self.assertEqual(self._text("#status"), "refused")
            self.assertFalse(self.app.query_one("#nav").display)

    async def test_an_entry_runs_its_step_resets_its_dropdown_and_keeps_the_bar(self):
        async with self.app.run_test() as pilot:
            await pilot.pause()
            await self._submit(pilot, user="alice")
            await self._choose(pilot, "Rôles", "Créer un rôle")

            self.assertTrue(self.app.query(Select).first().is_blank())
            await self._submit(pilot, name="editor")

            self.assertEqual(self.data.calls, [("role", {"name": "editor"})])
            self.assertEqual(self._text("#message"), "Enregistré.")
            self.assertTrue(self.app.query_one("#nav").display)

    async def test_chained_steps_are_prefilled_from_the_previous_one(self):
        async with self.app.run_test() as pilot:
            await pilot.pause()
            await self._submit(pilot, user="alice")
            await self._choose(pilot, "Utilisateurs", "Créer un utilisateur")
            await self._submit(pilot, login="bob")

            self.assertEqual(
                (self.app.query_one("#field-login").value, self.app.query_one("#field-id").value),
                ("bob", "credentials-1"),
            )
            await self._submit(pilot, name="Bob")
            self.assertEqual(self.data.calls[-1], ("profile", {"login": "bob", "id": "credentials-1", "name": "Bob"}))

    async def test_sign_out_hides_the_bar_and_returns_to_the_login_screen(self):
        async with self.app.run_test() as pilot:
            await pilot.pause()
            await self._submit(pilot, user="alice")
            await pilot.click("#sign-out")
            await pilot.pause()

            self.assertEqual(self.events[-1], ("out",))
            self.assertFalse(self.app.query_one("#nav").display)
            self.assertEqual(len(self.app.query("#field-user")), 1)


    async def test_at_80_columns_four_sections_the_user_and_sign_out_all_fit(self):
        wide = load_application_yaml("""
title: Administration
login: {screen: login, transport: auth, user: user}
menu:
  - {label: Mon compte, entries: [{label: a, steps: [{screen: role, transport: data}]}]}
  - {label: Organisations, entries: [{label: b, steps: [{screen: role, transport: data}]}]}
  - {label: Rôles et permissions, entries: [{label: c, steps: [{screen: role, transport: data}]}]}
  - {label: Utilisateurs, entries: [{label: Créer un utilisateur, steps: [{screen: role, transport: data}]}]}
""")

        async def noop(*args):
            pass

        app = ShellApplication(wide, SCREENS.__getitem__, {"auth": self.auth, "data": self.data}, noop, noop)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            app.query_one("#field-user").value = "administrator"
            await pilot.click("#action-submit")
            await pilot.pause()

            screen = app.screen.region
            for widget in [*app.query(Select), app.query_one("#user"), app.query_one("#sign-out")]:
                with self.subTest(widget=widget.id):
                    self.assertTrue(screen.contains_region(widget.region), f"{widget.id} at {widget.region}")
            for select in app.query(Select):
                with self.subTest(select=select.prompt):
                    # a one-line bar, each section label whole
                    self.assertEqual(select.region.height, 1)
                    self.assertGreaterEqual(select.region.width, len(select.prompt) + 2)
            users = app.query_one("#menu-3", Select)
            users.focus()
            await pilot.press("enter")
            await pilot.pause()
            overlay = users.query_one("SelectOverlay")
            # the open list shows each entry whole, on one line
            self.assertGreaterEqual(overlay.region.width, len("Créer un utilisateur") + 2)
            self.assertTrue(screen.contains_region(overlay.region), f"open list at {overlay.region}")


if __name__ == "__main__":
    unittest.main()
