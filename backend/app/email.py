"""Envoi d'emails transactionnels.

Ce module est la SEULE frontière avec le fournisseur d'envoi (Brevo) : le reste
du code n'appelle que les fonctions de haut niveau (`send_password_reset_email`,
`send_verification_email`) et ignore tout de l'API sous-jacente. Changer de
fournisseur = ne toucher qu'à ce fichier.

Mode DEV : si BREVO_API_KEY est absente, aucun appel réseau n'est fait et le
lien est écrit dans les logs. On peut donc dérouler tout le parcours (reset,
vérification) en local sans consommer de quota d'envoi.

Appel réseau : `urllib.request` de la stdlib, plutôt qu'une dépendance HTTP
supplémentaire. Une seule requête POST JSON suffit ici ; le jour où l'on aura
besoin de retries ou d'asynchrone, la bascule vers httpx restera confinée à ce
module.
"""

import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
_TIMEOUT_SECONDS = 10


def _get_frontend_url() -> str:
    """URL publique du front, base des liens envoyés par email."""
    return os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")


def _send(to_email: str, subject: str, html_content: str, dev_link: str) -> None:
    """Envoie un email via Brevo, ou logue le lien si la clé API est absente.

    Ne lève jamais : un échec d'envoi ne doit pas faire échouer l'inscription ou
    la demande de reset (l'utilisateur peut toujours redemander un email). On
    trace l'erreur côté serveur.
    """
    api_key = os.getenv("BREVO_API_KEY")
    sender_email = os.getenv("BREVO_SENDER_EMAIL")

    # --- Mode DEV : rien n'est envoyé, le lien est affiché dans la console ---
    if not api_key or not sender_email:
        logger.warning(
            "[email dev] BREVO_API_KEY/BREVO_SENDER_EMAIL absente : aucun email "
            "envoyé à %s. Sujet : %s. Lien : %s",
            to_email,
            subject,
            dev_link,
        )
        return

    payload = {
        "sender": {
            "email": sender_email,
            "name": os.getenv("BREVO_SENDER_NAME", "Cockpit"),
        },
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_content,
    }
    request = urllib.request.Request(
        BREVO_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "api-key": api_key,
            "content-type": "application/json",
            "accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            logger.info(
                "Email « %s » envoyé à %s (HTTP %s).", subject, to_email, response.status
            )
    except urllib.error.HTTPError as exc:
        # On logue le corps de la réponse : Brevo y détaille la cause (quota,
        # expéditeur non validé, clé révoquée…). Jamais le contenu du lien.
        body = exc.read().decode("utf-8", errors="replace")
        logger.error("Échec d'envoi Brevo (HTTP %s) : %s", exc.code, body)
    except (urllib.error.URLError, TimeoutError) as exc:
        logger.error("Échec d'envoi Brevo (réseau) : %s", exc)


def _layout(title: str, body: str, button_label: str, link: str) -> str:
    """Gabarit HTML commun aux emails transactionnels.

    Le lien est répété en texte brut sous le bouton : certains clients mail
    n'affichent pas les boutons stylés, et l'utilisateur doit toujours pouvoir
    copier l'URL.
    """
    return f"""\
<div style="font-family: system-ui, sans-serif; color: #2e2a26; line-height: 1.55;">
  <h1 style="font-size: 20px;">{title}</h1>
  <p>{body}</p>
  <p>
    <a href="{link}"
       style="display: inline-block; padding: 10px 18px; border-radius: 10px;
              background: #0f766e; color: #ffffff; text-decoration: none;">
      {button_label}
    </a>
  </p>
  <p style="font-size: 13px; color: #625b54;">
    Si le bouton ne fonctionne pas, copiez ce lien dans votre navigateur :<br />
    <a href="{link}">{link}</a>
  </p>
</div>"""


def send_password_reset_email(to_email: str, token: str) -> None:
    """Envoie le lien de réinitialisation de mot de passe (valable 60 minutes)."""
    link = f"{_get_frontend_url()}/reset-password?token={token}"
    html = _layout(
        title="Réinitialisation de votre mot de passe",
        body=(
            "Vous avez demandé à réinitialiser le mot de passe de votre compte "
            "Cockpit. Ce lien est valable <strong>1 heure</strong> et ne peut "
            "servir qu'une fois. Si vous n'êtes pas à l'origine de cette "
            "demande, ignorez cet email : votre mot de passe reste inchangé."
        ),
        button_label="Choisir un nouveau mot de passe",
        link=link,
    )
    _send(to_email, "Réinitialisez votre mot de passe Cockpit", html, dev_link=link)


def send_verification_email(to_email: str, token: str) -> None:
    """Envoie le lien de vérification d'adresse email (valable 24 heures)."""
    link = f"{_get_frontend_url()}/verify-email?token={token}"
    html = _layout(
        title="Confirmez votre adresse email",
        body=(
            "Bienvenue sur Cockpit ! Confirmez votre adresse email pour "
            "sécuriser votre compte. Ce lien est valable <strong>24 heures</strong>."
        ),
        button_label="Confirmer mon adresse",
        link=link,
    )
    _send(to_email, "Confirmez votre adresse email Cockpit", html, dev_link=link)
