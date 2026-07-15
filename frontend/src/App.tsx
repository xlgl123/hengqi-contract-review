import { CSSProperties, FormEvent, useEffect, useMemo, useRef, useState } from "react";

type Severity = "high" | "medium" | "low";
type EngineMode = "hybrid_ai" | "rules_demo" | "hybrid_fallback";
type SourceFilter = "all" | "rule" | "ai";

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
  ideal_revision: string;
  compromise_revision: string;
  bottom_line: string;
  negotiation_message: string;
  confidence: string;
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

const roleOptions = [
  ["service_provider", "乙方 / 服务提供方"],
  ["customer", "甲方 / 客户方"],
  ["seller", "销售方"],
  ["buyer", "采购方"],
];

const severityLabel: Record<Severity, string> = {
  high: "高风险",
  medium: "中风险",
  low: "低风险",
};

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
};

const loadingSteps = ["解析合同结构", "运行原创规则", "AI交叉复核", "生成经营建议"];

function engineLabel(result: ReviewResult): string {
  if (result.engine_mode === "hybrid_ai") return `AI＋规则联合审查 · ${result.model_name}`;
  if (result.engine_mode === "hybrid_fallback") return "AI服务异常 · 已安全降级";
  return "本地规则演示 · 未调用AI";
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function buildMarkdown(result: ReviewResult): string {
  const risks = result.risks.map((risk, index) => `
## ${index + 1}. [${severityLabel[risk.severity]}] ${risk.title}

- 风险领域：${categoryLabel[risk.category] || risk.category}
- 发现方式：${risk.source === "ai" ? "AI补充" : "原创规则"}
- 原文位置：${risk.source_block_ids.join("、") || "缺失条款"}
- 原文引用：${risk.quote || "合同中未约定"}
- 经营后果：${risk.business_impact}
- 理想修改：${risk.ideal_revision}
- 可接受方案：${risk.compromise_revision}
- 最低底线：${risk.bottom_line}
- 沟通话术：${risk.negotiation_message}
`).join("\n");

  return `# ${result.filename}｜合同风险审查报告

生成时间：${new Date(result.created_at).toLocaleString("zh-CN")}  
合同类型：${result.summary.contract_type}  
我方身份：${result.summary.our_role}  
审查引擎：${engineLabel(result)}  

> 本报告用于签约前经营风险辅助识别，不替代律师针对具体交易出具法律意见。

## 风险总览

- 风险总数：${result.risk_bill.total_risks}
- 高风险：${result.risk_bill.high}
- 中风险：${result.risk_bill.medium}
- 低风险：${result.risk_bill.low}

## 签约前必须处理

${result.summary.must_fix.map((item, index) => `${index + 1}. ${item}`).join("\n")}

# 风险明细
${risks}`;
}

export default function App() {
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [role, setRole] = useState("service_provider");
  const [loading, setLoading] = useState(false);
  const [loadingSample, setLoadingSample] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ReviewResult | null>(null);
  const [history, setHistory] = useState<ReviewListItem[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [severityFilter, setSeverityFilter] = useState<"all" | Severity>("all");
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [copiedId, setCopiedId] = useState("");
  const demoStarted = useRef(false);

  const submitDisabled = useMemo(
    () => loading || (!file && text.trim().length < 30),
    [file, loading, text],
  );

  const score = useMemo(() => {
    if (!result) return 100;
    return Math.max(0, 100 - result.risk_bill.high * 12 - result.risk_bill.medium * 5 - result.risk_bill.low * 2);
  }, [result]);

  const categories = useMemo(() => {
    if (!result) return [];
    return Array.from(new Set(result.risks.map((risk) => risk.category)));
  }, [result]);

  const filteredRisks = useMemo(() => {
    if (!result) return [];
    const keyword = search.trim().toLowerCase();
    return result.risks.filter((risk) => {
      if (severityFilter !== "all" && risk.severity !== severityFilter) return false;
      if (sourceFilter !== "all" && risk.source !== sourceFilter) return false;
      if (categoryFilter !== "all" && risk.category !== categoryFilter) return false;
      if (!keyword) return true;
      return [risk.title, risk.quote, risk.business_impact, risk.ideal_revision]
        .join(" ")
        .toLowerCase()
        .includes(keyword);
    });
  }, [categoryFilter, result, search, severityFilter, sourceFilter]);

  async function refreshHistory() {
    try {
      const response = await fetch("/api/reviews?limit=8");
      if (response.ok) setHistory(await response.json());
    } catch {
      // 历史记录不是主流程，离线时静默保留当前页面。
    }
  }

  async function runReview(inputText: string, inputFile: File | null, selectedRole: string, scroll = true) {
    setLoading(true);
    setLoadingStep(0);
    setError("");
    setResult(null);
    const body = new FormData();
    body.append("party_role", selectedRole);
    if (inputFile) body.append("file", inputFile);
    else body.append("text", inputText);

    try {
      const response = await fetch("/api/reviews", { method: "POST", body });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "合同审查失败");
      setResult(payload);
      setSeverityFilter("all");
      setSourceFilter("all");
      setCategoryFilter("all");
      setSearch("");
      await refreshHistory();
      if (scroll) requestAnimationFrame(() => document.getElementById("review-result")?.scrollIntoView({ behavior: "smooth" }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "合同审查失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshHistory();
    if (new URLSearchParams(window.location.search).get("demo") !== "1" || demoStarted.current) return;
    demoStarted.current = true;
    void (async () => {
      setLoadingSample(true);
      try {
        const response = await fetch("/api/sample");
        if (!response.ok) throw new Error("示例合同加载失败");
        const sample = await response.json();
        setText(sample.text);
        setRole(sample.recommended_role);
        await runReview(sample.text, null, sample.recommended_role, false);
      } catch (err) {
        setError(err instanceof Error ? err.message : "演示审查失败");
      } finally {
        setLoadingSample(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (!loading) return;
    const timer = window.setInterval(() => setLoadingStep((current) => Math.min(current + 1, loadingSteps.length - 1)), 6500);
    return () => window.clearInterval(timer);
  }, [loading]);

  async function loadSample() {
    setLoadingSample(true);
    setError("");
    try {
      const response = await fetch("/api/sample");
      if (!response.ok) throw new Error("示例合同加载失败");
      const payload = await response.json();
      setText(payload.text);
      setRole(payload.recommended_role);
      setFile(null);
      setResult(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "示例合同加载失败");
    } finally {
      setLoadingSample(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void runReview(text, file, role);
  }

  function selectFile(nextFile: File | null) {
    setFile(nextFile);
    if (nextFile) setText("");
    setError("");
  }

  async function loadReview(reviewId: string) {
    setError("");
    try {
      const response = await fetch(`/api/reviews/${reviewId}`);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "记录加载失败");
      setResult(payload);
      setShowHistory(false);
      requestAnimationFrame(() => document.getElementById("review-result")?.scrollIntoView({ behavior: "smooth" }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "记录加载失败");
    }
  }

  async function deleteCurrentReview() {
    if (!result) return;
    await fetch(`/api/reviews/${result.review_id}`, { method: "DELETE" });
    setResult(null);
    await refreshHistory();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function downloadReport() {
    if (!result) return;
    const blob = new Blob([buildMarkdown(result)], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${result.filename.replace(/\.[^.]+$/, "")}-风险审查报告.md`;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function copyText(id: string, value: string) {
    await navigator.clipboard.writeText(value);
    setCopiedId(id);
    window.setTimeout(() => setCopiedId(""), 1800);
  }

  return (
    <div className="app-shell">
      <header className="site-header">
        <a className="brand" href="#top" aria-label="衡契首页">
          <span className="brand-mark">衡</span>
          <span><strong>衡契</strong><small>Contract Lens</small></span>
        </a>
        <nav>
          <span className="privacy-pill"><i /> 合同文本不入库</span>
          <button className="nav-button" type="button" onClick={() => setShowHistory(true)}>
            近期审查 <b>{history.length}</b>
          </button>
        </nav>
      </header>

      <main id="top">
        <section className="hero">
          <div className="hero-glow hero-glow-one" />
          <div className="hero-glow hero-glow-two" />
          <div className="hero-layout">
            <div className="hero-copy">
              <span className="eyebrow"><i /> 面向中小企业的签约风险雷达</span>
              <h1>签合同之前，<br /><em>先看清风险账。</em></h1>
              <p>从合同原文出发，把晦涩条款翻译成经营后果、修改方案和可直接使用的谈判话术。</p>
              <div className="hero-proof">
                <div><strong>双引擎</strong><span>原创规则＋大模型</span></div>
                <div><strong>可核验</strong><span>风险定位到原文</span></div>
                <div><strong>可执行</strong><span>给方案也给底线</span></div>
              </div>
            </div>

            <form className="review-panel" onSubmit={submit}>
              <div className="panel-heading">
                <div><span className="step-number">01</span><div><h2>提交合同</h2><p>约1分钟生成经营风险清单</p></div></div>
                <button className="text-button" type="button" onClick={loadSample} disabled={loadingSample}>
                  {loadingSample ? "加载中…" : "使用演示合同"}
                </button>
              </div>

              <label className="field-label" htmlFor="role">我方签约身份</label>
              <select id="role" value={role} onChange={(event) => setRole(event.target.value)}>
                {roleOptions.map(([value, label]) => <option value={value} key={value}>{label}</option>)}
              </select>

              <label
                className={`drop-zone ${dragging ? "dragging" : ""} ${file ? "has-file" : ""}`}
                htmlFor="contract-file"
                onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={(event) => {
                  event.preventDefault();
                  setDragging(false);
                  selectFile(event.dataTransfer.files[0] || null);
                }}
              >
                <input
                  id="contract-file"
                  type="file"
                  accept=".docx,.pdf,.txt"
                  onChange={(event) => selectFile(event.target.files?.[0] || null)}
                />
                <span className="upload-icon">↥</span>
                {file ? (
                  <span><strong>{file.name}</strong><small>{(file.size / 1024).toFixed(1)} KB · 点击可更换</small></span>
                ) : (
                  <span><strong>拖入合同，或点击选择文件</strong><small>支持 DOCX、文本型 PDF、TXT · 最大10MB</small></span>
                )}
              </label>

              <div className="or-divider"><span>或粘贴合同文本</span></div>
              <div className="textarea-wrap">
                <textarea
                  value={text}
                  onChange={(event) => { setText(event.target.value); if (event.target.value) setFile(null); }}
                  placeholder="将合同全文粘贴到这里，至少30个字符……"
                  rows={7}
                />
                <small>{text.length.toLocaleString()} 字符</small>
              </div>

              {error && <div className="error" role="alert"><strong>暂时无法完成：</strong>{error}</div>}
              <button className="primary-action" type="submit" disabled={submitDisabled}>
                {loading ? "正在审查合同…" : <><span>开始智能审查</span><b>→</b></>}
              </button>
              <p className="privacy-note">🔒 文件仅在内存中解析，结果24小时后自动清理</p>

              {loading && (
                <div className="loading-layer" aria-live="polite">
                  <div className="scanner"><span /></div>
                  <h3>正在审查合同</h3>
                  <p>{loadingSteps[loadingStep]}，请稍候…</p>
                  <ol>
                    {loadingSteps.map((step, index) => (
                      <li className={index < loadingStep ? "done" : index === loadingStep ? "active" : ""} key={step}>
                        <span>{index < loadingStep ? "✓" : index + 1}</span>{step}
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </form>
          </div>
        </section>

        <section className="how-it-works" aria-label="产品流程">
          <span>上传或粘贴合同</span><i>→</i><span>定位高风险条款</span><i>→</i><span>获得三档修改方案</span><i>→</i><span>导出审查报告</span>
        </section>

        {result && (
          <section id="review-result" className="results-shell" aria-label="审查结果">
            <div className="report-header">
              <div>
                <span className="section-kicker">REVIEW REPORT · 审查完成</span>
                <h2>{result.filename}</h2>
                <p>{result.summary.contract_type} · 我方为{result.summary.our_role} · {formatDate(result.created_at)}</p>
              </div>
              <div className="report-actions">
                <span className={`engine ${result.engine_mode}`}><i />{engineLabel(result)}</span>
                <button type="button" onClick={downloadReport}>↓ 导出报告</button>
                <button className="ghost-danger" type="button" onClick={deleteCurrentReview}>删除记录</button>
              </div>
            </div>

            {result.warnings.map((warning) => <div className="warning" key={warning}>⚠ {warning}</div>)}

            <div className="overview-grid">
              <article className="score-card">
                <div className="score-ring" style={{ "--score": `${score * 3.6}deg` } as CSSProperties}>
                  <span><strong>{score}</strong><small>签约安全分</small></span>
                </div>
                <div><span className="card-label">风险总览</span><h3>{score < 50 ? "暂不建议直接签署" : score < 75 ? "建议修改后签署" : "整体风险可控"}</h3><p>优先处理高风险条款，再确认交易底线。</p></div>
              </article>
              <article className="metric-card high"><span>高风险</span><strong>{result.risk_bill.high}</strong><small>签约前必须处理</small></article>
              <article className="metric-card medium"><span>中风险</span><strong>{result.risk_bill.medium}</strong><small>建议协商优化</small></article>
              <article className="metric-card low"><span>低风险</span><strong>{result.risk_bill.low}</strong><small>留意执行细节</small></article>
            </div>

            <div className="insight-grid">
              <article className="must-fix-card">
                <div className="card-title"><span>!</span><div><small>PRIORITY</small><h3>签约前必须处理</h3></div></div>
                <ol>{result.summary.must_fix.map((item, index) => <li key={`${item}-${index}`}><b>{index + 1}</b><span>{item}</span></li>)}</ol>
              </article>
              <article className="terms-card">
                <div className="card-title"><span>≡</span><div><small>KEY TERMS</small><h3>合同关键摘要</h3></div></div>
                {result.summary.key_terms.length ? (
                  <ul>{result.summary.key_terms.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul>
                ) : <p>未提取到明确的金额、付款、期限或验收摘要。</p>}
              </article>
            </div>

            <div className="exposure-grid">
              {[
                ["付款暴露", result.risk_bill.payment_exposure],
                ["验收暴露", result.risk_bill.acceptance_exposure],
                ["责任暴露", result.risk_bill.liability_exposure],
                ["知识产权", result.risk_bill.ip_exposure],
              ].map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}
            </div>

            <div className="risk-section">
              <div className="risk-section-heading">
                <div><span className="section-kicker">RISK DETAILS</span><h2>风险明细 <b>{filteredRisks.length}</b></h2></div>
                <div className="filter-row">
                  <input aria-label="搜索风险" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索条款或建议" />
                  <select aria-label="风险领域" value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)}>
                    <option value="all">全部领域</option>
                    {categories.map((category) => <option key={category} value={category}>{categoryLabel[category] || category}</option>)}
                  </select>
                  <select aria-label="发现方式" value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value as SourceFilter)}>
                    <option value="all">全部来源</option><option value="rule">原创规则</option><option value="ai">AI补充</option>
                  </select>
                </div>
              </div>

              <div className="severity-tabs" role="tablist">
                {(["all", "high", "medium", "low"] as const).map((value) => (
                  <button className={severityFilter === value ? "active" : ""} type="button" key={value} onClick={() => setSeverityFilter(value)}>
                    {value === "all" ? "全部风险" : severityLabel[value]}
                    <b>{value === "all" ? result.risks.length : result.risks.filter((risk) => risk.severity === value).length}</b>
                  </button>
                ))}
              </div>

              {filteredRisks.length ? (
                <div className="risk-grid">
                  {filteredRisks.map((risk, index) => (
                    <article className={`risk-card ${risk.severity}`} key={risk.risk_id}>
                      <div className="risk-card-top">
                        <span className={`severity ${risk.severity}`}><i />{severityLabel[risk.severity]}</span>
                        <span className="category">{categoryLabel[risk.category] || risk.category}</span>
                        <span className="source">{risk.source === "ai" ? "AI补充" : "原创规则"}</span>
                      </div>
                      <h3><small>{String(index + 1).padStart(2, "0")}</small>{risk.title}</h3>
                      {risk.quote ? (
                        <blockquote><span>“{risk.quote}”</span><small>定位：{risk.source_block_ids.join("、")}</small></blockquote>
                      ) : <div className="missing-clause">合同中缺少相关约定</div>}
                      <div className="impact"><span>经营后果</span><p>{risk.business_impact}</p></div>
                      <div className="revision-box">
                        <div><span>建议修改</span><button type="button" onClick={() => void copyText(`${risk.risk_id}-revision`, risk.ideal_revision)}>{copiedId === `${risk.risk_id}-revision` ? "已复制 ✓" : "复制"}</button></div>
                        <p>{risk.ideal_revision}</p>
                      </div>
                      <details>
                        <summary>查看协商方案与沟通话术 <span>＋</span></summary>
                        <dl>
                          <div><dt>可接受方案</dt><dd>{risk.compromise_revision}</dd></div>
                          <div><dt>最低底线</dt><dd>{risk.bottom_line}</dd></div>
                          <div className="talk-track"><dt>沟通话术</dt><dd>{risk.negotiation_message}<button type="button" onClick={() => void copyText(`${risk.risk_id}-talk`, risk.negotiation_message)}>{copiedId === `${risk.risk_id}-talk` ? "已复制" : "复制话术"}</button></dd></div>
                        </dl>
                      </details>
                    </article>
                  ))}
                </div>
              ) : <div className="empty-state"><strong>没有符合条件的风险</strong><span>调整筛选条件后再试试。</span></div>}
            </div>

            <div className="report-disclaimer">本结果用于签约前经营风险辅助识别，不替代律师针对具体交易出具法律意见。AI结果均经过原文引用校验，仍建议结合实际交易背景复核。</div>
          </section>
        )}
      </main>

      <footer className="site-footer"><div><span className="brand-mark">衡</span><strong>衡契 · 中小企业合同风险助手</strong></div><p>让合同审查从“看懂法律”变成“做出经营决策”</p></footer>

      {showHistory && (
        <div className="drawer-backdrop" onMouseDown={() => setShowHistory(false)}>
          <aside className="history-drawer" onMouseDown={(event) => event.stopPropagation()} aria-label="近期审查记录">
            <div className="drawer-heading"><div><small>RECENT REVIEWS</small><h2>近期审查</h2></div><button type="button" onClick={() => setShowHistory(false)}>×</button></div>
            <p className="drawer-note">仅保存结构化结果，不保存合同全文；记录24小时后自动清理。</p>
            {history.length ? <div className="history-list">{history.map((item) => (
              <button type="button" key={item.review_id} onClick={() => void loadReview(item.review_id)}>
                <span className={`history-risk ${item.high_risks ? "has-high" : ""}`}>{item.high_risks}</span>
                <span><strong>{item.filename}</strong><small>{item.contract_type} · {item.total_risks}项风险 · {formatDate(item.created_at)}</small></span>
                <b>›</b>
              </button>
            ))}</div> : <div className="empty-history"><span>◌</span><strong>还没有审查记录</strong><p>完成第一次审查后会显示在这里。</p></div>}
          </aside>
        </div>
      )}
    </div>
  );
}
