import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";

type Severity = "high" | "medium" | "low";
type EngineMode = "hybrid_ai" | "rules_demo" | "hybrid_fallback";
type AIProvider = "siliconflow" | "deepseek";
type LegalNature = "compliance_risk" | "enforceability_risk" | "agreement_gap" | "commercial_risk";
type RiskStatus = "pending" | "adopted" | "communicated" | "ignored";
type WorkspaceTab = "risks" | "document" | "detail";

interface DocumentBlock {
  block_id: string;
  kind: "paragraph" | "table_row";
  text: string;
  page: number | null;
  paragraph_index: number | null;
  table_index: number | null;
  source_order: number;
}

interface LegalBasis {
  basis_id: string;
  document_name: string;
  article_number: string;
  authority_type: string;
  article_excerpt: string;
  application_note: string;
  limitations: string[];
  effective_status: "现行有效" | "待复核";
  official_url: string;
  verified_at: string;
}

interface RiskItem {
  risk_id: string;
  category: string;
  severity: Severity;
  risk_type: "existing_clause" | "missing_clause";
  title: string;
  quote: string;
  source_block_ids: string[];
  legal_issue: string;
  business_impact: string;
  legal_nature: LegalNature;
  legal_conclusion: string;
  legal_bases: LegalBasis[];
  ideal_revision: string;
  compromise_revision: string;
  bottom_line: string;
  negotiation_message: string;
  confidence: "high" | "medium" | "low";
  source: "rule" | "ai";
}

interface ReviewResult {
  review_id: string;
  engine_mode: EngineMode;
  model_name: string | null;
  warnings: string[];
  filename: string;
  file_type: string;
  text_length: number;
  legal_library_version: string;
  legal_library_verified_at: string | null;
  document_blocks: DocumentBlock[];
  summary: {
    contract_type: string;
    our_role: string;
    counterparty_role: string;
    key_terms: string[];
    must_fix: string[];
  };
  risk_bill: {
    total_risks: number;
    high: number;
    medium: number;
    low: number;
    payment_exposure: string;
    acceptance_exposure: string;
    liability_exposure: string;
    ip_exposure: string;
  };
  risks: RiskItem[];
  created_at: string;
  expires_at: string;
}

interface ReviewListItem {
  review_id: string;
  filename: string;
  engine_mode: EngineMode;
  contract_type: string;
  total_risks: number;
  high_risks: number;
  created_at: string;
  expires_at: string;
}

interface AISettingsStatus {
  configured: boolean;
  provider: AIProvider;
  base_url: string;
  model: string;
  key_hint: string | null;
  storage: "memory_only" | "encrypted_local" | "environment";
  tested_model: string | null;
  test_tokens: number | null;
}

const roleOptions = [
  ["service_provider", "乙方 / 服务提供方"],
  ["customer", "甲方 / 客户方"],
  ["seller", "销售方"],
  ["buyer", "采购方"],
];

const aiPresets: Record<AIProvider, { label: string; baseUrl: string; model: string; note: string }> = {
  siliconflow: {
    label: "SiliconFlow",
    baseUrl: "https://api.siliconflow.cn/v1",
    model: "deepseek-ai/DeepSeek-V4-Flash",
    note: "推荐用于本地测试，兼容 OpenAI 接口",
  },
  deepseek: {
    label: "DeepSeek 官方",
    baseUrl: "https://api.deepseek.com",
    model: "deepseek-v4-flash",
    note: "使用 DeepSeek 官方 API 账户",
  },
};

const severityLabel: Record<Severity, string> = { high: "高风险", medium: "中风险", low: "低风险" };
const categoryLabel: Record<string, string> = {
  acceptance: "验收",
  payment: "付款",
  scope: "服务范围",
  change_management: "需求变更",
  intellectual_property: "知识产权",
  liability: "违约责任",
  termination: "合同解除",
  dispute_resolution: "争议解决",
  confidentiality: "保密",
  data_compliance: "数据合规",
  data_privacy: "数据与个人信息",
};
const legalNatureLabel: Record<LegalNature, string> = {
  compliance_risk: "法定合规风险",
  enforceability_risk: "效力 / 执行风险",
  agreement_gap: "重要约定缺失",
  commercial_risk: "商业风险",
};
const riskStatusLabel: Record<RiskStatus, string> = {
  pending: "待处理",
  adopted: "已采用建议",
  communicated: "已沟通",
  ignored: "暂时忽略",
};
const loadingSteps = ["解析合同结构", "运行原创规则", "AI 交叉复核", "生成审查建议"];

