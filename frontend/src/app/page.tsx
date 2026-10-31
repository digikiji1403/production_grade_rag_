"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Activity, BookOpen, Bot, ChevronDown, ChevronRight, Database,
  FileText, FolderOpen, LayoutDashboard, LogOut, MessageSquare,
  Plus, RefreshCw, Send, Settings, ShieldCheck, Sparkles,
  Trash2, Upload, X,
} from "lucide-react";
import {
  api, clearToken, getToken, setToken,
  type User, type KnowledgeBase, type Document, type QueryResponse,
} from "@/lib/api";

type View = "overview" | "knowledge" | "playground";

const navItems = [
  { id: "overview" as const, label: "Overview", icon: LayoutDashboard },
  { id: "knowledge" as const, label: "Knowledge Bases", icon: Database },
  { id: "playground" as const, label: "RAG Playground", icon: MessageSquare },
];

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function Status({ value }: { value: string }) {
  const normalized = value.toLowerCase();
  const style =
    normalized === "processed" || normalized === "completed" || normalized === "success"
      ? "bg-emerald-50 text-emerald-700"
      : normalized === "failed" || normalized === "error"
        ? "bg-red-50 text-red-700"
        : "bg-amber-50 text-amber-700";

  return <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${style}`}>{value}</span>;
}

function AuthScreen({ onLogin }: { onLogin: (user: User) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (mode === "register") {
        await api.register(email, password);
      }
      const token = await api.login(email, password);
      setToken(token.access_token);
      const user = await api.me();
      onLogin(user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#f7f8fa] px-5 py-12">
      <div className="w-full max-w-md">
        <div className="mb-9 flex items-center justify-center gap-3">
          <div className="rounded-xl bg-slate-950 p-3 text-white"><Bot size={25} /></div>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">RAGForge</h1>
            <p className="text-xs text-slate-500">Build. Retrieve. Understand.</p>
          </div>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
          <h2 className="text-xl font-semibold">{mode === "login" ? "Welcome back" : "Create your account"}</h2>
          <p className="mt-1 text-sm text-slate-500">
            {mode === "login" ? "Sign in to access your knowledge workspace." : "Register to start building your knowledge base."}
          </p>
          <form onSubmit={submit} className="mt-7 space-y-5">
            <label className="block text-sm font-medium">
              Email address
              <input required type="email" value={email} onChange={e => setEmail(e.target.value)}
                className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-3 font-normal outline-none focus:border-slate-500"
                placeholder="you@example.com" />
            </label>
            <label className="block text-sm font-medium">
              Password
              <input required minLength={mode === "register" ? 12 : 1} type="password" value={password}
                onChange={e => setPassword(e.target.value)}
                className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-3 font-normal outline-none focus:border-slate-500"
                placeholder={mode === "register" ? "At least 12 characters" : "Your password"} />
            </label>
            {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
            <button disabled={busy} className="w-full rounded-lg bg-slate-950 py-3 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50">
              {busy ? "Please wait..." : mode === "login" ? "Sign in" : "Create account"}
            </button>
          </form>
          <p className="mt-6 text-center text-sm text-slate-500">
            {mode === "login" ? "New to RAGForge?" : "Already have an account?"}{" "}
            <button onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}
              className="font-semibold text-slate-900 hover:underline">
              {mode === "login" ? "Create account" : "Sign in"}
            </button>
          </p>
        </div>
        <p className="mt-6 text-center text-xs text-slate-400">Secure document intelligence workspace</p>
      </div>
    </main>
  );
}

export default function Home() {
  const [user, setUser] = useState<User | null>(null);
  const [authChecking, setAuthChecking] = useState(true);
  const [view, setView] = useState<View>("overview");
  const [bases, setBases] = useState<KnowledgeBase[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [queryResult, setQueryResult] = useState<QueryResponse | null>(null);
  const [queryBusy, setQueryBusy] = useState(false);
  const [expandedChunk, setExpandedChunk] = useState<string | null>(null);

  const selectedBase = bases.find(base => base.id === selectedId) ?? null;

  const refreshBases = useCallback(async () => {
    const data = await api.listBases();
    setBases(data);
    setSelectedId(current => data.some(base => base.id === current) ? current : (data[0]?.id ?? ""));
  }, []);

  const refreshDocuments = useCallback(async () => {
    if (!selectedId) {
      setDocuments([]);
      return;
    }
    const data = await api.listDocuments(selectedId);
    setDocuments(data);
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
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!user) return;
    setLoading(true);
    setError("");
    refreshBases()
      .catch(err => setError(err instanceof Error ? err.message : "Could not load knowledge bases"))
      .finally(() => setLoading(false));
  }, [user, refreshBases]);

  useEffect(() => {
    if (!user) return;
    refreshDocuments().catch(err => setError(err instanceof Error ? err.message : "Could not load documents"));
  }, [user, refreshDocuments]);

  async function createBase(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    setError("");
    try {
      const created = await api.createBase({ name: newName.trim(), description: newDescription.trim() || null });
      setBases(current => [created, ...current]);
      setSelectedId(created.id);
      setNewName("");
      setNewDescription("");
      setShowCreate(false);
      setNotice("Knowledge base created.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create knowledge base");
    }
  }

  async function deleteBase(base: KnowledgeBase) {
    if (!window.confirm(`Delete "${base.name}" and its associated data?`)) return;
    try {
      await api.deleteBase(base.id);
      const remaining = bases.filter(item => item.id !== base.id);
      setBases(remaining);
      if (selectedId === base.id) setSelectedId(remaining[0]?.id ?? "");
      setNotice("Knowledge base deleted.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete knowledge base");
    }
  }

  async function uploadFiles(files: FileList | null) {
    if (!files || !selectedId) return;
    const selectedFiles = Array.from(files);
    for (const file of selectedFiles) {
      if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
        setError(`${file.name} is not a PDF file.`);
        continue;
      }
      try {
        setError("");
        await api.uploadDocument(selectedId, file);
        setNotice(`${file.name} uploaded. Processing may take some time.`);
      } catch (err) {
        setError(err instanceof Error ? err.message : `Could not upload ${file.name}`);
      }
    }
    await refreshDocuments();
  }

  async function deleteDocument(doc: Document) {
    if (!selectedId || !window.confirm(`Delete "${doc.filename}"?`)) return;
    try {
      await api.deleteDocument(selectedId, doc.id);
      setDocuments(current => current.filter(item => item.id !== doc.id));
      setNotice("Document deleted.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete document");
    }
  }

  async function runQuery(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedId || !query.trim()) return;
    setQueryBusy(true);
    setError("");
    setQueryResult(null);
    try {
      const result = await api.query(selectedId, query.trim(), topK);
      setQueryResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query failed");
    } finally {
      setQueryBusy(false);
    }
  }

  function logout() {
    clearToken();
    setUser(null);
    setBases([]);
    setDocuments([]);
    setSelectedId("");
    setQueryResult(null);
  }

  if (authChecking) {
    return <div className="flex min-h-screen items-center justify-center text-sm text-slate-500"><RefreshCw className="mr-2 animate-spin" size={17} /> Checking session...</div>;
  }
  if (!user) return <AuthScreen onLogin={setUser} />;

  return (
    <div className="min-h-screen bg-[#f7f8fa] text-slate-900">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-64 flex-col border-r border-slate-200 bg-white lg:flex">
        <div className="flex h-20 items-center gap-3 border-b border-slate-100 px-6">
          <div className="rounded-lg bg-slate-950 p-2 text-white"><Bot size={21} /></div>
          <div><div className="font-semibold tracking-tight">RAGForge</div><div className="text-[11px] text-slate-400">DOCUMENT INTELLIGENCE</div></div>
        </div>
        <div className="px-4 pt-7">
          <p className="mb-3 px-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">Workspace</p>
          <nav className="space-y-1">
            {navItems.map(item => {
              const Icon = item.icon;
              return <button key={item.id} onClick={() => setView(item.id)}
                className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm ${view === item.id ? "bg-slate-100 font-semibold text-slate-950" : "text-slate-500 hover:bg-slate-50 hover:text-slate-900"}`}>
                <Icon size={17} />{item.label}
              </button>;
            })}
          </nav>
        </div>
        <div className="mt-8 px-4">
          <div className="mb-3 flex items-center justify-between px-3">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">Your collections</p>
            <button title="Create knowledge base" onClick={() => setShowCreate(true)} className="text-slate-500 hover:text-slate-950"><Plus size={16} /></button>
          </div>
          <div className="space-y-1">
            {bases.slice(0, 6).map(base => <button key={base.id} onClick={() => { setSelectedId(base.id); setView("knowledge"); }}
              className={`flex w-full items-center gap-2 truncate rounded-lg px-3 py-2 text-left text-xs ${selectedId === base.id ? "bg-slate-100 text-slate-900" : "text-slate-500 hover:bg-slate-50"}`}>
              <FolderOpen size={14} className="shrink-0" /><span className="truncate">{base.name}</span>
            </button>)}
            {bases.length === 0 && <p className="px-3 text-xs text-slate-400">No collections yet</p>}
          </div>
        </div>
        <div className="mt-auto border-t border-slate-100 p-4">
          <div className="flex items-center gap-3 rounded-lg bg-slate-50 p-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-200 text-sm font-semibold">{user.email[0]?.toUpperCase()}</div>
            <div className="min-w-0 flex-1"><p className="truncate text-xs font-semibold">{user.email}</p><p className="text-[10px] text-slate-400">Workspace member</p></div>
            <button title="Sign out" onClick={logout} className="text-slate-400 hover:text-red-600"><LogOut size={16} /></button>
          </div>
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-slate-200 bg-white/90 px-5 backdrop-blur md:px-9">
          <div className="flex items-center gap-2 text-sm text-slate-500"><span className="hidden sm:inline">Workspace</span><ChevronRight size={14} /><span className="font-medium text-slate-900">{navItems.find(item => item.id === view)?.label}</span></div>
          <div className="flex items-center gap-3">
            <span className="hidden text-xs text-slate-500 sm:inline">{user.email}</span>
            <span className="flex items-center gap-1.5 rounded-full border border-emerald-100 bg-emerald-50 px-2.5 py-1 text-[11px] font-medium text-emerald-700"><span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> Connected</span>
            <button onClick={logout} title="Sign out" className="text-slate-400 hover:text-red-600 lg:hidden"><LogOut size={17} /></button>
          </div>
        </header>

        <main className="mx-auto max-w-7xl p-5 md:p-9">
          {(error || notice) && <div className={`mb-5 flex items-start justify-between rounded-lg border p-3 text-sm ${error ? "border-red-100 bg-red-50 text-red-700" : "border-emerald-100 bg-emerald-50 text-emerald-800"}`}>
            <span>{error || notice}</span><button onClick={() => { setError(""); setNotice(""); }}><X size={16} /></button>
          </div>}

          {view === "overview" && <>
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
              <div><p className="text-xs font-medium uppercase tracking-widest text-slate-400">Your workspace</p><h1 className="mt-2 text-3xl font-semibold tracking-tight">Overview</h1><p className="mt-2 text-sm text-slate-500">Manage your knowledge and explore your documents with AI.</p></div>
              <button onClick={() => setShowCreate(true)} className="flex items-center justify-center gap-2 rounded-lg bg-slate-950 px-4 py-2.5 text-sm font-medium text-white hover:bg-slate-800"><Plus size={16} /> New knowledge base</button>
            </div>
            <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {[
                { label: "Knowledge bases", value: bases.length, icon: Database, note: "Your collections" },
                { label: "Documents", value: documents.length, icon: FileText, note: "In selected collection" },
                { label: "Processed documents", value: documents.filter(d => ["processed", "completed", "success"].includes(d.status.toLowerCase())).length, icon: ShieldCheck, note: "In selected collection" },
              ].map(card => <div key={card.label} className="rounded-xl border border-slate-200 bg-white p-5">
                <div className="flex items-center justify-between"><span className="text-sm text-slate-500">{card.label}</span><card.icon size={18} className="text-slate-400" /></div>
                <p className="mt-4 text-3xl font-semibold tracking-tight">{card.value}</p><p className="mt-1 text-xs text-slate-400">{card.note}</p>
              </div>)}
            </div>
            <div className="mt-8 grid gap-6 xl:grid-cols-[1.5fr_1fr]">
              <section className="rounded-xl border border-slate-200 bg-white">
                <div className="flex items-center justify-between border-b border-slate-100 p-5"><div><h2 className="font-semibold">Knowledge bases</h2><p className="mt-1 text-xs text-slate-400">Your document collections</p></div><button onClick={() => setView("knowledge")} className="text-xs font-medium text-slate-600 hover:text-black">View all</button></div>
                {bases.length === 0 ? <div className="px-5 py-12 text-center"><Database className="mx-auto text-slate-300" size={30} /><p className="mt-3 text-sm font-medium">No knowledge bases yet</p><p className="mt-1 text-xs text-slate-400">Create your first collection to get started.</p><button onClick={() => setShowCreate(true)} className="mt-4 rounded-lg bg-slate-950 px-4 py-2 text-xs font-medium text-white">Create knowledge base</button></div> :
                  <div className="divide-y divide-slate-100">{bases.slice(0, 5).map(base => <button key={base.id} onClick={() => { setSelectedId(base.id); setView("knowledge"); }} className="flex w-full items-center justify-between p-5 text-left hover:bg-slate-50"><div className="flex min-w-0 items-center gap-3"><div className="rounded-lg bg-slate-100 p-2.5"><Database size={17} /></div><div className="min-w-0"><p className="truncate text-sm font-medium">{base.name}</p><p className="mt-1 truncate text-xs text-slate-400">{base.description || "No description"}</p></div></div><ChevronRight size={17} className="shrink-0 text-slate-400" /></button>)}</div>}
              </section>
              <section className="rounded-xl border border-slate-200 bg-white p-5">
                <div className="flex items-center gap-2"><Sparkles size={17} /><h2 className="font-semibold">Get started</h2></div>
                <div className="mt-5 space-y-5">
                  {[["01", "Create a knowledge base", "Organize documents into a collection."], ["02", "Upload your PDFs", "Add source documents for retrieval."], ["03", "Ask your documents", "Query your collection with RAG."]].map(([number, title, description]) => <div key={number} className="flex gap-3"><span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold">{number}</span><div><p className="text-sm font-medium">{title}</p><p className="mt-1 text-xs leading-relaxed text-slate-500">{description}</p></div></div>)}
                </div>
                <button onClick={() => setView("playground")} className="mt-7 flex w-full items-center justify-center gap-2 rounded-lg border border-slate-200 py-2.5 text-sm font-medium hover:bg-slate-50">Open RAG Playground <ChevronRight size={15} /></button>
              </section>
            </div>
          </>}

          {view === "knowledge" && <>
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
              <div><p className="text-xs font-medium uppercase tracking-widest text-slate-400">Document management</p><h1 className="mt-2 text-3xl font-semibold tracking-tight">Knowledge Bases</h1><p className="mt-2 text-sm text-slate-500">Create collections and manage your source documents.</p></div>
              <button onClick={() => setShowCreate(true)} className="flex items-center justify-center gap-2 rounded-lg bg-slate-950 px-4 py-2.5 text-sm font-medium text-white"><Plus size={16} /> Create collection</button>
            </div>
            <div className="mt-8 grid gap-6 xl:grid-cols-[300px_1fr]">
              <section className="h-fit rounded-xl border border-slate-200 bg-white">
                <div className="border-b border-slate-100 p-4"><h2 className="text-sm font-semibold">Collections <span className="ml-1 text-xs font-normal text-slate-400">{bases.length}</span></h2></div>
                {bases.length === 0 ? <p className="p-5 text-sm text-slate-400">Create a knowledge base to begin.</p> : <div className="max-h-[500px] overflow-y-auto p-2">{bases.map(base => <div key={base.id} className={`group flex items-center gap-1 rounded-lg ${selectedId === base.id ? "bg-slate-100" : "hover:bg-slate-50"}`}><button onClick={() => setSelectedId(base.id)} className="min-w-0 flex-1 px-3 py-3 text-left"><p className="truncate text-sm font-medium">{base.name}</p><p className="mt-1 text-[11px] text-slate-400">{base.description || "No description"}</p></button><button title="Delete collection" onClick={() => deleteBase(base)} className="mr-2 p-2 text-slate-300 opacity-0 hover:text-red-600 group-hover:opacity-100"><Trash2 size={14} /></button></div>)}</div>}
              </section>
              <section className="min-w-0 rounded-xl border border-slate-200 bg-white">
                {selectedBase ? <>
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 p-5"><div className="min-w-0"><h2 className="truncate font-semibold">{selectedBase.name}</h2><p className="mt-1 text-xs text-slate-400">{selectedBase.description || "Document collection"}</p></div><label className="flex cursor-pointer items-center gap-2 rounded-lg bg-slate-950 px-4 py-2.5 text-xs font-medium text-white hover:bg-slate-800"><Upload size={15} /> Upload PDF<input type="file" accept="application/pdf,.pdf" multiple className="hidden" onChange={e => { void uploadFiles(e.target.files); e.currentTarget.value = ""; }} /></label></div>
                  <div className="p-5">
                    <div className="mb-4 flex items-center justify-between"><h3 className="text-sm font-semibold">Documents</h3><button onClick={() => refreshDocuments().catch(err => setError(err.message))} className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-900"><RefreshCw size={13} /> Refresh</button></div>
                    {documents.length === 0 ? <div className="rounded-xl border border-dashed border-slate-200 px-5 py-12 text-center"><Upload className="mx-auto text-slate-300" size={28} /><p className="mt-3 text-sm font-medium">No documents uploaded</p><p className="mt-1 text-xs text-slate-400">Upload PDF files to populate this knowledge base.</p></div> :
                      <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b border-slate-100 text-xs text-slate-400"><th className="pb-3 font-medium">Document</th><th className="pb-3 font-medium">Size</th><th className="pb-3 font-medium">Status</th><th className="pb-3 text-right font-medium">Action</th></tr></thead><tbody className="divide-y divide-slate-100">{documents.map(doc => <tr key={doc.id}><td className="py-4"><div className="flex min-w-0 items-center gap-2"><FileText size={17} className="shrink-0 text-slate-400" /><span className="max-w-[240px] truncate text-xs font-medium">{doc.filename}</span></div><p className="mt-1 pl-6 text-[10px] text-slate-400">{doc.page_count ? `${doc.page_count} pages` : "Page count pending"}</p></td><td className="py-4 text-xs text-slate-500">{formatBytes(doc.size_bytes)}</td><td className="py-4"><Status value={doc.status} /></td><td className="py-4 text-right"><button title="Delete document" onClick={() => deleteDocument(doc)} className="p-2 text-slate-400 hover:text-red-600"><Trash2 size={15} /></button></td></tr>)}</tbody></table></div>}
                    <p className="mt-4 text-[11px] leading-relaxed text-slate-400">New uploads are queued for processing. Their status will update when the backend worker completes ingestion.</p>
                  </div>
                </> : <div className="p-12 text-center"><Database className="mx-auto text-slate-300" size={30} /><p className="mt-3 text-sm font-medium">Select a knowledge base</p><p className="mt-1 text-xs text-slate-400">Choose a collection or create a new one.</p></div>}
              </section>
            </div>
          </>}

          {view === "playground" && <>
            <div><p className="text-xs font-medium uppercase tracking-widest text-slate-400">Retrieval augmented generation</p><h1 className="mt-2 text-3xl font-semibold tracking-tight">RAG Playground</h1><p className="mt-2 text-sm text-slate-500">Ask questions and inspect the retrieved context behind each answer.</p></div>
            <div className="mt-8 grid gap-6 xl:grid-cols-[minmax(0,1fr)_300px]">
              <section className="min-w-0 rounded-xl border border-slate-200 bg-white">
                <div className="flex items-center gap-2 border-b border-slate-100 p-5"><Bot size={18} /><h2 className="text-sm font-semibold">Ask your knowledge base</h2></div>
                <form onSubmit={runQuery} className="p-5">
                  <label className="mb-2 block text-xs font-medium text-slate-600">Your question</label>
                  <textarea value={query} onChange={e => setQuery(e.target.value)} rows={4} placeholder="Ask a question about your uploaded documents..."
                    className="w-full resize-y rounded-lg border border-slate-200 p-4 text-sm outline-none focus:border-slate-500" />
                  <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                    <label className="flex items-center gap-2 text-xs text-slate-500">Retrieved chunks
                      <select value={topK} onChange={e => setTopK(Number(e.target.value))} className="rounded-md border border-slate-200 bg-white px-2 py-1.5 text-xs"><option value={3}>3</option><option value={5}>5</option><option value={8}>8</option><option value={10}>10</option></select>
                    </label>
                    <button disabled={queryBusy || !selectedId || !query.trim()} className="flex items-center gap-2 rounded-lg bg-slate-950 px-5 py-2.5 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40">{queryBusy ? <><RefreshCw size={15} className="animate-spin" /> Retrieving...</> : <><Send size={15} /> Run query</>}</button>
                  </div>
                </form>
                {!selectedId && <p className="mx-5 mb-5 rounded-lg bg-amber-50 p-3 text-xs text-amber-800">Create or select a knowledge base before querying.</p>}
                {queryResult && <div className="border-t border-slate-100 p-5">
                  <div className="flex items-center gap-2"><Sparkles size={17} /><h3 className="text-sm font-semibold">Generated answer</h3></div>
                  <div className="mt-4 whitespace-pre-wrap rounded-xl bg-slate-50 p-5 text-sm leading-7 text-slate-700">{queryResult.answer || "No answer was returned."}</div>
                  <div className="mt-6 flex items-center justify-between"><h3 className="text-sm font-semibold">Retrieved sources</h3><span className="text-xs text-slate-400">{queryResult.sources.length} sources</span></div>
                  <div className="mt-3 space-y-3">{queryResult.sources.map(source => <div key={source.chunk_id} className="rounded-lg border border-slate-200">
                    <button onClick={() => setExpandedChunk(expandedChunk === source.chunk_id ? null : source.chunk_id)} className="flex w-full items-center justify-between gap-3 p-4 text-left"><div className="min-w-0"><p className="truncate text-xs font-semibold">{source.source_id} · {source.filename}</p><p className="mt-1 text-[11px] text-slate-400">Chunk {source.chunk_index} · Pages {source.page_numbers.join(", ") || "N/A"} · Score {source.score.toFixed(3)}</p></div>{expandedChunk === source.chunk_id ? <ChevronDown size={16} /> : <ChevronRight size={16} />}</button>
                    {expandedChunk === source.chunk_id && <div className="border-t border-slate-100 bg-slate-50 p-4 text-xs leading-6 text-slate-600">{queryResult.results.find(result => result.chunk_id === source.chunk_id)?.content || "Retrieved chunk content unavailable."}</div>}
                  </div>)}</div>
                </div>}
              </section>
              <aside className="h-fit rounded-xl border border-slate-200 bg-white p-5">
                <div className="flex items-center gap-2"><Activity size={17} /><h2 className="text-sm font-semibold">Query configuration</h2></div>
                <div className="mt-5"><p className="text-xs text-slate-400">ACTIVE KNOWLEDGE BASE</p><p className="mt-2 text-sm font-medium">{selectedBase?.name || "None selected"}</p></div>
                <div className="my-5 border-t border-slate-100" />
                <div><p className="text-xs text-slate-400">RETRIEVAL COUNT</p><p className="mt-2 text-sm font-medium">Top {topK} chunks</p></div>
                <div className="my-5 border-t border-slate-100" />
                <div><p className="text-xs text-slate-400">GENERATION MODEL</p><p className="mt-2 text-sm font-medium">Ollama · qwen3:4b</p></div>
                <div className="my-5 border-t border-slate-100" />
                <div><p className="text-xs text-slate-400">EMBEDDING MODEL</p><p className="mt-2 text-sm font-medium">embeddinggemma</p></div>
                <p className="mt-5 text-[11px] leading-relaxed text-slate-400">Configuration labels reflect the current backend setup. Retrieval and generation execute on the backend.</p>
              </aside>
            </div>
          </>}
        </main>
      </div>

      {showCreate && <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/40 p-4">
        <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
          <div className="flex items-center justify-between"><h2 className="text-lg font-semibold">New knowledge base</h2><button onClick={() => setShowCreate(false)} className="text-slate-400 hover:text-slate-900"><X size={19} /></button></div>
          <p className="mt-1 text-sm text-slate-500">Create a collection for your documents.</p>
          <form onSubmit={createBase} className="mt-6 space-y-4">
            <label className="block text-xs font-medium">Name<input autoFocus required maxLength={120} value={newName} onChange={e => setNewName(e.target.value)} placeholder="e.g. Research papers" className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-3 text-sm outline-none focus:border-slate-500" /></label>
            <label className="block text-xs font-medium">Description <span className="font-normal text-slate-400">(optional)</span><textarea maxLength={1000} rows={3} value={newDescription} onChange={e => setNewDescription(e.target.value)} placeholder="What is this collection about?" className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-3 text-sm outline-none focus:border-slate-500" /></label>
            <div className="flex justify-end gap-2 pt-2"><button type="button" onClick={() => setShowCreate(false)} className="rounded-lg border border-slate-200 px-4 py-2.5 text-sm">Cancel</button><button disabled={!newName.trim()} className="rounded-lg bg-slate-950 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-40">Create</button></div>
          </form>
        </div>
      </div>}
    </div>
  );
}
