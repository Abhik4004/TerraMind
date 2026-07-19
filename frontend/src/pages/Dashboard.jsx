// src/pages/Dashboard.jsx
import React, { useEffect, useState, useMemo, useRef, useLayoutEffect } from "react";
import { useNavigate } from "react-router-dom";
import { gsap, prefersReducedMotion } from "../anim/gsap";

function Dashboard() {
  const navigate = useNavigate();
  const rootRef = useRef(null);
  const [user, setUser] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("all");
  const [hoverStates, setHoverStates] = useState({
    newAnalysis: false,
    cta: false,
    views: {},
  });

  const API_BASE = import.meta.env.VITE_API_BASE || "";

  // Load user session
  useEffect(() => {
    const storedUser = localStorage.getItem("user");
    if (storedUser) {
      try {
        setUser(JSON.parse(storedUser));
      } catch {
        localStorage.removeItem("user");
        navigate("/login");
      }
    } else {
      navigate("/login");
    }
  }, [navigate]);

  const formatDate = (dateString) => {
    if (!dateString) return "Unknown date";
    try {
      const d = new Date(dateString);
      if (!isNaN(d)) {
        return (
          d.toLocaleDateString() +
          " " +
          d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
        );
      }
    } catch {
      return "Unknown date";
    }
    return "Unknown date";
  };

  const getLastMessage = (chatHistory) => {
    if (!chatHistory || chatHistory.length === 0) return "No messages yet";
    const lastUserMsg = chatHistory
      .slice()
      .reverse()
      .find((msg) => msg.role === "user");
    if (lastUserMsg && lastUserMsg.content) {
      const content = String(lastUserMsg.content);
      return content.slice(0, 150) + (content.length > 150 ? "..." : "");
    }
    return "No messages yet";
  };

  // Fetch sessions from the FastAPI backend (in-memory store)
  useEffect(() => {
    let mounted = true;
    async function fetchSessions() {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/api/sessions`, {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
          },
        });

        if (!res.ok) {
          console.error("Failed to fetch sessions:", res.status);
          if (mounted) setSessions([]);
          return;
        }

        const data = await res.json();
        const sessionsList = data.sessions || [];

        if (mounted) {
          setSessions(sessionsList);
        }
      } catch (err) {
        console.error("Error fetching sessions:", err);
        if (mounted) setSessions([]);
      } finally {
        if (mounted) setLoading(false);
      }
    }

    if (user) {
      fetchSessions();
    }

    return () => {
      mounted = false;
    };
  }, [API_BASE, user]);

  const handleNewAnalysis = () => {
    navigate("/analyze");
  };

  const handleViewSession = async (sessionId) => {
    try {
      const res = await fetch(`${API_BASE}/api/session/${sessionId}`);
      if (res.ok) {
        const sessionData = await res.json();
        navigate("/analyze", {
          state: {
            sessionData: sessionData,
            isViewMode: true,
          },
        });
      }
    } catch (err) {
      console.error("Error loading session:", err);
    }
  };

  const filteredSessions = useMemo(() => {
    let result = sessions;

    if (searchTerm) {
      const q = searchTerm.toLowerCase();
      result = result.filter((session) => {
        const sessionId = (session.session_id || "").toLowerCase();
        const chatHistory = session.chat_history || [];
        const messagesText = chatHistory
          .map((msg) => (msg.content || "").toLowerCase())
          .join(" ");

        return sessionId.includes(q) || messagesText.includes(q);
      });
    }

    if (activeTab === "recent") {
      result = result.slice(0, 5);
    }

    return result;
  }, [sessions, searchTerm, activeTab]);

  const updateHoverState = (key, value) => {
    setHoverStates((prev) => ({ ...prev, [key]: value }));
  };

  // GSAP entrance: panels slide in, stat + session cards stagger up.
  useLayoutEffect(() => {
    if (!user || prefersReducedMotion() || !rootRef.current) return;
    const ctx = gsap.context(() => {
      gsap.from("aside", { x: -32, opacity: 0, duration: 0.6, ease: "power3.out" });
      gsap.from("main", { x: 32, opacity: 0, duration: 0.6, ease: "power3.out" });
      gsap.from(".stat-anim", { y: 18, opacity: 0, stagger: 0.1, duration: 0.5, delay: 0.25, ease: "power3.out" });
      gsap.from(".analysis-card", {
        y: 28, opacity: 0, stagger: 0.08, duration: 0.5, delay: 0.3, ease: "power3.out",
        clearProps: "all", // let CSS :hover transform work after entrance
      });
    }, rootRef);
    return () => ctx.revert();
  }, [user, loading]);

  if (!user) {
    return <div style={styles.loading}>Loading...</div>;
  }

  return (
    <div style={styles.outerContainer} ref={rootRef}>
      <div style={styles.container}>
        {/* Left Panel - Premium Design */}
        <aside style={styles.leftPanel}>
          <div style={styles.logoContainer}>
            <div style={styles.logo}>
              <div style={styles.logoIcon}>🌍</div>
              <div style={styles.logoGlow}></div>
            </div>
            <h1 style={styles.logoText}>TerraMind Insight</h1>
            <div style={styles.logoSubtitle}>Premium Geospatial Analytics</div>
          </div>

          <div style={styles.userSection}>
            <div style={styles.avatarContainer}>
              <div style={styles.avatar}>
                {user.username ? user.username.charAt(0).toUpperCase() : "U"}
              </div>
              <div style={styles.statusIndicator}></div>
            </div>
            <h2 style={styles.welcomeTitle}>Welcome back, {user.username}!</h2>
            <p style={styles.welcomeSubtitle}>
              Your geospatial intelligence hub
            </p>
          </div>

          <div style={styles.statsGrid}>
            <div style={styles.statCard} className="stat-anim">
              <div style={styles.statIcon}>💬</div>
              <div style={styles.statContent}>
                <span style={styles.statNumber}>{sessions.length}</span>
                <span style={styles.statLabel}>Active Sessions</span>
              </div>
            </div>
            <div style={styles.statCard} className="stat-anim">
              <div style={styles.statIcon}>🔍</div>
              <div style={styles.statContent}>
                <span style={styles.statNumber}>
                  {sessions.reduce((sum, s) => sum + (s.message_count || 0), 0)}
                </span>
                <span style={styles.statLabel}>Total Queries</span>
              </div>
            </div>
          </div>

          <div style={styles.decoration}>
            <div style={styles.floatingOrb}></div>
            <div style={styles.floatingOrb}></div>
            <div style={styles.floatingOrb}></div>
          </div>
        </aside>

        {/* Right Panel - Enhanced Content */}
        <main style={styles.rightPanel}>
          <div style={styles.header}>
            <div style={styles.headerContent}>
              <h2 style={styles.pageTitle}>Your Sessions</h2>
              <div style={styles.headerActions}>
                <button
                  style={{
                    ...styles.newAnalysisBtn,
                    ...(hoverStates.newAnalysis && styles.newAnalysisBtnHover),
                  }}
                  onClick={handleNewAnalysis}
                  onMouseEnter={() => updateHoverState("newAnalysis", true)}
                  onMouseLeave={() => updateHoverState("newAnalysis", false)}
                >
                  <span style={styles.plusIcon}>+</span>
                  New Analysis
                </button>
              </div>
            </div>
          </div>

          <div style={styles.searchSection}>
            <div style={styles.searchContainer}>
              <div style={styles.searchWrapper}>
                <span style={styles.searchIcon}>🔍</span>
                <input
                  type="text"
                  placeholder="Search sessions by ID or message content..."
                  style={styles.searchInput}
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
              <div style={styles.tabContainer}>
                <button
                  style={
                    activeTab === "all"
                      ? { ...styles.tabButton, ...styles.tabButtonActive }
                      : styles.tabButton
                  }
                  onClick={() => setActiveTab("all")}
                >
                  All Sessions
                </button>
                <button
                  style={
                    activeTab === "recent"
                      ? { ...styles.tabButton, ...styles.tabButtonActive }
                      : styles.tabButton
                  }
                  onClick={() => setActiveTab("recent")}
                >
                  Recent
                </button>
              </div>
            </div>
          </div>

          <div style={styles.content}>
            {loading ? (
              <div style={styles.loadingState}>
                <div style={styles.spinner}></div>
                <p style={styles.loadingText}>Loading your sessions...</p>
              </div>
            ) : filteredSessions.length === 0 ? (
              <div style={styles.emptyState}>
                <div style={styles.emptyIcon}>
                  <div style={styles.compassSpin}>🧭</div>
                </div>
                <h3 style={styles.emptyTitle}>
                  {searchTerm ? "No matching sessions" : "No sessions yet"}
                </h3>
                <p style={styles.emptyText}>
                  {searchTerm
                    ? "Try a different search term or create a new session"
                    : "Start your geospatial journey with a new analysis"}
                </p>
                {!searchTerm && (
                  <button
                    style={{
                      ...styles.ctaButton,
                      ...(hoverStates.cta && styles.ctaButtonHover),
                    }}
                    onClick={handleNewAnalysis}
                    onMouseEnter={() => updateHoverState("cta", true)}
                    onMouseLeave={() => updateHoverState("cta", false)}
                  >
                    Start Analysis
                  </button>
                )}
              </div>
            ) : (
              <div style={styles.analysesGrid}>
                {filteredSessions.map((session, index) => {
                  const sessionId = session.session_id;
                  const createdDate = formatDate(session.created_at);
                  const lastActivity = formatDate(
                    session.last_activity || session.created_at,
                  );
                  const messageCount = session.message_count || 0;
                  const lastMessage = getLastMessage(session.chat_history);

                  return (
                    <div
                      key={sessionId}
                      style={{
                        ...styles.analysisCard,
                        animationDelay: `${index * 0.1}s`,
                      }}
                      className="analysis-card"
                    >
                      <div style={styles.cardHeader}>
                        <div style={styles.cardBadge}>
                          <span style={styles.badgeIcon}>💬</span>
                          Session
                        </div>
                        <span style={styles.date}>{createdDate}</span>
                      </div>
                      <div style={styles.cardContent}>
                        <h3 style={styles.analysisTitle}>
                          Session {sessionId.slice(0, 8)}...
                        </h3>
                        <div style={styles.sessionMeta}>
                          <div style={styles.metaItem}>
                            <span style={styles.metaIcon}>📊</span>
                            <span style={styles.metaText}>
                              {messageCount} messages
                            </span>
                          </div>
                          <div style={styles.metaItem}>
                            <span style={styles.metaIcon}>🕒</span>
                            <span style={styles.metaText}>
                              Last: {lastActivity}
                            </span>
                          </div>
                        </div>
                        <p style={styles.preview}>{lastMessage}</p>
                      </div>
                      <div style={styles.cardFooter}>
                        <button
                          style={{
                            ...styles.viewBtn,
                            ...(hoverStates.views[sessionId] &&
                              styles.viewBtnHover),
                          }}
                          onClick={() => handleViewSession(sessionId)}
                          onMouseEnter={() =>
                            updateHoverState("views", {
                              ...hoverStates.views,
                              [sessionId]: true,
                            })
                          }
                          onMouseLeave={() =>
                            updateHoverState("views", {
                              ...hoverStates.views,
                              [sessionId]: false,
                            })
                          }
                        >
                          View Session →
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </main>
      </div>

      {/* Enhanced CSS Animations */}
      <style>
        {`
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
          
          @keyframes fadeInUp {
            from {
              opacity: 0;
              transform: translateY(30px) scale(0.95);
            }
            to {
              opacity: 1;
              transform: translateY(0) scale(1);
            }
          }
          
          @keyframes pulse {
            0% { transform: scale(1); opacity: 0.7; }
            50% { transform: scale(1.1); opacity: 1; }
            100% { transform: scale(1); opacity: 0.7; }
          }
          
          @keyframes float {
            0% { transform: translateY(0px) rotate(0deg); }
            50% { transform: translateY(-10px) rotate(5deg); }
            100% { transform: translateY(0px) rotate(0deg); }
          }
          
          @keyframes glow {
            0% { box-shadow: 0 0 20px rgba(203, 226, 43, 0.3); }
            50% { box-shadow: 0 0 40px rgba(203, 226, 43, 0.6); }
            100% { box-shadow: 0 0 20px rgba(203, 226, 43, 0.3); }
          }
          
          @keyframes compassSpin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
          
          .analysis-card:hover {
            transform: translateY(-8px) scale(1.02);
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15);
          }
        `}
      </style>
    </div>
  );
}

const styles = {
  outerContainer: {
    minHeight: "100vh",
    background: "linear-gradient(135deg, #0f2b1d 0%, #1a3b2a 100%)",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    padding: "20px",
    fontFamily:
      "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  },
  container: {
    display: "flex",
    width: "100%",
    maxWidth: "1400px",
    minHeight: "850px",
    background: "#fff",
    borderRadius: "28px",
    overflow: "hidden",
    boxShadow: "0 30px 60px rgba(0, 0, 0, 0.3)",
  },
  leftPanel: {
    width: "35%",
    background: "linear-gradient(135deg, #013220 0%, #002817 100%)",
    color: "#fff",
    padding: "50px 40px",
    display: "flex",
    flexDirection: "column",
    justifyContent: "space-between",
    position: "relative",
    overflow: "hidden",
  },
  logoContainer: {
    textAlign: "center",
    marginBottom: "50px",
    position: "relative",
  },
  logo: {
    position: "relative",
    display: "inline-block",
    marginBottom: "20px",
  },
  logoIcon: {
    fontSize: "4rem",
    zIndex: 2,
    position: "relative",
    animation: "float 6s infinite ease-in-out",
  },
  logoGlow: {
    position: "absolute",
    top: "50%",
    left: "50%",
    transform: "translate(-50%, -50%)",
    width: "100px",
    height: "100px",
    borderRadius: "50%",
    background: "rgba(203, 226, 43, 0.1)",
    animation: "pulse 3s infinite ease-in-out",
    zIndex: 1,
  },
  logoText: {
    fontSize: "2.2rem",
    fontWeight: "800",
    color: "#cbe22b",
    margin: "0 0 8px 0",
    letterSpacing: "0.5px",
    background: "linear-gradient(135deg, #cbe22b 0%, #a8c91d 100%)",
    WebkitBackgroundClip: "text",
    WebkitTextFillColor: "transparent",
    backgroundClip: "text",
  },
  logoSubtitle: {
    fontSize: "0.9rem",
    color: "#d8f27b",
    opacity: 0.8,
    letterSpacing: "1px",
  },
  userSection: {
    textAlign: "center",
    marginBottom: "50px",
  },
  avatarContainer: {
    position: "relative",
    display: "inline-block",
    marginBottom: "25px",
  },
  avatar: {
    width: "80px",
    height: "80px",
    borderRadius: "50%",
    background: "linear-gradient(135deg, #cbe22b 0%, #a8c91d 100%)",
    color: "#013220",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "2rem",
    fontWeight: "bold",
    margin: "0 auto",
    boxShadow: "0 8px 25px rgba(0, 0, 0, 0.3)",
  },
  statusIndicator: {
    position: "absolute",
    bottom: "5px",
    right: "5px",
    width: "15px",
    height: "15px",
    borderRadius: "50%",
    background: "#10b981",
    border: "2px solid #013220",
  },
  welcomeTitle: {
    fontSize: "1.6rem",
    fontWeight: "600",
    margin: "0 0 12px 0",
    color: "#fff",
  },
  welcomeSubtitle: {
    fontSize: "1.1rem",
    color: "#d8f27b",
    lineHeight: "1.5",
    margin: 0,
    opacity: 0.9,
  },
  statsGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "20px",
    marginBottom: "50px",
  },
  statCard: {
    background: "rgba(203, 226, 43, 0.1)",
    borderRadius: "20px",
    padding: "25px",
    border: "1px solid rgba(203, 226, 43, 0.2)",
    textAlign: "center",
    backdropFilter: "blur(10px)",
    animation: "float 8s infinite ease-in-out",
  },
  statIcon: {
    fontSize: "2rem",
    marginBottom: "12px",
  },
  statContent: {
    display: "flex",
    flexDirection: "column",
    gap: "5px",
  },
  statNumber: {
    fontSize: "2.4rem",
    fontWeight: "800",
    color: "#cbe22b",
  },
  statLabel: {
    fontSize: "0.9rem",
    color: "#d8f27b",
    opacity: 0.9,
  },
  decoration: {
    position: "absolute",
    bottom: "40px",
    left: "40px",
    right: "40px",
    height: "150px",
    opacity: 0.3,
  },
  floatingOrb: {
    position: "absolute",
    width: "12px",
    height: "12px",
    borderRadius: "50%",
    background: "#cbe22b",
    animation: "pulse 4s infinite ease-in-out",
  },
  rightPanel: {
    width: "65%",
    padding: "50px",
    background: "#f8faf7",
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
  },
  header: {
    marginBottom: "40px",
  },
  headerContent: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  pageTitle: {
    fontSize: "2.2rem",
    fontWeight: "700",
    color: "#013220",
    margin: 0,
    background: "linear-gradient(135deg, #013220 0%, #004d2a 100%)",
    WebkitBackgroundClip: "text",
    WebkitTextFillColor: "transparent",
    backgroundClip: "text",
  },
  headerActions: {
    display: "flex",
    gap: "15px",
  },
  newAnalysisBtn: {
    background: "linear-gradient(135deg, #013220 0%, #004d2a 100%)",
    color: "#cbe22b",
    border: "none",
    padding: "16px 32px",
    borderRadius: "14px",
    fontWeight: "600",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    gap: "10px",
    transition: "all 0.3s ease",
    boxShadow: "0 6px 20px rgba(1, 50, 32, 0.25)",
    fontSize: "1rem",
  },
  newAnalysisBtnHover: {
    transform: "translateY(-3px)",
    boxShadow: "0 10px 30px rgba(1, 50, 32, 0.4)",
    animation: "glow 2s infinite",
  },
  plusIcon: {
    fontSize: "1.3rem",
  },
  searchSection: {
    marginBottom: "40px",
  },
  searchContainer: {
    display: "flex",
    flexDirection: "column",
    gap: "20px",
  },
  searchWrapper: {
    position: "relative",
    maxWidth: "600px",
  },
  searchIcon: {
    position: "absolute",
    left: "20px",
    top: "50%",
    transform: "translateY(-50%)",
    fontSize: "1.2rem",
    color: "#64748b",
  },
  searchInput: {
    width: "100%",
    padding: "18px 20px 18px 55px",
    border: "2px solid #e2e8f0",
    borderRadius: "14px",
    fontSize: "1.1rem",
    background: "#fff",
    outline: "none",
    transition: "all 0.3s ease",
    boxShadow: "0 4px 12px rgba(0, 0, 0, 0.08)",
  },
  tabContainer: {
    display: "flex",
    gap: "12px",
  },
  tabButton: {
    padding: "10px 20px",
    borderRadius: "10px",
    border: "2px solid #e2e8f0",
    background: "#fff",
    color: "#64748b",
    cursor: "pointer",
    transition: "all 0.3s ease",
    fontSize: "0.95rem",
    fontWeight: "500",
  },
  tabButtonActive: {
    background: "#013220",
    color: "#cbe22b",
    borderColor: "#013220",
    boxShadow: "0 4px 12px rgba(1, 50, 32, 0.2)",
  },
  content: {
    flex: 1,
    overflow: "hidden",
  },
  loadingState: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    height: "400px",
    color: "#64748b",
  },
  spinner: {
    width: "50px",
    height: "50px",
    border: "4px solid #e2e8f0",
    borderTop: "4px solid #013220",
    borderRadius: "50%",
    animation: "spin 1s linear infinite",
    marginBottom: "20px",
  },
  loadingText: {
    fontSize: "1.1rem",
    fontWeight: "500",
  },
  emptyState: {
    textAlign: "center",
    padding: "80px 20px",
    color: "#64748b",
  },
  emptyIcon: {
    marginBottom: "25px",
  },
  compassSpin: {
    fontSize: "5rem",
    animation: "compassSpin 8s linear infinite",
    display: "inline-block",
    opacity: 0.7,
  },
  emptyTitle: {
    fontSize: "1.6rem",
    fontWeight: "600",
    margin: "0 0 15px 0",
    color: "#334155",
  },
  emptyText: {
    fontSize: "1.1rem",
    maxWidth: "400px",
    margin: "0 auto 30px",
  },
  ctaButton: {
    background: "linear-gradient(135deg, #013220 0%, #004d2a 100%)",
    color: "#cbe22b",
    border: "none",
    padding: "15px 35px",
    borderRadius: "12px",
    fontWeight: "600",
    cursor: "pointer",
    transition: "all 0.3s ease",
    boxShadow: "0 6px 20px rgba(1, 50, 32, 0.25)",
    fontSize: "1.1rem",
  },
  ctaButtonHover: {
    transform: "translateY(-3px)",
    boxShadow: "0 10px 30px rgba(1, 50, 32, 0.4)",
  },
  analysesGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(350px, 1fr))",
    gap: "30px",
    maxHeight: "550px",
    overflowY: "auto",
    padding: "10px 15px",
  },
  analysisCard: {
    background: "#fff",
    borderRadius: "20px",
    padding: "25px",
    boxShadow: "0 8px 25px rgba(0, 0, 0, 0.1)",
    border: "1px solid #e2e8f0",
    transition: "all 0.3s ease",
    opacity: 0,
  },
  cardHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "20px",
  },
  cardBadge: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    padding: "6px 12px",
    background: "rgba(37, 99, 235, 0.1)",
    color: "#2563eb",
    borderRadius: "8px",
    fontSize: "0.85rem",
    fontWeight: "500",
  },
  badgeIcon: {
    fontSize: "0.9rem",
  },
  date: {
    fontSize: "0.9rem",
    color: "#64748b",
    fontWeight: "500",
  },
  cardContent: {
    marginBottom: "25px",
  },
  analysisTitle: {
    fontSize: "1.3rem",
    fontWeight: "600",
    color: "#013220",
    margin: "0 0 15px 0",
    lineHeight: "1.4",
  },
  sessionMeta: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
    marginBottom: "15px",
  },
  metaItem: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    fontSize: "0.95rem",
    color: "#475569",
  },
  metaIcon: {
    fontSize: "1rem",
  },
  metaText: {
    fontSize: "0.9rem",
  },
  preview: {
    fontSize: "1rem",
    color: "#64748b",
    lineHeight: "1.6",
    margin: 0,
    display: "-webkit-box",
    WebkitLineClamp: "3",
    WebkitBoxOrient: "vertical",
    overflow: "hidden",
  },
  cardFooter: {
    textAlign: "right",
  },
  viewBtn: {
    background: "transparent",
    color: "#013220",
    border: "2px solid #013220",
    padding: "10px 22px",
    borderRadius: "10px",
    fontSize: "1rem",
    fontWeight: "600",
    cursor: "pointer",
    transition: "all 0.3s ease",
    display: "inline-flex",
    alignItems: "center",
    gap: "8px",
  },
  viewBtnHover: {
    background: "#013220",
    color: "#cbe22b",
    transform: "translateX(5px)",
  },
  loading: {
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    minHeight: "100vh",
    fontSize: "1.3rem",
    color: "#64748b",
    fontWeight: "500",
  },
};

export default Dashboard;
