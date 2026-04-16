import { useState } from "react";

import { defaultFormState, mockDebugState } from "../data/mockDebugData";
import {
  fetchChatDebug,
  fetchChatHistory,
  getApiBaseUrl,
  sendChatRequest,
  streamChatRequest,
} from "../lib/api";
import type {
  ChatHistoryApiResponse,
  ChatMessage,
  ChatResponse,
  DebugFormState,
  DebugState,
  PreviewTab,
  RouteMode,
  StreamDoneEvent,
  StreamDeltaEvent,
} from "../types/debug";

function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleTimeString("zh-CN", { hour12: false });
}

function toMessagesFromHistory(history: ChatHistoryApiResponse): ChatMessage[] {
  return history.items.map((item) => ({
    id: item.id,
    role: item.role === "assistant" ? "assistant" : "user",
    content: item.content,
    timestamp: formatTimestamp(item.created_at),
    isStreaming: false,
  }));
}

function mergeNonStreamResponse(
  current: DebugState,
  form: DebugFormState,
  response: ChatResponse,
): DebugState {
  return {
    ...current,
    sessionId: response.session_id,
    userId: response.user_id ?? form.userId,
    routeType: response.route_type ?? current.routeType,
    model: response.model,
    stream: false,
    apiResponse: response,
    messages: [
      {
        id: `user-${Date.now()}`,
        role: "user",
        content: form.question,
        timestamp: new Date().toLocaleTimeString("zh-CN", { hour12: false }),
        routeMode: form.routeMode,
      },
      {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: response.content,
        timestamp: new Date().toLocaleTimeString("zh-CN", { hour12: false }),
      },
    ],
  };
}

function mergeStreamDelta(current: DebugState, form: DebugFormState, event: StreamDeltaEvent): DebugState {
  const userMessage: ChatMessage = {
    id: `user-${event.session_id}`,
    role: "user",
    content: form.question,
    timestamp: new Date().toLocaleTimeString("zh-CN", { hour12: false }),
    routeMode: form.routeMode,
  };

  const assistant = current.messages.find((message) => message.role === "assistant");
  const assistantMessage: ChatMessage = assistant
    ? { ...assistant, content: `${assistant.content}${event.delta}`, isStreaming: true }
    : {
        id: `assistant-${event.session_id}`,
        role: "assistant",
        content: event.delta,
        timestamp: new Date().toLocaleTimeString("zh-CN", { hour12: false }),
        isStreaming: true,
      };

  return {
    ...current,
    sessionId: event.session_id,
    userId: event.user_id,
    routeType: event.route_type ?? current.routeType,
    model: event.model,
    stream: true,
    messages: [userMessage, assistantMessage],
  };
}

function mergeStreamDone(current: DebugState, event: StreamDoneEvent): DebugState {
  return {
    ...current,
    sessionId: event.session_id,
    userId: event.user_id,
    routeType: event.route_type ?? current.routeType,
    model: event.model,
    stream: false,
    apiResponse: event,
    messages: current.messages.map((message) =>
      message.role === "assistant"
        ? {
            ...message,
            content: event.content,
            isStreaming: false,
          }
        : message,
    ),
  };
}

export function useDebugConsoleState() {
  const [form, setForm] = useState<DebugFormState>(defaultFormState);
  const [previewTab, setPreviewTab] = useState<PreviewTab>("table");
  const [debugState, setDebugState] = useState<DebugState>({
    ...mockDebugState,
    apiBaseUrl: getApiBaseUrl(),
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  function updateField<K extends keyof DebugFormState>(key: K, value: DebugFormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function handleRouteModeChange(value: RouteMode) {
    updateField("routeMode", value);
  }

  async function syncSessionData(sessionId: string) {
    const [history, detail] = await Promise.all([fetchChatHistory(sessionId), fetchChatDebug(sessionId)]);
    setDebugState((current) => ({
      ...current,
      sessionId: detail.session_id,
      userId: detail.user_id ?? current.userId,
      graphState: detail.graph_state,
      context: {
        ...detail.context,
        backend_url: getApiBaseUrl(),
      },
      recallItems: detail.recall_items,
      cacheInfo: detail.cache_info,
      toolCalls: detail.tool_calls.map((item) => ({
        id: item.id,
        name: item.name,
        target: item.target,
        status: item.status,
        latencyMs: item.latency_ms,
      })),
      apiResponse: detail.api_response,
      renderedPayload: detail.rendered_payload,
      timeline: detail.timeline,
      messages: toMessagesFromHistory(history),
      tableRows: detail.timeline.map((item, index) => ({
        step: index + 1,
        node: item.label,
        duration: item.status === "completed" ? "done" : "pending",
        status: item.status,
      })),
    }));
  }

  async function handleSend() {
    if (!form.question.trim()) {
      setErrorMessage("请输入调试问题。");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage("");

    try {
      if (form.stream) {
        let streamedSessionId = "";
        await streamChatRequest(form, {
          onDelta: (event: StreamDeltaEvent) => {
            streamedSessionId = event.session_id;
            setDebugState((current) => mergeStreamDelta(current, form, event));
          },
          onDone: (event: StreamDoneEvent) => {
            streamedSessionId = event.session_id;
            setDebugState((current) => mergeStreamDone(current, event));
          },
        });
        const currentSessionId = streamedSessionId || debugState.sessionId;
        if (currentSessionId) {
          await syncSessionData(currentSessionId);
        }
      } else {
        const response = await sendChatRequest(form);
        setDebugState((current) => mergeNonStreamResponse(current, form, response));
        await syncSessionData(response.session_id);
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "请求失败");
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleReset() {
    setForm(defaultFormState);
    setPreviewTab("table");
    setErrorMessage("");
    setDebugState({
      ...mockDebugState,
      apiBaseUrl: getApiBaseUrl(),
    });
  }

  return {
    form,
    debugState,
    previewTab,
    isSubmitting,
    errorMessage,
    updateField,
    handleRouteModeChange,
    setPreviewTab,
    handleSend,
    handleReset,
  };
}
