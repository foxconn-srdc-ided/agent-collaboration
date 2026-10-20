"""GitHub Actions event adapter around flow.py. State lives on poc-state."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

from flow import FlowError, Run, STAGES, parties

ORG = "foxconn-srdc-ided"
CENTRE = f"{ORG}/agent-collaboration"
STATE = Path(".state/runs.json")
ROLE_REPO = {"A": "agent-a", "B": "agent-b", "C": "agent-c"}
AUTOMATION_LOGIN = "ycliu-dev"
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
    h.pending_role = role
    h.pending_action = action
    if stage.startswith("B_C_FIX_"):
        previous = run.handoffs["A_B"]
    elif stage == "C_HUMAN":
        correction = [v for k, v in run.handoffs.items() if k.startswith("B_C_FIX_") and v.status == "已驗收"]
        previous = correction[-1] if correction else run.handoffs["B_C"]
    else:
        index = STAGES.index(stage)
        previous = run.handoffs[STAGES[index - 1]] if index else None
    prior_b = [v for k, v in run.handoffs.items() if k.startswith("B_C_FIX_") and v.status == "已驗收"]
    prior_b_sha = (prior_b[-1].passed_sha if prior_b else run.handoffs["B_C"].passed_sha) if stage.startswith("B_C_FIX_") else ""
    data = {"run_id": run.run_id, "stage": stage, "action": action,
            "issue": h.issue, "version": h.agreement_version, "attempt": h.attempt,
            "agreement": h.agreement, "sha": h.sha, "task": TASK,
            "previous_sha": previous.passed_sha if previous else "",
            "previous_repo": ROLE_REPO[parties(previous.stage)[0]] if previous else "",
            "prior_b_sha": prior_b_sha,
            "original_agreement": run.handoffs["B_C"].agreement if stage.startswith("B_C_FIX_") else "",
            **extra}
    gh("api", f"repos/{ORG}/{ROLE_REPO[role]}/dispatches", "-X", "POST",
       payload={"event_type": "agent-task", "client_payload": {"task": data}})


def comment(issue: int, body: str) -> None:
    gh("issue", "comment", str(issue), "-R", CENTRE, "--body", body)


def label(issue: int, status: str) -> None:
    for name in ["協議中", "執行中", "待檢查", "待補件", "待人工驗收", "阻塞", "取消", "已驗收"]:
        if name != status:
            subprocess.run(["gh", "issue", "edit", str(issue), "-R", CENTRE, "--remove-label", name],
                           capture_output=True, text=True)
    gh("issue", "edit", str(issue), "-R", CENTRE, "--add-label", status)


def create_card(run: Run, stage: str, agreement: str) -> None:
    giver, receiver = parties(stage)
    correction = stage.startswith("B_C_FIX_")
    title = f"[{giver} → {receiver}] CSV 統計{'修正' if correction else ''}交付 · {run.run_id}"
    origin = (f"依據原交付卡 #{run.handoffs['B_C'].issue} 及其已准收協議；原准收紀錄保留。\n\n"
              if correction else "")
    body = (f"{origin}## 協議 v1\n{agreement}\n\n## 交付成果\n待提交固定 commit。\n\n"
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
        subprocess.run(["git", "-C", ".state", "-c", "credential.helper=!gh auth git-credential",
                        "push", "origin", "HEAD:poc-state"], check=True)


def issue_from_event(event: dict) -> int:
    return int(event["issue"]["number"])


def find_run(runs: dict[str, Run], issue: int) -> tuple[Run, str]:
    for run in runs.values():
        for stage, handoff in run.handoffs.items():
            if handoff.issue == issue:
                return run, stage
    raise FlowError("不是受控交付卡")


def next_stage(run: Run, stage: str) -> None:
    if run.stage != "DONE":
        action = "produce" if stage.startswith("B_C_FIX_") else "propose"
        dispatch(parties(run.stage)[0], action, run, run.stage)
    else:
        comment(run.handoffs[stage].issue, "整輪已完成；可更新協作中心的 submodule 固定版本。")


def handle(runs: dict[str, Run], event: dict, event_name: str) -> None:
    if event_name == "workflow_dispatch":
        inputs = event.get("inputs", {})
        if inputs.get("mode") == "recheck_b_json":
            run = runs[inputs["run_id"]]
            h = run.handoffs["B_C"]
            if (event["sender"]["login"] != run.human or run.stage != "B_C" or run.stopped or
                    h.status != "待人工驗收" or h.sha != "7261a38c1fa3f5b2a57f6caca6db7f2849186434" or
                    h.passed_sha != h.sha or h.pending_action or h.pending_role):
                raise FlowError("只可重驗本次未實際解析 JSON 的 B 固定 SHA")
            h.passed_sha = h.passed_at = h.review = ""
            h.status = "待檢查"
            comment(h.issue, "先前 C 僅重跑使用 eval() 的 B 測試，未驗證 stdout 是 JSON；撤銷該次通過，對同一固定 SHA 加入獨立 JSON 解析後重審。")
            label(h.issue, h.status)
            dispatch("C", "review", run, "B_C", source_repo="agent-b")
            return
        if inputs.get("mode") == "retry_arbitration_agree":
            run = runs[inputs["run_id"]]
            h = run.handoffs["B_C"]
            if (event["sender"]["login"] != run.human or run.stage != "B_C" or
                    run.stopped != "改約無共識，等待人工裁決" or
                    h.status != "阻塞" or h.agreement_version != 4 or h.agreed or
                    h.pending_action or h.pending_role):
                raise FlowError("只可重試本次裁決後的 C 協議誤判")
            pages = json.loads(gh("api", f"repos/{CENTRE}/issues/{h.issue}/comments", "--paginate", "--slurp"))
            comments = [item for page in pages for item in page]
            if not any(c["user"]["login"] == run.human and c["body"].startswith("/resolve ")
                       and c["body"][9:].strip() == h.agreement for c in comments):
                raise FlowError("找不到指定人工的原協議裁決")
            if not comments or not comments[-1]["body"].startswith("C 不同意協議 v4："):
                raise FlowError("沒有可重試的 C 誤判回報")
            run.stopped = ""
            h.status = "協議中"
            comment(h.issue, "C 前次審核增加了原裁決未要求的案例；已修正審核範圍，在協議 v4 原卡重試 C 同意。")
            label(h.issue, h.status)
            dispatch("C", "agree", run, "B_C")
            return
        if inputs.get("mode") == "grant_a_fix":
            run = runs[inputs["run_id"]]
            h = run.handoffs["A_B"]
            if (event["sender"]["login"] != run.human or run.stage != "A_B" or
                    run.stopped != "A 修正額度耗盡" or h.status != "阻塞" or
                    run.fixes["A"] != 3 or run.extra_fixes["A"] != 0 or
                    h.pending_action or h.pending_role):
                raise FlowError("只可對本次 A 修正額度耗盡特准一次")
            pages = json.loads(gh("api", f"repos/{CENTRE}/issues/{h.issue}/comments", "--paginate", "--slurp"))
            comments = [item for page in pages for item in page]
            if not comments or comments[-1]["user"]["login"] != run.human or \
                    comments[-1]["body"].strip() != "授權在原 run 額外增加 A 一次修正額度":
                raise FlowError("需指定人工在原交付卡明確授權")
            run.extra_fixes["A"] = 1
            run.stopped = ""
            h.status = "待補件"
            h.attempt += 1
            comment(h.issue, "指定人工已特准 A 額外一次修正；沿用原 run、協議 v3 與本卡。")
            label(h.issue, h.status)
            dispatch("A", "produce", run, "A_B", feedback=(
                "SPEC.md 必須有至少兩筆資料的正常 CSV 輸入及對應可解析 JSON 輸出範例；"
                "所有標成 JSON 的區塊都須可解析，並保留已定義的 stderr 錯誤文字與退出碼。"))
            return
        if inputs.get("mode") == "retry_invalid_amend":
            run = runs[inputs["run_id"]]
            h = run.handoffs["A_B"]
            if (event["sender"]["login"] != run.human or run.stage != "A_B" or
                    h.agreement != "交付範圍、驗收條件、依據資料" or h.amendments != 1 or
                    h.pending_action != "produce" or h.pending_role != "A"):
                raise FlowError("只可重試已確認的 A→B 無效改約")
            issue = json.loads(gh("api", f"repos/{CENTRE}/issues/{h.issue}"))
            original = issue["body"].split("## 協議 v1\n", 1)[1].split("\n\n## 交付成果", 1)[0]
            comments = json.loads(gh("api", f"repos/{CENTRE}/issues/{h.issue}/comments", "--paginate"))
            feedback = next((c["body"][7:] for c in reversed(comments)
                             if c["user"]["login"] == run.human and c["body"].startswith("/amend ")), "")
            if not feedback:
                raise FlowError("找不到原人工改約指示")
            h.agreement = original
            h.agreement_version = 1
            h.amendments = 0
            h.agreed = []
            h.status = "協議中"
            h.pending_action = h.pending_role = ""
            comment(h.issue, "協議 v2 為無效佔位提案；已取消由此產生的交付，依原 `/amend` 指示在本 run 重試。")
            label(h.issue, h.status)
            dispatch("A", "amend", run, "A_B", feedback=feedback)
            return
        if inputs.get("mode") == "resume":
            run = runs[inputs["run_id"]]
            if event["sender"]["login"] != run.human or not run.stopped:
                raise FlowError("只有指定人工可恢復暫停的 run")
            h = run.handoffs[run.stage]
            if not h.blocked_action:
                raise FlowError("此阻塞需要人工裁決或明確修改額度")
            action, role = h.blocked_action, h.blocked_role
            h.blocked_action = h.blocked_role = ""
            run.stopped = ""
            h.status = ("協議中" if action in {"propose", "amend", "agree"} else
                        "待檢查" if action == "review" else "執行中")
            if h.issue:
                label(h.issue, h.status)
            dispatch(role, action, run, run.stage)
            return
        if inputs.get("mode") != "start":
            raise FlowError("未知手動模式")
        human = inputs.get("human", "").strip() or AUTOMATION_LOGIN
        run_id = f"run-{os.environ['GITHUB_RUN_ID']}"
        if run_id in runs:
            return
        run = Run(run_id, human)
        runs[run_id] = run
        dispatch("A", "propose", run, "A_B")
        return

    if event_name == "repository_dispatch":
        if event.get("action") != "agent-report" or event.get("sender", {}).get("login") != AUTOMATION_LOGIN:
            raise FlowError("拒絕非授權帳號的派工回報")
        p = event["client_payload"]["report"]
        run = runs[p["run_id"]]
        stage = p["stage"]
        h = run.current(stage)
        role = p["role"]
        action = p["action"]
        expected_action = p.get("failed_action") if action in {"failed", "selfcheck_failed", "upstream_defect"} else action
        if p.get("repo") != ROLE_REPO.get(role):
            raise FlowError("派工來源 repo 不符")
        if h.pending_role != role or h.pending_action != expected_action:
            raise FlowError("回報與待處理派工不符")
        if not run.event(f"{role}:{p['report_id']}"):
            return
        if p.get("version") != h.agreement_version or p.get("attempt") != h.attempt:
            raise FlowError("過期 Agent 回報")
        h.pending_role = h.pending_action = ""
        if action == "propose":
            run.propose(stage, p["text"], role)
            create_card(run, stage, p["text"])
            if stage != "C_HUMAN":
                dispatch(parties(stage)[1], "agree", run, stage)
            else:
                comment(h.issue, f"請指定人工驗收者 @{run.human} 留言 `/agree v{h.agreement_version}` 同意測試範圍。")
        elif action == "agree":
            if p.get("agree") is not True:
                if h.amendments >= 2:
                    h.status = "阻塞"
                    run.stopped = "改約無共識，等待人工裁決"
                    comment(h.issue, f"{role} 不同意協議 v{h.agreement_version}：{p.get('text', '')}。需人工裁決。")
                    label(h.issue, h.status)
                else:
                    comment(h.issue, f"{role} 回饋協議 v{h.agreement_version}：{p.get('text', '')}")
                    dispatch(parties(stage)[0], "amend", run, stage, feedback=p.get("text", ""))
                return
            ready = run.agree(stage, role, p["version"])
            comment(h.issue, f"{role} 同意協議 v{h.agreement_version}。")
            if ready:
                label(h.issue, h.status)
                dispatch(parties(stage)[0], "produce", run, stage)
            elif role == parties(stage)[1]:
                dispatch(parties(stage)[0], "agree", run, stage)
        elif action == "amend":
            run.propose(stage, p["text"], role, amendment=True)
            comment(h.issue, f"協議 v{h.agreement_version} 改約提案：\n{h.agreement}")
            label(h.issue, h.status)
            dispatch(parties(stage)[1], "agree", run, stage)
        elif action == "produce":
            gh("api", f"repos/{ORG}/{ROLE_REPO[role]}/git/commits/{p['sha']}")
            if stage == "C_HUMAN":
                run.submit_final(p["sha"], p["attempt"], p["text"])
                h.passed_at = datetime.now(timezone.utc).isoformat()
            else:
                run.submit(stage, role, p["sha"], p["attempt"], p["text"])
            link = f"https://github.com/{ORG}/{ROLE_REPO[role]}/commit/{p['sha']}"
            comment(h.issue, f"{role} 交付：{link}\n\n自檢：{p['text']}\nAttempt: {h.attempt}")
            label(h.issue, h.status)
            if stage != "C_HUMAN":
                dispatch(parties(stage)[1], "review", run, stage, source_repo=ROLE_REPO[role])
        elif action == "review":
            run.review_result(stage, role, p["sha"], p["attempt"], p["passed"], p["text"])
            if p["passed"]:
                h.passed_at = datetime.now(timezone.utc).isoformat()
            comment(h.issue, f"{role} 檢查協議 v{h.agreement_version}、SHA `{p['sha']}`："
                  f"{'通過' if p['passed'] else '退回'}\n\n{p['text']}")
            label(h.issue, h.status)
            if not p["passed"] and not run.stopped:
                dispatch(parties(stage)[0], "produce", run, stage, feedback=p["text"])
        elif action == "failed":
            h.blocked_action = p.get("failed_action", "")
            h.blocked_role = role
            h.status = "阻塞"
            run.stopped = f"{role} 工具或 API 失敗：{p['text']}"
            if h.issue:
                comment(h.issue, run.stopped)
                label(h.issue, h.status)
            else:
                gh("issue", "create", "-R", CENTRE, "--title", f"[工作] {run.run_id} 啟動阻塞",
                   "--body", run.stopped, "--label", "工作", "--label", "阻塞")
        elif action == "selfcheck_failed":
            h.status = "待補件"
            run.fix(stage, role, p["text"])
            comment(h.issue, f"{role} 自檢失敗，使用修正額度：{p['text']}")
            label(h.issue, h.status)
            if not run.stopped:
                dispatch(role, "produce", run, stage, feedback=p["text"])
        elif action == "upstream_defect":
            correction = run.start_correction(p["text"])
            comment(h.issue, f"C 獨立測試發現 B 缺陷；保留原准收紀錄。\n{p['text']}")
            if correction:
                dispatch("B", "propose", run, correction, feedback=p["text"])
            else:
                label(h.issue, h.status)
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
        if actor != run.human:
            return
        if run.stage != stage:
            return
        h = run.handoffs[stage]
        if body.startswith("/cancel "):
            run.cancel(stage, actor, body[8:])
            label(issue, h.status)
            return
        if body.startswith("/resolve ") and run.stopped.startswith("改約無共識"):
            h.agreement_version += 1
            h.agreement = body[9:].strip()
            h.agreed = []
            h.status = "協議中"
            run.stopped = ""
            comment(issue, f"人工裁決為協議 v{h.agreement_version}，雙方仍須同意：\n{h.agreement}")
            label(issue, h.status)
            if stage == "C_HUMAN":
                comment(issue, f"請 @{run.human} 留言 `/agree v{h.agreement_version}` 確認裁決後範圍。")
            else:
                dispatch(parties(stage)[1], "agree", run, stage)
            return
        if body == "/resume" and run.stopped and h.blocked_action:
            action, role = h.blocked_action, h.blocked_role
            h.blocked_action = h.blocked_role = ""
            run.stopped = ""
            h.status = ("協議中" if action in {"propose", "amend", "agree"} else
                        "待檢查" if action == "review" else "執行中")
            label(issue, h.status)
            dispatch(role, action, run, stage)
            return
        h = run.current(stage)
        if body.startswith("/amend ") and h.agreement and h.amendments < 2:
            h.status = "協議中"
            h.passed_sha = ""
            h.passed_at = ""
            label(issue, h.status)
            dispatch(parties(stage)[0], "amend", run, stage, feedback=body[7:])
            return
        if stage == "C_HUMAN" and body == f"/agree v{h.agreement_version}":
            ready = run.agree(stage, "HUMAN", h.agreement_version)
            if not ready:
                dispatch("C", "agree", run, stage)
            return
        if body.startswith("/reject ") and h.status == "待人工驗收":
            run.fix(stage, parties(stage)[0], body[8:])
            label(issue, h.status)
            if not run.stopped:
                dispatch(parties(stage)[0], "produce", run, stage, feedback=body[8:])
            return
        return

    if event_name == "issues" and event.get("action") == "closed":
        issue = issue_from_event(event)
        try:
            run, stage = find_run(runs, issue)
        except FlowError:
            return
        if run.stage != stage:
            return
        h = run.current(stage)
        actor = event["sender"]["login"]
        reason = event["issue"].get("state_reason")
        pages = json.loads(gh("api", f"repos/{CENTRE}/issues/{issue}/comments", "--paginate", "--slurp"))
        comments = [item for page in pages for item in page]
        passed_at = datetime.fromisoformat(h.passed_at.replace("Z", "+00:00")) if h.passed_at else None
        approvals = [c["body"] for c in comments if c["user"]["login"] == run.human
                     and c["body"].startswith(f"/accept {h.passed_sha} ")
                     and passed_at and datetime.fromisoformat(c["created_at"].replace("Z", "+00:00")) >= passed_at]
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
