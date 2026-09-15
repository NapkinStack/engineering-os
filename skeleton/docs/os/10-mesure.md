# 10 — Mesure et amélioration

## 1. À quoi servent les métriques

> Les métriques servent à améliorer le système, pas à produire des objectifs artificiels.

Toute métrique transformée en objectif individuel cesse de mesurer ce qu'elle mesurait.
Les indicateurs de ce document se lisent au niveau du **système** : ils servent à
répondre à « où ça grince ? », jamais à « qui est performant ? ».

**Ne jamais optimiser la quantité de code produite.** C'est la seule métrique que les
agents font exploser sans effort, et elle est inversement corrélée à ce qu'on cherche.

---

## 2. Les quatre familles

```mermaid
flowchart TB
    subgraph F1["FLUX — est-ce que ça avance ?"]
        A1["Lead time"]
        A2["Fréquence de livraison"]
        A3["Taille des changements"]
        A4["Temps de review"]
        A5["Temps de feedback CI"]
    end

    subgraph F2["STABILITÉ — est-ce que ça tient ?"]
        B1["Taux d'échec des changements"]
        B2["Temps de récupération"]
        B3["Incidents"]
        B4["Tests flaky"]
    end

    subgraph F3["FRONTIÈRES — est-ce que ça reste découplé ?"]
        C1["Taux de PR cross-module"]
        C2["Stabilité des interfaces"]
        C3["Contractions en retard"]
        C4["Violations de fitness functions"]
    end

    subgraph F4["VALEUR — est-ce que ça sert ?"]
        D1["Critères de succès atteints"]
        D2["Fonctionnalités retirées"]
        D3["Charge cognitive perçue"]
        D4["Temps jusqu'à 1re contribution"]
    end

    style F3 fill:#1f2937,color:#fff
    style F4 fill:#065f46,color:#fff
```

Les familles 1 et 2 sont classiques. Les deux autres sont spécifiques à cet OS et à mon
sens les plus informatives ici.

---

## 3. Les indicateurs qui comptent vraiment

### Taux de PR cross-module

**Le meilleur indicateur de qualité des frontières.** Il est collecté gratuitement,
puisqu'une PR cross-module nécessite un label explicite (`02-modules.md` §7).

| Tendance | Interprétation |
|---|---|
| Faible et stable | Les frontières tiennent |
| En hausse | Une frontière se dégrade — regarder quelle paire de modules revient |
| Concentré sur deux modules | Ces deux modules devraient probablement être fusionnés, ou découpés autrement |

### Taux de PR hors budget de revue

Mesure la pression réelle de la génération sur la capacité de vérification
(`05-workflow.md` §4). Une hausse signifie qu'on produit plus vite qu'on ne vérifie, et
que la qualité de la revue se dégrade silencieusement — bien avant que les incidents
n'augmentent.

### Contractions en retard

Nombre de versions de contrat dépréciées dont la date de retrait est dépassée
(`03-contrats.md` §4). C'est la mesure directe des **états intermédiaires permanents**.
Elle ne devrait jamais croître durablement.

### Temps de feedback CI

Une CI lente n'est pas seulement désagréable : elle est **contournée**. Au-delà d'un
certain seuil, les développeurs cessent de lancer les checks localement, poussent pour
voir, et ignorent les résultats. La vitesse du feedback est une propriété de qualité,
pas de confort.

### Critères de succès atteints

Proportion des décisions dont le critère daté a été vérifié à l'échéance
(`06-decisions.md` §5). Si cette proportion est faible ou inconnue, la documentation
décisionnelle est décorative.

### Fonctionnalités retirées

Un projet qui ne retire jamais rien accumule. Ce n'est pas un indicateur à maximiser,
mais un indicateur **qui ne doit pas rester à zéro** indéfiniment.

---

## 4. La boucle de feedback après incident

