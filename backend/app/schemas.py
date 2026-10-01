"""Schémas Pydantic : le contrat de l'API.

Distinction importante (et classique) :
- models.py  = ce qui est stocké en base (SQLAlchemy)
- schemas.py = ce qui entre et sort de l'API (Pydantic)
Les deux se ressemblent mais ne sont PAS la même chose : on ne veut pas
exposer tous les champs internes, et les règles de validation diffèrent.
"""

from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)
from pydantic_core import PydanticCustomError

from app.limits import (
    MAX_BOARD_NAME_LENGTH,
    MAX_APPLIED_AT,
    MAX_COMPANY_LENGTH,
    MAX_ID,
    MAX_LOCATION_LENGTH,
    MAX_NOTES_LENGTH,
    MAX_PASSWORD_INPUT_BYTES,
    MAX_PASSWORD_LENGTH,
    MAX_TITLE_LENGTH,
    MAX_URL_LENGTH,
    MIN_APPLIED_AT,
)
from app.models import ApplicationStatus


class InputModel(BaseModel):
    """Base de TOUS les schémas d'ENTRÉE (ce que le client envoie).

    Refuse, dans chaque champ texte, les caractères qu'on ne peut pas enregistrer :
    - le NUL (U+0000) : PostgreSQL le rejette dans un champ texte, bcrypt aussi
      dans un mot de passe. Sans ce contrôle : 500 ;
    - un surrogate ISOLÉ (ex. l'échappement JSON \\ud800) : Python l'accepte dans
      une chaîne, mais il n'a pas d'encodage UTF-8, donc le pilote de base (ou
      passlib) lève UnicodeEncodeError. Sans ce contrôle : 500. Une PAIRE valide
      (émoji) est un caractère normal et reste acceptée.

    La valeur est REFUSÉE (422) et non nettoyée : ni l'un ni l'autre n'a d'usage
    légitime ici, et les retirer en silence modifierait la donnée (dans un mot de
    passe, l'identifiant lui-même) sans que le client le sache.

    Le validateur `'*'` s'applique à tous les champs des sous-classes, présents et
    futurs : l'oubli est impossible par construction, et tests/test_input_validation.py
    vérifie que chaque schéma d'entrée hérite bien de cette classe. Les schémas de
    SORTIE (`*Read`, Token, MessageResponse) n'en héritent pas : ils décrivent ce
    que le serveur envoie, pas ce qu'il reçoit.

    Lève PydanticCustomError, PAS un simple ValueError : avec un ValueError nu, le
    `type` de l'erreur serait le générique `value_error` de Pydantic, identique à
    celui de tous nos AUTRES validateurs personnalisés (mot de passe trop long,
    date hors plage, null interdit…) — impossible de choisir le bon message
    français sans deviner d'après le texte de l'exception. Le CODE stable
    ("nul_character", "surrogate_character") permet à app/error_messages.py de
    les distinguer de façon fiable. Effet de bord utile : le `ctx` de l'erreur
    contient alors exactement ce qu'on lui passe (rien, ici), jamais l'objet
    exception Python lui-même — ValueError l'y aurait mis (vérifié par
    exécution), ce qui aurait empêché de bâtir une réponse JSON propre."""

    @field_validator("*", mode="before")
    @classmethod
    def _reject_unstorable_characters(cls, value):
        if isinstance(value, str):
            if "\x00" in value:
                raise PydanticCustomError(
                    "nul_character", "Le caractère NUL (U+0000) n'est pas autorisé."
                )
            try:
                value.encode("utf-8")
            except UnicodeEncodeError:
                raise PydanticCustomError(
                    "surrogate_character",
                    "Caractère Unicode invalide (surrogate isolé) non autorisé.",
                ) from None
        return value



