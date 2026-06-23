"""add model quality evaluation runs"""

from alembic import op
import sqlalchemy as sa

revision = "0002_evaluation_runs"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("company_id", sa.String(length=36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("triggered_by_id", sa.String(length=36), sa.ForeignKey("users.id")),
        sa.Column("dataset_name", sa.String(length=255), nullable=False),
        sa.Column("dataset_version", sa.String(length=64), nullable=False),
        sa.Column("scoring_policy_version", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("quality_status", sa.String(length=50)),
        sa.Column("total_cases", sa.Integer(), nullable=False),
        sa.Column("strong_pass_rate", sa.Float(), nullable=False),
        sa.Column("weak_rejection_rate", sa.Float(), nullable=False),
        sa.Column("average_score_separation", sa.Float(), nullable=False),
        sa.Column("minimum_score_separation", sa.Float(), nullable=False),
        sa.Column("false_negative_count", sa.Integer(), nullable=False),
        sa.Column("false_positive_count", sa.Integer(), nullable=False),
        sa.Column("regression_count", sa.Integer(), nullable=False),
        sa.Column("baseline_run_id", sa.String(length=36), sa.ForeignKey("evaluation_runs.id")),
        sa.Column("error_message", sa.Text()),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    for column in [
        "company_id",
        "triggered_by_id",
        "dataset_name",
        "dataset_version",
        "scoring_policy_version",
        "status",
        "quality_status",
        "baseline_run_id",
        "completed_at",
    ]:
        op.create_index(f"ix_evaluation_runs_{column}", "evaluation_runs", [column])

    op.create_table(
        "evaluation_case_results",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("evaluation_run_id", sa.String(length=36), sa.ForeignKey("evaluation_runs.id"), nullable=False),
        sa.Column("case_key", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=255), nullable=False),
        sa.Column("skill_category", sa.String(length=100), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("min_passing_score", sa.Float(), nullable=False),
        sa.Column("strong_score", sa.Float(), nullable=False),
        sa.Column("weak_score", sa.Float(), nullable=False),
        sa.Column("strong_passes", sa.Boolean(), nullable=False),
        sa.Column("weak_passes", sa.Boolean(), nullable=False),
        sa.Column("score_separation", sa.Float(), nullable=False),
        sa.Column("regression_detected", sa.Boolean(), nullable=False),
        sa.Column("regression_reason", sa.Text()),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    for column in [
        "evaluation_run_id",
        "case_key",
        "role",
        "skill_category",
        "regression_detected",
    ]:
        op.create_index(
            f"ix_evaluation_case_results_{column}",
            "evaluation_case_results",
            [column],
        )


def downgrade() -> None:
    op.drop_table("evaluation_case_results")
    op.drop_table("evaluation_runs")
