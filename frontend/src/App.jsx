import { useEffect, useMemo, useState } from "react";
import DetailPanel from "./components/DetailPanel.jsx";
import ResultCard from "./components/ResultCard.jsx";
import SearchBar from "./components/SearchBar.jsx";
import VideoList from "./components/VideoList.jsx";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export default function App() {
  const [videos, setVideos] = useState([]);
  const [selectedVideo, setSelectedVideo] = useState(null);
  const [selectedResult, setSelectedResult] = useState(null);
  const [results, setResults] = useState([]);
  const [query, setQuery] = useState("bad road");
  const [filters, setFilters] = useState({
    status: "",
    detected_object: "",
    road_quality_label: "",
    min_score: 0,
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    loadVideos();
  }, []);

  const detectedObjects = useMemo(() => {
    const objects = new Set();
    results.forEach((result) => result.objects.forEach((object) => objects.add(object)));
    return [...objects].sort();
  }, [results]);

  async function api(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `Request failed: ${response.status}`);
    }
    return response.json();
  }

  async function loadVideos() {
    const data = await api("/videos");
    setVideos(data);
  }

  async function discover() {
    await run("Discovered videos", async () => {
      const data = await api("/videos/discover", { method: "POST" });
      setVideos(data.videos);
      return `${data.discovered} videos discovered${data.demo_mode ? " in demo mode" : ""}.`;
    });
  }

  async function indexVideos() {
    await run("Indexing started", async () => {
      const data = await api("/videos/index", { method: "POST" });
      setVideos(data.videos);
      await search({ preventDefault: () => {} });
      return data.demo_mode
        ? `${data.completed} demo videos indexed.`
        : `${data.submitted} videos submitted to Azure AI Video Indexer.`;
    });
  }

  async function selectVideo(videoId) {
    await run("", async () => {
      const data = await api(`/videos/${videoId}`);
      setSelectedVideo(data);
      setSelectedResult(null);
      return "";
    });
  }

  async function search(event) {
    event.preventDefault();
    await run("Search complete", async () => {
      const data = await api("/search", {
        method: "POST",
        body: JSON.stringify({
          query,
          ...filters,
          status: filters.status || null,
          detected_object: filters.detected_object || null,
          road_quality_label: filters.road_quality_label || null,
          min_score: Number(filters.min_score),
          limit: 20,
        }),
      });
      setResults(data.results);
      return `${data.results.length} results.`;
    });
  }

  async function labelFrame(frameId, value) {
    await run("Label saved", async () => {
      await api(`/frames/${frameId}/label`, {
        method: "POST",
        body: JSON.stringify({ label_type: "road_quality", value }),
      });
      await search({ preventDefault: () => {} });
      return `Marked as ${value}.`;
    });
  }

  async function run(prefix, action) {
    setLoading(true);
    setMessage("");
    try {
      const detail = await action();
      setMessage([prefix, detail].filter(Boolean).join(": "));
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  function updateFilter(key, value) {
    setFilters((current) => ({ ...current, [key]: value }));
  }

  return (
    <main className="app-shell">
      <header>
        <div>
          <p>Dashcam Semantic Search Console</p>
          <h1>Find road scenes with natural language.</h1>
        </div>
      </header>

      <SearchBar query={query} setQuery={setQuery} onSearch={search} loading={loading} />
      {message && <p className="message">{message}</p>}

      <div className="workspace">
        <aside className="sidebar">
          <VideoList
            videos={videos}
            selectedVideoId={selectedVideo?.id}
            onSelectVideo={selectVideo}
            onDiscover={discover}
            onIndex={indexVideos}
            loading={loading}
          />

          <section className="filters">
            <h2>Filters</h2>
            <label>
              Status
              <select value={filters.status} onChange={(event) => updateFilter("status", event.target.value)}>
                <option value="">Any</option>
                <option value="discovered">Discovered</option>
                <option value="submitted">Submitted</option>
                <option value="indexing">Indexing</option>
                <option value="completed">Completed</option>
                <option value="failed">Failed</option>
              </select>
            </label>
            <label>
              Detected object
              <select
                value={filters.detected_object}
                onChange={(event) => updateFilter("detected_object", event.target.value)}
              >
                <option value="">Any</option>
                {detectedObjects.map((object) => (
                  <option key={object} value={object}>
                    {object}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Road label
              <select
                value={filters.road_quality_label}
                onChange={(event) => updateFilter("road_quality_label", event.target.value)}
              >
                <option value="">Any</option>
                <option value="good road">Good road</option>
                <option value="fair road">Fair road</option>
                <option value="poor road">Poor road</option>
                <option value="pothole">Pothole</option>
                <option value="flooding">Flooding</option>
                <option value="obstruction">Obstruction</option>
                <option value="false match">False match</option>
              </select>
            </label>
            <label>
              Similarity threshold: {filters.min_score}
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={filters.min_score}
                onChange={(event) => updateFilter("min_score", event.target.value)}
              />
            </label>
          </section>
        </aside>

        <section className="results">
          <div className="section-heading">
            <h2>Results</h2>
            <span>{results.length} matches</span>
          </div>
          {results.length === 0 ? (
            <div className="empty-state">
              Discover and index videos, then search for scenes like motorcycle, truck, or bad road.
            </div>
          ) : (
            results.map((result) => (
              <ResultCard
                key={result.frame_id}
                result={result}
                onOpen={(item) => {
                  setSelectedResult(item);
                  setSelectedVideo(videos.find((video) => video.id === item.video_id) || null);
                }}
                onLabel={labelFrame}
              />
            ))
          )}
        </section>

        <DetailPanel video={selectedVideo} result={selectedResult} />
      </div>
    </main>
  );
}