def _check_presented_password_size(value: str) -> str:
    """Refuse un mot de passe de plus de MAX_PASSWORD_INPUT_BYTES OCTETS UTF-8.

    En octets et non en caractères : passlib compte les octets et lève
    PasswordSizeError (donc un 500) au-delà de 4096. Une borne en caractères
    laisserait passer 2049 « é » (4098 octets).

    PydanticCustomError avec un code stable ("password_too_many_bytes") : voir
    InputModel._reject_unstorable_characters pour pourquoi un ValueError nu ne
    suffit pas (type générique `value_error`, indistinguable des autres
    validateurs personnalisés)."""
    if len(value.encode("utf-8")) > MAX_PASSWORD_INPUT_BYTES:
        raise PydanticCustomError(
            "password_too_many_bytes",
            "Le mot de passe dépasse {max_bytes} octets.",
            {"max_bytes": MAX_PASSWORD_INPUT_BYTES},
        )
    return value


def _normalize_email(value):
    """Adresse email en minuscules et sans espaces autour.

    Sans cela « Case@Example.com » et « case@example.com » étaient deux comptes
    (l'index unique de la colonne compare la casse) et la connexion échouait dès que
    la casse tapée différait de celle de l'inscription. EmailStr ne met en minuscules
    que le DOMAINE.

    S'exécute APRÈS le refus du NUL et du surrogate isolé (le validateur `'*'` de
    InputModel passe en premier : vérifié) et AVANT EmailStr, qui valide l'adresse
    déjà normalisée. Une valeur qui n'est pas une chaîne est laissée telle quelle :
    EmailStr produit alors son erreur habituelle. Les espaces À L'INTÉRIEUR ne sont
    pas touchés, EmailStr les refuse. `lower()` et non `casefold()` : casefold
    transformerait « ß » en « ss », donc changerait l'identité de l'adresse.
    Idempotent."""
    if isinstance(value, str):
        return value.strip().lower()
    return value


# Adresse email d'un schéma d'ENTRÉE. TOUT champ email d'un InputModel doit avoir ce
# type : un test (test_email_normalization.py) fait échouer la suite sinon.
NormalizedEmail = Annotated[EmailStr, BeforeValidator(_normalize_email)]

# Mot de passe PRÉSENTÉ (login, suppression de compte) : borne haute technique en
# octets, jamais un minimum ni la politique d'inscription.
PresentedPassword = Annotated[str, AfterValidator(_check_presented_password_size)]

# Types partagés par la CRÉATION et la MODIFICATION d'une candidature : une seule
# définition par champ, donc les deux payloads ne peuvent pas diverger (l'écart
# création/modification était à l'origine de 500 : location, url en PATCH).
# Les longueurs viennent de app/limits.py et ne dépassent jamais la colonne.
Title = Annotated[str, Field(min_length=1, max_length=MAX_TITLE_LENGTH)]
Company = Annotated[str, Field(min_length=1, max_length=MAX_COMPANY_LENGTH)]
Location = Annotated[str, Field(max_length=MAX_LOCATION_LENGTH)]
Url = Annotated[str, Field(max_length=MAX_URL_LENGTH)]
Notes = Annotated[str, Field(max_length=MAX_NOTES_LENGTH)]
BoardName = Annotated[str, Field(min_length=1, max_length=MAX_BOARD_NAME_LENGTH)]
# Identifiant : entier >= 1 et tenant dans le type `integer` de PostgreSQL.
RowId = Annotated[int, Field(ge=1, le=MAX_ID)]
# Origine d'une candidature, LISTE FERMÉE. Les sources d'API (V1.5) s'ajouteront le
# jour où elles existeront. La colonne reste String(50) : ApplicationRead.source
# reste un `str`, donc une valeur ancienne quelconque se lit toujours.
ApplicationSource = Literal["manual", "extension"]


class UserCreate(InputModel):
    """Payload d'inscription. NormalizedEmail normalise (minuscules, sans espaces
    autour) puis valide le format de l'email ; le mot de passe en clair n'existe
    que le temps de la requête, jamais stocké."""

    email: NormalizedEmail
    password: str = Field(min_length=8, max_length=MAX_PASSWORD_LENGTH)


