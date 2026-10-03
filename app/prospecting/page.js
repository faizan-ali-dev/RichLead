"use client";

import { useState, useEffect } from "react";
import { Search, MapPin, Briefcase, Zap, Users, Building2, Download } from "lucide-react";
import Link from "next/link";
import { getAccessToken, redirectToLogin } from "../lib/api";
import { submitBackgroundJob } from "../lib/jobs";
import styles from "./page.module.css";

export default function ProspectingPage() {
  const [jobTitles, setJobTitles] = useState("");
  const [location, setLocation] = useState("");
  const [keywords, setKeywords] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [provider, setProvider] = useState("apollo");
  const [leadType, setLeadType] = useState("people");
  const [leadCount, setLeadCount] = useState(10);
  const [fields, setFields] = useState(["email"]);
  const [companyResults, setCompanyResults] = useState([]);
  const [isFetching, setIsFetching] = useState(false);
  const [resultMessage, setResultMessage] = useState("");

  useEffect(() => {
    if (!getAccessToken()) redirectToLogin();
  }, []);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!getAccessToken()) return;
    
    setIsFetching(true);
    setResultMessage("");
    setCompanyResults([]);

    const searchParams = {
      lead_type: leadType,
      domain: provider === "hunter" ? companyName : "",
      job_titles: jobTitles,
      company_name: companyName,
      location: location,
      keywords: keywords,
      count: leadCount,
      fields: fields
    };

    try {
      const data = await submitBackgroundJob(
        `/api/integrations/${provider}-search/`,
        { search_params: searchParams },
        { onStatus: (job) => setResultMessage(job.status === "queued" ? "Queued for background processing…" : "Searching and processing leads…") },
      );

      if (data.success) {
        if (leadType === "companies") {
          setCompanyResults(data.companies || []);
          const matched = data.search_matches ?? data.returned_count ?? data.fetched_count;
          const returned = data.returned_count ?? data.fetched_count;
          const filtered = data.filtered_count ?? Math.max(0, returned - data.fetched_count);
          setResultMessage(provider === "hunter"
            ? `Hunter found ${data.fetched_count} companies. Discover is free; these are preview results and no contacts were created or emailed.`
            : data.fetched_count === 0 && matched > 0
              ? `Apollo matched ${matched} companies, but none of the ${returned} returned match your required fields. Uncheck a field and search again. No contacts were created or emailed.`
              : `Apollo matched ${matched} companies; ${data.fetched_count} preview results match your required fields${filtered ? ` (${filtered} filtered out)` : ""}. No contacts were created or emailed.`);
        } else if (leadType === "contacts") {
          setResultMessage(`Success! Imported ${data.fetched_count} saved Apollo contacts with verified work emails.`);
        } else {
          setResultMessage(`${provider === "hunter" ? "Hunter" : "Apollo"} imported ${data.fetched_count} verified-email leads. The AI engine is processing them now.`);
        }
        // Reset form
        setJobTitles("");
        setLocation("");
        setKeywords("");
        setCompanyName("");
      }
    } catch (error) {
      console.error("Fetch error:", error);
      setResultMessage(`Error: ${error.message || "Network error occurred."}`);
    } finally {
      setIsFetching(false);
    }
  };

  const toggleField = (field) => {
    if (fields.includes(field)) {
      setFields(fields.filter(f => f !== field));
    } else {
      setFields([...fields, field]);
    }
  };

  const availableFields = leadType === "people"
    ? [{ id: "email", label: "Verified email", required: true }, { id: "phone", label: "Phone" }, { id: "linkedin", label: "LinkedIn" }, { id: "company_website", label: "Company website" }]
    : [{ id: "phone", label: "Phone" }, { id: "company_website", label: "Company website" }, { id: "linkedin", label: "LinkedIn" }, { id: "funding_data", label: "Funding data" }];

  const changeLeadType = (nextType) => {
    setLeadType(nextType);
    setFields(nextType === "companies" ? [] : ["email"]);
    setCompanyResults([]);
    setResultMessage("");
  };

  const changeProvider = (nextProvider) => {
    setProvider(nextProvider);
    if (nextProvider === "hunter" && leadType === "contacts") setLeadType("people");
    setCompanyResults([]);
    setResultMessage("");
  };

  const downloadCompanies = () => {
    const columns = ["name", "website", "phone", "linkedin", "location", "industry", "employee_count", "funding", "emails_count"];
    const csv = [columns.join(","), ...companyResults.map(company => columns.map(key => {
      const value = company[key] ?? "";
      return `"${String(value).replaceAll('"', '""')}"`;
    }).join(","))].join("\r\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${provider}-companies.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className={`${styles.page} animate-fade-in`}>
      <header className={styles.header}>
        <h1 className={styles.title}>
          <Users size={24} className="text-accent-primary" />
          Lead Prospecting
        </h1>
        <p className={styles.description}>
          Choose Apollo or Hunter. Contact imports keep only verified work emails; company searches stay as previews.
        </p>
      </header>

      <div className={styles.card}>
        <form onSubmit={handleSearch}>
          <div className={styles.formGrid}>
          <div className={styles.field}>
            <label htmlFor="lead-provider" className={styles.fieldLabel}>Lead provider</label>
            <select id="lead-provider" value={provider} onChange={(e) => changeProvider(e.target.value)} className={styles.control}>
              <option value="apollo">Apollo</option>
              <option value="hunter">Hunter</option>
            </select>
          </div>
          <div className={styles.field}>
            <label htmlFor="prospect-type" className={styles.fieldLabel}>Search for</label>
            <select id="prospect-type" value={leadType} onChange={(e) => changeLeadType(e.target.value)} className={styles.control}>
              <option value="people">Find new people — {provider === "hunter" ? "Hunter Domain Search" : "Apollo People Search"}</option>
              <option value="companies">Find new companies — {provider === "hunter" ? "Hunter Discover" : "Apollo Organization Search"}</option>
              {provider === "apollo" && <option value="contacts">Import my saved Apollo contacts</option>}
            </select>
          </div>

          {leadType === "people" && provider === "apollo" ? <div className={styles.field}>
            <label htmlFor="apollo-job-titles" className={styles.fieldLabel}>
              Job Titles
            </label>
            <div className={styles.controlWrap}>
              <Briefcase size={16} className={styles.controlIcon} />
              <input 
                id="apollo-job-titles"
                type="text" 
                value={jobTitles}
                onChange={(e) => setJobTitles(e.target.value)}
                placeholder="e.g. CEO, Founder, VP of Sales" 
                className={`${styles.control} ${styles.controlWithIcon}`}
                required
              />
            </div>
          </div> : <div className={styles.field}>
            <label htmlFor="company-name" className={styles.fieldLabel}>{leadType === "people" ? "Company name or domain (required by Hunter)" : "Company name (optional)"}</label>
            <div className={styles.controlWrap}>
              <Building2 size={16} className={styles.controlIcon} />
              <input id="company-name" type="text" value={companyName} onChange={(e) => setCompanyName(e.target.value)} placeholder={provider === "hunter" && leadType === "people" ? "e.g. Acme or acme.com" : "e.g. Acme"} required={provider === "hunter" && leadType === "people"} className={`${styles.control} ${styles.controlWithIcon}`} />
            </div>
          </div>}

          {leadType === "people" && provider === "hunter" && <div className={styles.field}>
            <label htmlFor="hunter-job-titles" className={styles.fieldLabel}>Job titles (optional)</label>
            <div className={styles.controlWrap}>
              <Briefcase size={16} className={styles.controlIcon} />
              <input id="hunter-job-titles" type="text" value={jobTitles} onChange={(e) => setJobTitles(e.target.value)} placeholder="e.g. CEO, Founder, VP of Sales" className={`${styles.control} ${styles.controlWithIcon}`} />
            </div>
          </div>}

          <div className={styles.field}>
            <label htmlFor="prospect-location" className={styles.fieldLabel}>
              Location
            </label>
            <div className={styles.controlWrap}>
              <MapPin size={16} className={styles.controlIcon} />
              <input 
                id="prospect-location"
                type="text" 
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder={provider === "hunter" && leadType === "people" ? "2-letter country code, e.g. US or GB" : "e.g. United States, London, Remote"}
                className={`${styles.control} ${styles.controlWithIcon}`}
              />
            </div>
          </div>

          {!(provider === "hunter" && leadType === "people") && <div className={styles.field}>
            <label htmlFor="prospect-keywords" className={styles.fieldLabel}>
              {leadType === "people" ? (provider === "hunter" ? "Keywords (optional)" : "Industry / Keywords") : leadType === "companies" ? "Industry / Company keywords" : "Contact search keywords"}
            </label>
            <div className={styles.controlWrap}>
              <Search size={16} className={styles.controlIcon} />
              <input 
                id="prospect-keywords"
                type="text" 
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
                placeholder="e.g. SaaS, Fintech, Healthcare" 
                className={`${styles.control} ${styles.controlWithIcon}`}
              />
            </div>
          </div>}
          </div>

          <div className={styles.optionsRow}>
            <div className={styles.field}>
              <label htmlFor="prospect-count" className={styles.fieldLabel}>
                Number of {leadType === "companies" ? "Companies" : "Contacts"}
              </label>
              <input
                id="prospect-count"
                type="number" 
                min="1" 
                max="10"
                value={leadCount}
                onChange={(e) => setLeadCount(Number(e.target.value))}
                className={styles.control}
                required
              />
            </div>
            <div className={styles.field}>
              <span className={styles.fieldLabel}>Required fields</span>
              <div className={styles.fieldOptions}>
                {availableFields.map((field) => (
                  <label key={field.id} className={`${styles.optionChip} ${fields.includes(field.id) ? styles.optionChipSelected : ""}`}>
                    <input type="checkbox" checked={fields.includes(field.id)} disabled={field.required} onChange={() => toggleField(field.id)} aria-label={`Require ${field.label}`} />
                    {field.label}{field.required ? " (required)" : ""}
                  </label>
                ))}
              </div>
            </div>
          </div>

          <p className={styles.helperText}>
            {leadType === "people"
              ? provider === "hunter"
                ? "Hunter searches one company/domain at a time. Only Hunter-valid personal work emails are imported; returned matches can use credits from your Hunter balance."
                : "Apollo People Search and email enrichment are needed for new people; your current API key may not include those endpoints. Verified-email enrichment may use credits."
              : leadType === "companies"
                ? "Apollo Organization Search may use 1 credit per page and your current API key may not include it. Results are previewed and exportable; companies are not saved as people or emailed."
                : "This searches contacts already saved in your Apollo workspace (not new prospects). Only verified work-email contacts are imported."}
          </p>

          <div className={styles.submitRow}>
            <button 
              type="submit" 
              disabled={isFetching}
              className={styles.searchButton}
            >
              {isFetching ? (
                <>Loading...</>
              ) : (
                <>
                  <Zap size={18} />
                  {leadType === "people" ? "Find People & Import" : leadType === "companies" ? "Search Companies" : "Import Saved Contacts"}
                </>
              )}
            </button>
            
            {resultMessage && <span className={`${styles.resultMessage} ${resultMessage.startsWith("Error") ? styles.resultError : ""}`}>{resultMessage}</span>}
          </div>
        </form>

        {leadType === "companies" && companyResults.length > 0 && <section style={{ marginTop: '1.5rem', border: '1px solid var(--bg-border)', borderRadius: '10px', overflow: 'hidden' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem', borderBottom: '1px solid var(--bg-border)' }}>
            <h3 style={{ color: 'var(--text-primary)', margin: 0 }}>Company results ({companyResults.length})</h3>
            <button type="button" onClick={downloadCompanies} style={{ display: 'inline-flex', gap: '0.4rem', alignItems: 'center', padding: '0.5rem 0.75rem', borderRadius: '6px', border: '1px solid var(--bg-border)', background: 'var(--bg-base)', color: 'var(--text-primary)', cursor: 'pointer' }}><Download size={16} /> Export CSV</button>
          </div>
          <div style={{ overflowX: 'auto' }}><table style={{ width: '100%', borderCollapse: 'collapse', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            <thead><tr>{["Company", "Website", "Phone", "Location", "Industry", "Employees", "Funding", ...(provider === "hunter" ? ["Emails found", "Action"] : [])].map(label => <th key={label} style={{ textAlign: 'left', padding: '0.75rem', borderBottom: '1px solid var(--bg-border)' }}>{label}</th>)}</tr></thead>
            <tbody>{companyResults.map(company => <tr key={company.id || company.name}>
              <td style={{ padding: '0.75rem', color: 'var(--text-primary)' }}>{company.name}</td>
              <td style={{ padding: '0.75rem' }}>{company.website ? <a href={company.website.startsWith("http") ? company.website : `https://${company.website}`} target="_blank" rel="noreferrer" style={{ color: 'var(--accent-primary)' }}>{company.website}</a> : "—"}</td>
              <td style={{ padding: '0.75rem' }}>{company.phone || "—"}</td><td style={{ padding: '0.75rem' }}>{company.location || "—"}</td><td style={{ padding: '0.75rem' }}>{company.industry || "—"}</td><td style={{ padding: '0.75rem' }}>{company.employee_count ?? "—"}</td><td style={{ padding: '0.75rem' }}>{company.funding || "—"}</td>{provider === "hunter" && <><td style={{ padding: '0.75rem' }}>{company.emails_count ?? "—"}</td><td style={{ padding: '0.75rem' }}><button type="button" onClick={() => { setLeadType("people"); setCompanyName(company.website || company.name); setFields(["email"]); setResultMessage(""); }} style={{ padding: '0.4rem 0.6rem', borderRadius: '6px', border: '1px solid var(--bg-border)', background: 'var(--bg-base)', color: 'var(--accent-primary)', cursor: 'pointer' }}>Find people</button></td></>}
            </tr>)}</tbody>
          </table></div>
        </section>}

        <div style={{ marginTop: '2rem', paddingTop: '2rem', borderTop: '1px solid var(--bg-border)' }}>
          <h3 style={{ fontSize: '1rem', color: 'var(--text-primary)', marginBottom: '0.5rem' }}>{leadType === "companies" ? "Company search results" : "What happens next?"}</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', lineHeight: 1.5, marginBottom: '1rem' }}>
            {leadType === "companies"
              ? "Company results stay on this page for review or CSV export. They are not added as email contacts."
              : <>Depending on your <Link href="/settings" style={{ color: 'var(--accent-primary)', textDecoration: 'none' }}>Autopilot Settings</Link>, verified-email contacts will either be emailed automatically or sent to your Review Queue for manual approval.</>}
          </p>
          <Link href="/review" style={{ display: 'inline-block', color: 'var(--text-primary)', background: 'var(--bg-base)', border: '1px solid var(--bg-border)', padding: '0.5rem 1rem', borderRadius: '6px', fontSize: '0.875rem', textDecoration: 'none' }}>
            Go to Review Queue →
          </Link>
        </div>
      </div>
    </div>
  );
}
