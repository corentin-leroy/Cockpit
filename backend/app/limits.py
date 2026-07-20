"""Limites de quantité — garde-fous anti-abus, vérifiés CÔTÉ SERVEUR.

Ces plafonds protègent la base d'un usage abusif (création en boucle de tableaux
ou de candidatures, corps de requête démesurés). Ils sont TOUJOURS contrôlés à la
création côté backend : le front peut les afficher pour l'UX, mais ne fait jamais
autorité — un client qui contourne le front (extension, curl…) reste plafonné.

Source unique : ces constantes sont importées par les routers concernés
(boards, applications) et par le middleware de taille de requête (main.py).
"""

# Nombre maximum de tableaux par utilisateur. Un compte a toujours ≥ 1 tableau
# (board par défaut à l'inscription) ; ce plafond borne l'autre extrémité.
MAX_BOARDS_PER_USER = 10

# Nombre maximum de candidatures par utilisateur, GLOBAL (tous tableaux confondus).
# Ce n'est PAS une limite par tableau : l'utilisateur répartit librement ses 300
# candidatures entre ses tableaux. Le total se compte via la chaîne d'ownership
# (candidatures dont le board appartient à l'utilisateur).
MAX_APPLICATIONS_PER_USER = 300

# Taille maximale du corps d'une requête HTTP, en octets (1 Mo). Évite qu'une
# charge utile énorme (ex. un champ `notes` de plusieurs Mo) ne consomme mémoire
# et stockage. Appliqué globalement par un middleware (voir main.py).
MAX_REQUEST_BODY_BYTES = 1 * 1024 * 1024
