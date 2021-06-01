"""
Preferences framework.

Allows for generic site-wide preferences stored in cookies.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from typing import Protocol, runtime_checkable

from django.http import HttpRequest
from django.template import Context
from django.utils.text import camel_case_to_spaces


class PreferenceConfigurationError(Exception):
    """
    Raised when a preference is not configured properly.
    Client code should probably NOT catch this.
    """


@dataclass
class Preference:
    """
    A user preference, usually for the display of content on the website.
    """

    # internal name
    name: str

    # A mapping of all possible choices for this preference,
    # to user-readable labels.
    # {
    #     "internalname": "user-readable label"
    # }
    choices: dict[str, str]

    # Which one of the choices is the default
    default: str

    # Name used for the cookie
    cookie_name: str

    def current_value_from_template_context(self, context: Context) -> str:
        if hasattr(context, "request"):
            return self.current_value_from_request(context.request)
        else:
            return self.default

    def current_value_from_request(self, request: HttpRequest) -> str:
        return request.COOKIES.get(self.cookie_name, self.default)


def all_preferences():
    """
    Return all preferences registered in this site.
    """
    return _registry().items()


def register_preference(declaration) -> Preference:
    """
    Keep track of a preference in the currently running site.

    Usage:

        @register_preference
        class MyPreference:
            choices = ...
            default = ...

            name = "my_preference"  # optional; inferred from class name
            cookie_name = "mypref"  # optional: inferred from name
    """

    if isinstance(declaration, type):
        name = _snake_case_name_from_class(declaration)
    else:
        raise NotImplementedError

    # Validate the preference
    try:
        choices = dict(declaration.choices)  # type: ignore
    except AttributeError:
        raise PreferenceConfigurationError(
            "declaration must declare a dictionary of choices"
        )

    try:
        default = declaration.default  # type: ignore
    except AttributeError:
        raise PreferenceConfigurationError("Preference MUST declare a default")

    if default not in choices:
        raise PreferenceConfigurationError(
            f"Default does not exist in preference's choices: " f"{default=} {choices=}"
        )

    try:
        cookie_name = declaration.cookie_name  # type: ignore
    except AttributeError:
        cookie_name = name

    pref = Preference(
        name=name, choices=choices, default=default, cookie_name=cookie_name
    )

    _registry()[name] = pref

    return pref


@cache
def _registry() -> dict[str, Preference]:
    """
    Contains all Preference blueprints
    """
    return {}


def _snake_case_name_from_class(cls: type):
    return camel_case_to_spaces(cls.__name__).replace(" ", "_")
