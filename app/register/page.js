"use client";

import { useState } from "react";
import { Rocket, Mail, Lock, User, ArrowRight } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

export default function RegisterPage() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const router = useRouter();

  const handleRegister = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError("");

    try {
      const res = await fetch("http://127.0.0.1:8000/api/users/register/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, email, password })
      });

      const data = await res.json();

      if (res.ok) {
        setSuccess(true);
        setTimeout(() => {
          router.push("/login");
        }, 2000);
      } else {
        // Handle DRF validation errors
        const errorMsg = Object.values(data).flat().join(" ");
        setError(errorMsg || "Registration failed");
      }
    } catch (err) {
      setError("Network error occurred.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', minHeight: '100vh', width: '100%', background: 'linear-gradient(135deg, var(--bg-base) 0%, #0d0f1a 100%)', alignItems: 'center', justifyContent: 'center', padding: '2rem 0' }}>
      
      {/* Background Ornaments */}
      <div style={{ position: 'absolute', width: '400px', height: '400px', background: 'var(--accent-primary)', filter: 'blur(150px)', opacity: 0.15, borderRadius: '50%', top: '-10%', left: '-5%' }} />
      <div style={{ position: 'absolute', width: '300px', height: '300px', background: 'var(--accent-hover)', filter: 'blur(120px)', opacity: 0.1, borderRadius: '50%', bottom: '-5%', right: '-10%' }} />

      <div className="animate-fade-in" style={{ width: '100%', maxWidth: '420px', background: 'rgba(23, 25, 35, 0.6)', backdropFilter: 'blur(20px)', border: '1px solid rgba(255, 255, 255, 0.05)', borderRadius: '16px', padding: '2.5rem', zIndex: 1, boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)' }}>
        
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginBottom: '2rem' }}>
          <div style={{ width: '56px', height: '56px', background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-hover))', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1rem', boxShadow: '0 10px 20px -5px rgba(99, 102, 241, 0.4)' }}>
            <Rocket color="white" size={28} />
          </div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>Create Account</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', textAlign: 'center' }}>Start automating your outreach today.</p>
        </div>

        {success ? (
          <div style={{ background: 'rgba(34, 197, 94, 0.1)', border: '1px solid rgba(34, 197, 94, 0.2)', color: 'var(--accent-success)', padding: '1rem', borderRadius: '8px', fontSize: '0.9rem', textAlign: 'center' }}>
            Account created successfully! Redirecting to login...
          </div>
        ) : (
          <form onSubmit={handleRegister}>
            {error && (
              <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)', color: 'var(--accent-danger)', padding: '0.75rem', borderRadius: '8px', fontSize: '0.875rem', marginBottom: '1.5rem', textAlign: 'center' }}>
                {error}
              </div>
            )}

            <div style={{ marginBottom: '1.25rem' }}>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Username</label>
              <div style={{ position: 'relative' }}>
                <User size={18} style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                <input 
                  type="text" 
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Choose a username"
                  required
                  style={{ width: '100%', padding: '0.8rem 1rem 0.8rem 2.8rem', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--bg-border)', borderRadius: '8px', color: 'var(--text-primary)', fontSize: '0.95rem', transition: 'all 0.2s' }}
                />
              </div>
            </div>

            <div style={{ marginBottom: '1.25rem' }}>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Email</label>
              <div style={{ position: 'relative' }}>
                <Mail size={18} style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                <input 
                  type="email" 
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@company.com"
                  required
                  style={{ width: '100%', padding: '0.8rem 1rem 0.8rem 2.8rem', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--bg-border)', borderRadius: '8px', color: 'var(--text-primary)', fontSize: '0.95rem', transition: 'all 0.2s' }}
                />
              </div>
            </div>

            <div style={{ marginBottom: '2rem' }}>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Password</label>
              <div style={{ position: 'relative' }}>
                <Lock size={18} style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                <input 
                  type="password" 
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Create a strong password"
                  required
                  minLength={8}
                  style={{ width: '100%', padding: '0.8rem 1rem 0.8rem 2.8rem', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--bg-border)', borderRadius: '8px', color: 'var(--text-primary)', fontSize: '0.95rem', transition: 'all 0.2s' }}
                />
              </div>
            </div>

            <button 
              type="submit" 
              disabled={isLoading}
              style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-hover))', color: 'white', padding: '0.9rem', borderRadius: '8px', fontWeight: 600, fontSize: '1rem', border: 'none', cursor: isLoading ? 'not-allowed' : 'pointer', opacity: isLoading ? 0.7 : 1, transition: 'transform 0.2s', boxShadow: '0 4px 14px 0 rgba(99, 102, 241, 0.39)' }}
            >
              {isLoading ? "Creating Account..." : (
                <>Sign Up <ArrowRight size={18} /></>
              )}
            </button>
          </form>
        )}

        <p style={{ textAlign: 'center', marginTop: '2rem', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
          Already have an account? <Link href="/login" style={{ color: 'var(--accent-primary)', fontWeight: 600, textDecoration: 'none' }}>Sign in</Link>
        </p>
      </div>
    </div>
  );
}
