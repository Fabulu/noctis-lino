#!/usr/bin/env python3
"""Grade the live class-1/3/4/5 lunar surface-sun gallery cases."""

from sun_gallery_runtime import run_group


CASES = (
    "lunar-class1-sun50",
    "lunar-class3-sun75",
    "lunar-class4-sun135",
    "lunar-class5-sun270",
)


if __name__ == "__main__":
    raise SystemExit(run_group("lunar-classes", CASES))
