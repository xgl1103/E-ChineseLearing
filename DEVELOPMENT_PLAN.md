# AI Lesson Recorder 开发文档

## 1. 第一性原理

本项目的目标不是“做一个能总结课堂录音的 AI demo”，而是构建一条可信的课后反馈生成闭环：

```text
课堂内容
  -> 可追溯证据
  -> 结构化报告
  -> 质量评审
  -> 老师确认
  -> 学生/家长可执行反馈
```

一个合格的 MVP 必须满足：

- 老师能看懂 AI 为什么这样总结。
- 作业、纠错、发音反馈能回溯到课堂证据。
- 低置信内容不会伪装成确定结论。
- AI 不直接把报告发给学生或家长，必须经过老师确认。
- 前后端、Prompt、测试数据共享同一份结构化 schema。

因此开发原则是：

```text
先做端到端闭环，再接真实模型。
先固定 schema，再并行开发。
先让老师审核页可演示，再逐步补真实 pipeline。
```

## 2. MVP 范围

## 2.1 必做

- 老师审核工作台。
- 课堂转写展示。
- 证据时间戳展示。
- 低置信内容高亮。
- 作业候选勾选与编辑。
- 发音反馈展示与确认。
- 老师确认报告。
- 生成老师版、学生版、家长版报告。
- 后端 mock pipeline。
- 统一 JSON schema。
- demo 课堂样例数据。
- Writer / Reviewer / Rule Validator prompt 文档。

## 2.2 暂不做

- 真实 ASR 接入。
- 真实 Azure Pronunciation Assessment 接入。
- 真实音频上传和 VAD 切分。
- 用户登录。
- 数据库持久化。
- 多学生管理。
- 正式生产级权限系统。

这些功能进入第二阶段或第三阶段。

## 3. 推荐目录结构

```text
e-chineselearing/
  frontend/
    src/
      app/
      components/
      lib/
      styles/
    package.json
    README.md

  backend/
    app/
      main.py
      schemas.py
      mock_data.py
      pipeline/
        transcript_processor.py
        evidence_extractor.py
        confidence_scorer.py
        report_writer.py
        rule_validator.py
        report_reviewer.py
        final_report_generator.py
    requirements.txt
    README.md

  shared/
    schema.json
    types.md

  data/
    demo_lesson.json

  prompts/
    writer_prompt.md
    reviewer_prompt.md
    rule_validator.md

  docs/
    demo_script.md
    architecture.md

  DEVELOPMENT_PLAN.md
  README.md
```

## 4. 并行开发角色

建议开 3 个 Codex 进程。

## 4.1 进程 A：前端工作台

职责：

- 实现老师审核工作台。
- 读取后端 API 或本地 `data/demo_lesson.json`。
- 展示课堂转写、证据、AI 报告、低置信高亮。
- 支持老师编辑作业、确认风险点、生成最终报告。
- 做出可演示的 SaaS 风格界面。

只负责修改：

```text
frontend/
```

可以只读：

```text
shared/schema.json
data/demo_lesson.json
```

验收标准：

- 打开页面即可看到完整 demo lesson。
- 老师能编辑作业。
- 老师能确认低置信内容。
- 能切换老师版、学生版、家长版报告。
- UI 不像纯技术 demo，而像真实教师工作台。

## 4.2 进程 B：后端 Pipeline

职责：

- 实现 FastAPI mock backend。
- 输出符合 `shared/schema.json` 的结构化 lesson report。
- 实现 mock pipeline：

```text
demo transcript
  -> evidence extractor
  -> confidence scorer
  -> report writer
  -> rule validator
  -> report reviewer
  -> final report generator
```

只负责修改：

```text
backend/
```

可以只读：

```text
shared/schema.json
data/demo_lesson.json
prompts/
```

验收标准：

- `GET /api/lessons/demo` 返回完整 lesson 对象。
- `POST /api/lessons/demo/analyze` 返回 AI draft report。
- `POST /api/lessons/{lesson_id}/teacher-review` 接收老师修改。
- `POST /api/lessons/{lesson_id}/finalize` 返回三类最终报告。
- Rule Validator 能拦截明显错误。

