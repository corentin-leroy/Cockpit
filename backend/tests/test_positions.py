"""Ordre des cartes du kanban : `applications.position`, l'endpoint de déplacement
et la règle d'arrivée EN HAUT.

Règles vérifiées (cf. CLAUDE.md, « Ordre des cartes du kanban ») :
- dans chaque colonne ACTIVE (même tableau, même statut, non archivée), les
  positions valent exactement 0..n-1 ; 0 = en haut ;
- toute arrivée dans une colonne AUTREMENT que par POST /move place la carte en
  haut : création (formulaire ou extension), PATCH qui change RÉELLEMENT le statut
  ou le tableau, désarchivage ;
- seul POST /applications/{id}/move choisit une autre position ;
- une archivée a toujours une position NULL ;
- quitter une colonne (déplacement, archivage, suppression) la compacte.

`position` n'est pas exposée par l'API : les assertions portent sur l'ORDRE de la
liste (le contrat) et sur l'ÉTAT STOCKÉ (lu directement en base).
"""

import pytest
from sqlalchemy import select, text

from app.limits import MAX_APPLICATIONS_PER_USER
from app.models import Application


# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------


def _titles(client, user, board_id=None, status=None) -> list[str]:
    """Intitulés de la liste renvoyée par l'API, dans l'ordre, filtrés au besoin."""
    params = {"board_id": board_id if board_id is not None else user.default_board_id}
    response = client.get("/applications", params=params, headers=user.headers)
    assert response.status_code == 200, response.text
    return [a["title"] for a in response.json() if status is None or a["status"] == status]


def _stored(db_session, application_id: int) -> Application:
    db_session.expire_all()
    return db_session.get(Application, application_id)


def assert_positions_are_coherent(db_session) -> None:
    """INVARIANT, sur l'état stocké : chaque colonne active vaut exactement 0..n-1
    (ni trou, ni doublon, ni NULL) et toute archivée a une position NULL."""
    db_session.expire_all()
    columns: dict[tuple, list] = {}
    for app in db_session.scalars(select(Application)):
        if app.archived_at is not None:
            assert app.position is None, f"archivée {app.id} numérotée ({app.position})"
            continue
        columns.setdefault((app.board_id, app.status), []).append(app.position)
    for key, positions in columns.items():
        assert None not in positions, f"colonne {key} : position NULL {positions}"
        assert sorted(positions) == list(range(len(positions))), (
            f"colonne {key} : positions incohérentes {sorted(positions)}"
        )


def _make_column(make_application, user, titles, board_id=None) -> dict[str, dict]:
    """Crée les candidatures dans l'ordre donné. Chaque création arrive EN HAUT :
    l'ordre affiché est donc l'INVERSE de l'ordre de création."""
    return {t: make_application(user, board_id, title=t) for t in titles}


def _move(client, user, application_id, status, position):
    return client.post(
        f"/applications/{application_id}/move",
        json={"status": status, "position": position},
        headers=user.headers,
    )


# ---------------------------------------------------------------------------
# Arrivée en haut
# ---------------------------------------------------------------------------


def test_new_applications_arrive_at_the_top(client, make_user, make_application, db_session):
    user = make_user()
    _make_column(make_application, user, ["A", "B", "C"])
    assert _titles(client, user) == ["C", "B", "A"]
    assert_positions_are_coherent(db_session)


def test_extension_creation_also_arrives_at_the_top(client, make_user, make_application, db_session):
    user = make_user()
    _make_column(make_application, user, ["A", "B"])
    make_application(user, title="Ext", source="extension")
    assert _titles(client, user) == ["Ext", "B", "A"]
    assert_positions_are_coherent(db_session)


