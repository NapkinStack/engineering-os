# ADR-XXXX — <titre court à l'infinitif : « Adopter X », « Découper Y »>

- **Statut** : Proposé | Accepté | Supersédé par ADR-YYYY | Abandonné
- **Date** : AAAA-MM-JJ
- **Décideurs** : <équipe ou personnes>
- **Portée** : projet | module `<nom>`
- **Réversibilité** : facile | coûteuse | irréversible

---

## Contexte

<Ce qui est vrai aujourd'hui et pourquoi la question se pose maintenant. Factuel.
Quelqu'un qui arrive dans six mois doit comprendre la situation sans contexte oral.>

## Problème

<La question à trancher, en une ou deux phrases. Si elle n'est pas formulable en une
question, c'est probablement plusieurs décisions — les séparer.>

## Contraintes

<Ce qui est non négociable et cadre le choix : existant, compétences, exploitation,
sécurité, budget, délai, conformité. Distinguer contraintes réelles et préférences.>

---

## Prior art

> **Section obligatoire.** Minimum deux références nommées. Absence de section ou de
> référence → refusée en revue, en attendant un contrôle automatisé. (`skeleton/docs/os/06-decisions.md` §2)

**Convention dominante du domaine :** <quelle est la réponse standard à ce problème ?>

**Références examinées :**

| Référence | Ce qu'elle fait | Applicable ici ? |
|---|---|---|
| <projet, entreprise, standard> | | |
| <projet, entreprise, standard> | | |

**Pourquoi la convention ne suffit pas** *(à remplir uniquement si l'on s'en écarte)* :

<Le besoin démontré qui justifie l'écart. « Plus propre », « plus flexible »,
« plus moderne » ne sont pas des justifications recevables.>

---

## Options considérées

### Option 1 — <nom>
- Description :
- Avantages :
- Inconvénients :
- Coût de mise en place / de maintenance / **de sortie** :

### Option 2 — <nom>
<idem>

### Option 3 — Ne rien faire
<À évaluer systématiquement. C'est souvent l'option la moins chère et rarement la
plus mauvaise.>

---

## Décision

<L'option retenue, et **pourquoi celle-ci** plutôt que les autres. Pas une répétition
de la description : l'argument qui a tranché.>

### Déviation par rapport à la convention

*(Section obligatoire si la décision s'écarte de la convention identifiée.)*

- **Valeur utilisateur attendue** :
- **Comment on l'observera** :

---

## Critère de succès

*(Obligatoire si la décision construit sur-mesure ou dévie de la convention.)*

> On considérera que c'était le bon choix si **\<observation mesurable\>** est constaté
> avant le **\<AAAA-MM-JJ\>**.

Que fait-on si ce n'est pas le cas : <corriger · superséder · revenir en arrière>

---

## Conséquences

**Positives :**

**Négatives et dette acceptée :**

**Impacts sur d'autres modules ou contrats :**

**Règle à automatiser :** <quelle fitness function ou quel check découle de cette
décision ? Si aucun n'est possible, expliquer pourquoi. `skeleton/docs/os/07-governance.md` §2>

---

## Alternatives rejetées

<Pourquoi elles ont été écartées. Cette section vaut souvent plus que la décision
elle-même : elle évite que quelqu'un repropose dans un an une solution déjà évaluée.>
