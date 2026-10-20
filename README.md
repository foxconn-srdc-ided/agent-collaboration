# Agent 協作 PoC

四個 public repo：A 定義規格、B 實作、C 獨立測試；本 repo 集中工作卡、交付卡及狀態。工作卡不會派工。交付卡先議定、再執行與自檢、下家檢查，最後由指定人工准收才能接棒。狀態保存在 `poc-state` 分支，所有成果以固定 commit SHA 核對。

## 啟動與人工操作

完成 GitHub App、三個角色 repo 的 `MODEL_STUDIO_API_KEY` secret、`MODEL_STUDIO_BASE_URL` variable 後，由指定人工以 Actions → Agent handoff → Run workflow，填入 `mode=start` 及其 GitHub username。每次手動啟動建立新 run。`gh workflow run flow.yml -R foxconn-srdc-ided/agent-collaboration -f mode=start -f human=USERNAME` 效果相同。

Agent A/B 與下家在交付卡留言議定。最後 C → 人工交付卡，人工先留言 `/agree v1`（改約後使用當前版本）。檢查通過後，人工在同一卡留言 `/accept <完整40位SHA> <完成理由>`，再以 **Close as completed** 關卡；兩步均需指定帳號操作。退件留言 `/reject <具體缺失>`，取消留言 `/cancel <理由>`。一般聊天不派工。錯誤或過早關卡由腳本重開。

Agent/API 失敗或修正額度耗盡會停在阻塞；不得用新 run 重置同一任務。人工裁決或恢復尚需按該卡紀錄處理。整輪完成才更新 submodule 固定版本。

## 設定

GitHub App 安裝在本組織四個 repo，至少授予 Contents read/write、Issues read/write。協作中心與三個角色 repo 均設 `APP_CLIENT_ID` variable、`APP_PRIVATE_KEY` secret。角色 repo 另設 `MODEL_STUDIO_API_KEY` secret、`MODEL_STUDIO_BASE_URL` variable。模型固定 `qwen3-coder-flash-2025-07-28`，OpenCode 固定 `1.18.34`。未配置完成前 workflow 不會成功。

需要人工操作時，在本 repo 執行 `bash setup-human.sh`。精靈逐步引導建立／安裝 App、下載私鑰並直接寫入四個 repo 的 Secrets，再安全輸入阿里雲 API key；不把密鑰寫入 Issue 或 repo。完成後分別手動執行 A/B/C 的 Agent workflow `mode=smoke`，檢查模型連線與串流事件。

檢查：`python3 -m unittest -v`。相關正式證據以 run 的 Issue、Actions run 和成果 SHA 連結為準；示意圖非真實紀錄。
