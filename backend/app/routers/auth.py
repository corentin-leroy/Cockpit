"""Endpoints d'authentification : inscription, connexion, mot de passe oublié,
vérification d'adresse email.

Deux principes transverses ici :
- Anti-énumération : aucun endpoint public ne doit permettre de découvrir si un
  email a un compte. Le login renvoie un 401 identique dans tous les cas ;
  /forgot-password renvoie le même message, que le compte existe ou non.
- Les liens envoyés par email sont des tokens à usage unique (SecurityToken),
  stockés hachés et datés. Voir models.SecurityToken pour le détail.
"""

from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.email import send_password_reset_email, send_verification_email
from app.models import Board, SecurityToken, TokenPurpose, User
from app.schemas import (
    DeleteAccountRequest,
    ForgotPasswordRequest,
    MessageResponse,
    ResetPasswordRequest,
    Token,
    UserCreate,
    UserLogin,
    UserRead,
    VerifyEmailRequest,
)
from app.security import (
    DUMMY_PASSWORD_HASH,
    EMAIL_VERIFICATION_EXPIRE_HOURS,
    PASSWORD_RESET_EXPIRE_MINUTES,
    create_access_token,
    generate_url_token,
    hash_password,
    hash_token,
    utcnow,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# --- Rate limiting des emails sortants ---
# Un envoi d'email est une action coûteuse (quota Brevo) et NUISIBLE si elle est
# déclenchée en boucle : n'importe qui peut saisir l'adresse d'un tiers dans
# /forgot-password et la faire spammer. On plafonne donc les demandes par compte.
#
# Approche : on ne stocke aucun compteur dédié, on COMPTE les SecurityToken déjà
# émis pour ce couple (utilisateur, usage) dans la dernière heure — la table qui
# les porte est déjà là, avec un created_at. Avantages : rien à installer (pas de
# Redis ni de dépendance type slowapi), le compteur survit à un redémarrage et
# reste correct si plusieurs workers tournent, puisque la source de vérité est la
# base. Limite assumée : c'est une fenêtre glissante par compte, pas une défense
# volumétrique par IP — celle-ci se posera au niveau du reverse proxy en prod.
MAX_EMAILS_PER_HOUR = 3


def _recent_token_count(db: Session, user_id: int, purpose: TokenPurpose) -> int:
    """Nombre de tokens émis pour cet utilisateur et cet usage depuis 1 heure."""
    since = utcnow() - timedelta(hours=1)
    return db.scalar(
        select(func.count())
        .select_from(SecurityToken)
        .where(
            SecurityToken.user_id == user_id,
            SecurityToken.purpose == purpose,
            SecurityToken.created_at >= since,
        )
    )


def _issue_token(db: Session, user: User, purpose: TokenPurpose) -> str:
    """Crée un SecurityToken en base et renvoie le token EN CLAIR.

    Le clair n'existe qu'ici et dans l'email : la base n'en garde que le SHA-256.
    N'effectue pas le commit — l'appelant décide de la transaction.
    """
    plain_token = generate_url_token()
    lifetime = (
        timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES)
        if purpose is TokenPurpose.PASSWORD_RESET
        else timedelta(hours=EMAIL_VERIFICATION_EXPIRE_HOURS)
    )
    db.add(
        SecurityToken(
            token_hash=hash_token(plain_token),
            purpose=purpose,
            user_id=user.id,
            expires_at=utcnow() + lifetime,
        )
    )
    return plain_token


