#!/usr/bin/env python3
"""Grade the live higher-class and frozen surface-sun gallery cases."""

from sun_gallery_runtime import run_group


CASES = (
    "lunar-class9-sun135",
    "lunar-class11-sun135",
    "dense-class8-sun0",
    "frozen-sun0",
)


if __name__ == "__main__":
    raise SystemExit(run_group("class-variants", CASES))
