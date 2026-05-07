export default function HomePage() {
  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "system-ui, sans-serif",
        gap: "1rem",
      }}
    >
      <h1>MailFlow</h1>
      <p>Open source AI email assistant &mdash; coming soon</p>
      <p style={{ fontSize: "0.875rem", color: "#888" }}>
        Use any LLM &bull; Self-hostable &bull; AGPL
      </p>
    </main>
  );
}