## 4.3 进程 C：数据、Prompt、文档

职责：

- 设计 demo 课堂样例。
- 完善 `data/demo_lesson.json`。
- 编写 Writer Agent prompt。
- 编写 Reviewer Agent prompt。
- 编写 Rule Validator 规则。
- 编写面试演示脚本。
- 维护 `docs/architecture.md`。

只负责修改：

```text
data/
prompts/
docs/
```

可以只读：

```text
shared/schema.json
```

验收标准：

- demo 数据覆盖中英混合、学生疑问、老师纠错、作业布置、发音评估。
- prompt 能约束 Agent 不根据 ASR 文本臆测发音。
- reviewer rubric 能检查证据、置信度和家长友好度。
- demo script 能支撑 2-3 分钟面试演示。

## 5. 共享接口契约

所有进程围绕同一个 lesson object 开发。

## 5.1 Lesson Object

```json
{
  "lesson_id": "demo_001",
  "metadata": {},
  "transcripts": {
    "teacher": [],
    "student": []
  },
  "practice_clips": [],
  "pronunciation_assessments": [],
  "evidence": {},
  "confidence_scores": {},
  "draft_report": {},
  "rule_validation_result": {},
  "review_result": {},
  "risk_highlights": [],
  "teacher_review": {},
  "final_reports": {
    "teacher": {},
    "student": {},
    "parent": {}
  },
  "teacher_edit_log": []
}
```

## 5.2 Metadata

```json
{
  "student_name": "Alex Chen",
  "student_age": 10,
  "student_level": "YCT 3",
  "course_type": "Kids Chinese",
  "lesson_topic": "餐厅点餐",
  "lesson_duration_minutes": 45,
  "teacher_name": "Ms. Lin",
  "lesson_date": "2026-07-09"
}
```

## 5.3 Transcript Segment

```json
{
  "segment_id": "t_001",
  "speaker": "teacher",
  "start_time": 12.4,
  "end_time": 18.7,
  "text": "Please repeat after me: 我想要一杯果汁。",
  "language_tags": ["en", "zh-CN"],
  "asr_confidence": 0.94
}
```

变量说明：

- `segment_id`：转写片段唯一 ID。
- `speaker`：`teacher` 或 `student`。
- `start_time` / `end_time`：音频秒级时间戳。
- `text`：ASR 转写文本。
- `language_tags`：片段语言类型。
- `asr_confidence`：ASR 置信度。

## 5.4 Practice Clip

```json
{
  "clip_id": "clip_001",
  "student_segment_id": "s_003",
  "audio_uri": "/mock/student_493200_496800.wav",
  "clip_start": 493.2,
  "clip_end": 496.8,
  "reference_text": "我想要一杯果汁",
  "reference_source": "teacher_repeat_instruction",
  "reference_confidence": "high",
  "should_assess_pronunciation": true
}
```

变量说明：

- `reference_text`：发音评估标准文本。
- `reference_source`：标准文本来源。
- `reference_confidence`：`high` / `medium` / `low`。
- `should_assess_pronunciation`：是否进入发音评估。

规则：

- 只有 `reference_confidence = high` 时才做精细发音评分。
- `medium` 只做轻量反馈并高亮给老师。
- `low` 不做发音评分，只作为候选内容。

## 5.5 Pronunciation Assessment

```json
{
  "assessment_id": "pa_001",
  "clip_id": "clip_001",
  "reference_text": "我想要一杯果汁",
  "pronunciation_score": 78,
  "accuracy_score": 74,
  "fluency_score": 82,
  "completeness_score": 100,
  "prosody_score": 76,
  "low_score_words": [
    {
      "word": "果汁",
      "accuracy_score": 58,
      "error_type": "Mispronunciation"
    }
  ],
  "model_confidence": "medium",
  "teacher_confirmation_required": true
}
```

规则：

- Writer Agent 只能根据此字段描述发音问题。
- 如果没有此字段，不允许生成确定的发音评价。
- 声调问题不能被写成确定结论，除非底层模型明确输出 tone-level 结果。

