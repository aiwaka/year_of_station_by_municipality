class ErrorStorage:
    def __init__(self) -> None:
        self.storage = []

    def add(self, content):
        self.storage.append(content)


error_storage = ErrorStorage()