```mermaid
flowchart TD
    A["Anomalie significative"] --> B["Corriger l'effet<br/>rétablir le service"]
    B --> C["Identifier la cause réelle"]
    C --> D{"POURQUOI le système<br/>ne l'a-t-il pas détecté ?"}

    D --> E1["Aucun test ne couvrait ce cas"]
    D --> E2["Une règle existait mais<br/>seulement dans le prompt"]
    D --> E3["Une frontière a été franchie<br/>sans être détectée"]
    D --> E4["Le contrat ne couvrait pas<br/>ce comportement"]
    D --> E5["La gate existait mais<br/>a été contournée"]

    E1 --> F["Ajouter le test"]
    E2 --> G["AUTOMATISER la règle<br/>puis la retirer du prompt"]
    E3 --> H["Ajouter une fitness function"]
    E4 --> I["Étendre le contract test"]
    E5 --> J["La gate est mal conçue :<br/>la corriger, pas blâmer"]

    F --> K["Le même bug ne peut<br/>plus revenir silencieusement"]
    G --> K
    H --> K
    I --> K
    J --> K

    K --> L["Mettre à jour la<br/>documentation impactée"]

    style D fill:#7c2d12,color:#fff
    style K fill:#065f46,color:#fff
```

> **Ne pas simplement corriger un bug : améliorer le système qui a permis au bug de
> passer.**

La question `D` est la seule qui compte réellement. Un post-mortem qui s'arrête à la
cause technique produit une correction ; un post-mortem qui répond à « pourquoi le
système ne l'a-t-il pas vu ? » produit un garde-fou.

> Objectif : **transformer les erreurs passées en garde-fous futurs.**

Noter le traitement du cas `E5` : quand une gate a été contournée, le réflexe de blâmer
l'individu est une impasse. Une gate systématiquement contournée est une gate mal
conçue — trop lente, trop bruyante, ou sans valeur perçue (`07-gouvernance.md` §5).

---

## 5. Les rituels

Trois rendez-vous suffisent. Tous produisent une décision, jamais un simple constat.

| Rituel | Fréquence | Contenu | Sortie |
|---|---|---|---|
| **Revue de frontières** | Mensuelle | PR cross-module, violations de fitness functions, contractions en retard | Issues *Architecture*, ou rien |
| **Revue de décisions** | Trimestrielle | ADR/PDR dont le critère est arrivé à échéance | Confirmée · supersédée · fonctionnalité retirée |
| **Revue du backlog d'automatisation** | Trimestrielle | Règles qui vivent encore dans le prompt | Automatiser · supprimer · reconduire avec échéance |

Les deux dernières peuvent se tenir ensemble : elles traitent le même sujet vu de deux
côtés — ce qui aurait dû quitter le prompt, et ce qui aurait dû quitter le produit.

---

## 6. Amélioration de l'OS lui-même

L'OS est soumis à ses propres règles. En particulier :

**Le kernel a un budget.** 250 lignes. Ajouter une règle impose d'en retirer une autre
ou de l'automatiser. Sans cette contrainte, le kernel grossit à chaque incident et
redevient le document de 6 000 mots qu'il remplace.

**Toute règle du prompt est candidate à l'automatisation.** Sa présence dans le kernel
ou un playbook est un état transitoire, documenté dans le backlog d'automatisation avec
une échéance prévue.

**Un changement structurant de l'OS passe par un ADR.** Ajouter un format de document,
un playbook, une loi au kernel, ou changer le budget de revue sont des décisions
structurantes.

**Les signaux qui doivent déclencher une révision de l'OS :**

| Signal | Ce qu'il indique |
|---|---|
| Une règle du kernel n'est jamais suivie | Elle est mal formulée, ou pas au bon endroit |
| Un playbook n'est jamais déclenché | Le déclencheur est mal défini, ou le playbook est inutile |
| Une exception est devenue la norme | La règle ne correspond pas à la réalité du projet |
| Les agents remontent souvent le même blocage | Le système a un défaut structurel, pas les agents |
| Le kernel dépasse son budget | Une automatisation a été repoussée trop longtemps |

---

## 7. Le critère ultime

> Un nouveau développeur, une nouvelle équipe ou un nouvel agent doit pouvoir
> comprendre rapidement **ce qu'il doit savoir, ce qu'il peut modifier, ce qu'il ne doit
> pas modifier, et comment vérifier que son travail est correct.**

Si ce n'est pas possible, le problème est architectural, documentaire ou
organisationnel — **pas uniquement un problème de code**.

```
Construire vite.
Construire petit.
Construire avec des frontières.
Reprendre ce qui existe.
Documenter les décisions.
Automatiser les règles.
Vérifier systématiquement.
Faire évoluer l'architecture continuellement.
```