function Icon({ name, size = 18 }: { name: string; size?: number }) {
  const paths: Record<string, ReactNode> = {
    upload: <><path d="M12 16V4"/><path d="m7 9 5-5 5 5"/><path d="M5 20h14"/></>,
    history: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l3 2"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3A1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/></>,
    arrow: <><path d="M5 12h14"/><path d="m14 7 5 5-5 5"/></>,
    back: <><path d="M19 12H5"/><path d="m10 17-5-5 5-5"/></>,
    file: <><path d="M6 2h8l4 4v16H6z"/><path d="M14 2v5h5"/><path d="M9 13h6M9 17h6"/></>,
    search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>,
    check: <path d="m5 12 4 4L19 6"/>,
    copy: <><rect x="8" y="8" width="11" height="11" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/></>,
    export: <><path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/></>,
    overview: <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
    close: <><path d="m6 6 12 12"/><path d="M18 6 6 18"/></>,
    shield: <><path d="M12 3 4 6v6c0 5 3.4 8.4 8 10 4.6-1.6 8-5 8-10V6z"/><path d="m9 12 2 2 4-5"/></>,
    link: <><path d="M10 13a5 5 0 0 0 7.5.5l2-2a5 5 0 0 0-7-7l-1.1 1"/><path d="M14 11a5 5 0 0 0-7.5-.5l-2 2a5 5 0 0 0 7 7l1.1-1"/></>,
  };
  return <svg aria-hidden="true" viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

function engineLabel(result: ReviewResult) {
  if (result.engine_mode === "hybrid_ai") return `AI＋规则 · ${result.model_name}`;
  if (result.engine_mode === "hybrid_fallback") return "AI 异常 · 已安全降级";
  return "本地规则演示模式";
}

export default function App() {
  const [screen, setScreen] = useState<"home" | "workspace">("home");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [role, setRole] = useState("service_provider");
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingSample, setLoadingSample] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ReviewResult | null>(null);
  const [history, setHistory] = useState<ReviewListItem[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [showOverview, setShowOverview] = useState(false);
  const [activeRiskId, setActiveRiskId] = useState("");
  const [riskStatuses, setRiskStatuses] = useState<Record<string, RiskStatus>>({});
  const [severityFilter, setSeverityFilter] = useState<"all" | Severity>("all");
  const [statusFilter, setStatusFilter] = useState<"all" | "pending" | "handled">("all");
  const [search, setSearch] = useState("");
  const [workspaceTab, setWorkspaceTab] = useState<WorkspaceTab>("risks");
  const [copied, setCopied] = useState("");
  const [aiStatus, setAIStatus] = useState<AISettingsStatus | null>(null);
  const [showAISettings, setShowAISettings] = useState(false);
  const [aiProvider, setAIProvider] = useState<AIProvider>("siliconflow");
  const [aiKey, setAIKey] = useState("");
  const [aiModel, setAIModel] = useState(aiPresets.siliconflow.model);
  const [aiRemember, setAIRemember] = useState(true);
  const [aiTesting, setAITesting] = useState(false);
  const [aiError, setAIError] = useState("");
  const [aiSuccess, setAISuccess] = useState("");
  const [exporting, setExporting] = useState(false);

  const activeRisk = useMemo(() => result?.risks.find((risk) => risk.risk_id === activeRiskId) || result?.risks[0] || null, [activeRiskId, result]);
  const handledCount = useMemo(() => result ? result.risks.filter((risk) => (riskStatuses[risk.risk_id] || "pending") !== "pending").length : 0, [result, riskStatuses]);
  const filteredRisks = useMemo(() => {
    if (!result) return [];
    const keyword = search.trim().toLowerCase();
    return result.risks.filter((risk) => {
      const status = riskStatuses[risk.risk_id] || "pending";
      if (severityFilter !== "all" && risk.severity !== severityFilter) return false;
      if (statusFilter === "pending" && status !== "pending") return false;
      if (statusFilter === "handled" && status === "pending") return false;
      return !keyword || [risk.title, risk.quote, categoryLabel[risk.category] || risk.category].join(" ").toLowerCase().includes(keyword);
    });
  }, [result, riskStatuses, search, severityFilter, statusFilter]);

  const submitDisabled = loading || (!file && text.trim().length < 30);

  async function refreshHistory() {
    try {
      const response = await fetch("/api/reviews?limit=12");
      if (response.ok) setHistory(await response.json());
    } catch { /* history is non-blocking */ }
  }

  async function refreshAIStatus() {
    try {
      const response = await fetch("/api/settings/ai");
      if (!response.ok) return;
      const status: AISettingsStatus = await response.json();
      setAIStatus(status);
      setAIProvider(status.provider);
      setAIModel(status.model);
    } catch { /* settings are non-blocking */ }
  }

  useEffect(() => { void refreshHistory(); void refreshAIStatus(); }, []);
  useEffect(() => {
    if (!loading) return;
    const timer = window.setInterval(() => setLoadingStep((value) => Math.min(value + 1, loadingSteps.length - 1)), 6000);
    return () => window.clearInterval(timer);
  }, [loading]);
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      if (showAISettings && !aiTesting) setShowAISettings(false);
      else if (showHistory) setShowHistory(false);
      else if (showOverview) setShowOverview(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [aiTesting, showAISettings, showHistory, showOverview]);

  function openAISettings() {
    const provider = aiStatus?.provider || "siliconflow";
    setAIProvider(provider);
    setAIModel(aiStatus?.model || aiPresets[provider].model);
    setAIKey("");
    setAIRemember(aiStatus?.storage === "encrypted_local" || !aiStatus?.configured);
    setAIError("");
    setAISuccess("");
    setShowAISettings(true);
  }

  async function connectAI(event: FormEvent) {
    event.preventDefault();
    setAITesting(true); setAIError(""); setAISuccess("");
    try {
      const response = await fetch("/api/settings/ai", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ provider: aiProvider, api_key: aiKey, model: aiModel, remember: aiRemember }) });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "AI 连接测试失败");
      setAIStatus(payload); setAIKey("");
      setAISuccess(`连接成功 · ${payload.tested_model || payload.model} · ${payload.storage === "encrypted_local" ? "已安全记住" : "仅本次运行"}`);
    } catch (reason) { setAIError(reason instanceof Error ? reason.message : "AI 连接测试失败"); }
    finally { setAITesting(false); }
  }

  async function clearAIConnection() {
    setAITesting(true); setAIError("");
    try {
      const response = await fetch("/api/settings/ai", { method: "DELETE" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "清除配置失败");
      setAIStatus(payload); setAIKey(""); setAISuccess("AI 连接和本机加密密钥已清除。");
    } catch (reason) { setAIError(reason instanceof Error ? reason.message : "清除配置失败"); }
    finally { setAITesting(false); }
  }

  async function runReview(inputText: string, inputFile: File | null, selectedRole: string) {
    setLoading(true); setLoadingStep(0); setError("");
    const body = new FormData();
    body.append("party_role", selectedRole);
    if (inputFile) body.append("file", inputFile); else body.append("text", inputText);
    try {
      const response = await fetch("/api/reviews", { method: "POST", body });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "合同审查失败");
      setResult(payload); setActiveRiskId(payload.risks[0]?.risk_id || ""); setRiskStatuses({});
      setSearch(""); setSeverityFilter("all"); setStatusFilter("all"); setWorkspaceTab("risks");
      setScreen("workspace"); setShowOverview(true); await refreshHistory();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "合同审查失败"); }
    finally { setLoading(false); }
  }

  async function runSampleReview() {
    setLoadingSample(true); setError("");
    try {
      const response = await fetch("/api/sample");
      if (!response.ok) throw new Error("演示合同加载失败");
      const payload = await response.json();
      setText(payload.text); setRole(payload.recommended_role); setFile(null);
      await runReview(payload.text, null, payload.recommended_role);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "演示合同加载失败"); }
    finally { setLoadingSample(false); }
  }

  async function loadReview(reviewId: string) {
    setError("");
    try {
      const response = await fetch(`/api/reviews/${reviewId}`);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "记录加载失败");
      setResult(payload); setActiveRiskId(payload.risks[0]?.risk_id || ""); setRiskStatuses({});
      setScreen("workspace"); setShowHistory(false); setShowOverview(true); setWorkspaceTab("risks");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "记录加载失败"); }
  }

  async function deleteReview() {
    if (!result || !window.confirm(`确定删除“${result.filename}”的审查记录吗？此操作无法撤销。`)) return;
    await fetch(`/api/reviews/${result.review_id}`, { method: "DELETE" });
    setResult(null); setScreen("home"); setShowOverview(false); await refreshHistory();
  }

  function selectRisk(risk: RiskItem) {
    setActiveRiskId(risk.risk_id); setWorkspaceTab("detail");
    window.setTimeout(() => document.getElementById(`block-${risk.source_block_ids[0]}`)?.scrollIntoView({ behavior: "smooth", block: "center" }), 40);
  }

  function setRiskStatus(status: RiskStatus) {
    if (!activeRisk) return;
    if (status === "ignored" && !window.confirm("确定暂时忽略这项风险吗？它仍会保留在报告中。")) return;
    setRiskStatuses((current) => ({ ...current, [activeRisk.risk_id]: status }));
  }

  async function copyValue(key: string, value: string) {
    await navigator.clipboard.writeText(value); setCopied(key); window.setTimeout(() => setCopied(""), 1600);
  }

  async function downloadReport() {
    if (!result) return;
    setExporting(true);
    try {
      const response = await fetch(`/api/reviews/${result.review_id}/export/docx`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ risk_statuses: riskStatuses }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || "Word 报告生成失败");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob); const link = document.createElement("a");
      link.href = url;
      link.download = `${result.filename.replace(/\.[^.]+$/, "")}-合同风险审查报告.docx`;
      document.body.appendChild(link); link.click(); link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (reason) {
      window.alert(reason instanceof Error ? reason.message : "Word 报告生成失败");
    } finally {
      setExporting(false);
    }
  }

  function startNewReview() {
    setScreen("home"); setResult(null); setShowOverview(false); setError(""); window.scrollTo({ top: 0 });
  }

  return (
    <div className={`app ${screen}`}>
      {screen === "home" ? (
        <>
          <header className="home-header">
            <Brand />
            <nav aria-label="主要操作">
              <span className="privacy-chip"><Icon name="shield" size={16}/> 合同全文不入库</span>
              <button className={`header-button ${aiStatus?.configured ? "connected" : ""}`} onClick={openAISettings}><span className="status-dot"/>{aiStatus?.configured ? "AI 已连接" : "连接 AI"}</button>
              <button className="header-button" onClick={() => setShowHistory(true)}><Icon name="history" size={17}/>近期审查 <b>{history.length}</b></button>
            </nav>
          </header>
          <main className="product-home">
            <section className="product-hero">
              <div className="hero-copy-new">
                <span className="eyebrow"><i/>HENGQI CONTRACT CONTROL DESK</span>
                <h1>让每一个合同风险，<br/><em>都有依据和下一步。</em></h1>
                <p>上传合同，快速找出付款、验收、责任与知识产权风险，并获得可以直接拿去协商的修改建议。</p>
              </div>
              <div className="hero-capabilities" aria-label="产品能力">
                <article><span>01</span><div><strong>联合审查</strong><small>原创规则与大模型交叉复核</small></div></article>
                <article><span>02</span><div><strong>证据链</strong><small>风险、原文与法条逐项绑定</small></div></article>
                <article><span>03</span><div><strong>处置闭环</strong><small>建议、底线、话术与进度</small></div></article>
              </div>
            </section>
            <section className="product-body">
              <form className="upload-card" onSubmit={(event) => { event.preventDefault(); void runReview(text, file, role); }}>
              <div className="upload-heading"><div><span>新建</span><div><h2>提交一份合同</h2><p>完成解析后进入审查工作台</p></div></div><button type="button" onClick={() => void runSampleReview()} disabled={loadingSample || loading}>{loadingSample ? "正在生成演示…" : "一键体验示例"}</button></div>
              <label className="form-label" htmlFor="party-role">我方签约身份</label>
              <select id="party-role" value={role} onChange={(event) => setRole(event.target.value)}>{roleOptions.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select>
              <label className={`dropzone ${dragging ? "dragging" : ""} ${file ? "has-file" : ""}`} htmlFor="contract-file" onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); const next = event.dataTransfer.files[0]; if (next) { setFile(next); setText(""); } }}>
                <input id="contract-file" type="file" accept=".docx,.pdf,.txt" onChange={(event) => { const next = event.target.files?.[0] || null; setFile(next); if (next) setText(""); }}/>
                <span className="upload-icon"><Icon name="upload" size={22}/></span>
                <span>{file ? <><strong>{file.name}</strong><small>{(file.size / 1024).toFixed(1)} KB · 点击更换</small></> : <><strong>拖入合同，或点击选择文件</strong><small>DOCX、文本型 PDF、TXT · 最大 10MB</small></>}</span>
              </label>
              <div className="divider"><span>或粘贴合同全文</span></div>
              <div className="textarea-box"><textarea value={text} onChange={(event) => { setText(event.target.value); if (event.target.value) setFile(null); }} rows={6} placeholder="将合同全文粘贴到这里，至少 30 个字符……"/><small>{text.length.toLocaleString()} 字符</small></div>
              {error && <div className="form-error" role="alert"><strong>暂时无法完成</strong><span>{error}</span></div>}
              <button className="primary-button" type="submit" disabled={submitDisabled}>{loading ? "正在审查合同…" : <><span>开始智能审查</span><Icon name="arrow" size={19}/></>}</button>
              <div className={`ai-strip ${aiStatus?.configured ? "connected" : ""}`}><span><i/>{aiStatus?.configured ? `${aiPresets[aiStatus.provider].label} · ${aiStatus.model}` : "当前为本地规则演示模式"}</span><button type="button" onClick={openAISettings}>{aiStatus?.configured ? "管理连接" : "连接 AI"}</button></div>
              <p className="privacy-note"><Icon name="shield" size={15}/> 文件仅在内存解析，结构化结果 24 小时后清理</p>
              {loading && <LoadingOverlay step={loadingStep}/>}
              </form>
              <aside className="home-control-rail">
                <article className={`control-card mode-card ${aiStatus?.configured ? "connected" : ""}`}>
                  <header><span className="control-icon">✦</span><small>审查引擎</small></header>
                  <strong>{aiStatus?.configured ? "规则＋AI 联合审查" : "本地规则演示模式"}</strong>
                  <p>{aiStatus?.configured ? `${aiPresets[aiStatus.provider].label} · ${aiStatus.model}` : "连接 AI 后，可补充跨条款与语义风险。"}</p>
                  <button onClick={openAISettings}>{aiStatus?.configured ? "管理 AI 连接" : "连接 AI 审查服务"}<Icon name="arrow" size={16}/></button>
                </article>
                <article className="control-card process-card">
                  <header><span className="control-icon"><Icon name="overview" size={18}/></span><small>一次审查怎么完成</small></header>
                  <ol>
                    <li><b>1</b><span><strong>提交合同</strong><small>上传文件或粘贴文本</small></span></li>
                    <li><b>2</b><span><strong>核对证据</strong><small>逐项查看原文与法条</small></span></li>
                    <li><b>3</b><span><strong>处理风险</strong><small>采用建议或记录沟通</small></span></li>
                  </ol>
                </article>
                <button className="recent-card" onClick={() => setShowHistory(true)}>
                  <span><Icon name="history" size={19}/></span><span><small>近期审查</small><strong>{history.length ? `${history.length} 份结果可查看` : "还没有审查记录"}</strong></span><Icon name="arrow" size={18}/>
                </button>
                <div className="privacy-control"><Icon name="shield" size={20}/><p><strong>合同全文不入库</strong><span>文件只在内存解析，历史记录仅保留证据摘录。</span></p></div>
              </aside>
            </section>
          </main>
          <footer className="home-footer"><Brand compact/><p>让合同审查从“看懂法条”变成“做出经营决策”</p></footer>
        </>
      ) : result ? (
        <Workspace
          result={result} activeRisk={activeRisk} filteredRisks={filteredRisks} statuses={riskStatuses}
          handledCount={handledCount} severityFilter={severityFilter} statusFilter={statusFilter}
          search={search} workspaceTab={workspaceTab} copied={copied}
          onNew={startNewReview} onHistory={() => setShowHistory(true)} onSettings={openAISettings}
          onOverview={() => setShowOverview(true)} onExport={() => void downloadReport()} exporting={exporting} onDelete={() => void deleteReview()}
          onSelectRisk={selectRisk} onSeverity={setSeverityFilter} onStatusFilter={setStatusFilter}
          onSearch={setSearch} onTab={setWorkspaceTab} onRiskStatus={setRiskStatus} onCopy={copyValue}
        />
      ) : null}

      {showOverview && result && <OverviewModal result={result} handledCount={handledCount} onClose={() => setShowOverview(false)} onDelete={() => void deleteReview()}/>}
      {showHistory && <HistoryDrawer history={history} onClose={() => setShowHistory(false)} onLoad={(id) => void loadReview(id)}/>}
      {showAISettings && <AISettingsModal status={aiStatus} provider={aiProvider} model={aiModel} apiKey={aiKey} remember={aiRemember} testing={aiTesting} error={aiError} success={aiSuccess} onClose={() => !aiTesting && setShowAISettings(false)} onProvider={(next) => { setAIProvider(next); setAIModel(aiPresets[next].model); setAIError(""); setAISuccess(""); }} onModel={setAIModel} onKey={setAIKey} onRemember={setAIRemember} onSubmit={connectAI} onClear={() => void clearAIConnection()}/>}
    </div>
  );
}

