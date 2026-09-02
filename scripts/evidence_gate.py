#!/usr/bin/env python3
"""
Le gate d'evidence: un gate dont la portee est celle de sa preuve.

SHADOW ONLY. Il ne gouverne rien. Comme tout le reste ici.

Pourquoi un gate de plus
------------------------
Le gate 10 dimensions prend 8 entrees dont AUCUNE n a passe ADOPTION_RULE.
L echelle Pivot Ladder prend 8 entrees rotation dont aucune non plus. Les deux
sont bien construits et reposent sur des signaux dont on a mesure, cette
semaine, qu ils ne demontrent pas d edge.

Ce module part de l autre bout: qu est-ce que la preuve autorise a decider ?

La reponse est asymetrique, et c est tout l interet
---------------------------------------------------
COTE VENTE - une entree qualifie:
  lth_share, la part de capitalisation realisee detenue par les pieces de 6
  mois et plus. Sur 1430 jours, une baisse sur 30 jours precede une
  sous-performance BTC de -2,1 / -6,1 / -6,8 points a 30 / 60 / 90 jours.
  Un edge NEGATIF est le signe correct pour un declencheur de vente, et sa
  direction avait ete ECRITE AVANT la mesure - le critere 4 de ADOPTION_RULE,
  jamais satisfait par aucun autre signal du systeme.

COTE ROTATION - zero entree qualifie:
  Sept analyses, aucun signal ne passe edge >= 3 pts ET >= 4 episodes ET
  walk-forward au-dessus de son melange. Fear & Greed s accorde avec lui-meme
  1 fois sur 9 plis. L hypothese des fourchettes sur la dominance s est
  dissoute hors echantillon.

Donc ce gate DECIDE d un cote et RAPPORTE de l autre. Un gate symetrique sur
une preuve asymetrique serait une symetrie decorative.

Ce que ce module ne fait PAS
-----------------------------
Il ne remplace ni dimensions.py ni ladder.py. Ceux-la portent la structure
MECE et la mecanique anti-churn, qui restent valides independamment de la
qualite des signaux - le Monte Carlo l a montre: zero aller-retour contre
87,6. Ce module ajoute une question qu aucun des deux ne pose: de quoi
avons-nous le droit de decider aujourd hui ?

Il n arme pas non plus le sell gate. lth_share est un PROXY de T1, pas T1:
frontiere a 180 jours au lieu de 155, ponderation par capitalisation realisee
au lieu de l offre. Il echoue d ailleurs 2 des 4 criteres - 73% de ses jours
de tir dans trois episodes, walk-forward a 33% sous son melange a 39% sur
trois plis. Il est le MEILLEUR candidat du systeme et cela ne suffit pas.

Lancer: python scripts/evidence_gate.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dimensions

# Ce qui a le droit de decider, et ce qui n a que le droit de parler.
#
# La liste de gauche est vide cote rotation. Ce vide est le resultat, pas un
# oubli: le remplir demanderait de promouvoir un signal qui echoue la regle,
# ce qui viderait la regle de son sens le lendemain de son ecriture.
DECIDING = {
    "sell": ["lth_share"],
    "rotation": [],
}

REPORTING = {
    "sell": ["sth_realized_price", "nupl", "sopr", "puell_multiple",
             "peak_indicators"],
    "rotation": ["eth_btc_momentum", "btc_dominance", "alt_dominance",
                 "stablecoin_supply_ratio", "alt_funding_rates",
                 "exchange_netflows", "mvrv_z_score", "nvt", "fear_greed"],
}

# Edge mesure de lth_share contre le rendement BTC, en points de mediane
# contre une baseline appariee en periode (analysis/, 1430 jours).
LTH_MEASURED_EDGE = {30: -2.1, 60: -6.1, 90: -6.8}

# Pourquoi lth_share ne suffit pas a armer une vente, chiffre.
LTH_ADOPTION = {
    "edge_pts_90d": True,        # -6.8, magnitude au-dessus de 3
    "episodes": False,           # 73% dans trois episodes, plafond 50%
    "walkforward_vs_shuffle": False,   # 33% contre 39%, trois plis
    "preregistered_direction": True,   # ecrite avant la mesure
}


def _readable(payload):
    """Lisible = statut ok, frais, et porteur d une valeur."""
    if not isinstance(payload, dict):
        return False
    if payload.get("status") != "ok":
        return False
    age = payload.get("source_age_days")
    if age is not None and age > 3:
        return False
    return payload.get("signal") is not None


def evaluate(signals):
    """Rend ce que la preuve autorise, et rien de plus."""
    lth = signals.get("lth_share")
    sell_readable = _readable(lth)

    # La regle cote vente: distribution = part LTH en baisse sur 30 jours.
    # Elle ne DECLENCHE rien - elle est rapportee avec son score d adoption,
    # pour que le lecteur voie a la fois le signal et ce qui lui manque.
    distributing = None
    if sell_readable:
        change = lth.get("change_30d")
        distributing = None if change is None else change < 0

    passed = sum(1 for v in LTH_ADOPTION.values() if v)
    total = len(LTH_ADOPTION)

    reporting = {}
    for axis, keys in REPORTING.items():
        readable = [k for k in keys if _readable(signals.get(k))]
        reporting[axis] = {
            "readable": len(readable),
            "total": len(keys),
            "signals": readable,
        }

    return {
        "governs": False,
        "status": "SHADOW - portee limitee a la preuve, ne gouverne rien",
        "sell": {
            "deciding_input": "lth_share",
            "readable": sell_readable,
            "distributing_30d": distributing,
            "measured_edge_pts": LTH_MEASURED_EDGE,
            "adoption_passed": "%d/%d" % (passed, total),
            "adoption_detail": LTH_ADOPTION,
            "armed": False,
            # Chaine litterale, pas un format: les %% s y afficheraient tels
            # quels. Ecrit en clair plutot que d ajouter un formatage dont le
            # seul role serait d echapper des pourcents.
            "why_not_armed": "echoue independance (73 pourcent des jours dans "
                             "trois episodes) et walk-forward (33 contre un "
                             "melange a 39, sur trois plis). Meilleur candidat "
                             "du systeme, et cela ne suffit pas a armer une "
                             "vente.",
        },
        "rotation": {
            "deciding_inputs": DECIDING["rotation"],
            "verdict": "AUCUNE DECISION POSSIBLE",
            "why": "zero signal ne passe ADOPTION_RULE apres sept analyses. "
                   "Le vide est le resultat, pas un oubli.",
        },
        "reporting": reporting,
        "note": "Un gate symetrique sur une preuve asymetrique serait une "
                "symetrie decorative. Celui-ci decide d un cote et rapporte "
                "de l autre.",
    }


def render(verdict):
    out = []
    A = out.append
    A("=" * 74)
    A("GATE D EVIDENCE - portee limitee a ce que la preuve autorise")
    A("SHADOW: ne gouverne rien.")
    A("=" * 74)
    A("")

    s = verdict["sell"]
    A("COTE VENTE")
    A("-" * 74)
    A("  entree decisionnelle : %s" % s["deciding_input"])
    A("  lisible aujourd hui  : %s" % ("oui" if s["readable"] else "NON"))
    A("  distribution 30j     : %s" % s["distributing_30d"])
    A("  edge mesure (pts)    : 30j %+.1f | 60j %+.1f | 90j %+.1f"
      % (s["measured_edge_pts"][30], s["measured_edge_pts"][60],
         s["measured_edge_pts"][90]))
    A("  regle d adoption     : %s" % s["adoption_passed"])
    for k, v in s["adoption_detail"].items():
        A("      %-26s %s" % (k, "passe" if v else "ECHOUE"))
    A("  arme                 : %s" % ("oui" if s["armed"] else "NON"))
    A("")
    A("  %s" % s["why_not_armed"])
    A("")

    r = verdict["rotation"]
    A("COTE ROTATION")
    A("-" * 74)
    A("  entrees decisionnelles : %d" % len(r["deciding_inputs"]))
    A("  verdict                : %s" % r["verdict"])
    A("  %s" % r["why"])
    A("")

    A("CE QUI EST LU SANS DECIDER")
    A("-" * 74)
    for axis, info in verdict["reporting"].items():
        A("  %-9s %d lisibles sur %d" % (axis, info["readable"], info["total"]))
    A("")
    A(verdict["note"])
    return out


def main():
    import json
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "data", "latest.json")
    try:
        with open(path, encoding="utf-8") as f:
            signals = json.load(f).get("signals", {})
    except (OSError, ValueError):
        print("data/latest.json absent - lance d abord scripts/fetch_signals.py")
        return 1

    text = "\n".join(render(evaluate(signals)))
    print(text)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "analysis", "evidence_gate.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
