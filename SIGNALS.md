# Les signaux et la méthode

Ce document dit trois choses : ce que chaque signal mesure, comment un signal
gagne le droit de voter, et ce que les mesures ont trouvé.

Il est écrit pour être lu avant de faire confiance à un chiffre du pipeline.

---

## 1. Le principe qui gouverne tout le reste

**Un signal qui informe et un signal qui décide sont deux objets différents.**

Les confondre est ce qui a produit un gate à neuf votes dont aucun n'était
validé. Le pipeline sépare donc deux couches :

| Couche | Contenu | Rôle |
|---|---|---|
| **Tableau de bord** | 17 signaux | informer le brief hebdomadaire |
| **Décision** | 8 signaux Tier A | alimenter le gate et l'échelle |

Un signal peut être utile en tableau de bord et incapable de porter un vote.
Fear & Greed est exactement ce cas depuis le 1er septembre.

---

## 2. Comment un signal gagne un vote

C'est la règle d'adoption, inscrite dans `dimensions.ADOPTION_RULE` et
exécutoire — pas une intention.

Un signal ne peut être Tier A que s'il franchit **les quatre** :

| # | Critère | Pourquoi |
|---|---|---|
| 1 | edge ≥ 3 points à 90 j contre une baseline **appariée en période** | comparer 2022-2026 à une baseline 2019-2026 fabrique du faux edge — erreur commise et corrigée |
| 2 | ≥ 4 épisodes distincts, les 3 plus gros sous la moitié du bucket | 149 jours ne sont pas 149 observations si 90 sont dans deux grappes |
| 3 | accord walk-forward **au-dessus de son propre mélange** | deux directions coïncident 50 % du temps par hasard |
| 4 | direction **écrite avant** la mesure | choisir la direction après avoir vu le résultat est du surapprentissage |

**Aucun signal actuel ne franchit les quatre.** Ils sont conservés sur la
plausibilité de leur mécanisme, ce qui est une hypothèse et non un résultat.

### Pourquoi cette règle existe

Sept analyses ont été lancées sur les mêmes quatre ans de données. L'une a
produit un gradient monotone 4/4 parfait sur la dominance BTC — qui s'est
dissous au test hors échantillon : trois bandes sur cinq vides en test, et la
forme de la relation change selon la fenêtre.

Sans compteur d'hypothèses, la vingtième qui « marche » est simplement le
vingtième tirage.

---

## 3. Les signaux, un par un

### Tier A — les huit qui votent

| Signal | Mesure | Source | Règle | Ce qu'on sait |
|---|---|---|---|---|
| `eth_btc_momentum` | ETH/BTC sur 14 j | CoinGecko | > +10 % | **retardé par construction** : quand il tire, les 10 % sont faits |
| `mvrv_z_score` | cap. marché vs cap. réalisée, normalisée | BGeometrics | > 3 | −15,7 pts à 90 j, hit 0 % — mais 3 épisodes seulement |
| `nvt` | valorisation vs valeur transférée | BGeometrics | > moyenne 90 j | affaibli en 2026 : L2 et ETF sortent l'activité de la chaîne |
| `stablecoin_supply_ratio` | cap. BTC / offre stablecoins | BGeometrics | en baisse 30 j | corrélé **0,79** avec MVRV Z — deux votes, une observation |
| `alt_funding_rates` | **écart** funding alts moins BTC | Binance→Bybit→OKX→Hyperliquid | positif ET en hausse | coïncident : monte *parce que* la rotation a lieu |
| `exchange_netflows` | variation de l'offre détenue en exchange | CoinMetrics | négatif = accumulation | estimation par adresses étiquetées |
| `sth_realized_price` | prix de revient des détenteurs récents | BGeometrics | prix > STH-RP | edge +1,4 pt à 90 j, bucket concentré à 76 % |
| `eth_etf_flows` | flux nets ETF ETH | — | positifs 1 semaine | **aucune API publique** — jamais mesurable |

### Suivis seulement — pas de vote

`btc_dominance`, `alt_dominance`, `altseason_index`, `mvrv_ratio`,
`mayer_multiple`, `puell_multiple`, `nupl`, `sopr`, `social_volume`,
et **`fear_greed`**.

### Le cas Fear & Greed, à part

Retiré du Tier A le 1er septembre, **sur mesure et non sur avis** :

```
walk-forward : 1 accord sur 9 plis
mélange      : 51 %
écart        : -40
```

Sa direction s'inverse d'une fenêtre à l'autre. C'est pire qu'un signal
absent — un tirage au sort au moins n'induit pas en erreur de façon
systématique. C'était aussi la seule règle Tier A avec assez de plis pour être
mesurée, ce qui en fait le verdict le mieux étayé du registre.

Il reste au tableau de bord : c'est du contexte légitime pour le brief.

---

## 4. Les deux instruments de décision

### Le gate 10 dimensions

Compte les votes Tier A. Seuil **5**, sur une base de **8** depuis la
rétrogradation de F&G.

**Convention essentielle** : un signal absent réduit le *dénominateur*, il ne
vote pas non. Une valeur périmée ou gelée ne vote jamais non plus.

