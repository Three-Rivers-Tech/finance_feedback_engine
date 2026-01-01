# Finance Feedback Engine - Frontend

A production-grade React + TypeScript frontend with **neo-brutalist terminal aesthetic** for the Finance Feedback Engine trading system.

![Tech Stack](https://img.shields.io/badge/React-19.2-blue) ![TypeScript](https://img.shields.io/badge/TypeScript-5.9-blue) ![Tailwind](https://img.shields.io/badge/Tailwind-3.4-blue) ![Vite](https://img.shields.io/badge/Vite-7.2-purple)

## Features

### Real-Time Dashboard
- **Portfolio Overview**: Live balance, unrealized P&L, position utilization
- **Positions Table**: Active positions with color-coded P&L (auto-refresh every 3s)
- **Recent Decisions**: Last 10 AI trading decisions with reasoning

### Agent Control Panel
- **Agent Status**: Live state monitoring (IDLE/REASONING/EXECUTION/etc.)
- **Controls**: Start/Stop/Emergency Stop buttons
- **Circuit Breakers**: Real-time circuit breaker state indicators
- **Config Editor**: Live configuration updates (coming soon)

### Performance Analytics
- **Embedded Grafana**: Full trading metrics dashboard with auto-refresh
- **8 Visualization Panels**:
  - Portfolio Value Over Time
  - Active Positions Gauge
  - Agent State Indicator
  - Trade P&L Distribution
  - Decisions by Action (Pie Chart)
  - Decision Latency by Provider
  - Circuit Breaker States
  - Win Rate Gauge (24h)

## Tech Stack

- **Framework**: React 19.2 + TypeScript 5.9
- **Build Tool**: Vite 7.2 (fast dev server, HMR)
- **Routing**: React Router v6
- **State**: Zustand (lightweight, persistent auth)
- **API**: Axios with interceptors
- **Styling**: Tailwind CSS (neo-brutalist design system)
- **Forms**: React Hook Form + Zod validation
- **Date**: date-fns
- **Utilities**: clsx

## Design System

**Neo-Brutalist Terminal Aesthetic**

### Color Palette
- Background: `#0A0E14` (deep dark blue-black)
- Surface: `#151A21` (elevated panels)
- Border: `#2D3748` (3px thick borders)
- Accent: `#00D9FF` (cyan - primary actions)
- Success: `#10B981` (green - profitable trades)
- Danger: `#FF3E3E` (red - losses/emergency)
- Warning: `#FFB020` (amber - warnings)

### Typography
- **Primary**: IBM Plex Mono (monospace for data/numbers)
- **Secondary**: Inter (UI labels)

### Principles
- High contrast for readability
- Thick 3px borders, minimal rounded corners
- Monospace fonts for perfect number alignment
- Grid-based layouts
- Data-dense but not overwhelming

## Quick Start

### Prerequisites

1. **Backend API** must be running on `http://localhost:8000`
2. **Grafana + Prometheus** stack running (see root `observability/` folder)

### Installation

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Create environment file
cp .env.example .env

# Start development server
npm run dev
```

The app will be available at **http://localhost:5173**

### Environment Variables

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_GRAFANA_URL=http://localhost:3001
VITE_POLLING_INTERVAL_CRITICAL=3000  # 3s for positions/agent status
VITE_POLLING_INTERVAL_MEDIUM=5000    # 5s for portfolio/decisions
```

## Complete Setup (All Services)

To run the entire stack:

```bash
# Terminal 1: Start Grafana + Prometheus
docker-compose up -d

# Terminal 2: Start Backend API
source .venv/bin/activate
uvicorn finance_feedback_engine.api.app:app --reload --port 8000

# Terminal 3: Start Frontend
cd frontend
npm run dev
```

**Access Points:**
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- Grafana: http://localhost:3001 ⚠️ **Default credentials: admin/admin** — Change immediately before shared/production use (see [Grafana Admin docs](https://grafana.com/docs/grafana/latest/manage-users/server-admin/)), or set via provisioning in `docker-compose.yml`: `GF_SECURITY_ADMIN_PASSWORD=<new_password>`
- Prometheus: http://localhost:9090

## Project Structure

```
frontend/
├── src/
│   ├── api/
│   │   ├── client.ts              # Axios instance with auth
│   │   ├── types.ts               # TypeScript interfaces
│   │   └── hooks/
│   │       ├── useAgentStatus.ts  # Poll /api/v1/bot/status (3s)
│   │       ├── usePortfolio.ts    # Poll /api/v1/status (5s)
│   │       ├── usePositions.ts    # Poll /api/v1/bot/positions (3s)
│   │       ├── useDecisions.ts    # Poll /api/v1/decisions (5s)
│   │       └── useHealth.ts       # Poll /health (5s)
│   ├── components/
│   │   ├── common/
│   │   │   ├── Button.tsx         # Brutalist styled buttons
│   │   │   ├── Card.tsx           # Bordered panel container
│   │   │   ├── MetricCard.tsx     # Reusable metric display
│   │   │   ├── Badge.tsx          # Status badges
│   │   │   └── Spinner.tsx        # Loading indicator
│   │   ├── layout/
│   │   │   ├── AppLayout.tsx      # Main layout with sidebar
│   │   │   ├── Sidebar.tsx        # Navigation
│   │   │   └── Header.tsx         # API status indicator
│   │   ├── dashboard/
│   │   │   ├── PortfolioOverview.tsx  # Balance, P&L cards
│   │   │   ├── PositionsTable.tsx     # Active positions
│   │   │   └── RecentDecisions.tsx    # Last 10 AI decisions
│   │   └── agent/
│   │       ├── AgentStatusDisplay.tsx  # Live agent state
│   │       ├── AgentControlPanel.tsx   # Start/Stop controls
│   │       └── CircuitBreakerStatus.tsx # Breaker states
│   ├── stores/
│   │   └── authStore.ts           # API key storage (Zustand)
│   ├── services/
│   │   └── formatters.ts          # Number/currency/date formatters
│   ├── pages/
│   │   ├── Dashboard.tsx          # Main dashboard
│   │   ├── AgentControl.tsx       # Agent control page
│   │   └── Analytics.tsx          # Embedded Grafana
│   ├── utils/
│   │   └── constants.ts           # App constants
│   ├── App.tsx                    # Root with routing
│   └── main.tsx                   # Vite entry point
├── .env                           # Environment variables
├── package.json                   # Dependencies
├── tailwind.config.js             # Brutalist design tokens
├── vite.config.ts                 # Vite config with proxy
└── README.md
```

## API Integration

The frontend connects to the Finance Feedback Engine API:

**Key Endpoints:**
- `GET /health` - System health & circuit breakers
- `GET /api/v1/status` - Portfolio status (balance, positions)
- `GET /api/v1/decisions?limit=10` - Recent AI decisions
- `GET /api/v1/bot/status` - Agent state & performance
- `GET /api/v1/bot/positions` - Open positions with P&L
- `POST /api/v1/bot/start` - Start autonomous agent
- `POST /api/v1/bot/stop` - Stop agent gracefully
- `POST /api/v1/bot/emergency-stop` - Emergency halt + close positions

**Authentication:**
- API Key stored in localStorage (persistent across sessions)
- Auto-added to all requests via Axios interceptor
- 401 errors trigger re-authentication

**Polling Strategy:**
- **Critical data** (3s): Agent status, positions (real-time monitoring)
- **Medium data** (5s): Portfolio balance, decisions, health checks
- Polling pauses when tab is inactive (performance optimization)

## Building for Production

```bash
# Type check
npm run type-check

# Build
npm run build

# Preview production build
npm run preview
```

Build output: `dist/` directory

**Docker Deployment:**
```bash
# Build Docker image (from repository root)
docker build -t finance-feedback-engine-frontend:latest -f frontend/Dockerfile frontend/

# Or using docker-compose
docker-compose build frontend
```

**Important Notes:**
- The Dockerfile uses `frontend/` as the build context for self-contained builds
- `nginx.conf` is copied from the parent `docker/nginx.conf` directory for consistency
- When using docker-compose, the `docker/nginx.conf` is mounted as a volume for development convenience
- Keep `docker/nginx.conf` as the source of truth; copy changes to `frontend/nginx.conf` when needed

**Static Hosting Deployment:**
- Serve with nginx, Vercel, Netlify, or any static host
- Configure nginx reverse proxy to backend API
- Update `VITE_API_BASE_URL` to production API URL

## Development

### Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint
- `npm run type-check` - TypeScript type checking

### Adding New Features

1. **New API Endpoint**: Add to `src/api/hooks/`
2. **New Component**: Use brutalist design tokens from `tailwind.config.js`
3. **New Page**: Create in `src/pages/` and add route to `App.tsx`

### Styling Guidelines

- Use Tailwind utility classes
- Reference design tokens: `bg-bg-primary`, `text-accent-cyan`, `border-3`
- Monospace font for data/numbers: `font-mono`
- High contrast for accessibility
- 3px borders for brutalist aesthetic

## Troubleshooting

**"Network error: API is unreachable"**
- Ensure backend is running on port 8000
- Check Vite proxy config in `vite.config.ts`

**"No data in Grafana dashboard"**
- Start Grafana/Prometheus: `docker-compose up -d`
- Verify backend metrics endpoint: http://localhost:8000/metrics
- Check Prometheus targets: http://localhost:9090/targets

**"Agent status unavailable"**
- Backend API must be running
- Check API key is set (localStorage: `api_key`)
- Verify `/api/v1/bot/status` endpoint responds

**Polling not working**
- Check browser console for errors
- Verify API endpoints return valid JSON
- Ensure API CORS allows `localhost:5173`

## License

Part of the Finance Feedback Engine project.
