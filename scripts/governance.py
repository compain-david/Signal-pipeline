#!/usr/bin/env python3
"""
Qui gouverne, et qui ne fait que parler.

Le probleme que ce module resout
--------------------------------
Le depot contient quatre instruments qui rendent chacun un verdict:
gate_legacy, gate_new, ladder_shadow, evidence_gate. Aucun fichier ne disait
lequel decide. Un lecteur pressé - ou le brief hebdomadaire - pouvait lire
n importe lequel et croire lire LA reponse.

C est le meme defaut que le README qui affirmait "SHADOW" pendant que le JSON
affirmait "authoritative" le meme jour: un etat qui depend d une date, ecrit
en prose a quatre endroits, derive toujours. La difference ici est qu il est
CALCULE a chaque run et rendu en tete de sortie.

La hierarchie, et ce qu il faut pour en changer
-----------------------------------------------
  gate_legacy     GOUVERNE aujourd hui. Conserve pour continuite jusqu a
                  ADOPTED_FROM, pas parce qu il est bon.
  gate_new        ombre jusqu au 2026-09-30, puis il prend la main.
  ladder_shadow   ombre INDEFINIMENT: c est une mise a jour versionnee de la
                  strategie (plafond ETH 25%) et elle exige une signature.
  evidence_gate   ombre par construction. Il ne demandera jamais a gouverner:
                  son role est de dire de quoi on a le droit de decider.

Un seul de ces quatre peut gouverner a la fois. Le module l assert.

Ce que la v2 n est pas
----------------------
Ce n est pas un nouveau modele. Aucun signal n a ete promu, aucun seuil
change. C est la consolidation de ce qui existait en quatre modules muets sur
leur propre autorite. La preuve n a pas bouge et le plafond a ~6,0 tient.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dimensions

VERSION = "2.0"

# Ordre de precedence. Le premier dont la condition est vraie gouverne.
# Ecrit comme une liste plutot que par des if imbriques pour que l ajout d un
# cinquieme instrument oblige a choisir sa place explicitement.
HIERARCHY = [
    ("gate_legacy", "gouverne jusqu a ADOPTED_FROM, par continuite"),
    ("gate_new", "gouverne a partir de ADOPTED_FROM"),
    ("ladder_shadow", "ombre indefinie - mise a jour de strategie non signee"),
    ("evidence_gate", "ombre par construction - portee, pas decision"),
]

# Ce qu il faudrait pour que chacun change de statut. Ecrit ici pour qu un
# changement de statut soit un acte, pas une derive.
PROMOTION_REQUIREMENTS = {
    "gate_new": "atteindre ADOPTED_FROM (%s), idealement avec la ceremonie "
                "Part D / Part E prevue" % dimensions.ADOPTED_FROM,
    "ladder_shadow": "signature des trois decisions: plafond ETH 25%, les six "
                     "seuils, et l interdiction d entrer en USDT seule",
    "evidence_gate": "jamais - il rapporte la portee, il ne decide pas",
}


def governing(today):
    """Rend le nom de l instrument qui gouverne aujourd hui.

    Calcule depuis la date, jamais ecrit en dur, parce que la seule chose
    qui change ce statut est le calendrier.
    """
    return "gate_new" if today >= dimensions.ADOPTED_FROM else "gate_legacy"


def summarise(snapshot, today):
    """Bloc de gouvernance a placer EN TETE de la sortie."""
    active = governing(today)

    instruments = []
    for name, role in HIERARCHY:
        present = name in snapshot
        instruments.append({
            "name": name,
            "role": role,
            "present_this_run": present,
            "governs": name == active,
            "to_promote": PROMOTION_REQUIREMENTS.get(name),
        })

    n_governing = sum(1 for i in instruments if i["governs"])
    # Deux autorites sur une decision est la collision que toute cette
    # architecture existe pour empecher. Si elle apparait, il vaut mieux
    # planter qu emettre un rapport ambigu.
    assert n_governing == 1, (
        "exactement un instrument doit gouverner, trouve %d" % n_governing)

    return {
        "version": VERSION,
        "governing": active,
        "adopted_from": dimensions.ADOPTED_FROM,
        "instruments": instruments,
        "note": "Un seul instrument gouverne. Les autres sont lisibles et "
                "n engagent rien. Ce bloc est calcule a chaque run, jamais "
                "recopie en prose.",
    }


def render(gov):
    out = []
    A = out.append
    A("GOUVERNANCE - v%s" % gov["version"])
    A("-" * 74)
    for i in gov["instruments"]:
        mark = "  >>" if i["governs"] else "    "
        state = "GOUVERNE" if i["governs"] else "ombre   "
        seen = "" if i["present_this_run"] else "   (absent de ce run)"
        A("%s %-15s %s  %s%s" % (mark, i["name"], state, i["role"], seen))
    A("")
    A("  Un seul instrument gouverne a la fois. Les trois autres sont")
    A("  lisibles et n engagent rien.")
    return out
