"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import {
  Activity,
  AlertCircle,
  Bot,
  BookOpen,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Clock3,
  Database,
  FileText,
  FlaskConical,
  LayoutDashboard,
  LoaderCircle,
  LogOut,
  Menu,
  MessageSquareText,
  Plus,
  RefreshCw,
  Search,
  Server,
  Settings2,
  ShieldCheck,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { EvaluationLab } from "@/components/evaluation-lab";
import {
  api,
  clearToken,
  getToken,
  setToken,
  type Document,
  type HealthCheck,
  type KnowledgeBase,
  type ProcessingRun,
  type QueryResponse,
  type User,
} from "@/lib/api";

type View = "overview" | "knowledge" | "documents" | "playground" | "evaluation";

interface NavigationItem {
  id: View;
  label: string;
  icon: typeof LayoutDashboard;
}

interface HealthState {
  data: HealthCheck | null;
  loading: boolean;
  error: string | null;
}

interface BaseModalState {
  mode: "create" | "edit";
  base?: KnowledgeBase;
}

const navigation: NavigationItem[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "knowledge", label: "Knowledge Bases", icon: Database },
  { id: "documents", label: "Documents", icon: FileText },
  { id: "playground", label: "RAG Playground", icon: MessageSquareText },
  { id: "evaluation", label: "Evaluation Lab", icon: FlaskConical },
];

const DOCUMENT_BATCH_SIZE = 100;
const DOCUMENTS_PER_PAGE = 20;

async function fetchAllDocuments(knowledgeBaseId: string): Promise<Document[]> {
  const allDocuments: Document[] = [];
  let skip = 0;

  while (true) {
    const batch = await api.listDocuments(knowledgeBaseId, skip, DOCUMENT_BATCH_SIZE);
    allDocuments.push(...batch);
    if (batch.length < DOCUMENT_BATCH_SIZE) return allDocuments;
    skip += batch.length;
  }
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "Not available";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Not available" : date.toLocaleString();
}

function StatusBadge({ value }: { value: string }) {
  const normalized = value.toLowerCase();
  const tone =
    ["processed", "completed", "success", "healthy", "ready"].includes(normalized)
      ? "border-emerald-400/20 bg-emerald-400/8 text-emerald-300"
      : ["failed", "error", "not_ready", "unhealthy"].includes(normalized)
        ? "border-red-400/20 bg-red-400/8 text-red-300"
        : "border-amber-400/20 bg-amber-400/8 text-amber-200";

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-medium capitalize ${tone}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {value.replaceAll("_", " ")}
    </span>
  );
}

function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: typeof Database;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-dashed border-white/10 px-5 py-12 text-center">
      <Icon size={25} className="mx-auto text-slate-500" />
      <p className="mt-3 text-sm font-medium text-slate-200">{title}</p>
      <p className="mt-1 text-xs text-slate-500">{description}</p>
      {action && <div className="mt-5 flex justify-center">{action}</div>}
    </div>
  );
}

