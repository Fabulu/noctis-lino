#!/usr/bin/env python3
"""Grade the live rocky and quartz surface-sun gallery cases."""

from sun_gallery_runtime import run_group


CASES = (
    "rocky-sun90",
    "rocky-class1-sun180",
    "rocky-class2-sun0",
    "quartz-sun228",
)


if __name__ == "__main__":
    raise SystemExit(run_group("rocky-quartz", CASES))