## 5.6 Evidence Object

```json
{
  "knowledge_points": [
    {
      "evidence_id": "ev_kp_001",
      "type": "knowledge_point",
      "source_segment_ids": ["t_001", "t_002"],
      "timestamp": "00:12",
      "claim": "本节课学习了“我想要……”句型。",
      "confidence": "high"
    }
  ],
  "homework": [
    {
      "evidence_id": "ev_hw_001",
      "type": "homework",
      "source_segment_ids": ["t_009"],
      "timestamp": "36:20",
      "claim": "老师布置了跟读目标句 5 遍的作业。",
      "confidence": "high"
    }
  ],
  "corrections": [
    {
      "evidence_id": "ev_cr_001",
      "type": "correction",
      "source_segment_ids": ["s_004", "t_005"],
      "timestamp": "18:42",
      "student_original": "我想要一个果汁",
      "teacher_correction": "一杯果汁",
      "confidence": "high"
    }
  ]
}
```

规则：

- 报告中的确定性结论必须能关联至少一个 `evidence_id`。
- 没有 evidence 的内容只能作为建议或候选，不写成事实。

## 5.7 Confidence Scores

```json
{
  "homework_extraction": "high",
  "student_question_extraction": "medium",
  "pronunciation_reference_text": "medium",
  "correction_extraction": "high",
  "overall_report_reliability": "medium"
}
```

## 5.8 Risk Highlight

```json
{
  "risk_id": "risk_001",
  "level": "medium",
  "module": "pronunciation",
  "message": "“果汁”的发音反馈来自中置信 reference_text，建议老师确认。",
  "related_ids": ["pa_001", "clip_001"],
  "teacher_action": "confirm_or_edit"
}
```

## 5.9 Draft Report

```json
{
  "lesson_summary": "本节课围绕餐厅点餐展开。",
  "knowledge_points": [],
  "teacher_questions": [],
  "student_questions": [],
  "corrections": [],
  "pronunciation_feedback": [],
  "homework_items": [],
  "student_assessment": {},
  "next_lesson_suggestions": []
}
```

## 5.10 Homework Item

```json
{
  "homework_id": "hw_001",
  "title": "跟读目标句",
  "description": "朗读 5 遍“我想要一杯果汁”。",
  "type": "recording",
  "source_evidence_id": "ev_hw_001",
  "confidence": "high",
  "teacher_confirmed": false
}
```

## 6. API 设计

## 6.1 获取 Demo Lesson

```http
GET /api/lessons/demo
```

返回：

```json
{
  "lesson": {}
}
```

用途：

- 前端初次加载 demo 数据。
- 不触发重新分析。

## 6.2 触发分析

```http
POST /api/lessons/demo/analyze
```

请求：

```json
{
  "mode": "mock",
  "include_pronunciation": true
}
```

返回：

```json
{
  "lesson_id": "demo_001",
  "draft_report": {},
  "evidence": {},
  "confidence_scores": {},
  "risk_highlights": [],
  "review_result": {}
}
```

用途：

- 模拟 ASR 后的 AI 报告生成流程。
- 后续真实接入时可把 `mode` 改为 `real`。

## 6.3 提交老师审核

```http
POST /api/lessons/{lesson_id}/teacher-review
```

请求：

```json
{
  "confirmed_homework_ids": ["hw_001"],
  "edited_homework_items": [],
  "confirmed_risk_ids": ["risk_001"],
  "teacher_notes": "下节课继续练习量词。",
  "report_edits": {}
}
```

返回：

```json
{
  "teacher_review": {
    "status": "confirmed",
    "reviewed_at": "2026-07-09T18:00:00+08:00"
  },
  "teacher_edit_log": []
}
```

## 6.4 生成最终报告

```http
POST /api/lessons/{lesson_id}/finalize
```

请求：

```json
{
  "audiences": ["teacher", "student", "parent"]
}
```

返回：

```json
{
  "final_reports": {
    "teacher": {},
    "student": {},
    "parent": {}
  }
}
```

## 7. Pipeline 模块职责

