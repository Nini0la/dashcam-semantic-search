export default function DetailPanel({ video, result }) {
  const source = result?.blob_url || video?.blob_url;
  const timestamp = result?.timestamp_seconds || 0;

  return (
    <aside className="detail-panel">
      <h2>Details</h2>
      {!video && !result ? (
        <p className="muted">Select a video or search result.</p>
      ) : (
        <>
          <div className="player-shell">
            {source ? (
              <video key={`${source}-${timestamp}`} src={`${source}#t=${Math.floor(timestamp)}`} controls />
            ) : (
              <div className="empty-player">No playable source</div>
            )}
          </div>
          <dl>
            <dt>File</dt>
            <dd>{result?.blob_name || video?.blob_name}</dd>
            <dt>Status</dt>
            <dd>{video?.status || "indexed"}</dd>
            <dt>Timestamp</dt>
            <dd>{Math.floor(timestamp)}s</dd>
            <dt>Duration</dt>
            <dd>{video?.duration ? `${Math.round(video.duration)}s` : "Unknown"}</dd>
          </dl>
          {video?.frames?.length > 0 && (
            <div className="frame-list">
              <h3>Indexed Frames</h3>
              {video.frames.map((frame) => (
                <div key={frame.id}>
                  <strong>{Math.floor(frame.timestamp_seconds)}s</strong>
                  <span>{[...frame.labels, ...frame.objects].join(", ")}</span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </aside>
  );
}
