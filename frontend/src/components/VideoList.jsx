import { RefreshCw, UploadCloud } from "lucide-react";

export default function VideoList({
  videos,
  selectedVideoId,
  onSelectVideo,
  onDiscover,
  onIndex,
  loading,
}) {
  return (
    <section className="video-list">
      <div className="section-heading">
        <h2>Blob Videos</h2>
        <div className="actions">
          <button onClick={onDiscover} disabled={loading} title="Discover Azure Blob videos">
            <RefreshCw size={16} />
            Discover
          </button>
          <button onClick={onIndex} disabled={loading || videos.length === 0} title="Index videos">
            <UploadCloud size={16} />
            Index
          </button>
        </div>
      </div>
      <div className="video-items">
        {videos.length === 0 ? (
          <p className="muted">No videos yet. Discover blobs to seed the library.</p>
        ) : (
          videos.map((video) => (
            <button
              key={video.id}
              className={`video-row ${selectedVideoId === video.id ? "selected" : ""}`}
              onClick={() => onSelectVideo(video.id)}
            >
              <span>{video.blob_name}</span>
              <strong className={`status ${video.status}`}>{video.status}</strong>
            </button>
          ))
        )}
      </div>
    </section>
  );
}
