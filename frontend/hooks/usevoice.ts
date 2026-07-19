"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { VoiceSocket } from "@/lib/voice/websocket";
import { VoiceRecorder } from "@/lib/voice/recorder";

export function useVoice() {

    const audioContextRef = useRef<AudioContext | null>(null);

    const socketRef = useRef<VoiceSocket | null>(null);

    const recorderRef = useRef<VoiceRecorder | null>(null);

    // Playback scheduler
    const nextPlaybackTimeRef = useRef(0);

    const [connected, setConnected] = useState(false);

    const [connecting, setConnecting] = useState(false);

    const [listening, setListening] = useState(false);

    const [transcript, setTranscript] =
        useState("");

    const [assistantResponse, setAssistantResponse] =
        useState("");

    const connect = useCallback(() => {

        if (socketRef.current) {
            return;
        }

        const socket = new VoiceSocket();

        socket.onOpen = () => {

            setConnecting(false);

            setConnected(true);

        };

        socket.onClose = () => {

            setConnecting(false);

            setConnected(false);

            setListening(false);

            recorderRef.current?.stop();

            socketRef.current = null;

            nextPlaybackTimeRef.current = 0;

        };

        socket.onError = () => {

            setConnecting(false);

            setConnected(false);

        };

        socket.onTranscript = (text) => {

            setTranscript(text);

        };

        socket.onAssistantStreamStart = () => {

            setAssistantResponse("");

        };

        socket.onAssistantStream = (token) => {

            setAssistantResponse((previous) =>

                previous + token

            );

        };

        socket.onAssistantAudio = async (pcm) => {

            if (!audioContextRef.current) {

                audioContextRef.current = new AudioContext();

                console.log(
                    "[AUDIO] Context sample rate:",
                    audioContextRef.current.sampleRate,
                );

                nextPlaybackTimeRef.current =
                    audioContextRef.current.currentTime;
            }

            const ctx = audioContextRef.current;

            const float32 = new Float32Array(pcm);

            const buffer = ctx.createBuffer(
                1,
                float32.length,
                16000,
            );

            buffer.copyToChannel(
                float32,
                0,
            );

            const source =
                ctx.createBufferSource();

            source.buffer = buffer;

            source.connect(
                ctx.destination,
            );

            const startTime = Math.max(
                nextPlaybackTimeRef.current,
                ctx.currentTime,
            );

            source.start(startTime);

            nextPlaybackTimeRef.current =
                startTime + buffer.duration;

        };

        socket.onAssistantStreamEnd = () => {

            console.log("[VOICE] Stream complete");

        };

        setConnecting(true);

        socket.connect(
            "ws://127.0.0.1:8000/ws/voice",
        );

        socketRef.current = socket;

    }, []);

    const disconnect = useCallback(() => {

        recorderRef.current?.stop();

        recorderRef.current = null;

        socketRef.current?.disconnect();

        audioContextRef.current?.close();

        audioContextRef.current = null;

        nextPlaybackTimeRef.current = 0;

    }, []);

    const startListening = useCallback(async () => {

        if (!socketRef.current?.connected) {
            return;
        }

        if (!recorderRef.current) {

            recorderRef.current =
                new VoiceRecorder();

        }

        await recorderRef.current.start((buffer) => {

            socketRef.current?.sendPCM(buffer);

        });

        setListening(true);

    }, []);

    const stopListening = useCallback(() => {

        recorderRef.current?.stop();

        recorderRef.current = null;

        setListening(false);

    }, []);

    useEffect(() => {

        return () => {

            recorderRef.current?.stop();

            socketRef.current?.disconnect();

            audioContextRef.current?.close();

        };

    }, []);

    return {

        connected,

        connecting,

        listening,

        transcript,

        assistantResponse,

        connect,

        disconnect,

        startListening,

        stopListening,

    };

}