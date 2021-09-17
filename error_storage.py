from logzero import logger


class ErrorStorage:
    def __init__(self) -> None:
        self.storage = []

    def add(self, content, log: str = ""):
        # log引数を付けておくと自動でログ出力もされる.
        if log:
            if log == "i":
                logger.info(content)
            elif log == "w":
                logger.warning(content)
            elif log == "e":
                logger.error(content)
        self.storage.append(content)


error_storage = ErrorStorage()
