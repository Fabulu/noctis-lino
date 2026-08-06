def check(req, filter_one, data):
    """R3: fb_ref.c:947 -- want built with the very function under test."""
    want = filter_one(data)
    got = filter_one(data)
    req(want == got, "S2 the filter agrees with itself")
