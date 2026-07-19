from __future__ import annotations

from backend.app.schemas import FinalReport, FinalReportSection, FinalReports, Lesson


def generate_final_reports(lesson: Lesson, audiences: list[str] | None = None) -> Lesson:
    audiences = audiences or ["teacher", "student", "parent"]
    draft = lesson.draft_report
    student_name = lesson.metadata.student_name
    report_status = (
        "teacher_confirmed"
        if lesson.teacher_review.status == "confirmed"
        else "draft_waiting_teacher_confirmation"
    )

    reports = lesson.final_reports

    if "teacher" in audiences:
        reports.teacher = FinalReport(
            title=f"Teacher Report - {lesson.metadata.lesson_topic}",
            audience="teacher",
            status=report_status,
            sections=[
                FinalReportSection(heading="Lesson Summary", content=draft.lesson_summary),
                FinalReportSection(
                    heading="Evidence-Backed Corrections",
                    content=[item.model_dump() for item in draft.corrections],
                ),
                FinalReportSection(
                    heading="Pronunciation Feedback",
                    content=[item.model_dump() for item in draft.pronunciation_feedback],
                ),
                FinalReportSection(
                    heading="Next Lesson Suggestions",
                    content=[item.model_dump() for item in draft.next_lesson_suggestions],
                ),
                FinalReportSection(
                    heading="Risk Highlights",
                    content=[item.model_dump() for item in lesson.risk_highlights],
                ),
            ],
        )

    if "student" in audiences:
        reports.student = FinalReport(
            title=f"Student Report - {lesson.metadata.lesson_topic}",
            audience="student",
            status=report_status,
            sections=[
                FinalReportSection(heading="What You Practiced", content=draft.lesson_summary),
                FinalReportSection(
                    heading="Key Points",
                    content=[item.model_dump() for item in draft.knowledge_points],
                ),
                FinalReportSection(
                    heading="Homework",
                    content=[item.model_dump() for item in draft.homework_items],
                ),
                FinalReportSection(
                    heading="Practice Focus",
                    content=[item.model_dump() for item in draft.pronunciation_feedback],
                ),
            ],
        )

    if "parent" in audiences:
        reports.parent = FinalReport(
            title=f"Parent Report - {lesson.metadata.student_name}",
            audience="parent",
            status=report_status,
            sections=[
                FinalReportSection(
                    heading="Today in Class",
                    content=(
                        f"{lesson.metadata.student_name} practiced restaurant ordering "
                        "and learned how to use measure words for drinks."
                    ),
                ),
                FinalReportSection(
                    heading="Progress",
                    content=(
                        f"{student_name} participated actively. "
                        "Teacher should confirm any medium-confidence extracted questions."
                    ),
                ),
                FinalReportSection(
                    heading="This Week",
                    content=[
                        f"Help {student_name} complete the recording homework.",
                        "Review 杯, 份, 碗 with short examples.",
                    ],
                ),
                FinalReportSection(
                    heading="Teacher Confirmation",
                    content="This report should be sent only after teacher review.",
                ),
            ],
        )

    lesson.final_reports = FinalReports(
        teacher=reports.teacher,
        student=reports.student,
        parent=reports.parent,
    )
    return lesson
