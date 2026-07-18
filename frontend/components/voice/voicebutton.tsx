"use client";

type Props = {

    connected: boolean;

    listening: boolean;

    connect(): void;

    disconnect(): void;

    startListening(): void;

    stopListening(): void;

};

export default function VoiceButton({

    connected,

    listening,

    connect,

    disconnect,

    startListening,

    stopListening,

}: Props) {

    if (!connected) {

        return (

            <button

                onClick={connect}

                className="rounded-md bg-black px-5 py-3 text-white"

            >

                Connect

            </button>

        );

    }

    return (

        <div className="flex gap-4">

            <button

                onClick={disconnect}

                className="rounded-md bg-red-600 px-5 py-3 text-white"

            >

                Disconnect

            </button>

            <button

                onClick={

                    listening

                        ? stopListening

                        : startListening

                }

                className="rounded-md bg-green-600 px-5 py-3 text-white"

            >

                {

                    listening

                        ? "Stop Listening"

                        : "Start Listening"

                }

            </button>

        </div>

    );

}