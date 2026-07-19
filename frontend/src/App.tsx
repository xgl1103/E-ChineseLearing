import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  CircleCheck,
  ClipboardCheck,
  ChevronDown,
  ChevronRight,
  Clock3,
  FileText,
  Languages,
  ListChecks,
  MessageSquareText,
  Mic2,
  Pencil,
  Plus,
  Send,
  Settings2,
  ShieldCheck,
  Sparkles,
  UploadCloud,
  UserRoundCheck,
  X
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { mockLesson } from "./lib/mockLesson";
import { createT, LangContext, useT, type Lang, type TranslationKey } from "./lib/i18n";
import type {
  Audience,
  AudioSource,
  AudioIngestResult,
  Confidence,
  CourseFilter,
  CourseListItem,
  DemoSampleId,
  HomeworkItem,
  LessonObject,
  LlmTraceItem,
  NewLessonDraft,
  ReportObject,
  RiskHighlight,
  SchemaValidationResult,
  WorkflowStatus,
  WorkflowTraceItem
} from "./lib/types";

const DIRECT_API_BASE = import.meta.env.VITE_API_BASE ?? "";
const PROXY_API_BASE = "";
const DEMO_LESSON_ID = "demo_001";
type RecordingTrack = "teacher" | "student";
type RecordingStatus = "idle" | "recording" | "stopped" | "error";

interface RecordedTrack {
  track: RecordingTrack;
  blob: Blob;
  filename: string;
  mimeType: string;
  durationSeconds: number;
  objectUrl: string;
}
const mojibakePattern = /[ÂÃÄÅÆÇÈÉÐÑÒÓÔÕÖØÙÚÛÜÝÞßà-ÿ]|â[\u0080-\u00bf]/;

const confidenceLabelMap: Record<Confidence, TranslationKey> = {
  high: "high",
  medium: "needsReview",
  low: "low",
  unknown: "unknown"
};

function confidenceLabelText(confidence: Confidence, t: (key: TranslationKey) => string): string {
  return t(confidenceLabelMap[confidence] ?? "unknown");
}

const riskRank: Record<string, number> = {
  high: 0,
  medium: 1,
  low: 2
};

const workflowNodeDefinitions = [
  { id: "transcript_processor", labelKey: "nodeTranscriptProcessor" as const },
  { id: "evidence_extractor", labelKey: "nodeEvidenceExtractor" as const },
  { id: "confidence_scorer", labelKey: "nodeConfidenceScorer" as const },
  { id: "report_writer", labelKey: "nodeReportWriter" as const },
  { id: "rule_validator", labelKey: "nodeRuleValidator" as const },
  { id: "report_reviewer", labelKey: "nodeReportReviewer" as const },
  { id: "teacher_review", labelKey: "nodeTeacherReview" as const },
  { id: "final_report_generator", labelKey: "nodeFinalReportGenerator" as const }
] as const;

type WorkflowNodeId = (typeof workflowNodeDefinitions)[number]["id"];

interface WorkflowNodeView {
  id: WorkflowNodeId;
  label: string;
  status: WorkflowStatus;
  detail: string;
  source: "backend" | "inferred";
  badges: string[];
}

interface AgentRuntimeView {
  mode: string;
  provider?: string;
  model?: string;
  schemaStatus: WorkflowStatus;
  schemaLabel: string;
  fallbackReason?: string;
  writerMode?: string;
  reviewerMode?: string;
}

type AppView = "list" | "new" | "workspace";

const archivedCourses: CourseListItem[] = [
  { lessonId: "lesson_002", studentName: "Emma Smith", topic: "问路", date: "2026-07-08", duration: 25, status: "ready_to_send", teacher: "Li Laoshi", interactive: true },
  { lessonId: "lesson_003", studentName: "Tom Brown", topic: "购物对话", date: "2026-07-07", duration: 35, status: "sent", teacher: "Wang Laoshi", interactive: true },
  { lessonId: "lesson_004", studentName: "Sophie Lee", topic: "家庭成员", date: "2026-07-06", duration: 28, status: "review_required", teacher: "Zhang Laoshi", interactive: true }
];

function defaultNewLesson(metadata: LessonObject["metadata"]): NewLessonDraft {
  return {
    studentName: metadata.student_name,
    studentAge: metadata.student_age,
    studentLevel: metadata.student_level,
    teacherName: metadata.teacher_name,
    topic: metadata.lesson_topic,
    date: metadata.lesson_date,
    duration: metadata.lesson_duration_minutes
  };
}

function courseStatusKey(status: CourseListItem["status"]): TranslationKey {
  if (status === "processing") return "statusProcessing";
  if (status === "ready_to_send") return "statusReadyToSend";
  if (status === "sent") return "statusSent";
  return "statusReviewRequired";
}

function audienceLabelKey(audience: Audience): TranslationKey {
  if (audience === "student") return "studentReport";
  if (audience === "parent") return "parentReport";
  return "teacherReport";
}

function riskProductCopy(risk: RiskHighlight, lang: Lang) {
  const module = risk.module.toLowerCase();
  const isZh = lang === "zh";
  if (module.includes("homework")) {
    return {
      title: isZh ? "确认课后作业" : "Confirm homework",
      message: isZh
        ? "部分作业由 AI 根据课堂内容推断，请确认它是否确实由老师布置。"
        : "Some homework was inferred from the lesson. Confirm that the teacher actually assigned it."
    };
  }
  if (module.includes("student_question")) {
    return {
      title: isZh ? "核对学生疑问" : "Verify the student question",
      message: isZh
        ? "学生疑问的措辞可能受到转写误差影响，请结合课堂原话核对。"
        : "The wording may be affected by transcription errors. Check it against the lesson evidence."
    };
  }
  if (module.includes("pronunciation")) {
    return {
      title: isZh ? "确认发音反馈" : "Confirm pronunciation feedback",
      message: isZh
        ? "发音结论包含中低置信结果，请回听学生片段后决定是否保留。"
        : "Pronunciation feedback contains lower-confidence results. Review the student clip before keeping it."
    };
  }
  if (module.includes("overall")) {
    return {
      title: isZh ? "完成报告核对" : "Complete report review",
      message: isZh
        ? "报告仍包含需要老师判断的内容，完成其他待确认项后即可生成最终版本。"
        : "The report still contains items requiring teacher judgment. Resolve them before finalizing."
    };
  }
  return {
    title: isZh ? "核对 AI 建议" : "Review AI suggestion",
    message: isZh ? "该内容需要老师结合课堂证据确认。" : "Confirm this item against the lesson evidence."
  };
}

function lessonSummaryText(lesson: LessonObject, lang: Lang, fallback: string) {
  const summary = lesson.draft_report.lesson_summary;
  if (!summary) return fallback;
  if (lang === "zh" && /\bpracticed\b|\bAI draft\b/i.test(summary)) {
    return `${lesson.metadata.student_name} 本节课围绕“${lesson.metadata.lesson_topic}”展开，AI 已整理课堂重点、纠错、发音反馈和课后作业，等待老师确认。`;
  }
  return summary;
}

interface ProductReportView {
  title: string;
  sections: Array<{ heading: string; items: string[] }>;
}

function buildProductReport(
  lesson: LessonObject,
  audience: Audience,
  lang: Lang,
  homework: HomeworkItem[],
  teacherNote: string,
  fallback: string
): ProductReportView {
  const isZh = lang === "zh";
  const summary = lessonSummaryText(lesson, lang, fallback).replace("等待老师确认", "老师已完成审核");
  const list = (items: Array<ReportObject | HomeworkItem> | undefined) =>
    (items ?? []).map((item) => getText(item)).filter(Boolean);
  const corrections = list(lesson.draft_report.corrections);
  const knowledgePoints = list(lesson.draft_report.knowledge_points);
  const suggestions = list(lesson.draft_report.next_lesson_suggestions).map((item) =>
    isZh && /review measure words|restaurant-ordering role play/i.test(item)
      ? "复习“一杯、一份、一碗”等量词，并安排一次餐厅点餐角色扮演。"
      : item
  );
  const homeworkItems = homework.map((item) => {
    if (isZh && item.description.startsWith('Use "我想要')) {
      return "使用“我想要……”和“多少钱？”完成一段简短的点餐对话。";
    }
    return item.description;
  });
  const pronunciation = lesson.pronunciation_assessments.map((assessment) => {
    const lowWords = assessment.low_score_words.map((word) => word.word).join("、");
    if (isZh) {
      return `“${assessment.reference_text}”整体得分 ${assessment.pronunciation_score}，${lowWords ? `重点关注：${lowWords}` : "整体表现稳定"}。`;
    }
    return `${assessment.reference_text}: ${assessment.pronunciation_score}/100${lowWords ? `; focus on ${lowWords}` : "; performance is stable"}.`;
  });

  if (audience === "student") {
    return {
      title: isZh ? `${lesson.metadata.student_name} 的课后练习` : `${lesson.metadata.student_name}'s lesson practice`,
      sections: [
        { heading: isZh ? "今天学了什么" : "What you practiced", items: [summary, ...knowledgePoints] },
        { heading: isZh ? "需要复习" : "What to review", items: corrections.length > 0 ? corrections : suggestions },
        { heading: isZh ? "课后作业" : "Homework", items: homeworkItems }
      ]
    };
  }

  if (audience === "parent") {
    return {
      title: isZh ? `${lesson.metadata.student_name} 的学习反馈` : `${lesson.metadata.student_name}'s learning update`,
      sections: [
        {
          heading: isZh ? "本节课进展" : "Lesson progress",
          items: [
            isZh
              ? `${lesson.metadata.student_name} 本节课学习了“${lesson.metadata.lesson_topic}”，能够参与课堂练习并回应老师提问。`
              : `${lesson.metadata.student_name} practiced ${lesson.metadata.lesson_topic} and participated in teacher-led activities.`
          ]
        },
        { heading: isZh ? "本周练习" : "Practice this week", items: homeworkItems },
        { heading: isZh ? "老师备注" : "Teacher note", items: [teacherNote] }
      ]
    };
  }

  return {
    title: isZh ? `${lesson.metadata.lesson_topic} · 老师课后复盘` : `Teacher review · ${lesson.metadata.lesson_topic}`,
    sections: [
      { heading: isZh ? "课程摘要" : "Lesson summary", items: [summary] },
      { heading: isZh ? "课堂纠错" : "Corrections", items: corrections },
      { heading: isZh ? "发音反馈" : "Pronunciation feedback", items: pronunciation },
      { heading: isZh ? "下节课建议" : "Next lesson suggestions", items: suggestions }
    ]
  };
}

function timeRange(start: number, end: number) {
  return `${formatTime(start)}-${formatTime(end)}`;
}

