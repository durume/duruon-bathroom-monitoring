"""Executable wrapper so users can run `python main_runner.py --config config.yaml`.
This avoids relative import issues when not invoking as a package.
"""
import argparse, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'src')
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from src.main import run  # type: ignore

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default='config.yaml')
    ns = ap.parse_args()
    run(ns.config)

if __name__ == '__main__':
    main()