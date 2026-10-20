"""GitHub Actions event adapter around flow.py. State lives on poc-state."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys

from flow import FlowError, PARTIES, Run, STAGES

ORG = "foxconn-srdc-ided"
CENTRE = f"{ORG}/agent-collaboration"
STATE = Path(".state/runs.json")
ROLE_REPO = {"A": "agent-a", "B": "agent-b", "C": "agent-c"}
TASK = "Python 標準函式庫 CSV 統計 CLI；category、amount 欄位；JSON 輸出總筆數、總金額、分類統計；Decimal 金額。A 定義格式、精度、範例、錯誤行為；至少測正常、負金額、只有標頭、缺欄位、空白分類、非法金額。"


def gh(*args: str, payload: dict | None = None) -> str:
    cmd = ["gh", *args]
    if payload is not None:
        cmd.extend(["--input", "-"])
    result = subprocess.run(cmd, input=json.dumps(payload, ensure_ascii=False) if payload is not None else None,
                            text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"{' '.join(cmd)}: {result.stderr.strip()}")
    return result.stdout.strip()


def dispatch(role: str, action: str, run: Run, stage: str, **extra: object) -> None:
    h = run.handoffs[stage]
    index = STAGES.index(stage)
    previous = run.handoffs[STAGES[index - 1]] if index else None
    data = {"run_id": run.run_id, "stage": stage, "action": action,
            "issue": h.issue, "version": h.agreement_version, "attempt": h.attempt,
            "agreement": h.agreement, "sha": h.sha, "task": TASK,
            "previous_sha": previous.passed_sha if previous else "",
            "previous_repo": ROLE_REPO[PARTIES[previous.stage][0]] if previous else "",
            **extra}
    gh("api", f"repos/{ORG}/{ROLE_REPO[role]}/dispatches", "-X", "POST",
       payload={"event_type": "agent-task", "client_payload": data})


def comment(issue: int, body: str) -> None:
    gh("issue", "comment", str(issue), "-R", CENTRE, "--body", body)


def label(issue: int, status: str) -> None:
    for name in ["協議中", "執行中", "待檢查", "待補件", "待人工驗收", "阻塞", "取消", "已驗收"]:
        if name != status:
            subprocess.run(["gh", "issue", "edit", str(issue), "-R", CENTRE, "--remove-label", name],
                           capture_output=True, text=True)
    gh("issue", "edit", str(issue), "-R", CENTRE, "--add-label", status)


def create_card(run: Run, stage: str, agreement: str) -> None:
    giver, receiver = PARTIES[stage]
    title = f"[{giver} → {receiver}] CSV 統計交付 · {run.run_id}"
    body = (f"## 協議 v1\n{agreement}\n\n## 交付成果\n待提交固定 commit。\n\n"
            f"## 上家自檢\n待提交。\n\nRun: `{run.run_id}`。定約、檢查與准收請使用本卡留言。")
    url = gh("issue", "create", "-R", CENTRE, "--title", title, "--body", body,
             "--label", "交付", "--label", "協議中")
    run.set_issue(stage, int(url.rsplit("/", 1)[-1]))
    comment(run.handoffs[stage].issue, f"協議 v1 提案（{giver}）：\n{agreement}")


def load() -> dict[str, Run]:
    if not STATE.exists():
        return {}
    return {k: Run.from_dict(v) for k, v in json.loads(STATE.read_text()).items()}


def save(runs: dict[str, Run]) -> None:
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps({k: v.as_dict() for k, v in runs.items()},
                                ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    subprocess.run(["git", "-C", ".state", "add", "runs.json"], check=True)
    result = subprocess.run(["git", "-C", ".state", "diff", "--cached", "--quiet"])
    if result.returncode:
        subprocess.run(["git", "-C", ".state", "-c", "user.name=agent-flow[bot]",
                        "-c", "user.email=agent-flow@users.noreply.github.com", "commit", "-m", "Update PoC state"], check=True)
        subprocess.run(["git", "-C", ".state", "push", "origin", "HEAD:poc-state"], check=True)


def issue_from_event(event: dict) -> int:
    return int(event["issue"]["number"])


def find_run(runs: dict[str, Run], issue: int) -> tuple[Run, str]:
    for run in runs.values():
        for stage in STAGES:
            if run.handoffs[stage].issue == issue:
                return run, stage
    raise FlowError("不是受控交付卡")


def next_stage(run: Run, stage: str) -> None:
    if run.stage != "DONE":
        dispatch(PARTIES[run.stage][0], "propose", run, run.stage)
    else:
        comment(run.handoffs[stage].issue, "整輪已完成；可更新協作中心的 submodule 固定版本。")


def handle(runs: dict[str, Run], event: dict, event_name: str) -> None:
    if event_name == "workflow_dispatch":
        inputs = event.get("inputs", {})
        if inputs.get("mode") != "start":
            raise FlowError("僅支援明確手動 start；恢復須使用受控事件")
        human = inputs.get("human", "").strip()
        run_id = f"run-{os.environ['GITHUB_RUN_ID']}"
        if run_id in runs:
            return
        run = Run(run_id, human)
        runs[run_id] = run
        dispatch("A", "propose", run, "A_B")
        return

    if event_name == "repository_dispatch":
        if event.get("action") != "agent-report" or event.get("sender", {}).get("type") != "Bot":
            raise FlowError("拒絕非 App 的派工回報")
        p = event["client_payload"]
        run = runs[p["run_id"]]
        stage = p["stage"]
        h = run.current(stage)
        role = p["role"]
        if p.get("repo") != ROLE_REPO.get(role) or not run.event(f"{role}:{p['report_id']}"):
            return
        if p.get("version") != h.agreement_version or p.get("attempt") != h.attempt:
            raise FlowError("過期 Agent 回報")
        action = p["action"]
        if action == "propose":
            run.propose(stage, p["text"], role)
            create_card(run, stage, p["text"])
            if stage != "C_HUMAN":
                dispatch(PARTIES[stage][1], "agree", run, stage)
            else:
                comment(h.issue, f"請指定人工驗收者 @{run.human} 留言 `/agree v{h.agreement_version}` 同意測試範圍。")
        elif action == "agree":
            if p.get("agree") is not True:
                if h.amendments >= 2:
                    h.status = "阻塞"
                    run.stopped = "改約無共識，等待人工裁決"
                    comment(h.issue, f"{role} 不同意協議 v{h.agreement_version}：{p.get('text', '')}。需人工裁決。")
                else:
                    comment(h.issue, f"{role} 回饋協議 v{h.agreement_version}：{p.get('text', '')}")
                    dispatch(PARTIES[stage][0], "amend", run, stage, feedback=p.get("text", ""))
                return
            ready = run.agree(stage, role, p["version"])
            comment(h.issue, f"{role} 同意協議 v{h.agreement_version}。")
            if ready:
                label(h.issue, h.status)
                dispatch(PARTIES[stage][0], "produce", run, stage)
            elif role == PARTIES[stage][1]:
                dispatch(PARTIES[stage][0], "agree", run, stage)
        elif action == "amend":
            run.propose(stage, p["text"], role, amendment=True)
            comment(h.issue, f"協議 v{h.agreement_version} 改約提案：\n{h.agreement}")
            label(h.issue, h.status)
            dispatch(PARTIES[stage][1], "agree", run, stage)
        elif action == "produce":
            if stage == "C_HUMAN":
                run.submit_final(p["sha"], p["attempt"], p["text"])
            else:
                run.submit(stage, role, p["sha"], p["attempt"], p["text"])
            link = f"https://github.com/{ORG}/{ROLE_REPO[role]}/commit/{p['sha']}"
            comment(h.issue, f"{role} 交付：{link}\n\n自檢：{p['text']}\nAttempt: {h.attempt}")
            label(h.issue, h.status)
            if stage != "C_HUMAN":
                dispatch(PARTIES[stage][1], "review", run, stage, source_repo=ROLE_REPO[role])
        elif action == "review":
            run.review_result(stage, role, p["sha"], p["attempt"], p["passed"], p["text"])
            comment(h.issue, f"{role} 檢查協議 v{h.agreement_version}、SHA `{p['sha']}`："
                  f"{'通過' if p['passed'] else '退回'}\n\n{p['text']}")
            label(h.issue, h.status)
            if not p["passed"] and not run.stopped:
                dispatch(PARTIES[stage][0], "produce", run, stage, feedback=p["text"])
        elif action == "failed":
            h.status = "阻塞"
            run.stopped = f"{role} 工具或 API 失敗：{p['text']}"
            comment(h.issue, run.stopped)
            label(h.issue, h.status)
        elif action == "selfcheck_failed":
            h.status = "待補件"
            run.fix(stage, role, p["text"])
            comment(h.issue, f"{role} 自檢失敗，使用修正額度：{p['text']}")
            label(h.issue, h.status)
            if not run.stopped:
                dispatch(role, "produce", run, stage, feedback=p["text"])
        else:
            raise FlowError("未知 Agent 動作")
        return

    if event_name == "issue_comment":
        if event.get("action") != "created":
            return
        issue = issue_from_event(event)
        try:
            run, stage = find_run(runs, issue)
        except FlowError:
            return
        actor = event["comment"]["user"]["login"]
        body = event["comment"]["body"].strip()
        h = run.current(stage)
        if actor != run.human:
            return
        if stage == "C_HUMAN" and body == f"/agree v{h.agreement_version}":
            ready = run.agree(stage, "HUMAN", h.agreement_version)
            if not ready:
                dispatch("C", "agree", run, stage)
            return
        if body.startswith("/reject ") and h.status == "待人工驗收":
            run.fix(stage, PARTIES[stage][0], body[8:])
            label(issue, h.status)
            if not run.stopped:
                dispatch(PARTIES[stage][0], "produce", run, stage, feedback=body[8:])
            return
        if body.startswith("/cancel "):
            run.cancel(stage, actor, body[8:])
            label(issue, h.status)
            return
        return

    if event_name == "issues" and event.get("action") == "closed":
        issue = issue_from_event(event)
        try:
            run, stage = find_run(runs, issue)
        except FlowError:
            return
        h = run.current(stage)
        actor = event["sender"]["login"]
        reason = event["issue"].get("state_reason")
        comments = json.loads(gh("api", f"repos/{CENTRE}/issues/{issue}/comments", "--paginate"))
        approvals = [c["body"] for c in comments if c["user"]["login"] == run.human
                     and c["body"].startswith(f"/accept {h.passed_sha} ")]
        if actor != run.human or reason != "completed" or not approvals:
            gh("issue", "reopen", str(issue), "-R", CENTRE)
            comment(issue, "關卡未符合准收條件：指定人工、completed、最新版通過及 `/accept <SHA> <理由>` 均必需。")
            return
        try:
            run.accept(stage, actor, h.passed_sha, approvals[-1].split(" ", 2)[2])
        except FlowError:
            gh("issue", "reopen", str(issue), "-R", CENTRE)
            comment(issue, "最新版尚未檢查通過；已重開。")
            return
        label(issue, h.status)
        next_stage(run, stage)


def main() -> None:
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    runs = load()
    try:
        handle(runs, event, os.environ["GITHUB_EVENT_NAME"])
    except (FlowError, KeyError) as exc:
        print(f"Controlled stop: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    save(runs)


if __name__ == "__main__":
    main()
