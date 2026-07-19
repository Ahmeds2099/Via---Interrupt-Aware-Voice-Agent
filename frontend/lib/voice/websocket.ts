type ConnectionState =
    | "connecting"
    | "connected"
    | "disconnected";

export class VoiceSocket {

    private socket: WebSocket | null = null;

    onOpen?: () => void;

    onClose?: () => void;

    onError?: (event: Event) => void;

    onMessage?: (data: unknown) => void;

    connect(url: string) {

        if (this.socket) {
            return;
        }

        this.socket = new WebSocket(url);

        this.socket.binaryType = "arraybuffer";

        this.socket.onopen = () => {

            console.log("[VOICE] Connected");

            this.onOpen?.();
        };


        this.socket.onmessage = (event) => {

            if (event.data instanceof ArrayBuffer) {

                this.onAssistantAudio?.(
                    event.data,
                );

                return;

            }

            const message = JSON.parse(
                event.data,
            );

            switch (message.type) {

                case "transcript":

                    this.onTranscript?.(
                        message.text,
                    );

                    break;

                case "assistant_response":

                    this.onAssistantResponse?.(
                        message.text,
                    );

                    break;

                case "assistant_stream_start":

                    this.onAssistantStreamStart?.();

                    break;

                case "assistant_stream":

                    this.onAssistantStream?.(
                        message.token,
                    );

                    break;

                case "assistant_stream_end":

                    this.onAssistantStreamEnd?.();

                    break;

                default:

                    this.onMessage?.(message);

            }

        };
        this.socket.onerror = (event) => {

            console.error("[VOICE]", event);

            this.onError?.(event);
        };

        this.socket.onclose = () => {

            console.log("[VOICE] Closed");

            this.socket = null;

            this.onClose?.();
        };
    }

    sendJSON(data: unknown) {

        this.socket?.send(
            JSON.stringify(data),
        );
    }

    sendAudio(data: ArrayBuffer) {

        this.socket?.send(data);
    }

    disconnect() {

        this.socket?.close();
    }

    get connected() {

        return this.socket?.readyState === WebSocket.OPEN;
    }

    sendPCM(buffer: ArrayBuffer) {

        if (!this.connected) {
            return;
        }

        this.socket?.send(buffer);
    }

    onTranscript?: (text: string) => void;

    onAssistantResponse?: (text: string) => void;

    onAssistantStreamStart?: () => void;

    onAssistantStream?: (token: string) => void;

    onAssistantStreamEnd?: () => void;

    onAssistantAudio?: (audio: ArrayBuffer) => void;

}