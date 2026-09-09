"""The `--rbb-policy` default, changed to `amortized` on 2 Sep 2026 (§P0.17).

The standing rule was explicit about what would justify the change: *"`stock` ships as the default
so an un-flagged re-run reproduces the recorded catalogue... it wants to ride one deliberate
catalogue re-run rather than drift in."* §P0.16's four-arm re-run is that run, and its arm B -> arm
C step isolates this flag across 145 catalogue points: **no verdict flips in either direction**.
§P0.10 had already settled the semantics from `McPAT/core.cc`.

What must not break: the recorded catalogue stays reproducible under `--rbb-policy stock`.
"""
import argparse

from HotGauge.thermal.rbb import (add_rbb_argument, RBB_POLICIES, DEFAULT_RBB_POLICY)


def test_default_constant_is_amortized():
    assert DEFAULT_RBB_POLICY == 'amortized'
    assert set(RBB_POLICIES) == {'stock', 'amortized'}


def test_add_rbb_argument_uses_the_new_default():
    ap = argparse.ArgumentParser()
    add_rbb_argument(ap)
    assert ap.parse_args([]).rbb_policy == 'amortized'


def test_the_recorded_placement_is_still_reachable_and_pinnable():
    """Two ways the back catalogue stays verifiable: the flag, and an explicit driver default."""
    ap = argparse.ArgumentParser()
    add_rbb_argument(ap)
    assert ap.parse_args(['--rbb-policy', 'stock']).rbb_policy == 'stock'

    pinned = argparse.ArgumentParser()
    add_rbb_argument(pinned, default='stock')
    assert pinned.parse_args([]).rbb_policy == 'stock', \
        'a driver that must reproduce a recorded row un-flagged can still pin stock'
