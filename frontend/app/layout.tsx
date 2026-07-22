import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Via | Adaptive Voice Intelligence",
  description: "An interruptible, emotionally adaptive, document-grounded universal voice agent.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">
        {process.env.NEXT_PUBLIC_DEPLOYMENT_PROFILE === "lite" && (
          <div style={{ backgroundColor: "#ffeb3b", color: "#000", padding: "10px", textAlign: "center", fontWeight: "bold", zIndex: 1000, fontSize: "0.9rem" }}>
            ⚠️ Lite Mode: This is a constrained build for free deployment. Full emotional intelligence and Whisper fallback are only available in the local/dev version. Responses may be slower than local.
          </div>
        )}
        {children}
      </body>
    </html>
  );
}
