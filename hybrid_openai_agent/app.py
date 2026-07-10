from __future__ import annotations

import os
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
from flask import Flask, jsonify, render_template, request, send_file

from classifier import HybridClassifier


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv"}
DEFAULT_TEXT_COLUMNS = (
    "description",
    "app_description",
    "desc",
    "简介",
    "描述",
    "应用描述",
)

app = Flask(__name__)
classifier = HybridClassifier()


@dataclass
class BatchTask:
    task_id: str
    filename: str
    status: str = "queued"
    progress: int = 0
    total: int = 0
    processed: int = 0
    result_file: str | None = None
    error: str | None = None
    column_name: str | None = None
    preview_columns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "filename": self.filename,
            "status": self.status,
            "progress": self.progress,
            "total": self.total,
            "processed": self.processed,
            "result_file": self.result_file,
            "error": self.error,
            "column_name": self.column_name,
            "preview_columns": self.preview_columns,
        }


TASKS: dict[str, BatchTask] = {}
TASK_LOCK = threading.Lock()


def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def detect_text_column(frame: pd.DataFrame) -> str:
    columns = [str(column) for column in frame.columns]
    lowered = {column.lower(): column for column in columns}

    for candidate in DEFAULT_TEXT_COLUMNS:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]

    for column in columns:
        series = frame[column].dropna().astype(str).head(20)
        if not series.empty and series.str.len().mean() >= 12:
            return column

    return columns[0]


def read_table(file_path: Path) -> pd.DataFrame:
    if file_path.suffix.lower() == ".csv":
        return pd.read_csv(file_path)
    return pd.read_excel(file_path)


def update_task(task_id: str, **kwargs: Any) -> None:
    with TASK_LOCK:
        task = TASKS[task_id]
        for key, value in kwargs.items():
            setattr(task, key, value)


def process_batch(task_id: str, file_path: Path, column_name: str | None) -> None:
    try:
        update_task(task_id, status="running", progress=2)
        frame = read_table(file_path)
        preview_columns = [str(column) for column in frame.columns]
        selected_column = column_name or detect_text_column(frame)

        if selected_column not in frame.columns:
            raise ValueError(f"列名不存在: {selected_column}")

        total = len(frame.index)
        update_task(
            task_id,
            total=total,
            preview_columns=preview_columns,
            column_name=selected_column,
            progress=5,
        )

        category_results: list[str] = []
        decision_sources: list[str] = []
        model_used_list: list[str] = []
        rule_path_list: list[str] = []
        reasons: list[str] = []

        for index, value in enumerate(frame[selected_column].fillna("").astype(str), start=1):
            result = classifier.classify(value)
            category_results.append(result.category_path)
            decision_sources.append(result.source)
            model_used_list.append(result.model_used or "")
            rule_path_list.append(result.rule_path)
            reasons.append(result.reason)
            progress = min(95, int(index / max(total, 1) * 100))
            update_task(task_id, processed=index, progress=progress)

        frame["category_result"] = category_results
        frame["decision_source"] = decision_sources
        frame["model_used"] = model_used_list
        frame["rule_path"] = rule_path_list
        frame["decision_reason"] = reasons

        output_name = f"{task_id}_classified.xlsx"
        output_path = OUTPUT_DIR / output_name
        frame.to_excel(output_path, index=False)

        update_task(
            task_id,
            status="completed",
            progress=100,
            processed=total,
            result_file=output_name,
        )
    except Exception as exc:  # noqa: BLE001
        update_task(task_id, status="failed", error=str(exc), progress=100)


@app.get("/")
def index():
    return render_template(
        "index.html",
        openai_model=os.environ.get("OPENAI_MODEL", "gpt-5.4-mini"),
        llm_enabled=os.environ.get(
            "ENABLE_LLM_PRIMARY",
            os.environ.get("ENABLE_LLM_FALLBACK", "true"),
        ).lower() == "true",
        api_key_present=bool(os.environ.get("OPENAI_API_KEY", "").strip()),
    )


@app.post("/api/classify")
def classify_single():
    payload = request.get_json(silent=True) or {}
    description = str(payload.get("description", ""))
    result = classifier.classify(description)
    return jsonify(
        {
            "result": result.category_path,
            "source": result.source,
            "model_used": result.model_used,
            "rule_path": result.rule_path,
            "reason": result.reason,
        }
    )


@app.post("/api/batch")
def classify_batch():
    upload = request.files.get("file")
    column_name = (request.form.get("column_name") or "").strip() or None

    if upload is None or not upload.filename:
        return jsonify({"error": "请上传文件。"}), 400

    if not allowed_file(upload.filename):
        return jsonify({"error": "仅支持 xlsx、xls、csv 文件。"}), 400

    task_id = uuid.uuid4().hex
    saved_name = f"{task_id}{Path(upload.filename).suffix.lower()}"
    saved_path = UPLOAD_DIR / saved_name
    upload.save(saved_path)

    task = BatchTask(task_id=task_id, filename=upload.filename, column_name=column_name)
    with TASK_LOCK:
        TASKS[task_id] = task

    worker = threading.Thread(target=process_batch, args=(task_id, saved_path, column_name), daemon=True)
    worker.start()

    return jsonify(task.to_dict())


@app.get("/api/batch/<task_id>")
def batch_status(task_id: str):
    with TASK_LOCK:
        task = TASKS.get(task_id)
        if task is None:
            return jsonify({"error": "任务不存在。"}), 404
        return jsonify(task.to_dict())


@app.get("/api/download/<task_id>")
def download_result(task_id: str):
    with TASK_LOCK:
        task = TASKS.get(task_id)
        if task is None:
            return jsonify({"error": "任务不存在。"}), 404
        if task.status != "completed" or not task.result_file:
            return jsonify({"error": "结果尚未生成。"}), 400
        output_path = OUTPUT_DIR / task.result_file

    return send_file(
        output_path,
        as_attachment=True,
        download_name=f"classified_{task.filename.rsplit('.', 1)[0]}.xlsx",
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))
    app.run(host="0.0.0.0", port=port, debug=True)
