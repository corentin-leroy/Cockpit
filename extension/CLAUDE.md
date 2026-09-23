# Extension Chrome (Manifest V3)

## Sécurité — non négociable
- L'URL de l'API est figée dans `api.js` et dans `host_permissions`.
  N'ajoute jamais de page d'options ni de champ permettant de la configurer :
  une URL modifiable serait un canal d'exfiltration du token d'authentification.
- Pour le dev local, la bascule d'URL est manuelle et ne doit jamais être committée.

## Design tokens — synchronisation manuelle
- Le bloc `<style>` de `popup.html` duplique volontairement les tokens de `tokens.css`
  (couleurs des deux thèmes, espacements, rayons, typo).
- Deux sélecteurs seulement : `:root` pour le thème clair, et une media query
  `prefers-color-scheme: dark`. La popup n'a pas de bascule de thème manuelle.
- Toute modification de la palette dans `tokens.css` doit être reportée ici dans la même
  passe. Signale-le-moi explicitement quand tu touches aux couleurs.

## Messages de la popup
- Un seul conteneur, `<p id="message">`, présent dans le HTML initial et partagé entre
  succès, erreur et messages neutres. Le type est porté par `className`.
- Il porte `role="status"` et `aria-atomic="true"` : ne les retire pas, ne crée pas de
  second conteneur.
- Aucun emoji dans les chaînes de `popup.js` : le pictogramme d'état vient uniquement
  du CSS (`::before`).

## Comportements volontaires — ne pas « corriger »
- La popup se ferme automatiquement 900 ms après un ajout réussi. C'est un choix assumé :
  la fermeture fait elle-même office de confirmation.
- Les messages d'erreur n'ont pas de timer et restent affichés sans limite de temps.