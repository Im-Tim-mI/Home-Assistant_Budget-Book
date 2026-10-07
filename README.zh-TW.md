# 記帳本 (Budget Book)

[English](README.md)

Home Assistant 自訂整合，提供側邊欄記帳面板、收支統計、分類預算、固定支出與資料匯入匯出功能。資料儲存在 Home Assistant storage，會跟著 HA 備份一起保存。

目前版本：`v1.1.1`

## 軟體截圖

### 桌面版

| 總覽 | 英文介面 |
| --- | --- |
| ![總覽畫面](docs/images/screenshot-overview.png) | ![英文總覽畫面](docs/images/screenshot-overview-en.png) |

| 交易 | 語系設定 |
| --- | --- |
| ![交易畫面](docs/images/screenshot-transactions.png) | ![語系設定畫面](docs/images/screenshot-settings-language.png) |

| 圖表 | 預算 |
| --- | --- |
| ![圖表畫面](docs/images/screenshot-charts.png) | ![預算畫面](docs/images/screenshot-budgets.png) |

### 手機版

![手機總覽畫面](docs/images/screenshot-mobile-overview.png)

## 功能

- 多本記帳本管理，可分開紀錄家庭、個人或專案支出。
- 收入、支出、分類、備註與日期時間紀錄。
- 月度支出、收入、結餘與總結餘統計。
- 分類支出、近 6 個月趨勢與預算使用率圖表。
- 每月分類預算與 80% / 超支提醒。
- 固定支出規則，每天 09:00 自動檢查並寫入到期項目。
- JSON 匯入、匯出與範例資料載入。
- 內建英文、繁體中文、簡體中文介面語系。
- 自動語系會跟隨 Home Assistant 語系，也可在記帳本設定中手動指定。
- 服務呼叫後會自動刷新前端狀態，新增、刪除、匯入或切換資料後不需要重新載入 Home Assistant 頁面。

## 語系

記帳本的前端語系檔放在 `www/locales/`：

- `en.json`
- `zh-Hant.json`
- `zh-Hans.json`

未來若要新增語系，可以新增一份同 key 的 JSON 檔，再到 `www/app.js` 註冊該語系。

## 狀態同步

記帳本會從父層 Home Assistant 前端讀取狀態。由於 Home Assistant 收到新狀態時可能會替換 `hass` 物件，記帳本現在會在每次輪詢前重新取得目前的 `hass`，並在服務呼叫成功後安排短延遲刷新。這可以避免新增交易、刪除交易、匯入資料或切換記帳本後畫面停在舊資料。

## 安裝教學

### Release ZIP

到最新 Release 下載 ZIP：

<https://github.com/Im-Tim-mI/budget_book/releases/latest>

解壓縮後，將 `budget_book` 資料夾放到：

```bash
/config/custom_components/budget_book
```

複製完成後重新啟動 Home Assistant。

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

若你是用 ZIP 安裝，請重新下載最新 Release ZIP，並覆蓋原本的 `budget_book` 資料夾。更新後重新啟動 Home Assistant。若仍看到舊畫面，請清除瀏覽器或 App WebView 快取，或重新載入一次 Home Assistant。

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
