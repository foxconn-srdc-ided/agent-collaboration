"""Small, deterministic handoff state machine; GitHub is the record of events."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


STAGES = ("A_B", "B_C", "C_HUMAN")
PARTIES = {"A_B": ("A", "B"), "B_C": ("B", "C"), "C_HUMAN": ("C", "HUMAN")}
STATUSES = {"協議中", "執行中", "待檢查", "待補件", "待人工驗收", "阻塞", "取消", "已驗收"}


class FlowError(ValueError):
    pass


@dataclass
class Handoff:
    stage: str
    issue: int | None = None
    status: str = "協議中"
    agreement: str = ""
    agreement_version: int = 1
    amendments: int = 0
    agreed: list[str] = field(default_factory=list)
    sha: str = ""
    passed_sha: str = ""
    attempt: int = 0
    review: str = ""


@dataclass
class Run:
    run_id: str
    human: str
    stage: str = "A_B"
    handoffs: dict[str, Handoff] = field(default_factory=dict)
    fixes: dict[str, int] = field(default_factory=lambda: {"A": 0, "B": 0, "C": 0})
    stopped: str = ""
    seen: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.handoffs:
            self.handoffs = {name: Handoff(name) for name in STAGES}
        if not self.human:
            raise FlowError("指定人工驗收者不可為空")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Run:
        data = dict(data)
        data["handoffs"] = {k: Handoff(**v) for k, v in data["handoffs"].items()}
        return cls(**data)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def current(self, stage: str) -> Handoff:
        if self.stopped:
            raise FlowError(f"流程已暫停：{self.stopped}")
        if self.stage != stage or stage not in STAGES:
            raise FlowError("不是目前交接階段")
        return self.handoffs[stage]

    def event(self, event_id: str) -> bool:
        if not event_id:
            raise FlowError("事件缺少識別碼")
        if event_id in self.seen:
            return False
        self.seen.append(event_id)
        return True

    def set_issue(self, stage: str, issue: int) -> None:
        h = self.current(stage)
        if h.issue is not None and h.issue != issue:
            raise FlowError("交付卡已綁定")
        h.issue = issue

    def propose(self, stage: str, text: str, actor: str, *, amendment: bool = False) -> None:
        h = self.current(stage)
        if actor != PARTIES[stage][0]:
            raise FlowError("只有上家可以提案")
        if not text.strip():
            raise FlowError("協議內容不可為空")
        if h.agreement and not amendment:
            raise FlowError("已有協議，改約須明示")
        if amendment:
            if h.amendments >= 2:
                raise FlowError("改約已達上限")
            h.amendments += 1
            h.agreement_version += 1
        h.agreement = text
        h.agreed = []
        h.passed_sha = ""
        h.review = ""
        h.status = "協議中"

    def agree(self, stage: str, actor: str, version: int) -> bool:
        h = self.current(stage)
        if h.status != "協議中" or not h.agreement or version != h.agreement_version:
            raise FlowError("協議版本或狀態不符")
        if actor not in PARTIES[stage]:
            raise FlowError("非交接當事方")
        if actor not in h.agreed:
            h.agreed.append(actor)
        if set(h.agreed) == set(PARTIES[stage]):
            h.status = "執行中"
            h.attempt += 1
            return True
        return False

    def submit(self, stage: str, actor: str, sha: str, attempt: int, self_check: str) -> None:
        h = self.current(stage)
        if h.status not in {"執行中", "待補件"} or actor != PARTIES[stage][0]:
            raise FlowError("不接受此交付")
        if attempt != h.attempt or len(sha) != 40 or not all(c in "0123456789abcdef" for c in sha):
            raise FlowError("交付版本或嘗試序號無效")
        if not self_check.strip():
            raise FlowError("缺少自檢證據")
        h.sha = sha
        h.passed_sha = ""
        h.review = ""
        h.status = "待檢查"

    def review_result(self, stage: str, actor: str, sha: str, attempt: int, passed: bool, evidence: str) -> None:
        h = self.current(stage)
        if h.status != "待檢查" or actor != PARTIES[stage][1] or sha != h.sha or attempt != h.attempt:
            raise FlowError("檢查身分、版本或狀態不符")
        if not evidence.strip():
            raise FlowError("缺少逐項檢查證據")
        h.review = evidence
        if passed:
            h.passed_sha = sha
            h.status = "待人工驗收"
        else:
            h.passed_sha = ""
            self.fix(stage, PARTIES[stage][0], evidence)

    def fix(self, stage: str, actor: str, reason: str) -> None:
        h = self.current(stage)
        if actor != PARTIES[stage][0] or h.status not in {"待補件", "待檢查", "待人工驗收"}:
            raise FlowError("此時不可修正")
        if not reason.strip():
            raise FlowError("退件需要理由")
        self.fixes[actor] += 1
        h.passed_sha = ""
        if self.fixes[actor] > 2:
            h.status = "阻塞"
            self.stopped = f"{actor} 修正額度耗盡"
        else:
            h.attempt += 1
            h.status = "待補件"

    def accept(self, stage: str, github_actor: str, sha: str, reason: str) -> str:
        h = self.current(stage)
        if github_actor != self.human or h.status != "待人工驗收" or h.passed_sha != sha:
            raise FlowError("人工身分、狀態或受檢版本不符")
        if not reason.strip():
            raise FlowError("准收需完成理由")
        h.status = "已驗收"
        index = STAGES.index(stage)
        self.stage = STAGES[index + 1] if index + 1 < len(STAGES) else "DONE"
        return self.stage

    def submit_final(self, sha: str, attempt: int, self_check: str) -> None:
        self.submit("C_HUMAN", "C", sha, attempt, self_check)
        h = self.handoffs["C_HUMAN"]
        h.review = self_check
        h.passed_sha = sha
        h.status = "待人工驗收"

    def cancel(self, stage: str, github_actor: str, reason: str) -> None:
        h = self.current(stage)
        if github_actor != self.human or not reason.strip():
            raise FlowError("取消需指定人工及理由")
        h.status = "取消"
        self.stopped = reason
