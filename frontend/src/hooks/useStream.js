import { useRef, useCallback } from "react";
import { openStream } from "../services/api";
import { useApp } from "../context/AppContext";

/**
 * useStream — manages the WebSocket stream lifecycle.
 *
 * Returns { startStream, stopStream }
 */
export function useStream() {
  const wsRef = useRef(null);
  const { llmConfig, connectors, activeSessionId, setStreamState, setRightPanel, appendMessage } = useApp();

  const stopStream = useCallback(() => {
    console.log("[useStream] Stopping stream");
    wsRef.current?.stop();
    wsRef.current = null;
    setStreamState((s) => ({ ...s, active: false }));
  }, [setStreamState]);

  const startStream = useCallback((prompt, intervalSec = 1, durationSec = null) => {
    console.log("[useStream] Starting stream:", prompt);

    // Build active connector config if any is configured
    let connector = null;
    for (const [type, val] of Object.entries(connectors)) {
      if (val.configured) {
        const typeMap = { publicApi: "public-api", hivemq: "hivemq", snowflake: "snowflake", databricks: "databricks" };
        connector = { type: typeMap[type], ...val.config };
        console.log("[useStream] Using connector:", connector.type);
        break;
      }
    }

    // Reset stream state and open right panel
    setStreamState({ active: true, records: [], total: 0, status: "Connecting..." });
    setRightPanel("stream");

    const ws = openStream(
      {
        prompt,
        backend:     llmConfig.backend,
        apiKey:      llmConfig.apiKey,
        intervalSec,
        durationSec,
        connector,
        sessionId:   activeSessionId,
      },
      {
        onStatus: (msg) => {
          console.log("[useStream] status:", msg.message);
          setStreamState((s) => ({ ...s, status: msg.message }));
        },
        onRecord: (msg) => {
          setStreamState((s) => ({
            ...s,
            records: [msg.data, ...s.records].slice(0, 200), // keep latest 200
            total: msg.index,
          }));
        },
        onDone: (msg) => {
          console.log("[useStream] done. Total:", msg.total);
          setStreamState((s) => ({ ...s, active: false, total: msg.total, status: "Done" }));
          appendMessage("assistant", { type: "stream_done", total: msg.total, prompt });
        },
        onError: (msg) => {
          console.error("[useStream] error:", msg.message);
          setStreamState((s) => ({ ...s, active: false, status: `Error: ${msg.message}` }));
        },
      }
    );

    wsRef.current = ws;
  }, [llmConfig, connectors, activeSessionId, setStreamState, setRightPanel, appendMessage]);

  return { startStream, stopStream };
}