def test_patch_changing_status_puts_the_card_at_the_top_of_its_new_column(
    client, make_user, make_application, db_session
):
    user = make_user()
    apps = _make_column(make_application, user, ["A", "B", "C"])
    for t in ["X", "Y"]:
        created = make_application(user, title=t)
        client.patch(f"/applications/{created['id']}", json={"status": "applied"}, headers=user.headers)
    # Colonne « applied » : Y (arrivée en dernier) puis X.
    assert _titles(client, user, status="applied") == ["Y", "X"]

    # « A » est en BAS de « saved » ; changement de statut par PATCH → en haut de « applied ».
    response = client.patch(
        f"/applications/{apps['A']['id']}", json={"status": "applied"}, headers=user.headers
    )
    assert response.status_code == 200
    assert _titles(client, user, status="applied") == ["A", "Y", "X"]
    assert _titles(client, user, status="saved") == ["C", "B"]
    assert_positions_are_coherent(db_session)


def test_patch_resending_the_same_status_and_board_does_not_move_the_card(
    client, make_user, make_application, db_session
):
    """Le formulaire d'édition envoie TOUJOURS `status` et `board_id`, même
    inchangés. Le serveur compare aux valeurs stockées : un PATCH qui renvoie les
    mêmes ne doit PAS faire remonter la carte (ce n'est pas une arrivée)."""
    user = make_user()
    apps = _make_column(make_application, user, ["A", "B", "C"])
    assert _titles(client, user) == ["C", "B", "A"]

    response = client.patch(
        f"/applications/{apps['A']['id']}",
        json={
            "status": "saved",
            "board_id": user.default_board_id,
            "title": "A modifiée",
            "notes": "une note",
        },
        headers=user.headers,
    )
    assert response.status_code == 200
    assert _titles(client, user) == ["C", "B", "A modifiée"]
    assert_positions_are_coherent(db_session)


def test_patch_of_other_fields_does_not_move_the_card(client, make_user, make_application, db_session):
    """Avant ce lot, la liste était triée par updated_at : modifier une note
    faisait remonter la carte. Ce n'est plus le cas."""
    user = make_user()
    apps = _make_column(make_application, user, ["A", "B", "C"])
    client.patch(f"/applications/{apps['A']['id']}", json={"notes": "n"}, headers=user.headers)
    assert _titles(client, user) == ["C", "B", "A"]


def test_patch_moving_to_another_board_puts_the_card_at_the_top_there(
    client, make_user, make_application, make_board, db_session
):
    user = make_user()
    other = make_board(user)
    apps = _make_column(make_application, user, ["A", "B", "C"])
    _make_column(make_application, user, ["P", "Q"], board_id=other)

    response = client.patch(
        f"/applications/{apps['A']['id']}", json={"board_id": other}, headers=user.headers
    )
    assert response.status_code == 200
    assert _titles(client, user, board_id=other) == ["A", "Q", "P"]
    assert _titles(client, user) == ["C", "B"]
    assert_positions_are_coherent(db_session)


def test_patch_moving_board_keeps_the_status_and_lands_in_the_matching_column(
    client, make_user, make_application, make_board, db_session
):
    user = make_user()
    other = make_board(user)
    a = make_application(user, title="A")
    client.patch(f"/applications/{a['id']}", json={"status": "interview"}, headers=user.headers)
    make_application(user, other, title="I1")  # « saved » dans l'autre tableau

    client.patch(f"/applications/{a['id']}", json={"board_id": other}, headers=user.headers)
    assert _titles(client, user, board_id=other, status="interview") == ["A"]
    assert _titles(client, user, board_id=other, status="saved") == ["I1"]
    assert_positions_are_coherent(db_session)


def test_unarchived_application_comes_back_at_the_top_of_its_column(
    client, make_user, make_application, db_session
):
    user = make_user()
    apps = _make_column(make_application, user, ["A", "B", "C"])
    assert client.post(f"/applications/{apps['B']['id']}/archive", headers=user.headers).status_code == 200
    assert _titles(client, user) == ["C", "A"]
    assert _stored(db_session, apps["B"]["id"]).position is None
    assert_positions_are_coherent(db_session)

    make_application(user, title="D")
    assert client.post(f"/applications/{apps['B']['id']}/unarchive", headers=user.headers).status_code == 200
    assert _titles(client, user) == ["B", "D", "C", "A"]
    assert_positions_are_coherent(db_session)


