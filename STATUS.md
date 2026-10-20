# PoC 狀態（2026-10-20）

四個 public repo 已建立，角色 Actions、交付控制器、兩種 Issue 範本、標籤及 `poc-state` 分支已部署。本機 12 項測試通過，涵蓋三段交付模擬、准收防重、退件、改約與 B 缺陷修正。三張圖是設計示意。

尚未建立 GitHub App，也未配置 `APP_PRIVATE_KEY`、`MODEL_STUDIO_API_KEY` Secrets；故真實 OpenCode smoke、模型交接與人工准收尚未執行。沒有可引用的真實 run、交付 Issue、成果 SHA 或成功 Actions 紀錄。不可將本機模擬視為端到端驗收。

接續順序：指定人工執行 [`setup-human.sh`](setup-human.sh)；確認 GitHub 人工驗收 username；先在 [A](https://github.com/foxconn-srdc-ided/agent-a/actions)、[B](https://github.com/foxconn-srdc-ided/agent-b/actions)、[C](https://github.com/foxconn-srdc-ided/agent-c/actions) 執行 smoke，核對模型、串流與工具呼叫；再由 [協作中心](https://github.com/foxconn-srdc-ided/agent-collaboration/actions/workflows/flow.yml) 明確手動 start。依卡片在每棒由人工准收。真實整輪成功後才更新 submodule 與本頁證據連結。
