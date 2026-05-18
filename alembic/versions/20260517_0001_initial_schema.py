"""initial schema

Revision ID: 20260517_0001
Revises:
Create Date: 2026-05-17 17:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260517_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("task_kind", sa.String(length=32), nullable=False),
        sa.Column("task_key", sa.String(length=64), nullable=False),
        sa.Column("task_display_name", sa.String(length=255), nullable=False),
        sa.Column("task_description", sa.Text(), nullable=True),
        sa.Column("input_schema_json", sa.JSON(), nullable=False),
        sa.Column("output_schema_json", sa.JSON(), nullable=False),
        sa.Column("default_metric_config_json", sa.JSON(), nullable=False),
        sa.Column("task_definition_json", sa.JSON(), nullable=False),
        sa.Column("report_profile_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "artifacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_type", sa.String(length=64), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("relative_path", sa.String(length=512), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_artifacts_owner_id"), "artifacts", ["owner_id"], unique=False)
    op.create_index(op.f("ix_artifacts_owner_type"), "artifacts", ["owner_type"], unique=False)
    op.create_table(
        "datasets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("schema_json", sa.JSON(), nullable=False),
        sa.Column("command", sa.Text(), nullable=True),
        sa.Column("generation_model", sa.String(length=128), nullable=True),
        sa.Column("parent_dataset_id", sa.Integer(), nullable=True),
        sa.Column("quality_summary_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["parent_dataset_id"], ["datasets.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_datasets_project_id"), "datasets", ["project_id"], unique=False)
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("locked_by", sa.String(length=128), nullable=True),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(op.f("ix_jobs_job_type"), "jobs", ["job_type"], unique=False)
    op.create_index(op.f("ix_jobs_target_id"), "jobs", ["target_id"], unique=False)
    op.create_table(
        "prompts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_template", sa.Text(), nullable=False),
        sa.Column("output_schema_json", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "name", "version", name="uq_prompt_version"),
    )
    op.create_index(op.f("ix_prompts_project_id"), "prompts", ["project_id"], unique=False)
    op.create_table(
        "run_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_type", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("data_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_run_logs_run_id"), "run_logs", ["run_id"], unique=False)
    op.create_index(op.f("ix_run_logs_run_type"), "run_logs", ["run_type"], unique=False)
    op.create_table(
        "dataset_examples",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("split", sa.String(length=32), nullable=False),
        sa.Column("input_json", sa.JSON(), nullable=False),
        sa.Column("expected_output_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("quality_status", sa.String(length=32), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dataset_examples_dataset_id"), "dataset_examples", ["dataset_id"], unique=False)
    op.create_index("ix_dataset_examples_dataset_content_hash", "dataset_examples", ["dataset_id", "content_hash"], unique=False)
    op.create_index("ix_dataset_examples_dataset_quality", "dataset_examples", ["dataset_id", "quality_status"], unique=False)
    op.create_index("ix_dataset_examples_dataset_split", "dataset_examples", ["dataset_id", "split"], unique=False)
    op.create_table(
        "evaluations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("prompt_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("metric_config_json", sa.JSON(), nullable=False),
        sa.Column("model_config_json", sa.JSON(), nullable=False),
        sa.Column("prompt_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("dataset_split_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("package_versions_json", sa.JSON(), nullable=False),
        sa.Column("random_seed", sa.Integer(), nullable=True),
        sa.Column("artifact_dir", sa.String(length=512), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["prompt_id"], ["prompts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_evaluations_dataset_id"), "evaluations", ["dataset_id"], unique=False)
    op.create_index(op.f("ix_evaluations_project_id"), "evaluations", ["project_id"], unique=False)
    op.create_index(op.f("ix_evaluations_prompt_id"), "evaluations", ["prompt_id"], unique=False)
    op.create_table(
        "optimization_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("prompt_id", sa.Integer(), nullable=False),
        sa.Column("optimizer_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("baseline_score", sa.Float(), nullable=True),
        sa.Column("optimized_score", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("artifact_dir", sa.String(length=512), nullable=True),
        sa.Column("prompt_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("dataset_split_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("model_config_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("optimizer_config_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("metric_config_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("package_versions_json", sa.JSON(), nullable=False),
        sa.Column("random_seed", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["prompt_id"], ["prompts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_optimization_runs_dataset_id"), "optimization_runs", ["dataset_id"], unique=False)
    op.create_index(op.f("ix_optimization_runs_project_id"), "optimization_runs", ["project_id"], unique=False)
    op.create_index(op.f("ix_optimization_runs_prompt_id"), "optimization_runs", ["prompt_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_optimization_runs_prompt_id"), table_name="optimization_runs")
    op.drop_index(op.f("ix_optimization_runs_project_id"), table_name="optimization_runs")
    op.drop_index(op.f("ix_optimization_runs_dataset_id"), table_name="optimization_runs")
    op.drop_table("optimization_runs")
    op.drop_index(op.f("ix_evaluations_prompt_id"), table_name="evaluations")
    op.drop_index(op.f("ix_evaluations_project_id"), table_name="evaluations")
    op.drop_index(op.f("ix_evaluations_dataset_id"), table_name="evaluations")
    op.drop_table("evaluations")
    op.drop_index("ix_dataset_examples_dataset_split", table_name="dataset_examples")
    op.drop_index("ix_dataset_examples_dataset_quality", table_name="dataset_examples")
    op.drop_index("ix_dataset_examples_dataset_content_hash", table_name="dataset_examples")
    op.drop_index(op.f("ix_dataset_examples_dataset_id"), table_name="dataset_examples")
    op.drop_table("dataset_examples")
    op.drop_index(op.f("ix_run_logs_run_type"), table_name="run_logs")
    op.drop_index(op.f("ix_run_logs_run_id"), table_name="run_logs")
    op.drop_table("run_logs")
    op.drop_index(op.f("ix_prompts_project_id"), table_name="prompts")
    op.drop_table("prompts")
    op.drop_index(op.f("ix_jobs_target_id"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_job_type"), table_name="jobs")
    op.drop_table("jobs")
    op.drop_index(op.f("ix_datasets_project_id"), table_name="datasets")
    op.drop_table("datasets")
    op.drop_index(op.f("ix_artifacts_owner_type"), table_name="artifacts")
    op.drop_index(op.f("ix_artifacts_owner_id"), table_name="artifacts")
    op.drop_table("artifacts")
    op.drop_table("projects")
