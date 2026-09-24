"use client";

import { useState } from "react";
import { Rocket, Mail, Lock, ArrowRight } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();

  const handleLogin = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError("");

    try {
      const res = await fetch("http://127.0.0.1:8000/api/token/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
      });

      const data = await res.json();

      if (res.ok) {
        // Save token to localStorage for our MVP
        localStorage.setItem("richlead_token", data.access);
        router.push("/");
      } else {
        setError(data.detail || "Invalid credentials");
      }
    } catch (err) {
      setError("Network error occurred.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', minHeight: '100vh', width: '100%', background: 'linear-gradient(135deg, var(--bg-base) 0%, #0d0f1a 100%)', alignItems: 'center', justifyContent: 'center' }}>
      
      {/* Background Ornaments */}
      <div style={{ position: 'absolute', width: '400px', height: '400px', background: 'var(--accent-primary)', filter: 'blur(150px)', opacity: 0.15, borderRadius: '50%', top: '-10%', right: '-5%' }} />
      <div style={{ position: 'absolute', width: '300px', height: '300px', background: 'var(--accent-hover)', filter: 'blur(120px)', opacity: 0.1, borderRadius: '50%', bottom: '-5%', left: '-10%' }} />

      <div className="animate-fade-in" style={{ width: '100%', maxWidth: '420px', background: 'rgba(23, 25, 35, 0.6)', backdropFilter: 'blur(20px)', border: '1px solid rgba(255, 255, 255, 0.05)', borderRadius: '16px', padding: '2.5rem', zIndex: 1, boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginBottom: '2rem' }}>
          <div style={{ width: '56px', height: '56px', background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-hover))', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1rem', boxShadow: '0 10px 20px -5px rgba(99, 102, 241, 0.4)' }}>
            <Rocket color="white" size={28} />
          </div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>Welcome Back</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', textAlign: 'center' }}>Sign in to continue to RichLead</p>
        </div>

        {error && (
          <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)', color: 'var(--accent-danger)', padding: '0.75rem', borderRadius: '8px', fontSize: '0.875rem', marginBottom: '1.5rem', textAlign: 'center' }}>
            {error}
          </div>
        )}

        <form onSubmit={handleLogin}>
          <div style={{ marginBottom: '1.25rem' }}>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Username</label>
            <div style={{ position: 'relative' }}>
              <Mail size={18} style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input 
                type="text" 
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter your username"
                required
                style={{ width: '100%', padding: '0.8rem 1rem 0.8rem 2.8rem', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--bg-border)', borderRadius: '8px', color: 'var(--text-primary)', fontSize: '0.95rem', transition: 'all 0.2s' }}
              />
            </div>
          </div>

          <div style={{ marginBottom: '2rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Password</label>
              <a href="#" style={{ fontSize: '0.8rem', color: 'var(--accent-primary)', textDecoration: 'none' }}>Forgot?</a>
            </div>
            <div style={{ position: 'relative' }}>
              <Lock size={18} style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input 
                type="password" 
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                style={{ width: '100%', padding: '0.8rem 1rem 0.8rem 2.8rem', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--bg-border)', borderRadius: '8px', color: 'var(--text-primary)', fontSize: '0.95rem', transition: 'all 0.2s' }}
              />
            </div>
          </div>

          <button 
            type="submit" 
            disabled={isLoading}
            style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-hover))', color: 'white', padding: '0.9rem', borderRadius: '8px', fontWeight: 600, fontSize: '1rem', border: 'none', cursor: isLoading ? 'not-allowed' : 'pointer', opacity: isLoading ? 0.7 : 1, transition: 'transform 0.2s', boxShadow: '0 4px 14px 0 rgba(99, 102, 241, 0.39)' }}
          >
            {isLoading ? "Signing in..." : (
              <>Sign In <ArrowRight size={18} /></>
            )}
          </button>
        </form>

        <p style={{ textAlign: 'center', marginTop: '2rem', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
          Don't have an account? <Link href="/register" style={{ color: 'var(--accent-primary)', fontWeight: 600, textDecoration: 'none' }}>Sign up</Link>
        </p>
      </div>
    </div>
  );
}
