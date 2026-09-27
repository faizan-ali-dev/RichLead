"use client";

import { useCallback, useEffect, useState } from "react";
import { Cpu, Check, AlertCircle, Loader2, Trash2, Star } from "lucide-react";
import { authFetch } from "../lib/api";
import styles from "./page.module.css";

const STEP_HINT = {
  idle: "Pick a provider, paste its API key, then load the models it can run.",
  loaded: "Choose a model. It will be tested with a real request before anything is saved.",
};

export default function LlmProviderCard() {
  const [catalog, setCatalog] = useState([]);
  const [configured, setConfigured] = useState({});
  const [active, setActive] = useState(null);

  const [provider, setProvider] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [models, setModels] = useState([]);
  const [model, setModel] = useState("");

  const [loadingModels, setLoadingModels] = useState(false);
  const [testing, setTesting] = useState(false);
  const [notice, setNotice] = useState(null); // {type: 'error'|'success', text}

  const refresh = useCallback(async () => {
    try {
      const [catRes, activeRes] = await Promise.all([
        authFetch("/api/ai/llm/catalog/"),
        authFetch("/api/ai/llm/active/"),
      ]);
      if (catRes.ok) {
        const data = await catRes.json();
        setCatalog(data.providers || []);
        setConfigured(data.configured || {});
        setProvider((current) => current || data.providers?.[0]?.provider || "");
      }
      if (activeRes.ok) setActive((await activeRes.json()).active);
    } catch {
      setNotice({ type: "error", text: "Could not load AI provider settings." });
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const meta = catalog.find((c) => c.provider === provider);
  const saved = configured[provider];

  // Switching provider invalidates the model list from the previous one.
  const selectProvider = (next) => {
    setProvider(next);
    setModels([]);
    setModel("");
    setApiKey("");
    setNotice(null);
  };

  const loadModels = async () => {
    setLoadingModels(true);
    setNotice(null);
    try {
      const res = await authFetch("/api/ai/llm/models/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider, api_key: apiKey }),
      });
      const data = await res.json();
      if (!res.ok) {
        setNotice({ type: "error", text: data.error || "Could not reach the provider." });
        setModels([]);
      } else {
        setModels(data.models || []);
        const recommended = (data.models || []).find((m) => m.recommended);
        setModel(saved?.model || recommended?.id || data.models?.[0]?.id || "");
      }
    } catch {
      setNotice({ type: "error", text: "Network error contacting the provider." });
    }
    setLoadingModels(false);
  };

  const testAndSave = async () => {
    setTesting(true);
    setNotice(null);
    try {
      const res = await authFetch("/api/ai/llm/connect/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider, api_key: apiKey, model, make_primary: true }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        setNotice({ type: "error", text: data.error || "Could not verify that model." });
      } else {
        setNotice({ type: "success", text: `${model} verified and saved. It is now your active AI model.` });
        setApiKey("");
        await refresh();
      }
    } catch {
      setNotice({ type: "error", text: "Network error while verifying the model." });
    }
    setTesting(false);
  };

  const makePrimary = async (prov) => {
    await authFetch("/api/ai/llm/primary/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider: prov }),
    });
    refresh();
  };

  const disconnect = async (prov) => {
    if (!window.confirm(`Remove the stored ${prov} key?`)) return;
    await authFetch(`/api/ai/llm/${prov}/`, { method: "DELETE" });
    setModels([]);
    setModel("");
    refresh();
  };

  const canLoadModels = provider && (apiKey.trim() || saved) && !loadingModels;
  const canSave = provider && model && !testing;
  const connected = Object.values(configured);

  return (
    <div className={styles.section}>
      <h2 className={styles.sectionTitle}>
        <Cpu size={20} className="text-accent-primary" />
        AI Provider
      </h2>

      {active ? (
        <div className={styles.activeBanner}>
          <Check size={16} />
          <span>
            Every AI feature is using <strong>{active.provider_label}</strong> &middot;{" "}
            <code>{active.model}</code>
          </span>
        </div>
      ) : (
        <div className={styles.warnBanner}>
          <AlertCircle size={16} />
          <span>No AI provider connected. Lead research and draft generation are disabled.</span>
        </div>
      )}

      <p className={styles.hint}>{models.length ? STEP_HINT.loaded : STEP_HINT.idle}</p>

      <div className={styles.formGroup}>
        <label>Provider</label>
        <select
          className={styles.input}
          value={provider}
          onChange={(e) => selectProvider(e.target.value)}
        >
          {catalog.map((c) => (
            <option key={c.provider} value={c.provider}>
              {c.label}
              {configured[c.provider] ? "  (connected)" : ""}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.formGroup}>
        <label>
          API Key
          {saved && <span className={styles.savedTag}>saved — leave blank to keep</span>}
        </label>
        <input
          type="password"
          className={styles.input}
          placeholder={saved ? "••••••••••••  (using saved key)" : `${meta?.key_prefix || ""}...`}
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          autoComplete="off"
        />
        {meta?.console_url && (
          <a className={styles.helpLink} href={meta.console_url} target="_blank" rel="noreferrer">
            Get a key from {meta.label}
          </a>
        )}
      </div>

      <button className={styles.secondaryBtn} onClick={loadModels} disabled={!canLoadModels}>
        {loadingModels ? <Loader2 size={16} className={styles.spin} /> : null}
        {loadingModels ? "Loading models..." : "Load available models"}
      </button>

      {models.length > 0 && (
        <>
          <div className={styles.formGroup} style={{ marginTop: "1.5rem" }}>
            <label>Model</label>
            <select className={styles.input} value={model} onChange={(e) => setModel(e.target.value)}>
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                  {m.recommended ? "  ★ recommended" : ""}
                </option>
              ))}
            </select>
          </div>

          {models.find((m) => m.id === model)?.note && (
            <p className={styles.modelNote}>{models.find((m) => m.id === model).note}</p>
          )}

          <button className={styles.saveBtn} onClick={testAndSave} disabled={!canSave}>
            {testing ? <Loader2 size={16} className={styles.spin} /> : <Check size={16} />}
            {testing ? "Sending test request..." : "Test & Save"}
          </button>
        </>
      )}

      {notice && (
        <div className={notice.type === "error" ? styles.errorBox : styles.successBox}>
          {notice.type === "error" ? <AlertCircle size={16} /> : <Check size={16} />}
          <span>{notice.text}</span>
        </div>
      )}

      {connected.length > 0 && (
        <div className={styles.connectedList}>
          <h3 className={styles.subTitle}>Connected providers</h3>
          {connected.map((c) => (
            <div key={c.provider} className={styles.connectedRow}>
              <div>
                <strong>{c.provider_label}</strong>
                <code className={styles.modelChip}>{c.model}</code>
                {c.is_primary && <span className={styles.primaryTag}>active</span>}
              </div>
              <div className={styles.rowActions}>
                {!c.is_primary && (
                  <button
                    className={styles.iconBtn}
                    onClick={() => makePrimary(c.provider)}
                    title="Make this the active AI model"
                  >
                    <Star size={15} />
                  </button>
                )}
                <button
                  className={styles.iconBtnDanger}
                  onClick={() => disconnect(c.provider)}
                  title="Remove this key"
                >
                  <Trash2 size={15} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
