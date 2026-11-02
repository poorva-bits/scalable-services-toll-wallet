class AppError(Exception):
    # Business/HTTP error carrying the fields of the agreed error JSON
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message