# 02 — Modules et frontières

## 1. La règle fondamentale

> Un développeur ou un agent travaillant sur un module doit pouvoir **comprendre,
> modifier, tester et valider** ce module sans devoir comprendre l'ensemble du système.

C'est la définition opérationnelle d'un module. Tout le reste — granularité, ownership,
contrats, cycle de vie — en découle.

Si cette propriété n'est pas vérifiée, ce n'est pas un module : c'est un dossier.

---

## 2. Ce qui est uniforme, ce qui ne l'est pas

Le piège classique en multi-équipes : pour que tout le monde « travaille de la même
manière », on standardise l'*implémentation* — même framework, mêmes couches, mêmes
patterns internes. Cela produit du couplage par convention, vieillit mal, et empêche
chaque équipe d'adapter son module à son domaine.

Ce que l'on standardise, c'est l'**interface d'ingénierie** du module : la façon dont
on le découvre, le lance, le teste, le valide, le livre.

> Un développeur ou un agent qui change de module retrouve les mêmes **verbes**,
> jamais le même **code**.

```mermaid
flowchart TB
    subgraph P["PLATEFORME — uniforme, imposée, versionnée"]
        direction LR
        P1["Verbes standards<br/>bootstrap · check · test<br/>run · migrate · release"]
        P2["Enveloppe de fichiers<br/>MANIFEST · AGENTS.md<br/>README · docs/ · tests/"]
        P3["Checks obligatoires<br/>identiques partout"]
        P4["Templates issue / PR<br/>DoR · DoD"]
    end

    subgraph M["MODULES — autonomes, hétérogènes à l'intérieur"]
        direction LR
        MA["Module A<br/>équipe 1"]
        MB["Module B<br/>équipe 2"]
        MC["Module C<br/>équipe 1, plus tard"]
    end

    subgraph C["CONTRATS — le seul canal inter-modules"]
        direction LR
        CT["API · événements · schémas<br/>versionnés · testés"]
    end

    P ==>|"impose la forme"| M
    MA -.->|"jamais d'import direct"| MB
    MA --> CT
    MB --> CT
    MC --> CT

    style P fill:#1f2937,color:#fff
    style C fill:#065f46,color:#fff
```

La règle tient en une phrase :

> **Deux modules ne se connaissent que par leur contrat. Deux équipes ne se coordonnent
> que par le contrat. Tout le reste est local.**

### Le partage frontal

| Catégorie | Uniforme ? | Détail |
|---|---|---|
| Verbes de commande | **Oui, imposé** | `09-platform.md` |
| Enveloppe de fichiers | **Oui, imposé** | §4 ci-dessous |
| Checks obligatoires | **Oui, imposé** | `07-governance.md` |
| Format des contrats | **Oui, imposé** | `03-contracts.md` |
| Formats ADR / PDR | **Oui, imposé** | `06-decisions.md` |
| Langage, framework, base de données | Non | Décision locale, ADR si structurante |
| Architecture interne, patterns | Non | Décision locale |
| Stratégie de test détaillée | Non | Guidée par le risque, `08-quality.md` |
| Conventions de nommage internes | Non | Locales, décrites dans l'`AGENTS.md` du module |

**Attention au coût de l'hétérogénéité.** L'autonomie technique n'est pas gratuite :
elle se paie en capacité à prêter main-forte entre équipes, en outillage à maintenir,
en surface de sécurité. La liberté existe, mais un ADR est attendu dès qu'un module
introduit une technologie absente du reste du projet, et le Prior Art Gate s'applique
(`06-decisions.md`).

---

## 3. Granularité : où couper

Ne jamais créer de modules artificiellement petits. Un module représente une
**capacité cohérente**, pas une table, une entité ou quelques endpoints.