def test_patch_on_an_archived_application_does_not_number_it(
    client, make_user, make_application, make_board, db_session
):
    """Correction depuis la page d'archives (statut ou tableau) : elle reste
    archivée, donc hors de toute colonne, position NULL ; au désarchivage, elle
    arrive en haut de la colonne correspondant à son NOUVEAU statut et tableau."""
    user = make_user()
    other = make_board(user)
    a = make_application(user, title="A")
    client.post(f"/applications/{a['id']}/archive", headers=user.headers)
    make_application(user, other, title="Z")
    client.patch(f"/applications/{a['id']}", json={"board_id": other}, headers=user.headers)
    client.patch(f"/applications/{a['id']}", json={"status": "saved"}, headers=user.headers)
    assert _stored(db_session, a["id"]).position is None
    assert_positions_are_coherent(db_session)

    client.post(f"/applications/{a['id']}/unarchive", headers=user.headers)
    assert _titles(client, user, board_id=other) == ["A", "Z"]
    assert_positions_are_coherent(db_session)


def test_deleting_an_active_application_compacts_its_column(
    client, make_user, make_application, db_session
):
    user = make_user()
    apps = _make_column(make_application, user, ["A", "B", "C", "D"])
    assert client.delete(f"/applications/{apps['C']['id']}", headers=user.headers).status_code == 204
    assert _titles(client, user) == ["D", "B", "A"]
    assert_positions_are_coherent(db_session)


# ---------------------------------------------------------------------------
# POST /applications/{id}/move
# ---------------------------------------------------------------------------


def test_move_within_a_column_from_bottom_to_top(client, make_user, make_application, db_session):
    user = make_user()
    apps = _make_column(make_application, user, ["A", "B", "C", "D"])
    assert _titles(client, user) == ["D", "C", "B", "A"]

    response = _move(client, user, apps["A"]["id"], "saved", 0)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "saved"
    assert _titles(client, user) == ["A", "D", "C", "B"]
    assert_positions_are_coherent(db_session)


def test_move_within_a_column_downwards(client, make_user, make_application, db_session):
    """La position est l'index FINAL de la carte dans la colonne."""
    user = make_user()
    apps = _make_column(make_application, user, ["A", "B", "C", "D"])
    _move(client, user, apps["D"]["id"], "saved", 2)
    assert _titles(client, user) == ["C", "B", "D", "A"]
    assert_positions_are_coherent(db_session)


def test_move_to_another_column_at_a_given_position(client, make_user, make_application, db_session):
    """Exemple de la demande : déposer en TROISIÈME position de « Postulée »."""
    user = make_user()
    apps = _make_column(make_application, user, ["A", "B"])
    for t in ["P1", "P2", "P3", "P4"]:
        created = make_application(user, title=t)
        _move(client, user, created["id"], "applied", 99)  # chacune en fin de colonne
    assert _titles(client, user, status="applied") == ["P1", "P2", "P3", "P4"]

    response = _move(client, user, apps["A"]["id"], "applied", 2)
    assert response.status_code == 200
    assert response.json()["status"] == "applied"
    assert _titles(client, user, status="applied") == ["P1", "P2", "A", "P3", "P4"]
    assert _titles(client, user, status="saved") == ["B"]
    assert_positions_are_coherent(db_session)


def test_move_into_an_empty_column(client, make_user, make_application, db_session):
    user = make_user()
    apps = _make_column(make_application, user, ["A"])
    assert _move(client, user, apps["A"]["id"], "accepted", 0).status_code == 200
    assert _titles(client, user, status="accepted") == ["A"]
    assert_positions_are_coherent(db_session)


