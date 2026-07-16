"use client";

import { useEffect, useState } from "react";
import { getSystemStatus } from "@/lib/api";

export default function Home() {
  const [status, setStatus] = useState("Connecting...");

  useEffect(() => {
    async function load() {
      try {
        const data = await getSystemStatus();
        setStatus(data.status);
      } catch {
        setStatus("Backend Offline");
      }
    }

    load();
  }, []);

  return (
    <main className="flex min-h-screen items-center justify-center">
      <div className="space-y-4 text-center">
        <h1 className="text-5xl font-bold">Via</h1>

        <p>Adaptive Universal Resilient Agent</p>

        <div className="rounded-lg border p-4">
          <p>Backend Status</p>

          <p className="font-semibold">{status}</p>
        </div>
      </div>
    </main>
  );
}