# Home-Assistant 记账本 (Budget Book)

[English](README.md) | [繁體中文](README.zh-TW.md)

Home Assistant 自定义集成，提供侧边栏记账面板、收支统计、分类预算、固定支出与数据导入导出功能。数据储存在 Home Assistant storage 中，会随 HA 备份一起保存。

当前版本：`v1.1.1`

## 软件截图

### 桌面版

| 总览 | 英文界面 |
| --- | --- |
| ![总览画面](docs/images/screenshot-overview.png) | ![英文总览画面](docs/images/screenshot-overview-en.png) |

| 交易 | 语言设置 |
| --- | --- |
| ![交易画面](docs/images/screenshot-transactions.png) | ![语言设置画面](docs/images/screenshot-settings-language.png) |

| 图表 | 预算 |
| --- | --- |
| ![图表画面](docs/images/screenshot-charts.png) | ![预算画面](docs/images/screenshot-budgets.png) |

### 手机版

![手机总览画面](docs/images/screenshot-mobile-overview.png)

## 功能

- 多本记账本管理，可分别记录家庭、个人或项目支出。
- 收入、支出、分类、备注与日期时间记录。
- 月度支出、收入、结余与总余额统计。
- 分类支出、近 6 个月趋势与预算使用率图表。
- 每月分类预算与 80% / 超支提醒。
- 固定支出规则，每天 09:00 自动检查并写入到期项目。
- JSON 导入、导出与示例数据载入。
- 内置英文、繁体中文、简体中文界面语言。
- 自动语言会跟随 Home Assistant 语言，也可以在记账本设置中手动指定。
- 服务调用后会自动刷新前端状态，新增、删除、导入或切换数据后不需要重新载入 Home Assistant 页面。

## 语言

记账本的前端语言文件放在 `www/locales/`：

- `en.json`
- `zh-Hant.json`
- `zh-Hans.json`

未来如果要新增语言，可以新增一份相同 key 的 JSON 文件，再到 `www/app.js` 注册该语言。

## 状态同步

记账本会从父层 Home Assistant 前端读取状态。由于 Home Assistant 收到新状态时可能会替换 `hass` 对象，记账本现在会在每次轮询前重新取得当前的 `hass`，并在服务调用成功后安排短延迟刷新。这可以避免新增交易、删除交易、导入数据或切换记账本后画面停留在旧数据。

## 安装教程

### Release ZIP

到最新 Release 下载 ZIP：

<https://github.com/Im-Tim-mI/Home-Assistant_Budget-Book/releases/latest>

解压后，将 `budget_book` 文件夹放到：

```bash
/config/custom_components/budget_book
```

复制完成后重新启动 Home Assistant。

### 手动安装

1. 在 Home Assistant 的配置目录中创建集成文件夹：

   ```bash
   mkdir -p /config/custom_components/budget_book
   ```

2. 将本项目内容复制到该文件夹。如果 HA 主机上可以直接使用 Git：

   ```bash
   git clone https://github.com/Im-Tim-mI/Home-Assistant_Budget-Book.git /config/custom_components/budget_book
   ```

3. 重新启动 Home Assistant。

4. 到“设置”→“设备与服务”→“添加集成”，搜索“Home-Assistant 记账本”、“记账本”或“Budget Book”并添加。

5. 添加完成后，左侧边栏会出现“记账本”。第一次打开可先载入示例数据或直接新增交易。

### 更新

如果使用 Git 安装：

```bash
cd /config/custom_components/budget_book
git pull
```

如果你使用 ZIP 安装，请重新下载最新 Release ZIP，并覆盖原本的 `budget_book` 文件夹。更新后重新启动 Home Assistant。如果仍看到旧画面，请清除浏览器或 App WebView 缓存，或重新载入一次 Home Assistant。

## 服务

集成提供 `budget_book` domain 服务，可从自动化或开发者工具调用，例如：

- `budget_book.add_transaction`
- `budget_book.delete_transaction`
- `budget_book.create_book`
- `budget_book.set_budget`
- `budget_book.add_category`
- `budget_book.add_recurring`
- `budget_book.run_recurring`
- `budget_book.replace_data`

详细字段可参考 `services.yaml`。

## 授权

本项目采用 MIT License。