def test_move_beyond_the_end_is_clamped_to_the_end(client, make_user, make_application, db_session):
    """Un onglet en retard peut viser un index qui n'existe plus : la carte va en
    fin de colonne plutôt qu'en erreur (décision validée)."""
    user = make_user()
    apps = _make_column(make_application, user, ["A", "B", "C"])
    assert _move(client, user, apps["C"]["id"], "saved", 250).status_code == 200
    assert _titles(client, user) == ["B", "A", "C"]
    assert_positions_are_coherent(db_session)


def test_move_to_its_current_place_is_accepted_and_changes_nothing(
    client, make_user, make_application, db_session
):
    user = make_user()
    apps = _make_column(make_application, user, ["A", "B", "C"])
    assert _move(client, user, apps["B"]["id"], "saved", 1).status_code == 200
    assert _titles(client, user) == ["C", "B", "A"]


def test_move_does_not_touch_the_neighbours_updated_at(
    client, make_user, make_application, db_session
):
    """Décaler une voisine n'est pas la modifier : son updated_at est conservé.
    La carte déplacée, elle, est modifiée (comme lors d'un changement de statut)."""
    user = make_user()
    apps = _make_column(make_application, user, ["A", "B", "C"])
    before = {t: _stored(db_session, a["id"]).updated_at for t, a in apps.items()}
    _move(client, user, apps["A"]["id"], "saved", 0)
    after = {t: _stored(db_session, a["id"]).updated_at for t, a in apps.items()}
    assert after["B"] == before["B"]
    assert after["C"] == before["C"]


def test_move_only_affects_the_owner_columns(
    client, make_user, make_application, make_board, db_session
):
    """Les colonnes des autres tableaux et des autres utilisateurs ne bougent pas."""
    alice, bob = make_user(), make_user()
    other = make_board(alice)
    a = _make_column(make_application, alice, ["A", "B"])
    _make_column(make_application, alice, ["O1", "O2"], board_id=other)
    _make_column(make_application, bob, ["X", "Y"])

    _move(client, alice, a["A"]["id"], "saved", 0)
    assert _titles(client, alice, board_id=other) == ["O2", "O1"]
    assert _titles(client, bob) == ["Y", "X"]
    assert_positions_are_coherent(db_session)


def test_move_an_archived_application_is_refused(client, make_user, make_application, db_session):
    user = make_user()
    a = make_application(user)
    client.post(f"/applications/{a['id']}/archive", headers=user.headers)
    response = _move(client, user, a["id"], "saved", 0)
    assert response.status_code == 409
    assert response.json()["detail"] == "Une candidature archivée ne se déplace pas dans le kanban."
    assert _stored(db_session, a["id"]).position is None


def test_move_someone_elses_application_is_404(client, make_user, make_application, db_session):
    alice, bob = make_user(), make_user()
    a = _make_column(make_application, alice, ["A", "B"])
    response = _move(client, bob, a["A"]["id"], "saved", 0)
    assert response.status_code == 404
    assert _titles(client, alice) == ["B", "A"]


def test_move_requires_authentication(client, make_user, make_application):
    user = make_user()
    a = make_application(user)
    response = client.post(f"/applications/{a['id']}/move", json={"status": "saved", "position": 0})
    assert response.status_code == 401


@pytest.mark.parametrize(
    "body",
    [
        {"status": "saved", "position": -1},
        {"status": "saved", "position": MAX_APPLICATIONS_PER_USER},
        {"status": "saved", "position": 10**12},
        {"status": "saved", "position": None},
        {"status": "saved"},
        {"position": 0},
        {"status": None, "position": 0},
        {"status": "rejected", "position": 0},
        {"status": "saved", "position": 1.5},
    ],
)
def test_move_rejects_malformed_bodies_with_422(client, make_user, make_application, body):
    user = make_user()
    a = make_application(user)
    response = client.post(f"/applications/{a['id']}/move", json=body, headers=user.headers)
    assert response.status_code == 422, response.text
    assert isinstance(response.json()["detail"], str)


