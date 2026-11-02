# ADR 0282 — 취소 대기에 갇힌 주문은 거래소를 정본으로 묻고, 열려 있으면 직접 취소한다

- **Status**: Accepted (2026-10-28 — known-issue #13 의 근본 수선; 유저 지시 「known-issue 열린 항목 전부 장기적이고 근본적인 추천대로 해결」)
- **Related**: ADR 0182(즉시 재시도는 원인을 알 때만) · `qtbot/venue/algo_order_truth.py`(같은 꼴의 거래소 대조·액터 승인·직접 취소) ·
  `qtbot/strategies/_calendar_cancel.py`(슬리브의 취소 대사) · NT 2.0.0rc7 `crates/live/src/execution/manager.rs::check_inflight_orders` ·
  `crates/execution/src/reconciliation/orders.rs`(「Status mismatch with matching fill qty」) · `crates/trading/src/strategy/mod.rs::mark_order_pending_cancel`
- **구현 상태**: 2026-10-28 착지 — `qtbot/venue/stuck_cancel.py` · `qtbot/scheduler/stuck_cancel.py` · 스케줄러 타이머 `_stuck_cancel_check`(60 s) ·
  시험 `test_stuck_cancel.py` 12건(변이 넷) · 골든 재기록(타이머 표·설정 스냅숏)

## Context

2026-10-25 01:11:55Z Calendar 사다리 재마크의 취소(`O-20261025-011040-001-CAL-9`, ETHUSDT_270326 SELL 0.024 중 0.008 체결)가 TLS 끊김으로
모호하게 실패했다(`Ambiguous cancel failure … awaiting reconciliation`). 주문은 거래소에서 `PARTIALLY_FILLED` 로 살아 있었다.

- NT 재조정은 로컬 `PendingCancel`·거래소 `PartiallyFilled`·체결 수량 동일이면 **경고만** 내고 사건을 만들지 않는다 — 로컬 상태가 되돌아오지 않는다.
- NT 전략은 `PendingCancel` 주문의 취소를 **버린다**(`Cannot cancel order: state is PendingCancel`), 위험 엔진도 거부한다
  (`already pending cancel`). 그래서 슬리브의 재취소(known-issue #13 의 옛 후속안)는 효과가 없다.
- NT 진행 중 점검은 재시도를 다 쓰면 `PendingCancel` 을 「취소됨」으로 **지어 낸다**(`create_reconciliation_canceled`). 거래소에 산 주문이면
  캐시 밖 유령이 된다 — 갇힘보다 나쁘다. 이번에는 조회 응답 뒤 추적이 풀려 그것조차 일어나지 않았다.

결과: 주문은 낡은 가격에 13분 걸려 있다가 잔량 체결로 스스로 풀렸다(다리 재마크 정지, 미헤지 노출 1453.6 s, 0.024 ETH). Calendar 만의 일이
아니다 — 취소를 쓰는 모든 슬리브(트렌드 사다리·모멘텀 손절 갈이·MR 청산)가 같은 길에 놓인다.

## Decision

1. 스케줄러가 60 s 마다 캐시의 진행 중 주문에서 **`PendingCancel` 로 180 s 넘게 변화 없는 주문**을 고른다(오래된 순, 한 번에 하나).
   180 s 는 NT 진행 중 점검의 조회(01:12:00·01:12:07 실측)가 끝난 뒤다 — NT 가 스스로 푸는 일에는 끼어들지 않는다.
2. 작업 스레드가 거래소를 정본으로 묻는다(`GET /fapi/v1/order` symbol·orderId). 모양이 틀리거나 다른 주문이면 결함이지 부재가 아니다.
3. 거래소가 **열림**(`NEW`·`PARTIALLY_FILLED`)이면, 보내기 직전에 액터가 「캐시에서 아직 갇혀 있다」를 승인한 경우에만
   `DELETE /fapi/v1/order` 를 보내고, ACK 의 orderId·`CANCELED` 를 확인한다. NT 는 거래소의 CANCELED 통지(사용자 스트림)로 그 주문을 닫는다 —
   거래소 웹에서의 수동 취소와 같은 길이다. WARN 한 줄.
4. 거래소가 이미 **종결**(`CANCELED`·`FILLED`·`EXPIRED`)인데 캐시가 갇혀 있으면 NT 가 종결 이벤트를 못 받은 것 — ERROR 한 줄, 사람이 본다
   (봇이 캐시를 손으로 고치지 않는다).
5. 같은 주문은 300 s 안에 다시 묻지 않고, 3 회 뒤에는 ERROR 를 남기고 손을 뗀다 — 끊긴 회선 위에서 같은 주문을 두드리지 않는다.
   자격 증명은 알고 대조와 같다(라이브에서만, 테스트넷·키 없음이면 침묵).

## Consequences

- 갇힌 취소는 3~8 분 안에 거래소에서 실제로 취소된다(문턱 180 s + 점검 60 s + 승인). 슬리브의 취소 대사(`_calendar_cancel`)는 캐시
  종결을 보고 평소대로 다음 단계로 간다 — 슬리브 코드·신호·사이징 무접촉.
- 거래 가중치: 갇힌 주문이 있을 때만 GET 1·DELETE 1(주문 하나당 최대 3 회). 평소에는 요청 0.
- 남는 것: NT 상류 수선(재조정이 `PendingCancel`↔열림을 OrderCancelRejected 로 되돌리기)이 나오면 이 감시는 사건이 0 이 된다 — 지워도 된다.
