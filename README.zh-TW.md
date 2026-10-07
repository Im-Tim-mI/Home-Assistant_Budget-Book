# 記帳本 (Budget Book)

[English](README.md)

Home Assistant 自訂整合，提供側邊欄記帳面板、收支統計、分類預算、固定支出與資料匯入匯出功能。資料儲存在 Home Assistant storage，會跟著 HA 備份一起保存。

![記帳本軟體畫面](docs/images/screenshot-overview.png)

## 功能

- 多本記帳本管理，可分開紀錄家庭、個人或專案支出。
- 收入、支出、分類、備註與日期時間紀錄。
- 月度支出、收入、結餘與總結餘統計。
- 分類支出、近 6 個月趨勢與預算使用率圖表。
- 每月分類預算與 80% / 超支提醒。
- 固定支出規則，每天 09:00 自動檢查並寫入到期項目。
- JSON 匯入、匯出與範例資料載入。

## 安裝教學

### 手動安裝

1. 在 Home Assistant 的設定目錄建立整合資料夾：

   ```bash
   mkdir -p /config/custom_components/budget_book
   ```

2. 將本專案內容複製到該資料夾。若在 HA 主機上可直接使用 Git：

   ```bash
   git clone https://github.com/Im-Tim-mI/budget_book.git /config/custom_components/budget_book
   ```

3. 重新啟動 Home Assistant。

4. 到「設定」→「裝置與服務」→「新增整合」，搜尋「記帳本」或「Budget Book」並加入。

5. 加入完成後，左側側邊欄會出現「記帳本」。第一次開啟可先載入範例資料或直接新增交易。

### 更新

若使用 Git 安裝：

```bash
cd /config/custom_components/budget_book
git pull
```

更新後重新啟動 Home Assistant。

## 服務

整合提供 `budget_book` domain 服務，可從自動化或開發者工具呼叫，例如：

- `budget_book.add_transaction`
- `budget_book.delete_transaction`
- `budget_book.create_book`
- `budget_book.set_budget`
- `budget_book.add_category`
- `budget_book.add_recurring`
- `budget_book.run_recurring`
- `budget_book.replace_data`

詳細欄位可參考 `services.yaml`。

## 授權

本專案採用 MIT License。
