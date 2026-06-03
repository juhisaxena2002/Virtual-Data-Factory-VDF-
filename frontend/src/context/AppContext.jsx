import React, { createContext, useContext, useState, useCallback } from "react";
import * as api from "../services/api";

const AppContext = createContext(null);

export function AppProvider({ children }) {
  // ── LLM config ──────────────────────────────────────────────────────────
  const [llmConfig, setLlmConfig] = useState({
    backend: "gemini",   // "gemini" | "anthropic"
    apiKey: "",
    count: 10,
  });

  // ── Sessions (sidebar) ──────────────────────────────────────────────────
  const [sessions, setSessions]           = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [messages, setMessages]           = useState([]);   // current session msgs

  // ── Connectors ──────────────────────────────────────────────────────────
  const [connectors, setConnectors] = useState({
    snowflake:  { configured: false, config: {} },
    databricks: { configured: false, config: {} },
    hivemq:     { configured: false, config: {} },
    publicApi:  { configured: false, config: {} },
  });

  // ── Right panel ─────────────────────────────────────────────────────────
  const [rightPanel, setRightPanel] = useState(null); // null | "stream" | "data"
  const [streamState, setStreamState] = useState({
    active: false, records: [], total: 0, status: "",
  });

  // ── Load sessions from backend ───────────────────────────────────────────
  const loadSessions = useCallback(async () => {
    console.log("[CTX] Loading sessions");
    const data = await api.listSessions();
    setSessions(data.sessions ?? []);
  }, []);

  // ── Create new session ───────────────────────────────────────────────────
  const newSession = useCallback(async (name = "New chat") => {
    console.log("[CTX] Creating session:", name);
    const session = await api.createSession(name);
    setSessions((prev) => [session, ...prev]);
    setActiveSessionId(session.id);
    setMessages([]);
    return session;
  }, []);

  // ── Open existing session ────────────────────────────────────────────────
  const openSession = useCallback(async (id) => {
    console.log("[CTX] Opening session:", id);
    const session = await api.getSession(id);
    setActiveSessionId(id);
    setMessages(session.messages ?? []);
  }, []);

  // ── Delete session ───────────────────────────────────────────────────────
  const removeSession = useCallback(async (id) => {
    console.log("[CTX] Deleting session:", id);
    await api.deleteSession(id);
    setSessions((prev) => prev.filter((s) => s.id !== id));
    if (activeSessionId === id) {
      setActiveSessionId(null);
      setMessages([]);
    }
  }, [activeSessionId]);

  // ── Append message locally ───────────────────────────────────────────────
  const appendMessage = useCallback((role, content) => {
    const msg = { id: Date.now(), role, content, ts: new Date().toISOString() };
    setMessages((prev) => [...prev, msg]);
    return msg;
  }, []);

  // ── Update connector config ──────────────────────────────────────────────
  const updateConnector = useCallback((type, config, configured = false) => {
    console.log("[CTX] Connector update:", type, configured);
    setConnectors((prev) => ({
      ...prev,
      [type]: { configured, config },
    }));
  }, []);

  const value = {
    llmConfig, setLlmConfig,
    sessions, loadSessions, newSession, openSession, removeSession,
    activeSessionId,
    messages, appendMessage, setMessages,
    connectors, updateConnector,
    rightPanel, setRightPanel,
    streamState, setStreamState,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export const useApp = () => {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used inside AppProvider");
  return ctx;
};
