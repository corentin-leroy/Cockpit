import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import { AuthProvider } from './auth/AuthContext.jsx'
import { ThemeProvider } from './theme/ThemeProvider.jsx'
import { initTheme } from './theme/theme.js'
import AppRoutes from './router/routes.jsx'

// Applique le thème (choix mémorisé, sinon préférence système) AVANT le premier
// rendu : évite un flash du mauvais thème.
initTheme()

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ThemeProvider>
      <BrowserRouter>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  </StrictMode>,
)
