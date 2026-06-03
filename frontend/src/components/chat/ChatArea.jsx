import React, { useRef, useEffect } from "react";
import { Bot, User, FileDown, Table2 } from "lucide-react";
import { useApp } from "../../context/AppContext";

export default function ChatArea() {
  const { messages, activeSessionId } = useApp();
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (!activeSessionId) {
    return (
      <div style={styles.empty}>
        <div style={styles.emptyIcon}>VDF</div>
        <div style={styles.emptyTitle}>Virtual Data Factory</div>
        <div style={styles.emptySubtitle}>
          Describe the data you want to generate, stream, or push to a connector.
        </div>
        <div style={styles.exampleGrid}>
          {EXAMPLES.map((ex) => (
            <div key={ex} style={styles.exampleCard}>{ex}</div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div style={styles.area}>
      {messages.map((msg) => (
        <MessageRow key={msg.id} msg={msg} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}

function MessageRow({ msg }) {
  const isUser = msg.role === "user";
  const content = msg.content;

  return (
    <div style={{ ...styles.row, justifyContent: isUser ? "flex-end" : "flex-start" }}>
      {!isUser && (
        <div style={styles.avatarAI}>
          <Bot size={14} />
        </div>
      )}

      <div style={{ maxWidth: "72%" }}>
        {/* Simple string message */}
        {typeof content === "string" && (
          <div style={{ ...styles.bubble, ...(isUser ? styles.bubbleUser : styles.bubbleAI) }}>
            {content}
          </div>
        )}

        {/* Batch result */}
        {content?.records && (
          <div style={styles.resultCard}>
            <div style={styles.resultHeader}>
              <Table2 size={14} style={{ color: "#f58321" }} />
              <span style={styles.resultTitle}>Data Generated Successfully</span>
            </div>
            <div style={styles.resultMeta}>
              {content.count} records · {content.prompt}
            </div>
            <div style={styles.recordPreview}>
              {content.records.slice(0, 3).map((r, i) => (
                <div key={i} style={styles.recordLine}>
                  {JSON.stringify(r).slice(0, 90)}{JSON.stringify(r).length > 90 ? "..." : ""}
                </div>
              ))}
              {content.records.length > 3 && (
                <div style={styles.recordMore}>+{content.records.length - 3} more records</div>
              )}
            </div>
            <div style={styles.resultActions}>
              <DownloadBtn records={content.records} format="json" />
              <DownloadBtn records={content.records} format="csv" />
            </div>
          </div>
        )}

        {/* Stream done summary */}
        {content?.type === "stream_done" && (
          <div style={styles.resultCard}>
            <div style={styles.resultHeader}>
              <Bot size={14} style={{ color: "#f58321" }} />
              <span style={styles.resultTitle}>Stream Completed</span>
            </div>
            <div style={styles.resultMeta}>
              {content.total} records streamed · {content.prompt}
            </div>
          </div>
        )}

        <div style={styles.ts}>
          {new Date(msg.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </div>
      </div>

      {isUser && (
        <div style={styles.avatarUser}>
          <User size={14} />
        </div>
      )}
    </div>
  );
}

function DownloadBtn({ records, format }) {
  const download = () => {
    let content, mime, ext;
    if (format === "json") {
      content = JSON.stringify(records, null, 2);
      mime = "application/json"; ext = "json";
    } else {
      const keys = Object.keys(records[0] ?? {});
      const rows = [keys.join(","), ...records.map((r) => keys.map((k) => JSON.stringify(r[k] ?? "")).join(","))];
      content = rows.join("\n");
      mime = "text/csv"; ext = "csv";
    }
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `vdf_data.${ext}`; a.click();
    URL.revokeObjectURL(url);
    console.log(`[ChatArea] Downloaded ${format}`);
  };

  return (
    <button style={styles.dlBtn} onClick={download}>
      <FileDown size={11} /> {format.toUpperCase()}
    </button>
  );
}

const EXAMPLES = [
  "Generate 100 IoT sensor readings with spikes",
  "200 customer profiles with anomalies",
  "50 HR records with attrition risk scores",
  "Stream machine logs every 2 seconds",
];

const styles = {
  area: { flex: 1, overflowY: "auto", padding: "24px 32px", display: "flex", flexDirection: "column", gap: 20 },
  empty: {
    flex: 1, display: "flex", flexDirection: "column",
    alignItems: "center", justifyContent: "center", gap: 12,
    padding: 40, textAlign: "center",
  },
  emptyIcon: {
    background: "#f58321", color: "#fff", fontWeight: 700,
    fontSize: 18, padding: "8px 14px", borderRadius: 10, letterSpacing: 1,
  },
  emptyTitle: { fontSize: 22, fontWeight: 600, color: "#1a1a1a" },
  emptySubtitle: { fontSize: 14, color: "#888", maxWidth: 400, lineHeight: 1.6 },
  exampleGrid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 8, maxWidth: 500 },
  exampleCard: {
    padding: "10px 14px", border: "1px solid #f0f0f0", borderRadius: 8,
    fontSize: 12, color: "#666", cursor: "pointer", textAlign: "left",
    background: "#fafafa", lineHeight: 1.4,
  },
  row: { display: "flex", gap: 10, alignItems: "flex-start" },
  avatarAI: {
    width: 30, height: 30, borderRadius: "50%", background: "#fff4ea",
    color: "#f58321", display: "flex", alignItems: "center", justifyContent: "center",
    flexShrink: 0, border: "1px solid #ffe0b8",
  },
  avatarUser: {
    width: 30, height: 30, borderRadius: "50%", background: "#f5f5f5",
    color: "#888", display: "flex", alignItems: "center", justifyContent: "center",
    flexShrink: 0,
  },
  bubble: { padding: "10px 14px", borderRadius: 10, fontSize: 13, lineHeight: 1.6 },
  bubbleUser: { background: "#fff4ea", color: "#1a1a1a", borderBottomRightRadius: 3 },
  bubbleAI: { background: "#f8f8f8", color: "#1a1a1a", borderBottomLeftRadius: 3, border: "1px solid #f0f0f0" },
  ts: { fontSize: 10, color: "#ccc", marginTop: 3, paddingLeft: 2 },
  resultCard: {
    background: "#fff", border: "1px solid #f0f0f0", borderRadius: 10,
    overflow: "hidden", fontSize: 13,
  },
  resultHeader: {
    display: "flex", alignItems: "center", gap: 7,
    padding: "10px 14px", borderBottom: "1px solid #f5f5f5",
    background: "#fafafa",
  },
  resultTitle: { fontWeight: 600, color: "#1a1a1a", fontSize: 13 },
  resultMeta: { padding: "6px 14px", fontSize: 11, color: "#888" },
  recordPreview: { padding: "0 14px 8px", display: "flex", flexDirection: "column", gap: 3 },
  recordLine: {
    fontSize: 11, fontFamily: "monospace", color: "#555",
    background: "#f8f8f8", borderRadius: 5, padding: "4px 8px",
  },
  recordMore: { fontSize: 11, color: "#aaa", padding: "2px 8px" },
  resultActions: { display: "flex", gap: 6, padding: "8px 14px", borderTop: "1px solid #f5f5f5" },
  dlBtn: {
    display: "flex", alignItems: "center", gap: 4,
    padding: "5px 10px", border: "1px solid #ebebeb", borderRadius: 6,
    background: "#fafafa", fontSize: 11, color: "#555", cursor: "pointer",
    fontFamily: "'DM Sans', sans-serif",
  },
};
