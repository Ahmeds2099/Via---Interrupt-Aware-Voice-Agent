"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { resolveApiUrl } from "@/lib/env";
import { VoiceRecorder } from "@/lib/voice/recorder";
import {
    AssistantSegment,
    EmotionUpdate,
    VoiceSocket,
} from "@/lib/voice/websocket";
import type {
    ConversationTurn,
    DemoDocument,
    PipelineStage,
    SystemStatus,
    TurnContext,
    TurnMetrics,
    UploadedDocument,
    VoiceState,
} from "@/lib/voice/types";

const CLIENT_ID_KEY = "via_client_id";
const DOCUMENT_KEY = "via_active_document";

const createClientId = () => {
    const bytes = new Uint8Array(16);
    if (globalThis.crypto?.getRandomValues) {
        globalThis.crypto.getRandomValues(bytes);
    } else {
        for (let index = 0; index < bytes.length; index += 1) {
            bytes[index] = Math.floor(Math.random() * 256);
        }
    }
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const value = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
    return `${value.slice(0, 8)}-${value.slice(8, 12)}-${value.slice(12, 16)}-${value.slice(16, 20)}-${value.slice(20)}`;
};

const stableClientId = () => {
    const existing = localStorage.getItem(CLIENT_ID_KEY);
    if (existing) return existing;
    const created = createClientId();
    localStorage.setItem(CLIENT_ID_KEY, created);
    return created;
};

type SegmentPlayback = {
    responseId: string;
    segmentId: string;
    sources: Set<AudioBufferSourceNode>;
    closed: boolean;
    cancelled: boolean;
    text: string;
    textShown: boolean;
};

const segmentKey = (segment: AssistantSegment) =>
    `${segment.responseId}:${segment.segmentId}`;

const mergePipelineStage = (
    stages: PipelineStage[],
    update: PipelineStage,
) => [
    ...stages.filter((candidate) =>
        !(
            candidate.responseId === update.responseId
            && candidate.stage === update.stage
        ),
    ),
    update,
].slice(-16);