function Brand({ compact = false }: { compact?: boolean }) {
  return <div className={`brand ${compact ? "compact" : ""}`}><span className="brand-mark">衡</span><span><strong>衡契</strong><small>CONTRACT LENS</small></span></div>;
}

function LoadingOverlay({ step }: { step: number }) {
  return <div className="loading-overlay" aria-live="polite"><div className="scan-document"><span/></div><h3>正在审查合同</h3><p>{loadingSteps[step]}，请稍候…</p><ol>{loadingSteps.map((label, index) => <li className={index < step ? "done" : index === step ? "active" : ""} key={label}><span>{index < step ? <Icon name="check" size={14}/> : index + 1}</span><small>{label}</small></li>)}</ol></div>;
}

interface WorkspaceProps {
  result: ReviewResult; activeRisk: RiskItem | null; filteredRisks: RiskItem[]; statuses: Record<string, RiskStatus>;
  handledCount: number; severityFilter: "all" | Severity; statusFilter: "all" | "pending" | "handled";
  search: string; workspaceTab: WorkspaceTab; copied: string;
  exporting: boolean;
  onNew: () => void; onHistory: () => void; onSettings: () => void; onOverview: () => void; onExport: () => void; onDelete: () => void;
  onSelectRisk: (risk: RiskItem) => void; onSeverity: (value: "all" | Severity) => void; onStatusFilter: (value: "all" | "pending" | "handled") => void;
  onSearch: (value: string) => void; onTab: (value: WorkspaceTab) => void; onRiskStatus: (value: RiskStatus) => void; onCopy: (key: string, value: string) => Promise<void>;
}

