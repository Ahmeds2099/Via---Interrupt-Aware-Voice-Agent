import type {
  ConversationTurn,
  PipelineStage,
  SystemStatus,
  UploadedDocument,
  VoiceState,
} from "@/lib/voice/types";

const PIPELINE = [
  ["microphone", "Microphone"],
  ["stt", "Deepgram"],
  ["memory", "Memory"],
  ["retrieval", "Retrieval"],
  ["llm", "Groq"],
  ["emotion", "Emotion"],
  ["tts", "Cartesia"],
  ["playback", "Playback"],
] as const;

const providerLabel = (value: string | Record<string, unknown>) => {
  if (typeof value === "string") return value;
  if (typeof value.status === "string") return value.status;
  return "configured";
};

const provenanceLabel = (value?: string) => {
  if (value === "document") return "Domain knowledge";
  if (value === "not_in_source") return "Not in source";
  return "General knowledge";
};

type Props = {
  stages: PipelineStage[];
  conversation: ConversationTurn[];
  systemStatus: SystemStatus | null;
  activeDocument: UploadedDocument | null;
  voiceState: VoiceState;
  interruptCount: number;
  sessionId: string;
};

export default function ArchitectureDashboard({
  stages,
  conversation,
  systemStatus,
  activeDocument,
  voiceState,
  interruptCount,
  sessionId,
}: Props) {
  const latestByStage = new Map(stages.map((stage) => [stage.stage, stage]));
  const assistantTurns = conversation.filter((turn) => turn.role === "assistant");
  const measured = assistantTurns
    .map((turn) => turn.metrics?.serverResponseMs)
    .filter((value): value is number => typeof value === "number");
  const averageLatency = measured.length
    ? Math.round(measured.reduce((total, value) => total + value, 0) / measured.length)
    : null;
  const memoriesUsed = assistantTurns.reduce((total, turn) => total + (turn.memoryCount ?? 0), 0);
  const retrievedSources = assistantTurns.reduce((total, turn) => total + (turn.sources?.length ?? 0), 0);
  const estimatedTokens = assistantTurns.reduce((total, turn) => total + (turn.metrics?.estimatedOutputTokens ?? 0), 0);

  return (
    <div className="architecture-view">
      <section className="dashboard-heading">
        <div>
          <p className="section-label">Live architecture</p>
          <h2>One turn, end to end.</h2>
          <p>Measured events from the active voice session, not simulated telemetry.</p>
        </div>
        <div className="dashboard-heading-actions">
          <details className="architecture-help">
            <summary aria-label="What this architecture view shows">i</summary>
            <div className="help-popover">
              <strong>What you are seeing</strong>
              <p>This view follows a real request through microphone capture, transcription, memory, retrieval, reasoning, emotion, speech, and playback. Measured values come from the active session. Configured values come from provider health checks.</p>
            </div>
          </details>
          <div className="session-identity">
            <span className="status-dot" data-status={voiceState} />
            <span>{voiceState}</span>
            <code>{sessionId ? sessionId.slice(0, 8) : "not connected"}</code>
          </div>
        </div>
      </section>

      <section className="pipeline-panel" aria-labelledby="pipeline-title">
        <div className="section-heading-row">
          <div><p className="section-label">Current turn</p><h3 id="pipeline-title">Voice pipeline</h3></div>
          <span className="context-chip">{activeDocument ? activeDocument.filename : "General mode, retrieval skipped"}</span>
        </div>
        <ol className="pipeline-flow">
          {PIPELINE.map(([key, label]) => {
            const stage = latestByStage.get(key);
            const skipped = key === "retrieval" && !activeDocument;
            const active = stage?.status === "active" || stage?.status === "first_token" || stage?.status === "first_byte" || stage?.status === "started";
            return (
              <li key={key} className="pipeline-step" data-active={active} data-skipped={skipped}>
                <strong>{label}</strong>
                <span>{skipped ? "skipped" : stage?.status ?? "waiting"}</span>
                {typeof stage?.durationMs === "number" && <code>{stage.durationMs} ms</code>}
              </li>
            );
          })}
        </ol>
      </section>

      <div className="dashboard-grid">
        <section className="metrics-panel" aria-labelledby="metrics-title">
          <div className="section-heading-row"><div><p className="section-label">Session proof</p><h3 id="metrics-title">Measured outcomes</h3></div></div>
          <dl className="metric-list">
            <div><dt>Average response</dt><dd>{averageLatency ? `${averageLatency} ms` : "Not measured"}</dd></div>
            <div><dt>Completed turns</dt><dd>{assistantTurns.length}</dd></div>
            <div><dt>Interruptions</dt><dd>{interruptCount}</dd></div>
            <div><dt>Source passages</dt><dd>{retrievedSources}</dd></div>
            <div><dt>Memories used</dt><dd>{memoriesUsed}</dd></div>
            <div><dt>Output tokens</dt><dd>{estimatedTokens || "Not measured"}<small>estimated</small></dd></div>
          </dl>
        </section>

        <section className="providers-panel" aria-labelledby="providers-title">
          <div className="section-heading-row"><div><p className="section-label">Dependencies</p><h3 id="providers-title">Provider status</h3></div></div>
          <ul className="provider-list">
            {Object.entries(systemStatus?.providers ?? {}).map(([name, value]) => {
              const rawStatus = providerLabel(value);
              const isLite = process.env.NEXT_PUBLIC_DEPLOYMENT_PROFILE === "lite";
              const isHeavyML = name === "emotion" || name === "whisper";
              const status = isLite && isHeavyML ? "Local/dev only" : rawStatus;
              
              return <li key={name}><span className="status-dot" data-status={isLite && isHeavyML ? "idle" : rawStatus} /><strong>{name === "emotion" ? "Emotion2Vec+" : name}</strong><span>{status}</span></li>;
            })}
            {!systemStatus && <li className="muted-row">Connect to load provider health.</li>}
          </ul>
        </section>
      </div>

      <section className="trace-panel" aria-labelledby="trace-title">
        <div className="section-heading-row"><div><p className="section-label">Conversation trace</p><h3 id="trace-title">What shaped each answer</h3></div></div>
        <div className="trace-list">
          {assistantTurns.slice(-4).reverse().map((turn) => {
            const index = conversation.findIndex((candidate) => candidate.id === turn.id);
            const question = index > 0 && conversation[index - 1]?.role === "user" ? conversation[index - 1].text : "User request not retained";
            return (
              <article key={turn.id} className="trace-turn">
                <div><strong>User asked</strong><time>{new Date(turn.createdAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time></div>
                <p className="trace-question">{question}</p>
                <dl className="trace-details">
                  <div><dt>Via answered</dt><dd>{turn.text || "Response is being prepared..."}</dd></div>
                  <div><dt>Knowledge used</dt><dd>{provenanceLabel(turn.provenance)}{turn.sources?.length ? `, ${turn.sources.length} passages` : ""}</dd></div>
                  <div><dt>Emotion adaptation</dt><dd>{turn.emotionAdapted ? `Simplified for ${turn.emotionLabel ?? "uncertainty"}` : turn.emotionLabel ? `Observed as ${turn.emotionLabel}` : "No adaptation recorded"}</dd></div>
                  <div><dt>Latency</dt><dd>{turn.metrics?.serverResponseMs ? `${turn.metrics.serverResponseMs} ms` : "Measuring"}</dd></div>
                </dl>
                <details className="trace-raw"><summary>Show source details</summary><p>{turn.sources?.map((source) => source.filename).filter(Boolean).join(", ") || "No source passage"}</p></details>
              </article>
            );
          })}
          {!assistantTurns.length && <div className="teaching-empty"><strong>No turns measured yet</strong><p>Start a voice conversation, then return here to inspect its path through Via.</p></div>}
        </div>
      </section>
    </div>
  );
}