function formatTime(value: number) {
  const minutes = Math.floor(value / 60);
  const seconds = Math.floor(value % 60);
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function confidenceClass(confidence: Confidence | string | undefined) {
  return `confidence ${confidence ?? "unknown"}`;
}

function confidenceValue(value: unknown): Confidence {
  return value === "high" || value === "medium" || value === "low" || value === "unknown" ? value : "unknown";
}

function workflowStatusValue(value: unknown): WorkflowStatus | undefined {
  if (value === "pending" || value === "running" || value === "passed" || value === "warning" || value === "failed") {
    return value;
  }
  if (value === "pass" || value === "success" || value === "complete" || value === "completed") return "passed";
  if (value === "error" || value === "fail") return "failed";
  return undefined;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function hasArrayItems(value: unknown) {
  return Array.isArray(value) && value.length > 0;
}

function hasObjectFields(value: unknown) {
  return isRecord(value) && Object.keys(value).length > 0;
}

function normalizeTraceKey(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
}

function traceAliases(id: WorkflowNodeId, label: string) {
  const base = [id, label, label.replace("Report ", ""), id.replace("_", " ")];
  const explicit: Partial<Record<WorkflowNodeId, string[]>> = {
    report_writer: ["writer_agent", "writer", "writer node"],
    report_reviewer: ["reviewer_agent", "reviewer", "reviewer node"]
  };
  return [...base, ...(explicit[id] ?? [])].map(normalizeTraceKey);
}

function formatAgentMode(value: unknown, t?: (key: TranslationKey) => string) {
  if (value === "real_llm") return t ? t("realLlm") : "Real LLM";
  if (value === "fallback") return t ? t("fallbackToMock") : "Fallback to mock";
  if (value === "mock") return t ? t("mockPipeline") : "Mock pipeline";
  return typeof value === "string" && value.length > 0 ? value : (t ? t("mockPipeline") : "Mock pipeline");
}

function getStringField(item: Record<string, unknown>, key: string) {
  const value = item[key];
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function getText(item: ReportObject | HomeworkItem | string | number | boolean | null | undefined) {
  if (item === null || item === undefined) return "";
  if (typeof item !== "object") return String(item);

  const record = item as Record<string, unknown>;
  const preferred = [
    getStringField(record, "text"),
    getStringField(record, "summary"),
    getStringField(record, "question"),
    getStringField(record, "description"),
    getStringField(record, "detail"),
    getStringField(record, "title"),
    getStringField(record, "explanation"),
    getStringField(record, "teacher_correction") && getStringField(record, "student_original")
      ? `${getStringField(record, "student_original")} -> ${getStringField(record, "teacher_correction")}`
      : undefined
  ];

  const value = preferred.find((entry) => typeof entry === "string" && entry.length > 0);
  return value ?? JSON.stringify(item);
}

function normalizeRisks(risks: RiskHighlight[] = []) {
  return risks.map((risk) => ({ ...risk, confirmed: Boolean(risk.confirmed) }));
}

function normalizeHomework(homework: HomeworkItem[] = []) {
  return homework.map((item) => ({ ...item, teacher_confirmed: Boolean(item.teacher_confirmed) }));
}

function getEvidenceIds(item: ReportObject | HomeworkItem) {
  const sourceEvidenceIds = "source_evidence_ids" in item ? item.source_evidence_ids : undefined;
  if (Array.isArray(sourceEvidenceIds)) return sourceEvidenceIds.filter((id): id is string => typeof id === "string");
  if ("source_evidence_id" in item && typeof item.source_evidence_id === "string") return [item.source_evidence_id];
  return [];
}

function getItemKey(item: ReportObject | HomeworkItem, title: string, index: number) {
  if ("id" in item && typeof item.id === "string") return item.id;
  if ("homework_id" in item && typeof item.homework_id === "string") return item.homework_id;
  return `${title}-${index}`;
}

function getTraceField(trace: WorkflowTraceItem | Record<string, unknown>, key: string) {
  const value = trace[key];
  return typeof value === "string" ? value : undefined;
}

function getTraceMessage(trace: WorkflowTraceItem | Record<string, unknown>) {
  return (
    getTraceField(trace, "summary") ??
    getTraceField(trace, "message") ??
    getTraceField(trace, "detail") ??
    getTraceField(trace, "description")
  );
}

function getTraceMetadata(trace: WorkflowTraceItem | Record<string, unknown>) {
  return isRecord(trace.metadata) ? trace.metadata : {};
}

function compactValue(value: unknown) {
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  return undefined;
}

function metadataBadges(trace: WorkflowTraceItem | undefined, llmTrace: LlmTraceItem | undefined, t?: (key: TranslationKey) => string) {
  const metadata = trace ? getTraceMetadata(trace) : {};
  const llmMetadata = isRecord(llmTrace?.metadata) ? llmTrace.metadata : {};
  const badges = [
    compactValue(llmTrace?.mode) ? formatAgentMode(llmTrace?.mode, t) : undefined,
    compactValue(llmTrace?.model_provider ?? llmTrace?.provider ?? metadata.provider ?? llmMetadata.provider)
      ? `${t ? t("provider") : "provider"}: ${compactValue(llmTrace?.model_provider ?? llmTrace?.provider ?? metadata.provider ?? llmMetadata.provider)}`
      : undefined,
    compactValue(llmTrace?.model_name ?? llmTrace?.model ?? metadata.model ?? llmMetadata.model)
      ? `${t ? t("modelLabel") : "model"}: ${compactValue(llmTrace?.model_name ?? llmTrace?.model ?? metadata.model ?? llmMetadata.model)}`
      : undefined,
    compactValue(metadata.tokens ?? metadata.token_count ?? llmMetadata.tokens ?? llmMetadata.token_count)
      ? `${t ? t("tokens") : "tokens"}: ${compactValue(metadata.tokens ?? metadata.token_count ?? llmMetadata.tokens ?? llmMetadata.token_count)}`
      : undefined,
    metadata.json_repair || metadata.repaired || llmMetadata.json_repair || llmMetadata.repaired || llmTrace?.schema_validation?.repaired ? (t ? t("jsonRepair") : "json repair") : undefined
  ];
  return badges.filter((badge): badge is string => Boolean(badge));
}

function readTraceItems(value: unknown): WorkflowTraceItem[] {
  if (Array.isArray(value)) return value.filter(isRecord) as WorkflowTraceItem[];
  if (!isRecord(value)) return [];
  return Object.entries(value).map(([key, entry]) => {
    if (isRecord(entry)) return { node_id: key, ...entry } as WorkflowTraceItem;
    return { node_id: key, status: typeof entry === "string" ? entry : undefined } as WorkflowTraceItem;
  });
}

function readLlmTraceItems(value: unknown): LlmTraceItem[] {
  if (Array.isArray(value)) return value.filter(isRecord) as LlmTraceItem[];
  if (!isRecord(value)) return [];
  return Object.entries(value).map(([key, entry]) => {
    if (isRecord(entry)) return { node_id: key, ...entry } as LlmTraceItem;
    return { node_id: key, mode: typeof entry === "string" ? entry : undefined } as LlmTraceItem;
  });
}

function getLlmTraceMap(lesson: LessonObject) {
  const items = [
    ...readLlmTraceItems(lesson.llm_trace),
    ...readLlmTraceItems(isRecord(lesson.graph_state) ? lesson.graph_state.llm_trace : undefined)
  ];
  const traceMap = new Map<string, LlmTraceItem>();
  for (const item of items) {
    const rawName = item.node_id ?? item.node ?? item.agent ?? item.name;
    if (!rawName) continue;
    traceMap.set(normalizeTraceKey(rawName), item);
  }
  return traceMap;
}

function findLlmTrace(traceMap: Map<string, LlmTraceItem>, id: WorkflowNodeId, label: string) {
  return traceAliases(id, label).map((alias) => traceMap.get(alias)).find(Boolean);
}

function getBackendTraceMap(lesson: LessonObject) {
  const traceItems = [
    ...readTraceItems(lesson.workflow_trace),
    ...readTraceItems(lesson.agent_trace),
    ...readTraceItems(lesson.graph_trace),
    ...readTraceItems(isRecord(lesson.graph_state) ? lesson.graph_state.workflow_trace : undefined),
    ...readTraceItems(isRecord(lesson.graph_state) ? lesson.graph_state.agent_trace : undefined),
    ...readTraceItems(isRecord(lesson.graph_state) ? lesson.graph_state.graph_trace : undefined),
    ...readTraceItems(isRecord(lesson.graph_state) ? lesson.graph_state.nodes : undefined)
  ];

  const traceMap = new Map<string, WorkflowTraceItem>();
  for (const item of traceItems) {
    const rawName = item.node_id ?? item.node ?? item.name ?? item.label;
    if (!rawName) continue;
    traceMap.set(normalizeTraceKey(rawName), item);
  }
  return traceMap;
}

function findBackendTrace(traceMap: Map<string, WorkflowTraceItem>, id: WorkflowNodeId, label: string) {
  return traceAliases(id, label).map((alias) => traceMap.get(alias)).find(Boolean);
}

function inferWorkflowStatus(lesson: LessonObject, nodeId: WorkflowNodeId, teacherConfirmed: boolean): WorkflowNodeView["status"] {
  switch (nodeId) {
    case "transcript_processor":
      return hasArrayItems(lesson.transcripts.teacher) || hasArrayItems(lesson.transcripts.student) ? "passed" : "pending";
    case "evidence_extractor":
      return Object.values(lesson.evidence).some((items) => hasArrayItems(items)) ? "passed" : "pending";
    case "confidence_scorer":
      return hasObjectFields(lesson.confidence_scores) ? "passed" : "pending";
    case "report_writer":
      return hasObjectFields(lesson.draft_report) ? "passed" : "pending";
    case "rule_validator":
      return lesson.rule_validation_result.pass
        ? "passed"
        : hasArrayItems(lesson.rule_validation_result.blocking_issues)
          ? "failed"
          : "warning";
    case "report_reviewer":
      return lesson.review_result.pass ? "passed" : "failed";
    case "teacher_review":
      return teacherConfirmed ? "passed" : "pending";
    case "final_report_generator":
      return hasObjectFields(lesson.final_reports) ? "passed" : "pending";
  }
}

function inferWorkflowDetail(lesson: LessonObject, nodeId: WorkflowNodeId, teacherConfirmed: boolean, t: (key: TranslationKey) => string) {
  switch (nodeId) {
    case "transcript_processor":
      return `${lesson.transcripts.teacher.length + lesson.transcripts.student.length} ${t("classTranscript").toLowerCase()}`;
    case "evidence_extractor":
      return `${Object.values(lesson.evidence).reduce((count, items) => count + (items?.length ?? 0), 0)} evidence items linked`;
    case "confidence_scorer":
      return `${Object.keys(lesson.confidence_scores).length} confidence scores`;
    case "report_writer":
      return t("aiDraftReport");
    case "rule_validator":
      return lesson.rule_validation_result.pass
        ? `${lesson.rule_validation_result.warnings.length} ${t("schemaWarning").toLowerCase()}`
        : lesson.rule_validation_result.blocking_issues.join("; ") || t("failed");
    case "report_reviewer":
      return lesson.review_result.pass
        ? `${t("reviewerScore")} ${lesson.review_result.score}`
        : lesson.review_result.revision_instruction || t("failed");
    case "teacher_review":
      return teacherConfirmed ? t("teacherConfirmed") : t("pendingReview");
    case "final_report_generator":
      return `${t("finalReportPreview")}`;
  }
}

function buildWorkflowNodes(lesson: LessonObject, teacherConfirmed: boolean, t: (key: TranslationKey) => string): WorkflowNodeView[] {
  const backendTraceMap = getBackendTraceMap(lesson);
  const llmTraceMap = getLlmTraceMap(lesson);
  return workflowNodeDefinitions.map((definition) => {
    const label = t(definition.labelKey);
    const backendTrace = findBackendTrace(backendTraceMap, definition.id, label);
    const llmTrace = findLlmTrace(llmTraceMap, definition.id, label);
    const backendStatus = workflowStatusValue(backendTrace?.status);
    return {
      id: definition.id,
      label,
      status: backendStatus ?? inferWorkflowStatus(lesson, definition.id, teacherConfirmed),
      detail: (backendTrace && getTraceMessage(backendTrace)) || inferWorkflowDetail(lesson, definition.id, teacherConfirmed, t),
      source: backendStatus ? "backend" : "inferred",
      badges: metadataBadges(backendTrace, llmTrace, t)
    };
  });
}

function schemaValidationStatus(schemaValidation: SchemaValidationResult | undefined, t?: (key: TranslationKey) => string): { status: WorkflowStatus; label: string } {
  if (!schemaValidation) return { status: "pending", label: t ? t("schemaUnknown") : "Schema unknown" };
  const status = typeof schemaValidation.status === "string" ? schemaValidation.status.toLowerCase() : undefined;
  if (schemaValidation.pass || schemaValidation.passed || schemaValidation.valid || status === "passed" || status === "valid") {
    return { status: schemaValidation.repaired || schemaValidation.json_repair ? "warning" : "passed", label: schemaValidation.repaired || schemaValidation.json_repair ? (t ? t("schemaRepaired") : "Schema repaired") : (t ? t("schemaValid") : "Schema valid") };
  }
  if (status === "warning" || (schemaValidation.warnings?.length ?? 0) > 0) return { status: "warning", label: t ? t("schemaWarning") : "Schema warning" };
  if (status === "failed" || status === "invalid" || (schemaValidation.errors?.length ?? 0) > 0) return { status: "failed", label: t ? t("schemaFailed") : "Schema failed" };
  return { status: "pending", label: t ? t("schemaUnknown") : "Schema unknown" };
}

function buildAgentRuntime(lesson: LessonObject, t: (key: TranslationKey) => string): AgentRuntimeView {
  const llmTraceMap = getLlmTraceMap(lesson);
  const writerTrace = findLlmTrace(llmTraceMap, "report_writer", t("nodeReportWriter"));
  const reviewerTrace = findLlmTrace(llmTraceMap, "report_reviewer", t("nodeReportReviewer"));
  const schema = schemaValidationStatus(lesson.schema_validation, t);
  return {
    mode: formatAgentMode(lesson.agent_mode ?? writerTrace?.mode ?? reviewerTrace?.mode ?? "mock", t),
    provider: lesson.model_provider ?? writerTrace?.model_provider ?? writerTrace?.provider ?? reviewerTrace?.model_provider ?? reviewerTrace?.provider,
    model: lesson.model_name ?? writerTrace?.model_name ?? writerTrace?.model ?? reviewerTrace?.model_name ?? reviewerTrace?.model,
    schemaStatus: schema.status,
    schemaLabel: schema.label,
    fallbackReason: lesson.fallback_reason ?? writerTrace?.fallback_reason ?? reviewerTrace?.fallback_reason,
    writerMode: writerTrace?.mode ? formatAgentMode(writerTrace.mode, t) : undefined,
    reviewerMode: reviewerTrace?.mode ? formatAgentMode(reviewerTrace.mode, t) : undefined
  };
}

function formatScore(value: number): string {
  return String(Math.round(value * 10) / 10);
}

function unwrapLesson(payload: unknown): LessonObject {
  const maybeWrapped = payload as { lesson?: LessonObject };
  return maybeWrapped.lesson ?? (payload as LessonObject);
}

function mergeLessonPayload(currentLesson: LessonObject, payload: unknown): LessonObject {
  const normalizedPayload = normalizeTextFields(payload);
  const record = normalizedPayload as Record<string, unknown>;
  const payloadLesson = isRecord(record.lesson) ? record.lesson : record;
  const lessonPatch = payloadLesson as Partial<LessonObject>;

  return {
    ...currentLesson,
    ...lessonPatch,
    metadata: { ...currentLesson.metadata, ...(lessonPatch.metadata ?? {}) },
    transcripts: lessonPatch.transcripts ?? currentLesson.transcripts,
    practice_clips: lessonPatch.practice_clips ?? currentLesson.practice_clips,
    pronunciation_assessments: lessonPatch.pronunciation_assessments ?? currentLesson.pronunciation_assessments,
    evidence: lessonPatch.evidence ?? currentLesson.evidence,
    confidence_scores: lessonPatch.confidence_scores ?? currentLesson.confidence_scores,
    draft_report: { ...currentLesson.draft_report, ...(lessonPatch.draft_report ?? {}) },
    rule_validation_result: lessonPatch.rule_validation_result ?? currentLesson.rule_validation_result,
    review_result: lessonPatch.review_result ?? currentLesson.review_result,
    risk_highlights: lessonPatch.risk_highlights ?? currentLesson.risk_highlights,
    teacher_review: { ...currentLesson.teacher_review, ...(lessonPatch.teacher_review ?? {}) },
    final_reports: lessonPatch.final_reports ?? currentLesson.final_reports,
    teacher_edit_log: lessonPatch.teacher_edit_log ?? currentLesson.teacher_edit_log,
    workflow_trace:
      lessonPatch.workflow_trace ??
      (record.workflow_trace as LessonObject["workflow_trace"]) ??
      currentLesson.workflow_trace,
    agent_trace:
      lessonPatch.agent_trace ??
      (record.agent_trace as LessonObject["agent_trace"]) ??
      currentLesson.agent_trace,
    graph_trace:
      lessonPatch.graph_trace ??
      (record.graph_trace as LessonObject["graph_trace"]) ??
      currentLesson.graph_trace,
    graph_state:
      lessonPatch.graph_state ??
      (record.graph_state as LessonObject["graph_state"]) ??
      currentLesson.graph_state,
    revision_history:
      lessonPatch.revision_history ??
      (record.revision_history as LessonObject["revision_history"]) ??
      currentLesson.revision_history,
    agent_mode:
      lessonPatch.agent_mode ??
      (record.agent_mode as LessonObject["agent_mode"]) ??
      currentLesson.agent_mode,
    model_provider:
      lessonPatch.model_provider ??
      (record.model_provider as LessonObject["model_provider"]) ??
      currentLesson.model_provider,
    model_name:
      lessonPatch.model_name ??
      (record.model_name as LessonObject["model_name"]) ??
      currentLesson.model_name,
    llm_trace:
      lessonPatch.llm_trace ??
      (record.llm_trace as LessonObject["llm_trace"]) ??
      currentLesson.llm_trace,
    schema_validation:
      lessonPatch.schema_validation ??
      (record.schema_validation as LessonObject["schema_validation"]) ??
      currentLesson.schema_validation,
  fallback_reason:
      lessonPatch.fallback_reason ??
      (record.fallback_reason as LessonObject["fallback_reason"]) ??
      currentLesson.fallback_reason,
    audio_ingest:
      lessonPatch.audio_ingest ??
      (record.audio_ingest as LessonObject["audio_ingest"]) ??
      currentLesson.audio_ingest
  };
}

async function requestJson(path: string, signal: AbortSignal | undefined, init?: RequestInit) {
  const response = await fetch(path, { ...init, signal });
  if (!response.ok) throw new Error(`${path} returned ${response.status}`);
  return response.json();
}

async function requestApi(path: string, signal: AbortSignal | undefined, init?: RequestInit) {
  const directUrl = `${DIRECT_API_BASE}${path}`;
  const proxyUrl = `${PROXY_API_BASE}${path}`;
  try {
    return await requestJson(directUrl, signal, init);
  } catch (directError) {
    if (signal?.aborted) throw directError;
    return requestJson(proxyUrl, signal, init);
  }
}

async function analyzeLesson(signal: AbortSignal) {
  return requestApi("/api/lessons/demo/analyze", signal, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode: "mock", include_pronunciation: true })
  });
}

