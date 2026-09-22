/**
 * 环境自检页（原 App.tsx 的内容，整体搬过来）。
 *
 * 这一页是给组员用的：打开就能看到"后端通不通、依赖装没装、Key 配没配"，
 * 不用去看终端日志猜。
 *
 * 路由：/debug
 * 注意页面上的 "存在待处理项" 很可能只因为**可选**的多模态 Key 没配，
 * 不代表你的环境有问题。
 */

import { useEffect, useState } from "react";

import { api } from "@/api/client";
import type { EnvCheckResponse, HealthResponse } from "@/types/api";

export default function DebugPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [envCheck, setEnvCheck] = useState<EnvCheckResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [healthData, envData] = await Promise.all([api.health(), api.envCheck()]);
        if (cancelled) return;
        setHealth(healthData);
        setEnvCheck(envData);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "未知错误");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="app">
      <h1>环境自检</h1>
      <p className="muted">
        脚手架自检页 —— 确认环境通了再用 <a href="/">对话页</a>。
      </p>

      {loading && <div className="card">正在连接后端…</div>}

      {error && (
        <div className="card">
          <h2>❌ 后端未就绪</h2>
          <pre>{error}</pre>
          <p className="muted">
            排查：确认已在 <code>backend</code> 目录执行{" "}
            <code>uvicorn app.main:app --reload --port 8000</code>
          </p>
        </div>
      )}

      {health && (
        <div className="card">
          <h2>后端状态</h2>
          <p>
            应用：{health.app_name} 环境：<code>{health.env}</code>
          </p>
          <p>
            LLM 配置：{" "}
            <span className={health.llm_configured ? "badge ok" : "badge err"}>
              {health.llm_configured ? "已配置" : "未配置"}
            </span>{" "}
            多模态：
            <span className={health.multimodal_enabled ? "badge ok" : "badge warn"}>
              {health.multimodal_enabled ? "已启用" : "未启用（视频将降级）"}
            </span>
          </p>
        </div>
      )}

      {envCheck && (
        <div className="card">
          <h2>
            环境自检{" "}
            <span className={envCheck.all_ok ? "badge ok" : "badge warn"}>
              {envCheck.all_ok ? "全部通过" : "存在待处理项"}
            </span>
          </h2>
          <p className="muted">
            注意：带「（可选）」的项即使没配也会让这里显示"存在待处理项"，
            不影响核心功能。
          </p>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <tbody>
              {envCheck.checks.map((check) => (
                <tr key={check.item}>
                  <td style={{ padding: "6px 8px", width: 60 }}>
                    {check.ok ? "✅" : "⚠️"}
                  </td>
                  <td style={{ padding: "6px 8px" }}>{check.item}</td>
                  <td style={{ padding: "6px 8px" }} className="muted">
                    {check.ok ? "" : check.hint}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted" style={{ marginTop: 12 }}>
            {envCheck.python_hint}
          </p>
        </div>
      )}

      {health && (
        <div className="card">
          <h2>下一步</h2>
          <ol>
            <li>
              打开 <code>http://127.0.0.1:8000/docs</code> 试调接口
            </li>
            <li>
              在 <code>backend/.env</code> 填入 <code>LLM_API_KEY</code>
            </li>
            <li>按《组员手册》领取你负责的功能模块</li>
          </ol>
        </div>
      )}
    </div>
  );
}
