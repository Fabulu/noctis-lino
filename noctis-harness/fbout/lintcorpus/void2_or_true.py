def check(req, m, n):
    """R1: fb_wrap.py:416 -- the disjunction cannot be false."""
    req(m != n or True, "W6 the two multipliers differ")
