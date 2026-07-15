# 衡契｜天河中小企业合同风险助手

阶段四参赛展示版本，核心链路：

```text
上传DOCX/PDF/TXT或粘贴文本 -> 提取带位置合同块 -> 原创规则审查 -> 可选DeepSeek V4复核 -> 风险提示
```

## 当前状态

- 页面右上角提供“连接AI”，可直接选择SiliconFlow或DeepSeek、填写密钥并测试连接，不需要修改源码。
- 未连接AI时，页面会明确显示“本地规则演示”，不会冒充AI输出。
- 配置DeepSeek密钥后，使用`deepseek-v4-pro`补充跨条款风险，并对引用原文进行后端验证。
- 使用SiliconFlow时，网页默认填入`deepseek-ai/DeepSeek-V4-Flash`；默认关闭思考模式以控制响应时间和费用。
- 支持DOCX、文本型PDF、TXT及粘贴文本。
- 支持风险等级、领域、发现方式筛选及关键词搜索。
- 支持一键复制修改建议和谈判话术、导出Markdown审查报告。
- 支持近期审查记录，结构化结果默认保留24小时，合同全文不入库。
- 桌面端和移动端均使用响应式布局。
- 当前不支持扫描PDF、旧版DOC和在线修订。

## 本地运行

### 本机一键启动（Windows）

当前开发机已经准备好Python依赖和前端生产构建。双击项目根目录的：

```text
start-local.cmd
```

然后访问：

```text
http://127.0.0.1:8765
```

停止时双击`stop-local.cmd`。启动器只监听`127.0.0.1`，不会向局域网或公网开放端口。

如需真实AI，将`.env.local.example`复制为`.env.local`并填写服务端密钥。`.env.local`已被Git忽略；不要将密钥提交到仓库。

### 从零安装

后端：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:AI_API_KEY="你的DeepSeek密钥"  # 可选；也可以启动后在网页中连接
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

开发模式访问`http://127.0.0.1:5173`。

生产构建后，也可以让FastAPI直接提供`frontend/dist`中的静态文件。

访问`http://127.0.0.1:8000/?demo=1`可自动载入项目自带的原创示例合同并完成一次审查，便于验收和录制演示；普通访问不会自动执行。

## 自动测试

```powershell
cd backend
python -m unittest discover -s tests -v
```

测试覆盖文本、DOCX、PDF解析，核心风险规则，虚构AI引用拦截，SiliconFlow请求参数，近期审查接口及完整API流程。

## 数据处理

- 文件在内存中解析，不写入公开静态目录。
- SQLite只保存结构化结果，不保存合同全文。
- 结果默认保留24小时。
- 从网页连接时，API密钥只保存在本机服务进程内存中，不写入源码、浏览器存储或数据库；停止服务后需要重新填写。
- AI配置接口仅允许从本机访问，供应商接口地址使用内置白名单。
- 本地部署可从`.env.local`读取密钥，该文件不会提交到Git。

## 原创与依赖

业务代码、审查规则、示例合同和界面为本项目原创。第三方依赖及许可证见[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