class UserRead(BaseModel):
    """Représentation publique d'un utilisateur.

    N'expose volontairement PAS hashed_password : le contrat de sortie est
    distinct du modèle ORM, c'est tout l'intérêt de séparer schemas et models.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    # Exposé pour que le front puisse inviter à confirmer l'adresse (bandeau).
    # La vérification n'est PAS bloquante : le compte est utilisable sans.
    is_verified: bool
    created_at: datetime


class UserLogin(InputModel):
    """Identifiants de connexion. Aucune règle de POLITIQUE ici (pas de minimum) :
    on valide le mot de passe en le comparant au hash, pas en rejouant la politique
    d'inscription (un mot de passe valide hier ne doit pas devenir non saisissable).

    Seule exception, une borne HAUTE technique de 4096 OCTETS : passlib lève
    PasswordSizeError au-delà, ce qui faisait de cet endpoint public un 500. Un
    mot de passe accepté à l'inscription (128 caractères au plus, soit 512 octets)
    est très en deçà : la borne ne peut verrouiller aucun compte. Au-delà : 422 —
    le 401 reste réservé à un mot de passe bien formé mais incorrect."""

    email: NormalizedEmail
    password: PresentedPassword


class Token(BaseModel):
    """Réponse du login : le JWT et son type, au format attendu par OAuth2."""

    access_token: str
    token_type: str = "bearer"


class ForgotPasswordRequest(InputModel):
    """Demande d'un lien de réinitialisation. Seul l'email est fourni."""

    email: NormalizedEmail


class ResetPasswordRequest(InputModel):
    """Consommation du lien de réinitialisation.

    Le mot de passe est validé exactement comme à l'inscription (min 8) : la
    politique de mot de passe ne doit pas être contournable par ce chemin."""

    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=MAX_PASSWORD_LENGTH)


class VerifyEmailRequest(InputModel):
    """Consommation du lien de vérification d'adresse email."""

    token: str = Field(min_length=1)


class DeleteAccountRequest(InputModel):
    """Confirmation de suppression de compte : le mot de passe courant.

    Le JWT ne suffit délibérément pas. Un token peut fuiter (poste laissé
    déverrouillé, historique, sauvegarde de navigateur) et vit 60 minutes ; il
    autorise des actions réversibles, pas la destruction définitive de toutes les
    données du compte. Redemander le mot de passe exige un secret que le porteur
    d'un token volé n'a pas — c'est une ré-authentification, pas une case à
    cocher.

    Même borne haute technique que UserLogin (4096 octets, sans minimum) : on
    compare à un hash existant, on ne rejoue pas la politique d'inscription."""

    password: PresentedPassword


class MessageResponse(BaseModel):
    """Réponse générique à une action sans contenu à renvoyer.

    Utilisée notamment par /auth/forgot-password, dont le message est
    volontairement identique que le compte existe ou non."""

    message: str


class BoardCreate(InputModel):
    """Payload pour créer un tableau. Seul le nom est fourni ; le propriétaire
    (user_id) est renseigné côté serveur depuis le current_user."""

    # MAX_BOARD_NAME_LENGTH (100) : garde-fou de cohérence des données. Le front
    # limite à 25 pour l'UX (sidebar/titre lisibles) ; le backend borne plus
    # largement pour empêcher un nom délirant stocké en contournant le front.
    name: BoardName


class BoardUpdate(InputModel):
    """Payload pour renommer un tableau. Le nom est le seul champ modifiable."""

    name: BoardName


