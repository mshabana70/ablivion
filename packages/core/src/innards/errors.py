"""Error taxonomy shared by the CLIs."""


class InputError(ValueError):
    """User-supplied input (config, data, paths, records) is invalid.

    CLIs catch this, print the message, and exit with status 2. Anything else
    that escapes is a bug and exits 1 with a traceback.
    """
