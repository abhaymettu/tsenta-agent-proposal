"""CORE_FACTORY for 552's oracle (stress-fixture/test_contract.py): the real core over an in-process sandbox.
Run: CORE_FACTORY=tests.oracle_factory:make PYTHONPATH=.:<stress-fixture dir> python3 -m unittest test_contract"""
from core.engine import Core
from core.sandbox import Sandbox


def make(seed_path):
    return Core(seed_path, Sandbox())