## 7.1 Transcript Processor

输入：

- teacher transcript
- student transcript

输出：

- 统一格式的 transcript segments。
- language tags。
- asr confidence。

## 7.2 Evidence Extractor

输入：

- transcript segments
- pronunciation assessments

输出：

- knowledge evidence
- homework evidence
- correction evidence
- student question evidence
- pronunciation evidence

规则：

- 证据必须带 source segment 和 timestamp。
- 作业证据优先来自老师端音轨。

## 7.3 Confidence Scorer

输入：

- evidence
- ASR confidence
- reference confidence
- model confidence

输出：

- module-level confidence scores。
- risk highlights。

## 7.4 Report Writer

输入：

- transcript
- evidence
- confidence scores
- pronunciation assessments

输出：

- draft report。

规则：

- 不能根据 ASR 文本判断发音标准。
- 不能写没有 evidence 的确定结论。
- 低置信内容必须以“建议老师确认”表达。

## 7.5 Rule Validator

输入：

- draft report
- evidence
- confidence scores

输出：

- pass / fail
- blocking issues
- warnings

硬规则：

- 发音反馈必须有 pronunciation assessment。
- 作业必须有关联 evidence 或 teacher confirmation。
- 学生评分必须有依据。
- 低置信内容必须出现在 risk highlights。
- Writer-Reviewer 循环不得超过 2 次。

## 7.6 Report Reviewer

输入：

- draft report
- rule validation result

输出：

- review score
- pass / fail
- revision instruction

评审维度：

- 完整性
- 准确性
- 可执行性
- 家长友好度
- 安全合规
- 证据绑定

## 7.7 Final Report Generator

输入：

- teacher-confirmed draft report
- target audiences

输出：

- teacher report
- student report
- parent report

规则：

- 家长版减少技术术语。
- 学生版突出作业和练习。
- 老师版保留证据、时间戳和低分词。

## 8. 开发阶段计划

## 8.1 阶段 0：契约冻结

负责人：

- 主进程

任务：

- 创建 `shared/schema.json`。
- 创建 `data/demo_lesson.json`。
- 创建基础目录。
- 确定 API 路由。

验收：

- 三个进程都能围绕同一份 schema 开发。

## 8.2 阶段 1：Mock 端到端闭环

负责人：

- A：前端工作台。
- B：后端 mock API。
- C：demo 数据和 prompt。

目标：

```text
前端调用后端 mock API
  -> 展示 AI 课后报告
  -> 老师确认
  -> 生成三类报告
```

验收：

- 不接真实模型也能完整演示。
- 用户能理解产品价值。

## 8.3 阶段 2：可信 AI 控制点

负责人：

- A：低置信内容高亮和老师确认交互。
- B：Evidence Extractor、Confidence Scorer、Rule Validator。
- C：Reviewer rubric、risk examples、demo script。

验收：

- 每个作业和纠错点都有 evidence。
- 低置信内容出现在 risk highlights。
- Rule Validator 能拦截错误报告。

## 8.4 阶段 3：LangGraph 雏形

负责人：

- B 为主。
- C 提供 prompts。
- A 适配返回结构。

目标：

```text
Writer Node
  -> Rule Validator Node
  -> Reviewer Node
  -> conditional edge
  -> Teacher Review State
  -> Final Report Node
```

验收：

- 代码层面能展示写作-评审循环。
- 最多循环 2 次。
- 不通过时返回结构化修改意见。

## 8.5 阶段 4：真实模型接入，可选

负责人：

- B 为主。

优先级：

1. 真实 LLM 生成报告。
2. 真实 ASR。
3. 真实音频上传。
4. 真实 Pronunciation Assessment。
5. 真实 VAD。

说明：

- 面试 demo 不依赖这一阶段完成。
- 先保证 mock demo 稳定。

## 9. 启动三个 Codex 进程的提示词

## 9.1 进程 A 提示词

```text
你负责 frontend/。请基于 shared/schema.json 和 data/demo_lesson.json 实现老师审核工作台。

目标：展示课堂转写、证据时间戳、AI 报告、低置信风险高亮、作业候选勾选、发音反馈确认，并能生成老师版/学生版/家长版报告预览。

不要修改 backend/、data/、prompts/、docs/。
```

