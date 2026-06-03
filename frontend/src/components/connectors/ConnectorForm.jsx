import React, { useState } from "react";
import { X, Loader2, CheckCircle, AlertCircle } from "lucide-react";
import { useApp } from "../../context/AppContext";
import { testConnector } from "../../services/api";

const FIELDS = {
  snowflake: [
    { key: "account",   label: "Account",   placeholder: "e.g. PIB20461",          type: "text" },
    { key: "user",      label: "User",       placeholder: "john@company.com",        type: "text" },
    { key: "password",  label: "Password",   placeholder: "Leave blank for SSO",     type: "password" },
    { key: "warehouse", label: "Warehouse",  placeholder: "COMPUTE_WH",              type: "text" },
    { key: "database",  label: "Database",   placeholder: "SYNTHGEN_DB",             type: "text" },
    { key: "schema",    label: "Schema",     placeholder: "PUBLIC",                  type: "text" },
    { key: "table",     label: "Table",      placeholder: "SYNTHGEN_STREAM",         type: "text" },
  ],
  databricks: [
    { key: "host",      label: "Host",       placeholder: "dbc-xxx.cloud.databricks.com", type: "text" },
    { key: "token",     label: "Token",      placeholder: "dapiXXXXXXXX",            type: "password" },
    { key: "http_path", label: "HTTP Path",  placeholder: "/sql/1.0/warehouses/abc", type: "text" },
    { key: "catalog",   label: "Catalog",    placeholder: "hive_metastore",          type: "text" },
    { key: "schema",    label: "Schema",     placeholder: "synthgen",                type: "text" },
    { key: "table",     label: "Table",      placeholder: "synthgen_stream",         type: "text" },
  ],
  hivemq: [
    { key: "host",     label: "Host",     placeholder: "abc123.s1.eu.hivemq.cloud", type: "text" },
    { key: "port",     label: "Port",     placeholder: "8883",                      type: "number" },
    { key: "username", label: "Username", placeholder: "your-username",             type: "text" },
    { key: "password", label: "Password", placeholder: "your-password",             type: "password" },
    { key: "topic",    label: "Topic",    placeholder: "synthgen/stream",           type: "text" },
  ],
  publicApi: [
    { key: "url",        label: "Endpoint URL", placeholder: "https://webhook.site/your-uuid", type: "text" },
    { key: "auth_type",  label: "Auth Type",    placeholder: "",                    type: "select",
      options: ["none", "bearer", "api_key"] },
    { key: "auth_value", label: "Auth Value",   placeholder: "Token or key",        type: "password" },
    { key: "data_format",label: "Format",       placeholder: "",                    type: "select",
      options: ["json", "ndjson"] },
  ],
};

const TITLES = {
  snowflake:  "Snowflake",
  databricks: "Databricks",
  hivemq:     "HiveMQ",
  publicApi:  "Public API",
};

const TYPE_MAP = {
  snowflake: "snowflake",
  databricks: "databricks",
  hivemq: "hivemq",
  publicApi: "public-api",
};

