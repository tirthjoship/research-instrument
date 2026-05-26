"""Fake RecommendationStorePort implementation for testing."""

from domain.models import (
    AccuracyRecord,
    EvaluationRun,
    StockRecommendation,
    WeeklyReport,
)


class FakeRecommendationStore:
    def __init__(self) -> None:
        self.recommendations: list[StockRecommendation] = []
        self.accuracy_records: list[AccuracyRecord] = []
        self.evaluation_runs: list[EvaluationRun] = []
        self.weekly_reports: dict[str, WeeklyReport] = {}

    def save_recommendation(self, rec: StockRecommendation) -> None:
        self.recommendations.append(rec)

    def get_recommendations(
        self, week_start: str | None = None, symbol: str | None = None
    ) -> list[StockRecommendation]:
        results = self.recommendations
        if week_start is not None:
            results = [r for r in results if r.week_start == week_start]
        if symbol is not None:
            results = [r for r in results if r.symbol == symbol]
        return results

    def save_accuracy_record(self, record: AccuracyRecord) -> None:
        self.accuracy_records.append(record)

    def get_accuracy_records(
        self, week_start: str | None = None, symbol: str | None = None
    ) -> list[AccuracyRecord]:
        results = self.accuracy_records
        if week_start is not None:
            results = [r for r in results if r.week_start == week_start]
        if symbol is not None:
            results = [r for r in results if r.symbol == symbol]
        return results

    def save_evaluation_run(self, run: EvaluationRun) -> None:
        self.evaluation_runs.append(run)

    def get_evaluation_runs(
        self, run_date: str | None = None, eval_type: str | None = None
    ) -> list[EvaluationRun]:
        results = self.evaluation_runs
        if run_date is not None:
            results = [r for r in results if r.run_date == run_date]
        if eval_type is not None:
            results = [r for r in results if r.eval_type == eval_type]
        return results

    def save_weekly_report(self, report: WeeklyReport) -> None:
        self.weekly_reports[report.report_date] = report

    def get_weekly_report(self, report_date: str) -> WeeklyReport | None:
        return self.weekly_reports.get(report_date)
