def check(req, measured, bmp_bytes):
    """Graded against an artifact this project did not make."""
    req(all(b % 4 == 0 for b in bmp_bytes) and measured, "v*4, not shift-or")
