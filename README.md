# 🎤 Agent de surveillance des billets Céline Dion

Cet agent vérifie **toutes les 15 minutes, 24h/24**, les sites de billetterie et de revente pour les concerts de Céline Dion à Paris La Défense Arena (mai 2027). Il vous envoie un **email** dès qu'une nouvelle offre apparaît.

- Il tourne gratuitement sur GitHub. Votre ordinateur peut rester éteint.
- Il ne consomme pas vos limites Claude.
- Sites surveillés : AXS, Ticketmaster, Fnac Spectacles (officiels), ainsi que Viagogo et StubHub (non officiels). Vous pouvez les modifier dans `sites.json`.

---

## Installation (environ 15 minutes, une seule fois)

### Étape 1 : créer un mot de passe d'application Gmail

L'agent a besoin d'un mot de passe spécial pour envoyer des emails depuis votre Gmail. **Ce n'est pas votre mot de passe habituel.**

1. Allez sur https://myaccount.google.com/security
2. Activez la **Validation en deux étapes** si ce n'est pas déjà fait (obligatoire).
3. Allez sur https://myaccount.google.com/apppasswords
4. Donnez un nom, par exemple `Agent Celine`, puis cliquez sur **Créer**.
5. Copiez le code de 16 lettres qui s'affiche et gardez-le pour l'étape 3.

### Étape 2 : créer le dépôt GitHub et y mettre les fichiers

1. Connectez-vous sur https://github.com, puis cliquez sur **+** (en haut à droite) → **New repository**.
2. Nom : `agent-celine`.
3. Choisissez **Public**. Les vérifications automatiques sont alors illimitées et gratuites. Vos mots de passe restent secrets : ils sont stockés à part, à l'étape 3.
4. Cochez **Add a README file**, puis cliquez sur **Create repository**.
5. Dans le dépôt, cliquez sur **Add file → Upload files**. Glissez-y `celine_watch.py`, `sites.json`, `requirements.txt` et `README.md`. Cliquez ensuite sur **Commit changes**.
6. Créez le fichier du planificateur :
   - Cliquez sur **Add file → Create new file**.
   - Dans le nom du fichier, tapez exactement : `.github/workflows/surveillance.yml` (les `/` créent les dossiers automatiquement).
   - Ouvrez le fichier `surveillance.yml` fourni, copiez **tout** son contenu et collez-le.
   - Cliquez sur **Commit changes**.

### Étape 3 : ajouter vos secrets

Dans le dépôt, allez dans **Settings → Secrets and variables → Actions → New repository secret**. Créez ces secrets un par un :

| Nom du secret | Valeur |
|---|---|
| `GMAIL_ADDRESS` | votre adresse Gmail |
| `GMAIL_APP_PASSWORD` | le code de 16 lettres de l'étape 1 |
| `ALERT_TO` | *(facultatif)* une autre adresse où recevoir les alertes |

### Étape 4 : lancer l'agent

1. Ouvrez l'onglet **Actions** du dépôt. Si GitHub le demande, cliquez sur **I understand my workflows, go ahead and enable them**.
2. À gauche, choisissez **Surveillance billets Céline Dion**, puis cliquez sur **Run workflow** → **Run workflow**.
3. Après environ 2 minutes, vous recevez l'email **« 🎤 Agent Céline Dion activé »** avec l'état de chaque site.

Ensuite, l'agent tourne tout seul toutes les 15 minutes.

---

## Les emails que vous recevrez

| Email | Quand |
|---|---|
| 🎤 Agent activé | à la toute première vérification |
| 🎟️ Nouvelle(s) offre(s) détectée(s) | dès qu'une nouvelle ligne avec un prix apparaît sur un site, avec le lien direct |
| ℹ️ Changement d'accès | quand un site se met à bloquer l'agent ou le laisse de nouveau passer |
| 📋 Bilan de la semaine | chaque lundi, pour confirmer que l'agent fonctionne |

L'agent ne vous écrit **pas** quand rien ne change, donc pas de spam.

---

## À savoir

- **Protections anti-robots.** Ticketmaster, Viagogo et StubHub bloquent parfois les visites automatiques. Dans ce cas, vous recevez un email « Changement d'accès » et vous pouvez vérifier à la main avec le lien fourni. Si un site bloque en permanence, désactivez-le dans `sites.json` en mettant `"actif": false`.
- **Pages plus précises.** Les liens par défaut sont des pages de recherche « celine dion ». Pour un résultat plus précis, ouvrez le site dans votre navigateur, allez sur la page de l'événement ou de la revente, copiez l'adresse et remplacez l'`url` correspondante dans `sites.json`. Pour cela, cliquez sur le fichier sur GitHub, puis sur le crayon ✏️, puis sur **Commit changes**.
- **Filtres facultatifs** dans `sites.json` :
  - `"prix_max_euros": 400` pour n'être alerté que sous 400 € ;
  - `"mots_cles_obligatoires": ["mai 2027"]` pour ignorer les lignes qui ne contiennent pas ces mots.
- **Sites non officiels.** Les alertes Viagogo et StubHub portent la mention « site NON officiel ». Les vendeurs agréés sont AXS, Ticketmaster, Fnac Spectacles, Paris La Défense Arena et Event Travel.
- **Arrêter l'agent :** **Actions → Surveillance billets Céline Dion → ⋯ → Disable workflow**.
- **Les emails s'arrêtent ?** Regardez l'onglet **Actions**. Une croix rouge signale une erreur : cliquez dessus pour voir le détail. Le plus souvent, il s'agit d'un mot de passe Gmail mal copié.