```mermaid
flowchart TD
    A["Candidat au découpage"] --> B{"Correspond-il à une capacité<br/>métier cohérente ?"}
    B -->|Non| B1["Ne pas découper.<br/>C'est un détail d'implémentation<br/>d'un module existant."]
    B -->|Oui| C{"Peut-il être compris<br/>et testé seul ?"}

    C -->|Non| C1["Frontière mal placée.<br/>Rechercher la vraie couture<br/>du domaine."]
    C -->|Oui| D{"A-t-il un owner<br/>identifiable ?"}

    D -->|Non| D1["Ne pas créer.<br/>Un module orphelin<br/>devient une dette."]
    D -->|Oui| E{"Son rythme de changement<br/>diffère-t-il du reste ?"}

    E -->|Oui| F["Bon candidat"]
    E -->|Non| G{"Autre raison explicite ?<br/>criticité · isolation · ownership<br/>parallélisme · charge cognitive"}

    G -->|Oui| F
    G -->|Non| G1["Ne pas découper.<br/>Le couplage temporel<br/>rendra les deux inséparables."]

    F --> H["ADR de création<br/>+ MANIFEST + contrat v1"]

    style F fill:#065f46,color:#fff
    style H fill:#065f46,color:#fff
    style B1 fill:#7c2d12,color:#fff
    style C1 fill:#7c2d12,color:#fff
    style D1 fill:#7c2d12,color:#fff
    style G1 fill:#7c2d12,color:#fff
```

Les critères qui déterminent légitimement la granularité : le domaine, le niveau de
couplage, l'ownership, le rythme de changement, la criticité, le besoin d'isolation, et
la charge cognitive.

Le découpage n'est donc **pas uniquement une décision de déploiement**. Il sert aussi à
borner le contexte d'un agent, réduire le rayon d'impact d'un changement, permettre le
travail parallèle et rendre les validations locales fiables.

---

## 4. L'enveloppe d'un module

Structure minimale, identique partout :

```
modules/<nom>/
├── MANIFEST.yaml        ← identité machine-lisible (§5)
├── AGENTS.md            ← instructions IA locales : uniquement le spécifique
├── README.md            ← humain : à quoi ça sert, comment démarrer
├── docs/
│   ├── adr/             ← décisions techniques locales
│   └── runbook.md       ← si module opéré en production
├── contracts/           ← contrats PRODUITS par ce module
├── src/
└── tests/
```

**Règle sur l'`AGENTS.md` local** : il contient uniquement ce qui est spécifique au
module. Ne jamais y dupliquer une règle du kernel. Un `AGENTS.md` local qui répète le
kernel est un bug — il gaspille du contexte et crée un risque de divergence.

Contenu typique d'un `AGENTS.md` local : conventions internes non devinables, pièges
connus, invariants métier, commandes non standards, zones à ne pas modifier et
pourquoi.

---

## 5. Le Module Manifest

C'est la pièce qui rend le multi-équipes opérationnel. Un fichier déclaratif unique,
lisible par un humain, un agent **et la CI**.

Voir `templates/MANIFEST.example.yaml` pour le format complet. Il déclare :

- identité et responsabilité en une phrase ;
- owner (équipe, pas individu) ;
- statut de cycle de vie ;
- niveau de criticité — il détermine le niveau de gouvernance exigé ;
- contrats produits ;
- contrats consommés, avec versions ;
- commandes standards.

### Les trois usages qui justifient son coût

```mermaid
flowchart LR
    MF["MANIFEST.yaml<br/>déclare l'intention"]

    MF --> U1["ONBOARDING<br/>un agent arrivant sur un module<br/>inconnu sait quoi charger,<br/>sans explorer le repo"]

    MF --> U2["FITNESS FUNCTION<br/>graphe déclaré vs graphe réel<br/>extrait du code<br/>→ tout écart = violation"]

    MF --> U3["COORDINATION<br/>matrice producteurs/consommateurs<br/>générée → on sait toujours<br/>qui casse qui"]

    U2 --> CI["CI : check bloquant"]
    U3 --> CI

    style MF fill:#1f2937,color:#fff
    style CI fill:#065f46,color:#fff
```

Le point essentiel : **le manifest déclare l'intention, la CI vérifie la réalité.** Un
import vers un module non déclaré échoue en CI. Une dépendance déclarée mais inutilisée
est signalée. Aucune analyse sémantique n'est nécessaire — c'est une comparaison de
graphes.

---

## 6. Cycle de vie d'un module

Nécessaire dès qu'une équipe travaille séquentiellement sur plusieurs modules : sans
statut explicite, une équipe qui revient sur un module six mois plus tard ne sait pas ce
qu'elle a le droit de casser.

```mermaid
stateDiagram-v2
    [*] --> Proposé
    Proposé --> Actif : ADR de création<br/>manifest + owner + contrat v1

    Actif --> Maintenance : plus d'évolution prévue<br/>owner conservé
    Maintenance --> Actif : nouveau besoin

    Actif --> Déprécié : remplacé par un autre module
    Maintenance --> Déprécié : remplacé ou obsolète

    Déprécié --> Retiré : consommateurs = 0<br/>date butoir atteinte
    Retiré --> [*]

    note right of Actif
        Contrat peut évoluer
        Breaking change = expand/contract
        Checks complets selon criticité
    end note

    note right of Maintenance
        Contrat gelé
        Correctifs et sécurité uniquement
        Reprise = relecture du manifest
    end note

    note right of Déprécié
        Aucun nouveau consommateur
        Date de retrait OBLIGATOIRE
        Check qui échoue si dépassée
    end note
```

