# PoC 狀態（2026-10-20）

四個 public repo 已建立，角色 Actions、交付控制器、兩種 Issue 範本、標籤及 `poc-state` 分支已部署。本機控制器 15 項及各角色 3 項測試通過。三張圖是設計示意。

已改用個人 token 方案；`CROSS_REPO_TOKEN` 僅供四個 repo，`MODEL_STUDIO_API_KEY` 與新加坡 base URL 僅供 A/B/C。三個模型 smoke 成功：[A](https://github.com/foxconn-srdc-ided/agent-a/actions/runs/39399063253)、[B](https://github.com/foxconn-srdc-ided/agent-b/actions/runs/39399165212)、[C](https://github.com/foxconn-srdc-ided/agent-c/actions/runs/39399168799)。

真實 run [`run-39399553395`](https://github.com/foxconn-srdc-ided/agent-collaboration/actions/runs/39399553395) 使用第一張 [A → B 交付卡 #6](https://github.com/foxconn-srdc-ided/agent-collaboration/issues/6)。指定人工已留言 `/amend`，要求 JSON 金額字串、可解析範例、只有標頭的確切輸出及 CLI 錯誤退出碼。A 首次回傳佔位提案，B 誤判同意；已取消錯誤交付，於原 run 重播同一人工修訂。角色程式現在拒絕佔位協議，並釐清協議審核的回報格式。A 提出完整 v2；B 的一次格式誤讀又觸發 v3，雙方已同意 v3。A 新成果為固定 [SHA `b0875d082b586a3def3fb842832f470e8c6e0763`](https://github.com/foxconn-srdc-ided/agent-a/commit/b0875d082b586a3def3fb842832f470e8c6e0763)，B 已回報通過，卡片狀態為「待人工驗收」。

指定人工已於 #6 留言 `/reject`，其後 A 兩次補件仍有缺失，B 也曾誤判找不到實際存在的 SPEC.md，導致修正額度耗盡。指定人工在原卡明確授權額外一次 A 修正；控制器只為原 run 增加一額度，沒有開新 run。A 第 6 次交付固定 [SHA `6c501ce430286a48d1df70a561a22b6faa268230`](https://github.com/foxconn-srdc-ided/agent-a/commit/6c501ce430286a48d1df70a561a22b6faa268230)。獨立核對其正常、負金額、空白分類、只有標頭的 JSON 範例可解析且算式正確，缺欄位與非法金額各有 stderr 範例和退出碼 1。B 已檢查這個 SHA 並回報通過；#6 現在「待人工驗收」。需由指定人工留言 `/accept <完整SHA> <完成理由>` 並將卡片 Close as completed，控制器才會派發 B → C。未完成 B、C 交接、整輪人工准收與 submodule 更新；不可宣稱端到端完成。
