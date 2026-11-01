"use client";

import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import {
  AlertCircle,
  ArrowUp,
  Check,
  ChevronDown,
  Clock3,
  FlaskConical,
  LoaderCircle,
  Plus,
  Trash2,
} from "lucide-react";
import {
  api,
  type EvaluationCase,
  type EvaluationRun,
  type EvaluationRunDetail,
} from "@/lib/api";

interface CaseDraft {
  query_id: string;
  query: string;
  relevant_chunk_ids: string;
  relevance_grades: string;
  top_k: number;
}

interface EvaluationLabProps {
  knowledgeBaseId: string;
  knowledgeBaseName: string;
}

const metricLabels: Record<string, string> = {
  precision_at_k: "Precision@K",
  recall_at_k: "Recall@K",
  hit_rate_at_k: "HitRate@K",
  mrr_at_k: "MRR@K",
  ndcg_at_k: "nDCG@K",
};

const uuidPattern = /^[\da-f]{8}-(?:[\da-f]{4}-){3}[\da-f]{12}$/i;

function makeCase(index: number): CaseDraft {
  return {
    query_id: `q${index}`,
    query: "",
    relevant_chunk_ids: "",
    relevance_grades: "",
    top_k: 5,
  };
}

function parseIds(value: string): string[] {
  return value
    .split(/[\n,]+/)
    .map((id) => id.trim().toLowerCase())
    .filter(Boolean);
}

function parseGrades(value: string): Record<string, number> | null {
  const entries = value
    .split(/[\n,]+/)
    .map((entry) => entry.trim())
    .filter(Boolean);
  const grades: Record<string, number> = {};

  for (const entry of entries) {
    const [id, gradeText, ...extra] = entry.split("=").map((part) => part.trim());
    if (!id || !gradeText || extra.length > 0 || !/^\d+$/.test(gradeText)) {
      return null;
    }
    const normalizedId = id.toLowerCase();
    if (Object.hasOwn(grades, normalizedId)) return null;
    grades[normalizedId] = Number(gradeText);
  }

  return grades;
}

function validateDataset(
  name: string,
  version: string,
  drafts: CaseDraft[],
): { dataset: { dataset_name: string; dataset_version: string; cases: EvaluationCase[] } | null; error: string | null } {
  const datasetName = name.trim();
  const datasetVersion = version.trim();
  if (!datasetName || datasetName.length > 100) {
    return { dataset: null, error: "Dataset name is required and must be at most 100 characters." };
  }
  if (!datasetVersion || datasetVersion.length > 30) {
    return { dataset: null, error: "Dataset version is required and must be at most 30 characters." };
  }
  if (drafts.length < 1 || drafts.length > 100) {
    return { dataset: null, error: "A dataset must contain between 1 and 100 test cases." };
  }

  const queryIds = drafts.map((draft) => draft.query_id.trim());
  if (queryIds.some((id) => !id || id.length > 100)) {
    return { dataset: null, error: "Each query ID is required and must be at most 100 characters." };
  }
  if (new Set(queryIds).size !== queryIds.length) {
    return { dataset: null, error: "Query IDs must be unique within the dataset." };
  }

  const cases: EvaluationCase[] = [];
  for (const [index, draft] of drafts.entries()) {
    const query = draft.query.trim();
    if (!query || query.length > 10000) {
      return { dataset: null, error: `Test case ${index + 1} needs a query (up to 10,000 characters).` };
    }
    if (!Number.isInteger(draft.top_k) || draft.top_k < 1 || draft.top_k > 20) {
      return { dataset: null, error: `Test case ${index + 1} Top-K must be between 1 and 20.` };
    }

    const relevantIds = parseIds(draft.relevant_chunk_ids);
    if (relevantIds.length === 0) {
      return { dataset: null, error: `Test case ${index + 1} needs at least one relevant chunk UUID.` };
    }
    if (relevantIds.some((id) => !uuidPattern.test(id))) {
      return { dataset: null, error: `Test case ${index + 1} contains a chunk ID that is not a UUID.` };
    }
    if (new Set(relevantIds).size !== relevantIds.length) {
      return { dataset: null, error: `Test case ${index + 1} contains duplicate relevant chunk IDs.` };
    }

    const grades = parseGrades(draft.relevance_grades);
    if (grades === null) {
      return { dataset: null, error: `Test case ${index + 1} relevance grades must use one UUID=0–3 entry per line.` };
    }
    const gradeIds = Object.keys(grades);
    if (gradeIds.some((id) => !uuidPattern.test(id) || !relevantIds.includes(id))) {
      return { dataset: null, error: `Test case ${index + 1} grades may only reference listed relevant chunk UUIDs.` };
    }
    if (Object.values(grades).some((grade) => grade < 0 || grade > 3)) {
      return { dataset: null, error: `Test case ${index + 1} relevance grades must be from 0 to 3.` };
    }
    if (gradeIds.length > 0 && !Object.values(grades).some((grade) => grade > 0)) {
      return { dataset: null, error: `Test case ${index + 1} needs at least one relevance grade greater than zero.` };
    }

    cases.push({
      query_id: draft.query_id.trim(),
      query,
      relevant_chunk_ids: relevantIds,
      relevance_grades: grades,
      top_k: draft.top_k,
    });
  }

  return {
    dataset: {
      dataset_name: datasetName,
      dataset_version: datasetVersion,
      cases,
    },
    error: null,
  };
}

