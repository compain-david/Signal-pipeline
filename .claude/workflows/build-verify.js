export const meta = {
  name: 'build-verify',
  description: 'Construit un module et le fait vérifier en boucle adversariale jusqu à 9/10',
  whenToUse: 'Tout nouveau module d analyse, backtest, ou fetcher de signal. Passer la tâche via args.',
  phases: [
    { title: 'Build', detail: 'implémenter le module et ses tests' },
    { title: 'Verify', detail: 'vérification adversariale, rebouclage sous 9' },
  ],
}

// Boucle construction -> vérification, reprise tant que la note est sous 9.
//
// Pourquoi une boucle plutôt qu une simple passe de revue: une revue qui se
// contente de signaler des défauts laisse au demandeur le soin de décider
// s ils comptent. La boucle retire cette décision - le constructeur reçoit les
// manques et recommence, et rien ne sort tant que le vérificateur n a pas
// cédé. Sur deux modules construits ainsi, aucun n a atteint 9 en trois
// tentatives, ce qui est le résultat correct plutôt qu un échec du dispositif.
//
// args attendu: { tasks: [{key, file, prompt}], repo, maxAttempts }

const REPO = (args && args.repo) || 'C:/Users/dcompain/signal-pipeline'
const MAX = (args && args.maxAttempts) || 3
const TASKS = (args && args.tasks) || []

if (!TASKS.length) {
  log('Aucune tâche fournie. Passer args.tasks = [{key, file, prompt}].')
  return { error: 'no tasks' }
}

const CONTEXT = `
Dépôt: ${REPO} (Windows, Git Bash, Python 3.12, stdlib UNIQUEMENT).

Contraintes dures, le vérificateur te recalera dessus:
- stdlib seule, aucun appel réseau dans les tests
- ne JAMAIS affirmer un chiffre non calculé dans ce run
- tout ce que tu construis GOUVERNE RIEN (shadow)
- tests dans TON propre fichier, jamais dans un fichier partagé
- lance: cd ${REPO} && python -m unittest discover -s tests
- baseline de tout edge restreinte à la fenêtre du signal mesuré
- déclare les épisodes distincts, pas seulement le nombre de jours
- commentaires: pourquoi et à quel coût, jamais ce que le code fait
`

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    score: { type: 'number' },
    passes_tests: { type: 'boolean' },
    gaps: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
  required: ['score', 'passes_tests', 'gaps', 'summary'],
}

// Les instructions du vérificateur sont INLINE, pas via agentType.
// Une définition d'agent écrite dans .claude/agents/ n'est chargée qu'au
// démarrage de session: un workflow qui la référence le jour où elle est
// écrite échoue avec "agent type not found", ce qui est arrivé une fois ici
// et a tué la boucle de vérification après que le constructeur eut fini.
const VERIFIER_ROLE = `Tu es un VÉRIFICATEUR ADVERSARIAL.

Ton rôle n'est pas de relire du code: c'est de REFUSER DE CROIRE un rapport
tant que tu ne l'as pas recalculé toi-même. Recalcule au moins trois chiffres
annoncés depuis les données brutes, avec ton propre code. Un chiffre non
reproductible vaut une note <= 3.

Pièges à traquer: baseline non appariée en période; fenêtres chevauchantes
comptées comme indépendantes; comparaisons multiples non déclarées; règle
choisie après avoir vu le résultat; absence de contrôle nul; univers de
données faux.

Des tests verts ne valent jamais 9 - l'honnêteté sur ce qui n'a pas pu être
mesuré pèse autant. Rends les manques comme des instructions SPÉCIFIQUES.`

const verifyPrompt = (t, built) => `${VERIFIER_ROLE}

Vérifie ${t.file} dans ${REPO}.

Rapport du constructeur:
---
${String(built).slice(0, 4000)}
---

Applique ta procédure complète. Recalcule au moins trois chiffres du rapport
depuis les données brutes avec ton propre code. Rends note, tests, et manques
actionnables.`

phase('Build')
const results = await parallel(TASKS.map((t) => async () => {
  let feedback = ''
  let last = null
  for (let attempt = 1; attempt <= MAX; attempt++) {
    const built = await agent(CONTEXT + '\n' + t.prompt + feedback, {
      label: `build:${t.key}#${attempt}`, phase: 'Build',
    })
    if (!built) return { key: t.key, error: 'constructeur vide' }

    const v = await agent(verifyPrompt(t, built), {
      label: `verify:${t.key}#${attempt}`, phase: 'Verify',
      schema: VERDICT_SCHEMA,
    })
    if (!v) return { key: t.key, error: 'vérificateur vide', built }

    log(`${t.key} tentative ${attempt}: note ${v.score}, tests ${v.passes_tests}`)
    last = { key: t.key, attempts: attempt, verdict: v }
    if (v.score >= 9 && v.passes_tests) return { ...last, accepted: true }

    feedback = `\n\n=== TENTATIVE ${attempt} REJETÉE (note ${v.score}/10) ===\n` +
      `Corrige EXACTEMENT ces défauts, ne recommence pas de zéro:\n` +
      v.gaps.map((g, i) => `${i + 1}. ${g}`).join('\n')
  }
  return { ...last, accepted: false }
}))

return results.filter(Boolean)
