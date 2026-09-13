# PRODUCT — NapkinStack

> **Ce fichier n'a pas sa place dans un projet client.** S'il est présent dans un dépôt
> créé à partir du template, c'est une erreur d'installation : supprime-le.
> `nstack doctor` le signale.
>
> Il décrit ce qu'est le produit et comment travailler **sur** l'OS, pas **avec** lui.
> À lire en premier par tout humain ou agent qui contribue ici.

---

## 1. Le double rôle de ce dépôt

Ce dépôt est **le produit NapkinStack**. Ce n'est pas un projet qui utilise l'OS : c'est
l'OS lui-même, celui qui sera copié comme racine de projets futurs.

Il est aussi son **premier utilisateur**. Un socle qui ne tient pas ses propres règles
ne tiendra chez personne.

D'où une règle de désambiguïsation à garder en tête en permanence :

| Quand tu lis… | Comprends… |
|---|---|
| `AGENTS.md`, `playbooks/`, `docs/os/` | Le **livrable**. Ce que liront les clients. On l'édite comme on édite un produit. |
| `platform/`, `.github/`, `contracts/` | Le **produit outillé**. Le code de NapkinStack. |
| Ce fichier, `docs/governance/` | Le **contexte de travail**. Il ne part pas chez le client. |

Un agent qui travaille ici n'est donc **pas** dans le cas nominal décrit par le kernel
(« tu travailles dans un seul module »). Il n'y a pas encore de modules. Les règles qui
s'appliquent réellement à toi sont en §5.

---

## 2. Ce que NapkinStack vend

**Le problème client.** Les agents rendent l'écriture de code quasi gratuite. Trois
coûts ne baissent pas : comprendre, vérifier, coordonner. Une équipe qui branche un
agent sur un dépôt sans frontières ne produit pas plus vite — elle produit plus vite
quelque chose que personne ne peut relire.

**La promesse.** Plusieurs équipes, et leurs agents, travaillent en parallèle sur des
modules différents sans réunion de synchronisation, et sans que la qualité dépende de
la vigilance de quiconque.

**Le mécanisme.** Trois idées, et elles seules :

1. Le **module** est l'unité de parallélisme. Deux modules ne se connaissent que par
   leur contrat.
2. Le **prompt est une zone de transit**. Toute règle automatisable descend en CI et
   quitte le prompt.
3. L'**oracle avant la génération**. Le critère de réussite est exécutable avant la
   première ligne.

**Ce qu'on ne vend pas.** Ni stack, ni framework, ni architecture interne, ni liste
d'outils. NapkinStack fournit la couche qui permet à **la stack du client** de tenir à
plusieurs équipes.

---

## 3. Les utilisateurs

| Utilisateur | Ce qu'il doit pouvoir faire | Critère de réussite |
|---|---|---|
| **Tech lead** qui démarre un projet | Créer un dépôt conforme et un premier module | < 30 min, sans lire tout le manuel |
| **Développeur** qui rejoint une équipe | Contribuer utilement | Sans conversation orale |
| **Agent IA** sur une tâche | Travailler borné, être bloqué s'il dérive | PR non mergeable plutôt que dette dans `main` |
| **Deuxième équipe** qui arrive | Avancer sans bloquer la première | Zéro réunion de synchronisation |

Ces quatre critères sont les tests d'acceptation du produit. Une modification qui en
dégrade un est un échec, quelle que soit son élégance.

---

## 4. Invariants produit

Non négociables. Une PR qui en viole un est refusée, même si tout le reste est vert.

| # | Invariant | Pourquoi |
|---|---|---|
| P1 | **Aucune stack imposée** — ni langage, ni framework, ni base | La plateforme orchestre, elle ne connaît aucune stack. Toute logique spécifique à un écosystème dans `platform/` est un bug. |
| P2 | **Portabilité des règles** — `AGENTS.md`, `playbooks/`, `docs/os/` restent en markdown générique | Un client doit pouvoir utiliser l'OS avec un autre agent que Claude. Un outil est un adaptateur, jamais une fondation. |
| P3 | **L'enforcement reste en CI** — jamais dans un hook, jamais dans un plugin | Un hook est contournable. Le confondre avec une garantie fait repousser le vrai check. |
| P4 | **Kernel sous budget** — 250 lignes | Sans plafond, il regrossit à chaque incident et redevient le document illisible qu'il remplace. |
| P5 | **Tout check a un test qui prouve qu'il échoue** | Un garde-fou qui ne sait pas échouer ne garde rien. |
| P6 | **Message d'échec explicatif** — règle, fichier, ligne, action | Un check qui dit « violation » sera contourné. |
| P7 | **Branding en périphérie** — `platform/`, CLI et distribution portent la marque ; les règles restent génériques | Personne n'adopte un cadre de travail qui porte le nom d'un fournisseur dans chaque fichier. |

---

## 5. Comment travailler sur ce dépôt

Le kernel `AGENTS.md` reste ta référence de **méthode** — oracle d'abord, changement
minimal, résumé en cinq blocs, arrêt sur action à haut risque. Trois adaptations :

**« Un module » se lit « un chantier ».** Il n'y a pas de modules ici. L'unité de lot
est le chantier listé dans `docs/governance/chantiers.md`. Un chantier, une PR, un
commit. Jamais deux chantiers ensemble.

**L'oracle, ici, c'est `platform/tests/run.sh`.** Pour chaque nouveau contrôle, écris
d'abord le cas qui prouve qu'il échoue quand la règle est violée, et vois-le échouer.
Le pattern existe déjà dans ce fichier.

**Le « client » est fictif mais exigeant.** Avant chaque changement, demande-toi lequel
des quatre utilisateurs du §3 en bénéficie, et comment on le saura. Une amélioration qui
ne sert aucun d'eux n'est pas une amélioration.

## 6. Hors périmètre produit

Ne construis pas, ne propose pas :

- une stack de référence, un module d'exemple, une architecture applicative ;
- un plugin ou un marketplace Claude Code — l'enforcement reste en CI (P3) ;
- des fitness functions au-delà du chantier en cours — les suivantes sont priorisées
  dans `docs/os/07-gouvernance.md` §3, et leur besoin n'est pas démontré ;
- de l'abstraction ou de la configuration pour un usage unique ;
- une interface web, un tableau de bord, un service.

## 7. État actuel

Le socle est complet côté règles. Côté garde-fous, les checks existent mais plusieurs
sont défaillants ou n'ont aucun test qui prouve qu'ils échouent (P5), et le manuel promet
des contrôles qui ne sont pas implémentés. Le produit évolue vers un modèle *framework*,
décision à formaliser dans le PDR-0001. Défauts, décisions et ordre de traitement :
`docs/governance/chantiers.md`.

La roadmap au-delà : ouvrir un premier module réel, et laisser l'usage dicter les
fitness functions suivantes. Rien ne se construit avant d'avoir servi une fois.
