def check(req, mask32, cpms, ms):
    """The subject is masked, the truth is not: the mask cannot cancel."""
    got = mask32(cpms * ms)
    req(got == cpms * ms, "the recovered window equals the unbounded truth")
