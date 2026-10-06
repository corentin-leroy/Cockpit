# Session JWT : durée de vie et révocation
- 12 HEURES (720 minutes), pour couvrir une journée d'utilisation sans
  reconnexion. Réglable par ACCESS_TOKEN_EXPIRE_MINUTES sans redéploiement ;
  `ACCESS_TOKEN_EXPIRE_MINUTES` (app/security.py) est la seule source.
- Les jetons sont SANS ÉTAT : rien n'est stocké côté serveur, la signature suffit
  à les valider. Conséquence directe, ils sont IRRÉVOCABLES — se déconnecter
  efface le jeton du navigateur, mais une copie dérobée reste valable jusqu'à son
  expiration, et aucune action serveur ne peut l'annuler. L'EXPIRATION EST DONC
  LA SEULE BORNE à l'exploitation d'un jeton volé : 12 h, c'est douze fois la
  fenêtre d'attaque de l'ancienne heure. Compromis accepté en connaissance de
  cause, contre le confort d'une journée sans reconnexion.
- Seul levier de révocation existant : changer JWT_SECRET_KEY, qui invalide les
  jetons de TOUS les utilisateurs d'un coup. Mesure d'incident, pas de gestion
  courante.
- Baisser la valeur ne raccourcit PAS les sessions en cours : l'expiration est
  inscrite dans chaque jeton à l'émission. Le changement ne vaut que pour les
  connexions suivantes.
- ⚠ NE PAS ALLONGER DAVANTAGE sans introduire des REFRESH TOKENS (déjà en V3,
  cf. hors périmètre). C'est la réponse propre au dilemme confort/sécurité, et
  elle ne consiste pas à étirer la durée : un jeton d'accès COURT (15-30 min,
  donc fenêtre de vol réduite) accompagné d'un refresh token long, stocké EN BASE
  et donc révocable individuellement. On récupère alors ce que le sans-état
  interdit aujourd'hui — déconnecter un appareil, invalider une session
  compromise, sans toucher aux autres utilisateurs. Prolonger encore la durée
  actuelle ne ferait qu'aggraver le problème que les refresh tokens résolvent.
- L'expiration est couverte par test_auth.py (jeton expiré rejeté en 401 sur
  /auth/me et sur les endpoints de données, `exp` conforme à la durée
  configurée, jeton signé d'une autre clé rejeté). Ces tests n'existaient pas
  avant l'allongement : une régression sur la validation de `exp` serait
  parfaitement silencieuse — tout continuerait de marcher, les jetons ne
  cesseraient simplement jamais d'être valables.
