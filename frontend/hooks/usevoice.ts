"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { VoiceSocket } from "@/lib/voice/websocket";
import { VoiceRecorder } from "@/lib/voice/recorder";

export function useVoice() {

    const socketRef = useRef<VoiceSocket | null>(null);

    const recorderRef = useRef<VoiceRecorder | null>(null);

    const [connected, setConnected] = useState(false);

    const [connecting, setConnecting] = useState(false);

    const [listening, setListening] = useState(false);

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

        };

        socket.onError = () => {

            setConnecting(false);

            setConnected(false);

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

        };

    }, []);

    return {

        connected,

        connecting,

        listening,

        connect,

        disconnect,

        startListening,

        stopListening,

    };

}