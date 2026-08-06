def check(req, parse, alloc):
    """R3: fb_layout.py:564 -- got was built by iterating want."""
    want = parse(alloc)
    got = [r for r in want]
    req(want == got, "L1 layout order == farmalloc order")
