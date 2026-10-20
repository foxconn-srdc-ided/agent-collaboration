# PoC 狀態（2026-10-20）

四個 public repo 已建立，角色 Actions、交付控制器、兩種 Issue 範本、標籤及 `poc-state` 分支已部署。本機控制器 15 項及各角色 3 項測試通過。三張圖是設計示意。

已改用個人 token 方案；`CROSS_REPO_TOKEN` 僅供四個 repo，`MODEL_STUDIO_API_KEY` 與新加坡 base URL 僅供 A/B/C。三個模型 smoke 成功：[A](https://github.com/foxconn-srdc-ided/agent-a/actions/runs/39399063253)、[B](https://github.com/foxconn-srdc-ided/agent-b/actions/runs/39399165212)、[C](https://github.com/foxconn-srdc-ided/agent-c/actions/runs/39399168799)。

真實 run [`run-39399553395`](https://github.com/foxconn-srdc-ided/agent-collaboration/actions/runs/39399553395) 使用第一張 [A → B 交付卡 #6](https://github.com/foxconn-srdc-ided/agent-collaboration/issues/6)。指定人工已留言 `/amend`，要求 JSON 金額字串、可解析範例、只有標頭的確切輸出及 CLI 錯誤退出碼。A 首次回傳佔位提案，B 誤判同意；已取消錯誤交付，於原 run 重播同一人工修訂。角色程式現在拒絕佔位協議，並釐清協議審核的回報格式。A 提出完整 v2；B 的一次格式誤讀又觸發 v3，雙方已同意 v3。A 新成果為固定 [SHA `b0875d082b586a3def3fb842832f470e8c6e0763`](https://github.com/foxconn-srdc-ided/agent-a/commit/b0875d082b586a3def3fb842832f470e8c6e0763)，B 已回報通過，卡片狀態為「待人工驗收」。

指定人工在 #6 特准一次額外 A 修正後，A 第 6 次交付固定 [SHA `6c501ce430286a48d1df70a561a22b6faa268230`](https://github.com/foxconn-srdc-ided/agent-a/commit/6c501ce430286a48d1df70a561a22b6faa268230)。B 檢查通過，指定人工已留言 `/accept` 並以 completed 關卡；控制器確認 #6「已驗收」，原 run 進入 [B → C 交付卡 #7](https://github.com/foxconn-srdc-ided/agent-collaboration/issues/7)。B 的 v1、v2、v3 協議文字幾乎相同，C/B 多次誤判找不到已附上的固定 SPEC.md，兩次改約後仍無共識；#7 現在「阻塞」，等待指定人工留言 `/resolve <完整裁決協議>`。已部署對此類來源誤判的重試檢查，並在角色 repo 各通過 5 項測試。未完成 B、C 交接、整輪人工准收與 submodule 更新；不可宣稱端到端完成。
