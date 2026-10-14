// Staged fictional fixtures for the live variant. Code may cite these; the model cannot add to them.
// Every name, employer and outcome here is synthetic.
(function (root) {
  const FIXTURES = {
    // Portal checks the code can run when an application's effect is unknown. Keyed by opportunity id.
    evidence: {
      O3: { found: true, source: 'Quill Health portal shows one application (staged)' },
      O8: { found: true, source: 'Corvid Systems portal shows one application (staged)' },
    },
    // Route options the code may propose. The model picks an id; it cannot write a route.
    routes: {
      'platform-shift': { to: '10 as now + 5 platform roles at recently-replying companies', why: 'synthetic outcome data' },
      'backend-focus': { to: '15 a week: backend only', why: 'candidate preference (synthetic)' },
    },
    defaultRoute: '15 a week: backend + ML platform',
    candidateEvidence: 'Maya said so',
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = FIXTURES;
  else root.TSENTA_FIXTURES = FIXTURES;
})(this);
