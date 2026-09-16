# 07 — Gouvernance

## 1. Le principe

> Si une règle peut être vérifiée automatiquement, elle ne doit **pas** dépendre de la
> vigilance de l'IA ou du développeur.

C'est le passage d'une *gouvernance par inspection* — quelqu'un relit et repère — à une
*gouvernance par règle* : le système refuse l'état invalide.

Corollaire : **une règle importante qui n'est contrôlée que par la mémoire humaine
dérivera.** Pas peut-être, pas si l'équipe est négligente. Elle dérivera.

---

## 2. Où vit cette règle ?

C'est l'arbitrage central de l'OS et il doit être fait explicitement, à chaque nouvelle
règle.

```mermaid
flowchart TD
    A["Nouvelle règle<br/>ou convention"] --> B{"Vérifiable<br/>mécaniquement ?"}

    B -->|Oui| C{"Coût de mise<br/>en place ?"}
    B -->|Non| G{"Structurelle<br/>ou situationnelle ?"}

    C -->|Faible| D["CI : check bloquant<br/>+ hook local pour le feedback"]
    C -->|Élevé| E{"Risque si<br/>violée ?"}

    E -->|Élevé| D
    E -->|Faible| F["Backlog d'automatisation<br/>+ règle temporaire dans un playbook"]

    G -->|Structurelle| H["Frontière : repo, package,<br/>ownership, CODEOWNERS"]
    G -->|Situationnelle| I{"S'applique à<br/>TOUTE tâche ?"}

    I -->|Oui| J["KERNEL<br/>budget strictement limité"]
    I -->|Non| K["PLAYBOOK<br/>chargé par déclencheur"]

    D --> L["RETIRER la règle du prompt"]
    H --> L

    style D fill:#065f46,color:#fff
    style H fill:#065f46,color:#fff
    style J fill:#1f2937,color:#fff
    style L fill:#7c2d12,color:#fff
```

Le nœud `L` est le plus important et le plus oublié : **une fois automatisée, la règle
quitte le prompt**. Sinon le kernel grossit indéfiniment et finit par coûter, à chaque
tâche, plus de contexte qu'il n'en protège.

Le nœud `H` mérite aussi attention : une règle non vérifiable mais structurelle se
résout souvent par la **structure** plutôt que par le texte. « N'importez pas le code de
l'autre module » est une règle faible ; mettre les deux modules dans des packages
distincts avec des dépendances déclarées la rend inutile.

---

## 3. Les fitness functions

> Une règle importante ne doit pas rester dans le prompt ; elle doit devenir un test
> automatisé qui échoue si l'architecture dérive.

C'est le mécanisme qui transforme les principes de cet OS en contraintes réelles.

```mermaid
flowchart LR
    subgraph SRC["Sources — déjà présentes"]
        S1["MANIFEST<br/>des modules"]
        S2["Graphe réel extrait<br/>du code"]
        S3["Contrats<br/>versionnés"]
        S4["Métriques<br/>build & runtime"]
    end

    subgraph FF["Fitness functions"]
        F1["Dépendances :<br/>déclaré = réel"]
        F2["Absence de cycles"]
        F3["Respect des couches"]
        F4["Pas d'accès base<br/>d'un autre module"]
        F5["Contrats : compat.<br/>et consommateurs"]
        F6["Budgets : perf,<br/>taille, temps"]
        F7["Cycle de vie :<br/>statuts et dates"]
    end

    S1 --> F1
    S2 --> F1
    S2 --> F2
    S2 --> F3
    S2 --> F4
    S3 --> F5
    S1 --> F7
    S4 --> F6

    FF --> CI["CI — bloquant"]

    style CI fill:#065f46,color:#fff
    style FF fill:#1f2937,color:#fff
```

### Les fitness functions de base

À mettre en place dès le deuxième module, par ordre de rentabilité :

