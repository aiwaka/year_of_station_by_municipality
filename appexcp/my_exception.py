class ThisAppException(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class NonWikipediaLink(ThisAppException):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class ElementNotFound(ThisAppException):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class CannotOpenURL(ThisAppException):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class NoDateColumn(ThisAppException):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)
