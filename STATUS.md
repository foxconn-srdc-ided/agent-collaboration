# PoC 狀態（2026-10-20）

四個 public repo 已建立，角色 Actions、交付控制器、兩種 Issue 範本、標籤及 `poc-state` 分支已部署。本機控制器 15 項及各角色 2 項測試通過。三張圖是設計示意。

已改用個人 token 方案；`CROSS_REPO_TOKEN` 僅供四個 repo，`MODEL_STUDIO_API_KEY` 與新加坡 base URL 僅供 A/B/C。三個模型 smoke 成功：[A](https://github.com/foxconn-srdc-ided/agent-a/actions/runs/39399063253)、[B](https://github.com/foxconn-srdc-ided/agent-b/actions/runs/39399165212)、[C](https://github.com/foxconn-srdc-ided/agent-c/actions/runs/39399168799)。

真實 run [`run-39399553395`](https://github.com/foxconn-srdc-ided/agent-collaboration/actions/runs/39399553395) 已走到第一張 [A → B 交付卡 #6](https://github.com/foxconn-srdc-ided/agent-collaboration/issues/6) 的「待人工驗收」。A 成果為固定 [SHA `da3af81b6de6256f61caa7e2f1ec6b749c873526`](https://github.com/foxconn-srdc-ided/agent-a/commit/da3af81b6de6256f61caa7e2f1ec6b749c873526)，B 已回報通過。檢視固定 SHA 發現規格的 JSON 範例含未加引號的 `int`／`Decimal`，且「只有標頭回傳空結果」沒有定義確切 JSON；這兩點需由指定人工在卡片修約或退件，不應直接准收。

未完成 B、C 交接、整輪人工准收與 submodule 更新；不可宣稱端到端完成。待指定人工於 #6 留言後，控制器會在原 run 繼續。
