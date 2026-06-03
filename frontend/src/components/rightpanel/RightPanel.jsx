import React, { useState } from "react";
import { X, ChevronRight, Activity, Table2, Pause, Square } from "lucide-react";
import { useApp } from "../../context/AppContext";
import { useStream } from "../../hooks/useStream";

export default function RightPanel() {
  const { rightPanel, setRightPanel, streamState, messages } = useApp();
  const { stopStream } = useStream();
  const [tab, setTab] = useState("records"); // "records" | "stream"

  if (!rightPanel) return null;

  // Get latest batch records from last assistant message
  const lastBatch = [...messages].reverse().find((m) => m.content?.records);
  const batchRecords = lastBatch?.content?.records ?? [];

  const { active, records: streamRecords, total, status } = streamState;

  return (
    <aside style={styles.panel}>
      {/* Header */}
      <div style={styles.header}>
        <div style={styles.headerLeft}>
          {rightPanel === "stream"
            ? <><Activity size={14} style={{ color: "#f58321" }} /> Live Data Stream</>
            : <><Table2 size={14} style={{ color: "#f58321" }} /> Data Preview</>
          }
        </div>
        <button style={styles.closeBtn} onClick={() => setRightPanel(null)}>
          <X size={14} />
        </button>
      </div>

      {/* Tabs */}
      <div style={styles.tabs}>
        <button style={{ ...styles.tab, ...(tab === "records" ? styles.tabActive : {}) }} onClick={() => setTab("records")}>Records</button>
        <button style={{ ...styles.tab, ...(tab === "stream" ? styles.tabActive : {}) }} onClick={() => setTab("stream")}>
          Stream {active && <span style={styles.liveDot} />}
        </button>
      </div>

      {/* Records tab */}
      {tab === "records" && (
        <div style={styles.body}>
          {batchRecords.length === 0
            ? <div style={styles.empty}>Generate data to preview it here</div>
            : batchRecords.map((r, i) => <RecordCard key={i} record={r} index={i + 1} />)
          }
        </div>
      )}

      {/* Stream tab */}
      {tab === "stream" && (
        <div style={styles.body}>
          {/* Stream stats */}
          <div style={styles.statsRow}>
            <Stat label="Status" value={active ? "Streaming" : (status || "Idle")} accent={active} />
            <Stat label="Records" value={total} />
          </div>

          {/* Stop button */}
          {active && (
            <button style={styles.stopBtn} onClick={() => { stopStream(); }}>
              <Square size={12} /> Stop Stream
            </button>
          )}

          {/* Status message */}
          {status && <div style={styles.statusMsg}>{status}</div>}

          {/* Live records */}
          {streamRecords.length === 0
            ? <div style={styles.empty}>Start streaming to see live records here</div>
            : streamRecords.map((r, i) => <RecordCard key={i} record={r} index={total - i} live={i === 0} />)
          }
        </div>
      )}
    </aside>
  );
}

function RecordCard({ record, index, live }) {
  const entries = Object.entries(record).slice(0, 6);
  return (
    <div style={{ ...styles.card, ...(live ? styles.cardLive : {}) }}>
      <div style={styles.cardNum}>#{index} {live && <span style={styles.liveTag}>live</span>}</div>
      {entries.map(([k, v]) => (
        <div key={k} style={styles.fieldRow}>
          <span style={styles.fieldKey}>{k}</span>
          <span style={styles.fieldVal}>{String(v).slice(0, 30)}</span>
        </div>
      ))}
      {Object.keys(record).length > 6 && (
        <div style={styles.moreFields}>+{Object.keys(record).length - 6} more fields</div>
      )}
    </div>
  );
}

function Stat({ label, value, accent }) {
  return (
    <div style={styles.stat}>
      <div style={styles.statLabel}>{label}</div>
      <div style={{ ...styles.statValue, color: accent ? "#22c55e" : "#1a1a1a" }}>{value}</div>
    </div>
  );
}

const styles = {
  panel: {
    width: 300, minWidth: 300, height: "100vh",
    background: "#fff", borderLeft: "1px solid #f0f0f0",
    display: "flex", flexDirection: "column",
    fontFamily: "'DM Sans', sans-serif",
    animation: "slideIn 0.2s ease",
  },
  header: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    padding: "13px 14px", borderBottom: "1px solid #f0f0f0",
    fontSize: 13, fontWeight: 600, color: "#1a1a1a",
    gap: 6,
  },
  headerLeft: { display: "flex", alignItems: "center", gap: 6 },
  closeBtn: {
    background: "none", border: "none", cursor: "pointer",
    color: "#aaa", display: "flex", alignItems: "center",
  },
  tabs: {
    display: "flex", borderBottom: "1px solid #f0f0f0", padding: "0 8px",
  },
  tab: {
    padding: "8px 12px", border: "none", background: "none",
    fontSize: 12, color: "#888", cursor: "pointer",
    fontFamily: "'DM Sans', sans-serif",
    display: "flex", alignItems: "center", gap: 5,
    borderBottom: "2px solid transparent",
  },
  tabActive: { color: "#f58321", borderBottomColor: "#f58321", fontWeight: 500 },
  liveDot: {
    width: 6, height: 6, borderRadius: "50%", background: "#22c55e",
    display: "inline-block", animation: "pulse 1s infinite",
  },
  body: { flex: 1, overflowY: "auto", padding: "10px" },
  empty: { fontSize: 12, color: "#ccc", textAlign: "center", padding: "30px 10px" },
  statsRow: { display: "flex", gap: 8, marginBottom: 8 },
  stat: {
    flex: 1, background: "#f8f8f8", borderRadius: 8,
    padding: "8px 10px", border: "1px solid #f0f0f0",
  },
  statLabel: { fontSize: 10, color: "#aaa", fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.4 },
  statValue: { fontSize: 16, fontWeight: 600, marginTop: 2 },
  stopBtn: {
    width: "100%", padding: "7px", border: "1px solid #fca5a5",
    borderRadius: 7, background: "#fef2f2", color: "#dc2626",
    fontSize: 12, cursor: "pointer", display: "flex",
    alignItems: "center", justifyContent: "center", gap: 5,
    marginBottom: 8, fontFamily: "'DM Sans', sans-serif",
  },
  statusMsg: {
    fontSize: 11, color: "#888", padding: "4px 8px",
    background: "#f8f8f8", borderRadius: 6, marginBottom: 8,
  },
  card: {
    background: "#fafafa", border: "1px solid #f0f0f0",
    borderRadius: 8, padding: "8px 10px", marginBottom: 6,
  },
  cardLive: { borderColor: "#86efac", background: "#f0fdf4" },
  cardNum: {
    fontSize: 10, color: "#aaa", marginBottom: 4,
    display: "flex", alignItems: "center", gap: 5,
  },
  liveTag: {
    background: "#22c55e", color: "#fff", fontSize: 9,
    padding: "1px 5px", borderRadius: 10, fontWeight: 600,
  },
  fieldRow: {
    display: "flex", justifyContent: "space-between",
    fontSize: 11, padding: "2px 0", borderBottom: "1px solid #f0f0f0",
  },
  fieldKey: { color: "#999" },
  fieldVal: { color: "#333", fontFamily: "monospace", fontSize: 10 },
  moreFields: { fontSize: 10, color: "#bbb", marginTop: 3 },
};
