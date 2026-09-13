# PDR-XXXX — <titre court, orienté utilisateur>

- **Statut** : Proposé | Accepté | Supersédé par PDR-YYYY | Abandonné
- **Date** : AAAA-MM-JJ
- **Décideurs** :
- **Modules impactés** :

> Le PDR décrit **ce que le produit doit faire et pourquoi**, jamais son implémentation.
> Le comment relève d'un ADR.

---

## Problème utilisateur

<Qui a le problème, dans quelle situation, et qu'est-ce qui échoue aujourd'hui ?
Décrire l'utilisateur, pas la fonctionnalité manquante.
Mauvais : « il manque un export CSV ».
Bon : « les comptables reconstituent chaque mois à la main un tableau que le produit
possède déjà, ce qui leur prend une demi-journée et introduit des erreurs ».>

## Objectif

<Ce que l'utilisateur doit pouvoir faire à l'issue. Une phrase.>

## Hors périmètre

<Ce qu'on ne fait délibérément pas. Section la plus utile du document : c'est elle qui
empêche le glissement progressif.>

---

## Prior art

> **Section obligatoire.** Minimum deux références nommées.
> (`docs/06-decisions.md` §2)

**Comment ce problème est-il résolu ailleurs ?**

| Produit / référence | Solution retenue | Ce qu'on en garde |
|---|---|---|
| | | |
| | | |

**Convention que l'utilisateur connaît déjà :** <quel pattern s'attend-il à trouver ?>

**Pourquoi s'en écarter** *(uniquement si l'on s'en écarte)* :

<La valeur utilisateur qui paie le coût d'apprentissage imposé. Sur une interface, la
convention est presque toujours le bon choix — sa valeur vient précisément de ce que
l'utilisateur la connaît déjà.>

---

## Options envisagées

| Option | Ce que vit l'utilisateur | Coût | Retenue ? |
|---|---|---|---|
| Ne rien faire | | 0 | |
| <option 1> | | | |
| <option 2> | | | |

## Décision

<Ce que fait le produit, décrit du point de vue de l'utilisateur. Arbitrages assumés.>

---

## Comportement attendu

**Parcours nominal :**

**Cas limites et états dégradés :**

**Règles métier :**

**Permissions :** <qui peut faire quoi>

**Critères d'acceptation** *(testables — c'est l'oracle de la tâche,
`docs/05-workflow.md` §3)* :

- [ ] Étant donné <contexte>, quand <action>, alors <résultat observable>
- [ ] …

---

## Conception fonctionnelle détaillée *(optionnelle)*

> À remplir uniquement si la fonctionnalité est réellement complexe : nombreux acteurs,
> machine à états, matrice de permissions. Sinon, supprimer cette section.
>
> Elle remplace l'ancien format FDR (`docs/06-decisions.md` §4).

**Acteurs :**
**États et transitions :**
**Matrice de permissions :**
**Interactions avec d'autres modules :**

---

## Critère de succès

> **Section obligatoire.** Sans date, personne ne revient vérifier et le dossier des
> décisions devient un cimetière.

> On considérera que c'était le bon choix si **\<observation mesurable\>** est constaté
> avant le **\<AAAA-MM-JJ\>**.

Comment on l'observe : <métrique, retour utilisateur, usage>

Si le critère n'est pas atteint : <ajuster · superséder · retirer>

---

## Condition de retrait

> **Section obligatoire.** Une fonctionnalité sans condition de retrait est définitive
> par défaut, y compris quand personne ne l'utilise.

> Cette fonctionnalité sera retirée si **\<condition\>**.

---

## Impacts

- **Utilisateurs existants** : <migration, communication, apprentissage>
- **Modules et contrats** :
- **Support et documentation** :
- **Données** : <collecte, rétention, conformité>