function formatDate(value: string | null): string {
  if (!value) return "Not available";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Not available" : date.toLocaleString();
}

function formatMetric(value: number | undefined): string {
  return value === undefined || !Number.isFinite(value)
    ? "Not returned"
    : `${(value * 100).toFixed(1)}%`;
}

function metricEntries(metrics: Record<string, number>) {
  return Object.entries(metrics).filter(([, value]) => Number.isFinite(value));
}

export function EvaluationLab({
  knowledgeBaseId,
  knowledgeBaseName,
}: EvaluationLabProps) {
  const [datasetName, setDatasetName] = useState("");
  const [datasetVersion, setDatasetVersion] = useState("1.0");
  const [cases, setCases] = useState<CaseDraft[]>([makeCase(1)]);
  const [submitError, setSubmitError] = useState("");
  const [historyError, setHistoryError] = useState("");
  const [success, setSuccess] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [history, setHistory] = useState<EvaluationRun[]>([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [historySkip, setHistorySkip] = useState(0);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [detail, setDetail] = useState<EvaluationRunDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [compareLeft, setCompareLeft] = useState("");
  const [compareRight, setCompareRight] = useState("");
  const submissionInProgress = useRef(false);

  useEffect(() => {
    if (!knowledgeBaseId) return;
    let active = true;
    async function loadHistory() {
      await Promise.resolve();
      if (!active) return;
      setHistoryLoading(true);
      setHistoryError("");
      try {
        const response = await api.evaluationHistory(knowledgeBaseId);
        if (!active) return;
        setHistory(response.items);
        setHistoryTotal(response.total);
        setHistorySkip(response.items.length);
        setCompareLeft(response.items[0]?.id ?? "");
        setCompareRight(response.items[1]?.id ?? "");
      } catch (error: unknown) {
        if (active) {
          setHistoryError(error instanceof Error ? error.message : "Could not load evaluation history.");
        }
      } finally {
        if (active) setHistoryLoading(false);
      }
    }
    void loadHistory();
    return () => {
      active = false;
    };
  }, [knowledgeBaseId]);

  const compareRuns = useMemo(
    () => ({
      left: history.find((run) => run.id === compareLeft),
      right: history.find((run) => run.id === compareRight),
    }),
    [compareLeft, compareRight, history],
  );

  function updateCase(index: number, patch: Partial<CaseDraft>) {
    setCases((current) =>
      current.map((item, itemIndex) =>
        itemIndex === index ? { ...item, ...patch } : item,
      ),
    );
  }

  async function submitDataset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submissionInProgress.current) return;
    setSubmitError("");
    setSuccess("");
    const validation = validateDataset(datasetName, datasetVersion, cases);
    if (!validation.dataset) {
      setSubmitError(validation.error ?? "Check the dataset fields.");
      return;
    }

    submissionInProgress.current = true;
    setSubmitting(true);
    try {
      const run = await api.createEvaluation(knowledgeBaseId, validation.dataset);
      setSuccess(`Evaluation ${run.status}. ${run.completed_queries} of ${run.total_queries} queries completed.`);
      setHistory((current) => [run, ...current.filter((item) => item.id !== run.id)]);
      setHistoryTotal((current) => current + 1);
      setSelectedRunId(run.id);
      setDetailLoading(true);
      setDetailError("");
      try {
        const runDetail = await api.evaluationDetail(knowledgeBaseId, run.id);
        setDetail(runDetail);
      } catch (error) {
        setDetailError(error instanceof Error ? error.message : "Could not load evaluation results.");
      } finally {
        setDetailLoading(false);
      }
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "Could not submit the retrieval evaluation.");
    } finally {
      submissionInProgress.current = false;
      setSubmitting(false);
    }
  }

  async function loadMoreHistory() {
    setHistoryLoading(true);
    setHistoryError("");
    try {
      const response = await api.evaluationHistory(knowledgeBaseId, historySkip);
      setHistory((current) => [...current, ...response.items]);
      setHistorySkip((current) => current + response.items.length);
      setHistoryTotal(response.total);
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : "Could not load more evaluation history.");
    } finally {
      setHistoryLoading(false);
    }
  }

  async function selectRun(run: EvaluationRun) {
    setSelectedRunId(run.id);
    setDetail(null);
    setDetailError("");
    setDetailLoading(true);
    try {
      setDetail(await api.evaluationDetail(knowledgeBaseId, run.id));
    } catch (error) {
      setDetailError(error instanceof Error ? error.message : "Could not load this evaluation run.");
    } finally {
      setDetailLoading(false);
    }
  }

  const compareMetrics = Array.from(
    new Set([
      ...Object.keys(compareRuns.left?.aggregate_metrics ?? {}),
      ...Object.keys(compareRuns.right?.aggregate_metrics ?? {}),
    ]),
  );

  return (
    <div className="space-y-6">
      <header>
        <p className="eyebrow">Retrieval evaluation</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100 sm:text-3xl">
          Evaluation Lab
        </h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
          Measure retrieval ranking against human-verified ground truth. This is
          retrieval evaluation, not LLM answer-quality evaluation.
        </p>
      </header>

      <div className="rounded-lg border border-indigo-400/20 bg-indigo-400/5 p-4 text-sm leading-6 text-slate-300">
        <strong className="font-medium text-indigo-200">Ground-truth guidance:</strong>{" "}
        chunk IDs must come from the selected knowledge base, belong to processed
        documents, and be human-verified. The backend validates chunk membership
        when a run is submitted.
        <span className="mt-1 block text-xs text-slate-500">
          Selected knowledge base: {knowledgeBaseName}
        </span>
      </div>

      {!knowledgeBaseId ? (
        <div className="surface p-8 text-center text-sm text-slate-400">
          Select a knowledge base before editing or running an evaluation dataset.
        </div>
      ) : (
        <>
          <form onSubmit={submitDataset} className="surface space-y-5 p-5 sm:p-6">
            <div className="flex items-start gap-3">
              <span className="rounded-lg bg-indigo-400/10 p-2 text-indigo-300">
                <FlaskConical size={18} />
              </span>
              <div>
                <h2 className="font-semibold text-slate-100">Dataset editor</h2>
                <p className="mt-1 text-xs leading-5 text-slate-500">
                  Dataset metadata: 1–100 characters for the name and 1–30 for the version.
                  A dataset can include up to 100 cases.
                </p>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <label className="space-y-1.5 text-xs font-medium text-slate-300">
                Dataset name
                <input
                  className="field"
                  maxLength={100}
                  required
                  value={datasetName}
                  onChange={(event) => setDatasetName(event.target.value)}
                  placeholder="e.g. Product documentation"
                />
              </label>
              <label className="space-y-1.5 text-xs font-medium text-slate-300">
                Dataset version
                <input
                  className="field"
                  maxLength={30}
                  required
                  value={datasetVersion}
                  onChange={(event) => setDatasetVersion(event.target.value)}
                  placeholder="1.0"
                />
              </label>
            </div>

            <div className="space-y-4">
              {cases.map((item, index) => (
                <section key={index} className="rounded-lg border border-white/8 bg-black/10 p-4">
                  <div className="mb-4 flex items-center justify-between">
                    <h3 className="text-sm font-medium text-slate-200">Test case {index + 1}</h3>
                    <button
                      type="button"
                      disabled={cases.length === 1}
                      onClick={() => setCases((current) => current.filter((_, i) => i !== index))}
                      className="button-secondary border-transparent px-2 text-slate-400 hover:text-red-300"
                      aria-label={`Remove test case ${index + 1}`}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                  <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_120px]">
                    <label className="space-y-1.5 text-xs font-medium text-slate-300">
                      Query ID
                      <input
                        className="field"
                        maxLength={100}
                        value={item.query_id}
                        onChange={(event) => updateCase(index, { query_id: event.target.value })}
                      />
                    </label>
                    <label className="space-y-1.5 text-xs font-medium text-slate-300">
                      Top-K (1–20)
                      <input
                        className="field"
                        type="number"
                        min={1}
                        max={20}
                        step={1}
                        value={item.top_k}
                        onChange={(event) => updateCase(index, { top_k: Number(event.target.value) })}
                      />
                    </label>
                    <label className="space-y-1.5 text-xs font-medium text-slate-300 sm:col-span-2">
                      Query text
                      <textarea
                        className="field min-h-20 resize-y"
                        maxLength={10000}
                        value={item.query}
                        onChange={(event) => updateCase(index, { query: event.target.value })}
                        placeholder="Write the query used to test retrieval."
                      />
                    </label>
                    <label className="space-y-1.5 text-xs font-medium text-slate-300">
                      Relevant chunk UUIDs
                      <textarea
                        className="field min-h-24 resize-y font-mono text-xs"
                        value={item.relevant_chunk_ids}
                        onChange={(event) => updateCase(index, { relevant_chunk_ids: event.target.value })}
                        placeholder={"One UUID per line, or comma-separated"}
                      />
                    </label>
                    <label className="space-y-1.5 text-xs font-medium text-slate-300">
                      Optional relevance grades
                      <textarea
                        className="field min-h-24 resize-y font-mono text-xs"
                        value={item.relevance_grades}
                        onChange={(event) => updateCase(index, { relevance_grades: event.target.value })}
                        placeholder={"UUID=0..3, one per line"}
                      />
                    </label>
                  </div>
                </section>
              ))}
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3">
              <button
                type="button"
                disabled={cases.length >= 100}
                onClick={() => setCases((current) => [...current, makeCase(current.length + 1)])}
                className="button-secondary"
              >
                <Plus size={15} /> Add test case
              </button>
              <button
                type="submit"
                disabled={submitting || !knowledgeBaseId}
                className="button-primary"
              >
                {submitting ? <LoaderCircle size={16} className="animate-spin" /> : <FlaskConical size={16} />}
                {submitting ? "Running evaluation…" : "Run retrieval evaluation"}
              </button>
            </div>

            {submitError && (
              <p role="alert" className="flex items-start gap-2 rounded-lg border border-red-400/20 bg-red-400/5 p-3 text-sm text-red-200">
                <AlertCircle size={16} className="mt-0.5 shrink-0" />
                <span>{submitError}</span>
              </p>
            )}
            {success && (
              <p role="status" className="flex items-start gap-2 rounded-lg border border-emerald-400/20 bg-emerald-400/5 p-3 text-sm text-emerald-200">
                <Check size={16} className="mt-0.5 shrink-0" />
                <span>{success}</span>
              </p>
            )}
          </form>

          <section className="surface p-5 sm:p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="font-semibold text-slate-100">Historical runs</h2>
                <p className="mt-1 text-xs text-slate-500">
                  {historyTotal} run{historyTotal === 1 ? "" : "s"} for this knowledge base
                </p>
              </div>
              {historyLoading && <LoaderCircle size={16} className="animate-spin text-slate-400" />}
            </div>

            {historyError && (
              <p role="alert" className="mt-4 rounded-lg border border-red-400/20 bg-red-400/5 p-3 text-sm text-red-200">
                {historyError}
              </p>
            )}

            {history.length === 0 && !historyLoading ? (
              <div className="mt-5 rounded-lg border border-dashed border-white/10 p-8 text-center">
                <p className="text-sm font-medium text-slate-300">No evaluation runs yet</p>
                <p className="mt-1 text-xs text-slate-500">Submit a human-verified dataset to measure retrieval.</p>
              </div>
            ) : (
              <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
                <div className="space-y-2">
                  {history.map((run) => (
                    <button
                      key={run.id}
                      type="button"
                      onClick={() => void selectRun(run)}
                      className={`w-full rounded-lg border p-3 text-left transition-colors ${
                        selectedRunId === run.id
                          ? "border-indigo-400/30 bg-indigo-400/8"
                          : "border-white/8 bg-black/10 hover:bg-white/4"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-sm font-medium text-slate-200">
                          {run.dataset_name} <span className="text-slate-500">v{run.dataset_version}</span>
                        </span>
                        <span className="shrink-0 rounded-full bg-white/6 px-2 py-1 text-[10px] uppercase tracking-wide text-slate-300">
                          {run.status}
                        </span>
                      </div>
                      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-500">
                        <span>{run.completed_queries} / {run.total_queries} queries</span>
                        <span>{formatDate(run.started_at)}</span>
                        {run.duration_ms !== null && <span>{run.duration_ms} ms</span>}
                      </div>
                      {run.total_queries > 0 && (
                        <div
                          className="mt-2 h-1 overflow-hidden rounded-full bg-white/8"
                          aria-label={`${Math.round((run.completed_queries / run.total_queries) * 100)}% complete`}
                        >
                          <div
                            className="h-full rounded-full bg-indigo-400"
                            style={{ width: `${Math.min(100, (run.completed_queries / run.total_queries) * 100)}%` }}
                          />
                        </div>
                      )}
                    </button>
                  ))}
                  {historySkip < historyTotal && (
                    <button
                      type="button"
                      onClick={() => void loadMoreHistory()}
                      disabled={historyLoading}
                      className="button-secondary w-full"
                    >
                      Load more runs
                    </button>
                  )}
                </div>

                <div className="min-w-0">
                  {detailLoading ? (
                    <div className="flex min-h-36 items-center justify-center gap-2 text-sm text-slate-400">
                      <LoaderCircle size={16} className="animate-spin" /> Loading run detail…
                    </div>
                  ) : detailError ? (
                    <p role="alert" className="rounded-lg border border-red-400/20 bg-red-400/5 p-3 text-sm text-red-200">
                      {detailError}
                    </p>
                  ) : detail ? (
                    <RunDetail detail={detail} />
                  ) : (
                    <div className="flex min-h-36 items-center justify-center rounded-lg border border-dashed border-white/10 text-sm text-slate-500">
                      Select a run to inspect its real metrics and query results.
                    </div>
                  )}
                </div>
              </div>
            )}

            {history.length > 1 && (
              <div className="mt-6 border-t border-white/8 pt-5">
                <div className="mb-4 flex items-center gap-2">
                  <ArrowUp size={15} className="text-indigo-300" />
                  <h3 className="text-sm font-medium text-slate-200">Compare historical runs</h3>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="space-y-1.5 text-xs text-slate-400">
                    Earlier run
                    <select className="field" value={compareLeft} onChange={(event) => setCompareLeft(event.target.value)}>
                      <option value="">Select a run</option>
                      {history.map((run) => <option key={run.id} value={run.id}>{run.dataset_name} v{run.dataset_version} · {formatDate(run.started_at)}</option>)}
                    </select>
                  </label>
                  <label className="space-y-1.5 text-xs text-slate-400">
                    Comparison run
                    <select className="field" value={compareRight} onChange={(event) => setCompareRight(event.target.value)}>
                      <option value="">Select a run</option>
                      {history.map((run) => <option key={run.id} value={run.id}>{run.dataset_name} v{run.dataset_version} · {formatDate(run.started_at)}</option>)}
                    </select>
                  </label>
                </div>
                {compareRuns.left && compareRuns.right ? (
                  <div className="mt-4 overflow-x-auto">
                    <table className="w-full min-w-[440px] text-left text-xs">
                      <thead className="text-slate-500">
                        <tr className="border-b border-white/8">
                          <th className="py-2 font-medium">Metric</th>
                          <th className="py-2 font-medium">{compareRuns.left.dataset_name}</th>
                          <th className="py-2 font-medium">{compareRuns.right.dataset_name}</th>
                          <th className="py-2 font-medium">Change</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/6">
                        {compareMetrics.map((metric) => {
                          const left = compareRuns.left?.aggregate_metrics[metric];
                          const right = compareRuns.right?.aggregate_metrics[metric];
                          const delta = left !== undefined && right !== undefined ? right - left : undefined;
                          return (
                            <tr key={metric}>
                              <td className="py-2.5 text-slate-300">{metricLabels[metric] ?? metric}</td>
                              <td className="py-2.5 text-slate-400">{formatMetric(left)}</td>
                              <td className="py-2.5 text-slate-200">{formatMetric(right)}</td>
                              <td className={`py-2.5 ${delta === undefined ? "text-slate-500" : delta >= 0 ? "text-emerald-300" : "text-red-300"}`}>
                                {delta === undefined ? "Not returned" : `${delta >= 0 ? "+" : ""}${(delta * 100).toFixed(1)} pp`}
                              </td>
                            </tr>
                          );
                        })}
                        {compareMetrics.length === 0 && (
                          <tr><td colSpan={4} className="py-4 text-center text-slate-500">No aggregate metrics were returned for these runs.</td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="mt-3 text-xs text-slate-500">Choose two runs with metrics to compare their API-reported values.</p>
                )}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}

function RunDetail({ detail }: { detail: EvaluationRunDetail }) {
  const metricRows = metricEntries(detail.aggregate_metrics);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-100">
            {detail.dataset_name} <span className="text-slate-500">v{detail.dataset_version}</span>
          </p>
          <p className="mt-1 flex items-center gap-1.5 text-[11px] text-slate-500">
            <Clock3 size={12} /> Started {formatDate(detail.started_at)}
          </p>
          {detail.completed_at && (
            <p className="mt-1 text-[11px] text-slate-500">Completed {formatDate(detail.completed_at)}</p>
          )}
        </div>
        <span className="rounded-full bg-white/6 px-2.5 py-1 text-[10px] uppercase tracking-wide text-slate-300">
          {detail.status}
        </span>
      </div>

      {detail.total_queries > 0 && (
        <div>
          <div className="mb-1.5 flex justify-between text-[11px] text-slate-500">
            <span>Query progress</span>
            <span>{detail.completed_queries} / {detail.total_queries}</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-white/8">
            <div
              className="h-full rounded-full bg-indigo-400"
              style={{ width: `${Math.min(100, (detail.completed_queries / detail.total_queries) * 100)}%` }}
            />
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {metricRows.map(([name, value]) => (
          <div key={name} className="rounded-lg border border-white/8 bg-black/10 p-3">
            <p className="text-[10px] text-slate-500">{metricLabels[name] ?? name}</p>
            <p className="mt-1 text-lg font-semibold tabular-nums text-slate-100">{formatMetric(value)}</p>
          </div>
        ))}
        {metricRows.length === 0 && (
          <p className="col-span-full rounded-lg border border-dashed border-white/10 p-4 text-xs text-slate-500">
            No aggregate metrics were returned for this run.
          </p>
        )}
      </div>

      <div className="flex flex-wrap gap-3 text-[11px] text-slate-500">
        <span>{detail.results.length} query result{detail.results.length === 1 ? "" : "s"} returned</span>
        {detail.duration_ms !== null && <span>{detail.duration_ms} ms total</span>}
      </div>

      <div className="space-y-3">
        {detail.results.map((result) => {
          const relevant = new Set(result.relevant_chunk_ids);
          const retrieved = new Set(result.retrieved_chunk_ids);
          const allIds = Array.from(new Set([...result.retrieved_chunk_ids, ...result.relevant_chunk_ids]));
          const retrievedDetails = new Map(result.retrieved_results.map((item) => [item.chunk_id, item]));
          const resultMetrics = metricEntries(result.metrics);

          return (
            <details key={result.id} className="group rounded-lg border border-white/8 bg-black/10">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 p-3">
                <span className="min-w-0">
                  <span className="block truncate text-xs font-medium text-slate-200">{result.query_id} · {result.query}</span>
                  <span className="mt-1 block text-[10px] text-slate-500">
                    Top {result.top_k} · {result.duration_ms} ms · {result.retrieved_chunk_ids.length} retrieved
                  </span>
                </span>
                <ChevronDown size={15} className="shrink-0 text-slate-500 transition-transform group-open:rotate-180" />
              </summary>
              <div className="border-t border-white/8 p-3">
                <div className="flex flex-wrap gap-2">
                  {resultMetrics.map(([name, value]) => (
                    <span key={name} className="rounded-md bg-white/5 px-2 py-1 text-[10px] text-slate-300">
                      {metricLabels[name] ?? name}: {formatMetric(value)}
                    </span>
                  ))}
                </div>
                {allIds.length === 0 ? (
                  <p className="mt-3 text-xs text-slate-500">No relevant or retrieved chunks were returned.</p>
                ) : (
                  <div className="mt-3 space-y-2">
                    {allIds.map((id) => {
                      const chunk = retrievedDetails.get(id);
                      return (
                        <div key={id} className="rounded-md border border-white/6 p-2.5">
                          <div className="flex flex-wrap items-center gap-2">
                            {retrieved.has(id) && <span className="rounded bg-indigo-400/10 px-1.5 py-0.5 text-[9px] text-indigo-200">Retrieved</span>}
                            {relevant.has(id) && <span className="rounded bg-emerald-400/10 px-1.5 py-0.5 text-[9px] text-emerald-200">Relevant</span>}
                            <code className="break-all text-[10px] text-slate-400">{id}</code>
                          </div>
                          {chunk && (
                            <p className="mt-1.5 text-[10px] text-slate-500">
                              {chunk.filename} · Chunk {chunk.chunk_index} · Similarity {chunk.score.toFixed(4)}
                            </p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </details>
          );
        })}
      </div>
    </div>
  );
}
