import type { DebugFormState, DebugState } from "../types/debug";

export const defaultFormState: DebugFormState = {
  question: "",
  userId: "",
  model: "glm-4.7-flash",
  routeMode: "auto",
  stream: true,
};

export const mockDebugState: DebugState = {
  traceId: "",
  sessionId: "",
  userId: "",
  routeType: "",
  model: "",
  stream: false,
  apiBaseUrl: "",
  graphState: {},
  context: {},
  recallItems: [],
  cacheInfo: {
    hit: false,
    scope: "",
    key: "",
    ttl: "",
  },
  toolCalls: [],
  apiResponse: {},
  renderedPayload: {},
  timeline: [],
  messages: [],
  tableRows: [],
};
