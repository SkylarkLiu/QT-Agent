import type { PreviewTab } from "../../types/debug";
import { Card, CardBody, CardHeader } from "../ui/Card";
import { Tabs } from "../ui/Tabs";
import "./debug-console.css";

type ResultPreviewPanelProps = {
  previewTab: PreviewTab;
  onPreviewTabChange: (value: PreviewTab) => void;
  tableRows: Array<Record<string, string | number>>;
  renderedPayload: Record<string, unknown>;
  apiResponse: Record<string, unknown>;
};

const previewItems = [
  { value: "table", label: "表格预览" },
  { value: "chart", label: "图表预览占位" },
  { value: "json", label: "JSON 预览" },
] as const;

export function ResultPreviewPanel({
  previewTab,
  onPreviewTabChange,
  tableRows,
  renderedPayload,
  apiResponse,
}: ResultPreviewPanelProps) {
  const columns = Object.keys(tableRows[0] ?? {});

  return (
    <Card tone="bordered">
      <CardHeader title="结果预览区" description="用于预览结构化渲染结果与底层 JSON 数据。" />
      <CardBody>
        <Tabs items={[...previewItems]} value={previewTab} onChange={onPreviewTabChange}>
          <div className="previewGrid">
            {previewTab === "table" ? (
              <table className="previewTable">
                <thead>
                  <tr>
                    {columns.map((column) => (
                      <th key={column}>{column}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tableRows.map((row, index) => (
                    <tr key={`row-${index}`}>
                      {columns.map((column) => (
                        <td key={column}>{String(row[column])}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : null}

            {previewTab === "chart" ? (
              <div className="chartPlaceholder">
                <div className="tableMeta">
                  <span>图表预览占位</span>
                  <span>后续接真实图表库</span>
                </div>
                <div className="chartBars">
                  <div className="chartBar chartBarPrimary chartBarLarge" />
                  <div className="chartBar chartBarMedium" />
                  <div className="chartBar chartBarPrimary chartBarSmall" />
                  <div className="chartBar chartBarTiny" />
                </div>
              </div>
            ) : null}

            {previewTab === "json" ? (
              <pre className="jsonBlock">{JSON.stringify({ renderedPayload, apiResponse }, null, 2)}</pre>
            ) : null}
          </div>
        </Tabs>
      </CardBody>
    </Card>
  );
}