## 9.2 进程 B 提示词

```text
你负责 backend/。请实现 FastAPI mock pipeline，输出符合 shared/schema.json 的 lesson object。

需要实现 API：
- GET /api/lessons/demo
- POST /api/lessons/demo/analyze
- POST /api/lessons/{lesson_id}/teacher-review
- POST /api/lessons/{lesson_id}/finalize

需要实现模块：
Transcript Processor、Evidence Extractor、Confidence Scorer、Report Writer、Rule Validator、Report Reviewer、Final Report Generator。

不要修改 frontend/、data/、prompts/、docs/。
```

## 9.3 进程 C 提示词

```text
你负责 data/、prompts/、docs/。请完善 demo_lesson.json、writer_prompt.md、reviewer_prompt.md、rule_validator.md 和 demo_script.md。

样例课堂主题为“餐厅点餐”，必须覆盖：
- 老师英文讲解
- 学生中文回答
- 学生量词错误
- 老师纠正
- 学生主动疑问
- 老师布置课后跟读作业
- mock 发音评估结果
- risk highlights

不要修改 frontend/ 和 backend/。
```

## 9.4 阶段 5：真实 LLM Agent 层三进程提示词

阶段五目标：

```text
保留当前稳定 mock demo
  -> 增加真实 LLM provider 抽象
  -> Writer Agent / Reviewer Agent 可调用真实模型
  -> 输出必须通过 JSON schema 校验
  -> 校验失败可自动修复或回退 mock
  -> 前端能清楚展示当前使用的是 mock 还是 real LLM
```

阶段五不做真实 ASR、真实音频上传、真实发音评估模型。音频相关能力留给后续阶段。阶段五的第一性原理是：真实 LLM 只能替换“报告写作和评审判断”，不能破坏证据约束、规则校验、老师确认和现有演示闭环。

### 9.4.1 阶段五进程 A：前端工作台提示词

```text
你负责 frontend/。当前项目已经完成阶段三：后端有 LangGraph-style writer-reviewer loop，前端能展示 workflow_trace/graph_trace，并能完成 teacher-review/finalize 闭环。

本阶段目标：让老师端工作台能展示“真实 LLM Agent 层”的运行状态，但不要改后端核心逻辑。

你必须先阅读：
- DEVELOPMENT_PLAN.md
- shared/schema.json
- frontend/src/App.tsx
- frontend/src/lib/types.ts
- docs/demo_script.md
- backend/README.md

你本阶段只修改：
- frontend/
- 必要时可补充 frontend/README.md

不要修改：
- backend/
- data/
- prompts/
- shared/schema.json

开发任务：
1. 在前端增加 Agent Mode 展示：
   - mock pipeline
   - real LLM
   - fallback to mock
   - schema repair / validation warning
2. 适配后端阶段五可能返回的新字段，要求向后兼容：
   - agent_mode
   - model_provider
   - model_name
   - llm_trace
   - schema_validation
   - fallback_reason
3. 在 LangGraph Workflow 面板中展示：
   - writer_agent 是否来自真实 LLM
   - reviewer_agent 是否来自真实 LLM
   - JSON 校验是否通过
   - 是否发生 fallback
4. 页面不能因为这些字段缺失而崩溃。阶段三 mock 返回仍必须正常展示。
5. 不要加入大段解释文案。用状态 badge、tooltip、短标签展示。
6. 保持当前老师审核主流程不变：
   - 加载 analyze
   - 展示证据和报告
   - 老师确认作业和风险
   - 调用 teacher-review
   - 调用 finalize

建议实现：
- 在 types.ts 中补充可选类型：
  - agent_mode?: "mock" | "real_llm" | "fallback"
  - model_provider?: string
  - model_name?: string
  - llm_trace?: array
  - schema_validation?: object
  - fallback_reason?: string
- 在 App.tsx 的 mergeLessonPayload 中合并这些顶层字段。
- WorkflowPanel 中优先展示后端 trace 的 summary/status/metadata。
- 如果 metadata 中出现 model/provider/token/json_repair 等信息，用紧凑 badge 展示。

验收标准：
- npm run build 通过。
- 后端只返回阶段三字段时，前端不报错。
- 后端返回阶段五字段时，前端能显示 Agent Mode、模型名、fallback 状态、schema validation 状态。
- Confirm all and finalize 原流程不回退。
```

