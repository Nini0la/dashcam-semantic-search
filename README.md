# Dashcam Semantic Search Console

MVP web app for discovering dashcam videos from Azure Blob Storage, submitting them to Azure AI Video Indexer, storing insights/keyframe metadata in SQLite, and searching the library with natural language.

The app also runs without Azure credentials. In demo mode it seeds fake dashcam videos, fake Video Indexer insights, frame metadata, and local deterministic embeddings so the UI can be tested immediately.

## Project Structure

```text
dashcam-semantic-search/
  backend/
    app/
      main.py
      config.py
      db.py
      models.py
      azure_blob.py
      video_indexer.py
      embeddings.py
      search.py
      schemas.py
    requirements.txt
    .env.example
  frontend/
    package.json
    src/
      App.jsx
      components/
        SearchBar.jsx
        VideoList.jsx
        ResultCard.jsx
        DetailPanel.jsx
```

## Run Locally

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## Demo Flow

If Azure settings are blank, the backend automatically uses demo mode:

1. Click `Discover`.
2. Click `Index`.
3. Search for terms like `bad road`, `motorcycle`, `heavy traffic`, `street market`, `truck`, or `intersection`.
4. Label result frames as `good road`, `fair road`, `poor road`, `pothole`, `flooding`, `obstruction`, or `false match`.

## Azure Configuration

Set these in `backend/.env`:

```bash
AZURE_STORAGE_CONNECTION_STRING=
AZURE_BLOB_CONTAINER_NAME=
VIDEO_INDEXER_ACCOUNT_ID=
VIDEO_INDEXER_LOCATION=
VIDEO_INDEXER_API_KEY=
VIDEO_INDEXER_ACCOUNT_NAME=
DEMO_MODE=false
DATABASE_URL=sqlite:///./dashcam.db
```

Blob discovery lists video files from the configured container and creates read SAS URLs when the connection string exposes an account key. Video indexing submits those URLs to Azure AI Video Indexer.

The Video Indexer API wrapper includes TODO comments for account-specific parameters and response-state normalization. Confirm those against your Azure AI Video Indexer account before production use.

## API

- `GET /videos`
- `POST /videos/discover`
- `POST /videos/index`
- `GET /videos/{video_id}`
- `GET /videos/{video_id}/status`
- `POST /videos/{video_id}/refresh-insights`
- `POST /search`
- `POST /frames/{frame_id}/label`

## Search

Search embeds the query with the current embedding provider, compares it to stored frame embeddings with cosine similarity, and also applies keyword fallback over frame metadata, labels, objects, manual labels, and raw insight-derived text.

The default provider is a deterministic local hash embedding. Replace `HashEmbeddingProvider` in `backend/app/embeddings.py` with CLIP or another provider when ready.

## Database

SQLite is used for the MVP and initialized automatically on backend startup. The repository keeps all SQL access in `backend/app/db.py` and `backend/app/search.py` so a later Postgres migration can replace those data access functions without changing the frontend or API shapes.
