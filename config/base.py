import os

class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "you-should-override-this")
    # any other shared defaults, e.g. pagination, logging levels, etc.
