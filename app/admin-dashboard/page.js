"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, ArrowDown, ArrowUp, BarChart3, Check, ChevronLeft, ChevronRight,
  Eye, EyeOff, LayoutDashboard, LoaderCircle, RefreshCw, Search, ShieldCheck,
  SlidersHorizontal, Users, X,
} from "lucide-react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { authFetch } from "@/app/lib/api";
import { useFeedback } from "@/components/FeedbackProvider";
import styles from "./page.module.css";

const PREFS_KEY = "richlead_admin_dashboard_v1";
const WIDGETS = [
  { id: "traffic", label: "Traffic and signups" },
  { id: "clicks", label: "CTA clicks" },
  { id: "pages", label: "Popular pages" },
  { id: "signups", label: "Recent signups" },
];
const USER_COLUMNS = [
  { id: "name", label: "Name" },
  { id: "email", label: "Email" },
  { id: "status", label: "Account" },
  { id: "verified", label: "Email status" },
  { id: "joined", label: "Joined" },
  { id: "lastLogin", label: "Last login" },
];
const DEFAULT_PREFS = {
  widgets: WIDGETS.map((widget) => widget.id),
  columns: USER_COLUMNS.map((column) => column.id),
};

function formatDate(value, includeTime = false) {
  if (!value) return "Never";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat(undefined, includeTime
    ? { dateStyle: "medium", timeStyle: "short" }
    : { dateStyle: "medium" }).format(date);
}

function MetricCard({ label, value, detail, icon: Icon }) {
  return (
    <article className={styles.metricCard}>
      <div className={styles.metricIcon}><Icon size={18} aria-hidden="true" /></div>
      <p>{label}</p>
      <strong>{Number(value || 0).toLocaleString()}</strong>
      <span>{detail}</span>
    </article>
  );
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className={styles.tooltip}>
      <strong>{label}</strong>
      {payload.map((entry) => (
        <span key={entry.dataKey} style={{ color: entry.color }}>
          {entry.name}: {Number(entry.value || 0).toLocaleString()}
        </span>
      ))}
    </div>
  );
}

