import React, { useState, useRef, useLayoutEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { gsap, prefersReducedMotion } from "../anim/gsap";

export default function Signup() {
  const navigate = useNavigate();
  const cardRef = useRef(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [msg, setMsg] = useState("");
  const [msgType, setMsgType] = useState(""); // "success" or "error"
  const [loading, setLoading] = useState(false);

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

  const handleSignup = async (e) => {
    e.preventDefault();
    // Validation
    if (!username.trim() || !password) {
      setMsg("Please enter username and password.");
      setMsgType("error");
      return;
    }

    if (password !== confirmPassword) {
      setMsg("Passwords do not match.");
      setMsgType("error");
      return;
    }

    if (password.length < 6) {
      setMsg("Password must be at least 6 characters.");
      setMsgType("error");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch("/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      const data = await res.json();
      if (res.ok) {
        setMsg("Signup successful! Redirecting to login...");
        setMsgType("success");
        setTimeout(() => navigate("/login"), 1500);
      } else {
        setMsg(data.detail || "Signup failed. Please try again.");
        setMsgType("error");
      }
    } catch {
      setMsg("Server error. Please try again later.");
      setMsgType("error");
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

          <h1 style={styles.title}>Create Account</h1>
          <p style={styles.subtitle}>Join us to access land analysis tools</p>

          <form style={styles.form} onSubmit={handleSignup} noValidate>
            <input
              style={styles.input}
              type="text"
              placeholder="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              disabled={loading}
            />
            <input
              style={styles.input}
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              disabled={loading}
            />
            <input
              style={styles.input}
              type="password"
              placeholder="Confirm Password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
              disabled={loading}
            />
            <button
              type="submit"
              style={{
                ...styles.button,
                ...(loading ? styles.buttonDisabled : {}),
              }}
              disabled={loading}
            >
              {loading ? <span style={styles.spinner} /> : "SIGN UP"}
            </button>
          </form>

          {msg && (
            <div
              style={{
                ...styles.message,
                ...(msgType === "success" ? styles.success : styles.error),
              }}
            >
              {msg}
            </div>
          )}

          <p style={styles.loginLink}>
            Already have an account?{" "}
            <Link to="/login" style={styles.link}>
              Log in
            </Link>
          </p>
        </div>

        {/* Floating shapes */}
        <div style={styles.art} aria-hidden>
          <div style={{ ...styles.shape, ...styles.shape1 }} />
          <div style={{ ...styles.shape, ...styles.shape2 }} />
          <div style={{ ...styles.shape, ...styles.shape3 }} />
        </div>
      </div>

      {/* Global styles for animations */}
      <style>
        {`
          @keyframes fadeInUp {
            from {
              opacity: 0;
              transform: translateY(20px);
            }
            to {
              opacity: 1;
              transform: translateY(0);
            }
          }
          
          @keyframes spin {
            from {
              transform: rotate(0deg);
            }
            to {
              transform: rotate(360deg);
            }
          }
          
          @keyframes float {
            0% {
              transform: translateY(0) rotate(0deg);
            }
            50% {
              transform: translateY(-10px) rotate(5deg);
            }
            100% {
              transform: translateY(0) rotate(0deg);
            }
          }
        `}
      </style>
    </div>
  );
}

const styles = {
  page: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "linear-gradient(135deg, #013220 0%, #024d2e 100%)",
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
    background: "rgba(1, 50, 32, 0.95)",
    borderRadius: "16px",
    padding: "2.25rem",
    boxShadow: "0 20px 40px rgba(0,0,0,0.2), 0 10px 20px rgba(0,0,0,0.1)",
    border: "1px solid rgba(203, 226, 43, 0.2)",
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
  },
  brandText: { display: "flex", flexDirection: "column", lineHeight: 1 },
  brandTitle: { fontWeight: 800, color: "#fff", fontSize: "1.1rem" },
  brandSub: { fontWeight: 600, color: "#cbe22b", fontSize: "0.85rem" },
  title: {
    fontSize: "1.6rem",
    margin: 0,
    color: "#fff",
    fontWeight: 700,
  },
  subtitle: {
    color: "rgba(203, 226, 43, 0.8)",
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
  input: {
    padding: "1rem 1.2rem",
    borderRadius: "12px",
    border: "1px solid rgba(203, 226, 43, 0.2)",
    fontSize: "1rem",
    outline: "none",
    background: "rgba(0, 0, 0, 0.2)",
    color: "#fff",
    width: "100%",
    boxSizing: "border-box",
    transition: "all 0.3s ease",
  },
  inputFocus: {
    borderColor: "#cbe22b",
    boxShadow: "0 0 0 3px rgba(203, 226, 43, 0.1)",
  },
  button: {
    display: "inline-flex",
    justifyContent: "center",
    alignItems: "center",
    padding: "1rem 1.2rem",
    borderRadius: "12px",
    fontWeight: 700,
    fontSize: "1rem",
    background: "#cbe22b",
    color: "#013220",
    border: "none",
    width: "100%",
    cursor: "pointer",
    transition: "all 0.3s ease",
    marginTop: "0.5rem",
    boxShadow: "0 4px 6px rgba(0,0,0,0.1)",
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
    border: "2px solid rgba(1, 50, 32, 0.3)",
    borderTopColor: "rgba(1, 50, 32, 0.95)",
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
    color: "#cbe22b",
    background: "rgba(203, 226, 43, 0.1)",
    border: "1px solid rgba(203, 226, 43, 0.2)",
  },
  error: {
    color: "#ff6b6b",
    background: "rgba(255, 107, 107, 0.1)",
    border: "1px solid rgba(255, 107, 107, 0.2)",
  },
  loginLink: {
    color: "rgba(255, 255, 255, 0.7)",
    fontSize: "0.9rem",
    textAlign: "center",
    marginTop: "1.5rem",
  },
  link: {
    color: "#cbe22b",
    textDecoration: "none",
    fontWeight: 600,
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
    background: "rgba(203, 226, 43, 0.1)",
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
};

