# MetalGPT

AI-powered metal casting optimization system with conversational interface.

## Features

- 🤖 **AI Chat Interface**: Natural language interaction for casting design
- 📐 **STEP File Import**: Upload CAD models directly
- 🔥 **Automated Riser Design**: AI places and optimizes risers automatically
- ⚙️ **Casting Simulation**: FDM-based solidification analysis
- 🌐 **Web-Based**: Runs entirely in browser with 3D visualization

## Quick Start

```bash
# Backend
cd backend
pip install -r requirements.txt
python main.py

# Frontend (new terminal)
cd frontend
python -m http.server 8080

# Open http://localhost:8080 in browser
```

## Architecture

```
metalGPT/
├── backend/          # FastAPI + WebSocket server
│   ├── main.py       # Entry point
│   ├── casting/      # FDM solver + optimization
│   ├── chat/         # AI chat handler
│   └── models/       # ML models
├── frontend/         # Vanilla JS + Three.js
│   ├── index.html    # Main UI
│   ├── app.js        # Application logic
│   └── viewer.js     # 3D CAD viewer
└── models/           # Trained models
```

## Chat Commands

- "Upload a STEP file" - Import CAD model
- "Analyze this casting" - Run geometric analysis
- "Optimize for aluminum A356" - Set material + optimize
- "Add risers automatically" - AI places risers
- "Run simulation" - Execute FDM analysis
- "Show me the results" - Display defect predictions

## License

MIT