function Workspace(props: WorkspaceProps) {
  const { result, activeRisk, filteredRisks, statuses, handledCount, severityFilter, statusFilter, search, workspaceTab, copied } = props;
  const highlighted = new Set(activeRisk?.source_block_ids || []);
  const hasDocument = result.document_blocks.length > 0;
  return <div className="workspace-shell">
    <header className="workspace-header">
      <button className="back-button" onClick={props.onNew}><Icon name="back" size={18}/><span>新审查</span></button>
      <Brand compact/>
      <div className="contract-title"><Icon name="file" size={20}/><div><strong>{result.filename}</strong><small>{result.summary.contract_type} · 我方为{result.summary.our_role} · {formatDate(result.created_at)}</small></div></div>
      <div className="workspace-actions">
        <span className={`engine-badge ${result.engine_mode}`}><i/>{engineLabel(result)}</span>
        <button onClick={props.onOverview}><Icon name="overview" size={17}/><span>总览</span></button>
        <button onClick={props.onExport} disabled={props.exporting}><Icon name="export" size={17}/><span>{props.exporting ? "生成中…" : "导出 Word"}</span></button>
        <button aria-label="近期审查" title="近期审查" onClick={props.onHistory}><Icon name="history"/></button>
        <button aria-label="AI 设置" title="AI 设置" onClick={props.onSettings}><Icon name="settings"/></button>
      </div>
    </header>

    <nav className="mobile-workspace-tabs" aria-label="工作台区域">
      {(["risks", "document", "detail"] as WorkspaceTab[]).map((tab) => <button className={workspaceTab === tab ? "active" : ""} onClick={() => props.onTab(tab)} key={tab}>{tab === "risks" ? `风险 ${result.risks.length}` : tab === "document" ? "原文" : "详情"}</button>)}
    </nav>

    <main className="workspace-grid">
      <aside className={`risk-sidebar workspace-panel ${workspaceTab === "risks" ? "mobile-active" : ""}`}>
        <div className="sidebar-summary">
          <div><span>处置进度</span><strong>{handledCount}<small> / {result.risks.length}</small></strong></div>
          <div className="progress-track"><span style={{ width: `${result.risks.length ? handledCount / result.risks.length * 100 : 0}%` }}/></div>
          <p>{handledCount === result.risks.length ? "风险已全部完成处置" : `还有 ${result.risks.length - handledCount} 项风险待处理`}</p>
        </div>
        <div className="risk-toolbar">
          <label><Icon name="search" size={17}/><input aria-label="搜索风险" value={search} onChange={(event) => props.onSearch(event.target.value)} placeholder="搜索风险或条款"/></label>
          <div className="compact-filters">
            <select aria-label="风险等级" value={severityFilter} onChange={(event) => props.onSeverity(event.target.value as "all" | Severity)}><option value="all">全部等级</option><option value="high">高风险</option><option value="medium">中风险</option><option value="low">低风险</option></select>
            <select aria-label="处理状态" value={statusFilter} onChange={(event) => props.onStatusFilter(event.target.value as "all" | "pending" | "handled")}><option value="all">全部状态</option><option value="pending">待处理</option><option value="handled">已处理</option></select>
          </div>
        </div>
        <div className="risk-list" aria-label="风险列表">
          {filteredRisks.map((risk, index) => {
            const status = statuses[risk.risk_id] || "pending";
            return <button className={`risk-list-item ${risk.risk_id === activeRisk?.risk_id ? "active" : ""} ${status !== "pending" ? "handled" : ""}`} onClick={() => props.onSelectRisk(risk)} key={risk.risk_id}>
              <span className={`risk-index ${risk.severity}`}>{status !== "pending" ? <Icon name="check" size={15}/> : String(index + 1).padStart(2, "0")}</span>
              <span className="risk-list-copy"><strong>{risk.title}</strong><small><b className={risk.severity}>{severityLabel[risk.severity]}</b>{categoryLabel[risk.category] || risk.category} · {riskStatusLabel[status]}</small></span>
              <Icon name="arrow" size={16}/>
            </button>;
          })}
          {!filteredRisks.length && <div className="list-empty">没有符合条件的风险<br/><small>调整筛选条件后再试试</small></div>}
        </div>
      </aside>

      <section className={`document-pane workspace-panel ${workspaceTab === "document" ? "mobile-active" : ""}`}>
        <div className="pane-heading"><div><span className="pane-kicker">SOURCE DOCUMENT</span><h2>合同原文</h2></div><span className="document-state"><i/>{hasDocument ? "本次会话可定位" : "历史记录仅保留摘录"}</span></div>
        {hasDocument ? <div className="document-paper">
          <div className="paper-heading"><span className="paper-seal">衡契</span><div><strong>{result.filename}</strong><small>{result.text_length.toLocaleString()} 字符 · 原文仅在当前会话展示</small></div></div>
          {result.document_blocks.map((block) => <article id={`block-${block.block_id}`} className={`document-block ${highlighted.has(block.block_id) ? "highlighted" : ""}`} key={block.block_id}><span>{block.block_id}</span><p>{block.text}</p>{highlighted.has(block.block_id) && <b>当前风险依据</b>}</article>)}
        </div> : <div className="evidence-history">
          <div className="privacy-callout"><Icon name="shield" size={22}/><div><strong>历史记录没有保存合同全文</strong><p>为保护合同隐私，数据库只保留审查结论和被引用的证据摘录。重新上传原合同后才能恢复全文定位。</p></div></div>
          {result.risks.filter((risk) => risk.quote).map((risk) => <button className={risk.risk_id === activeRisk?.risk_id ? "active" : ""} onClick={() => props.onSelectRisk(risk)} key={risk.risk_id}><small>{risk.source_block_ids.join("、")}</small><strong>{risk.title}</strong><p>“{risk.quote}”</p></button>)}
        </div>}
        {activeRisk?.risk_type === "missing_clause" && <div className="missing-evidence"><span>＋</span><div><strong>这是缺失型风险</strong><p>系统未在合同中发现相关约定，因此不会伪造原文位置。请在合同中补充相应条款。</p></div></div>}
      </section>

      <aside className={`detail-pane workspace-panel ${workspaceTab === "detail" ? "mobile-active" : ""}`}>
        {activeRisk ? <RiskDetail risk={activeRisk} status={statuses[activeRisk.risk_id] || "pending"} copied={copied} onStatus={props.onRiskStatus} onCopy={props.onCopy}/> : <div className="detail-empty">请选择一项风险</div>}
      </aside>
    </main>
  </div>;
}

