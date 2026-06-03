import React, { useState, useEffect } from "react";
import {
  Plus, Search, MessageSquare, ChevronLeft, ChevronRight,
  Settings, Trash2, Snowflake, Database, Globe, Radio,
  ChevronDown, ChevronUp, Check, Loader2
} from "lucide-react";
import { useApp } from "../../context/AppContext";
import ConnectorForm from "../connectors/ConnectorForm";

export default function Sidebar() {
  const {
    sessions, loadSessions, newSession, openSession, removeSession,
    activeSessionId, llmConfig, setLlmConfig, connectors,
  } = useApp();

  const [collapsed, setCollapsed]       = useState(false);
  const [search, setSearch]             = useState("");
  const [llmOpen, setLlmOpen]           = useState(false);
  const [connectorsOpen, setConnectorsOpen] = useState(false);
  const [activeConnectorForm, setActiveConnectorForm] = useState(null); // "snowflake"|"databricks"|"hivemq"|"publicApi"

  useEffect(() => {
    console.log("[Sidebar] Loading sessions on mount");
    loadSessions();
  }, [loadSessions]);

  const filtered = sessions.filter((s) =>
    s.name.toLowerCase().includes(search.toLowerCase())
  );

  const connectorMeta = [
    { key: "snowflake",  label: "Snowflake",   Icon: Snowflake, color: "#29B5E8" },
    { key: "databricks", label: "Databricks",  Icon: Database,  color: "#FF3621" },
    { key: "hivemq",     label: "HiveMQ",      Icon: Radio,     color: "#f58321" },
    { key: "publicApi",  label: "Public API",  Icon: Globe,     color: "#22c55e" },
  ];

  if (collapsed) {
    return (
      <aside style={styles.collapsedBar}>
        <button style={styles.collapseBtn} onClick={() => setCollapsed(false)}>
          <ChevronRight size={16} />
        </button>
        <button style={styles.iconBtn} onClick={() => { setCollapsed(false); newSession(); }}>
          <Plus size={16} />
        </button>
      </aside>
    );
  }

  return (
    <>
      <aside style={styles.sidebar}>
        {/* Header */}
        <div style={styles.header}>
          <div style={styles.logo}>
            <div style={styles.logoMark}>VDF</div>
            <span style={styles.logoText}>SDK Studio</span>
          </div>
          <button style={styles.collapseBtn} onClick={() => setCollapsed(true)}>
            <ChevronLeft size={15} />
          </button>
        </div>

        {/* New chat */}
        <button style={styles.newChatBtn} onClick={() => newSession()}>
          <Plus size={14} />
          New Chat
        </button>

        {/* Search */}
        <div style={styles.searchWrap}>
          <Search size={13} style={{ color: "#aaa" }} />
          <input
            style={styles.searchInput}
            placeholder="Search chats..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        {/* Sessions */}
        <div style={styles.sectionLabel}>Chat History</div>
        <div style={styles.sessionList}>
          {filtered.length === 0 && (
            <div style={styles.emptyHint}>No chats yet — start one above</div>
          )}
          {filtered.map((s) => (
            <div
              key={s.id}
              style={{ ...styles.sessionItem, ...(s.id === activeSessionId ? styles.sessionActive : {}) }}
              onClick={() => openSession(s.id)}
            >
              <MessageSquare size={13} style={{ flexShrink: 0, opacity: 0.6 }} />
              <span style={styles.sessionName}>{s.name}</span>
              <button
                style={styles.deleteBtn}
                onClick={(e) => { e.stopPropagation(); removeSession(s.id); }}
              >
                <Trash2 size={11} />
              </button>
            </div>
          ))}
        </div>

        {/* Bottom config area */}
        <div style={styles.bottomArea}>

          {/* Connectors accordion */}
          <div style={styles.accordionWrap}>
            <button style={styles.accordionHead} onClick={() => setConnectorsOpen((v) => !v)}>
              <span style={styles.accordionLabel}>Connectors</span>
              {connectorsOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
            </button>
            {connectorsOpen && (
              <div style={styles.connectorGrid}>
                {connectorMeta.map(({ key, label, Icon, color }) => {
                  const isConfigured = connectors[key]?.configured;
                  return (
                    <button
                      key={key}
                      style={{ ...styles.connectorChip, borderColor: isConfigured ? color : "#e5e5e5" }}
                      onClick={() => setActiveConnectorForm(activeConnectorForm === key ? null : key)}
                    >
                      <Icon size={12} style={{ color }} />
                      <span style={{ fontSize: 11 }}>{label}</span>
                      {isConfigured && <Check size={10} style={{ color, marginLeft: "auto" }} />}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* LLM config accordion */}
          <div style={styles.accordionWrap}>
            <button style={styles.accordionHead} onClick={() => setLlmOpen((v) => !v)}>
              <Settings size={13} />
              <span style={styles.accordionLabel}>LLM Configure</span>
              {llmOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
            </button>
            {llmOpen && (
              <div style={styles.llmBody}>
                <label style={styles.fieldLabel}>Backend</label>
                <select
                  style={styles.select}
                  value={llmConfig.backend}
                  onChange={(e) => {
                    console.log("[Sidebar] Backend changed:", e.target.value);
                    setLlmConfig((c) => ({ ...c, backend: e.target.value }));
                  }}
                >
                  <option value="gemini">Google Gemini</option>
                  <option value="anthropic">Anthropic Claude</option>
                </select>

                <label style={styles.fieldLabel}>API Key</label>
                <input
                  type="password"
                  style={styles.input}
                  placeholder="Paste your API key..."
                  value={llmConfig.apiKey}
                  onChange={(e) => setLlmConfig((c) => ({ ...c, apiKey: e.target.value }))}
                />

                <label style={styles.fieldLabel}>Records per batch</label>
                <input
                  type="number"
                  style={styles.input}
                  min={1} max={200}
                  value={llmConfig.count}
                  onChange={(e) => setLlmConfig((c) => ({ ...c, count: Number(e.target.value) }))}
                />
              </div>
            )}
          </div>

        </div>
      </aside>

      {/* Connector form modal */}
      {activeConnectorForm && (
        <ConnectorForm
          type={activeConnectorForm}
          onClose={() => setActiveConnectorForm(null)}
        />
      )}
    </>
  );
}

const styles = {
  sidebar: {
    width: 240, minWidth: 240, height: "100vh",
    background: "#fff", borderRight: "1px solid #f0f0f0",
    display: "flex", flexDirection: "column", overflow: "hidden",
    fontFamily: "'DM Sans', sans-serif",
  },
  collapsedBar: {
    width: 44, minWidth: 44, height: "100vh",
    background: "#fff", borderRight: "1px solid #f0f0f0",
    display: "flex", flexDirection: "column", alignItems: "center",
    paddingTop: 12, gap: 8,
  },
  header: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    padding: "14px 12px 10px", borderBottom: "1px solid #f5f5f5",
  },
  logo: { display: "flex", alignItems: "center", gap: 8 },
  logoMark: {
    background: "#f58321", color: "#fff", fontWeight: 700,
    fontSize: 11, padding: "3px 6px", borderRadius: 6, letterSpacing: 0.5,
  },
  logoText: { fontSize: 13, fontWeight: 600, color: "#1a1a1a" },
  collapseBtn: {
    background: "none", border: "none", cursor: "pointer",
    color: "#aaa", padding: 4, borderRadius: 6,
    display: "flex", alignItems: "center",
  },
  iconBtn: {
    background: "none", border: "none", cursor: "pointer",
    color: "#888", padding: 6, borderRadius: 6,
  },
  newChatBtn: {
    margin: "10px 10px 6px",
    padding: "8px 12px",
    background: "#f58321", color: "#fff",
    border: "none", borderRadius: 8, cursor: "pointer",
    display: "flex", alignItems: "center", gap: 6,
    fontSize: 13, fontWeight: 500, fontFamily: "'DM Sans', sans-serif",
  },
  searchWrap: {
    margin: "0 10px 6px",
    display: "flex", alignItems: "center", gap: 6,
    background: "#f8f8f8", borderRadius: 7,
    padding: "6px 10px", border: "1px solid #efefef",
  },
  searchInput: {
    border: "none", background: "transparent", outline: "none",
    fontSize: 12, color: "#333", flex: 1, fontFamily: "'DM Sans', sans-serif",
  },
  sectionLabel: {
    fontSize: 10, fontWeight: 600, color: "#bbb",
    textTransform: "uppercase", letterSpacing: 0.8,
    padding: "6px 14px 4px",
  },
  sessionList: { flex: 1, overflowY: "auto", padding: "0 6px" },
  sessionItem: {
    display: "flex", alignItems: "center", gap: 7,
    padding: "7px 8px", borderRadius: 7, cursor: "pointer",
    fontSize: 12, color: "#555", marginBottom: 1,
    transition: "background 0.15s",
  },
  sessionActive: { background: "#fff4ea", color: "#f58321", fontWeight: 500 },
  sessionName: { flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  deleteBtn: {
    background: "none", border: "none", cursor: "pointer",
    color: "#ccc", padding: 2, borderRadius: 4, opacity: 0,
    display: "flex", alignItems: "center",
    ":hover": { opacity: 1 },
  },
  emptyHint: { fontSize: 11, color: "#ccc", padding: "12px 8px", textAlign: "center" },
  bottomArea: { borderTop: "1px solid #f0f0f0", padding: "8px 0" },
  accordionWrap: { marginBottom: 2 },
  accordionHead: {
    width: "100%", background: "none", border: "none", cursor: "pointer",
    display: "flex", alignItems: "center", gap: 6,
    padding: "8px 14px", fontSize: 12, color: "#555", fontFamily: "'DM Sans', sans-serif",
  },
  accordionLabel: { flex: 1, textAlign: "left", fontWeight: 500 },
  connectorGrid: { padding: "4px 10px 8px", display: "flex", flexDirection: "column", gap: 4 },
  connectorChip: {
    display: "flex", alignItems: "center", gap: 6,
    padding: "6px 10px", borderRadius: 7, border: "1px solid #e5e5e5",
    background: "#fafafa", cursor: "pointer", fontFamily: "'DM Sans', sans-serif",
    transition: "all 0.15s",
  },
  llmBody: { padding: "4px 12px 10px", display: "flex", flexDirection: "column", gap: 6 },
  fieldLabel: { fontSize: 10, color: "#aaa", fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 },
  select: {
    padding: "7px 10px", borderRadius: 7, border: "1px solid #ebebeb",
    fontSize: 12, color: "#333", background: "#fafafa",
    fontFamily: "'DM Sans', sans-serif", outline: "none",
  },
  input: {
    padding: "7px 10px", borderRadius: 7, border: "1px solid #ebebeb",
    fontSize: 12, color: "#333", background: "#fafafa",
    fontFamily: "'DM Sans', sans-serif", outline: "none",
  },
};
