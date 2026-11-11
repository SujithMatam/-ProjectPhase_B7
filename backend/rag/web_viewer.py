import http.server
import socketserver
import json
import chromadb
from pathlib import Path

CHROMA_DIR = Path(__file__).resolve().parent / "data" / "chroma_db"
COLLECTION_NAME = "orthosync_clinical_knowledge"
PORT = 8080

class ChromaViewerHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            
            client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            collection = client.get_collection(name=COLLECTION_NAME)
            results = collection.get(include=["metadatas", "documents"])
            
            ids = results.get("ids", [])
            docs = results.get("documents", [])
            metas = results.get("metadatas", [])
            
            cards_html = ""
            for i, (doc_id, doc_text, meta) in enumerate(zip(ids, docs, metas), 1):
                procedure = meta.get("procedure", "All")
                badge_class = "badge-tka" if procedure == "TKA" else ("badge-tha" if procedure == "THA" else "badge-all")
                topic = meta.get("topic", "Clinical Guideline")
                days = meta.get("days", "1-30")
                keywords = meta.get("keywords", "")
                
                cards_html += f"""
                <div class="card">
                    <div class="card-header">
                        <span class="badge {badge_class}">{procedure}</span>
                        <span class="card-id">{doc_id}</span>
                        <span class="badge badge-days">Days: {days}</span>
                    </div>
                    <h3 class="card-title">{topic}</h3>
                    <p class="card-content">{doc_text}</p>
                    <div class="card-footer">
                        <strong>Keywords:</strong> <code>{keywords}</code>
                    </div>
                </div>
                """
            
            html = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>ChromaDB Visual Explorer - OrthoSync</title>
                <link rel="preconnect" href="https://fonts.googleapis.com">
                <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
                <style>
                    :root {{
                        --bg: #0b0f19;
                        --card-bg: rgba(22, 30, 49, 0.85);
                        --card-border: rgba(255, 255, 255, 0.08);
                        --text-primary: #f3f4f6;
                        --text-secondary: #9ca3af;
                        --accent: #3b82f6;
                        --tka: #10b981;
                        --tha: #f59e0b;
                        --all: #8b5cf6;
                    }}
                    body {{
                        margin: 0;
                        padding: 2rem;
                        background: radial-gradient(circle at top right, #1e293b, #0b0f19);
                        font-family: 'Inter', sans-serif;
                        color: var(--text-primary);
                        min-height: 100vh;
                    }}
                    .container {{
                        max-width: 1100px;
                        margin: 0 auto;
                    }}
                    header {{
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                        margin-bottom: 2rem;
                        padding-bottom: 1.5rem;
                        border-bottom: 1px solid var(--card-border);
                    }}
                    .brand {{
                        display: flex;
                        align-items: center;
                        gap: 12px;
                    }}
                    .logo-icon {{
                        width: 36px;
                        height: 36px;
                        background: linear-gradient(135deg, #3b82f6, #8b5cf6);
                        border-radius: 8px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-weight: 700;
                    }}
                    h1 {{
                        font-size: 1.5rem;
                        margin: 0;
                    }}
                    .stats {{
                        background: var(--card-bg);
                        border: 1px solid var(--card-border);
                        padding: 8px 16px;
                        border-radius: 20px;
                        font-size: 0.9rem;
                    }}
                    .grid {{
                        display: grid;
                        grid-template-columns: repeat(auto-fill, minmax(480px, 1fr));
                        gap: 1.5rem;
                    }}
                    .card {{
                        background: var(--card-bg);
                        border: 1px solid var(--card-border);
                        border-radius: 12px;
                        padding: 1.5rem;
                        backdrop-filter: blur(12px);
                        transition: transform 0.2s, border-color 0.2s;
                    }}
                    .card:hover {{
                        transform: translateY(-2px);
                        border-color: rgba(59, 130, 246, 0.4);
                    }}
                    .card-header {{
                        display: flex;
                        align-items: center;
                        gap: 8px;
                        margin-bottom: 0.8rem;
                    }}
                    .card-id {{
                        font-family: monospace;
                        color: var(--text-secondary);
                        font-size: 0.85rem;
                    }}
                    .badge {{
                        padding: 3px 8px;
                        border-radius: 6px;
                        font-size: 0.75rem;
                        font-weight: 600;
                    }}
                    .badge-tka {{ background: rgba(16, 185, 129, 0.15); color: #34d399; }}
                    .badge-tha {{ background: rgba(245, 158, 11, 0.15); color: #fbbf24; }}
                    .badge-all {{ background: rgba(139, 92, 246, 0.15); color: #a78bfa; }}
                    .badge-days {{ background: rgba(255, 255, 255, 0.08); color: var(--text-secondary); margin-left: auto; }}
                    .card-title {{
                        font-size: 1.15rem;
                        margin: 0 0 0.8rem 0;
                        color: #ffffff;
                    }}
                    .card-content {{
                        font-size: 0.95rem;
                        line-height: 1.6;
                        color: #d1d5db;
                        margin: 0 0 1rem 0;
                    }}
                    .card-footer {{
                        font-size: 0.8rem;
                        color: var(--text-secondary);
                        border-top: 1px solid var(--card-border);
                        padding-top: 0.8rem;
                    }}
                    code {{
                        color: #93c5fd;
                        font-family: monospace;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <header>
                        <div class="brand">
                            <div class="logo-icon">C</div>
                            <div>
                                <h1>ChromaDB Vector Explorer</h1>
                                <span style="font-size: 0.85rem; color: var(--text-secondary);">Collection: {COLLECTION_NAME}</span>
                            </div>
                        </div>
                        <div class="stats">
                            Indexed Vectors: <strong>{len(ids)}</strong>
                        </div>
                    </header>
                    <div class="grid">
                        {cards_html}
                    </div>
                </div>
            </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_error(404)

def run_web_viewer():
    server = socketserver.TCPServer(("", PORT), ChromaViewerHandler)
    print(f"[*] Visual ChromaDB Explorer running at: http://localhost:{PORT}")
    server.serve_forever()

if __name__ == "__main__":
    run_web_viewer()
