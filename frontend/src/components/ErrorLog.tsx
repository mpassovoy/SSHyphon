type Props = {
  lines: string[];
};

export function ErrorLog({ lines }: Props) {
  return (
    <div className="card">
      <h2>Error Log</h2>
      <div className="error-log">
        {lines.length === 0 && <p className="muted">No errors recorded 🎉</p>}
        {lines.map((line, index) => (
          <p key={`${line}-${index}`}>{line}</p>
        ))}
      </div>
    </div>
  );
}

