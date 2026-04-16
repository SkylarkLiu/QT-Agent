export type RouteMode = "auto" | "knowledge" | "websearch" | "tool";
export type PreviewTab = "table" | "chart" | "json";
export type LogStatus = "completed" | "running" | "pending";

export type ChatRole = "user" | "assistant";

export type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  timestamp: string;
  routeMode?: RouteMode;
  isStreaming?: boolean;
};

export type TimelineEvent = {
  id: string;
  label: string;
  status: LogStatus;
  timestamp: string;
  detail: string;
};

export type RecallItem = {
  id: string;
  title: string;
  source: string;
  score: number;
  snippet: string;
};

export type ToolCall = {
  id: string;
  name: string;
  target: string;
  status: LogStatus;
  latencyMs: number;
};

export type CacheInfo = {
  hit: boolean;
  scope: string;
  key: string;
  ttl: string;
};

export type DebugState = {
  traceId: string;
  sessionId: string;
  userId: string;
  routeType: string;
  model: string;
  stream: boolean;
  apiBaseUrl: string;
  graphState: Record<string, unknown>;
  context: Record<string, unknown>;
  recallItems: RecallItem[];
  cacheInfo: CacheInfo;
  toolCalls: ToolCall[];
  apiResponse: Record<string, unknown>;
  renderedPayload: Record<string, unknown>;
  timeline: TimelineEvent[];
  messages: ChatMessage[];
  tableRows: Array<Record<string, string | number>>;
};

export type DebugFormState = {
  question: string;
  userId: string;
  model: string;
  routeMode: RouteMode;
  stream: boolean;
};

export type ChatResponse = {
  session_id: string;
  user_id: string | null;
  model: string;
  content: string;
  provider: string;
  route_type: string | null;
  cache_hit: boolean;
  finish_reason: string | null;
  usage: Record<string, unknown>;
};

export type ChatHistoryItem = {
  id: string;
  session_id: string;
  user_id: string | null;
  role: string;
  content: string;
  model: string | null;
  metadata: Record<string, unknown>;
  token_usage: Record<string, unknown>;
  created_at: string;
};

export type ChatHistoryApiResponse = {
  session_id: string;
  items: ChatHistoryItem[];
};

export type ChatDebugToolCall = {
  id: string;
  name: string;
  target: string;
  status: LogStatus;
  latency_ms: number;
};

export type ChatDebugTimelineItem = {
  id: string;
  label: string;
  status: LogStatus;
  timestamp: string;
  detail: string;
};

export type ChatDebugApiResponse = {
  session_id: string;
  user_id: string | null;
  graph_state: Record<string, unknown>;
  context: Record<string, unknown>;
  recall_items: RecallItem[];
  cache_info: CacheInfo;
  tool_calls: ChatDebugToolCall[];
  api_response: Record<string, unknown>;
  rendered_payload: Record<string, unknown>;
  timeline: ChatDebugTimelineItem[];
};

export type StreamDeltaEvent = {
  session_id: string;
  user_id: string;
  model: string;
  provider: string;
  delta: string;
  index: number;
  route_type: string | null;
  cache_hit: boolean;
};

export type StreamDoneEvent = {
  session_id: string;
  user_id: string;
  model: string;
  provider: string;
  content: string;
  finish_reason: string | null;
  route_type: string | null;
  cache_hit: boolean;
  timestamp: string;
};

export type StreamErrorEvent = {
  detail: string;
};
