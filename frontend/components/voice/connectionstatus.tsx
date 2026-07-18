"use client";

type Props = {

    connected: boolean;

    connecting: boolean;

};

export default function ConnectionStatus({

    connected,

    connecting,

}: Props) {

    if (connecting) {

        return (
            <p className="text-yellow-500">
                🟡 Connecting...
            </p>
        );
    }

    if (connected) {

        return (
            <p className="text-green-500">
                🟢 Connected
            </p>
        );
    }

    return (
        <p className="text-red-500">
            🔴 Disconnected
        </p>
    );
}