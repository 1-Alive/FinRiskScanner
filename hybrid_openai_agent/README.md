# IndoApp Classifier Agent Hybrid

基于原项目独立新建的升级版，采用“OpenAI 大模型主分类 + 规则校验”架构。

## 特性

- 大模型优先完成分类，覆盖长描述和复杂意图
- 规则负责校验模型结果，特别强化金融借贷细分
- 借贷类强冲突时会触发一次带规则证据的模型复核
- 单条测试展示决策来源、模型、规则路径和说明
- Excel/CSV 批量打标并导出完整审计列

## 启动

```powershell
pip install -r requirements.txt
```

复制环境变量模板并填写：

```powershell
Copy-Item .env.example .env
```

然后设置 `OPENAI_API_KEY`。默认模型是 `gpt-5.4-mini`，端口是 `5001`。

启动服务：

```powershell
python app.py
```

浏览器打开：

```text
http://127.0.0.1:5001
```

## 环境变量

- `OPENAI_API_KEY`: 必填，开启大模型主分类
- `OPENAI_MODEL`: 默认 `gpt-5.4-mini`
- `OPENAI_REASONING_EFFORT`: 默认 `low`
- `OPENAI_BASE_URL`: 可选，自定义 OpenAI 兼容网关地址
- `HTTP_PROXY`: 可选，HTTP 代理
- `HTTPS_PROXY`: 可选，HTTPS 代理
- `ENABLE_LLM_PRIMARY`: `true` 或 `false`
- `RULE_VALIDATION_THRESHOLD`: 一般规则强冲突阈值
- `RULE_VALIDATION_MARGIN`: 一般规则候选分差阈值
- `LOAN_VALIDATION_THRESHOLD`: 借贷细分强校验阈值
- `LOAN_VALIDATION_MARGIN`: 借贷细分分差阈值

## 批量导出列

- `category_result`
- `decision_source`
- `model_used`
- `rule_path`
- `decision_reason`

## 说明

- 未设置 `OPENAI_API_KEY` 时，项目仍可运行，但会退化为纯规则模式
- 分类词库仍在 `config/rules.json`
- 当前默认对金融借贷类描述做更严格的规则校验和复核

## 连通性测试

如果页面提示大模型不可用，可以运行：

```powershell
python connectivity_test.py
```

这个脚本会检查：

- `.env` 是否被正确读取
- `OPENAI_API_KEY` 是否存在
- `OPENAI_BASE_URL` 是否可达
- `HTTP_PROXY` / `HTTPS_PROXY` 是否已配置
- 真实 OpenAI API 请求是否成功
