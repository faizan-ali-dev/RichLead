import { authFetch } from "./api";

const sleep = (milliseconds) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));

function requestKey() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return `job-${Date.now()}-${Math.random().toString(36).slice(2, 14)}`;
}

async function readJson(response) {
  return response.json().catch(() => ({}));
}

export async function waitForBackgroundJob(jobId, { onStatus, timeoutMs = 20 * 60 * 1000 } = {}) {
  const startedAt = Date.now();
  let delayMs = 1000;

  while (Date.now() - startedAt < timeoutMs) {
    const response = await authFetch(`/api/jobs/${jobId}/`);
    const job = await readJson(response);
    if (!response.ok) throw new Error(job.error || "Could not read background job status.");
    onStatus?.(job);

    if (job.status === "succeeded") return job.result || {};
    if (job.status === "failed") throw new Error(job.error || "Background task failed.");

    await sleep(delayMs);
    delayMs = Math.min(Math.round(delayMs * 1.5), 5000);
  }

  throw new Error(`This task is still running. Job ID: ${jobId}`);
}

export async function submitBackgroundJob(path, payload, { onStatus } = {}) {
  const idempotencyKey = requestKey();
  const options = {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey,
    },
    body: JSON.stringify(payload),
  };

  let response;
  try {
    response = await authFetch(path, options);
  } catch {
    // Retry the enqueue once with the same key. If the server accepted the
    // first request but its response was lost, the API returns that same job.
    await sleep(300);
    response = await authFetch(path, options);
  }

  const job = await readJson(response);
  if (!response.ok) throw new Error(job.error || "Could not queue this task.");
  if (job.status === "failed") throw new Error(job.error || "Background task failed.");
  if (job.status === "succeeded") return job.result || {};
  if (!job.job_id) throw new Error("The server did not return a job ID.");
  onStatus?.(job);
  return waitForBackgroundJob(job.job_id, { onStatus });
}
