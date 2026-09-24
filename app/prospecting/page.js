"use client";

import { useState, useEffect } from "react";
import { Search, MapPin, Briefcase, Zap, Users } from "lucide-react";
import Link from "next/link";

export default function ProspectingPage() {
  const [jobTitles, setJobTitles] = useState("");
  const [location, setLocation] = useState("");
  const [keywords, setKeywords] = useState("");
  const [leadCount, setLeadCount] = useState(10);
  const [fields, setFields] = useState(["email", "name", "company", "title", "linkedin"]);
  const [isFetching, setIsFetching] = useState(false);
  const [resultMessage, setResultMessage] = useState("");
  const [token, setToken] = useState(null);

  useEffect(() => {
    // Get token from localStorage
    const storedToken = localStorage.getItem("richlead_token");
    if (storedToken) {
      setToken(storedToken);
    } else {
      // Redirect to login if not authenticated
      window.location.href = "/login";
    }
  }, []);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!token) return;
    
    setIsFetching(true);
    setResultMessage("");

    const searchParams = {
      job_titles: jobTitles,
      location: location,
      keywords: keywords,
      count: leadCount,
      fields: fields
    };

    try {
      const response = await fetch("http://127.0.0.1:8000/api/integrations/apollo-search/", {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}` 
        },
        body: JSON.stringify({ search_params: searchParams })
      });
      
      const data = await response.json();
      
      if (response.ok && data.success) {
        setResultMessage(`Success! Found ${data.fetched_count} leads. The AI engine is processing them now.`);
        // Reset form
        setJobTitles("");
        setLocation("");
        setKeywords("");
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

  const availableFields = ["email", "phone", "linkedin", "company_website", "funding_data"];

  return (
    <div className="animate-fade-in" style={{ padding: '2rem' }}>
      <header style={{ marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <Users size={28} className="text-accent-primary" />
          Apollo Prospecting
        </h1>
        <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
          Search for ideal prospects using Apollo. The AI Engine will automatically process the results.
        </p>
      </header>

      <div style={{ maxWidth: '800px', background: 'var(--bg-surface)', border: '1px solid var(--bg-border)', borderRadius: '12px', padding: '2rem', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }}>
        <form onSubmit={handleSearch}>
          
          <div style={{ marginBottom: '1.5rem' }}>
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
          </div>

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
                placeholder="e.g. United States, London, Remote" 
                style={{ width: '100%', padding: '0.75rem 1rem 0.75rem 2.5rem', background: 'var(--bg-base)', border: '1px solid var(--bg-border)', borderRadius: '8px', color: 'var(--text-primary)', fontSize: '0.95rem' }}
              />
            </div>
          </div>

          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
              Industry / Keywords
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
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '2rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
                Number of Leads to Fetch
              </label>
              <input 
                type="number" 
                min="1" 
                max="5000"
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
                  <button 
                    key={field} 
                    type="button"
                    onClick={() => toggleField(field)}
                    style={{ 
                      background: fields.includes(field) ? 'var(--accent-primary)' : 'var(--bg-base)', 
                      color: fields.includes(field) ? 'white' : 'var(--text-secondary)',
                      border: `1px solid ${fields.includes(field) ? 'var(--accent-primary)' : 'var(--bg-border)'}`,
                      padding: '0.4rem 0.8rem', 
                      borderRadius: '20px', 
                      fontSize: '0.75rem',
                      cursor: 'pointer',
                      transition: 'all 0.2s'
                    }}
                  >
                    {field.replace('_', ' ').toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <button 
              type="submit" 
              disabled={isFetching || !token}
              style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-hover))', color: 'white', padding: '0.8rem 1.5rem', borderRadius: '8px', fontWeight: 600, border: 'none', cursor: isFetching ? 'not-allowed' : 'pointer', opacity: isFetching ? 0.7 : 1, transition: 'transform 0.2s' }}
            >
              {isFetching ? (
                <>Loading...</>
              ) : (
                <>
                  <Zap size={18} />
                  Fetch & Generate Leads
                </>
              )}
            </button>
            
            {resultMessage && (
              <span style={{ color: resultMessage.includes("Success") ? 'var(--accent-success)' : 'var(--accent-warning)', fontWeight: 500 }}>
                {resultMessage}
              </span>
            )}
          </div>
        </form>

        <div style={{ marginTop: '2rem', paddingTop: '2rem', borderTop: '1px solid var(--bg-border)' }}>
          <h3 style={{ fontSize: '1rem', color: 'var(--text-primary)', marginBottom: '0.5rem' }}>What happens next?</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', lineHeight: 1.5, marginBottom: '1rem' }}>
            Depending on your <Link href="/settings" style={{ color: 'var(--accent-primary)', textDecoration: 'none' }}>Autopilot Settings</Link>, fetched leads will either be emailed automatically or sent to your Review Queue for manual approval.
          </p>
          <Link href="/review" style={{ display: 'inline-block', color: 'var(--text-primary)', background: 'var(--bg-base)', border: '1px solid var(--bg-border)', padding: '0.5rem 1rem', borderRadius: '6px', fontSize: '0.875rem', textDecoration: 'none' }}>
            Go to Review Queue →
          </Link>
        </div>
      </div>
    </div>
  );
}
