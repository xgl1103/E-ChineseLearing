# Docker 一键启动

## 前置条件

- 已安装 Docker Desktop。
- 如果要现场展示真实 LLM/ASR，确认 `backend/.env` 已配置：
  - `LLM_ENABLE_REAL=1`
  - `LLM_PROVIDER=deepseek`
  - `LLM_MODEL=deepseek-v4-flash`
  - `DEEPSEEK_API_KEY=...`
  - `ASR_PROVIDER=bailian`
  - `BAILIAN_ASR_MODEL=fun-asr-flash-2026-06-15`
  - `BAILIAN_API_KEY=...`

Azure Pronunciation Assessment 未配置时，系统会自动跳过真实发音评估或使用 mock 结果，不影响 demo 主流程。

## 启动

```powershell
cd F:\code\e-chineselearing
.\start-docker.ps1
```

或直接：

```powershell
docker compose up --build
```

## 访问

- 前端页面：`http://127.0.0.1:5173`
- 后端 Swagger：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:5173/health`

## 关闭

```powershell
docker compose down
```

## 数据持久化

上传或录音文件会保存到项目目录下的 `.uploads/`，并挂载到后端容器。

## 面试演示建议

1. 启动容器后打开 `http://127.0.0.1:5173`。
2. 选择长课程演示样本。
3. 点击创建并开始分析，展示双音轨、课堂转写、发音片段和作业抽取。
4. 新建课程入口会传 `agent_mode=real`，在 `backend/.env` 配置 DeepSeek 后会真实运行 Writer Agent 和 Reviewer Agent。
5. 在老师确认环节确认作业，再生成最终报告。
