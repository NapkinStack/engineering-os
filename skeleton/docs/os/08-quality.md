# 08 — Qualité et risque

> Ce document est la **référence**. Les règles opérationnelles correspondantes vivent
> dans `playbooks/`, chargés à la demande par un agent.

---

## 1. Le principe commun

Toutes les disciplines de ce document suivent la même règle :

> **On teste, on sécurise, on instrumente selon le risque — jamais selon un objectif
> chiffré arbitraire.**

Un projet à 90 % de couverture dont aucune règle métier critique n'est testée est moins
sûr qu'un projet à 40 % qui couvre les parcours à fort impact. Un objectif chiffré
déplace l'effort vers ce qui est facile à couvrir, c'est-à-dire vers ce qui compte le
moins.

---

## 2. Stratégie de tests

### Priorités

Par ordre décroissant, indépendamment du type de test :

```
1. règles métier
2. parcours critiques
3. permissions et autorisations
4. contrats
5. gestion des erreurs
6. cas limites
7. régressions déjà survenues
8. comportements à fort impact utilisateur
```

### Types et usage

| Type | Utile pour | Piège |
|---|---|---|
| Unitaire | Règles métier, cas limites, pur calcul | Tester des détails d'implémentation qui cassent à chaque refactor |
| Intégration | Interaction avec la base, le système de fichiers, un service | Devenir un E2E déguisé, lent et fragile |
| Contrat | Frontières inter-modules | Absent → le contrat n'est qu'un document |
| Composant | Une unité UI isolée | Sur-mock : on teste le mock |
| E2E | Parcours critiques uniquement | Multiplication → suite lente et flaky |
| Régression visuelle | Design system, composants stables | Faux positifs qu'on finit par ignorer |
| Accessibilité | Toute surface utilisateur | Vérifier l'automatisable seulement, le reste se teste au clavier |
| Performance | Budgets déclarés | Sans budget explicite, ne mesure rien |
| Sécurité | Entrées, authz, dépendances | Ne remplace pas la conception sécurisée |
| Smoke | Post-déploiement | Trop large → on ne sait pas ce qui a cassé |
| UAT | Adéquation au besoin réel | Utilisée comme substitut aux tests techniques |

### Tests flaky

Un test flaky est un **problème d'ingénierie**, jamais une fatalité.

Son coût réel n'est pas le temps perdu à relancer : c'est qu'il apprend à l'équipe à
ignorer un échec de CI. Un seul test flaky toléré dégrade la valeur de **toute** la
suite.

Traitement : isoler, diagnostiquer, corriger ou supprimer. Jamais « relancer jusqu'à ce
que ça passe ». Un test désactivé « temporairement » porte une issue et une date.

Les tests doivent être déterministes autant que possible : pas de dépendance à
l'horloge réelle, à l'ordre d'exécution, au réseau, ou à un état partagé non réinitialisé.

---

## 3. QA — avant le code

La QA commence au cadrage, pas à la livraison. Pour toute fonctionnalité significative,
chercher systématiquement :

```
happy paths · cas limites · entrées invalides · permissions
états inattendus · concurrence · erreurs réseau · erreurs externes
données manquantes ou partielles · régressions possibles
problèmes d'accessibilité · problèmes de compatibilité
```

**Les critères d'acceptation doivent être testables.** Un critère comme « l'interface
est fluide » n'est pas un critère : c'est une intention. Il faut le traduire en
comportement observable, ou reconnaître qu'il n'est pas vérifiable et l'assumer comme
tel.

C'est la même exigence que l'oracle du workflow (`05-workflow.md`), vue côté produit.

---

## 4. UX/UI

Pour toute fonctionnalité exposée à l'utilisateur, analyser au minimum :

| Dimension | Question |
|---|---|
| Parcours | L'utilisateur atteint-il son objectif sans détour ? |
| Compréhension | Sait-il ce qui se passe et ce qu'on attend de lui ? |
| Feedback | Chaque action a-t-elle une réponse perceptible ? |
| Erreurs | Le message dit-il quoi faire, pas seulement ce qui a échoué ? |
| Chargement | Les états d'attente sont-ils traités ? |
| États vides | Le premier usage est-il guidé ? |
| Responsive et mobile | Le comportement tient-il hors du poste de développement ? |
| Accessibilité | Clavier, contraste, lecteurs d'écran, cibles tactiles |
| Cohérence | Est-ce conforme au design system existant ? |
| Performance perçue | Le temps ressenti, pas le temps mesuré |

> **« L'interface fonctionne » n'est pas équivalent à « l'expérience est correcte ».**

Le Prior Art Gate s'applique pleinement ici, et c'est même son terrain le plus
rentable : sur les patterns d'interface, la convention est presque toujours le bon
choix, parce que sa valeur vient précisément du fait que l'utilisateur la connaît déjà.
Une innovation d'interface non demandée est un coût d'apprentissage imposé.

---

## 5. UAT

L'UAT valide que le produit répond **réellement** au besoin attendu.

Elle **ne remplace pas** les tests unitaires, d'intégration, de sécurité ou techniques.
Une UAT utilisée comme filet de sécurité technique est le symptôme d'une suite de tests
insuffisante — et elle arrive trop tard et coûte trop cher pour ce rôle.

