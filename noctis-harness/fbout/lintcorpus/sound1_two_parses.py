def check(req, parse_a, parse_b, text):
    """Two structurally different parses of one source: a real claim."""
    want = parse_a(text)
    got = parse_b(text)
    req(want == got, "L1 layout order, two independent parses")
