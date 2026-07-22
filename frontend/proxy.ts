import { NextRequest, NextResponse } from "next/server";

const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "::1"]);

function proxy(request: NextRequest) {
  if (process.env.NODE_ENV !== "development") {
    return NextResponse.next();
  }

  const configuredApi = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
  let backendIsLoopback = false;
  try {
    backendIsLoopback = LOOPBACK_HOSTS.has(new URL(configuredApi).hostname);
  } catch {
    return NextResponse.next();
  }

  if (backendIsLoopback && !LOOPBACK_HOSTS.has(request.nextUrl.hostname)) {
    const redirect = request.nextUrl.clone();
    redirect.hostname = "localhost";
    redirect.protocol = "http";
    redirect.port = request.nextUrl.port || "3000";
    return NextResponse.redirect(redirect);
  }

  return NextResponse.next();
}

export default proxy;

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
