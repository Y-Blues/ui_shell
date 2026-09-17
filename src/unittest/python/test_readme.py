"""every code block in README.md is reproduced here verbatim (run_screen itself is blocking --
never called from a test, see its own docstring) -- if this test fails, fix the code or the README,
whichever is wrong; the test is the source of truth."""

import unittest

from ycappuccino.ui.loader import load_screen_yaml
from ycappuccino.ui.model import Action, Endpoint, Field, Screen
from ycappuccino.ui_shell.app import ScreenApp

SCREEN_YAML = """
title: Sign in
fields:
  - name: username
    label: Username
    required: true
actions:
  - name: submit
    label: Sign in
    endpoint:
      service: login
      method: POST
"""


class HttpTransport:
    async def call(self, service, method, path, params, body):
        raise NotImplementedError("brancher un vrai appel HTTP/service ici")


class FakeTransport:
    def __init__(self, result=None):
        self.result = result
        self.calls = []

    async def call(self, service, method, path, params, body):
        self.calls.append((service, method, path, params, body))
        return self.result


class TestReadme(unittest.TestCase):

    def test_afficher_un_ecran_loads(self):
        screen = load_screen_yaml(SCREEN_YAML)

        self.assertEqual(screen.title, "Sign in")


class TestLogin(unittest.IsolatedAsyncioTestCase):

    async def test_submits_the_username(self):
        transport = FakeTransport(result={"token": "abc"})
        screen = Screen(
            title="Sign in",
            fields=(Field(name="username", label="Username", required=True),),
            actions=(Action(name="submit", label="Sign in", endpoint=Endpoint(service="login")),),
        )
        app = ScreenApp(screen, transport)

        async with app.run_test() as pilot:
            app.query_one("#field-username").value = "aurelien"
            await pilot.click("#action-submit")

        self.assertEqual(transport.calls, [("login", "POST", (), {}, {"username": "aurelien"})])
        self.assertEqual(app.last_result, {"token": "abc"})


if __name__ == "__main__":
    unittest.main()