### L'échelle Pivot Ladder — mode ombre, ne gouverne rien

Quatre états : `USDT ← BTC ↔ ETH ↔ ALT`. L'échelle ne peut **jamais** entrer
en USDT de sa propre autorité : le passage en cash appartient au sell gate.
Deux systèmes commandant la même sortie seraient deux autorités sur une
décision.

Trois mécaniques, et ce sont elles qui ont été validées :

- **hystérésis** — entrer coûte plus cher que rester, bande morte de 0,10
- **durée minimale** — 14 jours par état
- **plancher de couverture** — sous 70 % de poids mesurable, T est déclaré non
  mesurable et l'échelle gèle plutôt que de décider sur une base mince

Monte Carlo, 1000 trajectoires de 730 jours :

| Règle | Changements/an | Allers-retours/an |
|---|---|---|
| binaire ≥ 2 sur 4 | 92,3 | 87,6 |
| pondérée par corrélation | 92,3 | **87,6** |
| binaire ≥ 3 sur 4 | 18,5 | 15,4 |
| **échelle** | 12,5 | **0,0** |

La pondération par corrélation n'apporte **rien** sur le churn — identique au
binaire naïf à la deuxième décimale. Le zéro de l'échelle est structurel : une
durée minimale de 14 jours rend un aller-retour de moins de 14 jours
impossible par construction.

### Le sell gate — inopérant, et il le dit

Trois Tier-1, déclenchement à 2 sur 3 en 60 jours :

1. distribution LTH sur 30 jours ou plus — **aucune source gratuite**
2. perte du STH-RP en clôture hebdo — mesurable
3. inversion des flux ETF à moins de 10 % de l'ATH — **aucune API**

**Deux entrées sur trois sont illisibles, donc une règle 2-sur-3 ne peut
jamais atteindre 2.** Le module refuse délibérément de rééchelonner le seuil :
ce serait donner à un seul signal l'autorité de vendre le portefeuille, ce que
la règle 2-sur-3 existe précisément pour empêcher.

Mesuré sur 209 semaines : T2 tire **41,1 %** du temps, à une médiane de
**45,3 % sous l'ATH**. C'est un marqueur de capitulation, pas de distribution.
Et le verdict ESCALATE serait allumé **67,9 %** des semaines — une escalade
deux semaines sur trois n'est pas une escalade.

---

## 5. Ce que les mesures ont trouvé

### Aucun signal ne gagne son vote

Sur neuf règles testées : deux passent le test d'indépendance, aucune ne
montre d'edge suffisant. Ce n'est **pas** « les règles sont fausses » — c'est
« les données ne permettent pas de trancher ».

### Le signe s'inverse selon la rotation

`dominance ETH` donne −18,1 pour ETH/BTC et +11,1 pour ALT/ETH. Traiter « la
rotation » comme un objet unique était une erreur de conception.

### Deux rotations sur trois ne sont pas mesurables

CoinMetrics communautaire couvre 135 actifs et **aucun alt majeur de ce
cycle** : SOL, SUI, HYPE, APT, ARB, OP, TON, NEAR, AVAX sont tous absents.
Les résultats ALT/ETH et ALT/BTC ont été **retirés**, pas nuancés.

Des quatre jambes envisagées — BTC→ETH, ETH→ALT, ALT→USDT, USDT→BTC — **une
seule est mesurable aujourd'hui sur données gratuites : BTC→ETH.**

### Le framework ne peut pas être testé contre 2021

**Un seul signal Tier A sur huit** est reconstructible pour 2021. Un gate
calibré sur deux événements qu'il ne peut structurellement pas noter est un
gate calibré sur un souvenir.

---

## 6. Le plafond, et pourquoi il ne bouge pas

La note de preuve plafonne vers 6,0. Ce n'est pas de la modestie :

- il n'existe que **deux cycles datables**
- l'ère post-ETF **est** le jeu de test — y ajuster une règle puis citer sa
  performance post-ETF serait circulaire
- il n'existe pas de troisième période à garder de côté

La seule façon d'écrire 9 serait de redéfinir la preuve comme validité du
mécanisme, ce qui améliore la note en changeant la question.

**La contrainte est la donnée, pas l'analyse.** Sept analyses sur quatre ans :
le rendement marginal d'une huitième est désormais négatif, et c'est
littéralement ce que dit le résultat sur les comparaisons multiples.

---

## 7. Reproduire tout ceci

```bash
python -m unittest discover -s tests     # 512 tests, hors ligne
python scripts/build_rotations.py        # régénère dominance + rotations
python scripts/forward_study.py          # edge + indépendance par épisodes
python scripts/band_study.py             # fourchettes, monotonie
python scripts/oos_test.py               # hors échantillon — il ÉCHOUE
python scripts/walkforward.py            # walk-forward + contrôle mélange
python scripts/montecarlo.py             # comparaison des mécaniques
python scripts/sell_gate.py              # audit du sell gate
python scripts/event_study.py            # 2021 contre le jeu actuel
```

Chaque script écrit sa sortie dans `analysis/`, versionnée. Aucun chiffre de
ce document n'est saisi à la main.