Elle part des critères d'acceptation du PDR ou de l'issue et des parcours utilisateurs
réels, pas d'une exploration libre de l'interface.

---

## 6. Sécurité — secure by design

Approche par la conception, pas par l'inspection finale. Selon le risque, considérer :

```
authentification · autorisation · moindre privilège
secrets · validation des entrées · données sensibles · confidentialité
journalisation · audit · dépendances · supply chain
exposition réseau · injections · gestion des fichiers
rate limiting · isolation · sauvegardes · récupération après incident
```

**Règles absolues :**

- **Aucun secret dans le repository.** Jamais. La détection est automatisée, et une
  fuite déclenche une rotation, pas seulement une suppression du commit.
- **Toute entrée externe est hostile** jusqu'à validation.
- **Le moindre privilège par défaut**, y compris pour les agents et la CI.
- Les contrôles automatisables sont **intégrés au cycle de livraison**, pas exécutés
  ponctuellement.

Le détail opérationnel est dans `playbooks/security.md`, chargé dès qu'une tâche touche
à l'authentification, l'autorisation, des secrets, des données personnelles ou des
entrées externes.

---

## 7. Fiabilité et exploitation

Un module destiné à la production doit être **opérable**. Selon sa criticité :

| Capacité | Standard | Élevée | Critique |
|---|---|---|---|
| Logs structurés | ✔ | ✔ | ✔ |
| Gestion des erreurs explicite | ✔ | ✔ | ✔ |
| Health checks | ✔ | ✔ | ✔ |
| Métriques | — | ✔ | ✔ |
| Traces | — | selon besoin | ✔ |
| Alertes | — | ✔ | ✔ |
| Timeouts explicites | ✔ | ✔ | ✔ |
| Retries contrôlés | selon cas | ✔ | ✔ |
| Idempotence | selon cas | ✔ | ✔ |
| SLI / SLO | — | selon besoin | ✔ |
| Runbook | — | ✔ | ✔ |
| Rollback testé | — | ✔ | ✔ |
| Dégradation contrôlée | — | selon besoin | ✔ |

> **Ne jamais ajouter de retries automatiques sans analyser les effets de bord.** Un
> retry sur une opération non idempotente duplique. Un retry sans backoff transforme un
> incident local en panne généralisée. Un retry qui masque une erreur empêche de la
> détecter.

Détail : `playbooks/operations.md`.

---

## 8. Données

**Chaque domaine possède ses données.** Pas de données partagées implicitement, pas
d'accès direct à la base d'un autre module — c'est la forme de couplage la plus
difficile à défaire, parce qu'elle est invisible dans le code.

Toute modification importante de données ou de schéma prend en compte :

```
compatibilité (ancienne et nouvelle version du code coexistent-elles ?)
migration (comment ? combien de temps ? bloquante ?)
données existantes (que deviennent les cas non conformes ?)
rollback ou stratégie de récupération
performance pendant la migration
intégrité · sécurité · observabilité
```

> **Une migration de données est un changement de production, pas une modification de
> code.** Elle relève des actions à haut risque (kernel §5) : risque nommé, impact
> décrit, procédure sûre proposée, confirmation demandée.

Le schéma évolue selon la même logique expand/contract que les contrats
(`03-contracts.md`) : ajouter, faire coexister, migrer, retirer. Jamais renommer en place.

Détail : `playbooks/data-migration.md`.

---

## 9. Dépendances

Avant d'ajouter une dépendance significative, appliquer le **filtre niche**
(`06-decisions.md` §3) : adoption, maintenance, licence et sécurité, **stratégie de
sortie**.

Deux erreurs symétriques, aussi coûteuses l'une que l'autre :

| Erreur | Exemple | Coût |
|---|---|---|
| Dépendance pour du trivial | Une librairie pour trois lignes de code | Surface d'attaque, supply chain, maintenance |
| Réimplémentation du non-trivial | Cryptographie, parsing de dates, authentification | Bugs subtils, failles, temps perdu |

La ligne de partage : **est-ce que ce problème est subtil ?** Le formatage d'une chaîne
ne l'est pas. La gestion des fuseaux horaires, la cryptographie, l'analyse syntaxique et
l'authentification le sont — on prend la convention établie, toujours.

Toute dépendance significative est déclarée dans le manifest du module, avec sa
stratégie de sortie.

---

## 10. Changements architecturaux

Tout changement qui augmente significativement le couplage, le nombre de dépendances,
la surface d'attaque, la complexité opérationnelle, la charge cognitive, la criticité ou
le coût de migration doit être **explicitement évalué** — ADR, avec les alternatives
rejetées.

Deux règles :

**L'architecture évolue par petits pas.** Chaque évolution laisse le système dans un
état au moins aussi cohérent qu'avant. Un grand saut qui laisse le système incohérent
« le temps de finir » ne finit jamais tout à fait.

**Éviter les états intermédiaires permanents.** Quand un nouveau chemin remplace un
ancien, la suppression de l'ancien est planifiée dès le départ, avec une date et un
propriétaire — sinon les deux chemins coexistent indéfiniment, et personne ne sait plus
lequel fait autorité.
