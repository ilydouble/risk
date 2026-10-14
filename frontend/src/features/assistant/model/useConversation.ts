import { useCallback, useEffect, useRef, useState } from "react";
import * as AssistantApi from "@/entities/assistant/api/assistantApi";
import { subscribeTurn } from "@/entities/assistant/api/events";
import { applyTurnEvent } from "@/entities/assistant/model/events";
import type { Conversation, Turn } from "@/entities/assistant/model/types";
import type { RequestCreateTurn } from "@/shared/api/generated/schema";
import { handleApiError } from "@/shared/api/http";

export function useConversation(conversationId: string | null, select: (id: string) => void) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [connection, setConnection] = useState<"live" | "reconnecting" | "offline">("offline");
  const [reload, setReload] = useState(0);
  const generation = useRef(0);
  const busy = useRef(false);
  const pendingRequest = useRef<RequestCreateTurn | null>(null);
  const active = turns.find(turn => turn.status === "running");

  const refreshList = useCallback(async () => {
    const response = await AssistantApi.requestListConversations({});
    setConversations(response.conversations);
  }, []);
  useEffect(() => { void refreshList().catch(cause => setError(handleApiError(cause))); }, [refreshList]);
  useEffect(() => {
    const ticket = ++generation.current;
    setTurns([]);
    setError("");
    if (!conversationId) { setLoading(false); return; }
    setLoading(true);
    void AssistantApi.requestGetConversation({ conversationId }).then(response => {
      if (ticket === generation.current) setTurns(response.turns);
    }).catch(cause => {
      if (ticket === generation.current) setError(handleApiError(cause));
    }).finally(() => { if (ticket === generation.current) setLoading(false); });
    return () => { generation.current = ticket + 1; };
  }, [conversationId, reload]);

  const activeId = active?.id;
  useEffect(() => {
    if (!activeId || loading) return;
    const controller = new AbortController();
    const turn = turns.find(value => value.id === activeId)!;
    void subscribeTurn({ turnId: activeId, afterSequence: turn.sequence }, controller.signal,
      event => setTurns(current => current.map(value => applyTurnEvent(value, event))), setConnection,
    ).then(() => { if (!controller.signal.aborted) return refreshList(); }).catch(() => {
      if (!controller.signal.aborted) { setConnection("offline"); setError("STREAM_DISCONNECTED"); }
    });
    return () => controller.abort();
    // A snapshot sequence change must not restart the subscription on every token.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeId, loading, reload]);

  async function send(message: string, configuration: Pick<RequestCreateTurn, "connection" | "maxTokens">) {
    if (busy.current || active || !message.trim()) return false;
    busy.current = true;
    setSending(true);
    setError("");
    try {
      let id = conversationId;
      if (!id) {
        id = (await AssistantApi.requestCreateConversation({})).conversation.id;
        select(id);
      }
      const previous = pendingRequest.current;
      const matching = previous?.conversationId === id && previous.message === message.trim()
        && JSON.stringify(previous.connection) === JSON.stringify(configuration.connection)
        && previous.maxTokens === configuration.maxTokens;
      const request: RequestCreateTurn = matching ? previous : {
        conversationId: id, message: message.trim(), requestKey: crypto.randomUUID(), ...configuration,
      };
      pendingRequest.current = request;
      const response = await AssistantApi.requestCreateTurn(request);
      pendingRequest.current = null;
      // Load the authoritative snapshot after navigation; it may already include streamed items.
      select(id);
      setTurns(current => [...current.filter(turn => turn.id !== response.turn.id), response.turn]);
      setReload(value => value + 1);
      await refreshList().catch(cause => setError(handleApiError(cause)));
      return true;
    } catch (cause) {
      setError(handleApiError(cause, {
        ASSISTANT_BUSY: "ASSISTANT_BUSY", ASSISTANT_CAPACITY: "ASSISTANT_CAPACITY",
      }));
      return false;
    } finally { busy.current = false; setSending(false); }
  }

  async function cancel() {
    if (!active) return;
    try {
      const response = await AssistantApi.requestCancelTurn({ turnId: active.id });
      setTurns(current => current.map(turn => turn.id === active.id ? response.turn : turn));
    } catch (cause) { setError(handleApiError(cause)); }
  }

  return { conversations, turns, loading, sending, error, connection, active, send, cancel,
    retry: () => setReload(value => value + 1) };
}