function RiskDetail({ risk, status, copied, onStatus, onCopy }: { risk: RiskItem; status: RiskStatus; copied: string; onStatus: (value: RiskStatus) => void; onCopy: (key: string, value: string) => Promise<void> }) {
  return <div className="risk-detail">
    <div className="detail-heading">
      <div className="risk-tags"><span className={`severity-tag ${risk.severity}`}>{severityLabel[risk.severity]}</span><span>{categoryLabel[risk.category] || risk.category}</span><span>{risk.source === "ai" ? "AI 补充" : "原创规则"}</span></div>
      <span className={`status-badge ${status}`}>{riskStatusLabel[status]}</span>
    </div>
    <h1>{risk.title}</h1>
    <div className={`legal-conclusion ${risk.legal_nature}`}><span>§ {legalNatureLabel[risk.legal_nature]}</span><p>{risk.legal_conclusion}</p></div>
    <section className="detail-section"><h2>可能造成的经营后果</h2><p>{risk.business_impact}</p></section>
    <section className="revision-card"><div><h2>建议修改文本</h2><button onClick={() => void onCopy("revision", risk.ideal_revision)}><Icon name="copy" size={16}/>{copied === "revision" ? "已复制" : "复制"}</button></div><p>{risk.ideal_revision}</p></section>
    <details className="negotiation-details" open><summary>协商方案与谈判底线 <span>⌄</span></summary><dl><div><dt>可接受折中方案</dt><dd>{risk.compromise_revision}</dd></div><div><dt>最低底线</dt><dd>{risk.bottom_line}</dd></div><div><dt>沟通话术 <button onClick={() => void onCopy("talk", risk.negotiation_message)}>{copied === "talk" ? "已复制" : "复制话术"}</button></dt><dd>{risk.negotiation_message}</dd></div></dl></details>
    <section className="basis-section"><div className="section-title"><h2>法律依据</h2><span>{risk.legal_bases.length ? `${risk.legal_bases.length} 条已核验` : "无直接法条"}</span></div>
      {risk.legal_bases.length ? risk.legal_bases.map((basis) => <details className="basis-card" key={basis.basis_id}><summary><span><strong>{basis.document_name}</strong>{basis.article_number}</span><b>{basis.effective_status}</b></summary><div><blockquote>{basis.article_excerpt}</blockquote><p><strong>适用说明：</strong>{basis.application_note}</p>{basis.limitations.length > 0 && <p><strong>适用边界：</strong>{basis.limitations.join("；")}</p>}<footer><a href={basis.official_url} target="_blank" rel="noreferrer"><Icon name="link" size={15}/>官方来源</a><small>人工核验：{basis.verified_at}</small></footer></div></details>) : <div className="no-basis">该项主要提示交易利益或执行成本，不能据此直接认定条款违法或无效。</div>}
    </section>
    <div className="status-actions"><span>处理这项风险</span><div><button className={status === "adopted" ? "active" : ""} onClick={() => onStatus("adopted")}><Icon name="check" size={17}/>采用建议</button><button className={status === "communicated" ? "active" : ""} onClick={() => onStatus("communicated")}>已沟通</button><button className={status === "ignored" ? "active ignored" : ""} onClick={() => onStatus("ignored")}>暂时忽略</button>{status !== "pending" && <button className="reset-status" onClick={() => onStatus("pending")}>恢复待处理</button>}</div></div>
  </div>;
}

