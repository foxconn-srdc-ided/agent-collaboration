# PoC 狀態（2026-10-20）

四個 public repo 已建立，角色 Actions、交付控制器、兩種 Issue 範本、標籤及 `poc-state` 分支已部署。本機控制器 15 項及各角色 3 項測試通過。三張圖是設計示意。

已改用個人 token 方案；`CROSS_REPO_TOKEN` 僅供四個 repo，`MODEL_STUDIO_API_KEY` 與新加坡 base URL 僅供 A/B/C。三個模型 smoke 成功：[A](https://github.com/foxconn-srdc-ided/agent-a/actions/runs/39399063253)、[B](https://github.com/foxconn-srdc-ided/agent-b/actions/runs/39399165212)、[C](https://github.com/foxconn-srdc-ided/agent-c/actions/runs/39399168799)。

真實 run [`run-39399553395`](https://github.com/foxconn-srdc-ided/agent-collaboration/actions/runs/39399553395) 使用第一張 [A → B 交付卡 #6](https://github.com/foxconn-srdc-ided/agent-collaboration/issues/6)。指定人工已留言 `/amend`，要求 JSON 金額字串、可解析範例、只有標頭的確切輸出及 CLI 錯誤退出碼。A 首次回傳佔位提案，B 誤判同意；已取消錯誤交付，於原 run 重播同一人工修訂。角色程式現在拒絕佔位協議，並釐清協議審核的回報格式。A 提出完整 v2；B 的一次格式誤讀又觸發 v3，雙方已同意 v3。A 正在依 v3 重新交付，尚待固定 SHA 與 B 的檢查。

未完成 B、C 交接、整輪人工准收與 submodule 更新；不可宣稱端到端完成。下一步是核對 A 的新規格與 B 的檢查，之後才請指定人工判定是否准收。