export function useVoice() {
    const audioContextRef = useRef<AudioContext | null>(null);
    const socketRef = useRef<VoiceSocket | null>(null);
    const recorderRef = useRef<VoiceRecorder | null>(null);
    const nextPlaybackTimeRef = useRef(0);
    const scheduledSourcesRef = useRef(
        new Set<AudioBufferSourceNode>(),
    );
    const playbackSegmentsRef = useRef(
        new Map<string, SegmentPlayback>(),
    );
    const activeSegmentKeyRef = useRef<string | null>(null);
    const activeResponseIdRef = useRef<string | null>(null);
    const responseStartedAtRef = useRef(new Map<string, number>());
    const connectionTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const emotionRef = useRef<EmotionUpdate>({ provider: "emotion2vec+", status: "idle" });

    const [connected, setConnected] = useState(false);
    const [connecting, setConnecting] = useState(false);
    const [listening, setListening] = useState(false);
    const [voiceState, setVoiceState] = useState<VoiceState>("idle");
    const [sessionId, setSessionId] = useState("");
    const [transcript, setTranscript] = useState("");
    const [interimTranscript, setInterimTranscript] = useState("");
    const [assistantResponse, setAssistantResponse] = useState("");
    const [sttProvider, setSTTProvider] = useState("initializing");
    const [fallbackRequired, setFallbackRequired] = useState(false);
    const [fallbackMessage, setFallbackMessage] = useState("");
    const [voiceError, setVoiceError] = useState("");
    const [emotion, setEmotion] = useState<EmotionUpdate>({
        provider: "emotion2vec+",
        status: "idle",
    });
    const [activeDocument, setActiveDocument] = useState<UploadedDocument | null>(() => {
        if (typeof window === "undefined") return null;
        const saved = localStorage.getItem(DOCUMENT_KEY);
        if (!saved) return null;
        try {
            return JSON.parse(saved) as UploadedDocument;
        } catch {
            localStorage.removeItem(DOCUMENT_KEY);
            return null;
        }
    });
    const [uploading, setUploading] = useState(false);
    const [uploadError, setUploadError] = useState("");
    const [restoredState, setRestoredState] = useState("");
    const [conversation, setConversation] = useState<ConversationTurn[]>([]);
    const [pipelineStages, setPipelineStages] = useState<PipelineStage[]>([]);
    const [turnContexts, setTurnContexts] = useState<Record<string, TurnContext>>({});
    const [turnMetrics, setTurnMetrics] = useState<Record<string, TurnMetrics>>({});
    const [interruptCount, setInterruptCount] = useState(0);
    const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
    const [systemError, setSystemError] = useState("");
    const [demoDocuments, setDemoDocuments] = useState<DemoDocument[]>([]);

    const apiBase = useMemo(() => resolveApiUrl().replace(/\/$/, ""), []);

    const checkSystem = useCallback(async () => {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 5000);
        try {
            const response = await fetch(`${apiBase}/system/status`, {
                signal: controller.signal,
            });
            if (!response.ok) throw new Error(`Backend returned ${response.status}`);
            const status = await response.json() as SystemStatus;
            setSystemStatus(status);
            setSystemError("");
            return true;
        } catch {
            setSystemError(`Via backend is not reachable at ${apiBase}.`);
            return false;
        } finally {
            clearTimeout(timer);
        }
    }, [apiBase]);

    const stopPlayback = useCallback(() => {
        playbackSegmentsRef.current.forEach((segment) => {
            segment.cancelled = true;
        });

        scheduledSourcesRef.current.forEach((source) => {
            try {
                source.stop();
            } catch {
                // The source already completed.
            }
        });

        scheduledSourcesRef.current.clear();
        playbackSegmentsRef.current.clear();
        activeSegmentKeyRef.current = null;

        if (audioContextRef.current) {
            nextPlaybackTimeRef.current =
                audioContextRef.current.currentTime;
        }
    }, []);

    const connect = useCallback(async () => {
        if (socketRef.current) {
            return;
        }

        setVoiceError("");
        setConnecting(true);
        setVoiceState("connecting");
        const backendReady = await checkSystem();
        if (!backendReady) {
            setConnecting(false);
            setVoiceState("error");
            setVoiceError(
                `Unable to reach Via at ${apiBase}. Start the backend and try again.`,
            );
            return;
        }

        const socket = new VoiceSocket();

        const maybeAcknowledge = (key: string) => {
            const segment = playbackSegmentsRef.current.get(key);
            if (
                !segment
                || segment.cancelled
                || !segment.closed
                || segment.sources.size > 0
            ) {
                return;
            }

            socket.acknowledgePlayback(
                segment.responseId,
                segment.segmentId,
            );
            playbackSegmentsRef.current.delete(key);
            if (activeSegmentKeyRef.current === key) {
                activeSegmentKeyRef.current = null;
            }
        };

        socket.onOpen = () => {
            if (connectionTimerRef.current) clearTimeout(connectionTimerRef.current);
            setConnecting(false);
            setConnected(true);
            setVoiceState("idle");
            setVoiceError("");
            const clientId = stableClientId();
            const saved = localStorage.getItem(DOCUMENT_KEY);
            let documentIds: string[] = [];
            if (saved) {
                try {
                    const document = JSON.parse(saved) as UploadedDocument;
                    documentIds = [document.document_id];
                } catch {
                    localStorage.removeItem(DOCUMENT_KEY);
                }
            }
            socket.initializeSession(clientId, documentIds);
        };

        socket.onClose = () => {
            if (connectionTimerRef.current) clearTimeout(connectionTimerRef.current);
            setConnecting(false);
            setConnected(false);
            setListening(false);
            setSTTProvider("disconnected");
            setVoiceState("idle");
            recorderRef.current?.stop();
            recorderRef.current = null;
            socketRef.current = null;
            stopPlayback();
        };

        socket.onError = () => {
            if (connectionTimerRef.current) clearTimeout(connectionTimerRef.current);
            setConnecting(false);
            setConnected(false);
            setVoiceState("error");
            setVoiceError(
                `The voice WebSocket at ${apiBase} could not be opened. Check the backend logs and try again.`,
            );
        };

        socket.onConnected = setSessionId;
        socket.onVoiceState = setVoiceState;

        socket.onTranscript = (text) => {
            setTranscript(text);
            setInterimTranscript("");
            setConversation((turns) => [
                ...turns,
                {
                    id: createClientId(),
                    role: "user",
                    text,
                    createdAt: Date.now(),
                },
            ]);
            setPipelineStages((stages) => mergePipelineStage(stages, {
                    stage: "stt",
                    status: "complete",
                    updatedAt: Date.now(),
            }));
        };

        socket.onInterimTranscript = (text) => {
            setInterimTranscript(text);
            setPipelineStages((stages) => mergePipelineStage(stages, {
                    stage: "stt",
                    status: "active",
                    updatedAt: Date.now(),
            }));
        };

        socket.onAssistantStreamStart = (responseId) => {
            setAssistantResponse("");
            if (!responseId) return;
            activeResponseIdRef.current = responseId;
            responseStartedAtRef.current.set(responseId, performance.now());
            setConversation((turns) => [
                ...turns,
                {
                    id: responseId,
                    role: "assistant",
                    text: "",
                    emotionLabel: emotionRef.current.displayLabel ?? "neutral",
                    emotionAdapted: Boolean(emotionRef.current.clarificationMode),
                    createdAt: Date.now(),
                },
            ]);
        };

        // Raw LLM tokens arrive much faster than speech. Render the
        // sentence only when its first audio chunk begins instead.
        socket.onAssistantStream = () => undefined;

        socket.onSegmentStart = (segment) => {
            const key = segmentKey(segment);
            playbackSegmentsRef.current.set(key, {
                responseId: segment.responseId,
                segmentId: segment.segmentId,
                sources: new Set<AudioBufferSourceNode>(),
                closed: false,
                cancelled: false,
                text: segment.text ?? "",
                textShown: false,
            });
            activeSegmentKeyRef.current = key;
        };

        socket.onSegmentEnd = (segment) => {
            const key = segmentKey(segment);
            const playback = playbackSegmentsRef.current.get(key);
            if (playback) {
                playback.closed = true;
            }
            maybeAcknowledge(key);
        };

        socket.onAssistantAudio = async (pcm) => {
            if (!audioContextRef.current) {
                audioContextRef.current = new AudioContext();
                nextPlaybackTimeRef.current =
                    audioContextRef.current.currentTime;
            }

            const context = audioContextRef.current;
            if (context.state === "suspended") {
                await context.resume();
            }

            const samples = new Float32Array(pcm);
            const buffer = context.createBuffer(
                1,
                samples.length,
                16000,
            );
            buffer.copyToChannel(samples, 0);

            const source = context.createBufferSource();
            source.buffer = buffer;
            source.connect(context.destination);

            const key = activeSegmentKeyRef.current;
            const segment = key
                ? playbackSegmentsRef.current.get(key)
                : undefined;

            if (segment && !segment.textShown && segment.text) {
                segment.textShown = true;
                setAssistantResponse((previous) =>
                    previous
                        ? `${previous} ${segment.text}`
                        : segment.text,
                );
                setConversation((turns) => turns.map((turn) =>
                    turn.id === segment.responseId
                        ? {
                            ...turn,
                            text: turn.text
                                ? `${turn.text} ${segment.text}`
                                : segment.text,
                        }
                        : turn,
                ));
                const startedAt = responseStartedAtRef.current.get(segment.responseId);
                socket.playbackStarted(
                    segment.responseId,
                    segment.segmentId,
                    startedAt ? Math.round(performance.now() - startedAt) : undefined,
                );
            }

            scheduledSourcesRef.current.add(source);
            segment?.sources.add(source);

            source.onended = () => {
                scheduledSourcesRef.current.delete(source);
                if (key) {
                    const current = playbackSegmentsRef.current.get(key);
                    current?.sources.delete(source);
                    maybeAcknowledge(key);
                }
            };

            const startTime = Math.max(
                nextPlaybackTimeRef.current,
                context.currentTime,
            );
            source.start(startTime);
            nextPlaybackTimeRef.current =
                startTime + buffer.duration;
        };

        socket.onInterrupted = (responseId) => {
            stopPlayback();
            setAssistantResponse("");
            setVoiceState("interrupted");
            setInterruptCount((count) => count + 1);
            if (responseId) {
                setConversation((turns) => turns.map((turn) =>
                    turn.id === responseId ? { ...turn, interrupted: true } : turn,
                ));
            }
        };

        socket.onSTTReady = (provider) => {
            setSTTProvider(provider);
            setFallbackRequired(false);
        };

        socket.onFallbackRequired = (message) => {
            setFallbackRequired(true);
            setFallbackMessage(message);
            setSTTProvider("awaiting choice");
            setVoiceState("fallback");
        };

        socket.onProviderChanged = (provider) => {
            setSTTProvider(provider);
            setFallbackRequired(false);
            setFallbackMessage("");

            if (provider === "disabled") {
                recorderRef.current?.stop();
                recorderRef.current = null;
                setListening(false);
            }
        };

        socket.onVoiceError = (error) => {
            setVoiceError(error.message);
            setVoiceState(error.recoverable ? "fallback" : "error");
        };

        socket.onPipelineStage = (stage) => {
            setPipelineStages((stages) => mergePipelineStage(stages, stage));
        };
        socket.onTurnContext = (context) => {
            setTurnContexts((contexts) => ({ ...contexts, [context.responseId]: context }));
            setConversation((turns) => turns.map((turn) =>
                turn.id === context.responseId
                    ? {
                        ...turn,
                        provenance: context.provenance,
                        sources: context.sources,
                        memoryCount: context.memoryCount,
                    }
                    : turn,
            ));
            setPipelineStages((stages) => mergePipelineStage(stages, {
                    responseId: context.responseId,
                    stage: "memory",
                    status: context.memoryCount ? "complete" : "skipped",
                    updatedAt: Date.now(),
            }));
        };
        socket.onTurnMetrics = (metrics) => {
            setTurnMetrics((values) => ({ ...values, [metrics.responseId]: metrics }));
            setConversation((turns) => turns.map((turn) =>
                turn.id === metrics.responseId ? { ...turn, metrics } : turn,
            ));
        };

        socket.onEmotionUpdate = (update) => {
            emotionRef.current = update;
            setEmotion(update);
            setPipelineStages((stages) => mergePipelineStage(stages, {
                    stage: "emotion",
                    status: update.label ? "complete" : update.status,
                    updatedAt: Date.now(),
            }));
        };
        socket.onSessionRestored = (messageCount, memoryCount) => {
            setRestoredState(
                `Restored ${messageCount} messages and ${memoryCount} memories`,
            );
        };

        setSTTProvider("initializing");

        const wsBase = apiBase.replace(/^http/, "ws");
        socket.connect(`${wsBase}/ws/voice`);
        socketRef.current = socket;
        connectionTimerRef.current = setTimeout(() => {
            if (!socket.connected) {
                socket.disconnect();
                socketRef.current = null;
                setConnecting(false);
                setVoiceState("error");
                setVoiceError("The voice connection timed out. Verify the backend and retry.");
            }
        }, 8000);
    }, [apiBase, checkSystem, stopPlayback]);

    const disconnect = useCallback(() => {
        recorderRef.current?.stop();
        recorderRef.current = null;
        socketRef.current?.disconnect();
        stopPlayback();
        audioContextRef.current?.close();
        audioContextRef.current = null;
        nextPlaybackTimeRef.current = 0;
        setVoiceState("idle");
    }, [stopPlayback]);

    const startListening = useCallback(async () => {
        if (!socketRef.current?.connected) {
            return;
        }

        if (!recorderRef.current) {
            recorderRef.current = new VoiceRecorder();
        }

        try {
            await recorderRef.current.start((buffer) => {
                socketRef.current?.sendPCM(buffer);
            });
            setListening(true);
            setVoiceState("listening");
            setPipelineStages((stages) => mergePipelineStage(stages, {
                    stage: "microphone",
                    status: "active",
                    updatedAt: Date.now(),
            }));
        } catch (error) {
            recorderRef.current = null;
            setVoiceState("error");
            setVoiceError(
                error instanceof Error
                    ? `Microphone access failed: ${error.message}`
                    : "Microphone access failed. Check browser permissions.",
            );
        }
    }, []);

    const stopListening = useCallback(() => {
        recorderRef.current?.stop();
        recorderRef.current = null;
        setListening(false);
        setVoiceState("idle");
        setPipelineStages((stages) => mergePipelineStage(stages, {
                stage: "microphone",
                status: "idle",
                updatedAt: Date.now(),
        }));
    }, []);

    const chooseWhisperFallback = useCallback(
        (choice: "continue" | "stop") => {
            socketRef.current?.chooseFallback(choice);
        },
        [],
    );

    const uploadDocument = useCallback(async (file: File) => {
        setUploading(true);
        setUploadError("");
        try {
            const form = new FormData();
            form.append("file", file);
            const response = await fetch(`${apiBase}/upload/`, {
                method: "POST",
                body: form,
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(payload.detail ?? "Upload failed");
            }
            const document = payload as UploadedDocument;
            setActiveDocument(document);
            localStorage.setItem(DOCUMENT_KEY, JSON.stringify(document));
            socketRef.current?.setDocumentContext([document.document_id]);
        } catch (error) {
            setUploadError(
                error instanceof Error ? error.message : "Upload failed",
            );
        } finally {
            setUploading(false);
        }
    }, [apiBase]);

    const loadDemoDocument = useCallback(async (slug: string) => {
        setUploading(true);
        setUploadError("");
        try {
            const response = await fetch(`${apiBase}/upload/demos/${slug}`, {
                method: "POST",
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(payload.detail ?? "Demo document could not be prepared");
            }
            const document = payload as UploadedDocument;
            setActiveDocument(document);
            localStorage.setItem(DOCUMENT_KEY, JSON.stringify(document));
            socketRef.current?.setDocumentContext([document.document_id]);
        } catch (error) {
            setUploadError(error instanceof Error ? error.message : "Demo document failed");
        } finally {
            setUploading(false);
        }
    }, [apiBase]);

    const removeDocument = useCallback(() => {
        setActiveDocument(null);
        localStorage.removeItem(DOCUMENT_KEY);
        socketRef.current?.setDocumentContext([]);
    }, []);

    const dismissVoiceError = useCallback(() => setVoiceError(""), []);
    const dismissSystemError = useCallback(() => setSystemError(""), []);
    const dismissUploadError = useCallback(() => setUploadError(""), []);

    useEffect(() => {
        fetch(`${apiBase}/upload/demos`)
            .then((response) => response.ok ? response.json() : Promise.reject())
            .then((payload) => setDemoDocuments(payload.documents ?? []))
            .catch(() => setDemoDocuments([]));
    }, [apiBase]);

    useEffect(() => {
        return () => {
            recorderRef.current?.stop();
            socketRef.current?.disconnect();
            if (connectionTimerRef.current) clearTimeout(connectionTimerRef.current);
            stopPlayback();
            audioContextRef.current?.close();
        };
    }, [stopPlayback]);

    return {
        connected,
        connecting,
        listening,
        voiceState,
        sessionId,
        transcript,
        interimTranscript,
        assistantResponse,
        sttProvider,
        fallbackRequired,
        fallbackMessage,
        voiceError,
        emotion,
        activeDocument,
        uploading,
        uploadError,
        restoredState,
        conversation,
        pipelineStages,
        turnContexts,
        turnMetrics,
        interruptCount,
        systemStatus,
        systemError,
        demoDocuments,
        apiBase,
        connect,
        disconnect,
        startListening,
        stopListening,
        chooseWhisperFallback,
        uploadDocument,
        loadDemoDocument,
        removeDocument,
        dismissVoiceError,
        dismissSystemError,
        dismissUploadError,
        checkSystem,
    };
}
