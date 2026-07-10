const singleForm = document.getElementById("single-form");
const singlePackageName = document.getElementById("single-package-name");
const singleDescription = document.getElementById("single-description");
const singleResult = document.getElementById("single-result");

const batchForm = document.getElementById("batch-form");
const batchStatus = document.getElementById("batch-status");
const taskState = document.getElementById("task-state");
const taskProgressText = document.getElementById("task-progress-text");
const taskProgressBar = document.getElementById("task-progress-bar");
const taskCount = document.getElementById("task-count");
const taskColumn = document.getElementById("task-column");
const taskPackageColumn = document.getElementById("task-package-column");
const taskColumns = document.getElementById("task-columns");
const taskError = document.getElementById("task-error");
const downloadLink = document.getElementById("download-link");

let pollingTimer = null;

singleForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  singleResult.textContent = "分类中...";

  const response = await fetch("/api/classify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      package_name: singlePackageName.value,
      description: singleDescription.value,
    }),
  });

  const data = await response.json();
  singleResult.textContent = data.result || "工具 (Tools) → 系统工具 (System Tools)";
});

batchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  stopPolling();
  resetBatchUI();

  const formData = new FormData(batchForm);
  const response = await fetch("/api/batch", {
    method: "POST",
    body: formData,
  });

  const data = await response.json();
  batchStatus.classList.remove("hidden");

  if (!response.ok) {
    taskState.textContent = "失败";
    taskError.textContent = data.error || "上传失败";
    return;
  }

  renderTask(data);
  startPolling(data.task_id);
});

function startPolling(taskId) {
  pollTask(taskId);
  pollingTimer = setInterval(() => pollTask(taskId), 1200);
}

function stopPolling() {
  if (pollingTimer) {
    clearInterval(pollingTimer);
    pollingTimer = null;
  }
}

async function pollTask(taskId) {
  const response = await fetch(`/api/batch/${taskId}`);
  const data = await response.json();
  renderTask(data);

  if (data.status === "completed" || data.status === "failed") {
    stopPolling();
  }
}

function renderTask(task) {
  taskState.textContent = translateStatus(task.status);
  taskProgressText.textContent = `${task.progress || 0}%`;
  taskProgressBar.style.width = `${task.progress || 0}%`;
  taskCount.textContent = `${task.processed || 0} / ${task.total || 0}`;
  taskColumn.textContent = task.column_name || "-";
  taskPackageColumn.textContent = task.package_column_name || "-";
  taskColumns.textContent = task.preview_columns?.length ? task.preview_columns.join(" | ") : "-";
  taskError.textContent = task.error || "";

  if (task.status === "completed") {
    downloadLink.href = `/api/download/${task.task_id}`;
    downloadLink.classList.remove("hidden");
  } else {
    downloadLink.classList.add("hidden");
  }
}

function resetBatchUI() {
  batchStatus.classList.remove("hidden");
  taskState.textContent = "初始化";
  taskProgressText.textContent = "0%";
  taskProgressBar.style.width = "0%";
  taskCount.textContent = "0 / 0";
  taskColumn.textContent = "-";
  taskPackageColumn.textContent = "-";
  taskColumns.textContent = "-";
  taskError.textContent = "";
  downloadLink.classList.add("hidden");
}

function translateStatus(status) {
  const mapping = {
    queued: "排队中",
    running: "处理中",
    completed: "已完成",
    failed: "失败",
  };
  return mapping[status] || status || "未知";
}