function AuthScreen({ onLogin }: { onLogin: (user: User) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (mode === "register") await api.register(email, password);
      const token = await api.login(email, password);
      setToken(token.access_token);
      onLogin(await api.me());
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Authentication failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden px-5 py-12">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_50%_0%,rgba(99,102,241,0.12),transparent_48%)]" />
      <div className="relative w-full max-w-md">
        <div className="mb-8 flex items-center justify-center gap-3">
          <div className="rounded-xl border border-indigo-300/15 bg-indigo-400/10 p-3 text-indigo-300">
            <Bot size={23} />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-white">RAGForge</h1>
            <p className="mt-0.5 text-xs text-slate-500">Retrieval engineering workspace</p>
          </div>
        </div>

        <section className="surface p-7 sm:p-8">
          <p className="eyebrow">{mode === "login" ? "Welcome back" : "Get started"}</p>
          <h2 className="mt-2 text-xl font-semibold text-slate-100">
            {mode === "login" ? "Sign in to your workspace" : "Create your account"}
          </h2>
          <p className="mt-1 text-sm leading-6 text-slate-400">
            {mode === "login"
              ? "Access your knowledge bases, documents, and retrieval tools."
              : "Register to begin building and evaluating your knowledge base."}
          </p>
          <form onSubmit={submit} className="mt-6 space-y-4">
            <label className="block space-y-1.5 text-xs font-medium text-slate-300">
              Email address
              <input
                className="field"
                required
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@example.com"
              />
            </label>
            <label className="block space-y-1.5 text-xs font-medium text-slate-300">
              Password
              <input
                className="field"
                required
                minLength={mode === "register" ? 12 : 1}
                type="password"
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder={mode === "register" ? "At least 12 characters" : "Your password"}
              />
            </label>
            {error && (
              <p role="alert" className="rounded-lg border border-red-400/20 bg-red-400/5 p-3 text-sm text-red-200">
                {error}
              </p>
            )}
            <button type="submit" disabled={busy} className="button-primary w-full py-3">
              {busy && <LoaderCircle size={16} className="animate-spin" />}
              {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
            </button>
          </form>
          <p className="mt-5 text-center text-xs text-slate-500">
            {mode === "login" ? "New to RAGForge?" : "Already have an account?"}{" "}
            <button
              type="button"
              onClick={() => {
                setMode(mode === "login" ? "register" : "login");
                setError("");
              }}
              className="font-medium text-indigo-300 hover:text-indigo-200"
            >
              {mode === "login" ? "Create an account" : "Sign in"}
            </button>
          </p>
        </section>
      </div>
    </main>
  );
}

function ProcessingHistory({
  knowledgeBaseId,
  document,
}: {
  knowledgeBaseId: string;
  document: Document;
}) {
  const [open, setOpen] = useState(false);
  const [runs, setRuns] = useState<ProcessingRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);

  async function toggle() {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    if (loaded) return;
    setLoading(true);
    setError("");
    try {
      setRuns(await api.processingRuns(knowledgeBaseId, document.id));
      setLoaded(true);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not load processing history.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => void toggle()}
        className="inline-flex items-center gap-1 text-[11px] font-medium text-indigo-300 hover:text-indigo-200"
        aria-expanded={open}
      >
        <Clock3 size={12} /> Processing history
        <ChevronDown size={12} className={open ? "rotate-180 transition-transform" : "transition-transform"} />
      </button>
      {open && (
        <div className="mt-3 rounded-lg border border-white/8 bg-black/15 p-3">
          {loading && <p className="flex items-center gap-2 text-xs text-slate-400"><LoaderCircle size={13} className="animate-spin" /> Loading processing attempts…</p>}
          {error && <p role="alert" className="text-xs text-red-300">{error}</p>}
          {!loading && !error && runs.length === 0 && (
            <p className="text-xs text-slate-500">No processing attempts were returned for this document.</p>
          )}
          <div className="space-y-3">
            {runs.map((run) => (
              <article key={run.id} className="border-b border-white/6 pb-3 last:border-0 last:pb-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-medium text-slate-200">Attempt {run.attempt_number}</span>
                  <StatusBadge value={run.status} />
                  {run.current_stage && <span className="text-[11px] text-slate-400">Stage: {run.current_stage}</span>}
                </div>
                <div className="mt-2 grid gap-x-4 gap-y-1 text-[10px] text-slate-500 sm:grid-cols-2">
                  <span>Started: {formatDate(run.started_at)}</span>
                  <span>Completed: {formatDate(run.completed_at)}</span>
                  <span>Duration: {run.duration_ms === null ? "Not available" : `${run.duration_ms} ms`}</span>
                  <span>Pages: {run.page_count ?? "Not available"}</span>
                  <span>Chunks: {run.chunk_count ?? "Not available"}</span>
                  <span>Embeddings: {run.embedding_count ?? "Not available"}</span>
                </div>
                {Object.keys(run.stage_timings_ms).length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {Object.entries(run.stage_timings_ms).map(([stage, duration]) => (
                      <span key={stage} className="rounded bg-white/5 px-2 py-1 text-[10px] text-slate-400">
                        {stage}: {duration} ms
                      </span>
                    ))}
                  </div>
                )}
                {(run.error_stage || run.error_message) && (
                  <p className="mt-2 rounded-md border border-red-400/15 bg-red-400/5 p-2 text-[11px] leading-5 text-red-200">
                    {run.error_stage && <strong>Error stage: {run.error_stage}. </strong>}
                    {run.error_message || "No safe error message was returned."}
                  </p>
                )}
              </article>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function Workspace() {
  const [user, setUser] = useState<User | null>(null);
  const [authChecking, setAuthChecking] = useState(true);
  const [view, setView] = useState<View>("overview");
  const [bases, setBases] = useState<KnowledgeBase[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [documents, setDocuments] = useState<Document[]>([]);
  const [documentLoading, setDocumentLoading] = useState(false);
  const [documentError, setDocumentError] = useState("");
  const [baseLoading, setBaseLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [baseModal, setBaseModal] = useState<BaseModalState | null>(null);
  const [baseName, setBaseName] = useState("");
  const [baseDescription, setBaseDescription] = useState("");
  const [baseSaving, setBaseSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [documentPage, setDocumentPage] = useState(0);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [queryResult, setQueryResult] = useState<QueryResponse | null>(null);
  const [queryLoading, setQueryLoading] = useState(false);
  const [queryError, setQueryError] = useState("");
  const [expandedChunk, setExpandedChunk] = useState<string | null>(null);
  const [apiHealth, setApiHealth] = useState<HealthState>({ data: null, loading: false, error: null });
  const [dbHealth, setDbHealth] = useState<HealthState>({ data: null, loading: false, error: null });
  const selectedIdRef = useRef(selectedId);

  const selectedBase = bases.find((base) => base.id === selectedId) ?? null;
  const currentPageLabel = navigation.find((item) => item.id === view)?.label ?? "Overview";

  useEffect(() => {
    selectedIdRef.current = selectedId;
  }, [selectedId]);

  useEffect(() => {
    let active = true;
    async function checkSession() {
      if (!getToken()) {
        if (active) setAuthChecking(false);
        return;
      }
      try {
        const currentUser = await api.me();
        if (active) setUser(currentUser);
      } catch {
        clearToken();
      } finally {
        if (active) setAuthChecking(false);
      }
    }
    void checkSession();
    return () => {
      active = false;
    };
  }, []);

  const refreshBases = useCallback(async () => {
    const data = await api.listBases();
    setBases(data);
    setSelectedId((current) =>
      data.some((base) => base.id === current) ? current : (data[0]?.id ?? ""),
    );
  }, []);

  function changeKnowledgeBase(id: string) {
    setSelectedId(id);
    setDocuments([]);
    setDocumentPage(0);
    setDocumentError("");
    setQueryResult(null);
    setQueryError("");
    setExpandedChunk(null);
  }

  const refreshHealth = useCallback(async () => {
    setApiHealth((current) => ({ ...current, loading: true, error: null }));
    setDbHealth((current) => ({ ...current, loading: true, error: null }));
    const [healthResult, readinessResult] = await Promise.allSettled([
      api.health(),
      api.readiness(),
    ]);
    if (healthResult.status === "fulfilled") {
      setApiHealth({ data: healthResult.value, loading: false, error: null });
    } else {
      setApiHealth({
        data: null,
        loading: false,
        error: healthResult.reason instanceof Error ? healthResult.reason.message : "API health check failed.",
      });
    }
    if (readinessResult.status === "fulfilled") {
      setDbHealth({ data: readinessResult.value, loading: false, error: null });
    } else {
      setDbHealth({
        data: null,
        loading: false,
        error: readinessResult.reason instanceof Error ? readinessResult.reason.message : "Database readiness check failed.",
      });
    }
  }, []);

  useEffect(() => {
    if (!user) return;
    let active = true;
    async function loadWorkspace() {
      await Promise.resolve();
      if (!active) return;
      setBaseLoading(true);
      setError("");
      try {
        await refreshBases();
      } catch (requestError: unknown) {
        if (active) setError(requestError instanceof Error ? requestError.message : "Could not load knowledge bases.");
      } finally {
        if (active) setBaseLoading(false);
      }
    }
    void loadWorkspace();
    void Promise.resolve().then(refreshHealth);
    return () => {
      active = false;
    };
  }, [user, refreshBases, refreshHealth]);

  useEffect(() => {
    let active = true;
    if (!user || !selectedId) {
      return () => {
        active = false;
      };
    }
    async function loadDocuments() {
      await Promise.resolve();
      if (!active) return;
      setDocumentLoading(true);
      setDocumentError("");
      try {
        const data = await fetchAllDocuments(selectedId);
        if (active && selectedIdRef.current === selectedId) setDocuments(data);
      } catch (requestError: unknown) {
        if (!active) return;
        const message = requestError instanceof Error ? requestError.message : "Could not load documents.";
        setDocumentError(message);
      } finally {
        if (active) setDocumentLoading(false);
      }
    }
    void loadDocuments();
    return () => {
      active = false;
    };
  }, [user, selectedId]);

  function openBaseModal(mode: "create" | "edit", base?: KnowledgeBase) {
    setBaseName(base?.name ?? "");
    setBaseDescription(base?.description ?? "");
    setBaseModal({ mode, base });
  }

  async function saveBase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!baseName.trim()) return;
    setBaseSaving(true);
    setError("");
    try {
      const description = baseDescription.trim() || null;
      if (baseModal?.mode === "edit" && baseModal.base) {
        const updated = await api.updateBase(baseModal.base.id, {
          name: baseName.trim(),
          description,
        });
        setBases((current) => current.map((base) => base.id === updated.id ? updated : base));
        setNotice("Knowledge base updated.");
      } else {
        const created = await api.createBase({ name: baseName.trim(), description });
        setBases((current) => [created, ...current]);
        changeKnowledgeBase(created.id);
        setView("knowledge");
        setNotice("Knowledge base created.");
      }
      setBaseModal(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not save knowledge base.");
    } finally {
      setBaseSaving(false);
    }
  }

  async function deleteBase(base: KnowledgeBase) {
    if (!window.confirm(`Delete "${base.name}" and its associated documents? This cannot be undone.`)) return;
    setError("");
    try {
      await api.deleteBase(base.id);
      const remaining = bases.filter((item) => item.id !== base.id);
      setBases(remaining);
      if (selectedId === base.id) {
        changeKnowledgeBase(remaining[0]?.id ?? "");
      }
      setNotice("Knowledge base deleted.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not delete knowledge base.");
    }
  }

  async function refreshDocuments() {
    if (!selectedId) return;
    setDocumentLoading(true);
    setDocumentError("");
    try {
      const data = await fetchAllDocuments(selectedId);
      if (selectedIdRef.current === selectedId) setDocuments(data);
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : "Could not load documents.";
      setDocumentError(message);
    } finally {
      setDocumentLoading(false);
    }
  }

  async function uploadFiles(files: FileList | null) {
    if (!files || !selectedId) return;
    const selectedFiles = Array.from(files);
    const uploaded: string[] = [];
    const failures: string[] = [];
    setDocumentPage(0);
    setUploading(true);
    setError("");
    for (const file of selectedFiles) {
      if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
        failures.push(`${file.name}: only PDF files are supported.`);
        continue;
      }
      try {
        await api.uploadDocument(selectedId, file);
        uploaded.push(file.name);
      } catch (requestError) {
        failures.push(`${file.name}: ${requestError instanceof Error ? requestError.message : "Upload failed."}`);
      }
    }
    await refreshDocuments();
    setUploading(false);
    if (uploaded.length > 0) {
      setNotice(`${uploaded.length} PDF${uploaded.length === 1 ? "" : "s"} uploaded. Processing may take some time.`);
    }
    if (failures.length > 0) setError(failures.join(" "));
  }

  async function deleteDocument(document: Document) {
    if (!selectedId || !window.confirm(`Delete "${document.filename}"?`)) return;
    setError("");
    try {
      await api.deleteDocument(selectedId, document.id);
      setDocuments((current) => current.filter((item) => item.id !== document.id));
      setDocumentPage(0);
      setNotice("Document deleted.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not delete document.");
    }
  }

  async function runQuery(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedId || !query.trim()) return;
    setQueryLoading(true);
    setQueryError("");
    setQueryResult(null);
    setExpandedChunk(null);
    try {
      setQueryResult(await api.query(selectedId, query.trim(), topK));
    } catch (requestError) {
      setQueryError(requestError instanceof Error ? requestError.message : "Query failed.");
    } finally {
      setQueryLoading(false);
    }
  }

  function logout() {
    clearToken();
    setUser(null);
    setBases([]);
    setDocuments([]);
    setSelectedId("");
    setQueryResult(null);
    setQueryError("");
  }

  if (authChecking) {
    return (
      <div className="flex min-h-screen items-center justify-center gap-2 text-sm text-slate-400">
        <LoaderCircle size={16} className="animate-spin" /> Checking session…
      </div>
    );
  }
  if (!user) return <AuthScreen onLogin={setUser} />;

  const sortedBases = [...bases].sort(
    (left, right) => new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime(),
  );
  const documentPages = Math.max(1, Math.ceil(documents.length / DOCUMENTS_PER_PAGE));
  const visibleDocuments = documents.slice(
    documentPage * DOCUMENTS_PER_PAGE,
    (documentPage + 1) * DOCUMENTS_PER_PAGE,
  );

  function selectView(nextView: View) {
    setView(nextView);
    setMobileMenuOpen(false);
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[252px] flex-col border-r border-white/8 bg-[#111319] lg:flex">
        <Brand />
        <WorkspaceNavigation view={view} onNavigate={selectView} />
        <div className="px-4 pt-7">
          <div className="mb-2 flex items-center justify-between px-3">
            <p className="eyebrow">Knowledge bases</p>
            <button
              type="button"
              aria-label="Create knowledge base"
              onClick={() => openBaseModal("create")}
              className="rounded-md p-1 text-slate-500 hover:bg-white/6 hover:text-slate-200"
            >
              <Plus size={15} />
            </button>
          </div>
          <div className="max-h-60 space-y-1 overflow-y-auto">
            {bases.slice(0, 8).map((base) => (
              <button
                key={base.id}
                type="button"
                onClick={() => {
                  changeKnowledgeBase(base.id);
                  selectView("documents");
                }}
                className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs transition-colors ${
                  selectedId === base.id ? "bg-indigo-400/10 text-indigo-200" : "text-slate-400 hover:bg-white/4 hover:text-slate-200"
                }`}
              >
                <Database size={14} className="shrink-0" />
                <span className="truncate">{base.name}</span>
              </button>
            ))}
            {!baseLoading && bases.length === 0 && (
              <p className="px-3 py-2 text-xs text-slate-500">No knowledge bases yet.</p>
            )}
          </div>
        </div>
        <div className="mt-auto border-t border-white/8 p-4">
          <div className="flex items-center gap-3 rounded-lg bg-white/[0.03] p-3">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-indigo-400/10 text-xs font-semibold text-indigo-200">
              {user.email[0]?.toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-medium text-slate-200">{user.email}</p>
              <p className="mt-0.5 text-[10px] text-slate-500">Workspace member</p>
            </div>
            <button type="button" aria-label="Sign out" onClick={logout} className="text-slate-500 hover:text-red-300">
              <LogOut size={15} />
            </button>
          </div>
        </div>
      </aside>

      <div className="lg:pl-[252px]">
        <header className="sticky top-0 z-20 border-b border-white/8 bg-[#14161c]/95 backdrop-blur">
          <div className="flex h-14 items-center justify-between px-4 sm:px-7">
            <div className="flex items-center gap-3">
              <button
                type="button"
                aria-label="Toggle navigation"
                aria-expanded={mobileMenuOpen}
                onClick={() => setMobileMenuOpen((open) => !open)}
                className="rounded-md p-2 text-slate-400 hover:bg-white/5 lg:hidden"
              >
                {mobileMenuOpen ? <X size={17} /> : <Menu size={17} />}
              </button>
              <span className="hidden text-xs text-slate-500 sm:inline">Workspace</span>
              <ChevronRight size={13} className="hidden text-slate-600 sm:block" />
              <span className="text-sm font-medium text-slate-200">{currentPageLabel}</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="hidden max-w-48 truncate text-xs text-slate-500 md:inline">{user.email}</span>
              <span className="hidden items-center gap-1.5 text-[11px] text-slate-400 sm:inline-flex">
                <span className={`size-1.5 rounded-full ${apiHealth.data ? "bg-emerald-400" : apiHealth.loading ? "bg-amber-300" : "bg-slate-500"}`} />
                {apiHealth.data?.status ?? (apiHealth.loading ? "Checking API" : "API unknown")}
              </span>
              <button type="button" title="Sign out" onClick={logout} className="p-1 text-slate-500 hover:text-red-300 lg:hidden">
                <LogOut size={16} />
              </button>
            </div>
          </div>
          <nav className="flex gap-1 overflow-x-auto px-3 pb-2 lg:hidden" aria-label="Workspace sections">
            {navigation.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  type="button"
                  key={item.id}
                  onClick={() => selectView(item.id)}
                  className={`flex shrink-0 items-center gap-2 rounded-md px-3 py-2 text-xs ${
                    view === item.id ? "bg-indigo-400/10 text-indigo-200" : "text-slate-400 hover:bg-white/4"
                  }`}
                >
                  <Icon size={14} /> {item.label}
                </button>
              );
            })}
          </nav>
          {mobileMenuOpen && (
            <div className="border-t border-white/8 px-3 py-2 lg:hidden">
              <WorkspaceNavigation view={view} onNavigate={selectView} />
              <div className="mt-2 border-t border-white/8 pt-2">
                {bases.map((base) => (
                  <button
                    type="button"
                    key={base.id}
                    onClick={() => {
                      changeKnowledgeBase(base.id);
                      selectView("documents");
                    }}
                    className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-xs text-slate-400 hover:bg-white/4"
                  >
                    <Database size={13} /> {base.name}
                  </button>
                ))}
              </div>
            </div>
          )}
        </header>

        <main className="mx-auto max-w-[1480px] space-y-5 px-4 py-6 sm:px-7 sm:py-8">
          {(error || notice) && (
            <div
              role={error ? "alert" : "status"}
              className={`flex items-start justify-between gap-4 rounded-lg border p-3 text-sm ${
                error
                  ? "border-red-400/20 bg-red-400/5 text-red-200"
                  : "border-emerald-400/20 bg-emerald-400/5 text-emerald-200"
              }`}
            >
              <span className="flex items-start gap-2">
                {error ? <AlertCircle size={16} className="mt-0.5 shrink-0" /> : <Check size={16} className="mt-0.5 shrink-0" />}
                {error || notice}
              </span>
              <button type="button" aria-label="Dismiss message" onClick={() => { setError(""); setNotice(""); }}>
                <X size={15} />
              </button>
            </div>
          )}

          {view === "overview" && (
            <Overview
              bases={sortedBases}
              documents={documents}
              selectedBase={selectedBase}
              selectedId={selectedId}
              documentLoading={documentLoading}
              documentError={documentError}
              apiHealth={apiHealth}
              dbHealth={dbHealth}
              onRefreshHealth={() => void refreshHealth()}
              onCreateBase={() => openBaseModal("create")}
              onNavigate={selectView}
              onSelectBase={(id) => {
              changeKnowledgeBase(id);
                selectView("documents");
              }}
            />
          )}

          {view === "knowledge" && (
            <KnowledgeBases
              bases={sortedBases}
              selectedId={selectedId}
              baseLoading={baseLoading}
              onSelect={changeKnowledgeBase}
              onOpen={(id) => {
                changeKnowledgeBase(id);
                selectView("documents");
              }}
              onCreate={() => openBaseModal("create")}
              onEdit={(base) => openBaseModal("edit", base)}
              onDelete={(base) => void deleteBase(base)}
            />
          )}

          {view === "documents" && (
            <Documents
              bases={bases}
              selectedId={selectedId}
              documents={visibleDocuments}
              totalDocuments={documents.length}
              page={documentPage}
              pageCount={documentPages}
              loading={documentLoading}
              loadError={documentError}
              uploading={uploading}
              onSelectBase={changeKnowledgeBase}
              onUpload={(files) => void uploadFiles(files)}
              onRefresh={() => void refreshDocuments()}
              onDelete={(document) => void deleteDocument(document)}
              onPageChange={setDocumentPage}
              onCreateBase={() => openBaseModal("create")}
            />
          )}

          {view === "playground" && (
            <Playground
              bases={bases}
              selectedId={selectedId}
              selectedBase={selectedBase}
              query={query}
              topK={topK}
              result={queryResult}
              loading={queryLoading}
              error={queryError}
              expandedChunk={expandedChunk}
              onSelectBase={changeKnowledgeBase}
              onQueryChange={setQuery}
              onTopKChange={setTopK}
              onSubmit={(event) => void runQuery(event)}
              onExpandChunk={setExpandedChunk}
            />
          )}

          {view === "evaluation" && (
            <EvaluationLab
              key={selectedId}
              knowledgeBaseId={selectedId}
              knowledgeBaseName={selectedBase?.name ?? "None selected"}
            />
          )}
        </main>
      </div>

      {baseModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-4 backdrop-blur-sm"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !baseSaving) setBaseModal(null);
          }}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="knowledge-base-dialog-title"
            className="surface w-full max-w-lg p-5 sm:p-6"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="eyebrow">{baseModal.mode === "create" ? "New collection" : "Collection settings"}</p>
                <h2 id="knowledge-base-dialog-title" className="mt-1 text-lg font-semibold text-slate-100">
                  {baseModal.mode === "create" ? "Create knowledge base" : "Edit knowledge base"}
                </h2>
              </div>
              <button
                type="button"
                aria-label="Close dialog"
                disabled={baseSaving}
                onClick={() => setBaseModal(null)}
                className="rounded-md p-1 text-slate-500 hover:bg-white/5 hover:text-slate-200"
              >
                <X size={17} />
              </button>
            </div>
            <form onSubmit={(event) => void saveBase(event)} className="mt-5 space-y-4">
              <label className="block space-y-1.5 text-xs font-medium text-slate-300">
                Name
                <input
                  autoFocus
                  className="field"
                  required
                  minLength={1}
                  maxLength={150}
                  value={baseName}
                  onChange={(event) => setBaseName(event.target.value)}
                  placeholder="e.g. Research papers"
                />
              </label>
              <label className="block space-y-1.5 text-xs font-medium text-slate-300">
                Description <span className="font-normal text-slate-500">(optional)</span>
                <textarea
                  className="field min-h-24 resize-y"
                  value={baseDescription}
                  onChange={(event) => setBaseDescription(event.target.value)}
                  placeholder="Describe the contents of this knowledge base."
                />
              </label>
              <div className="flex justify-end gap-2 pt-1">
                <button type="button" disabled={baseSaving} onClick={() => setBaseModal(null)} className="button-secondary">
                  Cancel
                </button>
                <button type="submit" disabled={baseSaving || !baseName.trim()} className="button-primary">
                  {baseSaving && <LoaderCircle size={15} className="animate-spin" />}
                  {baseSaving ? "Saving…" : baseModal.mode === "create" ? "Create knowledge base" : "Save changes"}
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}

function Brand() {
  return (
    <div className="flex h-16 items-center gap-3 border-b border-white/8 px-5">
      <div className="rounded-lg border border-indigo-300/15 bg-indigo-400/10 p-2 text-indigo-300">
        <Bot size={19} />
      </div>
      <div>
        <p className="text-sm font-semibold tracking-tight text-slate-100">RAGForge</p>
        <p className="mt-0.5 text-[9px] font-medium uppercase tracking-[0.16em] text-slate-500">Retrieval workspace</p>
      </div>
    </div>
  );
}

function WorkspaceNavigation({
  view,
  onNavigate,
}: {
  view: View;
  onNavigate: (view: View) => void;
}) {
  return (
    <div className="px-3 pt-5">
      <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-600">Workspace</p>
      <nav className="space-y-1" aria-label="Workspace">
        {navigation.map((item) => {
          const Icon = item.icon;
          return (
            <button
              type="button"
              key={item.id}
              onClick={() => onNavigate(item.id)}
              aria-current={view === item.id ? "page" : undefined}
              className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-xs transition-colors ${
                view === item.id
                  ? "bg-indigo-400/10 font-medium text-indigo-200"
                  : "text-slate-400 hover:bg-white/4 hover:text-slate-200"
              }`}
            >
              <Icon size={16} /> {item.label}
              {view === item.id && <span className="ml-auto size-1.5 rounded-full bg-indigo-300" />}
            </button>
          );
        })}
      </nav>
    </div>
  );
}

function Overview({
  bases,
  documents,
  selectedBase,
  selectedId,
  documentLoading,
  documentError,
  apiHealth,
  dbHealth,
  onRefreshHealth,
  onCreateBase,
  onNavigate,
  onSelectBase,
}: {
  bases: KnowledgeBase[];
  documents: Document[];
  selectedBase: KnowledgeBase | null;
  selectedId: string;
  documentLoading: boolean;
  documentError: string;
  apiHealth: HealthState;
  dbHealth: HealthState;
  onRefreshHealth: () => void;
  onCreateBase: () => void;
  onNavigate: (view: View) => void;
  onSelectBase: (id: string) => void;
}) {
  const statuses = documents.reduce<Record<string, number>>((counts, document) => {
    counts[document.status] = (counts[document.status] ?? 0) + 1;
    return counts;
  }, {});
  const processedCount = documents.filter((document) =>
    ["processed", "completed", "success"].includes(document.status.toLowerCase()),
  ).length;
  const recentDocuments = [...documents]
    .sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime())
    .slice(0, 5);
  const displayedDocumentCount = !selectedId
    ? "—"
    : documentLoading
      ? "…"
      : documentError
        ? "Unavailable"
        : documents.length;

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="eyebrow">Your workspace</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100 sm:text-3xl">Overview</h1>
          <p className="mt-2 text-sm text-slate-400">
            Knowledge, ingestion, retrieval, and evaluation in one place.
          </p>
        </div>
        <button type="button" onClick={onCreateBase} className="button-primary self-start sm:self-auto">
          <Plus size={15} /> New knowledge base
        </button>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <MetricCard label="Knowledge bases" value={bases.length} detail="Your collections" icon={Database} />
        <MetricCard
          label="Documents"
          value={displayedDocumentCount}
          detail={selectedBase ? `In ${selectedBase.name}` : "Select a knowledge base"}
          icon={FileText}
        />
        <MetricCard
          label="Processed"
          value={
            !selectedId ? "—" : documentLoading ? "…" : documentError ? "Unavailable" : processedCount
          }
          detail="In selected knowledge base"
          icon={ShieldCheck}
        />
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(300px,0.8fr)]">
        <section className="surface min-w-0">
          <div className="flex items-center justify-between gap-3 border-b border-white/8 px-5 py-4">
            <div>
              <h2 className="text-sm font-semibold text-slate-100">Knowledge bases</h2>
              <p className="mt-1 text-xs text-slate-500">Most recently updated collections</p>
            </div>
            <button type="button" onClick={() => onNavigate("knowledge")} className="text-xs text-indigo-300 hover:text-indigo-200">
              View all
            </button>
          </div>
          {bases.length === 0 ? (
            <div className="p-5">
              <EmptyState
                icon={Database}
                title="No knowledge bases yet"
                description="Create a knowledge base to begin adding source documents."
              />
            </div>
          ) : (
            <div className="divide-y divide-white/6">
              {bases.slice(0, 5).map((base) => (
                <button
                  type="button"
                  key={base.id}
                  onClick={() => onSelectBase(base.id)}
                  className="flex w-full items-center justify-between gap-4 px-5 py-3.5 text-left hover:bg-white/[0.025]"
                >
                  <span className="flex min-w-0 items-center gap-3">
                    <span className="rounded-lg bg-white/5 p-2 text-slate-400"><Database size={15} /></span>
                    <span className="min-w-0">
                      <span className="block truncate text-xs font-medium text-slate-200">{base.name}</span>
                      <span className="mt-1 block truncate text-[11px] text-slate-500">{base.description || "No description"}</span>
                    </span>
                  </span>
                  <span className="shrink-0 text-[10px] text-slate-500">{formatDate(base.updated_at)}</span>
                </button>
              ))}
            </div>
          )}
        </section>

        <section className="surface p-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity size={16} className="text-slate-400" />
              <h2 className="text-sm font-semibold text-slate-100">Service health</h2>
            </div>
            <button type="button" aria-label="Refresh health checks" onClick={onRefreshHealth} className="rounded-md p-1.5 text-slate-500 hover:bg-white/5 hover:text-slate-200">
              <RefreshCw size={14} />
            </button>
          </div>
          <div className="mt-4 divide-y divide-white/6">
            <HealthRow label="API" icon={Server} health={apiHealth} />
            <HealthRow label="Database" icon={Database} health={dbHealth} />
          </div>
          <p className="mt-4 text-[10px] leading-5 text-slate-600">
            Live checks from <code>/health</code> and <code>/health/ready</code>. A failed request is shown as unavailable, not healthy.
          </p>
        </section>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <section className="surface min-w-0">
          <div className="flex items-center justify-between border-b border-white/8 px-5 py-4">
            <div>
              <h2 className="text-sm font-semibold text-slate-100">Document status</h2>
              <p className="mt-1 text-xs text-slate-500">
                {selectedBase ? `In ${selectedBase.name}` : "Select a knowledge base to see status counts"}
              </p>
            </div>
            {selectedBase && <button type="button" onClick={() => onNavigate("documents")} className="text-xs text-indigo-300">View documents</button>}
          </div>
          <div className="p-5">
            {!selectedId ? (
              <p className="text-sm text-slate-500">Document status is unavailable until a knowledge base is selected.</p>
            ) : documentLoading ? (
              <p className="flex items-center gap-2 text-sm text-slate-400"><LoaderCircle size={15} className="animate-spin" /> Loading document statuses…</p>
            ) : documentError ? (
              <p className="flex items-start gap-2 text-sm text-amber-200"><CircleHelp size={15} className="mt-0.5 shrink-0" /> Status counts unavailable: {documentError}</p>
            ) : documents.length === 0 ? (
              <p className="text-sm text-slate-500">No documents are present in this knowledge base.</p>
            ) : (
              <div className="space-y-3">
                {Object.entries(statuses).map(([status, count]) => (
                  <div key={status}>
                    <div className="mb-1.5 flex justify-between text-xs">
                      <span className="capitalize text-slate-300">{status.replaceAll("_", " ")}</span>
                      <span className="tabular-nums text-slate-500">{count}</span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-white/6">
                      <div className="h-full rounded-full bg-indigo-400/75" style={{ width: `${(count / documents.length) * 100}%` }} />
                    </div>
                  </div>
                ))}
                <p className="pt-1 text-[10px] text-slate-600">Counts are derived from the documents returned by the API.</p>
              </div>
            )}
          </div>
        </section>

        <section className="surface min-w-0">
          <div className="flex items-center justify-between border-b border-white/8 px-5 py-4">
            <div>
              <h2 className="text-sm font-semibold text-slate-100">Recent documents</h2>
              <p className="mt-1 text-xs text-slate-500">{selectedBase?.name ?? "Selected knowledge base"}</p>
            </div>
            {selectedBase && <button type="button" onClick={() => onNavigate("documents")} className="text-xs text-indigo-300">Browse</button>}
          </div>
          {!selectedId ? (
            <p className="p-5 text-sm text-slate-500">Select a knowledge base to see its documents.</p>
          ) : documentLoading ? (
            <p className="flex items-center gap-2 p-5 text-sm text-slate-400"><LoaderCircle size={15} className="animate-spin" /> Loading recent documents…</p>
          ) : documentError ? (
            <p className="p-5 text-sm text-amber-200">Recent documents unavailable.</p>
          ) : recentDocuments.length === 0 ? (
            <p className="p-5 text-sm text-slate-500">No documents uploaded yet.</p>
          ) : (
            <div className="divide-y divide-white/6">
              {recentDocuments.map((document) => (
                <div key={document.id} className="flex items-center justify-between gap-3 px-5 py-3">
                  <span className="flex min-w-0 items-center gap-2.5">
                    <FileText size={15} className="shrink-0 text-slate-500" />
                    <span className="min-w-0">
                      <span className="block truncate text-xs font-medium text-slate-300">{document.filename}</span>
                      <span className="mt-1 block text-[10px] text-slate-600">{formatDate(document.created_at)}</span>
                    </span>
                  </span>
                  <StatusBadge value={document.status} />
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  detail,
  icon: Icon,
}: {
  label: string;
  value: string | number;
  detail: string;
  icon: typeof Database;
}) {
  return (
    <div className="surface p-4 sm:p-5">
      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-400">{label}</span>
        <Icon size={16} className="text-slate-500" />
      </div>
      <p className="mt-4 text-2xl font-semibold tracking-tight tabular-nums text-slate-100">{value}</p>
      <p className="mt-1 truncate text-[10px] text-slate-600">{detail}</p>
    </div>
  );
}

function HealthRow({
  label,
  icon: Icon,
  health,
}: {
  label: string;
  icon: typeof Server;
  health: HealthState;
}) {
  return (
    <div className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
      <span className="flex items-center gap-2 text-xs text-slate-300">
        <Icon size={14} className="text-slate-500" /> {label}
      </span>
      {health.loading ? (
        <span className="flex items-center gap-1.5 text-[10px] text-slate-500"><LoaderCircle size={12} className="animate-spin" /> Checking</span>
      ) : health.error ? (
        <span className="max-w-[65%] truncate text-right text-[10px] text-amber-200" title={health.error}>Unavailable</span>
      ) : health.data ? (
        <span className="flex items-center gap-2">
          <StatusBadge value={health.data.status} />
          {health.data.database && <span className="text-[10px] text-slate-500">{health.data.database}</span>}
        </span>
      ) : (
        <span className="text-[10px] text-slate-500">Not checked</span>
      )}
    </div>
  );
}

function KnowledgeBases({
  bases,
  selectedId,
  baseLoading,
  onSelect,
  onOpen,
  onCreate,
  onEdit,
  onDelete,
}: {
  bases: KnowledgeBase[];
  selectedId: string;
  baseLoading: boolean;
  onSelect: (id: string) => void;
  onOpen: (id: string) => void;
  onCreate: () => void;
  onEdit: (base: KnowledgeBase) => void;
  onDelete: (base: KnowledgeBase) => void;
}) {
  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="eyebrow">Organize your sources</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100 sm:text-3xl">Knowledge Bases</h1>
          <p className="mt-2 text-sm text-slate-400">Create collections for documents, retrieval, and evaluation.</p>
        </div>
        <button type="button" onClick={onCreate} className="button-primary self-start sm:self-auto">
          <Plus size={15} /> Create knowledge base
        </button>
      </div>
      {baseLoading ? (
        <div className="surface flex items-center justify-center gap-2 p-12 text-sm text-slate-400"><LoaderCircle size={16} className="animate-spin" /> Loading knowledge bases…</div>
      ) : bases.length === 0 ? (
        <section className="surface p-5">
          <EmptyState icon={Database} title="No knowledge bases" description="Create your first knowledge base to get started." action={<button type="button" onClick={onCreate} className="button-primary"><Plus size={15} /> Create knowledge base</button>} />
        </section>
      ) : (
        <section className="surface overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left">
              <thead className="border-b border-white/8 bg-white/[0.02] text-[10px] uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-5 py-3 font-medium">Name</th>
                  <th className="px-5 py-3 font-medium">Description</th>
                  <th className="px-5 py-3 font-medium">Created</th>
                  <th className="px-5 py-3 font-medium">Updated</th>
                  <th className="px-5 py-3 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/6">
                {bases.map((base) => (
                  <tr key={base.id} className={selectedId === base.id ? "bg-indigo-400/[0.025]" : ""}>
                    <td className="px-5 py-4">
                      <button type="button" onClick={() => onSelect(base.id)} className="flex items-center gap-2 text-left text-xs font-medium text-slate-200 hover:text-indigo-200">
                        <Database size={14} className="text-indigo-300" /> {base.name}
                      </button>
                    </td>
                    <td className="max-w-64 truncate px-5 py-4 text-xs text-slate-500">{base.description || "No description"}</td>
                    <td className="px-5 py-4 text-[11px] text-slate-500">{formatDate(base.created_at)}</td>
                    <td className="px-5 py-4 text-[11px] text-slate-500">{formatDate(base.updated_at)}</td>
                    <td className="px-5 py-4">
                      <div className="flex justify-end gap-1">
                        <button type="button" title={`Open ${base.name} documents`} onClick={() => onOpen(base.id)} className="rounded-md p-2 text-slate-500 hover:bg-white/5 hover:text-indigo-200"><BookOpen size={14} /></button>
                        <button type="button" title="Edit knowledge base" onClick={() => onEdit(base)} className="rounded-md p-2 text-slate-500 hover:bg-white/5 hover:text-slate-200"><Settings2 size={14} /></button>
                        <button type="button" title="Delete knowledge base" onClick={() => onDelete(base)} className="rounded-md p-2 text-slate-500 hover:bg-red-400/8 hover:text-red-300"><Trash2 size={14} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="border-t border-white/8 px-5 py-3 text-[10px] text-slate-600">{bases.length} knowledge base{bases.length === 1 ? "" : "s"}</div>
        </section>
      )}
    </div>
  );
}

function Documents({
  bases,
  selectedId,
  documents,
  totalDocuments,
  page,
  pageCount,
  loading,
  loadError,
  uploading,
  onSelectBase,
  onUpload,
  onRefresh,
  onDelete,
  onPageChange,
  onCreateBase,
}: {
  bases: KnowledgeBase[];
  selectedId: string;
  documents: Document[];
  totalDocuments: number;
  page: number;
  pageCount: number;
  loading: boolean;
  loadError: string;
  uploading: boolean;
  onSelectBase: (id: string) => void;
  onUpload: (files: FileList | null) => void;
  onRefresh: () => void;
  onDelete: (document: Document) => void;
  onPageChange: (page: number) => void;
  onCreateBase: () => void;
}) {
  const start = totalDocuments === 0 ? 0 : page * DOCUMENTS_PER_PAGE + 1;
  const end = Math.min((page + 1) * DOCUMENTS_PER_PAGE, totalDocuments);
  const selectedBase = bases.find((base) => base.id === selectedId);

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="eyebrow">Ingestion and processing</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100 sm:text-3xl">Documents</h1>
          <p className="mt-2 text-sm text-slate-400">Upload PDFs, inspect their status, and review processing attempts.</p>
        </div>
        <label className={`button-primary self-start sm:self-auto ${!selectedId || uploading ? "pointer-events-none opacity-45" : ""}`}>
          {uploading ? <LoaderCircle size={15} className="animate-spin" /> : <Upload size={15} />}
          {uploading ? "Uploading…" : "Upload PDFs"}
          <input
            type="file"
            accept="application/pdf,.pdf"
            multiple
            disabled={!selectedId || uploading}
            className="sr-only"
            onChange={(event) => {
              onUpload(event.currentTarget.files);
              event.currentTarget.value = "";
            }}
          />
        </label>
      </div>

      <section className="surface min-w-0">
        <div className="flex flex-col justify-between gap-3 border-b border-white/8 p-4 sm:flex-row sm:items-center sm:px-5">
          <label className="flex max-w-lg flex-1 items-center gap-3 text-xs text-slate-400">
            Knowledge base
            <select className="field max-w-sm" value={selectedId} onChange={(event) => onSelectBase(event.target.value)}>
              <option value="">Select a knowledge base</option>
              {bases.map((base) => <option key={base.id} value={base.id}>{base.name}</option>)}
            </select>
          </label>
          <div className="flex items-center gap-2">
            {selectedBase && <span className="text-[11px] text-slate-500">{totalDocuments} documents</span>}
            <button type="button" disabled={!selectedId || loading} onClick={onRefresh} className="button-secondary px-2.5">
              <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Refresh
            </button>
          </div>
        </div>
        {!selectedId ? (
          <div className="p-5">
            <EmptyState icon={Database} title="Select a knowledge base" description="Choose a collection to view or upload its documents." action={<button type="button" onClick={onCreateBase} className="button-secondary"><Plus size={14} /> Create knowledge base</button>} />
          </div>
        ) : loading ? (
          <div className="flex items-center justify-center gap-2 p-16 text-sm text-slate-400"><LoaderCircle size={16} className="animate-spin" /> Loading documents…</div>
        ) : loadError ? (
          <div className="m-5 rounded-lg border border-red-400/20 bg-red-400/5 p-4 text-sm text-red-200">
            Could not load documents: {loadError}
            <button type="button" onClick={onRefresh} className="ml-2 underline">Retry</button>
          </div>
        ) : totalDocuments === 0 ? (
          <div className="p-5">
            <EmptyState icon={Upload} title="No documents uploaded" description="Add one or more PDF files to populate this knowledge base." />
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left">
                <thead className="border-b border-white/8 bg-white/[0.02] text-[10px] uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-5 py-3 font-medium">Document</th>
                    <th className="px-5 py-3 font-medium">Size</th>
                    <th className="px-5 py-3 font-medium">Status</th>
                    <th className="px-5 py-3 font-medium">Uploaded</th>
                    <th className="px-5 py-3 text-right font-medium">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/6">
                  {documents.map((document) => (
                    <tr key={document.id} className="align-top hover:bg-white/[0.015]">
                      <td className="px-5 py-4">
                        <div className="flex min-w-0 items-start gap-2.5">
                          <FileText size={15} className="mt-0.5 shrink-0 text-slate-500" />
                          <span className="min-w-0">
                            <span className="block max-w-[300px] truncate text-xs font-medium text-slate-200" title={document.filename}>{document.filename}</span>
                            <span className="mt-1 block text-[10px] text-slate-600">
                              {document.page_count === null ? "Page count unavailable" : `${document.page_count} page${document.page_count === 1 ? "" : "s"}`}
                            </span>
                            <ProcessingHistory knowledgeBaseId={selectedId} document={document} />
                          </span>
                        </div>
                      </td>
                      <td className="px-5 py-4 text-xs tabular-nums text-slate-400">{formatBytes(document.size_bytes)}</td>
                      <td className="px-5 py-4"><StatusBadge value={document.status} /></td>
                      <td className="px-5 py-4 text-[11px] text-slate-500">{formatDate(document.created_at)}</td>
                      <td className="px-5 py-4 text-right">
                        <button type="button" title={`Delete ${document.filename}`} onClick={() => onDelete(document)} className="rounded-md p-2 text-slate-500 hover:bg-red-400/8 hover:text-red-300">
                          <Trash2 size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex flex-col justify-between gap-3 border-t border-white/8 px-5 py-3 sm:flex-row sm:items-center">
              <p className="text-[11px] text-slate-500">Showing {start}–{end} of {totalDocuments}</p>
              <div className="flex items-center justify-between gap-2 sm:justify-end">
                <span className="mr-2 text-[11px] text-slate-500">Page {page + 1} of {pageCount}</span>
                <button type="button" disabled={page === 0} onClick={() => onPageChange(page - 1)} className="button-secondary px-2 py-1.5" aria-label="Previous page"><ChevronLeft size={14} /></button>
                <button type="button" disabled={page + 1 >= pageCount} onClick={() => onPageChange(page + 1)} className="button-secondary px-2 py-1.5" aria-label="Next page"><ChevronRight size={14} /></button>
              </div>
            </div>
          </>
        )}
        <p className="border-t border-white/6 px-5 py-3 text-[10px] leading-5 text-slate-600">
          PDF uploads are sent as multipart FormData. File size limits are enforced by the backend.
        </p>
      </section>
    </div>
  );
}

function Playground({
  bases,
  selectedId,
  selectedBase,
  query,
  topK,
  result,
  loading,
  error,
  expandedChunk,
  onSelectBase,
  onQueryChange,
  onTopKChange,
  onSubmit,
  onExpandChunk,
}: {
  bases: KnowledgeBase[];
  selectedId: string;
  selectedBase: KnowledgeBase | null;
  query: string;
  topK: number;
  result: QueryResponse | null;
  loading: boolean;
  error: string;
  expandedChunk: string | null;
  onSelectBase: (id: string) => void;
  onQueryChange: (query: string) => void;
  onTopKChange: (topK: number) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onExpandChunk: (chunkId: string | null) => void;
}) {
  return (
    <div className="space-y-6">
      <header>
        <p className="eyebrow">Retrieval augmented generation</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100 sm:text-3xl">RAG Playground</h1>
        <p className="mt-2 text-sm text-slate-400">Submit a query and inspect the actual retrieved evidence used by the backend.</p>
      </header>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_280px]">
        <section className="surface min-w-0">
          <div className="flex items-center gap-2 border-b border-white/8 px-5 py-4">
            <MessageSquareText size={16} className="text-indigo-300" />
            <h2 className="text-sm font-semibold text-slate-100">Ask your knowledge base</h2>
          </div>
          <form onSubmit={(event) => onSubmit(event)} className="space-y-4 p-5">
            <label className="block space-y-1.5 text-xs font-medium text-slate-300">
              Knowledge base
              <select className="field" value={selectedId} onChange={(event) => onSelectBase(event.target.value)}>
                <option value="">Select a knowledge base</option>
                {bases.map((base) => <option key={base.id} value={base.id}>{base.name}</option>)}
              </select>
            </label>
            <label className="block space-y-1.5 text-xs font-medium text-slate-300">
              Your question
              <textarea
                className="field min-h-28 resize-y leading-6"
                maxLength={10000}
                value={query}
                onChange={(event) => onQueryChange(event.target.value)}
                placeholder="Ask a question about the documents in this knowledge base."
              />
            </label>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <label className="flex items-center gap-2 text-xs text-slate-400">
                Retrieved chunks
                <select className="field w-20 py-2" value={topK} onChange={(event) => onTopKChange(Number(event.target.value))}>
                  {Array.from({ length: 20 }, (_, index) => index + 1).map((count) => <option key={count} value={count}>{count}</option>)}
                </select>
              </label>
              <button type="submit" disabled={!selectedId || !query.trim() || loading} className="button-primary">
                {loading ? <LoaderCircle size={15} className="animate-spin" /> : <Search size={15} />}
                {loading ? "Retrieving…" : "Run query"}
              </button>
            </div>
          </form>
          {!selectedId && <p className="mx-5 mb-5 rounded-lg border border-amber-300/15 bg-amber-300/5 p-3 text-xs text-amber-100">Select a knowledge base before querying.</p>}
          {error && <p role="alert" className="mx-5 mb-5 flex gap-2 rounded-lg border border-red-400/20 bg-red-400/5 p-3 text-sm text-red-200"><AlertCircle size={15} className="mt-0.5 shrink-0" />{error}</p>}
          {result && (
            <div className="border-t border-white/8 p-5">
              <section aria-labelledby="answer-heading">
                <div className="flex items-center gap-2">
                  <Bot size={16} className="text-indigo-300" />
                  <h3 id="answer-heading" className="text-sm font-semibold text-slate-100">Generated answer</h3>
                </div>
                <div className="mt-3 whitespace-pre-wrap rounded-lg border border-white/6 bg-black/15 p-4 text-sm leading-7 text-slate-300">
                  {result.answer || "The API returned no answer text."}
                </div>
              </section>
              <section aria-labelledby="sources-heading" className="mt-6">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <BookOpen size={15} className="text-slate-400" />
                    <h3 id="sources-heading" className="text-sm font-semibold text-slate-100">Retrieved sources</h3>
                  </div>
                  <span className="text-[11px] text-slate-500">{result.sources.length} citations</span>
                </div>
                {result.sources.length === 0 ? (
                  <div className="mt-3 rounded-lg border border-dashed border-white/10 p-5 text-center text-xs text-slate-500">
                    No retrieved sources were returned for this query.
                  </div>
                ) : (
                  <div className="mt-3 space-y-2.5">
                    {result.sources.map((source) => {
                      const chunk = result.results.find((item) => item.chunk_id === source.chunk_id);
                      const expanded = expandedChunk === source.chunk_id;
                      return (
                        <article key={source.chunk_id} className="overflow-hidden rounded-lg border border-white/8">
                          <button
                            type="button"
                            onClick={() => onExpandChunk(expanded ? null : source.chunk_id)}
                            aria-expanded={expanded}
                            className="flex w-full items-center justify-between gap-4 p-3.5 text-left hover:bg-white/[0.025]"
                          >
                            <span className="min-w-0">
                              <span className="block truncate text-xs font-medium text-slate-200">{source.filename}</span>
                              <span className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-slate-500">
                                <span>Pages {source.page_numbers.length ? source.page_numbers.join(", ") : "Not available"}</span>
                                <span>Chunk {source.chunk_index}</span>
                                <span>Similarity {Number.isFinite(source.score) ? source.score.toFixed(4) : "Not available"}</span>
                              </span>
                            </span>
                            {expanded ? <ChevronDown size={15} className="shrink-0 text-slate-500" /> : <ChevronRight size={15} className="shrink-0 text-slate-500" />}
                          </button>
                          {expanded && (
                            <div className="border-t border-white/8 bg-black/15 p-4">
                              {chunk ? (
                                <p className="whitespace-pre-wrap text-xs leading-6 text-slate-400">{chunk.content}</p>
                              ) : (
                                <p className="text-xs text-slate-500">Chunk content was not returned by the API for this citation.</p>
                              )}
                            </div>
                          )}
                        </article>
                      );
                    })}
                  </div>
                )}
              </section>
            </div>
          )}
        </section>

        <aside className="surface h-fit p-5">
          <div className="flex items-center gap-2">
            <Settings2 size={16} className="text-slate-400" />
            <h2 className="text-sm font-semibold text-slate-100">Query configuration</h2>
          </div>
          <div className="mt-5 space-y-4">
            <div>
              <p className="text-[10px] uppercase tracking-wide text-slate-600">Selected knowledge base</p>
              <p className="mt-1.5 break-words text-xs font-medium text-slate-300">{selectedBase?.name ?? "None selected"}</p>
            </div>
            <div className="border-t border-white/8 pt-4">
              <p className="text-[10px] uppercase tracking-wide text-slate-600">Top-K</p>
              <p className="mt-1.5 text-xs font-medium text-slate-300">{topK} results</p>
            </div>
            <div className="border-t border-white/8 pt-4">
              <p className="text-[10px] uppercase tracking-wide text-slate-600">Evidence policy</p>
              <p className="mt-1.5 text-xs leading-5 text-slate-400">Citations and retrieved chunks are rendered only from the query API response.</p>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
