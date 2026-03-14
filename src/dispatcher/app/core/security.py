from fastapi import Request
def is_authorized(request: Request) -> bool:
    """Gelen istekte yetki-token olup olmadığını kontrol eder."""
    if request.url.path.startswith("/products"):
        if "Authorization" not in request.headers:
            return False
        return True
    