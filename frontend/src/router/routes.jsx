import { Routes, Route } from 'react-router-dom'

// Routing minimal de démonstration : juste de quoi vérifier que React Router
// fonctionne. Les vrais écrans (Login, Register, Board) remplaceront ces
// textes à l'étape suivante.
export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<p>Accueil — squelette React OK ✅</p>} />
      <Route path="/login" element={<p>Login — squelette React OK ✅</p>} />
    </Routes>
  )
}
