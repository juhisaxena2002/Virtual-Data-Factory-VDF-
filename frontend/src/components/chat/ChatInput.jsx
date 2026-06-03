import React, { useState } from "react";
import { Send, Radio, Square, Loader2 } from "lucide-react";
import { useApp } from "../../context/AppContext";
import { generateBatch } from "../../services/api";
import { useStream } from "../../hooks/useStream";

export default function ChatInput() {
  const { llmConfig, activeSessionId, newSession, appendMessage, setRightPanel } = useApp();
  const { startStream, stopStream } = useStream();
  const [prompt, setPrompt]       = useState("");
  const [loading, setLoading]     = useState(false);
  const [streaming, setStreaming]  = useState(false);

  const ensureSession = async () => {
    if (!activeSessionId) {
      console.log("[ChatInput] No active session — creating one");
      const s = await newSession(prompt.slice(0, 40) || "New chat");
      return s.id;
    }
    return activeSessionId;
  };

  const handleGenerate = async () => {
    if (!prompt.trim() || loading) return;
    console.log("[ChatInput] Generate batch:", prompt);
    await ensureSession();
    appendMessage("user", prompt);
    setLoading(true);
    try {
      const data = await generateBatch(prompt, llmConfig);
      appendMessage("assistant", data);
      setRightPanel("data");
    } catch (e) {
      console.error("[ChatInput] Generate error:", e);
      appendMessage("assistant", `Error: ${e.message}`);
    } finally {
      setLoading(false);
      setPrompt("");
    }
  };

  const handleStream = async () => {
    if (!prompt.trim()) return;
    if (streaming) {
      console.log("[ChatInput] Stopping stream");
      stopStream();
      setStreaming(false);
      return;
    }
    console.log("[ChatInput] Starting stream:", prompt);
    await ensureSession();
    appendMessage("user", `[Stream] ${prompt}`);
    setStreaming(true);
    startStream(prompt, 1, null);
    setPrompt("");
  };

  const handleKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleGenerate();
    }
  };

  return (
    <div style={styles.wrap}>
      <div style={styles.box}>
        <textarea
          style={styles.textarea}
          rows={2}
          placeholder="Describe the data you want to generate..."
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={handleKey}
        />
        <div style={styles.actions}>
          <span style={styles.hint}>Enter to generate · Shift+Enter for newline</span>
          <div style={styles.btnGroup}>
            {/* Stream button */}
            <button
              style={{ ...styles.streamBtn, ...(streaming ? styles.streamActive : {}) }}
              onClick={handleStream}
              title={streaming ? "Stop stream" : "Start live stream"}
            >
              {streaming ? <Square size={13} /> : <Radio size={13} />}
              {streaming ? "Stop Stream" : "Start Live"}
            </button>

            {/* Generate button */}
            <button
              style={styles.generateBtn}
              onClick={handleGenerate}
              disabled={loading || !prompt.trim()}
            >
              {loading ? <Loader2 size={13} style={styles.spin} /> : <Send size={13} />}
              {loading ? "Generating..." : "Generate"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

const styles = {
  wrap: {
    padding: "12px 24px 16px",
    borderTop: "1px solid #f0f0f0",
    background: "#fff",
  },
  box: {
    border: "1px solid #e8e8e8", borderRadius: 10,
    padding: "10px 12px",
    background: "#fafafa",
    transition: "border-color 0.2s",
    ":focus-within": { borderColor: "#f58321" },
  },
  textarea: {
    width: "100%", border: "none", outline: "none", resize: "none",
    fontSize: 13, color: "#1a1a1a", background: "transparent",
    fontFamily: "'DM Sans', sans-serif", lineHeight: 1.6,
  },
  actions: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    marginTop: 8,
  },
  hint: { fontSize: 11, color: "#ccc" },
  btnGroup: { display: "flex", gap: 6 },
  streamBtn: {
    display: "flex", alignItems: "center", gap: 5,
    padding: "7px 14px", border: "1px solid #e0e0e0",
    borderRadius: 7, background: "#fff", color: "#555",
    fontSize: 12, cursor: "pointer", fontFamily: "'DM Sans', sans-serif",
    transition: "all 0.15s",
  },
  streamActive: {
    background: "#fef2f2", borderColor: "#fca5a5", color: "#dc2626",
  },
  generateBtn: {
    display: "flex", alignItems: "center", gap: 5,
    padding: "7px 16px", background: "#f58321", border: "none",
    borderRadius: 7, color: "#fff", fontSize: 12, fontWeight: 500,
    cursor: "pointer", fontFamily: "'DM Sans', sans-serif",
    opacity: 1, transition: "opacity 0.15s",
  },
  spin: { animation: "spin 1s linear infinite" },
};
