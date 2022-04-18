"""Message codec base definitions."""

class MessageCodec:
    def __init__(self) -> None:
        self.sin = None
        self.min = None
        self.structure = {}