async function getDemoLesson(signal: AbortSignal) {
  return requestApi("/api/lessons/demo", signal);
}

async function ingestDemoAudio(formData: FormData) {
  return requestApi("/api/lessons/demo/audio-ingest", undefined, {
    method: "POST",
    body: formData
  });
}

function formatFileSize(value: number | undefined) {
  if (!value) return "0 KB";
  if (value < 1024 * 1024) return `${Math.round(value / 102.4) / 10} KB`;
  return `${Math.round(value / 1024 / 102.4) / 10} MB`;
}

function repairMojibake(value: string) {
  if (!mojibakePattern.test(value)) return value;
  const bytes = Uint8Array.from(Array.from(value, (char) => char.charCodeAt(0)));
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    return value;
  }
}

function normalizeTextFields<T>(value: T): T {
  if (typeof value === "string") return repairMojibake(value) as T;
  if (Array.isArray(value)) return value.map((item) => normalizeTextFields(item)) as T;
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, entry]) => [key, normalizeTextFields(entry)])
    ) as T;
  }
  return value;
}

export function App() {
  const [lesson, setLesson] = useState<LessonObject>(mockLesson);
  const [dataSource, setDataSource] = useState<"api" | "fallback">("fallback");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [homework, setHomework] = useState<HomeworkItem[]>(normalizeHomework(mockLesson.draft_report.homework_items));
  const [risks, setRisks] = useState<RiskHighlight[]>(normalizeRisks(mockLesson.risk_highlights));
  const [activeAudience, setActiveAudience] = useState<Audience>("teacher");
  const [confirmed, setConfirmed] = useState(false);
  const [finalizing, setFinalizing] = useState(false);
  const [teacherNote, setTeacherNote] = useState("下节课继续练习量词，并回听 00:35 的发音片段。");
  const [activeEvidenceId, setActiveEvidenceId] = useState<string | null>(null);
  const [lang, setLang] = useState<Lang>("zh");
  const [activeTab, setActiveTab] = useState<"overview" | "draft" | "review" | "report">("overview");
  const [workflowExpanded, setWorkflowExpanded] = useState(false);
  const [reviewSubTab, setReviewSubTab] = useState<"risks" | "homework" | "pronunciation">("risks");
  const [loading, setLoading] = useState(true);
  const [reportSent, setReportSent] = useState(false);
  const [sending, setSending] = useState(false);
  const [draftSaved, setDraftSaved] = useState(false);
  const [draftEdits, setDraftEdits] = useState<Record<string, { text?: string; deleted?: boolean }>>({});
  const [view, setView] = useState<AppView>("list");
  const [reportViewAudience, setReportViewAudience] = useState<"student" | "parent" | null>(null);
  const [reportViewLessonId, setReportViewLessonId] = useState<string | null>(null);
  const [courseFilter, setCourseFilter] = useState<CourseFilter>("all");
  const [audioSource, setAudioSource] = useState<AudioSource>("sample");
  const [sampleId, setSampleId] = useState<DemoSampleId>("standard");
  const [recordingConsent, setRecordingConsent] = useState(false);
  const [newLesson, setNewLesson] = useState<NewLessonDraft>(() => defaultNewLesson(mockLesson.metadata));
  const [teacherAudioFile, setTeacherAudioFile] = useState<File | null>(null);
  const [studentAudioFile, setStudentAudioFile] = useState<File | null>(null);
  const [audioProcessing, setAudioProcessing] = useState(false);
  const [recordingTrack, setRecordingTrack] = useState<RecordingTrack | null>(null);
  const [recordingStatus, setRecordingStatus] = useState<RecordingStatus>("idle");
  const [teacherRecording, setTeacherRecording] = useState<RecordedTrack | null>(null);
  const [studentRecording, setStudentRecording] = useState<RecordedTrack | null>(null);
  const [recordingError, setRecordingError] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const recordingStartedAtRef = useRef<number | null>(null);
  const t = createT(lang);

  useEffect(() => {
    const controller = new AbortController();

    async function loadLesson() {
      try {
        const analyzePayload = await analyzeLesson(controller.signal).catch(() => null);
        const payload = analyzePayload ?? (await getDemoLesson(controller.signal));
        const remoteLesson = mergeLessonPayload(mockLesson, payload);
        setLesson(remoteLesson);
        setHomework(normalizeHomework(remoteLesson.draft_report.homework_items));
        setRisks(normalizeRisks(remoteLesson.risk_highlights));
        setDataSource("api");
        setLoadError(null);
      } catch (error) {
        if (controller.signal.aborted) return;
        setLesson(mockLesson);
        setHomework(normalizeHomework(mockLesson.draft_report.homework_items));
        setRisks(normalizeRisks(mockLesson.risk_highlights));
        setDataSource("fallback");
        setLoadError(error instanceof Error ? error.message : "Backend API unavailable");
      } finally {
        setLoading(false);
      }
    }

    void loadLesson();
    return () => controller.abort();
  }, []);

  useEffect(() => {
    return () => {
      mediaRecorderRef.current?.stop();
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
      if (teacherRecording?.objectUrl) URL.revokeObjectURL(teacherRecording.objectUrl);
      if (studentRecording?.objectUrl) URL.revokeObjectURL(studentRecording.objectUrl);
    };
  }, [teacherRecording?.objectUrl, studentRecording?.objectUrl]);

  const allHomeworkConfirmed = homework.every((item) => item.teacher_confirmed);
  const allRisksConfirmed = risks.every((risk) => risk.confirmed);
  const unresolvedReviewRisks = risks.filter((risk) => !risk.confirmed && (risk.level === "high" || risk.level === "medium"));
  const readyToFinalize = allHomeworkConfirmed && allRisksConfirmed;
  const highMediumRisksResolved = unresolvedReviewRisks.length === 0;
  const confirmedHomeworkCount = homework.filter((item) => item.teacher_confirmed).length;
  const confirmedRiskCount = risks.filter((risk) => risk.confirmed).length;
  const teacherGateConfirmed = lesson.teacher_review.status === "confirmed" || confirmed;
  const finalReportSendReady = readyToFinalize && teacherGateConfirmed;
  const revisionCount = lesson.review_result.revision_count ?? lesson.revision_history?.length ?? 0;
  const workflowNodes = useMemo(
    () => buildWorkflowNodes(lesson, teacherGateConfirmed, t),
    [lesson, teacherGateConfirmed, t]
  );
  const agentRuntime = useMemo(() => buildAgentRuntime(lesson, t), [lesson, t]);
  const currentCourseStatus: CourseListItem["status"] = reportSent
    ? "sent"
    : teacherGateConfirmed
      ? "ready_to_send"
      : "review_required";
  const courseList = useMemo<CourseListItem[]>(
    () => [
      {
        lessonId: DEMO_LESSON_ID,
        studentName: lesson.metadata.student_name,
        topic: lesson.metadata.lesson_topic,
        date: lesson.metadata.lesson_date,
        duration: lesson.metadata.lesson_duration_minutes,
        status: currentCourseStatus,
        teacher: lesson.metadata.teacher_name,
        interactive: true
      },
      ...archivedCourses
    ],
    [currentCourseStatus, lesson.metadata]
  );
  const filteredCourses = courseList.filter((course) => {
    if (courseFilter === "all") return true;
    if (courseFilter === "sent") return course.status === "sent";
    return course.status === "review_required" || course.status === "ready_to_send";
  });
  const pendingCourseCount = courseList.filter((course) => course.status === "review_required").length;
  const completedCourseCount = courseList.filter((course) => course.status === "sent").length;
  const totalReviewItems = risks.length + homework.length;
  const reviewedItemCount = confirmedRiskCount + confirmedHomeworkCount;
  const pendingReviewCount = Math.max(totalReviewItems - reviewedItemCount, 0);
  const reviewProgress = totalReviewItems > 0 ? Math.round((reviewedItemCount / totalReviewItems) * 100) : 100;

  const mergedTranscript = useMemo(
    () =>
      [...lesson.transcripts.teacher, ...lesson.transcripts.student].sort(
        (a, b) => a.start_time - b.start_time
      ),
    [lesson]
  );

  const evidenceById = useMemo(() => {
    const entries = Object.values(lesson.evidence)
      .flatMap((items) => items ?? [])
      .map((item) => [item.evidence_id, item] as const);
    return new Map(entries);
  }, [lesson]);

  const activeSegmentIds = useMemo(() => {
    if (!activeEvidenceId) return new Set<string>();
    return new Set(evidenceById.get(activeEvidenceId)?.source_segment_ids ?? []);
  }, [activeEvidenceId, evidenceById]);

  const sortedRisks = useMemo(
    () =>
      [...risks].sort(
        (a, b) =>
          (riskRank[a.level] ?? 99) - (riskRank[b.level] ?? 99) ||
          Number(Boolean(a.confirmed)) - Number(Boolean(b.confirmed))
      ),
    [risks]
  );

  function focusEvidence(evidenceId: string | null) {
    setActiveEvidenceId(evidenceId);
    if (!evidenceId) return;
    const evidence = evidenceById.get(evidenceId);
    const firstSegmentId = evidence?.source_segment_ids[0];
    if (!firstSegmentId) return;
    window.setTimeout(() => {
      document.getElementById(`segment-${firstSegmentId}`)?.scrollIntoView({ block: "center", behavior: "smooth" });
    }, 0);
  }

  function toggleHomework(homeworkId: string) {
    setHomework((items) =>
      items.map((item) =>
        item.homework_id === homeworkId ? { ...item, teacher_confirmed: !item.teacher_confirmed } : item
      )
    );
  }

  function updateHomework(homeworkId: string, description: string) {
    setHomework((items) =>
      items.map((item) => (item.homework_id === homeworkId ? { ...item, description } : item))
    );
  }

  function updateHomeworkNote(homeworkId: string, note: string) {
    setHomework((items) =>
      items.map((item) => (item.homework_id === homeworkId ? { ...item, teacher_note: note } : item))
    );
  }

  function confirmRisk(riskId: string) {
    setRisks((items) =>
      items.map((risk) => (risk.risk_id === riskId ? { ...risk, confirmed: !risk.confirmed } : risk))
    );
  }

  function updateRiskMessage(riskId: string, message: string) {
    setRisks((items) =>
      items.map((risk) => (risk.risk_id === riskId ? { ...risk, message } : risk))
    );
  }

  function updateRiskNote(riskId: string, note: string) {
    setRisks((items) =>
      items.map((risk) => (risk.risk_id === riskId ? { ...risk, teacher_note: note } : risk))
    );
  }

  function dismissRisk(riskId: string) {
    setRisks((items) =>
      items.map((risk) => (risk.risk_id === riskId ? { ...risk, dismissed: !risk.dismissed } : risk))
    );
  }

  function togglePronConfirmation(assessmentId: string) {
    setLesson((prev) => ({
      ...prev,
      pronunciation_assessments: prev.pronunciation_assessments.map((a) =>
        a.assessment_id === assessmentId ? { ...a, teacher_confirmed: !a.teacher_confirmed } : a
      ),
    }));
  }

  function updatePronNote(assessmentId: string, note: string) {
    setLesson((prev) => ({
      ...prev,
      pronunciation_assessments: prev.pronunciation_assessments.map((a) =>
        a.assessment_id === assessmentId ? { ...a, teacher_note: note } : a
      ),
    }));
  }

  async function confirmAll() {
    if (!readyToFinalize) {
      setActiveTab("review");
      return;
    }
    const confirmedHomework = homework.map((item) => ({ ...item }));
    const confirmedRisks = risks.map((risk) => ({ ...risk }));
    setFinalizing(true);

    const lessonId = lesson.lesson_id || DEMO_LESSON_ID;
    const teacherReviewPayload = {
      confirmed_homework_ids: confirmedHomework.map((item) => item.homework_id),
      edited_homework_items: confirmedHomework,
      confirmed_risk_ids: confirmedRisks.map((risk) => risk.risk_id),
      teacher_notes: teacherNote,
      report_edits: {}
    };

    try {
      const reviewPayload = await requestApi(`/api/lessons/${lessonId}/teacher-review`, undefined, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(teacherReviewPayload)
      });
      const reviewedLesson = mergeLessonPayload(
        {
          ...lesson,
          draft_report: { ...lesson.draft_report, homework_items: confirmedHomework },
          risk_highlights: confirmedRisks,
          teacher_review: {
            ...lesson.teacher_review,
            status: "confirmed",
            confirmed_homework_ids: confirmedHomework.map((item) => item.homework_id),
            confirmed_risk_ids: confirmedRisks.map((risk) => risk.risk_id),
            teacher_notes: teacherNote
          }
        },
        reviewPayload
      );

      const finalizePayload = await requestApi(`/api/lessons/${lessonId}/finalize`, undefined, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ audiences: ["teacher", "student", "parent"] })
      });
      const finalizedLesson = mergeLessonPayload(reviewedLesson, finalizePayload);
      setLesson(finalizedLesson);
      setHomework(normalizeHomework(finalizedLesson.draft_report.homework_items));
      setRisks(normalizeRisks(finalizedLesson.risk_highlights));
      setConfirmed(true);
      setActiveTab("report");
      setLoadError(null);
    } catch (error) {
      setLesson((currentLesson) => ({
        ...currentLesson,
        draft_report: { ...currentLesson.draft_report, homework_items: confirmedHomework },
        risk_highlights: confirmedRisks,
        teacher_review: {
          ...currentLesson.teacher_review,
          status: "confirmed",
          confirmed_homework_ids: confirmedHomework.map((item) => item.homework_id),
          confirmed_risk_ids: confirmedRisks.map((risk) => risk.risk_id),
          teacher_notes: teacherNote
        }
      }));
      setConfirmed(true);
      setActiveTab("report");
      setLoadError(error instanceof Error ? error.message : "Finalize API unavailable");
    } finally {
      setFinalizing(false);
    }
  }

  function saveDraft() {
    setDraftSaved(true);
    setTimeout(() => setDraftSaved(false), 2000);
  }

  async function sendReport() {
    setSending(true);
    await new Promise((resolve) => setTimeout(resolve, 800));
    setReportSent(true);
    setSending(false);
  }

  function editDraftItem(key: string, text: string) {
    setDraftEdits((prev) => ({ ...prev, [key]: { ...prev[key], text } }));
  }

  function deleteDraftItem(key: string) {
    setDraftEdits((prev) => ({ ...prev, [key]: { ...prev[key], deleted: true } }));
  }

  function getDraftItemText(item: ReportObject | HomeworkItem, category: string, index: number): string {
    const key = `${category}_${index}`;
    if (draftEdits[key]?.text !== undefined) return draftEdits[key].text;
    return getText(item);
  }

  function isDraftItemDeleted(category: string, index: number): boolean {
    return Boolean(draftEdits[`${category}_${index}`]?.deleted);
  }

  const editedTexts: Record<string, string> = {};
  const deletedIndices = new Set<string>();
  for (const [key, edit] of Object.entries(draftEdits)) {
    if (edit.text !== undefined) editedTexts[key] = edit.text;
    if (edit.deleted) deletedIndices.add(key);
  }

  function updateNewLesson<K extends keyof NewLessonDraft>(key: K, value: NewLessonDraft[K]) {
    setNewLesson((current) => ({ ...current, [key]: value }));
  }

  function selectDemoSample(id: DemoSampleId) {
    setSampleId(id);
    setNewLesson((current) => ({
      ...current,
      topic: id === "extended" ? "餐厅点餐进阶" : "餐厅点餐",
      duration: id === "extended" ? 60 : 45
    }));
  }

  function supportedRecordingMimeType() {
    if (typeof MediaRecorder === "undefined") return "";
    if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) return "audio/webm;codecs=opus";
    if (MediaRecorder.isTypeSupported("audio/webm")) return "audio/webm";
    return "";
  }

  function clearRecordedTrack(track: RecordingTrack) {
    const current = track === "teacher" ? teacherRecording : studentRecording;
    if (current?.objectUrl) URL.revokeObjectURL(current.objectUrl);
    if (track === "teacher") {
      setTeacherRecording(null);
    } else {
      setStudentRecording(null);
    }
  }

  function recordedTrackToFile(recording: RecordedTrack) {
    return new File([recording.blob], recording.filename, { type: recording.mimeType });
  }

  async function startRecording(track: RecordingTrack) {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setRecordingStatus("error");
      setRecordingError(t("recordingUnsupported"));
      return;
    }

    if (mediaRecorderRef.current?.state === "recording") return;

    try {
      setRecordingError(null);
      clearRecordedTrack(track);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = supportedRecordingMimeType();
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      chunksRef.current = [];
      recordingStartedAtRef.current = Date.now();
      mediaStreamRef.current = stream;
      mediaRecorderRef.current = recorder;
      setRecordingTrack(track);
      setRecordingStatus("recording");

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };

      recorder.onerror = () => {
        setRecordingStatus("error");
        setRecordingError(t("recordingFailed"));
        stream.getTracks().forEach((item) => item.stop());
      };

      recorder.onstop = () => {
        const finalMimeType = recorder.mimeType || mimeType || "audio/webm";
        const blob = new Blob(chunksRef.current, { type: finalMimeType });
        const startedAt = recordingStartedAtRef.current ?? Date.now();
        const durationSeconds = Math.max(1, Math.round((Date.now() - startedAt) / 1000));
        const extension = finalMimeType.includes("webm") ? "webm" : "audio";
        const recordedTrack: RecordedTrack = {
          track,
          blob,
          filename: `${track}_recording_${new Date().toISOString().replace(/[:.]/g, "-")}.${extension}`,
          mimeType: finalMimeType,
          durationSeconds,
          objectUrl: URL.createObjectURL(blob)
        };
        if (track === "teacher") {
          setTeacherRecording(recordedTrack);
        } else {
          setStudentRecording(recordedTrack);
        }
        stream.getTracks().forEach((item) => item.stop());
        mediaStreamRef.current = null;
        mediaRecorderRef.current = null;
        recordingStartedAtRef.current = null;
        setRecordingTrack(null);
        setRecordingStatus("stopped");
      };

      recorder.start();
    } catch (error) {
      mediaStreamRef.current?.getTracks().forEach((item) => item.stop());
      mediaStreamRef.current = null;
      mediaRecorderRef.current = null;
      setRecordingTrack(null);
      setRecordingStatus("error");
      setRecordingError(error instanceof Error ? error.message : t("recordingFailed"));
    }
  }

  function stopRecording() {
    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.stop();
    }
  }

  function openNewLesson() {
    setNewLesson(defaultNewLesson(lesson.metadata));
    setAudioSource("sample");
    setSampleId("standard");
    setTeacherAudioFile(null);
    setStudentAudioFile(null);
    clearRecordedTrack("teacher");
    clearRecordedTrack("student");
    setRecordingTrack(null);
    setRecordingStatus("idle");
    setRecordingError(null);
    setRecordingConsent(false);
    setLoadError(null);
    setView("new");
  }

  async function startNewLesson() {
    const useSample = audioSource === "sample";
    const hasUploadedAudio = Boolean(teacherAudioFile && studentAudioFile);
    const hasRecordedAudio = Boolean(teacherRecording && studentRecording);
    if (!recordingConsent || (audioSource === "upload" && !hasUploadedAudio) || (audioSource === "record" && !hasRecordedAudio)) return;
    await processAudioUpload(useSample, newLesson, sampleId);
  }

  async function processAudioUpload(
    useSample = false,
    metadata?: NewLessonDraft,
    selectedSampleId: DemoSampleId = "standard"
  ) {
    const formData = new FormData();
    const recordedTeacherFile = teacherRecording ? recordedTrackToFile(teacherRecording) : null;
    const recordedStudentFile = studentRecording ? recordedTrackToFile(studentRecording) : null;
    if (teacherAudioFile) formData.append("teacher_audio", teacherAudioFile);
    else if (recordedTeacherFile) formData.append("teacher_audio", recordedTeacherFile);
    if (studentAudioFile) formData.append("student_audio", studentAudioFile);
    else if (recordedStudentFile) formData.append("student_audio", recordedStudentFile);
    formData.append("mode", "mock");
    formData.append("agent_mode", "real");
    formData.append("include_pronunciation", "true");
    const inputSource = useSample ? "sample" : (teacherAudioFile || studentAudioFile) ? "upload" : audioSource;
    formData.append("input_source", inputSource);
    if (metadata) formData.append("lesson_metadata", JSON.stringify(metadata));
    if (useSample) {
      formData.append("use_sample", "true");
      formData.append("sample_id", selectedSampleId);
    }

    setAudioProcessing(true);
    try {
      const ingestPayload = await ingestDemoAudio(formData);
      const ingestedLesson = mergeLessonPayload(lesson, ingestPayload);
      const lessonWithMetadata: LessonObject = metadata
        ? {
            ...ingestedLesson,
            metadata: {
              ...ingestedLesson.metadata,
              student_name: metadata.studentName,
              student_age: metadata.studentAge,
              student_level: metadata.studentLevel,
              teacher_name: metadata.teacherName,
              lesson_topic: metadata.topic,
              lesson_date: metadata.date,
              lesson_duration_minutes: metadata.duration
            }
          }
        : ingestedLesson;
      setLesson(lessonWithMetadata);
      setHomework(normalizeHomework(lessonWithMetadata.draft_report.homework_items));
      setRisks(normalizeRisks(lessonWithMetadata.risk_highlights));
      setConfirmed(false);
      setReportSent(false);
      setDraftEdits({});
      setActiveTab("overview");
      setWorkflowExpanded(false);
      setView("workspace");
      setLoadError(null);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "Audio ingest API unavailable");
    } finally {
      setAudioProcessing(false);
    }
  }

  const productReport = buildProductReport(lesson, activeAudience, lang, homework, teacherNote, t("noSummary"));
  const audioIngest = lesson.audio_ingest;

  const stepDefs: { id: typeof activeTab; labelKey: TranslationKey }[] = [
    { id: "overview", labelKey: "stepOverview" },
    { id: "draft", labelKey: "stepDraft" },
    { id: "review", labelKey: "stepReview" },
    { id: "report", labelKey: "stepReport" }
  ];

  const stepDoneMap: Record<typeof activeTab, boolean> = {
    overview: !loading,
    draft: !loading,
    review: allRisksConfirmed && allHomeworkConfirmed,
    report: teacherGateConfirmed
  };

  return (
    <LangContext.Provider value={lang}>
      <div className="shell">
        {/* ===== Top Navigation Bar ===== */}
        <nav className="top-nav">
          <div className="nav-left">
            <div className="brand-mark">AI</div>
            <div className="brand-text">
              <strong>{t("brandTitle")}</strong>
              <span>{t("brandSubtitle")}</span>
            </div>
            {view !== "list" && !reportViewAudience && (
              <button
                className="lang-toggle back-to-list-btn"
                type="button"
                onClick={() => setView("list")}
                title={t("backToList")}
              >
                <ArrowLeft size={16} />
                {t("backToList")}
              </button>
            )}
            {view === "workspace" && (
              <>
                <div className="nav-student">
                  <strong>{lesson.metadata.student_name}</strong>
                  <span>{lesson.metadata.student_age} {t("yrs")} · {lesson.metadata.student_level}</span>
                </div>
                <div className="nav-lesson-meta">
                  <span>{t("topic")}: {lesson.metadata.lesson_topic}</span>
                  <span>{t("duration")}: {lesson.metadata.lesson_duration_minutes} {t("min")}</span>
                </div>
              </>
            )}
            {reportViewAudience && (
              <button
                className="lang-toggle back-to-list-btn"
                type="button"
                onClick={() => { setReportViewAudience(null); setReportViewLessonId(null); }}
                title={t("backToList")}
              >
                <ArrowLeft size={16} />
                {t("backToList")}
              </button>
            )}
          </div>
          <div className="nav-right">
            {view === "workspace" && (
              <>
                <div className="status-pills">
                  <span className={`status-pill ${pendingReviewCount === 0 ? "done" : "pending"}`}>
                    {t("pendingItems")} {pendingReviewCount}
                  </span>
                  <span className={`status-pill ${readyToFinalize ? "done" : "pending"}`}>
                    {readyToFinalize ? t("readyToGenerate") : t("reviewInProgress")}
                  </span>
                </div>
                <button
                  className="lang-toggle"
                  type="button"
                  onClick={saveDraft}
                  disabled={finalizing}
                  title={t("saveDraft")}
                >
                  {draftSaved ? <CheckCircle2 size={16} /> : <FileText size={16} />}
                  {draftSaved ? t("draftSaved") : t("saveDraft")}
                </button>
                <button
                  className="primary-action"
                  type="button"
                  onClick={confirmAll}
                  disabled={!readyToFinalize || finalizing}
                  title={!readyToFinalize ? t("generateBlocked") : t("generateFinalReport")}
                >
                  <ShieldCheck size={16} />
                  {finalizing ? t("finalizing") : t("generateFinalReport")}
                </button>
              </>
            )}
            <button
              className="lang-toggle"
              type="button"
              onClick={() => setLang(lang === "zh" ? "en" : "zh")}
              title={lang === "zh" ? "Switch to English" : "切换到中文"}
            >
              <Languages size={16} />
              {lang === "zh" ? "EN" : "中文"}
            </button>
          </div>
        </nav>

        {/* ===== Course List View ===== */}
        {view === "list" && !reportViewAudience && (
          <div className="content-area course-list-view">
            <div className="course-list-header">
              <div>
                <span className="page-eyebrow">{t("teacherWorkspace")}</span>
                <h2>{t("courseCenterTitle")}</h2>
                <p className="course-list-subtitle">{t("courseCenterSubtitle")}</p>
              </div>
              <button className="primary-action course-create-btn" type="button" onClick={openNewLesson}>
                <Plus size={16} />
                {t("newLesson")}
              </button>
            </div>

            <div className="course-overview-band">
              <div>
                <strong>{pendingCourseCount}</strong>
                <span>{t("pendingLessons")}</span>
              </div>
              <div>
                <strong>{completedCourseCount}</strong>
                <span>{t("completedLessons")}</span>
              </div>
              <p>{t("courseOverviewHint")}</p>
            </div>

            <div className="course-filter-bar" aria-label={t("courseFilterLabel")}>
              {(["all", "review_required", "sent"] as CourseFilter[]).map((filter) => (
                <button
                  className={courseFilter === filter ? "active" : ""}
                  key={filter}
                  type="button"
                  onClick={() => setCourseFilter(filter)}
                >
                  {filter === "all" ? t("allCourses") : filter === "sent" ? t("sentCourses") : t("needsAction")}
                </button>
              ))}
            </div>

            <div className="course-grid">
              {filteredCourses.map((course) => {
                return (
                  <div
                    className={`course-card ${course.interactive ? "interactive" : "archive"}`}
                    key={course.lessonId}
                  >
                    <div className="course-card-header">
                      <strong>{course.studentName}</strong>
                      <span className={`course-status-badge ${course.status}`}>
                        {t(courseStatusKey(course.status))}
                      </span>
                    </div>
                    <div className="course-card-body">
                      <div className="course-card-row">
                        <span className="course-card-label">{t("topic")}</span>
                        <span>{course.topic}</span>
                      </div>
                      <div className="course-card-row">
                        <span className="course-card-label">{t("lessonDate")}</span>
                        <span>{course.date}</span>
                      </div>
                      <div className="course-card-row">
                        <span className="course-card-label">{t("duration")}</span>
                        <span>{course.duration} {t("min")}</span>
                      </div>
                      <div className="course-card-row">
                        <span className="course-card-label">{t("teacher")}</span>
                        <span>{course.teacher}</span>
                      </div>
                    </div>
                    <div className="course-card-actions">
                      {course.interactive ? (
                        <>
                          {course.status !== "sent" && (
                            <button className="course-card-open-btn" type="button" onClick={() => setView("workspace")}>
                              {course.status === "review_required" ? t("startReview") : t("openLesson")}
                            </button>
                          )}
                          {(course.status === "ready_to_send" || course.status === "sent") && (
                            <button
                              className="course-card-report-btn"
                              type="button"
                              onClick={() => {
                                setReportViewLessonId(course.lessonId);
                                setReportViewAudience("student");
                              }}
                            >
                              <FileText size={14} />
                              {t("viewReport")}
                            </button>
                          )}
                          {course.status === "sent" && (
                            <button className="course-card-open-btn" type="button" onClick={() => setView("workspace")}>
                              {t("openLesson")}
                            </button>
                          )}
                        </>
                      ) : (
                        <span className="course-card-muted-action">{t("historyRecord")}</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ===== New Lesson View ===== */}
        {view === "new" && !reportViewAudience && (
          <div className="content-area new-lesson-view">
            <div className="new-lesson-heading">
              <span className="page-eyebrow">{t("newLesson")}</span>
              <h2>{t("newLessonTitle")}</h2>
              <p>{t("newLessonSubtitle")}</p>
            </div>

            <div className="new-lesson-layout">
              <section className="new-lesson-section">
                <div className="section-heading">
                  <span>1</span>
                  <div>
                    <h3>{t("lessonDetails")}</h3>
                    <p>{t("lessonDetailsHint")}</p>
                  </div>
                </div>
                <div className="lesson-form-grid">
                  <label>
                    <span>{t("studentName")}</span>
                    <input value={newLesson.studentName} onChange={(event) => updateNewLesson("studentName", event.target.value)} />
                  </label>
                  <label>
                    <span>{t("studentLevel")}</span>
                    <input value={newLesson.studentLevel} onChange={(event) => updateNewLesson("studentLevel", event.target.value)} />
                  </label>
                  <label>
                    <span>{t("studentAge")}</span>
                    <input type="number" min="3" max="99" value={newLesson.studentAge} onChange={(event) => updateNewLesson("studentAge", Number(event.target.value))} />
                  </label>
                  <label>
                    <span>{t("teacherName")}</span>
                    <input value={newLesson.teacherName} onChange={(event) => updateNewLesson("teacherName", event.target.value)} />
                  </label>
                  <label>
                    <span>{t("lessonTopic")}</span>
                    <input value={newLesson.topic} onChange={(event) => updateNewLesson("topic", event.target.value)} />
                  </label>
                  <label>
                    <span>{t("lessonDate")}</span>
                    <input type="date" value={newLesson.date} onChange={(event) => updateNewLesson("date", event.target.value)} />
                  </label>
                  <label>
                    <span>{t("lessonDuration")}</span>
                    <input type="number" min="5" max="180" value={newLesson.duration} onChange={(event) => updateNewLesson("duration", Number(event.target.value))} />
                  </label>
                </div>
              </section>

              <section className="new-lesson-section">
                <div className="section-heading">
                  <span>2</span>
                  <div>
                    <h3>{t("audioSource")}</h3>
                    <p>{t("audioSourceHint")}</p>
                  </div>
                </div>
                <div className="audio-source-control">
                  <button className={audioSource === "sample" ? "active" : ""} type="button" onClick={() => setAudioSource("sample")}>
                    <Sparkles size={18} />
                    <strong>{t("demoSample")}</strong>
                    <small>{t("demoSampleHint")}</small>
                  </button>
                  <button className={audioSource === "upload" ? "active" : ""} type="button" onClick={() => setAudioSource("upload")}>
                    <UploadCloud size={18} />
                    <strong>{t("uploadRecording")}</strong>
                    <small>{t("uploadRecordingHint")}</small>
                  </button>
                  <button className={audioSource === "record" ? "active" : ""} type="button" onClick={() => setAudioSource("record")}>
                    <Mic2 size={18} />
                    <strong>{t("browserRecording")}</strong>
                    <small>{t("browserRecordingHint")}</small>
                  </button>
                </div>
                {audioSource === "sample" && (
                  <div className="demo-sample-options">
                    {(["standard", "extended"] as DemoSampleId[]).map((id) => (
                      <button
                        className={sampleId === id ? "active" : ""}
                        key={id}
                        type="button"
                        onClick={() => selectDemoSample(id)}
                      >
                        <span className="sample-select-icon">
                          {sampleId === id ? <CircleCheck size={18} /> : <span />}
                        </span>
                        <strong>{id === "extended" ? t("extendedSample") : t("standardSample")}</strong>
                        <small>{id === "extended" ? t("extendedSampleHint") : t("standardSampleHint")}</small>
                        <em>{id === "extended" ? t("extendedSampleDuration") : t("standardSampleDuration")}</em>
                      </button>
                    ))}
                  </div>
                )}
                {audioSource === "upload" && (
                  <div className="new-audio-grid">
                    <label className="audio-drop">
                      <span>{t("teacherTrack")}</span>
                      <strong>{teacherAudioFile?.name ?? t("chooseAudio")}</strong>
                      <small>{teacherAudioFile ? formatFileSize(teacherAudioFile.size) : t("audioRequired")}</small>
                      <input accept="audio/*" type="file" onChange={(event) => setTeacherAudioFile(event.target.files?.[0] ?? null)} />
                    </label>
                    <label className="audio-drop">
                      <span>{t("studentTrack")}</span>
                      <strong>{studentAudioFile?.name ?? t("chooseAudio")}</strong>
                      <small>{studentAudioFile ? formatFileSize(studentAudioFile.size) : t("audioRequired")}</small>
                      <input accept="audio/*" type="file" onChange={(event) => setStudentAudioFile(event.target.files?.[0] ?? null)} />
                    </label>
                  </div>
                )}
                {audioSource === "record" && (
                  <div className="recording-grid">
                    <RecordingTrackCard
                      durationLabel={t("recordingDuration")}
                      isActive={recordingTrack === "teacher" && recordingStatus === "recording"}
                      onClear={() => clearRecordedTrack("teacher")}
                      onStart={() => startRecording("teacher")}
                      onStop={stopRecording}
                      recording={teacherRecording}
                      reRecordLabel={t("reRecord")}
                      startLabel={t("startRecording")}
                      stopLabel={t("stopRecording")}
                      title={t("teacherTrack")}
                    />
                    <RecordingTrackCard
                      durationLabel={t("recordingDuration")}
                      isActive={recordingTrack === "student" && recordingStatus === "recording"}
                      onClear={() => clearRecordedTrack("student")}
                      onStart={() => startRecording("student")}
                      onStop={stopRecording}
                      recording={studentRecording}
                      reRecordLabel={t("reRecord")}
                      startLabel={t("startRecording")}
                      stopLabel={t("stopRecording")}
                      title={t("studentTrack")}
                    />
                    {recordingError && <p className="form-error recording-error">{recordingError}</p>}
                  </div>
                )}
              </section>

              <div className="new-lesson-footer">
                <label className="recording-consent">
                  <input type="checkbox" checked={recordingConsent} onChange={(event) => setRecordingConsent(event.target.checked)} />
                  <span>{t("recordingConsent")}</span>
                </label>
                <div className="new-lesson-actions">
                  <button className="secondary-action" type="button" onClick={() => setView("list")}>{t("cancelEdit")}</button>
                  <button
                    className="primary-action"
                    type="button"
                    onClick={startNewLesson}
                    disabled={
                      audioProcessing ||
                      recordingStatus === "recording" ||
                      !recordingConsent ||
                      (audioSource === "upload" && (!teacherAudioFile || !studentAudioFile)) ||
                      (audioSource === "record" && (!teacherRecording || !studentRecording))
                    }
                  >
                    <Sparkles size={16} />
                    {audioProcessing ? t("processingAudio") : t("createAndAnalyze")}
                  </button>
                </div>
              </div>
              {loadError && <p className="form-error">{loadError}</p>}
            </div>
          </div>
        )}

        {/* ===== Student/Parent Report View ===== */}
        {reportViewAudience && reportViewLessonId === DEMO_LESSON_ID && lesson.final_reports && (
          <div className="content-area report-view-area">
            <div className="report-view-container">
              {/* Audience Toggle */}
              <div className="report-audience-toggle">
                <button
                  className={`audience-btn ${reportViewAudience === "student" ? "active" : ""}`}
                  type="button"
                  onClick={() => setReportViewAudience("student")}
                >
                  <UserRoundCheck size={16} />
                  {t("studentReport")}
                </button>
                <button
                  className={`audience-btn ${reportViewAudience === "parent" ? "active" : ""}`}
                  type="button"
                  onClick={() => setReportViewAudience("parent")}
                >
                  <ShieldCheck size={16} />
                  {t("parentReport")}
                </button>
              </div>

              {/* Report Content */}
              {(() => {
                const rawReport = lesson.final_reports[reportViewAudience];
                if (!rawReport) {
                  return (
                    <div className="report-not-ready">
                      <AlertTriangle size={32} />
                      <p>{t("reportNotReady")}</p>
                    </div>
                  );
                }
                const sharedReport = buildProductReport(
                  lesson,
                  reportViewAudience,
                  lang,
                  homework,
                  teacherNote,
                  t("noSummary")
                );
                return (
                  <div className="report-card">
                    <div className="report-card-header">
                      <h2>{sharedReport.title}</h2>
                      <div className="report-card-meta">
                        <span>{lesson.metadata.student_name}</span>
                        <span>{t("topic")}: {lesson.metadata.lesson_topic}</span>
                        <span>{lesson.metadata.lesson_date}</span>
                      </div>
                    </div>
                    <div className="report-sections">
                      {sharedReport.sections.filter((section) => section.items.length > 0).map((section) => (
                        <div className="report-section" key={section.heading}>
                          <h3>{section.heading}</h3>
                          <ul>{section.items.map((item, index) => <li key={`${section.heading}-${index}`}>{item}</li>)}</ul>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })()}
            </div>
          </div>
        )}

        {/* ===== Workspace View ===== */}
        {view === "workspace" && !reportViewAudience && (
        <>
        {/* ===== Step Bar ===== */}
        <nav className="step-bar">
          {stepDefs.map((step, i) => (
            <button
              key={step.id}
              className={`step-item ${activeTab === step.id ? "active" : ""} ${stepDoneMap[step.id] ? "done" : ""}`}
              type="button"
              onClick={() => setActiveTab(step.id)}
            >
              <span className="step-num">{stepDoneMap[step.id] ? <CheckCircle2 size={12} /> : i + 1}</span>
              {t(step.labelKey)}
              {i < stepDefs.length - 1 && <span className="step-arrow">→</span>}
            </button>
          ))}
        </nav>

        {/* ===== Compact Metrics Row ===== */}
        <div className="metrics-row">
          <div className="metric-inline">
            <AlertTriangle size={16} />
            <strong>{pendingReviewCount}</strong>
            <span>{t("pendingItems")}</span>
          </div>
          <div className="metric-divider" />
          <div className="metric-inline">
            <CircleCheck size={16} />
            <strong>{reviewProgress}%</strong>
            <span>{t("reviewProgress")}</span>
          </div>
          <div className="metric-divider" />
          <div className="metric-inline">
            <ClipboardCheck size={16} />
            <strong>{homework.length}</strong>
            <span>{t("homeworkItems")}</span>
          </div>
          <div className="metric-divider" />
          <div className="metric-inline">
            <Clock3 size={16} />
            <strong>{pendingReviewCount > 0 ? "2-3" : "0"}</strong>
            <span>{t("minutesToFinish")}</span>
          </div>
        </div>

        {/* ===== Content Area ===== */}
        <div className="content-area">
          {loading ? (
            <div className="loading-overlay">
              <div className="spinner" />
              <p>{t("loadingLesson")}</p>
              <div className="skeleton-card" style={{ width: "60%" }} />
              <div className="skeleton-card" style={{ width: "80%" }} />
            </div>
          ) : (
            <>
              {/* ===== Tab: Overview ===== */}
              <div className={activeTab === "overview" ? "" : "tab-hidden"}>
                <section className="review-summary-band">
                  <div className="review-summary-copy">
                    <span className="page-eyebrow">{t("aiAnalysisReady")}</span>
                    <h2>{t("reviewSummaryTitle").replace("{name}", lesson.metadata.student_name)}</h2>
                    <p>{lessonSummaryText(lesson, lang, t("noSummary"))}</p>
                    <div className="review-progress-line">
                      <div className="review-progress-track"><span style={{ width: `${reviewProgress}%` }} /></div>
                      <strong>{reviewedItemCount}/{totalReviewItems} {t("confirmedItems")}</strong>
                    </div>
                  </div>
                  <div className="review-summary-actions">
                    <div className="pending-callout">
                      <strong>{pendingReviewCount}</strong>
                      <span>{t("itemsNeedReview")}</span>
                    </div>
                    <button className="primary-action" type="button" onClick={() => setActiveTab("review")}>
                      <ShieldCheck size={16} />
                      {t("startReview")}
                    </button>
                    <button className="secondary-action" type="button" onClick={() => setActiveTab("draft")}>
                      <FileText size={16} />
                      {t("openDraft")}
                    </button>
                  </div>
                </section>
                <AudioIngestPanel
                  audioIngest={audioIngest}
                  processing={audioProcessing}
                  studentFile={studentAudioFile}
                  teacherFile={teacherAudioFile}
                  onStudentFile={setStudentAudioFile}
                  onTeacherFile={setTeacherAudioFile}
                  onProcess={() => processAudioUpload(false)}
                  onUseSample={() => processAudioUpload(true)}
                />
                <div className="overview-grid">
                  <section className="panel transcript-panel">
                    <PanelTitle icon={<MessageSquareText size={18} />} title={t("classTranscript")}>
                      <span className="panel-count">{mergedTranscript.length} {t("segments")}</span>
                    </PanelTitle>
                    <div className="transcript-list">
                      {mergedTranscript.map((segment) => (
                        <article
                          className={`transcript-item ${segment.speaker} ${
                            activeSegmentIds.has(segment.segment_id) ? "highlighted" : ""
                          }`}
                          id={`segment-${segment.segment_id}`}
                          key={segment.segment_id}
                        >
                          <div className="transcript-meta">
                            <span>{segment.speaker === "teacher" ? t("teacherSpeaker") : t("studentSpeaker")}</span>
                            <strong>{timeRange(segment.start_time, segment.end_time)}</strong>
                          </div>
                          <p>{segment.text}</p>
                          {segment.asr_confidence <= 0.9 && (
                            <span className={confidenceClass("medium")}>{t("transcriptNeedsReview")}</span>
                          )}
                        </article>
                      ))}
                    </div>
                  </section>

                  <div>
                    {/* Developer details */}
                    <div className={`workflow-collapse ${workflowExpanded ? "expanded" : ""}`}>
                      <div
                        className="workflow-collapse-header"
                        onClick={() => setWorkflowExpanded(!workflowExpanded)}
                      >
                        <div className="header-left">
                          <Settings2 size={16} />
                          {t("developerInfo")}
                        </div>
                        <div className="header-badges">
                          <span className="runtime-badge passed">{t("aiAnalysisReady")}</span>
                          {workflowExpanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                        </div>
                      </div>
                      {workflowExpanded && (
                        <div className="workflow-collapse-body">
                          <WorkflowPanel
                            nodes={workflowNodes}
                            agentRuntime={agentRuntime}
                            reviewResult={lesson.review_result}
                            ruleValidationResult={lesson.rule_validation_result}
                            revisionCount={revisionCount}
                            teacherGateConfirmed={teacherGateConfirmed}
                            risksPending={!highMediumRisksResolved}
                          />
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* ===== Tab: Draft ===== */}
              <div className={activeTab === "draft" ? "" : "tab-hidden"}>
                <div className="draft-grid">
                  <section className="panel draft-panel">
                    <PanelTitle icon={<FileText size={18} />} title={t("aiDraftReport")} />
                    <div className="report-block">
                      <h3>{t("lessonSummary")}</h3>
                      <p>{lessonSummaryText(lesson, lang, t("noSummary"))}</p>
                    </div>
                    <ReportList title={t("knowledgePoints")} items={lesson.draft_report.knowledge_points ?? []} evidenceById={evidenceById} onEvidenceFocus={focusEvidence} editable category="knowledge_points" editedTexts={editedTexts} deletedIndices={deletedIndices} onEdit={editDraftItem} onDelete={deleteDraftItem} />
                    <ReportList title={t("studentQuestions")} items={lesson.draft_report.student_questions ?? []} evidenceById={evidenceById} onEvidenceFocus={focusEvidence} editable category="student_questions" editedTexts={editedTexts} deletedIndices={deletedIndices} onEdit={editDraftItem} onDelete={deleteDraftItem} />
                    <ReportList title={t("corrections")} items={lesson.draft_report.corrections ?? []} evidenceById={evidenceById} onEvidenceFocus={focusEvidence} editable category="corrections" editedTexts={editedTexts} deletedIndices={deletedIndices} onEdit={editDraftItem} onDelete={deleteDraftItem} />
                    <ReportList title={t("pronunciationFeedback")} items={lesson.draft_report.pronunciation_feedback ?? []} evidenceById={evidenceById} onEvidenceFocus={focusEvidence} editable category="pronunciation_feedback" editedTexts={editedTexts} deletedIndices={deletedIndices} onEdit={editDraftItem} onDelete={deleteDraftItem} />
                    <ReportList title={t("homework")} items={homework} evidenceById={evidenceById} onEvidenceFocus={focusEvidence} />
                    <ReportList
                      title={t("nextLessonSuggestions")}
                      items={lesson.draft_report.next_lesson_suggestions ?? []}
                      evidenceById={evidenceById}
                      onEvidenceFocus={focusEvidence}
                      editable
                      category="next_lesson_suggestions"
                      editedTexts={editedTexts}
                      deletedIndices={deletedIndices}
                      onEdit={editDraftItem}
                      onDelete={deleteDraftItem}
                    />
                  </section>

                  <section className="panel transcript-panel">
                    <PanelTitle icon={<MessageSquareText size={18} />} title={t("classTranscript")}>
                      <span className="panel-count">{mergedTranscript.length} {t("segments")}</span>
                    </PanelTitle>
                    <div className="transcript-list">
                      {mergedTranscript.map((segment) => (
                        <article
                          className={`transcript-item ${segment.speaker} ${
                            activeSegmentIds.has(segment.segment_id) ? "highlighted" : ""
                          }`}
                          id={`segment-${segment.segment_id}`}
                          key={segment.segment_id}
                        >
                          <div className="transcript-meta">
                            <span>{segment.speaker === "teacher" ? t("teacherSpeaker") : t("studentSpeaker")}</span>
                            <strong>{timeRange(segment.start_time, segment.end_time)}</strong>
                          </div>
                          <p>{segment.text}</p>
                          {segment.asr_confidence <= 0.9 && (
                            <span className={confidenceClass("medium")}>{t("transcriptNeedsReview")}</span>
                          )}
                        </article>
                      ))}
                    </div>
                  </section>
                </div>
              </div>

              {/* ===== Tab: Review ===== */}
              <div className={activeTab === "review" ? "" : "tab-hidden"}>
                <div className="review-queue-intro">
                  <div>
                    <span className="page-eyebrow">{t("reviewQueueEyebrow")}</span>
                    <h2>{t("reviewQueueTitle")}</h2>
                    <p>{t("reviewQueueHint")}</p>
                  </div>
                  <div className="review-queue-progress">
                    <strong>{reviewProgress}%</strong>
                    <span>{reviewedItemCount}/{totalReviewItems} {t("confirmedItems")}</span>
                  </div>
                </div>
                <div className="sub-tabs">
                  <button
                    className={reviewSubTab === "risks" ? "active" : ""}
                    type="button"
                    onClick={() => setReviewSubTab("risks")}
                  >
                    {t("subTabRisks")}
                    <span className="count-badge">{risks.length}</span>
                  </button>
                  <button
                    className={reviewSubTab === "homework" ? "active" : ""}
                    type="button"
                    onClick={() => setReviewSubTab("homework")}
                  >
                    {t("subTabHomework")}
                    <span className="count-badge">{homework.length}</span>
                  </button>
                  <button
                    className={reviewSubTab === "pronunciation" ? "active" : ""}
                    type="button"
                    onClick={() => setReviewSubTab("pronunciation")}
                  >
                    {t("subTabPronunciation")}
                    <span className="count-badge">{lesson.pronunciation_assessments.length}</span>
                  </button>
                </div>

                {reviewSubTab === "risks" && (
                  <section className="panel">
                    <PanelTitle icon={<AlertTriangle size={18} />} title={t("riskHighlights")}>
                      <span className="panel-count">{confirmedRiskCount}/{risks.length}</span>
                    </PanelTitle>
                    <div className="risk-list">
                      {sortedRisks.map((risk) => {
                        const copy = riskProductCopy(risk, lang);
                        const riskEvidenceIds = risk.related_ids.filter((id) => evidenceById.has(id));
                        return (
                          <article className={`risk-item ${risk.level} ${risk.confirmed ? "confirmed" : ""} ${risk.dismissed ? "dismissed" : ""}`} key={risk.risk_id}>
                          <input
                            type="checkbox"
                            checked={Boolean(risk.confirmed)}
                            onChange={() => confirmRisk(risk.risk_id)}
                            aria-label={copy.title}
                          />
                          <div>
                            <div className="risk-header">
                              <strong>{copy.title}</strong>
                              <span className={confidenceClass(risk.level)}>{confidenceLabelText(risk.level, t)}</span>
                            </div>
                            <textarea
                              className="risk-message-edit"
                              aria-label={t("editRiskMessage")}
                              value={risk.message}
                              onChange={(e) => updateRiskMessage(risk.risk_id, e.target.value)}
                              rows={2}
                            />
                            <div className="risk-detail">
                              <span>{risk.confirmed ? t("itemConfirmed") : t("confirmItemHint")}</span>
                            </div>
                            <textarea
                              className="teacher-note-input"
                              aria-label={t("teacherNoteLabel")}
                              placeholder={t("teacherNotePlaceholder")}
                              value={risk.teacher_note ?? ""}
                              onChange={(e) => updateRiskNote(risk.risk_id, e.target.value)}
                              rows={2}
                            />
                            <div className="risk-actions">
                              <button
                                className="mini-btn dismiss-btn"
                                type="button"
                                onClick={() => dismissRisk(risk.risk_id)}
                              >
                                {risk.dismissed ? t("reinstateRisk") : t("dismissRisk")}
                              </button>
                            </div>
                            {riskEvidenceIds.length > 0 && (
                              <EvidenceLinks ids={riskEvidenceIds} evidenceById={evidenceById} onFocus={focusEvidence} />
                            )}
                            {risk.confirmed && <strong className="resolved-label">{t("resolved")}</strong>}
                          </div>
                          </article>
                        );
                      })}
                    </div>
                  </section>
                )}

                {reviewSubTab === "homework" && (
                  <section className="panel">
                    <PanelTitle icon={<ListChecks size={18} />} title={t("homeworkCandidates")}>
                      <span className="panel-count">{confirmedHomeworkCount}/{homework.length}</span>
                    </PanelTitle>
                    <div className="homework-list">
                      {homework.map((item) => (
                        <article className="homework-item" key={item.homework_id}>
                          <div className="homework-head">
                            <label>
                              <input
                                type="checkbox"
                                checked={item.teacher_confirmed}
                                onChange={() => toggleHomework(item.homework_id)}
                              />
                              <strong>{item.title}</strong>
                            </label>
                            <span className={confidenceClass(item.confidence)}>{confidenceLabelText(item.confidence, t)}</span>
                          </div>
                          {(item.confidence === "medium" || item.confidence === "low") && (
                            <p className="review-hint">{t("teacherConfirmRequired")}</p>
                          )}
                          <textarea
                            aria-label={item.title}
                            value={item.description}
                            onChange={(event) => updateHomework(item.homework_id, event.target.value)}
                          />
                          <textarea
                            className="teacher-note-input"
                            aria-label={t("homeworkNoteLabel")}
                            placeholder={t("teacherNotePlaceholder")}
                            value={item.teacher_note ?? ""}
                            onChange={(e) => updateHomeworkNote(item.homework_id, e.target.value)}
                            rows={2}
                          />
                          <EvidenceLinks ids={getEvidenceIds(item)} evidenceById={evidenceById} onFocus={focusEvidence} />
                        </article>
                      ))}
                    </div>
                  </section>
                )}

                {reviewSubTab === "pronunciation" && (
                  <section className="panel">
                    <PanelTitle icon={<Mic2 size={18} />} title={t("pronunciationAssessment")}>
                      <span className="panel-count">{lesson.pronunciation_assessments.length}</span>
                    </PanelTitle>
                    <p className="boundary-note">{t("pronunciationBoundaryNote")}</p>
                    {lesson.pronunciation_assessments.map((assessment) => (
                      <article className={`pron-card ${assessment.teacher_confirmed ? "confirmed" : ""}`} key={assessment.assessment_id}>
                        <div className="pron-meta">
                          <span>{t("reference")}: {assessment.reference_text}</span>
                          <span className={confidenceClass(assessment.model_confidence)}>
                            {t("model")} {confidenceLabelText(assessment.model_confidence, t)}
                          </span>
                        </div>
                        <div className="score-row">
                          <Score label={t("overall")} value={assessment.pronunciation_score} />
                          <Score label={t("accuracy")} value={assessment.accuracy_score} />
                          <Score label={t("fluency")} value={assessment.fluency_score} />
                        </div>
                        <div className="low-word">
                          <strong>
                            {assessment.teacher_confirmation_required
                              ? t("needsTeacherConfirm")
                              : t("noTeacherConfirm")}
                          </strong>
                          {assessment.low_score_words.length > 0 ? (
                            <ul>
                              {assessment.low_score_words.map((word) => (
                                <li key={`${assessment.assessment_id}-${word.word}-${word.error_type}`}>
                                  {word.word}: {word.error_type} · score {word.accuracy_score}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <p>{t("noLowScoreWords")}</p>
                          )}
                          <span className="assessment-flag">
                            {assessment.teacher_confirmation_required ? t("teacherConfirmRequiredFlag") : t("teacherConfirmOptional")}
                          </span>
                        </div>
                        <div className="pron-teacher-actions">
                          <label className="pron-confirm-label">
                            <input
                              type="checkbox"
                              checked={Boolean(assessment.teacher_confirmed)}
                              onChange={() => togglePronConfirmation(assessment.assessment_id)}
                            />
                            {t("pronConfirmLabel")}
                          </label>
                          <textarea
                            className="teacher-note-input"
                            aria-label={t("pronTeacherNote")}
                            placeholder={t("teacherNotePlaceholder")}
                            value={assessment.teacher_note ?? ""}
                            onChange={(e) => updatePronNote(assessment.assessment_id, e.target.value)}
                            rows={2}
                          />
                        </div>
                      </article>
                    ))}
                  </section>
                )}
              </div>

              {/* ===== Tab: Final Report ===== */}
              <div className={activeTab === "report" ? "" : "tab-hidden"}>
                <section className="panel">
                  <div className="final-header">
                    <PanelTitle icon={<UserRoundCheck size={18} />} title={t("finalReportPreview")} />
                    <div className="audience-tabs">
                      {(["teacher", "student", "parent"] as Audience[]).map((audience) => (
                        <button
                          className={activeAudience === audience ? "active" : ""}
                          key={audience}
                          type="button"
                          onClick={() => setActiveAudience(audience)}
                        >
                          {t(audienceLabelKey(audience))}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="teacher-note">
                    <label htmlFor="teacher-note">
                      <Pencil size={16} />
                      {t("teacherNote")}
                    </label>
                    <textarea
                      id="teacher-note"
                      rows={2}
                      value={teacherNote}
                      onChange={(event) => setTeacherNote(event.target.value)}
                    />
                  </div>

                  <div className="delivery-settings">
                    <div>
                      <span>{t("recipients")}</span>
                      <strong>{lesson.metadata.student_name} · {t("parent")}</strong>
                    </div>
                    <div>
                      <span>{t("deliveryChannel")}</span>
                      <strong>{t("emailDelivery")}</strong>
                    </div>
                    <div>
                      <span>{t("deliveryStatus")}</span>
                      <strong>{reportSent ? t("reportSent") : finalReportSendReady ? t("readyToSend") : t("waitingForReview")}</strong>
                    </div>
                  </div>

                  <article className={`final-report ${finalReportSendReady ? "ready" : ""}`}>
                    <div className="report-status">
                      {finalReportSendReady ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}
                      <span>
                        {finalReportSendReady
                          ? t("teacherConfirmedStatus")
                          : highMediumRisksResolved && allHomeworkConfirmed
                            ? t("draftStatus")
                            : t("pendingReview")}
                      </span>
                    </div>
                    {!teacherGateConfirmed && (
                      <p className="draft-warning">{t("draftWarning")}</p>
                    )}
                    {!highMediumRisksResolved && (
                      <p className="draft-warning">{t("draftRiskWarning")}</p>
                    )}
                    <h3>{productReport.title}</h3>
                    {productReport.sections.filter((section) => section.items.length > 0).map((section) => (
                      <div className="final-section" key={section.heading}>
                        <strong>{section.heading}</strong>
                        <ul className="product-report-list">
                          {section.items.map((item, index) => <li key={`${section.heading}-${index}`}>{item}</li>)}
                        </ul>
                      </div>
                    ))}
                    {activeAudience === "teacher" && (
                      <div className="final-section">
                        <strong>{t("teacherNote")}</strong>
                        <p>{teacherNote}</p>
                      </div>
                    )}
                  </article>

                  {finalReportSendReady && !reportSent && (
                    <div className="send-report-section">
                      <p className="send-hint">{t("sendHint")}</p>
                      <button className="primary-action send-btn" type="button" onClick={sendReport} disabled={sending}>
                        <Send size={16} />
                        {sending ? t("sending") : t("sendReport")}
                      </button>
                    </div>
                  )}
                  {reportSent && (
                    <div className="send-report-section sent">
                      <CheckCircle2 size={20} />
                      <span>{t("reportSentTo")} {t("studentSpeaker")} / {t("parent")}</span>
                    </div>
                  )}
                </section>
              </div>
            </>
          )}
        </div>
        </>
        )}
      </div>
    </LangContext.Provider>
  );
}

function RecordingTrackCard({
  durationLabel,
  isActive,
  onClear,
  onStart,
  onStop,
  recording,
  reRecordLabel,
  startLabel,
  stopLabel,
  title
}: {
  durationLabel: string;
  isActive: boolean;
  onClear: () => void;
  onStart: () => void;
  onStop: () => void;
  recording: RecordedTrack | null;
  reRecordLabel: string;
  startLabel: string;
  stopLabel: string;
  title: string;
}) {
  return (
    <article className={`recording-card ${isActive ? "active" : ""}`}>
      <div className="recording-card-head">
        <strong>{title}</strong>
        <span>{isActive ? stopLabel : recording ? reRecordLabel : startLabel}</span>
      </div>
      {recording ? (
        <div className="recording-preview">
          <audio controls src={recording.objectUrl} />
          <small>{durationLabel}: {recording.durationSeconds}s</small>
        </div>
      ) : (
        <p>{startLabel}</p>
      )}
      <div className="recording-actions">
        {isActive ? (
          <button className="recording-stop" type="button" onClick={onStop}>
            {stopLabel}
          </button>
        ) : (
          <button className="recording-start" type="button" onClick={onStart}>
            <Mic2 size={15} />
            {recording ? reRecordLabel : startLabel}
          </button>
        )}
        {recording && !isActive && (
          <button className="recording-clear" type="button" onClick={onClear}>
            <X size={15} />
          </button>
        )}
      </div>
    </article>
  );
}

function AudioIngestPanel({
  audioIngest,
  processing,
  studentFile,
  teacherFile,
  onStudentFile,
  onTeacherFile,
  onProcess,
  onUseSample
}: {
  audioIngest?: AudioIngestResult;
  processing: boolean;
  studentFile: File | null;
  teacherFile: File | null;
  onStudentFile: (file: File | null) => void;
  onTeacherFile: (file: File | null) => void;
  onProcess: () => void;
  onUseSample: () => void;
}) {
  const t = useT();
  const teacherTrack = audioIngest?.tracks?.teacher;
  const studentTrack = audioIngest?.tracks?.student;
  const canProcess = Boolean(teacherFile && studentFile) && !processing;
  const pipeline = audioIngest?.pipeline ?? [];
  const loadedSampleLabel = audioIngest?.sample_id === "extended" ? t("extendedSample") : t("standardSample");
  const processed = audioIngest?.status === "mock_processed" || audioIngest?.status === "processed";
  const visiblePipeline = pipeline.length > 0
    ? pipeline.map((item) => item.step ?? "").filter(Boolean)
    : ["upload", "dual_track_binding", "mock_asr", "mock_pronunciation_assessment", "lesson_object_mapping"];
  return (
    <section className="panel audio-ingest-panel">
      <PanelTitle icon={<UploadCloud size={18} />} title={t("audioIngestTitle")}>
        <span className={`runtime-badge ${processed ? "passed" : "pending"}`}>
          {processed
            ? `${t("mockProcessed")}${audioIngest?.source === "demo_sample" ? ` · ${loadedSampleLabel}` : ""}`
            : t("waitingUpload")}
        </span>
      </PanelTitle>
      <div className="audio-ingest-grid">
        <label className="audio-drop">
          <span>{t("teacherTrack")}</span>
          <strong>{teacherFile?.name ?? teacherTrack?.filename ?? t("chooseAudio")}</strong>
          <small>{teacherFile ? formatFileSize(teacherFile.size) : teacherTrack?.status === "sample_loaded" ? t("sampleAudio") : formatFileSize(teacherTrack?.size_bytes)}</small>
          <input
            accept="audio/*"
            type="file"
            onChange={(event) => onTeacherFile(event.target.files?.[0] ?? null)}
          />
        </label>
        <label className="audio-drop">
          <span>{t("studentTrack")}</span>
          <strong>{studentFile?.name ?? studentTrack?.filename ?? t("chooseAudio")}</strong>
          <small>{studentFile ? formatFileSize(studentFile.size) : studentTrack?.status === "sample_loaded" ? t("sampleAudio") : formatFileSize(studentTrack?.size_bytes)}</small>
          <input
            accept="audio/*"
            type="file"
            onChange={(event) => onStudentFile(event.target.files?.[0] ?? null)}
          />
        </label>
        <div className="audio-actions">
          <button className="audio-process" type="button" disabled={!canProcess} onClick={onProcess}>
            <UploadCloud size={16} />
            {processing ? t("processingAudio") : t("processMockAudio")}
          </button>
          <button className="audio-sample" type="button" disabled={processing} onClick={onUseSample}>
            <Sparkles size={16} />
            {t("useTestSample")}
          </button>
        </div>
      </div>
      <div className="audio-pipeline">
        {visiblePipeline.map((step) => {
          const matched = pipeline.find((item) => item.step === step);
          const translationKey = `audioStep_${step}` as TranslationKey;
          const translated = t(translationKey);
          return (
            <span className={`runtime-badge ${matched?.status === "passed" ? "passed" : "pending"}`} key={step}>
              {translated === translationKey ? step : translated}
            </span>
          );
        })}
      </div>
      {audioIngest?.mock_outputs && (
        <div className="audio-output-metrics">
          <span>{t("teacherSegments")}: {audioIngest.mock_outputs.teacher_segments ?? 0}</span>
          <span>{t("studentSegments")}: {audioIngest.mock_outputs.student_segments ?? 0}</span>
          <span>{t("practiceClips")}: {audioIngest.mock_outputs.practice_clips ?? 0}</span>
          <span>{t("pronunciationAssessments")}: {audioIngest.mock_outputs.pronunciation_assessments ?? 0}</span>
          <span>{t("audioDuration")}: {Math.ceil((audioIngest.mock_outputs.duration_seconds ?? 0) / 60)} {t("min")}</span>
        </div>
      )}
    </section>
  );
}

function WorkflowPanel({
  nodes,
  agentRuntime,
  reviewResult,
  ruleValidationResult,
  revisionCount,
  teacherGateConfirmed,
  risksPending
}: {
  nodes: WorkflowNodeView[];
  agentRuntime: AgentRuntimeView;
  reviewResult: LessonObject["review_result"];
  ruleValidationResult: LessonObject["rule_validation_result"];
  revisionCount: number;
  teacherGateConfirmed: boolean;
  risksPending: boolean;
}) {
  const t = useT();
  const maxReviewLoopReached = revisionCount >= 2;
  return (
    <section className="panel workflow-panel">
      <div className="workflow-header">
        <PanelTitle icon={<Sparkles size={18} />} title={t("langGraphWorkflow")} />
        <div className="agent-runtime">
          <span className={`runtime-badge ${agentRuntime.mode === t("realLlm") ? "real" : agentRuntime.mode === t("fallbackToMock") ? "fallback" : "mock"}`}>
            {agentRuntime.mode}
          </span>
          {agentRuntime.provider && <span className="runtime-badge">{t("provider")}: {agentRuntime.provider}</span>}
          {agentRuntime.model && <span className="runtime-badge">{t("modelLabel")}: {agentRuntime.model}</span>}
          <span className={`runtime-badge ${agentRuntime.schemaStatus}`}>{agentRuntime.schemaLabel}</span>
          {agentRuntime.fallbackReason && (
            <span className="runtime-badge fallback" title={agentRuntime.fallbackReason}>
              {t("fallback")}
            </span>
          )}
        </div>
      </div>
      <span className="workflow-subtitle">{t("workflowSubtitle")}</span>

      <div className="workflow-nodes">
        {nodes.map((node, index) => (
          <article className={`workflow-node ${node.status}`} key={node.id}>
            <div className="workflow-node-top">
              <span className="node-index">{index + 1}</span>
              <strong>{node.label}</strong>
              <span className={`node-status ${node.status}`}>{node.status}</span>
            </div>
            <p>{node.detail}</p>
            {node.badges.length > 0 && (
              <div className="node-badges">
                {node.badges.map((badge) => (
                  <span className="runtime-badge" key={badge} title={badge}>
                    {badge}
                  </span>
                ))}
              </div>
            )}
            <small>{node.source === "backend" ? t("backendTrace") : t("inferredFromLesson")}</small>
          </article>
        ))}
      </div>

      <div className="workflow-gates">
        <div className="workflow-gate">
          <strong>{t("writerReviewerLoop")}</strong>
          <span>{t("revisionCountLabel")}: {revisionCount}</span>
          {agentRuntime.writerMode && <p>{t("writerAgent")}: {agentRuntime.writerMode}</p>}
          {agentRuntime.reviewerMode && <p>{t("reviewerAgent")}: {agentRuntime.reviewerMode}</p>}
          {!reviewResult.pass && reviewResult.revision_instruction && (
            <p>{reviewResult.revision_instruction}</p>
          )}
          {revisionCount > 0 && <p>{t("writerRevised")}</p>}
          {maxReviewLoopReached && <p className="gate-warning">{t("maxLoopReached")}</p>}
        </div>

        <div className="workflow-gate">
          <strong>{t("ruleValidator")}</strong>
          <span>{ruleValidationResult.pass ? t("passed") : t("failed")}</span>
          {ruleValidationResult.blocking_issues.length > 0 && (
            <p>{t("blocking")}: {ruleValidationResult.blocking_issues.join("; ")}</p>
          )}
          {ruleValidationResult.warnings.length > 0 && (
            <p>{t("warningsCount")}: {ruleValidationResult.warnings.length}</p>
          )}
        </div>

        <div className={`workflow-gate ${teacherGateConfirmed && !risksPending ? "passed" : "warning"}`}>
          <strong>{t("teacherReviewGate")}</strong>
          <span>{teacherGateConfirmed ? t("teacherConfirmed") : t("draftBeforeConfirm")}</span>
          {risksPending && <p>{t("pendingRiskConfirm")}</p>}
        </div>
      </div>
    </section>
  );
}

function StatusRow({ label, done }: { label: string; done: boolean }) {
  const t = useT();
  return (
    <div className="status-row">
      {done ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
      <span>{label}</span>
      <strong>{done ? t("done") : t("open")}</strong>
    </div>
  );
}

function Metric({ icon, value, label }: { icon: ReactNode; value: string; label: string }) {
  return (
    <div className="metric">
      {icon}
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function PanelTitle({ icon, title, children }: { icon: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="panel-title">
      {icon}
      <h3>{title}</h3>
      {children}
    </div>
  );
}

function EvidenceLinks({
  ids,
  evidenceById,
  onFocus
}: {
  ids: string[];
  evidenceById: Map<string, { source_segment_ids: string[]; timestamp: string; claim: string; confidence: Confidence }>;
  onFocus: (evidenceId: string | null) => void;
}) {
  const t = useT();
  if (ids.length === 0) return <span className="missing-evidence">{t("missingEvidence")}</span>;
  return (
    <div className="evidence-links">
      {ids.map((id) => {
        const evidence = evidenceById.get(id);
        if (!evidence) {
          return (
            <span className="missing-evidence" key={id}>
              {t("missingEvidence")}
            </span>
          );
        }
        return (
          <button
            className="evidence-pill"
            key={id}
            title={`${evidence.timestamp} · ${evidence.claim}`}
            type="button"
            onClick={() => onFocus(id)}
            onMouseEnter={() => onFocus(id)}
          >
            {evidence.timestamp} · {t("classEvidence")}
          </button>
        );
      })}
    </div>
  );
}

function ReportList({
  title,
  items,
  evidenceById,
  onEvidenceFocus,
  editable = false,
  category = "",
  editedTexts,
  deletedIndices,
  onEdit,
  onDelete
}: {
  title: string;
  items: Array<ReportObject | HomeworkItem>;
  evidenceById?: Map<string, { source_segment_ids: string[]; timestamp: string; claim: string; confidence: Confidence }>;
  onEvidenceFocus?: (evidenceId: string | null) => void;
  editable?: boolean;
  category?: string;
  editedTexts?: Record<string, string>;
  deletedIndices?: Set<string>;
  onEdit?: (key: string, text: string) => void;
  onDelete?: (key: string) => void;
}) {
  const t = useT();
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editBuffer, setEditBuffer] = useState("");

  const visibleItems = items.map((item, index) => ({ item, index, key: `${category}_${index}` }))
    .filter(({ key }) => !deletedIndices?.has(key));

  return (
    <div className="report-block">
      <h3>{title}{editable && visibleItems.length > 0 && <span className="edit-hint">{t("edit")}</span>}</h3>
      <ul className="report-list">
        {visibleItems.map(({ item, index, key }) => {
          const isEditing = editingKey === key;
          const displayText = editedTexts?.[key] ?? getText(item);
          return (
            <li
              className={`report-item ${
                confidenceValue(item.confidence) === "medium" || confidenceValue(item.confidence) === "low"
                  ? "needs-review"
                  : ""
              }`}
              key={key}
            >
              <div className="report-item-row">
                {isEditing ? (
                  <div className="inline-edit">
                    <textarea
                      value={editBuffer}
                      onChange={(e) => setEditBuffer(e.target.value)}
                      rows={2}
                    />
                    <div className="inline-edit-actions">
                      <button type="button" className="mini-btn save" onClick={() => { onEdit?.(key, editBuffer); setEditingKey(null); }}>
                        {t("save")}
                      </button>
                      <button type="button" className="mini-btn cancel" onClick={() => setEditingKey(null)}>
                        {t("cancelEdit")}
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <span>{displayText}</span>
                    {item.confidence && <span className={confidenceClass(item.confidence)}>{confidenceLabelText(confidenceValue(item.confidence), t)}</span>}
                    {editable && (
                      <div className="item-actions">
                        <button type="button" className="mini-btn" onClick={() => { setEditingKey(key); setEditBuffer(displayText); }}>
                          <Pencil size={13} />
                        </button>
                        <button type="button" className="mini-btn danger" onClick={() => onDelete?.(key)}>
                          ×
                        </button>
                      </div>
                    )}
                  </>
                )}
              </div>
              {evidenceById && onEvidenceFocus && (
                <EvidenceLinks ids={getEvidenceIds(item)} evidenceById={evidenceById} onFocus={onEvidenceFocus} />
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function Score({ label, value }: { label: string; value: number }) {
  return (
    <div className="score">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}
