import type { VoiceState } from "@/lib/voice/types";

const STATE_COPY: Record<VoiceState, { label: string; detail: string }> = {
  idle: { label: "Ready", detail: "Start listening when you are ready." },
  connecting: { label: "Connecting", detail: "Opening Via's real-time voice channel." },
  listening: { label: "Listening", detail: "Speak naturally. You can interrupt Via at any time." },
  thinking: { label: "Thinking", detail: "Retrieving context and preparing a response." },
  speaking: { label: "Speaking", detail: "Via is responding. Start speaking to barge in." },
  interrupted: { label: "Interrupted", detail: "Your question is taking priority." },
  fallback: { label: "Needs attention", detail: "Choose how Via should continue transcription." },
  error: { label: "Unavailable", detail: "Review the issue below, then retry." },
};

type Props = {
  state: VoiceState;
  connected: boolean;
  connecting: boolean;
  listening: boolean;
  onConnect(): void;
  onDisconnect(): void;
  onStartListening(): void;
  onStopListening(): void;
};

export default function VoiceOrb({
  state,
  connected,
  connecting,
  listening,
  onConnect,
  onDisconnect,
  onStartListening,
  onStopListening,
}: Props) {
  const copy = STATE_COPY[state];
  const primaryAction = !connected
    ? onConnect
    : listening
      ? onStopListening
      : onStartListening;
  const primaryLabel = !connected
    ? connecting ? "Connecting…" : "Connect Via"
    : listening ? "Stop listening" : "Start listening";

  return (
    <section className="voice-stage" aria-labelledby="voice-state-label">
      <div className="orb-wrap" data-state={state} aria-hidden="true">
        <div className="orb-aura" />
        <div className="voice-orb">
          <span className="orb-core">V</span>
          <span className="orb-wave orb-wave-one" />
          <span className="orb-wave orb-wave-two" />
        </div>
      </div>

      <div className="voice-state-copy" aria-live="polite">
        <p className="eyebrow" id="voice-state-label">{copy.label}</p>
        <p>{copy.detail}</p>
      </div>

      <div className="voice-actions">
        <button
          className="primary-action"
          type="button"
          onClick={primaryAction}
          disabled={connecting}
        >
          <span className="button-status-dot" aria-hidden="true" />
          {primaryLabel}
        </button>
        {connected && (
          <button className="quiet-action" type="button" onClick={onDisconnect}>
            Disconnect
          </button>
        )}
      </div>
    </section>
  );
}
