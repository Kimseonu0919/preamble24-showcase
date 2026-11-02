"""쇼케이스 자기검증을 pytest 에서도 돌리고, 각 절의 불변식을 독립 시험으로 한 번 더 못 박는다."""

from __future__ import annotations

import itertools
import random

import determinism_showcase as ds  # pyproject 의 pythonpath 로 찾는다
import pytest

# --- 자기검증 그대로 ------------------------------------------------------------------------------------

def test_section_1_self_check() -> None:
    ds.check_section_1()


def test_section_2_self_check() -> None:
    ds.check_section_2()


def test_section_3_self_check() -> None:
    ds.check_section_3()


# --- 1절: 순서 계약 -----------------------------------------------------------------------------------

@pytest.mark.parametrize("seed", range(20))
def test_plan_entries_is_permutation_invariant_with_held_and_alt(seed: int) -> None:
    rng = random.Random(seed)
    universe = [f"S{i:02d}USDT" for i in range(8)]
    symbols = rng.sample(universe, k=rng.randint(1, 8))
    held = frozenset(rng.sample(symbols, k=rng.randint(0, len(symbols))))
    kwargs = dict(leg_notional=100.0, gross_cap=rng.choice([200.0, 600.0, 1000.0]),
                  already_held=held, alt_notional=rng.choice([0.0, 100.0]))
    outcomes = {
        tuple(map(tuple, ds.plan_entries(dict.fromkeys(p, -3.0), **kwargs)))
        for p in itertools.islice(itertools.permutations(symbols), 200)
    }
    assert len(outcomes) == 1


def test_plan_entries_never_breaches_gross_cap() -> None:
    entered, skipped = ds.plan_entries(dict.fromkeys("ABCDEFG", -1.0), leg_notional=150.0, gross_cap=700.0)
    assert len(entered) * 150.0 * 2 <= 700.0
    assert all(reason == "gross_cap" for _, reason in skipped)
    assert len(entered) + len(skipped) == 7          # 조용히 사라지는 종목이 없다


# --- 2절: 동률 규칙 -----------------------------------------------------------------------------------

def test_close_boundary_rounds_up_to_bar_close() -> None:
    bar = 300
    assert ds.close_boundary(600, bar) == 600        # 정확한 마감은 그 봉
    assert ds.close_boundary(599, bar) == 600        # 마감 직전도 같은 봉
    assert ds.close_boundary(601, bar) == 900


def test_later_raw_timestamp_wins_regardless_of_arrival() -> None:
    bar = 300
    for order in itertools.permutations([(598, 1.0), (600, 2.0), (599, 3.0)]):
        norm = ds.NormalizedCloses(bar)
        for ts, close in order:
            norm.insert(ts, close)
        assert norm.mapping == {600: 2.0}
