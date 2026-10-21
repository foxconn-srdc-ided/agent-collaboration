# PoC 狀態（2026-10-21，整輪完成）

四個 public repo、角色 Actions、交付控制器、Issue 範本、標籤與 `poc-state` 分支已部署。三個角色使用 Model Studio；跨 repo 操作使用 GitHub 個人 token，四個 repo 各自設有必要的 Actions secrets。

真實 run [`run-39399553395`](https://github.com/foxconn-srdc-ided/agent-collaboration/actions/runs/39399553395) 的 [A → B 交付卡 #6](https://github.com/foxconn-srdc-ided/agent-collaboration/issues/6) 已由指定人工驗收並關閉，固定 A [SHA `6c501ce430286a48d1df70a561a22b6faa268230`](https://github.com/foxconn-srdc-ided/agent-a/commit/6c501ce430286a48d1df70a561a22b6faa268230)。

[B → C 交付卡 #7](https://github.com/foxconn-srdc-ided/agent-collaboration/issues/7) 經人工 `/resolve` 裁決協議 v4，B、C 均同意。B 先前交付的 Python dict repr 與缺失 stderr 已修正。指定人工先後在原卡授權 B 各增加一次修正額度。B 第 5 次交付固定 [SHA `247fcc73c270e4689f57bfb0fc13cd3fc8f9ea88`](https://github.com/foxconn-srdc-ided/agent-b/commit/247fcc73c270e4689f57bfb0fc13cd3fc8f9ea88)；六項測試、自行獨立執行的 JSON/數值/錯誤輸出檢查，以及 C 從固定 SHA 執行的六項測試和 JSON 檢查均通過。C 曾誤稱本機缺檔而退件；已修正審查提示、恢復誤扣的 B 額度，並重審同一 SHA 通過。目前 #7 狀態為「待人工驗收」，固定通過 SHA 同上，B 修正次數 4、額外額度 2。

指定人工已在 #7 留言 `/accept 247fcc73c270e4689f57bfb0fc13cd3fc8f9ea88 六項測試與固定 SHA 審查通過`，並以「Close as completed」關閉；控制器推進至 C → HUMAN，開出 [交付卡 #8](https://github.com/foxconn-srdc-ided/agent-collaboration/issues/8)。C 的 v1 誤把最後一棒寫成重新實現 CLI；指定人工已 `/amend` 並 `/agree v2`，C 亦同意。v2 規定依 B 已准收固定 SHA 交付 `test_acceptance.py` 和 `REPORT.md`，驗證六種案例、重跑 B 測試並記錄命令、結果與需求覆蓋。C 第一次交付固定 [SHA `caa1877422e2ffe1918b721e28f65fa2eb085db5`](https://github.com/foxconn-srdc-ided/agent-c/commit/caa1877422e2ffe1918b721e28f65fa2eb085db5)；控制器與本地從固定 SHA 重跑 B、C 各六項測試，均通過，報告引用 B 固定 SHA 與六種案例。指定人工已在 #8 留言 `/accept caa1877422e2ffe1918b721e28f65fa2eb085db5 B 與 C 各六項測試通過，需求覆蓋報告已核對`，並以「Close as completed」關閉。`poc-state` 的 run 階段為 `DONE`，A → B、B → C、C → HUMAN 三段均為「已驗收」。協作中心的三個 submodule 已固定至上列 A、B、C 已驗收 SHA。
