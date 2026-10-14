import { fetchEventSource } from "@microsoft/fetch-event-source";
import type { RequestTurnEvents, ResponseTurnEvent } from "@/shared/api/generated/schema";

class StreamRejected extends Error {}

export async function subscribeTurn(
  body: RequestTurnEvents, signal: AbortSignal,
  onEvent: (event: ResponseTurnEvent) => void,
  onConnection: (state: "live" | "reconnecting") => void,
): Promise<void> {
  let cursor = body.afterSequence ?? 0;
  let terminal = false;
  let retries = 0;
  await fetchEventSource("/api/v1/assistant/turns/events", {
    method: "POST", credentials: "same-origin", signal, openWhenHidden: true,
    headers: { "Content-Type": "application/json" },
    // Reconnection must use the newest cursor in the POST body, not just Last-Event-ID.
    fetch: (url, init) => fetch(url, { ...init, body: JSON.stringify({ ...body, afterSequence: cursor }) }),
    async onopen(response) {
      if (response.status === 401) {
        window.dispatchEvent(new Event("risk:session-expired"));
        throw new StreamRejected("Session expired");
      }
      if (!response.ok) {
        if (response.status < 500) throw new StreamRejected(`Stream rejected (${response.status})`);
        throw new Error("Stream unavailable");
      }
      if (!response.headers.get("content-type")?.startsWith("text/event-stream")) {
        throw new StreamRejected("Invalid stream content type");
      }
      onConnection("live");
    },
    onmessage(frame) {
      if (frame.event !== "turn_event") return;
      const event: ResponseTurnEvent = JSON.parse(frame.data);
      if (event.version !== 1 || event.turnId !== body.turnId || !Number.isInteger(event.sequence)) {
        throw new StreamRejected("Unsupported event protocol");
      }
      if (event.sequence <= cursor) return;
      if (event.sequence !== cursor + 1) throw new StreamRejected("Event sequence gap; reload history");
      onEvent(event);
      cursor = event.sequence;
      retries = 0;
      terminal = Boolean(event.status && event.status !== "running");
    },
    onclose() {
      if (!terminal) throw new Error("Stream disconnected");
    },
    onerror(error) {
      if (error instanceof StreamRejected || ++retries > 5) throw error;
      onConnection("reconnecting");
      return Math.min(1000 * 2 ** (retries - 1), 10000);
    },
  });
}
