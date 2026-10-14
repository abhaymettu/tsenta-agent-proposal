// Scripted scenes. Every person, employer, email and number here is synthetic.
// Steps: time | sys (inbound event, centered) | agent | user | aside (presenter note).
// `ev` are proposals for core.js; `card` renders from the deterministic state at that moment.
(function (root) {
  const JORDAN = 'jordan@halyard.example';
  const SCENES = [
    {
      title: 'Asks before it assumes',
      principle: 'Starts from the goal, says what it can and cannot see, and what it will never do alone.',
      steps: [
        { t: 'time', text: 'Mon 9:41 AM' },
        { t: 'agent', text: "Hey Maya, it's Tsenta. Before I apply anywhere else: what are you actually aiming for? One sentence is enough." },
        {
          t: 'user',
          text: "Backend or ML platform roles, new grad, US. I'm on OPT so I'll need sponsorship eventually. Want to start by January.",
          ev: [{ type: 'goal_set', text: 'New-grad backend or ML platform role, US, start by January', constraints: ['OPT now, sponsorship later', 'Backend / ML platform', 'Start by Jan'] }],
        },
        { t: 'agent', text: "Got it. This is what I'll hold onto:", card: 'goal' },
        {
          t: 'agent',
          text: "Here's what I can see, and what I can't. If it's not on this list, I don't know about it.",
          card: 'coverage',
          ev: [
            { type: 'source_status', id: 'tsenta', label: 'Applications sent through Tsenta', status: 'healthy' },
            { type: 'source_status', id: 'gmail', label: 'Gmail job mail', status: 'healthy' },
            { type: 'source_status', id: 'outlook', label: 'School Outlook', status: 'healthy' },
            { type: 'source_status', id: 'manual', label: 'Applications you sent yourself', status: 'not_connected' },
          ],
        },
        {
          t: 'agent',
          text: 'And what I never do without asking you first:',
          card: 'permissions',
          ev: [{
            type: 'permissions_set',
            permissions: [
              { what: 'Apply to roles inside your filters', rule: 'auto' },
              { what: 'Draft replies to recruiters', rule: 'auto' },
              { what: 'Put a reply in your Gmail drafts', rule: 'ask' },
              { what: 'Send anything from your account', rule: 'never' },
              { what: 'Accept or decline an interview time', rule: 'never' },
            ],
          }],
        },
        { t: 'user', text: 'Perfect' },
        { t: 'agent', text: "I'll only text when something changed or there's a decision for you. No daily pep talks." },
      ],
    },
    {
      title: 'Says unknown instead of guessing',
      principle: 'A receipt is not an attempt. Work cut off mid-flight gets checked, never blindly retried.',
      steps: [
        {
          t: 'sys',
          text: 'Oct 1 to 10: Tsenta worked on 6 applications (synthetic history)',
          ev: [
            { type: 'opp_added', id: 'O1', employer: 'Halyard', role: 'ML Platform Engineer', receipt: 'confirmed', applied: 'Oct 2' },
            { type: 'opp_added', id: 'O2', employer: 'Halyard', role: 'Data Infrastructure Engineer', receipt: 'attempted', applied: 'Oct 5' },
            { type: 'opp_added', id: 'O4', employer: 'Northwind', role: 'Platform Engineer I', receipt: 'confirmed', applied: 'Oct 1' },
            { type: 'opp_added', id: 'O5', employer: 'Lumen Data', role: 'Backend Engineer', receipt: 'confirmed', applied: 'Oct 3' },
            { type: 'opp_added', id: 'O6', employer: 'Fathom Robotics', role: 'ML Infrastructure', receipt: 'confirmed', applied: 'Oct 6' },
            { type: 'opp_added', id: 'O3', employer: 'Quill Health', role: 'Backend Engineer', receipt: 'queued', applied: 'Oct 10' },
          ],
        },
        { t: 'sys', text: 'Sat 9:02 PM · Maya paused Tsenta while it was submitting to Quill Health', ev: [{ type: 'submit_started', oppId: 'O3' }, { type: 'paused' }] },
        { t: 'time', text: 'Tue 8:15 AM' },
        { t: 'user', text: 'ok resume. how many did I actually apply to?', ev: [{ type: 'resumed' }] },
        { t: 'agent', text: 'Here is what actually landed, not what was attempted:', card: 'receipts' },
        { t: 'agent', text: "Halyard Data Infra: Tsenta tried on Oct 5, but there's no confirmation email or portal receipt. I'm counting it as unknown, not applied." },
        { t: 'agent', text: "Quill Health was mid-submit when you paused. It may have gone through, so I won't resubmit. Checking their portal first." },
        { t: 'sys', text: 'Reconcile: Quill Health portal shows one application, Sat 9:01 PM', ev: [{ type: 'reconciled', oppId: 'O3', found: true }] },
        { t: 'agent', text: "It went through. Counted once, no duplicate. So: 5 confirmed, 1 unknown. I'll recheck Halyard tonight." },
      ],
    },
    {
      title: 'A yes means one exact thing',
      principle: 'Approval binds to one action, one recipient and one version, not to whatever arrived last.',
      steps: [
        { t: 'time', text: 'Wed 10:02 AM' },
        {
          t: 'sys',
          text: 'Email from Jordan Lee, Halyard recruiting: "Thanks for applying to Halyard! Do you have time for a 30-minute chat next week?"',
          ev: [{ type: 'invite', id: 'I1', employer: 'Halyard', from: JORDAN, candidates: ['O1', 'O2'] }],
        },
        { t: 'agent', text: "Halyard wants a chat. The email doesn't say which role, and you have two there. I haven't linked it to either.", card: 'invite' },
        { t: 'agent', text: 'Want me to draft a reply that asks?' },
        {
          t: 'user',
          text: "yes, ask which role. I'm free Tue or Wed afternoon",
          ev: [{ type: 'draft', actionId: 'A1', taskId: 'T-reply-I1', kind: 'gmail_draft', recipient: JORDAN, body: "Hi Jordan, thanks so much for reaching out! I'd love to chat. I applied to both the ML Platform Engineer and Data Infrastructure Engineer roles, so could you let me know which one this is for? I'm free Tuesday or Wednesday afternoon next week. Best, Maya" }],
        },
        { t: 'agent', text: 'Draft:', card: 'draft:A1' },
        {
          t: 'user',
          text: 'shorter please',
          ev: [
            { type: 'draft', actionId: 'A1', body: "Hi Jordan, happy to chat. Which role is this for, ML Platform or Data Infra? I'm free Tue or Wed afternoon. Thanks, Maya" },
            { type: 'ask_approval', actionId: 'A1' },
          ],
        },
        { t: 'agent', text: 'Put this one in your Gmail drafts? You send it, not me.', card: 'draft:A1' },
        { t: 'sys', text: 'Tsenta: new match, Northwind Platform Engineer II', ev: [{ type: 'message_in', text: 'New match: Northwind Platform Engineer II' }] },
        { t: 'user', text: 'yes', ev: [{ type: 'yes' }, { type: 'placed', actionId: 'A1' }] },
        { t: 'agent', text: "Done. That yes was for this exact reply to Jordan, not the Northwind match that came in after. It's in your drafts.", card: 'approved:A1' },
      ],
    },
    {
      title: 'Retires stale work',
      principle: 'When you handle it yourself, or plans change, old drafts and reminders die instead of firing.',
      steps: [
        { t: 'time', text: 'Wed 11:40 AM' },
        { t: 'sys', text: 'Gmail: Maya sent her own reply to Jordan at 11:38 AM with her availability', ev: [{ type: 'manual_done', taskId: 'T-reply-I1' }] },
        { t: 'agent', text: 'Saw you sent your own reply with times. I retired my draft and the follow-up nudge, so nothing stale goes out. Waiting on Halyard now.' },
        { t: 'time', text: 'Thu 9:05 AM' },
        {
          t: 'sys',
          text: 'Email from Jordan: "Confirmed for Tue 2:00 PM, ML Platform Engineer."',
          ev: [
            { type: 'link', interviewId: 'I1', oppId: 'O1', evidence: 'confirmation names the role' },
            { type: 'employer_confirm', interviewId: 'I1', rev: 1, time: 'Tue 2:00 PM' },
          ],
        },
        { t: 'agent', text: "Confirmed: Tuesday 2:00 PM. Jordan named the ML Platform role, so now it's linked. I set prep and a reminder for that time.", card: 'interview:I1' },
        { t: 'time', text: 'Fri 4:47 PM' },
        { t: 'sys', text: 'Email from Jordan: "So sorry, need to cancel Tuesday. I\'ll reach out to reschedule."', ev: [{ type: 'employer_cancel', interviewId: 'I1', rev: 2 }] },
        { t: 'agent', text: "Halyard cancelled Tuesday. Reminder and prep are off. Nothing for you to do. I'll tell you when they send a new time." },
        { t: 'sys', text: "Sat 7:12 AM · A delayed copy of Thursday's confirmation arrives", ev: [{ type: 'employer_confirm', interviewId: 'I1', rev: 1, time: 'Tue 2:00 PM' }] },
        { t: 'aside', text: 'No text. A late copy of an old event cannot bring a cancelled interview back. See the event log.' },
      ],
    },
    {
      title: "Silence isn't rejection",
      principle: 'Healthy-and-quiet is different from disconnected. It offers one reversible change, no diagnosis.',
      steps: [
        { t: 'time', text: 'Mon 9:30 AM' },
        { t: 'sys', text: 'School Outlook disconnected Sunday 6:10 PM', ev: [{ type: 'source_status', id: 'outlook', status: 'disconnected', since: 'Sun 6:10 PM' }] },
        { t: 'user', text: "it's been 3 weeks. am I just getting rejected everywhere?" },
        { t: 'agent', text: "No. Here's what I can actually say:", card: 'silence' },
        { t: 'agent', text: "Your school Outlook disconnected Sunday, so anything sent there since then I can't see. Reconnect when you can. Until then I won't call it quiet." },
        {
          t: 'agent',
          text: "One option, your call. In this demo's outcome data, the companies you've applied to rarely answer new-grad applications within 30 days. I could shift 5 of next week's 15 toward platform roles at companies that replied to someone recently.",
          card: 'route',
          ev: [{ type: 'route_propose', from: '15 a week: backend + ML platform', to: '10 as now + 5 platform roles at recently-replying companies', why: 'synthetic outcome data' }],
        },
        { t: 'user', text: 'do it', ev: [{ type: 'route_choose', to: '10 as now + 5 platform roles at recently-replying companies' }] },
        { t: 'agent', text: 'Done for next week. Say "undo" and it goes back exactly as it was.' },
        { t: 'aside', text: 'One state across the search: goal, route, receipt, next task, done by you or by the agent, then an honest stage or closure.' },
      ],
    },
  ];
  if (typeof module !== 'undefined' && module.exports) module.exports = SCENES;
  else root.TSENTA_SCENES = SCENES;
})(this);