| # | Fonction | Détecte |
|---|---|---|
| 1 | Graphe déclaré (manifest) = graphe réel (code) | Dépendance cachée, import sauvage |
| 2 | Absence de dépendance circulaire | Modules devenus inséparables |
| 3 | Aucun accès direct aux données d'un autre module | Couplage par la base |
| 4 | Compatibilité ascendante des contrats | Rupture involontaire |
| 5 | Consommateurs d'une version dépréciée = 0 avant retrait | Rupture volontaire mal séquencée |
| 6 | Cohérence des statuts de cycle de vie | Contrat gelé modifié, module déprécié réutilisé |
| 7 | Dates de dépréciation non dépassées | États intermédiaires permanents |
| 8 | Une PR = un module | Érosion des frontières |
| 9 | Enveloppe de module complète (manifest, owner, tests) | Module orphelin |
| 10 | Budgets de performance et de taille | Régression silencieuse |

Les six premières sont peu coûteuses : elles se calculent sur des données déjà
présentes (manifests, imports, schémas de contrats). Il n'y a **aucune analyse
sémantique** — ce sont des comparaisons de graphes et de schémas.

### Écrire une fitness function

Une bonne fitness function est : rapide (elle tourne à chaque PR), déterministe (pas de
faux positifs aléatoires), et **explicative en cas d'échec**. Une fonction qui dit
seulement « violation d'architecture » sera contournée ; une qui dit « le module A
importe `B/internal/x.ts`, or le manifest de A ne déclare pas B ; utilisez le contrat
`b-api@v2` » sera respectée.

---

## 4. Ce qu'il faut automatiser

Par ordre de rentabilité décroissante :

```
Immédiat, coût quasi nul
  format · lint · type checking · détection de secrets · conventions de commit

Dès le 2e module
  tests unitaires · build · fitness functions 1 à 3 · une PR = un module

Dès le 1er contrat inter-équipes
  validation de schéma · contract tests · compatibilité · consommateurs

Dès la mise en production
  analyse de sécurité · dépendances/CVE · smoke tests · vérification post-déploiement

Quand le volume le justifie
  tests d'intégration · E2E ciblés · budgets de performance · merge queue
```

**Les contrôles critiques tournent en CI.** Les hooks locaux donnent un feedback rapide
mais ne sont **jamais** l'unique barrière : ils sont contournables, désactivables, et
absents chez le nouvel arrivant.

---

## 5. Quality gates

Une quality gate doit être : **objective · compréhensible · reproductible · automatisée
si possible · utile**.

Le dernier critère est le plus souvent oublié, et c'est celui qui tue l'adhésion.

| Situation | Réponse |
|---|---|
| Une gate bloque souvent sans jamais améliorer la qualité | La réévaluer ou la supprimer |
| Une règle importante jamais respectée | L'automatiser, la supprimer, ou reconsidérer explicitement |
| Une gate systématiquement contournée par label | Le problème est la gate, pas les gens |
| Une gate lente au point qu'on la saute | La rendre rapide ou la déplacer plus tard dans le pipeline |

> Éviter les gates bureaucratiques sans valeur. Chaque gate a un coût permanent payé par
> toutes les PR ; elle doit être rentable.

**Jamais de contournement silencieux.** Pas de `skip`, pas de `--no-verify`, pas de test
désactivé « temporairement », pas de seuil abaissé pour faire passer. Un contournement
nécessaire passe par un label visible et laisse une trace comptée.

---

## 6. Gouvernance proportionnelle

Le niveau d'exigence dépend de la **criticité déclarée dans le manifest**, pas d'une
règle uniforme. Ne jamais imposer à un petit module la cérémonie d'un système critique ;
ne jamais traiter un système critique comme un prototype.

```mermaid
flowchart TD
    A["Module"] --> B{"Criticité<br/>déclarée"}

    B -->|"Prototype / interne"| P["MINIMAL<br/>lint · types · tests unitaires<br/>manifest · owner"]
    B -->|"Standard"| S["STRUCTURÉ<br/>+ contrats validés · fitness functions<br/>+ ADR structurants · revue"]
    B -->|"Élevée"| E["RENFORCÉ<br/>+ intégration · E2E critiques<br/>+ observabilité · sécurité · runbook"]
    B -->|"Critique / sensible"| C["MAXIMAL<br/>+ revue par l'owner · UAT<br/>+ rollback vérifié · post-déploiement<br/>+ exigences de conformité"]

    style P fill:#1f2937,color:#fff
    style C fill:#7c2d12,color:#fff
```

