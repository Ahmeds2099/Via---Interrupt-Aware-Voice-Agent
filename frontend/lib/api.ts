import { env } from "./env";

export async function getSystemStatus() {
    const response = await fetch(`${env.apiUrl}/system/status`);

    if (!response.ok) {
        throw new Error("Unable to reach backend");
    }

    return response.json();
}