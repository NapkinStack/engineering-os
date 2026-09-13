# AI Engineering OS

Un système de règles, de frontières, de contrats, de documentation et de garde-fous
déterministes permettant à **plusieurs équipes et à des agents IA de développer en
parallèle** sans que la vitesse de génération fasse exploser la complexité.

---

## Le problème que cet OS résout

Les agents rendent l'écriture de code quasi gratuite. Trois coûts, eux, ne baissent pas :

1. **La compréhension** — quelqu'un doit encore savoir ce que fait le système.
2. **La vérification** — quelqu'un doit encore relire et valider.
3. **La coordination** — plusieurs équipes doivent avancer sans se bloquer.

Un accélérateur de génération branché sur un système sans frontières ne produit pas
un projet plus rapide : il produit un projet illisible plus rapidement.

Cet OS traite donc la **charge cognitive**, la **capacité de revue** et le **couplage
inter-équipes** comme les trois ressources rares du projet, et organise tout le reste
autour de leur préservation.

---

## Les cinq idées structurantes

| # | Idée | Conséquence pratique |
|---|------|----------------------|
| 1 | **Le prompt est une zone de transit, pas de résidence** | Toute règle automatisable descend en CI et quitte le prompt |
| 2 | **Le module est l'unité de parallélisme** | Une PR = un module ; deux modules ne se connaissent que par contrat |
| 3 | **L'oracle avant la génération** | On rend le critère exécutable avant d'écrire la première ligne |
| 4 | **La convention est le choix par défaut** | Elle ne se justifie pas ; toute déviation se justifie |
| 5 | **Aucune stack n'est imposée** | L'OS impose une méthode de sélection, pas une liste de technologies |

---

## Carte de navigation

### À lire selon qui vous êtes

| Vous êtes… | Lisez, dans l'ordre |
|-----------|---------------------|
| **Un agent IA** | `AGENTS.md` (kernel) + l'`AGENTS.md` local du module + les playbooks déclenchés |
| **Un nouveau développeur** | `docs/00-vue-ensemble.md` → `docs/02-modules.md` → `docs/05-workflow.md` |
| **Un tech lead / architecte** | `docs/00` → `02` → `03` → `07` |
| **Un product owner** | `docs/00-vue-ensemble.md` → `docs/06-decisions.md` |
| **Celui qui met en place le starter** | `docs/09-plateforme.md` puis tous les `templates/` |

### Contenu

```
.
├── README.md                     ← vous êtes ici
├── AGENTS.md                     ← LE KERNEL : résident, chargé à chaque tâche
│
├── docs/
│   ├── 00-vue-ensemble.md        Architecture de l'OS, les 4 couches, glossaire
│   ├── 01-principes.md           Principes non négociables et anti-patterns
│   ├── 02-modules.md             Frontières, manifest, cycle de vie, une PR = un module
│   ├── 03-contrats.md            Versioning, expand/contract, contract tests
│   ├── 04-contexte-ia.md         Context firewall, budget de contexte, franchissement
│   ├── 05-workflow.md            Boucle verification-first, DoR/DoD, budget de revue
│   ├── 06-decisions.md           ADR/PDR, Prior Art Gate, critères de succès datés
│   ├── 07-gouvernance.md         Où vit une règle, fitness functions, CI, quality gates
│   ├── 08-qualite.md             Tests, sécurité, fiabilité, données, UX, QA, UAT
│   ├── 09-plateforme.md          Verbes standards, arborescence, outillage, onboarding
│   └── 10-mesure.md              Métriques, boucle de feedback, revue des décisions
│
├── playbooks/                    ← modules d'instructions chargés à la demande
│   ├── securite.md
│   ├── tests.md
│   ├── donnees-migration.md
│   ├── ux.md
│   └── exploitation.md
│
└── templates/
    ├── MANIFEST.example.yaml     Manifest de module
    ├── adr.md                    Architecture Decision Record
    ├── pdr.md                    Product Decision Record
    ├── issue-feature.md          Issue form type
    └── pull_request_template.md
```

---

## Règle de lecture des documents

Les documents de `docs/` sont **la référence** : ils expliquent, justifient et
détaillent. Ils ne sont **pas** destinés à être chargés dans le contexte d'un agent.

Ce qu'un agent charge, c'est :

- `AGENTS.md` (kernel, toujours) ;
- l'`AGENTS.md` du module concerné (toujours) ;
- un ou plusieurs `playbooks/` (uniquement si déclenchés).

Si vous avez besoin de mettre une règle dans le kernel, relisez d'abord
`docs/07-gouvernance.md` § « Où vit cette règle ? ». La réponse est très souvent
« en CI », pas « dans le prompt ».

---

## Statut

Cet OS est lui-même soumis à ses propres règles : il évolue par petits pas, ses
changements structurants font l'objet d'un ADR, et toute règle qu'il contient est
candidate à l'automatisation. Voir `docs/10-mesure.md` § « Amélioration de l'OS ».
