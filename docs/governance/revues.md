# Revues périodiques

> Trois rendez-vous. Chacun produit une **décision**, jamais un simple constat.
> (`docs/os/10-mesure.md` §5)

## Revue de frontières — mensuelle

À regarder :

- taux de PR portant le label `cross-module`, et sur quelle paire de modules
- violations de fitness functions sur la période
- contractions en retard (versions dépréciées non retirées)
- signaux remontés dans les PR : « j'ai dû regarder l'implémentation d'un autre module »

Sortie : issues *Architecture*, ou rien. Quand plusieurs signaux convergent sur la même
paire de modules, la réponse est **fusionner ou redécouper** — jamais ajouter un
contrat de plus.

| Date | Signaux | Décision |
|---|---|---|
| | | |

## Revue de décisions — trimestrielle

Lister les ADR et PDR dont le critère de succès est arrivé à échéance. Pour chacun :
**confirmé**, **supersédé**, ou **fonctionnalité retirée**.

Sans ce rituel, `docs/adr/` devient un cimetière — ce qui est pire qu'une absence de
documentation, parce que ça inspire faussement confiance.

| Date | Décision | Critère | Verdict |
|---|---|---|---|
| | | | |

## Revue du backlog d'automatisation — trimestrielle

Voir `backlog-automatisation.md`. Peut se tenir avec la précédente : les deux traitent
le même sujet vu de deux côtés — ce qui aurait dû quitter le prompt, et ce qui aurait
dû quitter le produit.
