# Agent 協作 PoC

[目前部署與驗證狀態](STATUS.md)。

四個 public repo：A 定義規格、B 實作、C 獨立測試；本 repo 集中工作卡、交付卡及狀態。工作卡不會派工。交付卡先議定、再執行與自檢、下家檢查，最後由指定人工准收才能接棒。狀態保存在 `poc-state` 分支，所有成果以固定 commit SHA 核對。

視覺參考：[協作心智模型](docs/01-協作心智模型-v2.png)、[兩種 Issue 卡片](docs/02-Issue卡片範本-v2.png)、[Dashboard 卡片版](docs/03-協作Dashboard-卡片版-v2.png)。Dashboard 圖是示意設計，未作為實際執行紀錄。

## 啟動與人工操作

完成四個 repo 的 `CROSS_REPO_TOKEN` secret，以及三個角色 repo 的 `MODEL_STUDIO_API_KEY` secret、`MODEL_STUDIO_BASE_URL` variable 後，由指定人工以 Actions → Agent handoff → Run workflow，填入 `mode=start` 及其 GitHub username。每次手動啟動建立新 run。`gh workflow run flow.yml -R foxconn-srdc-ided/agent-collaboration -f mode=start -f human=USERNAME` 效果相同。

Agent A/B 與下家在交付卡留言議定。最後 C → 人工交付卡，人工先留言 `/agree v1`（改約後使用當前版本）。檢查通過後，人工在同一卡留言 `/accept <完整40位SHA> <完成理由>`，再以 **Close as completed** 關卡；兩步均需指定帳號操作。退件留言 `/reject <具體缺失>`，取消留言 `/cancel <理由>`。一般聊天不派工。錯誤或過早關卡由腳本重開。

協議條件須更新時，指定人工在交付卡留言 `/amend <修改理由>`，上家提出新版、雙方重同意；最多兩輪。兩輪仍無共識時，指定人工留言 `/resolve <裁決後的完整協議>`，雙方確認後繼續。工具或 API 失敗時，可由指定人工在原交付卡留言 `/resume`，或以 Actions `mode=resume`、`run_id=<原 run>` 恢復；不會建立新 run。

C 的獨立測試若判定為 B 缺陷，控制腳本會保留原 B → C 准收紀錄、另建修正交付卡，使用 B 剩餘修正額度；再次人工准收後，C 依原先議定範圍重測，不扣 C 額度。C 自己的測試或報告錯誤則扣 C 的修正額度。

Agent/API 失敗或修正額度耗盡會停在阻塞；不得用新 run 重置同一任務。人工裁決或恢復尚需按該卡紀錄處理。整輪完成才更新 submodule 固定版本。

## 設定

四個 repo 共用僅授予這四個 repo 的組織 Secret `CROSS_REPO_TOKEN`，其值是 `ycliu-dev` 的 GitHub 個人 token；若組織政策不允許，改設同名 repo Secret。角色 repo 另設 `MODEL_STUDIO_API_KEY` secret、`MODEL_STUDIO_BASE_URL` variable。模型固定 `qwen3-coder-flash-2025-07-28`，OpenCode 固定 `1.18.34`。未配置完成前 workflow 不會成功。

需要人工提供阿里雲資料時，在本 repo 執行 `bash setup-human.sh`。精靈安全輸入 API key 並設定三個角色 repo；不把密鑰寫入 Issue 或 repo。GitHub token 由已登入的 `gh` 設定，不需貼出。完成後分別手動執行 A/B/C 的 Agent workflow `mode=smoke`，檢查模型連線與串流事件。

檢查：`python3 -m unittest -v`。相關正式證據以 run 的 Issue、Actions run 和成果 SHA 連結為準；示意圖非真實紀錄。