def _consume_token(db: Session, plain_token: str, purpose: TokenPurpose) -> SecurityToken:
    """Valide un token reçu et le marque comme consommé.

    Le filtre sur `purpose` est essentiel : sans lui, un lien de vérification
    d'email (valable 24 h) pourrait servir à réinitialiser un mot de passe.

    Lève un 400 unique pour les trois cas d'échec (inconnu, expiré, déjà utilisé) :
    inutile de détailler à un client qui présente un lien invalide, et le message
    est de toute façon actionnable de la même façon — redemander un lien.
    """
    token = db.scalar(
        select(SecurityToken).where(
            SecurityToken.token_hash == hash_token(plain_token),
            SecurityToken.purpose == purpose,
        )
    )
    if (
        token is None
        or token.consumed_at is not None
        or token.expires_at < utcnow()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce lien est invalide ou expiré. Demandez-en un nouveau.",
        )

    token.consumed_at = utcnow()
    return token


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(
    payload: UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Crée un compte utilisateur.

    Refuse un email déjà pris avec un 409 Conflict. Le mot de passe est haché
    avant stockage ; la réponse (UserRead) n'expose jamais le hash.

    Envoie un email de vérification, mais l'inscription réussit et le compte est
    immédiatement utilisable : la vérification n'est PAS bloquante (décision
    produit). Un échec d'envoi ne compromet donc pas l'inscription.
    """
    # Contrôle applicatif du doublon : message clair pour le client.
    # La contrainte unique en base reste le garde-fou ultime (voir plus bas).
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte existe déjà avec cet email.",
        )

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.flush()  # attribue user.id sans clore la transaction

    # Tout utilisateur possède au moins un tableau : on lui en crée un par défaut
    # à l'inscription (garantit l'invariant « toujours ≥ 1 board » dès la création
    # du compte). Même transaction que l'utilisateur : les deux réussissent ou
    # échouent ensemble.
    db.add(Board(name="Mes candidatures", user_id=user.id))

    verification_token = _issue_token(db, user, TokenPurpose.EMAIL_VERIFICATION)

    db.commit()
    db.refresh(user)

    # Envoi APRÈS le commit et en tâche de fond : l'utilisateur n'attend pas
    # l'aller-retour vers Brevo, et on n'envoie jamais de lien pour un compte
    # dont la transaction aurait échoué.
    background_tasks.add_task(send_verification_email, user.email, verification_token)
    return user


@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """Authentifie un utilisateur et renvoie un JWT.

    En cas d'échec, renvoie un 401 avec un message **identique** que l'email
    soit inconnu ou le mot de passe faux : on ne révèle jamais si un compte
    existe. On exécute toujours verify_password (contre un hash leurre quand
    l'email est inconnu) pour ne pas trahir l'existence d'un compte par le
    temps de réponse.

    Un compte non vérifié se connecte normalement (vérification non bloquante).
    """
    user = db.scalar(select(User).where(User.email == payload.email))
    hashed = user.hashed_password if user is not None else DUMMY_PASSWORD_HASH

    if not verify_password(payload.password, hashed) or user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # `sub` (subject) = identité portée par le token ; chaîne par convention JWT.
    access_token = create_access_token({"sub": str(user.id)})
    return Token(access_token=access_token)


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)):
    """Renvoie l'utilisateur authentifié (id, email, is_verified, created_at).

    Le JWT ne porte que l'id (claim `sub`) : le front n'a aucun moyen d'en
    déduire l'état du compte. Cet endpoint est le seul canal qui lui dit si
    l'adresse est vérifiée — et il reste à jour, contrairement à un état qui
    serait figé dans le token à la connexion.
    """
    return current_user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_current_user(
    payload: DeleteAccountRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Supprime définitivement le compte de l'utilisateur courant (droit à l'effacement).

    Emportent le compte, par cascade déclarée dans le schéma : ses tableaux, les
    candidatures de ces tableaux, et ses jetons de sécurité en attente. Il ne
    subsiste aucune donnée personnelle après cet appel — c'est un effacement, pas
    une désactivation.

    DOUBLE contrôle, volontaire : le JWT prouve la session, le mot de passe prouve
    l'identité. Un token volé ne doit pas suffire à détruire un compte, parce que
    l'action est irréversible et sans recours (contrairement à la modification
    d'une candidature). C'est la même exigence de ré-authentification que celle
    des opérations sensibles ailleurs dans l'industrie.

    Le 403 en cas de mauvais mot de passe ne révèle rien : l'appelant est DÉJÀ
    authentifié comme cet utilisateur (il a un token valide), donc l'existence du
    compte n'est pas une information qu'on lui apprend. On ne renvoie pas 401,
    qui signifierait « session invalide » et ferait purger le token côté front
    alors que la session, elle, est parfaitement valide.
    """
    if not verify_password(payload.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mot de passe incorrect.",
        )

    # La cascade fait le reste : boards → applications, et security_tokens.
    # Les relations portent passive_deletes=True, donc SQLAlchemy émet UN seul
    # DELETE sur users et laisse la base propager (cf. models.py).
    db.delete(current_user)
    db.commit()


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Envoie un lien de réinitialisation de mot de passe (valable 1 heure).

    Renvoie TOUJOURS le même message, que le compte existe ou non : cet endpoint
    est public, il ne doit pas devenir un oracle permettant de savoir qui est
    inscrit (même logique que le 401 générique du login).

    Conséquence du même principe : quand le plafond d'envois est atteint, on ne
    renvoie pas un 429 — cela révélerait l'existence du compte. On s'abstient
    simplement d'envoyer, avec la même réponse.
    """
    user = db.scalar(select(User).where(User.email == payload.email))

    if user is not None and (
        _recent_token_count(db, user.id, TokenPurpose.PASSWORD_RESET)
        < MAX_EMAILS_PER_HOUR
    ):
        reset_token = _issue_token(db, user, TokenPurpose.PASSWORD_RESET)
        db.commit()
        background_tasks.add_task(send_password_reset_email, user.email, reset_token)

    return MessageResponse(
        message=(
            "Si un compte existe avec cette adresse, un email vient d'être envoyé."
        )
    )


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Change le mot de passe à partir d'un lien de réinitialisation.

    Le token doit exister, ne pas être expiré et ne pas avoir déjà servi.
    Le nouveau mot de passe est soumis à la même règle qu'à l'inscription
    (validée par le schéma : 8 caractères minimum).

    Effet de bord assumé : le compte devient vérifié. Avoir cliqué sur un lien
    envoyé à cette adresse prouve qu'on y a accès — c'est exactement ce que
    démontre la vérification d'email. Continuer à réclamer une confirmation
    après ça n'apporterait aucune garantie supplémentaire.
    """
    token = _consume_token(db, payload.token, TokenPurpose.PASSWORD_RESET)

    user = db.get(User, token.user_id)
    user.hashed_password = hash_password(payload.new_password)
    user.is_verified = True

    # Les autres liens de reset encore en attente pour ce compte deviennent
    # caducs : après un changement de mot de passe, un ancien lien (par exemple
    # issu d'un email intercepté) ne doit plus pouvoir en reprendre la main.
    others = db.scalars(
        select(SecurityToken).where(
            SecurityToken.user_id == user.id,
            SecurityToken.purpose == TokenPurpose.PASSWORD_RESET,
            SecurityToken.consumed_at.is_(None),
        )
    )
    for pending in others:
        pending.consumed_at = utcnow()

    db.commit()
    return MessageResponse(message="Votre mot de passe a été mis à jour.")


@router.post("/verify-email", response_model=MessageResponse)
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)):
    """Confirme l'adresse email à partir du lien reçu (valable 24 heures).

    Endpoint public : le token EST la preuve d'identité (l'utilisateur peut
    cliquer depuis sa boîte mail sans être connecté à l'app).
    """
    token = _consume_token(db, payload.token, TokenPurpose.EMAIL_VERIFICATION)

    user = db.get(User, token.user_id)
    user.is_verified = True

    db.commit()
    return MessageResponse(message="Votre adresse email est confirmée.")


@router.post("/resend-verification", response_model=MessageResponse)
def resend_verification(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Renvoie un email de vérification à l'utilisateur connecté.

    Authentifié : l'appelant a déjà prouvé qu'il possède le compte, donc aucun
    risque d'énumération ici — on peut être explicite (409 si déjà vérifié,
    429 si le plafond horaire est atteint).
    """
    if current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Votre adresse email est déjà confirmée.",
        )

    if (
        _recent_token_count(db, current_user.id, TokenPurpose.EMAIL_VERIFICATION)
        >= MAX_EMAILS_PER_HOUR
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Trop de demandes d'envoi. Réessayez dans une heure ou vérifiez "
                "vos spams."
            ),
        )

    verification_token = _issue_token(db, current_user, TokenPurpose.EMAIL_VERIFICATION)
    db.commit()

    background_tasks.add_task(
        send_verification_email, current_user.email, verification_token
    )
    return MessageResponse(message="Un email de confirmation vient d'être envoyé.")
