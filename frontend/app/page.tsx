"use client";

import { FormEvent, useMemo, useRef, useState } from "react";
import ArchitectureDashboard from "@/components/dashboard/architecturedashboard";
import VoiceOrb from "@/components/voice/voiceorb";
import { useVoice } from "@/hooks/usevoice";
import type { ConversationTurn, DemoDocument, Provenance } from "@/lib/voice/types";

const provenanceLabel = (value?: Provenance) => {
  if (value === "document") return "Domain knowledge";
  if (value === "not_in_source") return "Not available in source";
  return "General knowledge";
};

function SourceOptions({
  demos,
  uploading,
  activeSlug,
  onDemo,
}: {
  demos: DemoDocument[];
  uploading: boolean;
  activeSlug?: string;
  onDemo(slug: string): void;
}) {
  return (
    <div className="demo-source-list">
      {demos.map((demo) => (
        <button
          type="button"
          className="demo-source"
          key={demo.slug}
          onClick={() => onDemo(demo.slug)}
          disabled={uploading || activeSlug === demo.slug}
        >
          <span className="file-format">{demo.format}</span>
          <span>
            <strong>{demo.title}</strong>
            <small>{demo.description}</small>
          </span>
          <span className="source-action">
            {activeSlug === demo.slug ? "Active" : uploading ? "Preparing..." : "Use demo"}
          </span>
        </button>
      ))}
    </div>
  );
}

