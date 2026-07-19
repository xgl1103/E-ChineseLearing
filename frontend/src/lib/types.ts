export type Confidence = "high" | "medium" | "low" | "unknown";
export type Speaker = "teacher" | "student";
export type Audience = "teacher" | "student" | "parent";
export type WorkflowStatus = "pending" | "running" | "passed" | "warning" | "failed";
export type AgentMode = "mock" | "real_llm" | "fallback" | string;
export type LessonLifecycleStatus = "processing" | "review_required" | "ready_to_send" | "sent" | "failed";
export type CourseFilter = "all" | "review_required" | "sent";
export type AudioSource = "upload" | "sample" | "record";
export type DemoSampleId = "standard" | "extended";

export interface CourseListItem {
  lessonId: string;
  studentName: string;
  topic: string;
  date: string;
  duration: number;
  status: LessonLifecycleStatus;
  teacher: string;
  interactive?: boolean;
  jobId?: string;
  progress?: number;
  stage?: string;
  statusMessage?: string;
  error?: string;
}

export type AnalysisJobStatus = "queued" | "running" | "completed" | "failed";

export interface AnalysisJob {
  job_id: string;
  lesson_id: string;
  status: AnalysisJobStatus;
  stage: string;
  progress: number;
  message: string;
  revision_count: number;
  error?: string;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  metadata: Metadata;
  input_source: AudioSource;
  sample_id?: DemoSampleId | null;
  result?: LessonObject | null;
}

export interface NewLessonDraft {
  studentName: string;
  studentAge: number;
  studentLevel: string;
  teacherName: string;
  topic: string;
  date: string;
  duration: number;
}

export type ReportContent = string | number | boolean | null | ReportContent[] | { [key: string]: ReportContent };

export interface Metadata {
  student_name: string;
  student_age: number;
  student_level: string;
  course_type: string;
  lesson_topic: string;
  lesson_duration_minutes: number;
  teacher_name: string;
  lesson_date: string;
  [key: string]: unknown;
}

export interface TranscriptSegment {
  segment_id: string;
  speaker: Speaker;
  start_time: number;
  end_time: number;
  text: string;
  language_tags: string[];
  asr_confidence: number;
}

export interface EvidenceItem {
  evidence_id: string;
  type: string;
  source_segment_ids: string[];
  timestamp: string;
  claim: string;
  confidence: Confidence;
  [key: string]: unknown;
}

export interface Evidence {
  knowledge_points?: EvidenceItem[];
  homework?: EvidenceItem[];
  corrections?: EvidenceItem[];
  teacher_questions?: EvidenceItem[];
  student_questions?: EvidenceItem[];
  pronunciation?: EvidenceItem[];
  [key: string]: EvidenceItem[] | undefined;
}

export interface PracticeClip {
  clip_id: string;
  student_segment_id: string;
  audio_uri: string;
  clip_start: number;
  clip_end: number;
  reference_text: string;
  reference_source: string;
  reference_confidence: Exclude<Confidence, "unknown">;
  should_assess_pronunciation: boolean;
}

export interface LowScoreWord {
  word: string;
  accuracy_score: number;
  error_type: string;
  note?: string;
}

export interface PronunciationAssessment {
  assessment_id: string;
  clip_id: string;
  reference_text: string;
  pronunciation_score: number;
  accuracy_score: number;
  fluency_score: number;
  completeness_score: number;
  prosody_score: number;
  low_score_words: LowScoreWord[];
  model_confidence: Exclude<Confidence, "unknown">;
  teacher_confirmation_required: boolean;
  teacher_confirmed?: boolean;
  teacher_note?: string;
}

export interface HomeworkItem {
  homework_id: string;
  title: string;
  description: string;
  type: string;
  source_evidence_id: string;
  confidence: Exclude<Confidence, "unknown">;
  teacher_confirmed: boolean;
  teacher_note?: string;
}

export interface RiskHighlight {
  risk_id: string;
  level: Exclude<Confidence, "unknown">;
  module: string;
  message: string;
  related_ids: string[];
  teacher_action: string;
  confirmed?: boolean;
  teacher_note?: string;
  dismissed?: boolean;
}

export interface ReportObject {
  id?: string;
  text?: string;
  question?: string;
  summary?: string;
  explanation?: string;
  student_original?: string;
  teacher_correction?: string;
  source_evidence_id?: string;
  confidence?: Confidence;
  [key: string]: unknown;
}

