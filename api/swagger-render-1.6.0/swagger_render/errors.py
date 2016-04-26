import click


class SRError(click.ClickException):
    pass


class InvalidReferenceError(SRError):
    def __init__(self, full, ref_name):
        super().__init__("Can't resolve reference {!r}. Failed to find {!r}".format(full, ref_name))