export default function ConnectorForm({ type, onClose }) {
  const { connectors, updateConnector } = useApp();
  const existing = connectors[type]?.config ?? {};

  const [form, setForm]     = useState(existing);
  const [testing, setTesting] = useState(false);
  const [result, setResult]   = useState(null); // null | "ok" | "error"
  const [errMsg, setErrMsg]   = useState("");

  const fields = FIELDS[type] ?? [];

  const handleChange = (key, value) => {
    console.log(`[ConnectorForm] ${type}.${key} changed`);
    setForm((f) => ({ ...f, [key]: value }));
    setResult(null);
  };

  const handleTest = async () => {
    console.log("[ConnectorForm] Testing connector:", type, form);
    setTesting(true);
    setResult(null);
    try {
      const connector = { type: TYPE_MAP[type], ...form };
      const res = await testConnector(connector);
      if (res.ok) {
        console.log("[ConnectorForm] Test passed");
        setResult("ok");
        updateConnector(type, form, true);
      } else {
        console.warn("[ConnectorForm] Test failed:", res.error);
        setResult("error");
        setErrMsg(res.error ?? "Connection failed");
      }
    } catch (e) {
      setResult("error");
      setErrMsg(e.message);
    } finally {
      setTesting(false);
    }
  };

  const handleSave = () => {
    console.log("[ConnectorForm] Saving connector:", type);
    updateConnector(type, form, result === "ok");
    onClose();
  };

  return (
    <div style={styles.overlay} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div style={styles.modal}>
        {/* Header */}
        <div style={styles.head}>
          <span style={styles.title}>{TITLES[type]} Connector</span>
          <button style={styles.closeBtn} onClick={onClose}><X size={15} /></button>
        </div>

        {/* Fields */}
        <div style={styles.body}>
          {fields.map(({ key, label, placeholder, type: ftype, options }) => (
            <div key={key} style={styles.field}>
              <label style={styles.label}>{label}</label>
              {ftype === "select" ? (
                <select
                  style={styles.input}
                  value={form[key] ?? options[0]}
                  onChange={(e) => handleChange(key, e.target.value)}
                >
                  {options.map((o) => <option key={o} value={o}>{o}</option>)}
                </select>
              ) : (
                <input
                  style={styles.input}
                  type={ftype}
                  placeholder={placeholder}
                  value={form[key] ?? ""}
                  onChange={(e) => handleChange(key, e.target.value)}
                />
              )}
            </div>
          ))}

          {/* Test result */}
          {result === "ok" && (
            <div style={styles.resultOk}>
              <CheckCircle size={13} /> Connection successful
            </div>
          )}
          {result === "error" && (
            <div style={styles.resultErr}>
              <AlertCircle size={13} /> {errMsg}
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={styles.foot}>
          <button style={styles.testBtn} onClick={handleTest} disabled={testing}>
            {testing ? <Loader2 size={13} style={styles.spin} /> : null}
            {testing ? "Testing..." : "Test Connection"}
          </button>
          <button style={styles.saveBtn} onClick={handleSave}>
            Save
          </button>
        </div>
      </div>
    </div>
  );
}

const styles = {
  overlay: {
    position: "fixed", inset: 0, background: "rgba(0,0,0,0.25)",
    display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100,
  },
  modal: {
    background: "#fff", borderRadius: 12, width: 380,
    boxShadow: "0 8px 40px rgba(0,0,0,0.12)", overflow: "hidden",
    fontFamily: "'DM Sans', sans-serif",
  },
  head: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    padding: "14px 16px", borderBottom: "1px solid #f0f0f0",
  },
  title: { fontSize: 14, fontWeight: 600, color: "#1a1a1a" },
  closeBtn: {
    background: "none", border: "none", cursor: "pointer",
    color: "#aaa", display: "flex", alignItems: "center",
  },
  body: { padding: "14px 16px", display: "flex", flexDirection: "column", gap: 10, maxHeight: 420, overflowY: "auto" },
  field: { display: "flex", flexDirection: "column", gap: 4 },
  label: { fontSize: 11, fontWeight: 600, color: "#999", textTransform: "uppercase", letterSpacing: 0.4 },
  input: {
    padding: "8px 10px", borderRadius: 7, border: "1px solid #ebebeb",
    fontSize: 12, color: "#333", background: "#fafafa",
    fontFamily: "'DM Sans', sans-serif", outline: "none",
  },
  resultOk: {
    display: "flex", alignItems: "center", gap: 6,
    color: "#16a34a", background: "#f0fdf4", borderRadius: 7,
    padding: "8px 10px", fontSize: 12,
  },
  resultErr: {
    display: "flex", alignItems: "center", gap: 6,
    color: "#dc2626", background: "#fef2f2", borderRadius: 7,
    padding: "8px 10px", fontSize: 12,
  },
  foot: {
    display: "flex", gap: 8, padding: "12px 16px",
    borderTop: "1px solid #f0f0f0", justifyContent: "flex-end",
  },
  testBtn: {
    padding: "7px 14px", border: "1px solid #e5e5e5", borderRadius: 7,
    background: "#fafafa", color: "#555", fontSize: 12, cursor: "pointer",
    display: "flex", alignItems: "center", gap: 5,
    fontFamily: "'DM Sans', sans-serif",
  },
  saveBtn: {
    padding: "7px 18px", background: "#f58321", border: "none",
    borderRadius: 7, color: "#fff", fontSize: 12, fontWeight: 500,
    cursor: "pointer", fontFamily: "'DM Sans', sans-serif",
  },
  spin: { animation: "spin 1s linear infinite" },
};
