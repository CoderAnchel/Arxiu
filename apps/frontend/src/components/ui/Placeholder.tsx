/** Generic placeholder for pages not yet wired in this phase. */
export function Placeholder({ title, description }: { title: string; description: string }) {
  return (
    <div style={{ padding: "32px 32px 0", maxWidth: 720 }}>
      <p
        style={{
          margin: "0 0 6px",
          fontFamily: "var(--mono)",
          fontSize: 10.5,
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          color: "var(--ink-3)",
        }}
      >
        Properament
      </p>
      <h1
        style={{
          margin: "0 0 8px",
          fontFamily: "var(--serif)",
          fontStyle: "italic",
          fontSize: 32,
          letterSpacing: "-0.01em",
        }}
      >
        {title}
      </h1>
      <p style={{ margin: 0, color: "var(--ink-2)", lineHeight: 1.55 }}>{description}</p>
    </div>
  );
}
