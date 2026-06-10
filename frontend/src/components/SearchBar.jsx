import { Search } from "lucide-react";

export default function SearchBar({ query, setQuery, onSearch, loading }) {
  return (
    <form className="search-bar" onSubmit={onSearch}>
      <Search size={20} aria-hidden="true" />
      <input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder='Search: "bad road", "motorcycle", "heavy traffic"...'
      />
      <button type="submit" disabled={loading}>
        {loading ? "Searching" : "Search"}
      </button>
    </form>
  );
}
