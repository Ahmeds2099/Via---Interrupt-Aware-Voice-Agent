"use client";

import ConnectionStatus from "@/components/voice/connectionstatus";
import VoiceButton from "@/components/voice/voicebutton";
import { useVoice } from "@/hooks/usevoice";

export default function HomePage() {

  const {

    connected,

    connecting,

    listening,

    connect,

    disconnect,

    startListening,

    stopListening,

  } = useVoice();

  return (

    <main className="flex min-h-screen flex-col items-center justify-center gap-8">

      <h1 className="text-4xl font-bold">

        Via

      </h1>

      <ConnectionStatus

        connected={connected}

        connecting={connecting}

      />

      <VoiceButton

        connected={connected}

        listening={listening}

        connect={connect}

        disconnect={disconnect}

        startListening={startListening}

        stopListening={stopListening}

      />

    </main>

  );

}