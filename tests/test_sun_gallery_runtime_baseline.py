#!/usr/bin/env python3
"""Grade the live baseline surface-sun gallery cases."""

from sun_gallery_runtime import run_group


CASES = (
    "hab-sun270",
    "thin-sun45",
    "lunar-sun0",
    "dense-sun0",
)


if __name__ == "__main__":
    raise SystemExit(run_group("baseline", CASES))
