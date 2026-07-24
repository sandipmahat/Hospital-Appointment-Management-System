"""
Centralized error-handling helpers.

Keeping this separate from the controllers is a small architectural choice:
route handlers stay focused on request/response and business logic, while
"what do we do when the database is unreachable" lives in exactly one place
instead of being copy-pasted into every view.

login() intentionally keeps its own inline try/except instead of using
this decorator: on a DB failure it needs to re-render its own form
(preserving whatever the user already typed) rather than redirect away,
which doesn't fit this decorator's redirect-based contract.
"""
from functools import wraps

import pymysql
from flask import current_app, flash, redirect, url_for

DEFAULT_DB_ERROR_MESSAGE = (
    "We're having trouble reaching the database right now. Please try again shortly."
)


def handle_db_errors(fallback_endpoint="auth.home", message=None):
    """Wrap a view so a database outage becomes a friendly flash message and
    redirect instead of bubbling up into an unhandled 500 response.
    """
    flash_message = message or DEFAULT_DB_ERROR_MESSAGE

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            try:
                return view(*args, **kwargs)
            except pymysql.MySQLError:
                current_app.logger.exception(
                    "Database error handling request in %s", view.__name__
                )
                flash(flash_message, "error")
                return redirect(url_for(fallback_endpoint))

        return wrapped

    return decorator
