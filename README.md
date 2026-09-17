# ycappuccino-ui-shell

Rend un `ycappuccino.ui.model.Screen` en un vrai terminal : un widget `Input`/`Checkbox`/`Select` par
`Field` (selon son `type`), un `Button` par `Action`, [`textual`](https://textual.textualize.io/) pour le
layout et la navigation clavier. Ce dépôt ne connaît que la description (`ycappuccino-ui`) : il ne
contient aucune logique d'écran particulière, seulement le rendu générique et le câblage vers
`ycappuccino.ui.transport.perform_action`.

Prérequis : lire le README de [ui](../ui/README.md) (le modèle `Screen`/`Field`/`Action`/`Endpoint`, la
validation, `Transport`/`perform_action`) — ce dépôt n'ajoute rien à ce modèle, il le rend.

## Mise en place

```bash
uv add --editable ../ui_shell
```

## Afficher un écran

```python
from ycappuccino.ui.loader import load_screen_yaml
from ycappuccino.ui_shell.app import run_screen

SCREEN_YAML = """
title: Connexion
fields:
  - name: username
    label: Nom d'utilisateur
    required: true
actions:
  - name: submit
    label: Se connecter
    endpoint:
      service: login
      method: POST
"""


class HttpTransport:
    """un Transport minimal, à titre d'exemple -- un déploiement réel utilise par exemple
    ycappuccino-client's HttpTransport dans un navigateur, ou un appel HTTP direct au même
    protocole {"status", "meta", "data"} que http_server (voir son README)."""

    async def call(self, service, method, path, params, body):
        raise NotImplementedError("brancher un vrai appel HTTP/service ici")


screen = load_screen_yaml(SCREEN_YAML)
# run_screen(screen, HttpTransport())  # bloquant, lance le vrai terminal -- pas appelé dans les tests
`run_screen(screen, transport)` est bloquant (lance la boucle `textual`) : ce n'est jamais ce qu'appelle un
test, voir plus bas.
```

## Une console entière : `ShellApplication`

`ycappuccino.ui_shell.application.ShellApplication(application, screens, transports, on_signed_in,
on_signed_out)` est une App textual qui rend une `ycappuccino.ui.application.Application` (voir le README
de `ui`), avec le même layout que `ui_web` dans un navigateur :

- avant connexion, l'écran de connexion seul ;
- ensuite une barre `#nav` sur deux lignes, pour tenir en 80 colonnes : un menu déroulant compact (`Select`)
  par section, large comme son titre, dont la liste ouverte montre chaque entrée en entier ; puis
  l'utilisateur connecté (`#user`) et « Se déconnecter » (`#sign-out`), au-dessus d'une zone défilante `#main` : le message de bienvenue, les
  écrans d'une entrée (pré-remplis depuis l'étape précédente), puis « Enregistré. ».

`screens` charge un `Screen` par son nom, `transports` associe un nom à un `Transport`. `.run()` la lance.

Un écran seul existe aussi comme widget, `ScreenForm(screen, transport, on_result)` : un appel refusé
affiche son message dans la ligne `#status`, un appel réussi est passé à `on_result`.

## Tester un écran

`ScreenApp` s'instancie et se pilote directement, sans `run_screen()`, via l'API de test de `textual`
(`app.run_test()` — un vrai `App`, un vrai arbre de widgets, pas de simulation) :

```python
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


class TestLogin(unittest.IsolatedAsyncioTestCase):
    async def test_submits_the_username(self):
        transport = FakeTransport(result={"token": "abc"})
        screen = Screen(
            title="Connexion",
            fields=(Field(name="username", label="Nom d'utilisateur", required=True),),
            actions=(Action(name="submit", label="Se connecter", endpoint=Endpoint(service="login")),),
        )
        app = ScreenApp(screen, transport)

        async with app.run_test() as pilot:
            app.query_one("#field-username").value = "aurelien"
            await pilot.click("#action-submit")

        self.assertEqual(transport.calls, [("login", "POST", (), {}, {"username": "aurelien"})])
        self.assertEqual(app.last_result, {"token": "abc"})
```

Seul le `Transport` est falsifié : la validation, le rendu des widgets et la navigation sont exercés pour
de vrai, pas simulés.