### 9.4.2 阶段五进程 B：后端 LLM Agent 提示词

```text
你负责 backend/。当前项目已经完成阶段三：FastAPI mock backend、LangGraph-style runner、writer-reviewer loop、teacher review gate、finalize 都已通过验收。

本阶段目标：接入真实 LLM Agent 层，但必须保留 mock fallback。没有 API key 时，项目仍然可以完整运行。

你必须先阅读：
- DEVELOPMENT_PLAN.md
- backend/README.md
- backend/app/main.py
- backend/app/schemas.py
- backend/app/graph/state.py
- backend/app/graph/nodes.py
- backend/app/graph/runner.py
- backend/app/pipeline/report_writer.py
- backend/app/pipeline/report_reviewer.py
- backend/app/pipeline/rule_validator.py
- prompts/writer_prompt.md
- prompts/reviewer_prompt.md
- shared/schema.json

你本阶段只修改：
- backend/
- backend/README.md
- backend/requirements.txt

不要修改：
- frontend/
- data/
- prompts/
- docs/
- shared/schema.json，除非发现后端无法表达必要字段；如需改 schema，先在文档里说明，不要直接大改。

核心原则：
1. Rule Validator 仍然是确定性代码，不交给 LLM。
2. Evidence Extractor、Confidence Scorer 暂时仍用现有 mock/规则逻辑。
3. 真实 LLM 只替换 Writer Agent 和 Reviewer Agent。
4. 所有 LLM 输出必须是结构化 JSON，并通过 Pydantic/schema 校验。
5. LLM 失败、超时、JSON 解析失败、schema 校验失败时，必须 fallback 到当前 mock writer/reviewer，不能影响 demo。
6. 不允许真实 LLM 绕过 teacher_review_gate。

开发任务：
1. 增加 LLM provider 抽象，例如：
   - backend/app/llm/client.py
   - backend/app/llm/config.py
   - backend/app/llm/json_utils.py
2. 支持环境变量配置：
   - LLM_PROVIDER=openai 或 mock
   - LLM_MODEL=...
   - OPENAI_API_KEY=...
   - LLM_TIMEOUT_SECONDS=...
   - LLM_MAX_RETRIES=...
   - LLM_ENABLE_REAL=0/1
3. 增加真实 writer 调用：
   - 输入 lesson/evidence/confidence/pronunciation/risk
   - 使用 prompts/writer_prompt.md
   - 输出 draft_report JSON
   - 用 backend.app.schemas.DraftReport 校验
   - 校验失败时尝试一次 JSON repair；仍失败则 fallback mock writer
4. 增加真实 reviewer 调用：
   - 输入 draft_report/evidence/pronunciation/confidence/risk/rule_validation_result
   - 使用 prompts/reviewer_prompt.md
   - 输出 ReviewResult JSON
   - 用 backend.app.schemas.ReviewResult 校验
   - 校验失败 fallback mock reviewer
5. 在 graph trace 中写入可观测信息：
   - agent_mode: mock / real_llm / fallback
   - model_provider
   - model_name
   - fallback_reason
   - schema_validation pass/fail
   - json_repair_attempted
   - latency_ms，可选
6. /api/lessons/demo/analyze 返回顶层字段：
   - agent_mode
   - model_provider
   - model_name
   - llm_trace
   - schema_validation
   - fallback_reason
   同时保留阶段三字段：
   - workflow_trace
   - graph_trace
   - revision_count
   - revision_history
   - stop_reason
7. mode 行为建议：
   - mode="mock"：强制走现有 mock pipeline。
   - mode="real"：尝试真实 LLM；失败 fallback mock，并返回 fallback_reason。
   - 如果 LLM_ENABLE_REAL != 1，即使 mode="real" 也 fallback mock。

验收命令：
- py -3.13 -m compileall backend
- py -3.13 -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
- POST /api/lessons/demo/analyze {"mode":"mock","include_pronunciation":true}
- POST /api/lessons/demo/analyze {"mode":"real","include_pronunciation":true}
- POST /api/lessons/demo/analyze {"mode":"real","include_pronunciation":false}

验收标准：
- 没有 API key 时，mode=real 不崩溃，返回 fallback_reason。
- mode=mock 与阶段三行为一致。
- include_pronunciation=false 仍会触发 writer-reviewer loop，并最终 manual_review。
- 真实 LLM 输出不得绕过 Rule Validator。
- teacher-review/finalize 原接口不回退。
```

