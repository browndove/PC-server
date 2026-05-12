"""
Fallback JWT signing secret when JWT_SECRET is not set in the environment.

Railway / local: set JWT_SECRET in Variables to override. Do not commit production
secrets to public repos unless you accept the risk.
"""

DEFAULT_JWT_SECRET = "P9yOpywkxb6xMzYULb+gpT0tJ/4Tc7dXHSwbHePKdD4="
