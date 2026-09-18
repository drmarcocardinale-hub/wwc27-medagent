"""Deprecated shim: use scripts/pull_air_quality.py --mode climatology."""
import runpy
import sys

if __name__ == "__main__":
    print("refresh_air_quality.py is now pull_air_quality.py --mode climatology", file=sys.stderr)
    sys.argv = [sys.argv[0], "--mode", "climatology", *sys.argv[1:]]
    runpy.run_path(__file__.replace("refresh_air_quality.py", "pull_air_quality.py"), run_name="__main__")
