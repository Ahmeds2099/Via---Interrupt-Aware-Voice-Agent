export const env = {
    apiUrl:
        process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000",
};

export const resolveApiUrl = () => {
    // The configured URL is authoritative. Rewriting loopback to the page's
    // LAN hostname breaks local development when Uvicorn is intentionally
    // bound to 127.0.0.1. LAN deployments can explicitly configure a LAN URL.
    return env.apiUrl.replace(/\/$/, "");
};
