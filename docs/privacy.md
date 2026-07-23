---
title: Politique de confidentialité — Cockpit
---

# Politique de confidentialité — Cockpit

*Dernière mise à jour : 23 juillet 2026*

Cockpit est un outil de suivi de candidatures composé d'une application web et d'une extension de navigateur. Ce document décrit les données traitées, leur finalité et les droits dont vous disposez.

Cockpit est un projet personnel, sans exploitation commerciale. Aucune donnée n'est vendue, louée, ni utilisée à des fins publicitaires. Aucune publicité n'est diffusée dans le service.

---

## Responsable du traitement

Cockpit est édité par un particulier. Pour toute question ou demande relative à vos données : **cockpit.support@gmail.com**

---

## Données collectées

### Compte utilisateur

- **Adresse email** — sert d'identifiant de connexion et permet l'envoi des messages de vérification d'adresse et de réinitialisation de mot de passe.
- **Mot de passe** — jamais conservé en clair. Seule une empreinte cryptographique (bcrypt) est stockée ; elle ne permet pas de retrouver le mot de passe d'origine.
- **Date de création du compte** et statut de vérification de l'adresse email.

### Données que vous saisissez

Les tableaux que vous créez et les candidatures que vous y enregistrez : intitulé du poste, entreprise, lieu, lien vers l'offre, statut d'avancement et notes personnelles. Ces informations proviennent soit de votre saisie, soit des données publiques de l'offre que vous consultez au moment où vous demandez sa capture.

### Données techniques

- Un **jeton de connexion** est stocké localement dans votre navigateur (`localStorage` pour l'application web, `chrome.storage.local` pour l'extension). Il permet de rester connecté, expire automatiquement au bout de 12 heures, et est effacé à la déconnexion.
- Les **journaux du serveur** conservent temporairement les informations techniques usuelles liées aux requêtes.

Cockpit n'utilise **aucun cookie publicitaire**, **aucun traceur** et **aucun outil d'analyse d'audience**.

---

## Ce que fait l'extension de navigateur

L'extension n'observe pas votre navigation. Elle ne s'active que lorsque vous cliquez sur son icône.

À ce moment précis, elle lit le contenu de la page affichée dans l'onglet actif afin d'en extraire les informations de l'offre d'emploi — en priorité les données structurées publiées par le site lui-même (format `JobPosting`). Ces informations vous sont présentées pour correction avant tout enregistrement.

L'extension ne collecte aucun historique de navigation, ne lit aucune page en arrière-plan, et n'accède à aucun site en dehors de l'onglet que vous lui désignez explicitement. Elle ne communique avec aucun serveur autre que celui de Cockpit.

---

## Finalité du traitement

Les données ne sont traitées que pour faire fonctionner le service : authentifier votre compte, afficher et organiser vos candidatures, et vous envoyer les messages nécessaires à la gestion de votre accès (vérification d'adresse, réinitialisation de mot de passe).

Aucun autre usage n'en est fait.

---

## Sous-traitants et localisation des données

| Prestataire | Rôle | Localisation |
|---|---|---|
| Railway | Hébergement de l'application et de la base de données | Union européenne (Pays-Bas) |
| Brevo | Envoi des emails transactionnels | Union européenne (France) |

Vos données sont hébergées dans l'Union européenne. Seule votre adresse email est transmise à Brevo, et uniquement pour l'acheminement des messages liés à votre compte. Vos candidatures ne sont transmises à aucun tiers.

---

## Conservation

Vos données sont conservées tant que votre compte existe, et sont supprimées définitivement lorsque vous le supprimez.

Les jetons de vérification d'adresse et de réinitialisation de mot de passe expirent automatiquement — 60 minutes pour une réinitialisation, 24 heures pour une vérification — et sont invalidés dès leur première utilisation.

---

## Vos droits

Conformément au règlement général sur la protection des données, vous disposez d'un droit d'accès, de rectification, d'effacement, de limitation et de portabilité de vos données.

- **Modifier ou supprimer vos données** — vos tableaux et vos candidatures se modifient et se suppriment directement depuis l'application.
- **Supprimer votre compte** — la page « Mon compte » permet de supprimer votre compte à tout moment. La suppression est immédiate et définitive : elle efface votre compte, vos tableaux, vos candidatures et vos jetons de sécurité. Elle est irréversible.
- **Toute autre demande** — écrivez à **cockpit.support@gmail.com**. Votre demande sera traitée dans les meilleurs délais.

Vous disposez également du droit d'introduire une réclamation auprès de la CNIL.

---

## Sécurité

Les échanges entre votre navigateur et le serveur sont chiffrés (HTTPS). Les mots de passe sont stockés sous forme d'empreinte bcrypt, et les jetons de vérification et de réinitialisation ne sont jamais conservés en clair. Chaque requête est vérifiée côté serveur : vos tableaux et vos candidatures ne sont accessibles qu'à votre compte.

Aucun système n'étant infaillible, ces mesures constituent une obligation de moyens et non de résultat.

---

## Modifications

Cette politique peut évoluer. La date de dernière mise à jour figure en tête de document. En cas de modification substantielle, les utilisateurs disposant d'un compte en seront informés par email.