# Décisions en attente

Trois décisions appartiennent au propriétaire du framework, pas au code. Elles
sont documentées ici avec leurs conséquences mesurées, pour être tranchées
plutôt que subies.

Chacune est **actuellement subie** : le code a une valeur par défaut, et cette
valeur produit un comportement que personne n'a choisi.

---

## Décision 1 — `ADOPTED_FROM` : le gate gouverne-t-il déjà ?

**État actuel.** `ADOPTED_FROM = "2026-08-30"`. Le gate 10 dimensions est donc
**autoritaire depuis le 30 août**, par simple passage de date.

**Le problème.** Le spec prévoyait que l'adoption se fasse *à l'édition
mensuelle du 30 août*, accompagnée des prédictions Part D de septembre et de
la notation Part E d'août. Cette cérémonie n'a pas eu lieu. Le gate est
devenu autoritaire tout seul, et trois de ses seuils étaient des valeurs par
défaut provisoires à ce moment-là.

### Option A — laisser tel quel

| Pour | Contre |
|---|---|
| Le gate accumule de l'historique en conditions réelles | Il gouverne avec des seuils non validés |
| Pas de changement à faire | La cérémonie D/E qui donne sa valeur au cadre a été sautée |
| Le gate lit 4/8 pour un seuil de 5 — il ne tire pas aujourd'hui | Un signal de plus et il tire, sur une base non validée |

### Option B — reculer `ADOPTED_FROM` à la prochaine édition mensuelle

| Pour | Contre |
|---|---|
| Restaure la discipline que tout le reste du cadre applique | Un mois de plus en mode ombre |
| L'adoption est alors elle-même notée par le cycle D/E | Aucun coût réel : le gate ne tire pas actuellement |
| Le temps de trancher la décision 2 avant qu'elle ne morde | — |

**Recommandation : option B.** Le coût est nul — le gate ne tire pas
aujourd'hui — et le bénéfice est de restaurer la règle qui gouverne tout le
reste. Une adoption par calendrier est exactement le type de dérive
silencieuse que le spec interdit ailleurs.

C'est une ligne : `ADOPTED_FROM` dans `scripts/dimensions.py`.

---

## Décision 2 — Le seuil : 5 sur 8, ou autre chose ?

**État actuel.** `TIER_A_THRESHOLD = 5`, sur une base passée de 9 à 8 quand
Fear & Greed a été rétrogradé.

**Le problème.** Le seuil est resté pendant que la base rétrécissait. Le gate
est donc passé de 55,6 % à **62,5 %** de votes requis. **Ce durcissement n'a
pas été choisi, il a été hérité.**

### Ce que le backtest dit sur la sévérité

Mesuré sur 1366 jours, sur les quatre signaux Tier A ayant un historique :

| Barre | Fréquence de déclenchement |
|---|---|
| équivalent 4 sur 9 | **36,8 %** des jours |
| équivalent 5 sur 9 | **5,3 %** des jours (~19 j/an) |
| les 4 signaux ensemble | **0 jour sur 1366** |

### Option A — garder 5 sur 8 (62,5 %)

| Pour | Contre |
|---|---|
| Une porte ouverte un tiers du temps n'est pas une porte | Plus strict que ce que le spec avait calibré |
| Le côté vente n'ayant jamais été testé, l'asymétrie justifie la sévérité | Le durcissement reste non intentionnel, même si on le ratifie |
| ~19 déclenchements/an est une cadence plausible pour un appel de régime | — |

### Option B — descendre à 4 sur 8 (50 %)

| Pour | Contre |
|---|---|
| Restaure approximativement la difficulté du spec | Le backtest suggère un déclenchement très fréquent |
| Cohérent avec une base de signaux moins corrélée | Une porte trop lâche produit du churn — que l'échelle absorbe, mais pas le gate |

### Option C — passer à 5 sur 9 en promouvant un signal suivi

| Pour | Contre |
|---|---|
| Restaure la base d'origine | **Aucun signal suivi ne passe la règle d'adoption** |
| — | Promouvoir sans preuve viderait la règle de son sens |

**Recommandation : option A, mais ratifiée explicitement.** Garder 5, et
écrire dans le code que le durcissement est désormais *choisi* et non hérité.
L'option C est exclue tant que la règle d'adoption n'est pas satisfaite par un
candidat — et aujourd'hui aucun ne l'est.

**Ne pas monter à 6.** L'état de preuve maximale n'est pas survenu une seule
fois en quatre ans.

---

## Décision 3 — Acheter la donnée qui débloque le sell gate

**État actuel.** Le sell gate ne peut pas fonctionner : deux de ses trois
Tier-1 sont illisibles. C'est le seul mécanisme qui protège le capital, et le
seul qui n'a jamais tourné.

### Option A — Coinglass, palier HOBBYIST, 29 $/mois

L'endpoint `bull-market-peak-indicator` est inclus **dans tous les paliers**,
vérifié dans leur documentation. Il rend pour chaque indicateur : valeur
actuelle, valeur cible, valeur précédente, variation, et `hit_status`.

| Pour | Contre |
|---|---|
| Format directement exploitable : « N indicateurs de sommet atteints » | Ce sont **leurs** seuils, backtestés par personne ici |
| 29 $/mois, le prix d'entrée le plus bas des options | Mise à jour quotidienne seulement, pas intraday |
| Contient Pi Cycle Top, que le cadre a déjà en Tier B | 30 indicateurs de plus multiplient le problème des comparaisons multiples |
| Alimente le sell gate, le plus gros trou du système | N'apporte **pas** LTH supply, qui reste le Tier-1 manquant |

### Option B — Glassnode ou CryptoQuant pour LTH supply

| Pour | Contre |
|---|---|
| Débloque directement le Tier-1 n°1 du sell gate | Nettement plus cher (souvent 100 $+/mois pour les métriques LTH) |
| Une métrique précise plutôt qu'un agrégat | Ne résout pas le Tier-3 (flux ETF) |
| Rend la règle 2-sur-3 atteignable | À vérifier : la métrique exacte est-elle dans le palier d'entrée ? |

### Option C — ne rien acheter

| Pour | Contre |
|---|---|
| Zéro coût | Le mécanisme de protection du capital reste inopérant |
| Cohérent avec « la preuve plafonne de toute façon » | Le côté achat vient de s'activer pour la première fois |

**Recommandation : option A d'abord, en mode suivi.** 29 $/mois est le
meilleur euro du système — mais **inscrire les indicateurs Coinglass comme
`track`, pas comme Tier-1.** Leurs seuils n'ont pas franchi la règle
d'adoption, et les adopter d'office viderait cette règle de son sens le
lendemain de son écriture.

Ils construisent de l'historique pendant qu'on les évalue. C'est exactement la
séquence qui a été appliquée au gate 10 dimensions.

---

## Ce qu'aucune de ces décisions ne change

Aucune ne rend les signaux prédictifs. Le plafond de preuve à ~6,0 tient :
deux cycles datables, et l'ère post-ETF est le jeu de test.

Ces décisions rendent le système **cohérent et intentionnel**. Elles ne le
rendent pas validé.
