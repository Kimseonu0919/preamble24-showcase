"""동시성 · 순서 결정론 — 라이브 봇에서 실제로 푼 세 문제의 발췌 재구성.

이 파일은 저장소 코드를 **그대로 복사한 것이 아니라**, 각 해법의 핵심 불변식만 남겨 단독 실행 가능하게
다시 쓴 것이다(표준 라이브러리만 사용). 원본 위치와 시험은 각 절 머리에 적었다.
`python determinism_showcase.py` 로 세 절의 자기검증이 돈다.

  1절  같은 입력 -> 같은 포지션   : 총액 상한 경합에서 처리 순서를 고정한다
  2절  도착 순서와 무관한 상태     : 뒤섞여 들어온 봉이 정렬한 것과 같은 결과를 낸다
  3절  정리(GC)가 도는 스레드 고정 : 비결정적이던 스레드를 소유 스레드 하나로 못 박는다
"""

from __future__ import annotations

import gc
import itertools
import random
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field

# ======================================================================================================
# 1절. 총액 상한 경합 — 처리 순서가 승자를 정하므로, 순서를 **계약**으로 고정한다
#      원본: src/qtbot/cores/shock_reversion.py (plan_cycle, `for symbol in sorted(panels)`)
#            src/spec/execution.yaml            (mr_candidate_order_is_alphabetical: true)
#      시험: src/tests/test_research_reversion_sleeve.py::TestCandidateOrder
# ======================================================================================================
#
# 문제: 한 봉에 여러 종목이 동시에 신호를 낸다. 총액(gross) 상한이 있으면 먼저 처리된 종목이 상한을
#       채우고 뒤쪽은 탈락한다. 순회 순서가 dict 삽입 순서(= 데이터 도착 순서)에 묶여 있으면
#       같은 신호 집합에서도 실행마다 다른 포지션이 나온다.
#
# 결정: 순서를 성과가 아니라 **자유도** 기준으로 고른다. 신호 세기 순 정렬은 성과 지표를 올리지만
#       신호와 상관된 선택이라 검정되지 않은 새 자유도다 -> 중립적인 알파벳순으로 고정한다.

def plan_entries(
    signals: Mapping[str, float],
    *,
    leg_notional: float,
    gross_cap: float,
    already_held: frozenset[str] = frozenset(),
    alt_notional: float = 0.0,
) -> tuple[list[str], list[tuple[str, str]]]:
    """신호 난 종목들 중 상한 안에 들어가는 것만 진입시킨다 -> (진입 목록, 건너뜀 목록(사유))."""
    entered: list[str] = []
    skipped: list[tuple[str, str]] = []
    current = alt_notional
    for symbol in sorted(signals):                      # <-- 이 한 줄이 계약이다. 입력 순서에 의존하지 않는다.
        if symbol in already_held:
            continue
        projected_gross = (current + leg_notional) * 2   # 롱·헤지 두 다리가 모두 gross 에 든다
        if projected_gross > gross_cap:
            skipped.append((symbol, "gross_cap"))        # 사유를 남긴다 — 조용히 버리지 않는다
            continue
        entered.append(symbol)
        current += leg_notional
    return entered, skipped


def check_section_1() -> None:
    symbols = ["SOLUSDT", "ADAUSDT", "DOGEUSDT", "XRPUSDT", "LINKUSDT"]
    kwargs = dict(leg_notional=100.0, gross_cap=600.0)   # 세 다리까지만 들어간다 -> 순서가 승자를 정한다
    results = set()
    for perm in itertools.permutations(symbols):
        signals = {s: -3.0 for s in perm}                # 같은 종목, 도착 순서만 다르다
        entered, skipped = plan_entries(signals, **kwargs)
        results.add((tuple(entered), tuple(skipped)))
    assert len(results) == 1, f"입력 순서에 따라 결과가 갈렸다: {results}"   # 5! = 120 개 순열 전부 동일
    entered, skipped = next(iter(results))
    assert entered == ("ADAUSDT", "DOGEUSDT", "LINKUSDT")
    assert skipped == (("SOLUSDT", "gross_cap"), ("XRPUSDT", "gross_cap"))

    # 대조군: 도착 순서를 그대로 쓰면(= sorted 제거) 결과가 순열마다 달라진다. 이것이 막으려던 결함이다.
    def unordered(signals):
        cur, out = 0.0, []
        for s in signals:
            if (cur + 100.0) * 2 <= 600.0:
                out.append(s); cur += 100.0
        return tuple(out)
    assert len({unordered(dict.fromkeys(p)) for p in itertools.permutations(symbols)}) > 1


