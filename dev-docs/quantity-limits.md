# Limites de quantité (garde-fous anti-abus)
- Toutes les constantes sont dans `app/limits.py` (source unique, importée par
  les routers et par main.py) :
  - MAX_BOARDS_PER_USER = 10
  - MAX_APPLICATIONS_PER_USER = 300 (candidatures ACTIVES seulement, cf.
    « Archivage des candidatures »)
  - MAX_ARCHIVED_APPLICATIONS_PER_USER = 2000 (cf. même section)
  - MAX_REQUEST_BODY_BYTES = 1 Mo
- Vérifiées CÔTÉ SERVEUR à la création, jamais côté front : le front peut les
  afficher pour l'UX mais ne fait pas autorité (extension, curl… restent
  plafonnés). Dépassement → 409, et RIEN n'est créé.
- La limite de candidatures est GLOBALE par utilisateur, tous tableaux confondus
  (comptée via la chaîne d'ownership : jointure application → board, filtre sur
  board.user_id). Ce n'est PAS une limite par tableau : l'utilisateur répartit
  ses 300 candidatures librement. Répartir sur plusieurs tableaux ne permet donc
  pas d'en créer davantage.
- Le DÉPLACEMENT d'une candidature (PATCH board_id) ne fait AUCUN contrôle de
  limite, et c'est volontaire : déplacer ne change pas le total de l'utilisateur,
  donc la limite globale ne peut pas être contournée ainsi. Seule la création
  compte. Le PATCH garde évidemment son contrôle d'ownership sur le board cible.
- Taille des corps de requête : middleware ASGI `BodySizeLimitMiddleware`
  (main.py), qui refuse en 413 sur la foi de l'en-tête Content-Length, avant que
  l'endpoint ne bufferise le corps. Défense en profondeur applicative (utile en
  dev, sans proxy) ; en production le garde-fou AUTORITAIRE reste le reverse
  proxy (nginx `client_max_body_size`), seul capable de couper un client qui ment
  sur Content-Length ou l'omet (chunked). On n'implémente pas de comptage à la
  volée côté ASGI : renvoyer un 413 au milieu d'un flux déjà pris en charge par
  l'app provoque un double envoi de réponse.
