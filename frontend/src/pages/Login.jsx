import React, { useState, useEffect, useRef, useLayoutEffect } from "react";
import { useNavigate } from "react-router-dom";
import { gsap, prefersReducedMotion } from "../anim/gsap";

export default function Login() {
  const navigate = useNavigate();
  const cardRef = useRef(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState(""); // "success" | "error"
  const [loading, setLoading] = useState(false);

  // GSAP entrance: card scales in, contents stagger up.
  useLayoutEffect(() => {
    if (prefersReducedMotion() || !cardRef.current) return;
    const ctx = gsap.context(() => {
      gsap.from(cardRef.current, { scale: 0.96, opacity: 0, duration: 0.6, ease: "power3.out" });
      gsap.from(cardRef.current.children, {
        y: 22, opacity: 0, stagger: 0.09, duration: 0.5, ease: "power3.out", delay: 0.15,
      });
    }, cardRef);
    return () => ctx.revert();
  }, []);

  // --- Optional: Auto redirect if already logged in (from localStorage) ---
  useEffect(() => {
    const existingUser = localStorage.getItem("user");
    if (existingUser) {
      navigate("/dashboard", { replace: true });
    }
  }, [navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage("");
    setMessageType("");

    if (!username.trim() || !password) {
      setMessage("Please enter username and password.");
      setMessageType("error");
      return;
    }

    // --- Normal backend login (optional, kept for later use) ---
    setLoading(true);
    try {
      const res = await fetch("/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username.trim(), password }),
      });

      const data = await res.json().catch(() => ({}));

      if (res.ok) {
        const token = data.access_token || data.token || null;
        localStorage.setItem(
          "user",
          JSON.stringify({ username, access_token: token, token }),
        );
        setMessage("Login successful — redirecting...");
        setMessageType("success");
        setTimeout(() => navigate("/dashboard"), 800);
      } else {
        setMessage(data.detail || data.error || "Login failed.");
        setMessageType("error");
      }
    } catch (err) {
      console.error("Login error:", err);
      setMessage("Error connecting to server.");
      setMessageType("error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.page}>
      <div style={styles.hero}>
        <div style={styles.card} ref={cardRef}>
          <div style={styles.brand}>
            <div style={styles.logoIcon} aria-hidden>
              🌍
            </div>
            <div style={styles.brandText}>
              <span style={styles.brandTitle}>TerraMind</span>
              <span style={styles.brandSub}>Insight</span>
            </div>
          </div>

          <h1 style={styles.title}>Welcome back</h1>
          <p style={styles.subtitle}>
            Sign in to continue to your land analyses
          </p>

          <form style={styles.form} onSubmit={handleSubmit} noValidate>
            <div style={styles.inputContainer}>
              <input
                style={{
                  ...styles.input,
                  ...(username ? styles.inputFilled : {}),
                }}
                type="text"
                placeholder="Username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                disabled={loading}
              />
            </div>
            <div style={styles.inputContainer}>
              <input
                style={{
                  ...styles.input,
                  ...(password ? styles.inputFilled : {}),
                }}
                type="password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                disabled={loading}
              />
            </div>
            <button
              type="submit"
              style={{
                ...styles.button,
                ...(loading ? styles.buttonDisabled : {}),
              }}
              disabled={loading}
            >
              {loading ? <span style={styles.spinner} /> : "LOGIN"}
            </button>
          </form>

          {message && (
            <div
              style={{
                ...styles.message,
                ...(messageType === "success" ? styles.success : styles.error),
              }}
            >
              {message}
            </div>
          )}
        </div>

        <div style={styles.art} aria-hidden>
          <div style={{ ...styles.shape, ...styles.shape1 }} />
          <div style={{ ...styles.shape, ...styles.shape2 }} />
          <div style={{ ...styles.shape, ...styles.shape3 }} />
          <div style={{ ...styles.shape, ...styles.shape4 }} />
        </div>
      </div>

      <style>
        {`
          @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
          }
          @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
          }
          @keyframes float {
            0% { transform: translateY(0) rotate(0deg); }
            50% { transform: translateY(-10px) rotate(5deg); }
            100% { transform: translateY(0) rotate(0deg); }
          }
          @keyframes pulse {
            0% { transform: scale(1); opacity: 0.7; }
            50% { transform: scale(1.05); opacity: 0.9; }
            100% { transform: scale(1); opacity: 0.7; }
          }
        `}
      </style>
    </div>
  );
}

// --- styles unchanged from your version ---
const styles = {
  page: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "linear-gradient(135deg, #2563eb 0%, #10b981 100%)",
    padding: "2rem",
    fontFamily:
      "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif",
  },
  hero: {
    width: "100%",
    maxWidth: "1100px",
    display: "flex",
    gap: "2.5rem",
    alignItems: "center",
    justifyContent: "center",
    position: "relative",
  },
  card: {
    width: "100%",
    maxWidth: "420px",
    background: "rgba(255, 255, 255, 0.98)",
    borderRadius: "16px",
    padding: "2.25rem",
    boxShadow: "0 20px 40px rgba(0,0,0,0.1), 0 10px 20px rgba(0,0,0,0.05)",
    border: "1px solid rgba(255,255,255,0.2)",
    backdropFilter: "blur(10px)",
    zIndex: 10,
    display: "flex",
    flexDirection: "column",
    gap: "1rem",
  },
  brand: {
    display: "flex",
    alignItems: "center",
    gap: "0.9rem",
    marginBottom: "0.5rem",
  },
  logoIcon: {
    fontSize: "2.1rem",
    lineHeight: 1,
    animation: "pulse 4s infinite ease-in-out",
  },
  brandText: { display: "flex", flexDirection: "column", lineHeight: 1 },
  brandTitle: { fontWeight: 800, color: "#1e293b", fontSize: "1.1rem" },
  brandSub: { fontWeight: 600, color: "#059669", fontSize: "0.85rem" },
  title: {
    fontSize: "1.6rem",
    margin: 0,
    color: "#1e293b",
    fontWeight: 700,
    background: "linear-gradient(135deg, #2563eb 0%, #059669 100%)",
    backgroundClip: "text",
    WebkitBackgroundClip: "text",
    width: "fit-content",
  },
  subtitle: {
    color: "#64748b",
    marginBottom: "1rem",
    fontSize: "0.95rem",
    lineHeight: 1.5,
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: "1rem",
    marginTop: "0.5rem",
  },
  inputContainer: {
    position: "relative",
  },
  input: {
    padding: "1rem 1.2rem",
    borderRadius: "12px",
    border: "1px solid #e2e8f0",
    fontSize: "1rem",
    outline: "none",
    background: "white",
    color: "#1e293b",
    width: "100%",
    boxSizing: "border-box",
    transition: "all 0.3s ease",
    boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
  },
  inputFilled: {
    borderColor: "#10b981",
  },
  button: {
    display: "inline-flex",
    justifyContent: "center",
    alignItems: "center",
    padding: "1rem 1.2rem",
    borderRadius: "12px",
    fontWeight: 700,
    fontSize: "1rem",
    background: "linear-gradient(135deg, #2563eb 0%, #3b82f6 100%)",
    color: "white",
    border: "none",
    width: "100%",
    cursor: "pointer",
    transition: "all 0.3s ease",
    marginTop: "0.5rem",
    boxShadow: "0 4px 6px rgba(37, 99, 235, 0.2)",
  },
  buttonDisabled: {
    opacity: 0.7,
    cursor: "not-allowed",
    transform: "none",
  },
  spinner: {
    width: "20px",
    height: "20px",
    borderRadius: "50%",
    border: "2px solid rgba(255,255,255,0.3)",
    borderTopColor: "rgba(255,255,255,0.95)",
    animation: "spin 0.9s linear infinite",
  },
  message: {
    marginTop: "1rem",
    fontSize: "0.95rem",
    padding: "0.8rem 1rem",
    borderRadius: "10px",
    fontWeight: 500,
  },
  success: {
    color: "#065f46",
    background: "rgba(16,185,129,0.1)",
    border: "1px solid rgba(16,185,129,0.2)",
  },
  error: {
    color: "#b91c1c",
    background: "rgba(239,68,68,0.1)",
    border: "1px solid rgba(239,68,68,0.2)",
  },
  art: {
    position: "absolute",
    width: "100%",
    height: "100%",
    top: 0,
    left: 0,
    pointerEvents: "none",
  },
  shape: {
    position: "absolute",
    borderRadius: "50%",
    background:
      "linear-gradient(135deg, rgba(255,255,255,0.15) 0%, rgba(255,255,255,0.05) 100%)",
    animation: "float 6s infinite ease-in-out",
  },
  shape1: {
    width: "140px",
    height: "140px",
    top: "10%",
    left: "5%",
    animationDelay: "0s",
  },
  shape2: {
    width: "200px",
    height: "200px",
    bottom: "5%",
    right: "5%",
    animationDelay: "1s",
  },
  shape3: {
    width: "90px",
    height: "90px",
    bottom: "35%",
    left: "20%",
    animationDelay: "2s",
  },
  shape4: {
    width: "120px",
    height: "120px",
    top: "30%",
    right: "15%",
    animationDelay: "1.5s",
    borderRadius: "30% 70% 70% 30% / 30% 30% 70% 70%",
  },
};