# ======================================================================================================
# 2절. 도착 순서와 무관한 상태 — 증분 구조가 "전부 모아서 정렬"한 결과와 정확히 같아야 한다
#      원본: src/qtbot/strategies/_reversion_bars.py (NormalizedCloses, CloseAlignment._normalize)
#      시험: src/tests/test_reversion_cycle_fast_paths.py
#            (test_random_series_out_of_order_inserts..., test_from_raw_equals_incremental,
#             test_later_raw_timestamp_wins_the_same_close_boundary)   ADR 0200
# ======================================================================================================
#
# 문제: 주기마다 21개 계열 x 18k 봉을 다시 정렬해 579 ms 를 썼고, 다섯 슬리브가 한 스레드를 공유해
#       그동안 다른 슬리브 타이머가 3.2 초 밀렸다(head-of-line blocking).
#
# 결정: 정렬을 없애되 **답은 바꾸지 않는다**. 삽입 시점에 정규화하고, 같은 마감에 원시 시각이 둘이면
#       늦은 시각이 이긴다는 동률 규칙을 코드에 명시한다. 그리고 "정렬 방식과 정확히 같은가"를
#       무작위 도착 순서로 대조한다. 답이 달라지는 최적화는 이 변경의 범위 밖이다.

def close_boundary(ts: int, bar_ns: int) -> int:
    """원시 시각 -> 그 봉의 마감 시각(올림). 마감 직전 1 ms 와 정확한 마감이 같은 봉이 된다."""
    return -(-ts // bar_ns) * bar_ns


class NormalizedCloses:
    """마감 시각 -> 종가. 삽입 순서와 무관하게 `reference_normalize` 와 같은 사전이 된다."""

    def __init__(self, bar_ns: int) -> None:
        self.bar_ns = bar_ns
        self.mapping: dict[int, float] = {}
        self._winner_ts: dict[int, int] = {}      # 마감별로 지금 이기고 있는 원시 시각

    def insert(self, ts: int, close: float) -> None:
        end = close_boundary(ts, self.bar_ns)
        if ts >= self._winner_ts.get(end, -1):    # 동률 규칙: 늦은 원시 시각이 이긴다 (도착 순서가 아니라 시각)
            self._winner_ts[end] = ts
            self.mapping[end] = close


def reference_normalize(raw: Mapping[int, float], bar_ns: int) -> dict[int, float]:
    """느리지만 자명한 기준 구현 — 시각순으로 훑어 마지막 값이 남는다."""
    out: dict[int, float] = {}
    for ts, value in sorted(raw.items()):
        out[close_boundary(ts, bar_ns)] = value
    return out


def check_section_2(trials: int = 200) -> None:
    bar = 300_000_000_000                              # 5 분봉(ns)
    rng = random.Random(7)                             # 시드 고정 — 실패하면 같은 입력으로 재현된다
    for trial in range(trials):
        raw: dict[int, float] = {}
        n = rng.randint(30, 300)
        end = rng.randint(10_000, 20_000) * bar
        for i in range(n):
            if rng.random() < 0.05:                    # 결손 봉
                continue
            boundary = end - (n - 1 - i) * bar
            ts = boundary - 1_000_000 if rng.random() < 0.5 else boundary
            raw[ts] = rng.uniform(90, 110)
            if rng.random() < 0.1:                     # 같은 마감의 두 번째 원시 시각 — 동률 규칙을 건드린다
                other = boundary if ts != boundary else boundary - 999_000_000
                raw[other] = rng.uniform(90, 110)
        expected = reference_normalize(raw, bar)
        arrival = list(raw)
        rng.shuffle(arrival)                           # 늦게 온 봉, 뒤섞인 도착
        incremental = NormalizedCloses(bar)
        for ts in arrival:
            incremental.insert(ts, raw[ts])
        assert incremental.mapping == expected, f"trial {trial}: 도착 순서에 따라 상태가 달라졌다"   # 근사가 아니라 정확한 동등

    # 동률 규칙을 따로 못 박는다: 더 이른 시각은 나중에 와도 이기지 못한다.
    norm = NormalizedCloses(bar)
    b = 100 * bar
    norm.insert(b - 1_000_000, 1.0)
    norm.insert(b, 2.0)
    norm.insert(b - 999_000_000, 3.0)
    assert norm.mapping == {b: 2.0}


# ======================================================================================================
# 3절. 정리가 도는 스레드 고정 — "아무 스레드나"를 "소유 스레드 하나"로
#      원본: src/qtbot/observability/owner_gc.py        (arm / adopt / collect)
#            src/qtbot/composition/boot.py              (arm 은 node.run() 앞, disarm 은 dispose 뒤)
#            src/qtbot/scheduler/liveness.py            (60 s 타이머가 소유 스레드에서 collect)
#      시험: src/tests/test_owner_gc.py::test_cycles_are_finalized_on_the_owner_thread_only 외    ADR 0212
# ======================================================================================================
#
# 문제: 거래소 SDK(NT)의 로거 객체는 만든 스레드에서만 해제할 수 있다(pyo3 unsendable). 그런데 파이썬의
#       자동 순환 GC 는 할당 문턱을 넘긴 **아무 스레드**에서 돈다. 할당이 가장 많은 워커 스레드에서
#       회수가 일어나 객체를 유실하고 트레이스백이 났다(2026-09-18, 09-19). 언제 어느 스레드에서 정리가
#       도는지가 부하에 따라 달라지는 비결정성이다.
#
# 결정: 자동 GC 를 끄고, 소유 스레드 하나가 정해진 주기로 회수한다. 다른 스레드의 회수는 거부한다.
#       소유 스레드는 무장 시점이 아니라 **첫 회수 시점**에 정한다 — "무장하는 스레드 = 회수하는 스레드"는
#       가정이었고, 틀리면 자동 GC 를 끈 채 아무도 회수하지 않는 상태가 되기 때문이다.

@dataclass
class OwnerGc:
    armed: bool = False
    owner_ident: int | None = None
    _restore_enabled: bool | None = field(default=None, repr=False)

    def arm(self) -> None:
        if self.armed:                                 # 두 번 무장해도 무해
            return
        self._restore_enabled = gc.isenabled()
        self.armed = True
        gc.disable()                                   # 워커 스레드가 회수를 트리거하지 못하게 한다

    def adopt(self) -> int:
        if self.owner_ident is None:                   # 회수하는 쪽이 소유자가 된다
            self.owner_ident = threading.get_ident()
        return self.owner_ident

    def collect(self) -> int:
        if self.owner_ident is not None and threading.get_ident() != self.owner_ident:
            raise RuntimeError("순환 GC 회수는 소유 스레드에서만 — 이 모듈이 막으려는 사고다")
        return gc.collect()

    def disarm(self) -> None:
        if not self.armed:
            return
        self.armed, self.owner_ident = False, None     # 다음 부팅이 소유를 새로 정하게 잊는다
        if self._restore_enabled:
            gc.enable()
        self._restore_enabled = None


_finalized_on: list[int] = []


class _Cyclic:
    """참조 계수로는 안 풀리고 순환 GC 만 회수하는 객체. 종료자가 자기가 정리된 스레드를 적는다."""

    def __init__(self) -> None:
        self.me = self

    def __del__(self) -> None:
        _finalized_on.append(threading.get_ident())


def check_section_3() -> None:
    was_enabled = gc.isenabled()
    owner = OwnerGc()
    try:
        gc.collect()
        owner.arm()
        assert not gc.isenabled()
        owner.adopt()                                  # 이 스레드가 소유 스레드(실서비스에서는 NT 타이머 스레드)
        _finalized_on.clear()
        _Cyclic()                                      # 순환 쓰레기 하나를 만든다

        worker = threading.Thread(target=lambda: [[] for _ in range(300_000)])   # 문턱을 수십 번 넘는 할당
        worker.start(); worker.join(30)
        assert _finalized_on == [], "워커의 할당이 회수를 일으켰다 — 종료자가 워커에서 돌았다"

        assert owner.collect() >= 1
        assert _finalized_on == [threading.get_ident()], "정리가 소유 스레드가 아닌 곳에서 돌았다"

        refused: list[BaseException] = []              # 침입자 스레드의 회수는 거부된다
        def intruder() -> None:
            try:
                owner.collect()
            except RuntimeError as exc:
                refused.append(exc)
        t = threading.Thread(target=intruder); t.start(); t.join(5)
        assert len(refused) == 1
    finally:
        owner.disarm()
        (gc.enable if was_enabled else gc.disable)()


if __name__ == "__main__":
    check_section_1(); print("1절 OK  — 120개 입력 순열이 모두 같은 진입 목록(상한 경합에서도 결정적)")
    check_section_2(); print("2절 OK  — 200회 무작위 도착 순서가 정렬 기준 구현과 정확히 동일")
    check_section_3(); print("3절 OK  — 워커가 아무리 할당해도 정리는 소유 스레드에서만, 침입자는 거부")