export interface DraftReport {
  lesson_summary?: string;
  knowledge_points?: ReportObject[];
  teacher_questions?: ReportObject[];
  student_questions?: ReportObject[];
  corrections?: ReportObject[];
  pronunciation_feedback?: ReportObject[];
  homework_items?: HomeworkItem[];
  student_assessment?: Record<string, unknown>;
  next_lesson_suggestions?: ReportObject[];
  [key: string]: unknown;
}

export interface RuleValidationResult {
  pass: boolean;
  blocking_issues: string[];
  warnings: string[];
  [key: string]: unknown;
}

export interface ReviewResult {
  pass: boolean;
  score: number;
  issues: string[];
  revision_instruction: string;
  revision_count: number;
  [key: string]: unknown;
}

export interface FinalReportSection {
  heading: string;
  content: ReportContent;
  items?: string[];
}

export interface FinalReport {
  title?: string;
  audience?: string;
  status?: string;
  summary?: string;
  sections?: FinalReportSection[];
  [key: string]: ReportContent | FinalReportSection[] | undefined;
}

export interface TeacherReview {
  status?: string;
  reviewed_at?: string | null;
  confirmed_homework_ids?: string[];
  confirmed_risk_ids?: string[];
  teacher_notes?: string;
  report_edits?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface WorkflowTraceItem {
  node_id?: string;
  node?: string;
  name?: string;
  label?: string;
  status?: WorkflowStatus | string;
  message?: string;
  detail?: string;
  started_at?: string;
  completed_at?: string;
  metadata?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface LlmTraceItem {
  node_id?: string;
  node?: string;
  agent?: string;
  name?: string;
  mode?: AgentMode;
  model_provider?: string;
  model_name?: string;
  provider?: string;
  model?: string;
  summary?: string;
  status?: string;
  fallback_reason?: string;
  schema_validation?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface SchemaValidationResult {
  pass?: boolean;
  passed?: boolean;
  valid?: boolean;
  status?: string;
  warnings?: string[];
  errors?: string[];
  repaired?: boolean;
  json_repair?: boolean;
  [key: string]: unknown;
}

export interface AudioIngestFile {
  track?: string;
  filename?: string;
  content_type?: string;
  size_bytes?: number;
  status?: string;
  [key: string]: unknown;
}

export interface AudioIngestStep {
  step?: string;
  status?: string;
  [key: string]: unknown;
}

export interface AudioIngestResult {
  mode?: string;
  status?: string;
  pipeline?: AudioIngestStep[];
  tracks?: {
    teacher?: AudioIngestFile;
    student?: AudioIngestFile;
    [key: string]: AudioIngestFile | undefined;
  };
  mock_outputs?: Record<string, number>;
  note?: string;
  [key: string]: unknown;
}

export interface RevisionHistoryItem {
  revision?: number;
  node?: string;
  reviewer_feedback?: string;
  revision_instruction?: string;
  writer_response?: string;
  timestamp?: string;
  [key: string]: unknown;
}

export interface LessonObject {
  lesson_id: string;
  metadata: Metadata;
  transcripts: {
    teacher: TranscriptSegment[];
    student: TranscriptSegment[];
  };
  practice_clips: PracticeClip[];
  pronunciation_assessments: PronunciationAssessment[];
  evidence: Evidence;
  confidence_scores: Record<string, Confidence>;
  draft_report: DraftReport;
  rule_validation_result: RuleValidationResult;
  review_result: ReviewResult;
  risk_highlights: RiskHighlight[];
  teacher_review: TeacherReview;
  final_reports: Record<Audience, FinalReport>;
  teacher_edit_log: Record<string, unknown>[];
  workflow_trace?: WorkflowTraceItem[] | Record<string, WorkflowTraceItem | WorkflowStatus | string | unknown>;
  agent_trace?: WorkflowTraceItem[] | Record<string, WorkflowTraceItem | WorkflowStatus | string | unknown>;
  graph_trace?: WorkflowTraceItem[] | Record<string, WorkflowTraceItem | WorkflowStatus | string | unknown>;
  graph_state?: Record<string, unknown>;
  revision_history?: RevisionHistoryItem[];
  agent_mode?: AgentMode;
  model_provider?: string;
  model_name?: string;
  llm_trace?: LlmTraceItem[];
  schema_validation?: SchemaValidationResult;
  fallback_reason?: string;
  audio_ingest?: AudioIngestResult;
}
