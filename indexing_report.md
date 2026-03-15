# 索引完成报告

## 1. 项目概况
- **项目名称**: Any Router 多账号自动签到 (anyrouter-check-in)
- **核心功能**: 支持 Any Router 和 Agent Router 平台的自动化签到，绕过 WAF 限制，实时监控余额变化并多渠道通知。
- **技术栈**: 
  - **语言**: Python 3.11+
  - **网络**: `httpx` (HTTP/2 支持)
  - **自动化**: `playwright` (用于 WAF 绕过)
  - **包管理**: `uv`
  - **质控**: `ruff`, `mypy`, `bandit`, `pytest`

## 2. 逻辑地图
- **`checkin.py`**: 主入口，管理异步任务流。
  - `main()`: 控制全局流程，比对 `balance_hash.txt` 判断是否需通知。
  - `check_in_account()`: 单账号执行逻辑，包含获取 WAF Cookie 和签到请求。
- **`utils/config.py`**: 强类型配置管理。
  - `AppConfig`: 加载内置和自定义 `PROVIDERS`。
  - `AccountConfig`: 解析 `ANYROUTER_ACCOUNTS` 环境变量。
- **`utils/notify.py`**: 通知中转站，支持 Email, 钉钉, 飞书, 企业微信, Telegram, Bark 等 9 种通道。
- **持久化**: 通过 `balance_hash.txt` 记录上一次余额状态，实现“仅在变化时通知”。

## 3. 功能总结与现状
- **多端适配**: 完美兼容 NewAPI/OneAPI 架构。
- **安全保障**: 使用 Playwright 模拟真实浏览器行为获取 WAF Cookie。
- **智能计算**: 自动计算签到奖励及期间消耗额度。

## 4. 潜在问题/改进建议
- **环境依赖**: Playwright 依赖浏览器二进制文件，部署时需额外运行 `playwright install`。
- **配置复杂度**: 环境变量中的 JSON 字符串对用户书写格式要求较高。
- **WAF 演进**: 网站 WAF 策略升级可能导致 Playwright 模拟被识别（当前已通过 `AutomationControlled` 等参数优化）。
- **容错性**: 目前 partial success 时仍返回退出码 0，可考虑细化异常状态。

---
**索引已就绪**。项目背景、逻辑链路及环境细节已记录，Sonnet 模型可直接接力。
