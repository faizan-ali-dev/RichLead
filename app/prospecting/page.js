"use client";

import { useState, useEffect } from "react";
import { Search, MapPin, Briefcase, Zap, Users, Building2, Download } from "lucide-react";
import Link from "next/link";
import { authFetch, getAccessToken, redirectToLogin } from "../lib/api";

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
      const response = await authFetch(`/api/integrations/${provider}-search/`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ search_params: searchParams })
      });
      
      const data = await response.json();
      
      if (response.ok && data.success) {
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
      } else {
        setResultMessage(`Error: ${data.error || 'Failed to fetch leads'}`);
      }
    } catch (error) {
      console.error("Fetch error:", error);
      setResultMessage("Network error occurred.");
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
    <div className="animate-fade-in" style={{ padding: '2rem' }}>
      <header style={{ marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <Users size={28} className="text-accent-primary" />
          Lead Prospecting
        </h1>
        <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
          Choose Apollo or Hunter. Contact imports keep only verified work emails; company searches stay as previews.
        </p>
      </header>

      <div style={{ maxWidth: '800px', background: 'var(--bg-surface)', border: '1px solid var(--bg-border)', borderRadius: '12px', padding: '2rem', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }}>
        <form onSubmit={handleSearch}>
          <div style={{ marginBottom: '1.5rem' }}>
            <label htmlFor="lead-provider" style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>Lead provider</label>
            <select id="lead-provider" value={provider} onChange={(e) => changeProvider(e.target.value)} style={{ width: '100%', padding: '0.75rem 1rem', background: 'var(--bg-base)', border: '1px solid var(--bg-border)', borderRadius: '8px', color: 'var(--text-primary)', fontSize: '0.95rem' }}>
              <option value="apollo">Apollo</option>
              <option value="hunter">Hunter</option>
            </select>
          </div>
          <div style={{ marginBottom: '1.5rem' }}>
            <label htmlFor="prospect-type" style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>Search for</label>
            <select id="prospect-type" value={leadType} onChange={(e) => changeLeadType(e.target.value)} style={{ width: '100%', padding: '0.75rem 1rem', background: 'var(--bg-base)', border: '1px solid var(--bg-border)', borderRadius: '8px', color: 'var(--text-primary)', fontSize: '0.95rem' }}>
              <option value="people">Find new people — {provider === "hunter" ? "Hunter Domain Search" : "Apollo People Search"}</option>
              <option value="companies">Find new companies — {provider === "hunter" ? "Hunter Discover" : "Apollo Organization Search"}</option>
              {provider === "apollo" && <option value="contacts">Import my saved Apollo contacts</option>}
            </select>
          </div>

          {leadType === "people" && provider === "apollo" ? <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
              Job Titles
            </label>
            <div style={{ position: 'relative' }}>
              <Briefcase size={18} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input 
                type="text" 
                value={jobTitles}
                onChange={(e) => setJobTitles(e.target.value)}
                placeholder="e.g. CEO, Founder, VP of Sales" 
                style={{ width: '100%', padding: '0.75rem 1rem 0.75rem 2.5rem', background: 'var(--bg-base)', border: '1px solid var(--bg-border)', borderRadius: '8px', color: 'var(--text-primary)', fontSize: '0.95rem' }}
                required
              />
            </div>
          </div> : <div style={{ marginBottom: '1.5rem' }}>
            <label htmlFor="company-name" style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>{leadType === "people" ? "Company name or domain (required by Hunter)" : "Company name (optional)"}</label>
            <div style={{ position: 'relative' }}>
              <Building2 size={18} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input id="company-name" type="text" value={companyName} onChange={(e) => setCompanyName(e.target.value)} placeholder={provider === "hunter" && leadType === "people" ? "e.g. Acme or acme.com" : "e.g. Acme"} required={provider === "hunter" && leadType === "people"} style={{ width: '100%', padding: '0.75rem 1rem 0.75rem 2.5rem', background: 'var(--bg-base)', border: '1px solid var(--bg-border)', borderRadius: '8px', color: 'var(--text-primary)', fontSize: '0.95rem' }} />
            </div>
          </div>}

          {leadType === "people" && provider === "hunter" && <div style={{ marginBottom: '1.5rem' }}>
            <label htmlFor="hunter-job-titles" style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>Job titles (optional)</label>
            <div style={{ position: 'relative' }}>
              <Briefcase size={18} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input id="hunter-job-titles" type="text" value={jobTitles} onChange={(e) => setJobTitles(e.target.value)} placeholder="e.g. CEO, Founder, VP of Sales" style={{ width: '100%', padding: '0.75rem 1rem 0.75rem 2.5rem', background: 'var(--bg-base)', border: '1px solid var(--bg-border)', borderRadius: '8px', color: 'var(--text-primary)', fontSize: '0.95rem' }} />
            </div>
          </div>}

          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
              Location
            </label>
            <div style={{ position: 'relative' }}>
              <MapPin size={18} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input 
                type="text" 
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder={provider === "hunter" && leadType === "people" ? "2-letter country code, e.g. US or GB" : "e.g. United States, London, Remote"}
                style={{ width: '100%', padding: '0.75rem 1rem 0.75rem 2.5rem', background: 'var(--bg-base)', border: '1px solid var(--bg-border)', borderRadius: '8px', color: 'var(--text-primary)', fontSize: '0.95rem' }}
              />
            </div>
          </div>

          {!(provider === "hunter" && leadType === "people") && <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
              {leadType === "people" ? (provider === "hunter" ? "Keywords (optional)" : "Industry / Keywords") : leadType === "companies" ? "Industry / Company keywords" : "Contact search keywords"}
            </label>
            <div style={{ position: 'relative' }}>
              <Search size={18} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input 
                type="text" 
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
                placeholder="e.g. SaaS, Fintech, Healthcare" 
                style={{ width: '100%', padding: '0.75rem 1rem 0.75rem 2.5rem', background: 'var(--bg-base)', border: '1px solid var(--bg-border)', borderRadius: '8px', color: 'var(--text-primary)', fontSize: '0.95rem' }}
              />
            </div>
          </div>}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '2rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
                Number of {leadType === "companies" ? "Companies" : "Contacts"} to Fetch
              </label>
              <input 
                type="number" 
                min="1" 
                max="10"
                value={leadCount}
                onChange={(e) => setLeadCount(Number(e.target.value))}
                style={{ width: '100%', padding: '0.75rem 1rem', background: 'var(--bg-base)', border: '1px solid var(--bg-border)', borderRadius: '8px', color: 'var(--text-primary)', fontSize: '0.95rem' }}
                required
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
                Required Fields
              </label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                {availableFields.map(field => (
                  <label key={field.id} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', background: fields.includes(field.id) ? 'var(--accent-primary)' : 'var(--bg-base)', color: fields.includes(field.id) ? 'white' : 'var(--text-secondary)', border: `1px solid ${fields.includes(field.id) ? 'var(--accent-primary)' : 'var(--bg-border)'}`, padding: '0.4rem 0.65rem', borderRadius: '20px', fontSize: '0.75rem', cursor: field.required ? 'default' : 'pointer', transition: 'all 0.2s' }}>
                    <input type="checkbox" checked={fields.includes(field.id)} disabled={field.required} onChange={() => toggleField(field.id)} aria-label={`Require ${field.label}`} />
                    {field.label}{field.required ? " (required)" : ""}
                  </label>
                ))}
              </div>
            </div>
          </div>

          <p style={{ margin: '-1rem 0 1.5rem', color: 'var(--text-muted)', fontSize: '0.8rem', lineHeight: 1.5 }}>
            {leadType === "people"
              ? provider === "hunter"
                ? "Hunter searches one company/domain at a time. Only Hunter-valid personal work emails are imported; returned matches can use credits from your Hunter balance."
                : "Apollo People Search and email enrichment are needed for new people; your current API key may not include those endpoints. Verified-email enrichment may use credits."
              : leadType === "companies"
                ? "Apollo Organization Search may use 1 credit per page and your current API key may not include it. Results are previewed and exportable; companies are not saved as people or emailed."
                : "This searches contacts already saved in your Apollo workspace (not new prospects). Only verified work-email contacts are imported."}
          </p>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <button 
              type="submit" 
              disabled={isFetching}
              style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-hover))', color: 'white', padding: '0.8rem 1.5rem', borderRadius: '8px', fontWeight: 600, border: 'none', cursor: isFetching ? 'not-allowed' : 'pointer', opacity: isFetching ? 0.7 : 1, transition: 'transform 0.2s' }}
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
            
            {resultMessage && (
              <span style={{ color: resultMessage.startsWith("Error") ? 'var(--accent-warning)' : 'var(--accent-success)', fontWeight: 500 }}>
                {resultMessage}
              </span>
            )}
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