### 9.4.3 阶段五进程 C：Prompt、数据、验收文档提示词

```text
你负责 prompts/、docs/，必要时可检查 data/demo_lesson.json，但不要随意改后端和前端代码。

当前项目已经完成阶段三。阶段五要把 Writer Agent 和 Reviewer Agent 从 deterministic mock 升级为可接真实 LLM 的 agent。你的任务是让 prompt、样例输入输出、验收脚本足够清晰，帮助进程 B 接入真实模型，帮助主进程验收。

你必须先阅读：
- DEVELOPMENT_PLAN.md
- prompts/writer_prompt.md
- prompts/reviewer_prompt.md
- prompts/rule_validator.md
- docs/demo_script.md
- docs/architecture.md
- shared/schema.json
- data/demo_lesson.json
- backend/app/schemas.py

你本阶段只修改：
- prompts/
- docs/
- 必要时 data/demo_lesson.json 的注释性/样例性内容，但不要破坏现有 schema

不要修改：
- frontend/
- backend/
- shared/schema.json

开发任务：
1. 修订 writer_prompt.md：
   - 明确只输出 JSON。
   - 明确输出必须匹配 DraftReport。
   - 明确每个事实项必须有 source_evidence_ids 或 source_evidence_id。
   - 明确 pronunciation_feedback 只能使用 pronunciation_assessments。
   - 明确低置信内容必须 teacher_confirmation_required 或进入 risk。
   - 明确不要生成 final_reports。
2. 修订 reviewer_prompt.md：
   - 明确只输出 ReviewResult JSON。
   - 明确 pass/fail 标准。
   - 明确如果 rule_validation_result.pass=false，reviewer 必须 pass=false。
   - 明确 revision_instruction 要能被 Writer Agent 直接执行。
3. 新增或更新 docs/phase5_llm_agent_acceptance.md：
   - 阶段五目标
   - 三个模式：mock / real / fallback
   - 环境变量说明
   - 接口验收请求
   - 成功路径验收
   - 失败路径验收
   - JSON schema 校验标准
   - 面试演示讲法
4. 更新 docs/demo_script.md：
   - 增加一段 30-45 秒话术，说明为什么真实 LLM 必须被 Rule Validator、Reviewer 和 teacher gate 约束。
   - 增加 fallback 讲法：即使模型不可用，产品流程仍可演示。
5. 整理 prompt 中的中文编码问题。如果发现乱码，改成正常中文或英文；不要保留乱码样例。

验收标准：
- prompts 能直接被后端读取。
- 每个 prompt 都明确“只输出 JSON”。
- docs/phase5_llm_agent_acceptance.md 能指导主进程完成验收。
- demo_script 能支持面试讲解“真实 LLM + 可信 AI 控制点”。
```

## 10. 最终验收标准

一个合格 demo 应该能在 3 分钟内演示：

1. 选择 demo lesson。
2. 点击生成 AI 报告。
3. 展示课堂证据和时间戳。
4. 展示发音评估和低置信风险。
5. 老师确认或修改作业。
6. 生成学生版和家长版报告。
7. 说明老师修改会反哺 prompt、rubric 和词表。

面试表达重点：

> 我们不是简单做录音总结，而是做一个有证据、有置信度、有评审、有老师确认的 AI 课后反馈系统。
