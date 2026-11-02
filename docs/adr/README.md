# 결정문(ADR) 발췌

원 저장소는 모든 설계 변경을 [MADR](https://adr.github.io/madr/) 꼴의 결정문으로 남깁니다.
결정문은 **append-only** 입니다 — 한번 쓴 본문은 고치지 않고, 바뀐 결정은 새 결정문이 대체합니다. 색인은 생성물이며 검사가 검증합니다.

여기에는 그중 두 건을 **원문 그대로** 실었습니다.

| 번호 | 제목 | 상태 | 요지 |
|---|---|---|---|
| [0259](0259-arrival-book-contract-settlement-and-venue-guard-boundaries.md) | 실제 도착 호가 · 계약 정산 · 거래소 대사 · 발산 감축의 경계를 검증한다 | Proposed | 도착 호가 보존, 정산 계약 장부 종료, 가중치 예산 안의 독립 대사, 보류 종목 reduce-only |
| [0282](0282-stuck-pending-cancel-resolved-at-venue.md) | 취소 대기에 갇힌 주문은 거래소를 정본으로 묻고, 열려 있으면 직접 취소한다 | Accepted | `PendingCancel` 갇힘을 거래소 조회 · 승인 · 직접 취소로 해소 |

## 읽을 때 참고

- 본문의 `Related` 에 나오는 다른 ADR 번호와 `qtbot/...` 경로는 비공개 원 저장소를 가리키며, 여기서는 열리지 않습니다.
- "유저" 는 시스템 운영자(저장소 소유자)를 뜻합니다. 결정문은 운영자의 지시 · 승인과 그에 따른 구현 결정을 함께 기록합니다.
- `known-issue #13` 같은 표기는 원 저장소의 알려진 문제 목록 항목입니다.
- 결정문 작성 규칙: Context(사실과 실측) → Decision(번호 매긴 규칙) → Consequences(남는 비용과 지워도 되는 조건).
