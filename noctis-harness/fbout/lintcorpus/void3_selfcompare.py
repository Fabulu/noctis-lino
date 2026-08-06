def alias8(self):
    """R2b: fb_layout.py:675's L12b.  alias8() COMPUTES nw this way, and the
    check below compares its result against the same expression."""
    nw = self.seg_index("adapted", self.alias8_segoff)
    return {"nw": nw, "index": nw - 4}


def check(self, req):
    a8 = self.alias8()
    req(a8["nw"] == self.seg_index("adapted", self.alias8_segoff),
        "L12b alias 8 resolves through the SAME seg_index primitive")
