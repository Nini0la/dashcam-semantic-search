const ROAD_LABELS = [
  "good road",
  "fair road",
  "poor road",
  "pothole",
  "flooding",
  "obstruction",
  "false match",
];

export default function ResultCard({ result, onOpen, onLabel }) {
  return (
    <article className="result-card">
      <button className="thumbnail" onClick={() => onOpen(result)}>
        {result.image_path ? (
          <img src={result.image_path} alt="" />
        ) : (
          <span>{formatTime(result.timestamp_seconds)}</span>
        )}
      </button>
      <div className="result-body">
        <div className="result-title">
          <h3>{result.blob_name}</h3>
          <span className="score">{Math.round(result.score * 100)}%</span>
        </div>
        <p className="timestamp">{formatTime(result.timestamp_seconds)}</p>
        <TagGroup title="Labels" values={result.labels} />
        <TagGroup title="Objects" values={result.objects} />
        {result.user_labels.length > 0 && <TagGroup title="Manual" values={result.user_labels} />}
        <div className="card-actions">
          <button onClick={() => onOpen(result)}>Open at timestamp</button>
          <a href={`${result.blob_url}#t=${Math.floor(result.timestamp_seconds)}`} target="_blank">
            New tab
          </a>
        </div>
        <div className="label-buttons">
          {ROAD_LABELS.map((label) => (
            <button key={label} onClick={() => onLabel(result.frame_id, label)}>
              {label}
            </button>
          ))}
        </div>
      </div>
    </article>
  );
}

function TagGroup({ title, values }) {
  if (!values?.length) return null;
  return (
    <div className="tag-group">
      <span>{title}</span>
      {values.map((value) => (
        <em key={value}>{value}</em>
      ))}
    </div>
  );
}

function formatTime(seconds) {
  const total = Math.max(0, Math.floor(seconds || 0));
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  return `${mins}:${String(secs).padStart(2, "0")}`;
}
