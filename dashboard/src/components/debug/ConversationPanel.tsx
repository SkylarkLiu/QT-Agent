import { Bot, User } from "lucide-react";

import type { ChatMessage, TimelineEvent } from "../../types/debug";
import { Card, CardBody, CardHeader } from "../ui/Card";
import "./debug-console.css";

type ConversationPanelProps = {
  messages: ChatMessage[];
  timeline: TimelineEvent[];
};

function statusClass(status: TimelineEvent["status"]): string {
  if (status === "completed") {
    return "statusCompleted";
  }
  if (status === "running") {
    return "statusRunning";
  }
  return "statusPending";
}

export function ConversationPanel({ messages, timeline }: ConversationPanelProps) {
  return (
    <div className="panelStack">
      <Card tone="bordered">
        <CardHeader title="对话与流式输出" description="展示用户输入、assistant 返回与流式调试内容。" />
        <CardBody className="conversationList">
          {messages.map((message) => (
            <article key={message.id} className="messageCard">
              <div className="messageMeta">
                <span className="messageRole">
                  {message.role === "user" ? <User className="icon16" /> : <Bot className="icon16" />}{" "}
                  {message.role}
                </span>
                <span>{message.timestamp}</span>
              </div>
              <div className="messageBody">{message.content}</div>
              <div className="messageMeta">
                <span>{message.routeMode ? `route: ${message.routeMode}` : "route: generated"}</span>
                <span>{message.isStreaming ? "streaming" : "complete"}</span>
              </div>
            </article>
          ))}
        </CardBody>
      </Card>

      <Card tone="bordered">
        <CardHeader title="关键日志时间线" description="按阶段展示当前调试流程。" />
        <CardBody className="timelineList">
          {timeline.map((item) => (
            <article key={item.id} className="timelineItem">
              <div className="timelineLabelRow">
                <strong>{item.label}</strong>
                <span className={`statusBadge ${statusClass(item.status)}`}>{item.status}</span>
              </div>
              <div className="timelineDetail">{item.detail}</div>
              <div className="timelineMeta">
                <span>{item.timestamp}</span>
                <span>{item.id}</span>
              </div>
            </article>
          ))}
        </CardBody>
      </Card>
    </div>
  );
}
