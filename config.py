"""Settings for the initial Flask shell.

MySQL settings are documented in .env.example. Database integration will be
added in the next learning milestone; this shell does not connect to MySQL.
"""

import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