function ConversationTimeline({
  turns,
  interim,
  restoredState,
}: {
  turns: ConversationTurn[];
  interim: string;
  restoredState: string;
}) {
  const [historyExpanded, setHistoryExpanded] = useState(false);
  const [panelCollapsed, setPanelCollapsed] = useState(false);
  const hiddenCount = Math.max(0, turns.length - 2);
  const visibleTurns = historyExpanded ? turns : turns.slice(-2);

  return (
    <section className="conversation-panel" data-collapsed={panelCollapsed} aria-labelledby="conversation-title">
      <div className="section-heading-row">
        <div>
          <p className="section-label">Live transcript</p>
          <h2 id="conversation-title">Conversation</h2>
        </div>
        <div className="panel-heading-actions">
          {restoredState && <span className="restored-chip">{restoredState}</span>}
          <button className="panel-control" type="button" onClick={() => setPanelCollapsed((value) => !value)} aria-expanded={!panelCollapsed}>
            {panelCollapsed ? "Open" : "Collapse"}
          </button>
        </div>
      </div>

      {!panelCollapsed && <div className="conversation-scroll" aria-live="polite" aria-relevant="additions text">
        {hiddenCount > 0 && (
          <button className="history-toggle" type="button" onClick={() => setHistoryExpanded((value) => !value)}>
            {historyExpanded ? "Show latest exchange" : `Show history (${hiddenCount})`}
          </button>
        )}
        {visibleTurns.map((turn) => (
          <article className="conversation-turn" data-role={turn.role} key={turn.id}>
            <div className="turn-meta">
              <strong>{turn.role === "assistant" ? "Via" : "You"}</strong>
              <time>{new Date(turn.createdAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time>
            </div>
            <p>{turn.text || <span className="response-skeleton">Preparing a response</span>}</p>
            {turn.role === "assistant" && turn.text && (
              <footer className="turn-evidence">
                <span className="provenance" data-type={turn.provenance ?? "general"}>
                  {provenanceLabel(turn.provenance)}
                </span>
                {typeof turn.metrics?.serverResponseMs === "number" && (
                  <span>{turn.metrics.serverResponseMs} ms server</span>
                )}
                {turn.interrupted && <span className="interrupted-tag">Interrupted</span>}
              </footer>
            )}
          </article>
        ))}
        {interim && (
          <article className="conversation-turn interim-turn" data-role="user">
            <div className="turn-meta"><strong>You</strong><span>listening</span></div>
            <p>{interim}</p>
          </article>
        )}
        {!turns.length && !interim && (
          <div className="teaching-empty conversation-empty">
            <span className="empty-mark">V</span>
            <strong>Your conversation will appear here</strong>
            <p>Start listening and ask Via anything. Add a source only when you want grounded, domain-specific answers.</p>
          </div>
        )}
      </div>}
    </section>
  );
}

export default function HomePage() {
  const [entered, setEntered] = useState(false);
  const [workspace, setWorkspace] = useState<"session" | "architecture">("session");
  const [sourceOpen, setSourceOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const voice = useVoice();

  const latestAssistant = useMemo(
    () => [...voice.conversation].reverse().find((turn) => turn.role === "assistant"),
    [voice.conversation],
  );

  const startVia = () => {
    setEntered(true);
    void voice.connect();
  };

  const submitUpload = (event: FormEvent) => {
    event.preventDefault();
    if (file) void voice.uploadDocument(file);
  };

  const chooseDemo = (slug: string) => {
    void voice.loadDemoDocument(slug);
    setEntered(true);
  };

  return (
    <main className="app-shell">
      <a href="#main-content" className="skip-link">Skip to main content</a>
      <header className="site-header">
        <button className="brand" type="button" onClick={() => setEntered(false)} aria-label="Via home">
          <span className="brand-mark">V</span>
          <span><strong>Via</strong><small>Adaptive voice intelligence</small></span>
        </button>

        {entered ? (
          <div className="header-actions">
            <div className="workspace-switch" role="tablist" aria-label="Workspace">
              <button
                role="tab"
                aria-selected={workspace === "session"}
                onClick={() => setWorkspace("session")}
              >
                Voice session
              </button>
              <button
                role="tab"
                aria-selected={workspace === "architecture"}
                onClick={() => setWorkspace("architecture")}
              >
                Architecture
              </button>
            </div>
            <button className="source-trigger" type="button" onClick={() => setSourceOpen((open) => !open)}>
              <span className="status-dot" data-status={voice.activeDocument ? "ready" : "idle"} />
              {voice.activeDocument ? voice.activeDocument.filename : "Add knowledge"}
            </button>
          </div>
        ) : (
          <div className="header-proof"><span className="status-dot" data-status={voice.systemStatus ? "ready" : "degraded"} />Voice-first, interruptible, grounded</div>
        )}
      </header>

      {!entered ? (
        <div id="main-content" className="landing-view">
          <section className="hero-copy">
            <p className="section-label">Adaptive voice intelligence</p>
            <h1>Speak naturally.<br /><span>Via keeps the thread.</span></h1>
            <p className="hero-lede">
              A voice mentor that listens in real time, adapts to how you feel, remembers what matters, and can become an expert in any document you choose.
            </p>
            <div className="hero-actions">
              <button className="primary-action large" type="button" onClick={startVia}>
                <span className="button-status-dot" />Start Via
              </button>
              <button className="quiet-action large" type="button" onClick={() => document.getElementById("demo-sources")?.scrollIntoView({ behavior: "smooth" })}>
                Explore demo sources
              </button>
            </div>
            <p className="no-source-note">No document required. Via begins in general-assistant mode.</p>
          </section>

          <section className="hero-orb" aria-label={`Via is ${voice.voiceState}`}>
            <div className="landing-orb" data-state="idle" aria-hidden="true">
              <span className="landing-orb-letter">V</span>
            </div>
            <div className="hero-status"><span>Listening</span><span>Understanding</span><span>Responding</span></div>
          </section>

          <section className="landing-proof" aria-label="Via capabilities">
            <div><strong>Interrupt without losing the thread</strong><p>Via pauses, handles the side question, and resumes from the right place.</p></div>
            <div><strong>Bring any working context</strong><p>PDF, CSV, or JSON changes Via&apos;s role while provenance keeps answers honest.</p></div>
            <div><strong>Adapt to the human signal</strong><p>Local emotional cues make explanations calmer, clearer, and better timed.</p></div>
          </section>

          <section className="demo-section" id="demo-sources">
            <div className="demo-intro">
              <p className="section-label">Optional knowledge</p>
              <h2>Give Via a world to work in.</h2>
              <p>Use a prepared source for the fastest demo, upload your own, or continue without one.</p>
              <form className="upload-inline" onSubmit={submitUpload}>
                <input
                  ref={fileInputRef}
                  id="landing-file"
                  type="file"
                  accept=".pdf,.csv,.json,application/pdf,text/csv,application/json"
                  onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                />
                <button className="quiet-action" type="button" onClick={() => fileInputRef.current?.click()}>
                  {file ? file.name : "Choose your file"}
                </button>
                {file && <button className="primary-action compact" disabled={voice.uploading}>{voice.uploading ? "Indexing..." : "Upload"}</button>}
              </form>
              {voice.uploadError && <div className="inline-error dismissible" role="alert"><span>{voice.uploadError}</span><button type="button" onClick={voice.dismissUploadError} aria-label="Dismiss upload error">x</button></div>}
            </div>
            <SourceOptions
              demos={voice.demoDocuments}
              uploading={voice.uploading}
              activeSlug={voice.activeDocument?.demo_slug}
              onDemo={chooseDemo}
            />
          </section>
        </div>
      ) : (
        <div id="main-content" className="workspace-view">
          {sourceOpen && (
            <aside className="source-drawer" aria-labelledby="source-drawer-title">
              <div className="section-heading-row">
                <div><p className="section-label">Optional context</p><h2 id="source-drawer-title">Knowledge source</h2></div>
                <button className="icon-text-button" type="button" onClick={() => setSourceOpen(false)}>Close</button>
              </div>
              {voice.activeDocument ? (
                <div className="active-source-detail">
                  <span className="file-format">{voice.activeDocument.source_type.toUpperCase()}</span>
                  <div><strong>{voice.activeDocument.filename}</strong><p>{voice.activeDocument.domain_profile.professional_role}</p></div>
                  <dl><div><dt>Domain</dt><dd>{voice.activeDocument.domain_profile.domain}</dd></div><div><dt>Knowledge chunks</dt><dd>{voice.activeDocument.chunks}</dd></div></dl>
                  <button className="danger-quiet" type="button" onClick={voice.removeDocument}>Remove source</button>
                </div>
              ) : (
                <div className="general-mode-note"><strong>General mode is active</strong><p>Via can talk now. Add a source only for grounded domain expertise.</p></div>
              )}
              <SourceOptions demos={voice.demoDocuments} uploading={voice.uploading} activeSlug={voice.activeDocument?.demo_slug} onDemo={chooseDemo} />
              <form className="drawer-upload" onSubmit={submitUpload}>
                <label htmlFor="workspace-file">Upload PDF, CSV, or JSON</label>
                <input id="workspace-file" type="file" accept=".pdf,.csv,.json" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
                <button className="primary-action compact" disabled={!file || voice.uploading}>{voice.uploading ? "Preparing source..." : "Upload and activate"}</button>
              </form>
              {voice.uploadError && <div className="inline-error dismissible" role="alert"><span>{voice.uploadError}</span><button type="button" onClick={voice.dismissUploadError} aria-label="Dismiss upload error">x</button></div>}
            </aside>
          )}

          {workspace === "session" ? (
            <div className="session-workspace">
              <section className="session-main">
                <VoiceOrb
                  state={voice.voiceState}
                  connected={voice.connected}
                  connecting={voice.connecting}
                  listening={voice.listening}
                  onConnect={() => void voice.connect()}
                  onDisconnect={voice.disconnect}
                  onStartListening={() => void voice.startListening()}
                  onStopListening={voice.stopListening}
                />

                <div className="live-answer" aria-live="polite">
                  <p className="section-label">Via&apos;s current response</p>
                  <p>{voice.assistantResponse || latestAssistant?.text || "Ask a question when you're ready."}</p>
                  {latestAssistant?.provenance && (
                    <span className="provenance" data-type={latestAssistant.provenance}>{provenanceLabel(latestAssistant.provenance)}</span>
                  )}
                </div>

                <div className="session-signals">
                  <div><span className="status-dot" data-status={voice.connected ? "ready" : "idle"} /><span>Connection</span><strong>{voice.connected ? "Live" : "Offline"}</strong></div>
                  <div><span className="status-dot" data-status={voice.sttProvider === "deepgram" ? "ready" : "degraded"} /><span>Transcription</span><strong>{voice.sttProvider}</strong></div>
                  <div><span className="status-dot" data-status={voice.emotion.status === "ready" ? "ready" : "loading"} /><span>Emotion</span><strong>{voice.emotion.displayLabel ?? voice.emotion.status}</strong></div>
                  <div><span className="status-dot" data-status={voice.activeDocument ? "ready" : "idle"} /><span>Knowledge</span><strong>{voice.activeDocument ? voice.activeDocument.domain_profile.domain : "General"}</strong></div>
                </div>
              </section>

              <ConversationTimeline turns={voice.conversation} interim={voice.interimTranscript} restoredState={voice.restoredState} />
            </div>
          ) : (
            <ArchitectureDashboard
              stages={voice.pipelineStages}
              conversation={voice.conversation}
              systemStatus={voice.systemStatus}
              activeDocument={voice.activeDocument}
              voiceState={voice.voiceState}
              interruptCount={voice.interruptCount}
              sessionId={voice.sessionId}
            />
          )}

          {(voice.voiceError || voice.systemError) && (
            <div className="error-banner" role="alert">
              <div><strong>Via needs attention</strong><p>{voice.voiceError || voice.systemError}</p></div>
              <div className="error-actions"><button className="quiet-action" type="button" onClick={() => void voice.checkSystem()}>Check again</button><button className="close-error" type="button" onClick={() => { voice.dismissVoiceError(); voice.dismissSystemError(); }} aria-label="Dismiss error">x</button></div>
            </div>
          )}

          {voice.fallbackRequired && (
            <section className="fallback-banner" aria-labelledby="fallback-title">
              <div><p className="section-label">Transcription fallback</p><h2 id="fallback-title">Continue with the lower-accuracy local model?</h2><p>{voice.fallbackMessage}</p></div>
              <div><button className="primary-action compact" onClick={() => voice.chooseWhisperFallback("continue")}>Continue with Whisper</button><button className="quiet-action" onClick={() => voice.chooseWhisperFallback("stop")}>Stop and check</button></div>
            </section>
          )}
        </div>
      )}
    </main>
  );
}
