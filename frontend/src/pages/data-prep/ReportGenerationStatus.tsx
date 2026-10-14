import { useEffect, useState } from "react";

export function ReportGenerationStatus() {
  const [startedAt] = useState(() => Date.now());
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setElapsed(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [startedAt]);

  const hint = elapsed >= 180
    ? "这次等待较久，仍在等待模型返回。请求结束后会显示报告或失败原因。"
    : elapsed >= 60
      ? "报告还未返回。模型响应速度和报告长度会影响等待时间，请再稍等一会儿。"
      : "智能体需要读取字段统计、分析数据质量并撰写报告，可能需要几分钟。";

  return <div className="rounded-lg border border-primary-500/20 bg-primary-500/5 p-4">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <p className="flex items-center gap-2 text-sm font-medium">
        <span aria-hidden="true" className="h-4 w-4 rounded-full border-2 border-primary-500/25 border-t-primary-500 motion-safe:animate-spin" />
        正在生成数据分析报告
      </p>
      <span className="text-xs tabular-nums text-foreground-500" aria-live="off">已等待 {Math.floor(elapsed / 60)} 分 {elapsed % 60} 秒</span>
    </div>
    <p role="status" aria-atomic="true" className="mt-2 text-sm text-foreground-500">{hint}</p>
    <p className="mt-2 text-xs text-foreground-500">可以先查看下方体检结果。请保持此页面打开，无需重复提交；报告完成后会自动显示。</p>
  </div>;
}