class BoardRead(BaseModel):
    """Ce que l'API renvoie pour un tableau.

    active_applications_count / archived_applications_count : calculés par le
    router (routers/boards.py, _to_board_read), PAS lus depuis l'objet ORM
    directement (Board ne les porte pas) — model_config from_attributes reste
    utile pour les 5 autres champs quand on construit depuis un ORM Board, mais
    ces deux-là sont toujours fournis explicitement à la construction.
    Objectif : permettre au frontend d'annoncer « N archives concernées » avant
    de confirmer la suppression d'un tableau (lot frontend séparé, hors de
    celui-ci) sans avoir à interroger un second endpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    user_id: int
    created_at: datetime
    updated_at: datetime
    active_applications_count: int
    archived_applications_count: int


class ApplicationCreate(InputModel):
    """Payload pour créer une candidature (formulaire ou extension).

    board_id désigne le tableau cible ; le serveur vérifie qu'il appartient bien
    au current_user (sinon 404). Le statut n'est pas fourni : il démarre en
    « saved » (voir le modèle)."""

    board_id: RowId
    title: Title
    company: Company
    location: Location | None = None
    url: Url | None = None
    source: ApplicationSource = "manual"
    notes: Notes | None = None


class ApplicationUpdate(InputModel):
    """Payload pour modifier une candidature. Tous les champs optionnels :
    on ne met à jour que ce qui est fourni (PATCH sémantique).

    Les types sont ceux de la création (Title, Location, Url, Notes…) : une valeur
    acceptée à la modification l'est aussi à la création, et inversement.

    board_id permet de DÉPLACER une candidature vers un autre tableau. Le
    serveur vérifie que ce tableau cible appartient bien au current_user (sinon
    404), exactement comme à la création — on ne fait jamais confiance au payload
    pour l'ownership.

    `null` EXPLICITE : `X | None = None` accepte un null envoyé par le client, ce
    qui n'a de sens que pour VIDER un champ facultatif (location, url, notes,
    applied_at). Sur les champs obligatoires en base (title, company, status,
    board_id), il violerait le NOT NULL (500) : il est donc refusé (422). Pour ne
    pas modifier un champ, on l'OMET."""

    board_id: RowId | None = None
    title: Title | None = None
    company: Company | None = None
    location: Location | None = None
    url: Url | None = None
    status: ApplicationStatus | None = None
    notes: Notes | None = None
    applied_at: datetime | None = None

    @field_validator("board_id", "title", "company", "status", mode="before")
    @classmethod
    def _required_fields_cannot_be_null(cls, value):
        if value is None:
            raise PydanticCustomError(
                "null_not_allowed",
                "Ce champ ne peut pas être null : omettez-le pour ne pas le modifier.",
            )
        return value

    @field_validator("applied_at", mode="after")
    @classmethod
    def _normalize_and_bound_applied_at(cls, value: datetime | None) -> datetime | None:
        """Ramène la date en UTC NAÏF, puis vérifie qu'elle est dans la plage.

        1. Normalisation : les colonnes DateTime sont naïves en UTC (cf. convention
           du projet). Sans elle, un fuseau est traité différemment selon le moteur :
           `10:00+02:00` est écrit 08:00 par PostgreSQL mais 10:00 par SQLite, qui
           ignore le fuseau.
        2. Plage (MIN_APPLIED_AT..MAX_APPLIED_AT), jugée APRÈS conversion : PostgreSQL
           accepte des dates que Python ne sait pas relire (avant l'an 1, après
           l'an 9999). Elles étaient commitées puis rendaient la ligne illisible :
           liste des candidatures du compte en 500, suppression comprise.
        3. La conversion elle-même peut déborder (an 1 avec +02:00) : OverflowError,
           traité comme une date hors plage (422).

        Les deux échecs lèvent le MÊME code PydanticCustomError
        ("applied_at_out_of_range") : du point de vue de l'utilisateur, les deux
        signifient « choisissez une date dans la plage acceptée ». Le contexte
        transporte les bornes déjà formatées (JJ/MM/AAAA) : app/error_messages.py
        les affiche telles quelles, sans dupliquer MIN_APPLIED_AT/MAX_APPLIED_AT."""
        if value is None:
            return value
        range_ctx = {
            "min": MIN_APPLIED_AT.strftime("%d/%m/%Y"),
            "max": MAX_APPLIED_AT.strftime("%d/%m/%Y"),
        }
        if value.tzinfo is not None:
            try:
                value = value.astimezone(timezone.utc).replace(tzinfo=None)
            except OverflowError:
                raise PydanticCustomError(
                    "applied_at_out_of_range",
                    "Date hors plage : elle sort des dates représentables une fois "
                    "convertie en UTC.",
                    range_ctx,
                ) from None
        if not MIN_APPLIED_AT <= value <= MAX_APPLIED_AT:
            raise PydanticCustomError(
                "applied_at_out_of_range",
                "La date doit être comprise entre le {min} et le {max} (UTC).",
                range_ctx,
            )
        return value


class ApplicationRead(BaseModel):
    """Ce que l'API renvoie au client."""

    model_config = ConfigDict(from_attributes=True)  # lecture depuis l'objet ORM

    id: int
    board_id: int
    title: str
    company: str
    location: str | None
    url: str | None
    source: str
    status: ApplicationStatus
    notes: str | None
    applied_at: datetime | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime
