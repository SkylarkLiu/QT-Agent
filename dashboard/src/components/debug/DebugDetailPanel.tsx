import { Blocks, Database, PackageSearch, ServerCrash, Wrench } from "lucide-react";

import type { CacheInfo, RecallItem, ToolCall } from "../../types/debug";
import { Card, CardBody, CardHeader } from "../ui/Card";
import "./debug-console.css";

type DebugDetailPanelProps = {
  graphState: Record<string, unknown>;
  context: Record<string, unknown>;
  recallItems: RecallItem[];
  cacheInfo: CacheInfo;
  toolCalls: ToolCall[];
  apiResponse: Record<string, unknown>;
  renderedPayload: Record<string, unknown>;
};

function toolStatusClass(status: ToolCall["status"]): string {
  if (status === "completed") {
    return "statusCompleted";
  }
  if (status === "running") {
    return "statusRunning";
  }
  return "statusPending";
}

export function DebugDetailPanel({
  graphState,
  context,
  recallItems,
  cacheInfo,
  toolCalls,
  apiResponse,
  renderedPayload,
}: DebugDetailPanelProps) {
  return (
    <div className="panelStack">
      <Card tone="bordered">
        <CardHeader
          title="调试详情"
          description="当前 graph state、context、缓存和接口结果。"
          actions={<span className="panelHeaderAction monoMeta">{String(graphState.route_type ?? "unknown")}</span>}
        />
        <CardBody className="panelStack">
          <section className="detailSection">
            <div className="sectionLabel">
              <Blocks className="icon16" /> 当前 graph state / context
            </div>
            <pre className="jsonBlock">{JSON.stringify({ graphState, context }, null, 2)}</pre>
          </section>
          <section className="detailSection">
            <div className="sectionLabel">
              <PackageSearch className="icon16" /> recall 结果列表
            </div>
            <div className="recallList">
              {recallItems.map((item) => (
                <article key={item.id} className="recallItem">
                  <div className="recallHeader">
                    <strong>{item.title}</strong>
                    <span className="statusBadge">{item.score.toFixed(2)}</span>
                  </div>
                  <div className="detailMeta">
                    <span>{item.source}</span>
                    <span>{item.id}</span>
                  </div>
                  <div className="recallSnippet">{item.snippet}</div>
                </article>
              ))}
            </div>
          </section>
          <section className="detailSection">
            <div className="sectionLabel">
              <Database className="icon16" /> 命中缓存信息
            </div>
            <div className="detailItem">
              <div className="detailMeta">
                <span>hit</span>
                <span className={`statusBadge ${cacheInfo.hit ? "statusCompleted" : "statusPending"}`}>
                  {String(cacheInfo.hit)}
                </span>
              </div>
              <div className="detailValue monoMeta">{cacheInfo.key}</div>
              <div className="detailMeta">
                <span>{cacheInfo.scope}</span>
                <span>{cacheInfo.ttl}</span>
              </div>
            </div>
          </section>
          <section className="detailSection">
            <div className="sectionLabel">
              <Wrench className="icon16" /> 调用的工具 / MCP 接口
            </div>
            <div className="toolList">
              {toolCalls.map((item) => (
                <article key={item.id} className="toolItem">
                  <div className="toolHeader">
                    <strong>{item.name}</strong>
                    <span className={`statusBadge ${toolStatusClass(item.status)}`}>{item.status}</span>
                  </div>
                  <div className="detailMeta">
                    <span>{item.target}</span>
                    <span>{item.latencyMs}ms</span>
                  </div>
                </article>
              ))}
            </div>
          </section>
          <section className="detailSection">
            <div className="sectionLabel">
              <ServerCrash className="icon16" /> 原始接口返回 JSON
            </div>
            <pre className="jsonBlock">{JSON.stringify(apiResponse, null, 2)}</pre>
          </section>
          <section className="detailSection">
            <div className="sectionLabel">
              <Blocks className="icon16" /> 最终结构化渲染数据
            </div>
            <pre className="jsonBlock">{JSON.stringify(renderedPayload, null, 2)}</pre>
          </section>
        </CardBody>
      </Card>
    </div>
  );
}
