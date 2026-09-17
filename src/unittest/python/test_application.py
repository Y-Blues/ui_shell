import unittest

from textual.widgets import Button, Label

from ycappuccino.ui.application import load_application_yaml
from ycappuccino.ui.model import Action, Endpoint, Field, Screen
from ycappuccino.ui_shell.application import ShellApplication

APPLICATION = load_application_yaml("""
title: Administration
login: {screen: login, transport: auth}
menu:
  - label: Créer un rôle
    steps:
      - {screen: role, transport: data}
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

    def _buttons(self):
        return [str(button.label) for button in self.app.query(Button)]

    async def _submit(self, pilot, **values):
        for name, value in values.items():
            self.app.query_one(f"#field-{name}").value = value
        await pilot.click("#action-submit")
        await pilot.pause()

    async def _choose(self, pilot, label):
        button = next(button for button in self.app.query(Button) if str(button.label) == label)
        await pilot.click(f"#{button.id}")
        await pilot.pause()

    async def test_login_then_the_menu_with_its_entries_and_sign_out(self):
        async with self.app.run_test() as pilot:
            await pilot.pause()
            await self._submit(pilot, user="alice")

            self.assertEqual(self.events, [("in", {"_id": "login-1"})])
            self.assertEqual(self._buttons(), ["Créer un rôle", "Créer un utilisateur", "Se déconnecter"])
            self.assertEqual(str(self.app.query_one("#menu-title", Label).content), "Administration")

    async def test_a_refused_login_stays_on_the_login_screen(self):
        self.auth.fail = True
        async with self.app.run_test() as pilot:
            await pilot.pause()
            await self._submit(pilot, user="alice")

            self.assertEqual(self.events, [])
            self.assertEqual(str(self.app.query_one("#status", Label).content), "refused")

    async def test_an_entry_runs_its_step_then_shows_saved_and_back_to_the_menu(self):
        async with self.app.run_test() as pilot:
            await pilot.pause()
            await self._submit(pilot, user="alice")
            await self._choose(pilot, "Créer un rôle")
            await self._submit(pilot, name="editor")

            self.assertEqual(self.data.calls, [("role", {"name": "editor"})])
            self.assertEqual(str(self.app.query_one("#message", Label).content), "Enregistré.")
            await self._choose(pilot, "Retour au menu")
            self.assertIn("Créer un rôle", self._buttons())

    async def test_chained_steps_are_prefilled_from_the_previous_one(self):
        async with self.app.run_test() as pilot:
            await pilot.pause()
            await self._submit(pilot, user="alice")
            await self._choose(pilot, "Créer un utilisateur")
            await self._submit(pilot, login="bob")

            self.assertEqual(
                (self.app.query_one("#field-login").value, self.app.query_one("#field-id").value),
                ("bob", "credentials-1"),
            )
            await self._submit(pilot, name="Bob")
            self.assertEqual(self.data.calls[-1], ("profile", {"login": "bob", "id": "credentials-1", "name": "Bob"}))

    async def test_sign_out_returns_to_the_login_screen(self):
        async with self.app.run_test() as pilot:
            await pilot.pause()
            await self._submit(pilot, user="alice")
            await self._choose(pilot, "Se déconnecter")

            self.assertEqual(self.events[-1], ("out",))
            self.assertEqual(len(self.app.query("#field-user")), 1)


if __name__ == "__main__":
    unittest.main()
