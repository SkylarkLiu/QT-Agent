import { Play, RotateCcw } from "lucide-react";

import type { DebugFormState, RouteMode } from "../../types/debug";
import { Button } from "../ui/Button";
import { Card, CardBody, CardHeader } from "../ui/Card";
import { Field, Input, Select, Switch, Textarea } from "../ui/Input";
import "./debug-console.css";

type ControlPanelProps = {
  form: DebugFormState;
  apiBaseUrl: string;
  isSubmitting: boolean;
  errorMessage: string;
  onChange: <K extends keyof DebugFormState>(key: K, value: DebugFormState[K]) => void;
  onRouteModeChange: (value: RouteMode) => void;
  onSend: () => void;
  onReset: () => void;
};

export function ControlPanel({
  form,
  apiBaseUrl,
  isSubmitting,
  errorMessage,
  onChange,
  onRouteModeChange,
  onSend,
  onReset,
}: ControlPanelProps) {
  return (
    <Card tone="bordered">
      <CardHeader
        title="输入与控制"
        description="用于配置本次调试请求的输入参数。"
        actions={<span className="panelHeaderAction monoMeta">{apiBaseUrl}</span>}
      />
      <CardBody className="controlGrid">
        <Field label="用户问题输入框">
          <Textarea value={form.question} onChange={(event) => onChange("question", event.target.value)} />
        </Field>
        <Field label="user_id">
          <Input value={form.userId} onChange={(event) => onChange("userId", event.target.value)} />
        </Field>
        <Field label="模型选择">
          <Select value={form.model} onChange={(event) => onChange("model", event.target.value)}>
            <option value="glm-4.7-flash">glm-4.7-flash</option>
            <option value="mock-echo">mock-echo</option>
          </Select>
        </Field>
        <Field label="路由模式选择">
          <Select value={form.routeMode} onChange={(event) => onRouteModeChange(event.target.value as RouteMode)}>
            <option value="auto">auto</option>
            <option value="knowledge">knowledge</option>
            <option value="websearch">websearch</option>
            <option value="tool">tool</option>
          </Select>
        </Field>
        <Switch
          label="是否流式输出"
          hint="开启后中间区域将展示流式调试片段。"
          checked={form.stream}
          onChange={(value) => onChange("stream", value)}
        />
        <div className="buttonRow">
          <Button leadingIcon={<Play />} onClick={onSend} disabled={isSubmitting}>
            {isSubmitting ? "请求中" : "发送按钮"}
          </Button>
          <Button variant="secondary" leadingIcon={<RotateCcw />} onClick={onReset} disabled={isSubmitting}>
            清空按钮
          </Button>
        </div>
        {errorMessage ? <div className="errorBanner">{errorMessage}</div> : null}
      </CardBody>
    </Card>
  );
}
