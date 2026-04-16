import { ConsoleShell } from "./components/layout/ConsoleShell";
import { ControlPanel } from "./components/debug/ControlPanel";
import { ConversationPanel } from "./components/debug/ConversationPanel";
import { DebugDetailPanel } from "./components/debug/DebugDetailPanel";
import { ResultPreviewPanel } from "./components/debug/ResultPreviewPanel";
import { useDebugConsoleState } from "./hooks/useDebugConsoleState";

export default function App() {
  const {
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
  } = useDebugConsoleState();

  return (
    <ConsoleShell
      title="AI 调试控制台"
      subtitle="用于调试请求、上下文、路由结果、工具调用、接口返回和可视化渲染结果"
      left={
        <ControlPanel
          form={form}
          apiBaseUrl={debugState.apiBaseUrl}
          isSubmitting={isSubmitting}
          errorMessage={errorMessage}
          onChange={updateField}
          onRouteModeChange={handleRouteModeChange}
          onSend={handleSend}
          onReset={handleReset}
        />
      }
      center={<ConversationPanel messages={debugState.messages} timeline={debugState.timeline} />}
      right={
        <DebugDetailPanel
          graphState={debugState.graphState}
          context={debugState.context}
          recallItems={debugState.recallItems}
          cacheInfo={debugState.cacheInfo}
          toolCalls={debugState.toolCalls}
          apiResponse={debugState.apiResponse}
          renderedPayload={debugState.renderedPayload}
        />
      }
      bottom={
        <ResultPreviewPanel
          previewTab={previewTab}
          onPreviewTabChange={setPreviewTab}
          tableRows={debugState.tableRows}
          renderedPayload={debugState.renderedPayload}
          apiResponse={debugState.apiResponse}
        />
      }
    />
  );
}