function OverviewModal({ result, handledCount, onClose, onDelete }: { result: ReviewResult; handledCount: number; onClose: () => void; onDelete: () => void }) {
  const advice = result.risk_bill.high ? "建议修改后再签署" : result.risk_bill.medium ? "建议协商优化后签署" : "当前风险相对可控";
  return <div className="modal-backdrop" onMouseDown={onClose}><section className="overview-modal" role="dialog" aria-modal="true" aria-labelledby="overview-title" onMouseDown={(event) => event.stopPropagation()}>
    <header><div><span>REVIEW OVERVIEW</span><h2 id="overview-title">审查总览</h2><p>{result.filename}</p></div><button aria-label="关闭审查总览" onClick={onClose}><Icon name="close" size={21}/></button></header>
    <div className="decision-banner"><div><span>当前签约建议</span><strong>{advice}</strong><p>优先处理高风险条款，再确认交易底线。</p></div><div className="overview-progress"><strong>{handledCount}<small> / {result.risks.length}</small></strong><span>已处理风险</span></div></div>
    <div className="metric-row"><div className="high"><span>高风险</span><strong>{result.risk_bill.high}</strong><small>签约前必须处理</small></div><div className="medium"><span>中风险</span><strong>{result.risk_bill.medium}</strong><small>建议协商优化</small></div><div className="low"><span>低风险</span><strong>{result.risk_bill.low}</strong><small>留意执行细节</small></div></div>
    {result.warnings.length > 0 && <div className="overview-warning">{result.warnings.map((warning) => <p key={warning}>⚠ {warning}</p>)}</div>}
    <div className="overview-columns"><article><h3>签约前必须处理</h3><ol>{result.summary.must_fix.map((item, index) => <li key={item}><b>{index + 1}</b><span>{item}</span></li>)}</ol></article><article><h3>合同关键摘要</h3>{result.summary.key_terms.length ? <ul>{result.summary.key_terms.map((item) => <li key={item}>{item}</li>)}</ul> : <p>未提取到明确的金额、付款、期限或验收摘要。</p>}</article></div>
    <div className="exposure-row">{[["付款", result.risk_bill.payment_exposure], ["验收", result.risk_bill.acceptance_exposure], ["责任", result.risk_bill.liability_exposure], ["知识产权", result.risk_bill.ip_exposure]].map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
    <div className="library-note"><span>§</span><div><strong>可核验法律依据库 · {result.legal_library_version}</strong><small>官方来源白名单 · 核验于 {result.legal_library_verified_at || "未记录"} · 商业风险不会冒充违法认定</small></div></div>
    <footer><button className="danger-link" onClick={onDelete}>删除这条审查记录</button><button className="primary-small" onClick={onClose}>开始逐项处理 <Icon name="arrow" size={17}/></button></footer>
  </section></div>;
}

function HistoryDrawer({ history, onClose, onLoad }: { history: ReviewListItem[]; onClose: () => void; onLoad: (id: string) => void }) {
  return <div className="drawer-backdrop" onMouseDown={onClose}><aside className="history-drawer" role="dialog" aria-modal="true" aria-labelledby="history-title" onMouseDown={(event) => event.stopPropagation()}><header><div><span>RECENT REVIEWS</span><h2 id="history-title">近期审查</h2></div><button aria-label="关闭近期审查" onClick={onClose}><Icon name="close" size={21}/></button></header><div className="drawer-privacy"><Icon name="shield" size={20}/><p>只保存结构化结果，不保存合同全文；记录 24 小时后自动清理。</p></div><div className="history-list">{history.map((item) => <button onClick={() => onLoad(item.review_id)} key={item.review_id}><span className={item.high_risks ? "has-high" : ""}>{item.high_risks}</span><span><strong>{item.filename}</strong><small>{item.contract_type} · {item.total_risks} 项风险 · {formatDate(item.created_at)}</small></span><Icon name="arrow" size={17}/></button>)}{!history.length && <div className="history-empty"><Icon name="history" size={32}/><strong>还没有审查记录</strong><p>完成第一次审查后会显示在这里。</p></div>}</div></aside></div>;
}

interface AISettingsProps {
  status: AISettingsStatus | null; provider: AIProvider; model: string; apiKey: string; remember: boolean; testing: boolean; error: string; success: string;
  onClose: () => void; onProvider: (value: AIProvider) => void; onModel: (value: string) => void; onKey: (value: string) => void; onRemember: (value: boolean) => void; onSubmit: (event: FormEvent) => Promise<void>; onClear: () => void;
}

function AISettingsModal(props: AISettingsProps) {
  return <div className="modal-backdrop" onMouseDown={props.onClose}><section className="settings-modal" role="dialog" aria-modal="true" aria-labelledby="settings-title" onMouseDown={(event) => event.stopPropagation()}><header><div><span className="settings-symbol">✦</span><div><small>AI CONNECTION</small><h2 id="settings-title">连接 AI 审查服务</h2></div></div><button aria-label="关闭 AI 设置" onClick={props.onClose} disabled={props.testing}><Icon name="close" size={21}/></button></header><div className={`current-connection ${props.status?.configured ? "connected" : ""}`}><span><i/>{props.status?.configured ? "当前已连接" : "当前未连接"}</span><strong>{props.status?.configured ? `${aiPresets[props.status.provider].label} · ${props.status.key_hint}` : "合同将使用本地原创规则审查"}</strong></div><form onSubmit={(event) => void props.onSubmit(event)}><label className="settings-label">选择 API 服务</label><div className="provider-grid">{(Object.keys(aiPresets) as AIProvider[]).map((provider) => <button className={props.provider === provider ? "active" : ""} type="button" onClick={() => props.onProvider(provider)} disabled={props.testing} key={provider}><span>{provider === "siliconflow" ? "SF" : "DS"}</span><span><strong>{aiPresets[provider].label}</strong><small>{aiPresets[provider].note}</small></span>{props.provider === provider && <Icon name="check" size={17}/>}</button>)}</div><label className="settings-label" htmlFor="api-key">API Key</label><input id="api-key" className="settings-input" type="password" value={props.apiKey} onChange={(event) => props.onKey(event.target.value)} placeholder={props.status?.configured ? "输入新密钥以更换连接" : "粘贴你的 API 密钥"} autoComplete="off" required minLength={16} disabled={props.testing}/><label className="settings-label" htmlFor="ai-model">模型名称</label><input id="ai-model" className="settings-input" value={props.model} onChange={(event) => props.onModel(event.target.value)} required disabled={props.testing}/><p className="endpoint">接口地址：<code>{aiPresets[props.provider].baseUrl}</code></p><label className={`remember-option ${props.remember ? "selected" : ""}`}><input type="checkbox" checked={props.remember} onChange={(event) => props.onRemember(event.target.checked)} disabled={props.testing}/><Icon name="shield" size={21}/><span><strong>安全记住在这台电脑</strong><small>{props.remember ? "由当前 Windows 账户加密保存，重启后自动恢复。" : "仅保存在服务内存，停止衡契后自动消失。"}</small></span></label>{props.error && <div className="settings-message error">{props.error}</div>}{props.success && <div className="settings-message success">{props.success}</div>}<footer>{props.status?.configured && <button className="clear-button" type="button" onClick={props.onClear} disabled={props.testing}>清除连接和密钥</button>}<button className="connect-button" type="submit" disabled={props.testing || props.apiKey.trim().length < 16}>{props.testing ? "正在测试连接…" : "测试并连接"}</button></footer></form></section></div>;
}
