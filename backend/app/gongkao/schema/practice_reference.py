from datetime import date as calendar_date
from typing import Literal

from pydantic import Field

from backend.app.question_bank_v2.schema.platform_reference import PlatformReportReference
from backend.common.schema import SchemaBase


class LatestReferenceReport(PlatformReportReference):
    record_id: int
    record_title: str
    practiced_at: calendar_date


class ReferenceTrendPoint(SchemaBase):
    date: calendar_date
    total_questions: int = 0
    raw_accuracy_percent: float | None = None
    comparable_questions: int = 0
    reference_coverage_percent: float | None = None
    personal_reference_accuracy_percent: float | None = None
    platform_accuracy_percent: float | None = None
    reference_gap_pp: float | None = None
    rolling_gap_pp: float | None = None
    duplicate_attempts: int = 0
    conflicting_questions: int = 0
    observed_repeat_questions: int = 0
    active_records: int = 0


class ReferenceWindowComparison(SchemaBase):
    status: Literal['insufficient', 'reference_up', 'reference_down', 'uncertain'] = 'insufficient'
    reason: str = '需要前后两个窗口都有足够数据'
    previous_start: calendar_date
    previous_end: calendar_date
    current_start: calendar_date
    current_end: calendar_date
    previous_questions: int = 0
    current_questions: int = 0
    previous_days: int = 0
    current_days: int = 0
    common_cells: int = 0
    previous_support_percent: float | None = None
    current_support_percent: float | None = None
    previous_gap_pp: float | None = None
    current_gap_pp: float | None = None
    change_pp: float | None = None
    interval_low_pp: float | None = None
    interval_high_pp: float | None = None
    bootstrap_samples: int = 0


class GetReferenceTrends(SchemaBase):
    algorithm_version: Literal['external-reference-v1'] = 'external-reference-v1'
    source_platform: Literal['fenbi'] = 'fenbi'
    subject_name: str
    material_type: Literal['exam', 'practice', 'special']
    module_name: str | None = None
    start_date: calendar_date
    end_date: calendar_date
    record_count: int
    eligible_records: int
    excluded_legacy_records: int
    excluded_incomplete_records: int
    modules: list[str] = Field(default_factory=list)
    points: list[ReferenceTrendPoint] = Field(default_factory=list)
    comparison: ReferenceWindowComparison
    latest_report_reference: LatestReferenceReport | None = None
    warnings: list[str] = Field(default_factory=list)