export default function AdminDashboardPage() {
  const { notify, confirm } = useFeedback();
  const [access, setAccess] = useState("checking");
  const [currentAdminId, setCurrentAdminId] = useState(null);
  const [tab, setTab] = useState("overview");
  const [period, setPeriod] = useState(30);
  const [overview, setOverview] = useState(null);
  const [overviewLoading, setOverviewLoading] = useState(true);
  const [overviewError, setOverviewError] = useState("");
  const [users, setUsers] = useState({ results: [], count: 0, page: 1, page_count: 1 });
  const [usersLoading, setUsersLoading] = useState(false);
  const [usersError, setUsersError] = useState("");
  const [queryInput, setQueryInput] = useState("");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [userPage, setUserPage] = useState(1);
  const [editorUser, setEditorUser] = useState(null);
  const [savingUser, setSavingUser] = useState(false);
  const [customizeOpen, setCustomizeOpen] = useState(false);
  const [preferences, setPreferences] = useState(DEFAULT_PREFS);

  useEffect(() => {
    let timer;
    try {
      const saved = JSON.parse(window.localStorage.getItem(PREFS_KEY) || "null");
      if (saved) {
        const nextPreferences = {
          widgets: Array.isArray(saved.widgets)
            ? [...new Set(saved.widgets.filter((id) => WIDGETS.some((widget) => widget.id === id)))]
            : DEFAULT_PREFS.widgets,
          columns: Array.isArray(saved.columns)
            ? [...new Set(saved.columns.filter((id) => USER_COLUMNS.some((column) => column.id === id)))]
            : DEFAULT_PREFS.columns,
        };
        timer = window.setTimeout(() => setPreferences(nextPreferences), 0);
      }
    } catch {
      window.localStorage.removeItem(PREFS_KEY);
    }
    authFetch("/api/admin-dashboard/access/")
      .then(async (response) => {
        if (!response.ok) return setAccess("denied");
        const data = await response.json();
        setCurrentAdminId(data.admin_id);
        setAccess("allowed");
      })
      .catch(() => setAccess("denied"));
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setQuery(queryInput.trim());
      setUserPage(1);
    }, 250);
    return () => window.clearTimeout(timer);
  }, [queryInput]);

  const loadOverview = useCallback(async () => {
    setOverviewLoading(true);
    setOverviewError("");
    try {
      const response = await authFetch(`/api/admin-dashboard/overview/?days=${period}`);
      if (!response.ok) throw new Error("Could not load analytics right now.");
      setOverview(await response.json());
    } catch (error) {
      setOverviewError(error.message || "Could not load analytics right now.");
    } finally {
      setOverviewLoading(false);
    }
  }, [period]);

  const loadUsers = useCallback(async () => {
    setUsersLoading(true);
    setUsersError("");
    const params = new URLSearchParams({ page: String(userPage), page_size: "25", status: statusFilter });
    if (query) params.set("q", query);
    try {
      const response = await authFetch(`/api/admin-dashboard/users/?${params}`);
      if (!response.ok) throw new Error("Could not load user accounts right now.");
      setUsers(await response.json());
    } catch (error) {
      setUsersError(error.message || "Could not load user accounts right now.");
    } finally {
      setUsersLoading(false);
    }
  }, [query, statusFilter, userPage]);

  useEffect(() => {
    if (access !== "allowed" || tab !== "overview") return undefined;
    const timer = window.setTimeout(() => { void loadOverview(); }, 0);
    return () => window.clearTimeout(timer);
  }, [access, tab, loadOverview]);

  useEffect(() => {
    if (access !== "allowed" || tab !== "users") return undefined;
    const timer = window.setTimeout(() => { void loadUsers(); }, 0);
    return () => window.clearTimeout(timer);
  }, [access, tab, loadUsers]);

  const summary = overview?.summary || {};
  const activeWidgets = useMemo(
    () => preferences.widgets.map((id) => WIDGETS.find((widget) => widget.id === id)).filter(Boolean),
    [preferences.widgets],
  );

  const savePreferences = (next) => {
    setPreferences(next);
    window.localStorage.setItem(PREFS_KEY, JSON.stringify(next));
  };

  const toggleWidget = (id) => {
    const selected = preferences.widgets.includes(id);
    const widgets = selected
      ? preferences.widgets.filter((value) => value !== id)
      : [...preferences.widgets, id];
    savePreferences({ ...preferences, widgets });
  };

  const moveWidget = (id, offset) => {
    const currentIndex = preferences.widgets.indexOf(id);
    const targetIndex = currentIndex + offset;
    if (currentIndex < 0 || targetIndex < 0 || targetIndex >= preferences.widgets.length) return;
    const widgets = [...preferences.widgets];
    [widgets[currentIndex], widgets[targetIndex]] = [widgets[targetIndex], widgets[currentIndex]];
    savePreferences({ ...preferences, widgets });
  };

  const toggleColumn = (id) => {
    const columns = preferences.columns.includes(id)
      ? preferences.columns.filter((value) => value !== id)
      : [...preferences.columns, id];
    savePreferences({ ...preferences, columns });
  };

  const saveUser = async (event) => {
    event.preventDefault();
    if (!editorUser) return;
    if (editorUser.is_active === false && editorUser.initial_is_active) {
      const approved = await confirm({
        title: "Suspend this account?",
        message: "The user will no longer be able to sign in. Their existing data will be retained.",
        confirmLabel: "Suspend account",
        variant: "danger",
      });
      if (!approved) return;
    }
    setSavingUser(true);
    try {
      const response = await authFetch(`/api/admin-dashboard/users/${editorUser.id}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          full_name: editorUser.full_name,
          nickname: editorUser.nickname,
          is_active: editorUser.is_active,
          email_verified: editorUser.email_verified,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Could not update this account.");
      setEditorUser(null);
      notify("User account updated.", { type: "success" });
      await loadUsers();
      await loadOverview();
    } catch (error) {
      notify(error.message || "Could not update this account.", { type: "error" });
    } finally {
      setSavingUser(false);
    }
  };

  if (access === "checking") {
    return <div className={styles.centerState}><LoaderCircle className={styles.spinner} size={22} />Checking administrator access</div>;
  }
  if (access !== "allowed") {
    return (
      <div className={styles.centerState}>
        <div className={styles.accessCard}>
          <ShieldCheck size={28} />
          <h1>Administrator access required</h1>
          <p>This dashboard is available to authorized administrators only.</p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <header className={styles.pageHeader}>
        <div>
          <div className={styles.eyebrow}><ShieldCheck size={15} /> Administration</div>
          <h1>Admin dashboard</h1>
          <p>Monitor first-party site activity and manage user accounts.</p>
        </div>
        <div className={styles.headerActions}>
          {tab === "overview" && (
            <label className={styles.periodSelect}>
              <span>Range</span>
              <select value={period} onChange={(event) => setPeriod(Number(event.target.value))}>
                <option value={7}>7 days</option>
                <option value={30}>30 days</option>
                <option value={90}>90 days</option>
                <option value={365}>12 months</option>
              </select>
            </label>
          )}
          <button className={styles.secondaryButton} type="button" onClick={() => setCustomizeOpen((value) => !value)}>
            <SlidersHorizontal size={16} /> Customize
          </button>
          <button className={styles.iconButton} type="button" aria-label="Refresh data" onClick={() => tab === "overview" ? loadOverview() : loadUsers()}>
            <RefreshCw size={17} />
          </button>
        </div>
      </header>

      {customizeOpen && (
        <section className={styles.customizePanel} aria-label="Dashboard customization">
          <div className={styles.customizeHeader}>
            <div><strong>Customize this dashboard</strong><span>Choose visible sections and arrange their order.</span></div>
            <button className={styles.iconButton} type="button" aria-label="Close customization" onClick={() => setCustomizeOpen(false)}><X size={17} /></button>
          </div>
          {tab === "overview" ? (
            <div className={styles.preferenceList}>
              {WIDGETS.map((widget) => {
                const index = preferences.widgets.indexOf(widget.id);
                const shown = index >= 0;
                return (
                  <div className={styles.preferenceRow} key={widget.id}>
                    <label><input type="checkbox" checked={shown} onChange={() => toggleWidget(widget.id)} />{widget.label}</label>
                    <div className={styles.reorderButtons}>
                      <button type="button" aria-label={`Move ${widget.label} up`} disabled={!shown || index === 0} onClick={() => moveWidget(widget.id, -1)}><ArrowUp size={15} /></button>
                      <button type="button" aria-label={`Move ${widget.label} down`} disabled={!shown || index === preferences.widgets.length - 1} onClick={() => moveWidget(widget.id, 1)}><ArrowDown size={15} /></button>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className={styles.preferenceList}>
              {USER_COLUMNS.map((column) => (
                <label className={styles.preferenceRow} key={column.id}>
                  <span><input type="checkbox" checked={preferences.columns.includes(column.id)} onChange={() => toggleColumn(column.id)} />{column.label}</span>
                </label>
              ))}
            </div>
          )}
          <button className={styles.textButton} type="button" onClick={() => savePreferences(DEFAULT_PREFS)}>Restore defaults</button>
        </section>
      )}

      <nav className={styles.tabs} aria-label="Admin dashboard sections">
        <button className={tab === "overview" ? styles.tabActive : ""} type="button" onClick={() => setTab("overview")}><LayoutDashboard size={16} />Overview</button>
        <button className={tab === "users" ? styles.tabActive : ""} type="button" onClick={() => setTab("users")}><Users size={16} />User management</button>
      </nav>

      {tab === "overview" ? (
        <>
          <div className={styles.metricGrid}>
            <MetricCard label="Unique sessions" value={summary.unique_visitors} detail="One anonymous ID per browser tab" icon={Eye} />
            <MetricCard label="Page views" value={summary.page_views} detail="Tracked page loads" icon={Activity} />
            <MetricCard label="New signups" value={summary.new_signups} detail={`${period} day window`} icon={Users} />
            <MetricCard label="CTA clicks" value={summary.cta_clicks} detail="Landing page actions" icon={BarChart3} />
          </div>
          <div className={styles.accountSummary}>
            <span><strong>{Number(summary.total_users || 0).toLocaleString()}</strong> total accounts</span>
            <span><strong>{Number(summary.active_users || 0).toLocaleString()}</strong> active</span>
            <span><strong>{Number(summary.verified_users || 0).toLocaleString()}</strong> email verified</span>
            <span><strong>{summary.signup_rate || 0}%</strong> visitor-to-signup ratio</span>
            <small>Tracking starts when this version is deployed. Earlier traffic is not available. Signup ratio is directional; signup sessions are not linked to accounts.</small>
          </div>

          {overviewError && <div className={styles.errorBanner} role="alert">{overviewError}<button type="button" onClick={loadOverview}>Try again</button></div>}
          {overviewLoading && !overview ? <div className={styles.emptyState}><LoaderCircle className={styles.spinner} size={20} />Loading analytics</div> : null}
          {!overviewLoading && !overviewError && activeWidgets.length === 0 && <div className={styles.emptyState}>No dashboard sections selected. Use Customize to add a section.</div>}
          <div className={styles.widgetGrid}>
            {activeWidgets.map((widget) => (
              <section className={`${styles.widget} ${widget.id === "traffic" ? styles.wideWidget : ""}`} key={widget.id}>
                <div className={styles.widgetHeader}>
                  <div><h2>{widget.label}</h2><p>{widget.id === "traffic" ? `Daily activity over the last ${period} days` : widget.id === "signups" ? "Latest accounts created" : widget.id === "pages" ? "Most visited routes in this period" : "Landing page actions in this period"}</p></div>
                  <button className={styles.iconButton} type="button" aria-label={`Hide ${widget.label}`} onClick={() => toggleWidget(widget.id)}><EyeOff size={16} /></button>
                </div>
                {widget.id === "traffic" && (
                  <div className={styles.chart}>
                    {overview?.series?.some((row) => row.page_views || row.signups) ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={overview.series} margin={{ top: 8, right: 10, left: -16, bottom: 0 }}>
                          <defs>
                            <linearGradient id="visitorFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#7475ff" stopOpacity={0.32} /><stop offset="100%" stopColor="#7475ff" stopOpacity={0.01} /></linearGradient>
                            <linearGradient id="signupFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#31c48d" stopOpacity={0.24} /><stop offset="100%" stopColor="#31c48d" stopOpacity={0.01} /></linearGradient>
                          </defs>
                          <CartesianGrid stroke="var(--bg-border)" strokeDasharray="3 3" vertical={false} />
                          <XAxis dataKey="label" stroke="var(--text-muted)" tickLine={false} axisLine={false} minTickGap={24} interval={period <= 7 ? 0 : period <= 14 ? 1 : 4} tick={{ fontSize: 10 }} />
                          <YAxis stroke="var(--text-muted)" tickLine={false} axisLine={false} allowDecimals={false} />
                          <Tooltip content={<ChartTooltip />} />
                          <Area name="Page views" dataKey="page_views" type="monotone" stroke="#7475ff" strokeWidth={2.5} fill="url(#visitorFill)" />
                          <Area name="Signups" dataKey="signups" type="monotone" stroke="#31c48d" strokeWidth={2.5} fill="url(#signupFill)" />
                        </AreaChart>
                      </ResponsiveContainer>
                    ) : <div className={styles.chartEmpty}>No traffic data has been recorded in this range.</div>}
                  </div>
                )}
                {widget.id === "clicks" && (
                  <div className={styles.chart}>
                    {overview?.top_clicks?.length ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={overview.top_clicks} layout="vertical" margin={{ top: 4, right: 12, left: 12, bottom: 4 }}>
                          <CartesianGrid stroke="var(--bg-border)" strokeDasharray="3 3" horizontal={false} />
                          <XAxis type="number" stroke="var(--text-muted)" allowDecimals={false} />
                          <YAxis type="category" dataKey="label" stroke="var(--text-muted)" width={110} tickLine={false} />
                          <Tooltip content={<ChartTooltip />} />
                          <Bar name="Clicks" dataKey="clicks" fill="#7475ff" radius={[0, 5, 5, 0]} barSize={22} />
                        </BarChart>
                      </ResponsiveContainer>
                    ) : <div className={styles.chartEmpty}>No landing page clicks have been recorded yet.</div>}
                  </div>
                )}
                {widget.id === "pages" && (
                  <div className={styles.tableWrap}>
                    <table className={styles.dataTable}><thead><tr><th>Page</th><th>Views</th><th>Visitors</th></tr></thead>
                      <tbody>{overview?.top_pages?.length ? overview.top_pages.map((row) => <tr key={row.path}><td className={styles.pathCell}>{row.path}</td><td>{Number(row.page_views).toLocaleString()}</td><td>{Number(row.unique_visitors).toLocaleString()}</td></tr>) : <tr><td colSpan="3" className={styles.tableEmpty}>No page views recorded yet.</td></tr>}</tbody>
                    </table>
                  </div>
                )}
                {widget.id === "signups" && (
                  <div className={styles.tableWrap}>
                    <table className={styles.dataTable}><thead><tr><th>User</th><th>Joined</th><th>Status</th></tr></thead>
                      <tbody>{overview?.recent_signups?.length ? overview.recent_signups.map((user) => <tr key={user.id}><td><strong>{user.full_name || "Unnamed user"}</strong><small>{user.email}</small></td><td>{formatDate(user.date_joined)}</td><td><span className={`${styles.badge} ${user.is_active ? styles.badgeActive : styles.badgeInactive}`}>{user.is_active ? "Active" : "Suspended"}</span></td></tr>) : <tr><td colSpan="3" className={styles.tableEmpty}>No user accounts yet.</td></tr>}</tbody>
                    </table>
                  </div>
                )}
              </section>
            ))}
          </div>
        </>
      ) : (
        <section className={styles.userPanel}>
          <div className={styles.userToolbar}>
            <div><h2>User management</h2><p>Search accounts and manage profile, verification, and access status.</p></div>
            <div className={styles.userFilters}>
              <label className={styles.searchBox}><Search size={16} /><input value={queryInput} onChange={(event) => setQueryInput(event.target.value)} placeholder="Search name or email" /></label>
              <select value={statusFilter} onChange={(event) => { setStatusFilter(event.target.value); setUserPage(1); }} aria-label="Filter accounts">
                <option value="all">All accounts</option><option value="active">Active</option><option value="suspended">Suspended</option><option value="unverified">Unverified email</option>
              </select>
            </div>
          </div>
          {usersError && <div className={styles.errorBanner} role="alert">{usersError}<button type="button" onClick={loadUsers}>Try again</button></div>}
          <div className={styles.tableWrap}>
            <table className={styles.dataTable}>
              <thead><tr>{USER_COLUMNS.filter((column) => preferences.columns.includes(column.id)).map((column) => <th key={column.id}>{column.label}</th>)}<th>Actions</th></tr></thead>
              <tbody>
                {usersLoading && !users.results.length ? <tr><td className={styles.tableEmpty} colSpan={preferences.columns.length + 1}>Loading user accounts…</td></tr> : null}
                {!usersLoading && !users.results.length && <tr><td className={styles.tableEmpty} colSpan={preferences.columns.length + 1}>No matching accounts found.</td></tr>}
                {users.results.map((user) => (
                  <tr key={user.id}>
                    {preferences.columns.includes("name") && <td><strong>{user.full_name || "Unnamed user"}</strong>{user.nickname && <small>{user.nickname}</small>}</td>}
                    {preferences.columns.includes("email") && <td>{user.email || "—"}</td>}
                    {preferences.columns.includes("status") && <td><span className={`${styles.badge} ${user.is_active ? styles.badgeActive : styles.badgeInactive}`}>{user.is_active ? "Active" : "Suspended"}</span>{(user.is_superuser || user.is_staff) && <small>Administrator</small>}</td>}
                    {preferences.columns.includes("verified") && <td><span className={`${styles.badge} ${user.email_verified ? styles.badgeActive : styles.badgePending}`}>{user.email_verified ? "Verified" : "Unverified"}</span></td>}
                    {preferences.columns.includes("joined") && <td>{formatDate(user.date_joined)}</td>}
                    {preferences.columns.includes("lastLogin") && <td>{formatDate(user.last_login, true)}</td>}
                    <td><button className={styles.editButton} type="button" onClick={() => setEditorUser({ ...user, full_name: user.full_name || "", nickname: user.nickname || "", initial_is_active: user.is_active })}>Manage</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className={styles.pagination}>
            <span>{users.count ? `${((users.page - 1) * 25) + 1}–${Math.min(users.page * 25, users.count)} of ${users.count} accounts` : "0 accounts"}</span>
            <div><button type="button" aria-label="Previous page" disabled={users.page <= 1 || usersLoading} onClick={() => setUserPage((page) => Math.max(page - 1, 1))}><ChevronLeft size={17} /></button><span>Page {users.page} of {users.page_count}</span><button type="button" aria-label="Next page" disabled={users.page >= users.page_count || usersLoading} onClick={() => setUserPage((page) => page + 1)}><ChevronRight size={17} /></button></div>
          </div>
        </section>
      )}

      {editorUser && (
        <div className={styles.modalBackdrop} role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !savingUser) setEditorUser(null); }}>
          <section className={styles.editor} role="dialog" aria-modal="true" aria-labelledby="editor-title">
            <div className={styles.editorHeader}><div><h2 id="editor-title">Manage user</h2><p>{editorUser.email || "No email address"}</p></div><button className={styles.iconButton} type="button" aria-label="Close editor" disabled={savingUser} onClick={() => setEditorUser(null)}><X size={18} /></button></div>
            {(editorUser.is_superuser || editorUser.is_staff) && <div className={styles.adminNotice}><ShieldCheck size={16} />Administrative permissions are protected and cannot be changed here.</div>}
            <form onSubmit={saveUser}>
              <label className={styles.formField}>Full name<input maxLength={150} required value={editorUser.full_name} onChange={(event) => setEditorUser({ ...editorUser, full_name: event.target.value })} /></label>
              <label className={styles.formField}>Nickname<input maxLength={80} value={editorUser.nickname} onChange={(event) => setEditorUser({ ...editorUser, nickname: event.target.value })} /></label>
              <label className={styles.checkField}><input type="checkbox" checked={editorUser.email_verified} onChange={(event) => setEditorUser({ ...editorUser, email_verified: event.target.checked })} />Email verified</label>
              <label className={styles.checkField}><input type="checkbox" checked={editorUser.is_active} disabled={editorUser.id === currentAdminId} onChange={(event) => setEditorUser({ ...editorUser, is_active: event.target.checked })} />Account active</label>
              <p className={styles.editorHint}>Email changes use the user’s verified account flow. Suspended accounts and their data are retained.</p>
              <div className={styles.editorActions}><button className={styles.secondaryButton} type="button" disabled={savingUser} onClick={() => setEditorUser(null)}>Cancel</button><button className={styles.primaryButton} type="submit" disabled={savingUser}>{savingUser ? <><LoaderCircle className={styles.spinner} size={15} />Saving</> : <><Check size={16} />Save changes</>}</button></div>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}
