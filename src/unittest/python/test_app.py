import unittest

from ycappuccino.ui.model import Action, Endpoint, Field, Screen
from ycappuccino.ui_shell.app import ScreenApp


class FakeTransport:

    def __init__(self, result=None):
        self.result = result
        self.calls = []

    async def call(self, service, method, path, params, body):
        self.calls.append((service, method, path, params, body))
        return self.result


class TestScreenApp(unittest.IsolatedAsyncioTestCase):

    async def test_submits_valid_values_through_the_transport(self):
        transport = FakeTransport(result={"token": "abc"})
        screen = Screen(
            title="Login",
            fields=(Field(name="username", label="Username", required=True),),
            actions=(Action(name="submit", label="Submit", endpoint=Endpoint(service="login")),),
        )
        app = ScreenApp(screen, transport)

        async with app.run_test() as pilot:
            app.query_one("#field-username").value = "aurelien"
            await pilot.click("#action-submit")

        self.assertEqual(transport.calls, [("login", "POST", (), {}, {"username": "aurelien"})])
        self.assertEqual(app.last_result, {"token": "abc"})
        self.assertEqual(app.last_errors, {})

    async def test_invalid_values_are_not_sent_through_the_transport(self):
        transport = FakeTransport()
        screen = Screen(
            title="Login",
            fields=(Field(name="username", label="Username", required=True),),
            actions=(Action(name="submit", label="Submit", endpoint=Endpoint(service="login")),),
        )
        app = ScreenApp(screen, transport)

        async with app.run_test() as pilot:
            await pilot.click("#action-submit")

            error_label = app.query_one("#error-username")
            self.assertIn("required", str(error_label.content))

        self.assertEqual(transport.calls, [])
        self.assertIn("username", app.last_errors)

    async def test_boolean_field_round_trips(self):
        transport = FakeTransport()
        screen = Screen(
            title="s",
            fields=(Field(name="remember_me", label="Remember me", type="boolean", default=False),),
            actions=(Action(name="submit", label="Submit", endpoint=Endpoint(service="login")),),
        )
        app = ScreenApp(screen, transport)

        async with app.run_test() as pilot:
            app.query_one("#field-remember_me").value = True
            await pilot.click("#action-submit")

        self.assertEqual(transport.calls[0][4], {"remember_me": True})

    async def test_choice_field_round_trips(self):
        transport = FakeTransport()
        screen = Screen(
            title="s",
            fields=(Field(name="role", label="Role", type="choice", choices=("admin", "user"), required=True),),
            actions=(Action(name="submit", label="Submit", endpoint=Endpoint(service="login")),),
        )
        app = ScreenApp(screen, transport)

        async with app.run_test() as pilot:
            app.query_one("#field-role").value = "admin"
            await pilot.click("#action-submit")

        self.assertEqual(transport.calls[0][4], {"role": "admin"})

    async def test_number_field_is_parsed(self):
        transport = FakeTransport()
        screen = Screen(
            title="s",
            fields=(Field(name="count", label="Count", type="number"),),
            actions=(Action(name="submit", label="Submit", endpoint=Endpoint(service="login")),),
        )
        app = ScreenApp(screen, transport)

        async with app.run_test() as pilot:
            app.query_one("#field-count").value = "42"
            await pilot.click("#action-submit")

        self.assertEqual(transport.calls[0][4], {"count": 42})

    async def test_password_field_masks_input_and_round_trips(self):
        transport = FakeTransport()
        screen = Screen(
            title="s",
            fields=(Field(name="password", label="Password", type="password", required=True),),
            actions=(Action(name="submit", label="Submit", endpoint=Endpoint(service="login")),),
        )
        app = ScreenApp(screen, transport)

        async with app.run_test() as pilot:
            widget = app.query_one("#field-password")
            self.assertTrue(widget.password)
            widget.value = "secret"
            await pilot.click("#action-submit")

        self.assertEqual(transport.calls[0][4], {"password": "secret"})

    async def test_list_field_splits_on_commas(self):
        transport = FakeTransport()
        screen = Screen(
            title="s",
            fields=(Field(name="rights", label="Rights", type="list", required=True),),
            actions=(Action(name="submit", label="Submit", endpoint=Endpoint(service="login")),),
        )
        app = ScreenApp(screen, transport)

        async with app.run_test() as pilot:
            app.query_one("#field-rights").value = "read:book, write:book ,*:*"
            await pilot.click("#action-submit")

        self.assertEqual(transport.calls[0][4], {"rights": ["read:book", "write:book", "*:*"]})

    async def test_endpoint_method_and_path_are_forwarded(self):
        transport = FakeTransport()
        screen = Screen(
            title="s",
            fields=(),
            actions=(Action(
                name="run", label="Run",
                endpoint=Endpoint(service="scripts", method="POST", path=("run",), params={"scriptId": "hello"}),
            ),),
        )
        app = ScreenApp(screen, transport)

        async with app.run_test() as pilot:
            await pilot.click("#action-run")

        self.assertEqual(transport.calls, [("scripts", "POST", ("run",), {}, {"scriptId": "hello"})])


if __name__ == "__main__":
    unittest.main()