Le statut vit dans le manifest, donc il est vérifiable :

| Situation | Résultat CI |
|---|---|
| Module `Maintenance` dont le contrat change | **Rouge** |
| Module `Déprécié` qui gagne un consommateur | **Rouge** |
| Module `Déprécié` dont la date de retrait est dépassée | **Rouge** |
| Module `Actif` sans owner déclaré | **Rouge** |

C'est ce qui évite les **états intermédiaires permanents** : un chemin déprécié qui ne
disparaît jamais parce que personne n'est responsable de sa suppression.

---

## 7. Une PR, un module

C'est la contrainte la plus rentable du système. Objective, automatisable, et chaque
violation devient un signal d'architecture.

**Règle.** Une PR modifie les fichiers d'un seul module. Les exceptions existent mais
sont visibles, tracées et comptées.

| Exception | Traitement |
|---|---|
| Changement de contrat | Séquence expand/contract, jamais une PR unique (`03-contracts.md`) |
| Changement du socle | Fichiers du squelette : équipe socle, revue élargie ; module `platform/` s'il existe (`09-platform.md` §1) |
| Correction d'incident critique | Autorisée, label obligatoire, ADR ou post-mortem sous 5 jours |

Le déblocage passe par un label explicite sur la PR. Cela rend le taux de changements
cross-module **mesurable gratuitement** — c'est l'un des meilleurs indicateurs de
qualité des frontières (`10-measurement.md`).

---

## 8. Dépendances autorisées

```mermaid
flowchart LR
    subgraph A["Module A"]
        AI["implémentation<br/>interne"]
        AC["contrat produit v2"]
    end

    subgraph B["Module B"]
        BI["implémentation<br/>interne"]
        BC["contrat produit v1"]
    end

    subgraph SH["Partagé — autorisé"]
        S1["primitives techniques<br/>sans logique métier"]
        S2["types générés<br/>depuis les contrats"]
    end

    BI -->|"AUTORISÉ<br/>consomme le contrat"| AC
    BI -.->|"INTERDIT<br/>import direct"| AI
    BI -.->|"INTERDIT<br/>accès base d'autrui"| AI
    AI --> S1
    BI --> S1
    BI --> S2

    style AC fill:#065f46,color:#fff
    style SH fill:#1f2937,color:#fff
```

**Interdits, détectables automatiquement :**

- import direct du code interne d'un autre module ;
- accès direct à la base de données d'un autre module ;
- dépendance circulaire entre modules ;
- partage de logique métier entre domaines distincts ;
- base de données partagée sans ADR justificatif.

**Autorisé mais à surveiller :** les primitives techniques partagées (logging, erreurs,
utilitaires sans logique métier). Dès qu'une règle métier entre dans un package
partagé, deux modules deviennent inséparables.

---

## 9. Détecter une mauvaise frontière

Une frontière doit **réduire le coût de changement**. Si elle ne fait que déplacer le
code, elle est mal placée. Ces signaux sont mesurables, pas subjectifs :

| Signal | Comment le mesurer |
|---|---|
| PR nécessitant systématiquement plusieurs modules | Taux de PR cross-module (§7) |
| Modules toujours déployés ensemble | Corrélation des releases |
| Dépendances circulaires | Fitness function sur le graphe |
| Appels synchrones en cascade | Traces de production |
| Contrats trop nombreux entre deux modules | Comptage depuis les manifests |
| Tests nécessitant l'ensemble du système | Durée et périmètre de la suite locale |
| Ownership ambigu | Manifest sans owner, ou PR revue par plusieurs équipes |
| Agent incapable de travailler via le contrat seul | Remontée du kernel §4 |

Le dernier signal est le plus fiable et le moins cher : il est collecté à chaque tâche,
gratuitement, par l'agent lui-même. **Ne jamais le contourner silencieusement.**

Quand plusieurs signaux convergent sur la même paire de modules, ouvrir une issue de
type *Architecture* : la réponse est soit fusionner, soit redécouper autrement, jamais
ajouter un contrat de plus.