La criticité est déclarée dans le manifest, donc la CI sait quels checks appliquer à
quel module. Elle n'est pas décidée PR par PR, ce qui éviterait toute discussion au
mauvais moment.

**Elle est révisable**, par ADR : un module qui passe en production change de niveau.

---

## 7. Le repository comme organe de gouvernance

Le dépôt n'est pas un espace de stockage : c'est là que les règles deviennent
non contournables. Mécanismes à utiliser (formulation GitHub, transposable) :

| Mécanisme | Ce qu'il garantit |
|---|---|
| Pull requests obligatoires | Aucun changement direct sur la branche protégée |
| Required checks | Une CI rouge bloque le merge, sans exception |
| CODEOWNERS | Le bon owner est sollicité automatiquement |
| Rulesets / branch protection | Les règles ne dépendent pas de la bonne volonté |
| Issue forms | Le DoR est structurellement rempli |
| PR template | Le DoD est visible au moment de la revue |
| Labels | Les exceptions sont visibles et comptées |
| Environnements protégés | Le déploiement passe par une approbation |
| Dependency / security automation | Les CVE ne dépendent pas d'une veille manuelle |
| Merge queue | Évite les merges qui se cassent mutuellement |

> **Les règles critiques ne doivent pas être contournables par une instruction donnée à
> l'IA.** C'est le test ultime de la gouvernance : si demander gentiment à un agent
> suffit à passer outre, la règle n'existe pas.

---

## 8. Le pipeline CI

Ordre conceptuel, du plus rapide au plus coûteux — le feedback utile arrive tôt.

```mermaid
flowchart TD
    CH["Changement"] --> F1["Format · Lint"]
    F1 --> F2["Types"]
    F2 --> F3["Tests unitaires"]
    F3 --> F4["Build"]
    F4 --> F5["Fitness functions<br/>architecture"]
    F5 --> F6["Contrats :<br/>schéma · compatibilité"]
    F6 --> F7["Sécurité :<br/>secrets · dépendances · SAST"]
    F7 --> F8["Tests d'intégration"]
    F8 --> F9["E2E · visuel · accessibilité<br/>selon criticité"]
    F9 --> AR["Artefact"]
    AR --> DE["Déploiement"]
    DE --> SM["Smoke tests"]
    SM --> OB["Vérification par<br/>l'observabilité"]

    F1 -.->|"échec = arrêt immédiat"| STOP["Feedback < 2 min"]
    F5 -.->|"échec = violation<br/>architecturale"| STOP2["Explication précise<br/>+ règle violée"]

    style F5 fill:#065f46,color:#fff
    style F6 fill:#065f46,color:#fff
    style STOP fill:#1f2937,color:#fff
    style STOP2 fill:#1f2937,color:#fff
```

**Ne pas appliquer mécaniquement toutes les étapes à tous les modules.** Le niveau de
validation est proportionnel au risque (§6).

**Le temps de feedback est une propriété de qualité.** Une CI de trente minutes est une
CI qu'on contourne, qu'on lance en fin de journée, et dont on ignore les résultats. Le
temps de feedback est un indicateur suivi (`10-measurement.md`).

---

## 9. Le backlog d'automatisation

Toute règle qui *devrait* être automatisée mais ne l'est pas encore est une dette
identifiée, pas une fatalité. Elle figure dans un backlog dédié, avec :

- la règle et où elle vit temporairement (playbook, AGENTS.md local) ;
- le risque en cas de violation ;
- le coût estimé d'automatisation ;
- le déclencheur qui la rendra prioritaire.

Ce backlog est revu au même rythme que la revue des décisions (`06-decisions.md` §6).
C'est le mécanisme qui empêche le kernel de grossir : chaque règle ajoutée au prompt
arrive avec sa date de sortie prévue.
