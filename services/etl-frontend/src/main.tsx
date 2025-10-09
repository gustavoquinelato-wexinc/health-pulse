import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'
import { etlWebSocketService } from './services/websocketService'

// Initialize service-to-service WebSocket communication immediately on service startup
// This should happen when the ETL frontend service starts, not when user accesses the page
etlWebSocketService.initializeService()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
