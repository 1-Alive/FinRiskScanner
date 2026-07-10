# IndoApp Classifier Agent

一个基于 Python + Flask 的印尼 App 分类工具，支持：

- 单条描述分类
- 单条包名 + 描述联合分类
- Excel/CSV 批量打标
- 实时查看批量进度
- 导出分类结果

## 启动方式

```powershell
python app.py
```

浏览器打开：

```text
http://127.0.0.1:5000
```

## 批量文件要求

- 支持 `.xlsx`、`.xls`、`.csv`
- 可手动填写描述列名
- 可手动填写包名列名
- 若不填写，系统会优先识别 `description`、`app_description`、`desc`、`简介`、`描述`、`应用描述`
- 包名列会优先识别 `package_name`、`package`、`bundle_id`、`bundle`、`app_id`、`pkg`、`包名`
- 若仍无法命中，会自动选择最像文本描述的列
- 若描述为空，系统会根据包名进行分类推测

## 导出结果

导出文件会新增一列：

```text
category_result
```

## 分类规则说明

- 输出固定为完整路径
- 相同输入会得到相同输出
- 若描述过于模糊或不符合现有分类体系，当前默认回退为 `其他 (Others)`
- 当前分类逻辑不仅包含关键词规则，也包含主功能意图识别、语义加分和反向抑制逻辑，用于减少“命中词存在但业务意图并非该类”的误判
- 借贷类当前已支持细分为：`P2P借贷`、`小额现金贷`、`分期消费贷款`、`企业/商户贷款`、`抵押贷`
- 当前已额外支持欺诈类细分识别，包括：
- `欺诈 (Fraud) → 赌博 (Gambling)`
- `欺诈 (Fraud) → 博彩 (Betting)`
- `欺诈 (Fraud) → 刷单返利 (Task/Rebate Scam)`

## 规则配置

- 分类词库已拆分到 `config/rules.json`
- 你可以直接修改 `fallback_category`
- 每条规则包含 `path`、`priority`、`keywords`
- 修改后重新启动 `python app.py` 即可生效