def test_move_position_error_message_names_the_field(client, make_user, make_application):
    user = make_user()
    a = make_application(user)
    response = _move(client, user, a["id"], "saved", -1)
    assert response.json()["errors"][0]["field"] == "position"
    assert response.json()["detail"].startswith("La position")


def test_move_does_not_accept_the_position_through_patch(client, make_user, make_application, db_session):
    """`position` n'est PAS un champ du PATCH : seul /move la choisit. Un champ
    inconnu est ignoré (comportement Pydantic par défaut du projet)."""
    user = make_user()
    apps = _make_column(make_application, user, ["A", "B", "C"])
    client.patch(f"/applications/{apps['A']['id']}", json={"position": 0}, headers=user.headers)
    assert _titles(client, user) == ["C", "B", "A"]


def test_position_is_not_exposed_by_the_api(client, make_user, make_application):
    user = make_user()
    created = make_application(user)
    assert "position" not in created
    listed = client.get("/applications", headers=user.headers).json()
    assert "position" not in listed[0]


# ---------------------------------------------------------------------------
# Réparation : lignes sans position ou incohérentes (ancien code pendant le
# déploiement, SQL manuel, insertion directe)
# ---------------------------------------------------------------------------


def _insert_raw(db_session, board_id, title, *, position, status="SAVED", updated_at="2026-01-01 00:00:00"):
    db_session.execute(
        text(
            "INSERT INTO applications (title, company, source, status, board_id, position, "
            "created_at, updated_at) VALUES (:t, 'c', 'manual', :s, :b, :p, :u, :u)"
        ),
        {"t": title, "s": status, "b": board_id, "p": position, "u": updated_at},
    )
    db_session.commit()


def test_rows_without_position_are_listed_at_the_top(client, make_user, make_application, db_session):
    """Une candidature active créée par l'ANCIEN code pendant le déploiement n'a pas
    de position : elle s'affiche en haut (la règle d'arrivée), les plus récentes
    d'abord."""
    user = make_user()
    _make_column(make_application, user, ["A", "B"])
    _insert_raw(db_session, user.default_board_id, "Old1", position=None, updated_at="2026-01-01 00:00:00")
    _insert_raw(db_session, user.default_board_id, "Old2", position=None, updated_at="2026-01-02 00:00:00")
    assert _titles(client, user) == ["Old2", "Old1", "B", "A"]


def test_next_write_in_a_column_repairs_missing_and_duplicate_positions(
    client, make_user, make_application, db_session
):
    """La numérotation se répare à la prochaine écriture dans la colonne : NULL,
    doublons et trous redeviennent 0..n-1, dans l'ordre jusque-là affiché."""
    user = make_user()
    apps = _make_column(make_application, user, ["A", "B"])  # B=0, A=1
    _insert_raw(db_session, user.default_board_id, "Null", position=None)
    _insert_raw(db_session, user.default_board_id, "Dup", position=1, updated_at="2030-01-01 00:00:00")
    _insert_raw(db_session, user.default_board_id, "Gap", position=7)
    shown = _titles(client, user)
    assert shown == ["Null", "B", "Dup", "A", "Gap"]

    make_application(user, title="New")
    assert _titles(client, user) == ["New", *shown]
    assert_positions_are_coherent(db_session)


def test_sorting_is_by_position_not_by_last_modification(client, make_user, make_application, db_session):
    """Garde du changement de tri : une date de modification récente ne fait plus
    remonter une carte."""
    user = make_user()
    apps = _make_column(make_application, user, ["A", "B"])
    db_session.execute(
        text("UPDATE applications SET updated_at = :u WHERE id = :id"),
        {"u": "2099-01-01 00:00:00.000000", "id": apps["A"]["id"]},
    )
    db_session.commit()
    assert _titles(client, user) == ["B", "A"]
