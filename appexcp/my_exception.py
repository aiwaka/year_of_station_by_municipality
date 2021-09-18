class ThisAppException(Exception):
    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class NonWikipediaLink(ThisAppException):
    # リンクがwikipedia出ない場合の例外.
    def __init__(self, man_name: str, link: str) -> None:
        message = "link is not wikipedia : " + link + " [" + man_name + "]"
        super().__init__(message)


class ElementNotFound(ThisAppException):
    # 自治体ページに鉄道の項が存在しない場合の例外
    def __init__(self, man_name: str) -> None:
        message = f"railroad section not found : {man_name}"
        super().__init__(message)


class CannotOpenURL(ThisAppException):
    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class NoDateColumn(ThisAppException):
    def __init__(self, message: str = "") -> None:
        super().__init__(message)
