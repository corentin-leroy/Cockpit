// Styles inline partagés par les écrans d'authentification. Volontairement
// sobres (on raffinera le design plus tard) ; réutilisent les variables CSS
// définies dans index.css pour rester cohérents avec le thème clair/sombre.

export const styles = {
  page: {
    maxWidth: 360,
    margin: '64px auto',
    padding: '0 16px',
    textAlign: 'left',
  },
  card: {
    border: '1px solid var(--border)',
    borderRadius: 12,
    padding: 24,
    background: 'var(--bg)',
  },
  title: { marginTop: 0, marginBottom: 20 },
  field: { display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 16 },
  label: { fontSize: 14, color: 'var(--text-h)' },
  input: {
    padding: '10px 12px',
    borderRadius: 8,
    border: '1px solid var(--border)',
    background: 'transparent',
    color: 'inherit',
    font: 'inherit',
  },
  button: {
    width: '100%',
    padding: '10px 12px',
    borderRadius: 8,
    border: '1px solid var(--accent-border)',
    background: 'var(--accent-bg)',
    color: 'var(--text-h)',
    font: 'inherit',
    cursor: 'pointer',
  },
  buttonDisabled: { opacity: 0.6, cursor: 'not-allowed' },
  formError: {
    color: '#d33',
    fontSize: 14,
    marginBottom: 16,
    padding: '8px 12px',
    borderRadius: 8,
    background: 'rgba(221, 51, 51, 0.08)',
  },
  fieldError: { color: '#d33', fontSize: 13 },
  footer: { marginTop: 16, fontSize: 14 },
}
