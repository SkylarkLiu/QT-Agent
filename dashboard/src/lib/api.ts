import type {
  ChatDebugApiResponse,
  ChatHistoryApiResponse,
  ChatResponse,
  DebugFormState,
  RouteMode,
  StreamDoneEvent,
  StreamDeltaEvent,
  StreamErrorEvent,
} from "../types/debug";

const DEFAULT_API_BASE_URL = "http://localhost:8000";

export function getApiBaseUrl(): string {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  return envUrl && envUrl.length > 0 ? envUrl : DEFAULT_API_BASE_URL;
}

type SendChatPayload = DebugFormState;

export async function sendChatRequest(payload: SendChatPayload): Promise<ChatResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(buildChatPayload(payload)),
  });
  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }
  return (await response.json()) as ChatResponse;
}

export async function streamChatRequest(
  payload: SendChatPayload,
  handlers: {
    onDelta: (event: StreamDeltaEvent) => void;
    onDone: (event: StreamDoneEvent) => void;
  },
): Promise<void> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(buildChatPayload({ ...payload, stream: true })),
  });
  if (!response.ok || !response.body) {
    throw new Error(await readErrorMessage(response));
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let currentEvent = "message";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";

    for (const chunk of chunks) {
      const lines = chunk.split("\n");
      let data = "";
      currentEvent = "message";
      for (const line of lines) {
        if (line.startsWith("event:")) {
          currentEvent = line.slice(6).trim();
        }
        if (line.startsWith("data:")) {
          data += line.slice(5).trim();
        }
      }
      if (!data) {
        continue;
      }

      if (currentEvent === "delta") {
        handlers.onDelta(JSON.parse(data) as StreamDeltaEvent);
      } else if (currentEvent === "done") {
        handlers.onDone(JSON.parse(data) as StreamDoneEvent);
      } else if (currentEvent === "error") {
        const event = JSON.parse(data) as StreamErrorEvent;
        throw new Error(event.detail);
      }
    }
  }
}

export async function fetchChatHistory(sessionId: string): Promise<ChatHistoryApiResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/chat/history?session_id=${encodeURIComponent(sessionId)}&limit=50`);
  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }
  return (await response.json()) as ChatHistoryApiResponse;
}

export async function fetchChatDebug(sessionId: string): Promise<ChatDebugApiResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/chat/debug?session_id=${encodeURIComponent(sessionId)}&limit=50`);
  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }
  return (await response.json()) as ChatDebugApiResponse;
}

function buildChatPayload(payload: SendChatPayload) {
  return {
    username: payload.userId || "debug-console",
    user_id: payload.userId || undefined,
    message: payload.question,
    model: payload.model,
    route_mode: normalizeRouteMode(payload.routeMode),
    stream: payload.stream,
  };
}

function normalizeRouteMode(routeMode: RouteMode): RouteMode {
  return routeMode;
}

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: string };
    return data.detail || `Request failed with status ${response.status}`;
  } catch {
    return `Request failed with status ${response.status}`;
  }
}
