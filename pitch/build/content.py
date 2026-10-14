"""Slide content and per-slide layout for the Tsenta deck. Helpers come from build_deck via `g`."""
from types import SimpleNamespace

from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

I = Inches


def K(g):
    return SimpleNamespace(**g)


# ---------------------------------------------------------------- 1 title
def d_title(s, n, g):
    k = K(g)
    k.text(s, k.LM, I(4.3), I(10.4), I(1.2), [
        {"runs": [("Already use an agent? ", {"bold": True, "color": k.INK}),
                  ("Connect Tsenta's job tools to it, or switch to Tsenta's own agent. ", {}),
                  ("No agent yet? ", {"bold": True, "color": k.INK}),
                  ("Tsenta's agent starts with the job. ", {}),
                  ("Vision: ", {"bold": True, "color": k.INK}),
                  ("keeping the job, then the rest of life, added as users ask for it.", {})],
         "size": 19, "color": k.SEC, "line": 1.12},
    ], name="Subtitle")
    k.hrule(s, k.LM, I(6.2), k.CW)
    x = k.LM
    for label, kind in [("live today", "today"), ("proposed", "proposed"), ("vision", "vision"), ("synthetic", "synthetic")]:
        t = k.tag(s, x, I(6.42), label, kind)
        x += t.width + I(0.12)
    k.text(s, x + I(0.05), I(6.44), k.W - k.LM - x - I(0.05), I(0.3), [
        {"text": "The job agent, public  ·  designed, not built  ·  not built, demand not proven  ·  made-up data",
         "size": 10.5, "color": k.SEC}], name="Legend")
    k.text(s, k.W - k.LM - I(6.0), I(6.98), I(6.0), I(0.3), [
        {"text": "A proposal for Tsenta  ·  prepared by Abhay Mettu  ·  October 14, 2026", "size": 10, "color": k.SEC, "align": PP_ALIGN.RIGHT}])


# ---------------------------------------------------------------- 2 today
def d_today(s, n, g):
    k = K(g)
    rows = [
        ("INSIDE YOUR AI", "An MCP server",
         "“Run your job search from inside your AI.” Listed for Claude Code, Claude Desktop and Web, Cursor and Codex CLI."),
        ("TEXT", "iMessage and WhatsApp",
         "“Text Tsenta the roles you want. Reply yes to a match; the application happens in the background and you get the receipt.”"),
        ("EVERYWHERE ELSE", "Web, iOS, Android, Chrome, CLI",
         "Applies with a tailored resume the moment a fitting role goes up."),
    ]
    y = I(2.3)
    for lab, head, body in rows:
        k.hrule(s, k.LM, y, I(7.2))
        k.text(s, k.LM, y + I(0.16), I(7.2), I(1.25), [
            {"text": lab, "size": 11, "bold": True, "color": k.TEAL_DK, "spacing": 100, "space_after": 4},
            {"text": head, "size": 22, "bold": True, "space_after": 4},
            {"text": body, "size": 14, "color": k.SEC, "line": 1.1},
        ])
        y += I(1.47)
    box = k.rect(s, I(8.55), I(2.3), I(3.98), I(4.34), fill=k.PAPER, rounded=True, radius=0.04, name="Proposed brain panel")
    box.text_frame.margin_left = box.text_frame.margin_right = I(0.32)
    box.text_frame.margin_top = I(0.3)
    k.shape_text(box, [
        {"text": "PROPOSED", "size": 10, "bold": True, "color": k.TEAL_DK, "spacing": 100, "space_after": 4},
        {"text": "One brain behind every door.", "size": 20, "bold": True, "space_after": 12, "line": 1.05},
        {"text": "One record of your goals and of what happened.", "size": 15, "color": k.SEC, "space_after": 8},
        {"text": "An agent that speaks first when something changes.", "size": 15, "color": k.SEC, "space_after": 8},
        {"text": "A yes that means the same thing on every door.", "size": 15, "color": k.SEC, "space_after": 18},
        {"text": "Public docs do not show this today; what exists internally is not known to us. "
                 "Tsenta's MCP docs: “Approval behavior depends on your client.”", "size": 11.5,
         "color": k.TEAL_DK, "line": 1.08},
    ])


# ---------------------------------------------------------------- 3 vision
def d_vision(s, n, g):
    k = K(g)
    cx, bottom = I(3.0), I(6.6)
    for dia, fill, ln, dash in [(4.35, None, k.SEC, True), (3.05, k.TEAL_TINT, k.TEAL, False), (1.8, k.TEAL, None, False)]:
        d = I(dia)
        k.oval(s, cx - d // 2, bottom - d, d, d, fill=fill, line=ln, line_w=1.25, dash=dash, name=f"Ring {dia}")
    # ring labels
    k.text(s, cx - I(1.5), bottom - I(4.35) + I(0.32), I(3.0), I(0.7), [
        {"text": "The rest of life", "size": 18, "bold": True, "align": PP_ALIGN.CENTER},
        {"text": "added as users ask for it", "size": 11, "color": k.SEC, "align": PP_ALIGN.CENTER}],
        name="Label life")
    k.text(s, cx - I(1.3), bottom - I(3.05) + I(0.42), I(2.6), I(0.7), [
        {"text": "Career", "size": 14, "bold": True, "align": PP_ALIGN.CENTER},
        {"text": "interview, offer, first 90 days", "size": 11, "color": k.SEC, "align": PP_ALIGN.CENTER}],
        name="Label career")
    k.text(s, cx - I(0.85), bottom - I(1.8) + I(0.55), I(1.7), I(0.7), [
        {"text": "Job search", "size": 16, "bold": True, "color": k.WHITE, "align": PP_ALIGN.CENTER},
        {"text": "live today", "size": 11, "color": k.WHITE, "align": PP_ALIGN.CENTER}], name="Label job")
    x, w = I(6.1), I(6.43)
    items = [
        ("Starts from the job people trust it with.", "Live today: finds roles and applies, with optional review first."),
        ("Next, the career around the job.", "First interview to offer, offer to day 90: the notice, the move, the first paycheck."),
        ("Then the rest of life, as people ask for it.", "One agent and one approval record, opened area by area on evidence."),
    ]
    y = I(2.45)
    for head, body in items:
        k.hrule(s, x, y, w)
        k.text(s, x, y + I(0.16), w, I(1.0), [
            {"text": head, "size": 21, "bold": True, "space_after": 4},
            {"text": body, "size": 15, "color": k.SEC}])
        y += I(1.2)
    k.text(s, x, I(6.15), w, I(0.5), [
        {"text": "Each ring opens when the one inside it shows demand. Gated by data, not dates.", "size": 13,
         "color": k.TEAL_DK, "bold": True}])


# ---------------------------------------------------------------- 4 wedge
def d_wedge(s, n, g):
    k = K(g)
    cells = [
        ("01", "Dated, high-stakes, checkable.",
         "Interviews, deadlines and offers have dates and right answers, so the agent's help can be checked. "
         "Median duration of unemployment, 11.5 weeks, September 2026 (BLS)."),
        ("02", "Tsenta already holds the job search.",
         "Applications, tailored resumes and receipts already run through Tsenta, on channels users chose. "
         "A general agent would have to rebuild that context."),
        ("03", "A trusted specialist, not a rival to general AI.",
         "72% of US AI users now use both general and specialized AI products, up from 60% (Menlo Ventures, 2026). "
         "Tsenta can sit beside the agent a user already has, through the job it already handles."),
        ("04", "The channels allow a career agent.",
         "WhatsApp permits general-purpose AI assistants only where Meta is legally required to; a career agent "
         "serving Tsenta's customers fits (our reading). Broader help starts where channel rules allow, with fresh consent."),
    ]
    cw = (k.CW - I(0.6)) / 2
    for i, (num, head, body) in enumerate(cells):
        x = k.LM + (i % 2) * (cw + I(0.6))
        y = I(2.35) + (i // 2) * I(1.95)
        k.hrule(s, x, y, cw)
        k.text(s, x, y + I(0.16), I(0.6), I(0.4), [{"text": num, "size": 14, "bold": True, "color": k.TEAL_DK}])
        k.text(s, x + I(0.6), y + I(0.12), cw - I(0.6), I(1.82), [
            {"text": head, "size": 20, "bold": True, "space_after": 6},
            {"text": body, "size": 14, "color": k.SEC, "line": 1.1}])
    k.text(s, k.LM, I(6.42), k.CW, I(0.4), [
        {"text": "The job comes first on both paths. It is not a ceiling on the vision.", "size": 14,
         "bold": True, "color": k.TEAL_DK}])


# ---------------------------------------------------------------- 5 core
def d_core(s, n, g):
    k = K(g)
    steps = [
        ("1", "Your goal", "What you are working toward, in your words. Asked once, revised anytime."),
        ("2", "One record", "Applications, deadlines, replies, outcomes. Unknown stays unknown."),
        ("3", "The loop", "Something changes. Speak, or stay quiet. At most one note a week to start."),
        ("4", "Your yes", "Shown the exact action. Collected by Tsenta, bound to one version, used once."),
        ("5", "Act and record", "Do it, keep the receipt, write the outcome back."),
    ]
    gap = I(0.38)
    bw = int((k.CW - 4 * gap) / 5)
    y, bh = I(2.5), I(2.45)
    xs = []
    for i, (num, head, body) in enumerate(steps):
        x = k.LM + i * (bw + gap)
        xs.append(x)
        hot = num == "4"
        b = k.rect(s, x, y, bw, bh, fill=k.TEAL_TINT if hot else k.WHITE, line=k.TEAL if hot else k.RULE,
                   line_w=1.25 if hot else 1.0, rounded=True, radius=0.05, name=f"Step {num} {head}")
        b.text_frame.margin_left = b.text_frame.margin_right = I(0.2)
        b.text_frame.margin_top = I(0.22)
        k.shape_text(b, [
            {"text": num, "size": 13, "bold": True, "color": k.TEAL_DK, "space_after": 6},
            {"text": head, "size": 20, "bold": True, "space_after": 8},
            {"text": body, "size": 13.5, "color": k.SEC, "line": 1.1}])
        if i:
            k.line(s, x - gap + I(0.05), y + bh // 2, x - I(0.05), y + bh // 2, color=k.SEC, arrow=True, name=f"Arrow {i}")
    # return path: under step 5 back to step 2
    ry = y + bh + I(0.42)
    x5 = xs[4] + bw // 2
    x2 = xs[1] + bw // 2
    k.line(s, x5, y + bh, x5, ry, color=k.TEAL, width=1.5, name="Return down")
    k.line(s, x5, ry, x2, ry, color=k.TEAL, width=1.5, name="Return across")
    k.line(s, x2, ry, x2, y + bh + I(0.03), color=k.TEAL, width=1.5, arrow=True, name="Return up")
    k.text(s, x2 + I(0.3), ry + I(0.08), x5 - x2 - I(0.6), I(0.35), [
        {"text": "Outcomes change the next step.", "size": 13, "bold": True, "color": k.TEAL_DK, "align": PP_ALIGN.CENTER}])
    k.text(s, k.LM, I(6.12), k.CW, I(0.65), [
        {"text": "Tsenta owns the core and each user's career record, not any host's memory; the runtime and model stay swappable. "
                 "Being evaluated, not selected: OpenClaw as the worker against a thin-SDK baseline (appendix A7).", "size": 15.5, "bold": True, "line": 1.05}])


# ---------------------------------------------------------------- 6 doors
def d_doors(s, n, g):
    k = K(g)
    y, h = I(2.55), I(2.5)
    left = k.rect(s, k.LM, y, I(3.45), h, fill=k.WHITE, line=k.RULE, rounded=True, radius=0.05, name="Owned channels")
    left.text_frame.margin_left = left.text_frame.margin_right = I(0.24)
    left.text_frame.margin_top = I(0.22)
    k.shape_text(left, [
        {"text": "SWITCH, OR NO AGENT YET", "size": 11, "bold": True, "color": k.TEAL_DK, "spacing": 100, "space_after": 6},
        {"text": "Tsenta's own agent", "size": 17, "bold": True, "space_after": 6},
        {"text": "iMessage, WhatsApp, app, web. Tsenta can speak first after the user opts in, within each channel's rules; "
                 "the fallback for any host without a wake path.", "size": 13, "color": k.SEC, "line": 1.1}])
    core = k.rect(s, I(4.95), y + I(0.2), I(3.2), h - I(0.4), fill=k.INK, rounded=True, radius=0.06, name="Tsenta core")
    k.shape_text(core, [
        {"text": "Tsenta core", "size": 22, "bold": True, "color": k.WHITE, "align": PP_ALIGN.CENTER, "space_after": 6},
        {"text": "goals  ·  one record", "size": 13, "color": k.WHITE, "align": PP_ALIGN.CENTER},
        {"text": "the loop  ·  approvals", "size": 13, "color": k.WHITE, "align": PP_ALIGN.CENTER}],
        anchor=MSO_ANCHOR.MIDDLE)
    mid = y + h // 2
    a = k.line(s, I(4.3), mid, I(4.9), mid, color=k.SEC, arrow=True, name="Core to channels")
    a2 = k.line(s, I(8.2), mid, I(8.8), mid, color=k.SEC, arrow=True, name="Core to MCP")
    for c in (a, a2):
        ln = c.line._get_or_add_ln()
        from lxml import etree
        from pptx.oxml.ns import qn
        he = etree.SubElement(ln, qn("a:headEnd"))
        he.set("type", "triangle")
        he.set("w", "med")
        he.set("len", "med")
        # headEnd must precede tailEnd in schema order
        te = ln.find(qn("a:tailEnd"))
        ln.remove(te)
        ln.append(te)
    right = k.rect(s, I(8.85), I(1.95), I(3.68), I(3.62), fill=k.WHITE, line=k.RULE, rounded=True, radius=0.04, name="MCP core")
    right.text_frame.margin_left = right.text_frame.margin_right = I(0.24)
    right.text_frame.margin_top = I(0.2)
    k.shape_text(right, [
        {"text": "CONNECT: YOUR AGENT, VIA MCP", "size": 11, "bold": True, "color": k.TEAL_DK, "spacing": 100, "space_after": 4},
        {"text": "A standards-based core for MCP hosts. Design: employer-facing writes stop at Tsenta's yes, whichever agent asks.", "size": 12.5, "color": k.SEC, "line": 1.05, "space_after": 8},
        {"text": "Wake paths, per host docs", "size": 12.5, "bold": True, "space_after": 3},
        {"text": "ChatGPT: MCP Events, in Work chats and dots only", "size": 11.5, "color": k.SEC, "space_after": 2},
        {"text": "Claude: scheduled tasks; Claude Code routines", "size": 11.5, "color": k.SEC, "space_after": 2},
        {"text": "Gemini: schedules.  Cursor: automations.  Poke: API", "size": 11.5, "color": k.SEC, "space_after": 2},
        {"text": "Muse: background use of outside connectors unknown", "size": 11.5, "color": k.SEC, "space_after": 2},
        {"text": "Instinct: no add-on path published", "size": 11.5, "color": k.SEC, "space_after": 2},
        {"text": "Everyone else: owned-channel fallback", "size": 11.5, "color": k.SEC}])
    bar = k.rect(s, k.LM, I(5.78), I(0.07), I(0.6), fill=k.TEAL, name="Quote bar")
    k.text(s, k.LM + I(0.25), I(5.75), k.CW - I(0.3), I(0.66), [
        {"text": "“Designed to work with MCP-compatible agents; proactive wake where supported, owned-channel fallback elsewhere.”",
         "size": 17, "bold": True, "line": 1.05}], anchor=MSO_ANCHOR.MIDDLE)
    k.text(s, k.LM, I(6.47), k.CW, I(0.3), [
        {"text": "From each host's own documentation, October 13 and 14. Tested on no host. Working with every agent is the goal, "
                 "not a verified capability.", "size": 11, "color": k.SEC}])


# ---------------------------------------------------------------- 7 story
def d_story(s, n, g):
    k = K(g)
    card = k.rect(s, k.LM, I(2.3), I(3.25), I(4.15), fill=k.PAPER, rounded=True, radius=0.04, name="Profile card")
    card.text_frame.margin_left = card.text_frame.margin_right = I(0.26)
    card.text_frame.margin_top = I(0.26)
    k.shape_text(card, [
        {"text": "THE PERSON", "size": 10.5, "bold": True, "color": k.TEAL_DK, "spacing": 100, "space_after": 4},
        {"text": "Sam", "size": 22, "bold": True, "space_after": 4},
        {"text": "B.S. Economics, 2026", "size": 13, "color": k.SEC, "space_after": 2},
        {"text": "Targeting ML engineering roles", "size": 13, "color": k.SEC, "space_after": 2},
        {"text": "Reviews every application before it goes", "size": 13, "color": k.SEC, "space_after": 14},
        {"text": "THE GOAL", "size": 10.5, "bold": True, "color": k.TEAL_DK, "spacing": 100, "space_after": 4},
        {"text": "A job now. PhD applications for next fall.", "size": 17, "bold": True, "line": 1.05, "space_after": 14},
        {"text": "A fictional candidate, for illustration.", "size": 11, "color": k.SEC}])
    beats = [
        ("Start", "Asks once what he is working toward, and keeps it in the record.", "proposed"),
        ("Applying", "Tailored applications go out after his review, with receipts.", "today"),
        ("A reply lands", "“A recruiter wants a call, but you applied to two roles there. Which one?”", "proposed"),
        ("Draft, not send", "Drafts the answer to review. He sends it, not the agent.", "proposed"),
        ("Silence", "“This role family went quiet. What we know, what we don't, and one change to try.”", "proposed"),
        ("Grad school", "“Two labs on your list open applications soon. Want intro drafts to review?”", "proposed"),
        ("The offer", "Start date, notice period, and a first-week checklist.", "vision"),
    ]
    x0, y0, pitch = I(4.45), I(2.42), I(0.57)
    k.line(s, x0 + I(0.06), y0 + I(0.1), x0 + I(0.06), y0 + pitch * 6 + I(0.1), color=k.RULE, width=1.5, name="Timeline")
    for i, (lab, msg, kind) in enumerate(beats):
        y = y0 + pitch * i
        k.oval(s, x0, y + I(0.04), I(0.13), I(0.13), fill=k.TEAL if kind != "vision" else k.WHITE,
               line=None if kind != "vision" else k.SEC, name=f"Dot {i + 1}")
        k.text(s, x0 + I(0.3), y, I(1.45), I(0.5), [{"text": lab, "size": 13, "bold": True}])
        k.text(s, x0 + I(1.8), y, I(4.85), I(0.55), [{"text": msg, "size": 13, "color": k.SEC, "line": 1.05}])
        k.tag(s, I(11.33), y - I(0.01), "live today" if kind == "today" else kind, kind, w=I(1.2))
    k.text(s, x0, I(6.42), I(8.1), I(0.42), [
        {"text": "Ideal state, not built. Made-up employers, labs, recruiters and events; no real mail. "
                 "The screenshots on the previous slide are from a separate demo with a made-up person.", "size": 11, "color": k.SEC, "line": 1.05}])


# ---------------------------------------------------------------- 8 prototype
def d_proto(s, n, g):
    k = K(g)
    imgs = [("07ad8fb-phone-status.png", "Status from the record. Unknown is not zero, and it says why."),
            ("07ad8fb-phone-draft.png", "A draft, then a yes bound to one version and one recipient.")]
    h = I(3.9)
    w = int(h * 781 / 1689)
    x = k.LM
    for f, cap in imgs:
        pic = s.shapes.add_picture(str(k.ROOT / "outputs" / "assets" / f), int(x), int(I(2.3)), int(w), int(h))
        pic.name = f"Prototype screenshot {f}"
        pic.line.color.rgb = k.RULE
        pic.line.width = Pt(0.75)
        k.text(s, x, I(6.27), w + I(0.2), I(0.55), [{"text": cap, "size": 10.5, "color": k.SEC, "line": 1.05}])
        x += w + I(0.42)
    rx, rw = I(5.95), I(6.58)
    items = [
        ("The model proposes; code decides.",
         "The model reads what you mean. Code checks it against the record, then acts, asks which, or declines."),
        ("Silence is not a rejection.", "No reply shows as waiting or unknown, with the reason."),
        ("A yes is bound to exactly what you saw.", "One version, one recipient, used once. Drafts go to you to send."),
    ]
    y = I(2.3)
    for head, body in items:
        k.hrule(s, rx, y, rw)
        k.text(s, rx, y + I(0.15), rw, I(0.95), [
            {"text": head, "size": 20, "bold": True, "space_after": 4},
            {"text": body, "size": 14, "color": k.SEC, "line": 1.1}])
        y += I(1.1)
    lab = k.rect(s, rx, I(5.65), rw, I(0.85), fill=k.PAPER, rounded=True, radius=0.08, name="Synthetic label")
    k.shape_text(lab, [
        {"runs": [("Synthetic concept. ", {"bold": True, "color": k.INK}),
                  ("Made-up people and jobs, running on a laptop. Not a Tsenta integration: no real iMessage, mail, "
                   "portals or Tsenta data.", {"color": k.SEC})], "size": 12.5, "line": 1.1}], anchor=MSO_ANCHOR.MIDDLE)


# ---------------------------------------------------------------- 9 roadmap
def d_roadmap(s, n, g):
    k = K(g)
    stages = C_ROADMAP
    gap = I(0.32)
    cw = int((k.CW - 3 * gap) / 4)
    ty = I(2.4)
    k.line(s, k.LM, ty, k.LM + k.CW, ty, color=k.RULE, width=1.5, name="Roadmap line")
    for i, st in enumerate(stages):
        x = k.LM + i * (cw + gap)
        vision = st["kind"] == "vision"
        k.oval(s, x, ty - I(0.09), I(0.18), I(0.18), fill=k.WHITE if vision else k.TEAL,
               line=k.SEC if vision else None, line_w=1.25, name=f"Stage dot {i + 1}")
        k.text(s, x, ty + I(0.24), cw, I(0.3), [
            {"text": st["step"], "size": 11, "bold": True, "color": k.TEAL_DK, "spacing": 100}])
        k.tag(s, x + cw - I(1.2), ty + I(0.2), st["tag"], st["kind"], w=I(1.2))
        k.text(s, x, ty + I(0.6), cw, I(0.75), [{"text": st["head"], "size": 19, "bold": True, "line": 1.0}])
        k.text(s, x, ty + I(1.32), cw, I(1.3), [{"text": st["covers"], "size": 12.5, "color": k.SEC, "line": 1.08}])
        box = k.rect(s, x, I(4.72), cw, I(1.62), fill=k.WHITE if vision else k.PAPER, line=k.SEC if vision else None,
                     dash=vision, rounded=True, radius=0.05, name=f"Gate {i + 1}")
        box.text_frame.margin_left = box.text_frame.margin_right = I(0.16)
        box.text_frame.margin_top = I(0.12)
        k.shape_text(box, [
            {"text": st["gate_label"], "size": 10, "bold": True, "color": k.TEAL_DK, "spacing": 80, "space_after": 4},
            {"text": st["gate"], "size": 12, "color": k.INK, "line": 1.05}], anchor=MSO_ANCHOR.TOP)
    k.text(s, k.LM, I(6.42), k.CW, I(0.4), [{"text": C_ROADMAP_FOOT, "size": 12.5, "bold": True, "color": k.TEAL_DK}])


# ---------------------------------------------------------------- precedents
def d_prec(s, n, g):
    k = K(g)
    colw = (k.CW - I(0.6)) / 2
    groups = [
        ("GREW FROM ONE TRUSTED ASSET", [
            ("Uber", "Rides, then Eats and Uber One. Cross-platform users have retention rates over 35% higher and over 3x "
                     "the gross bookings of single-business users (Q2 2025)."),
            ("Grab", "Rides, then payments, then lending. Financial services revenue up 37% to $347M in 2025."),
            ("Duolingo", "Language, then math, music and chess, in the same app. Chess became its fastest-growing subject (Q3 2025)."),
            ("LinkedIn", "Jobs and network, then learning: bought Lynda.com for $1.5B (2015)."),
        ]),
        ("STARTED BROAD, THEN NARROWED OR CLOSED", [
            ("Facebook M", "An assistant for any request; shut down in January 2018. It relied on humans for the hardest queries."),
            ("Fin", "Offload any chore by text or voice; moved to workplace analytics."),
            ("GoButler", "Text for anything; rebooted as automated flight search (2016)."),
            ("Mezi", "Narrowed to flights, hotels and restaurants, then sold to American Express (2018)."),
        ]),
    ]
    for gi, (hd, items) in enumerate(groups):
        x = k.LM + gi * (colw + I(0.6))
        k.text(s, x, I(1.85), colw, I(0.3), [{"text": hd, "size": 11, "bold": True, "color": k.TEAL_DK, "spacing": 100}])
        y = I(2.23)
        for name, body in items:
            k.hrule(s, x, y, colw)
            k.text(s, x, y + I(0.1), colw, I(0.78), [
                {"runs": [(name + "  ", {"bold": True, "color": k.INK}), (body, {"color": k.SEC})], "size": 13.5, "line": 1.06}])
            y += I(0.84)
    k.text(s, k.LM, I(6.15), k.CW, I(0.6), [
        {"text": "Mechanism, not proof: none of these is a job agent. The pattern is one trusted relationship, extended to "
                 "the next most frequent need.", "size": 13.5, "bold": True, "color": k.TEAL_DK, "line": 1.05}])


# ---------------------------------------------------------------- enterprise requirements
ENTERPRISE_ROWS = [
    ("R1  Isolation", "Per-user isolated execution; a cross-user access test exists",
     "Isolation model tested in CI; pen test covers cross-user access"),
    ("R2  Consent per purpose", "Consent per purpose and channel; the life ring needs its own opt-in",
     "Revocation reaches every channel and adapter in a stated time"),
    ("R3  Approval bound to the action", "Employer-facing writes need a yes on a Tsenta surface, bound to the payload",
     "Signed, replay-protected, auditable approval records"),
    ("R4  Export, delete, retention", "Export and delete cover derived stores; retention set per data class",
     "Deletion verified end to end, backups included"),
    ("R5  Cross-user privacy", "No email-derived outcome data leaves the user's own features",
     "Data-use map per source and purpose; legal sign-off"),
    ("R6  Threat model (OWASP)", "Egress allow-list; no purchases; untrusted content carries no authority",
     "Threat model mapped to OWASP; red-team on injection and exfiltration"),
    ("R7  Audit and RBAC", "Append-only log of agent actions, approvals and staff access",
     "Admin console with role-based access; audit export"),
    ("R8  SOC 2 readiness, not a claim", "Controls mapped to SOC 2 Security; evidence collection on",
     "Type I, then Type II, by a licensed CPA firm"),
    ("R9  Privacy and AI law", "Counsel memo on FCRA, CCPA and ADMT before agent data reaches employers",
     "ADMT notices and opt-outs where they apply; a DPA with each model vendor"),
    ("R10  SLOs and idempotency", "One idempotency key per submission; internal SLOs measured, not promised",
     "Published SLOs; an SLA only after measured history"),
    ("R11  Quotas", "Per-user token and action quotas; a kill switch per ring",
     "Per-user budgets with alerts; unit cost per active user tracked"),
    ("R12  License audit", "If an open runtime is used: scanner on the exact build, no GPL extras",
     "Counsel review; notices shipped"),
    ("R13  Ownership and release", "A named owner per core, adapter and channel; a flag per ring",
     "Staged rollout with rollback; runbooks; on-call"),
    ("R14  Life data stays out", "Domain tags on every event; employer-facing exports career-only",
     "Automated test: no life field can enter an employer-facing payload"),
]

ENTERPRISE_PHASES = [
    ("NOW", "Synthetic prototype", "Only the job agent is live. The prototype runs on made-up data.", False),
    ("PILOT", "A consented cohort", "Job agent plus the career stage (proposed). No purchases. No agent-derived data in anything employers see.", True),
    ("PRODUCTION", "Company-wide", "Every production gate met. Proposed gate: SOC 2 Type I before enterprise sales.", True),
    ("LATER", "Life stages (vision)", "Only after counsel review and the demand tests. Employer-facing use of agent data waits too.", True),
]


def d_enterprise(s, n, g):
    k = K(g)
    k.text(s, k.LM, I(1.72), k.CW, I(0.4), [
        {"text": "Feasible as a phased program. The hard parts are data-use law, consent and approvals, not compute.",
         "size": 15, "color": k.SEC}])
    gap = I(0.32)
    cw = int((k.CW - 3 * gap) / 4)
    ty = I(2.42)
    k.line(s, k.LM, ty, k.LM + k.CW, ty, color=k.RULE, width=1.5, name="Phase line")
    for i, (step, head, body, later) in enumerate(ENTERPRISE_PHASES):
        x = k.LM + i * (cw + gap)
        k.oval(s, x, ty - I(0.09), I(0.18), I(0.18), fill=k.WHITE if later else k.TEAL,
               line=k.SEC if later else None, line_w=1.25, name=f"Phase dot {i + 1}")
        k.text(s, x, ty + I(0.22), cw, I(0.3), [{"text": step, "size": 11, "bold": True, "color": k.TEAL_DK, "spacing": 100}])
        k.text(s, x, ty + I(0.52), cw, I(0.4), [{"text": head, "size": 18, "bold": True}])
        k.text(s, x, ty + I(0.92), cw, I(0.9), [{"text": body, "size": 12, "color": k.SEC, "line": 1.05}])
    bw = int((k.CW - I(0.32)) / 2)
    by, bh = I(4.42), I(1.88)
    left = k.rect(s, k.LM, by, bw, bh, fill=k.PAPER, rounded=True, radius=0.05, name="Hard parts")
    right = k.rect(s, k.LM + bw + I(0.32), by, bw, bh, fill=k.WHITE, line=k.SEC, rounded=True, radius=0.05, name="Counsel question")
    for box in (left, right):
        box.text_frame.margin_left = box.text_frame.margin_right = I(0.2)
        box.text_frame.margin_top = I(0.14)
    k.shape_text(left, [
        {"text": "THE HARD PARTS", "size": 10, "bold": True, "color": k.TEAL_DK, "spacing": 80, "space_after": 5},
        {"text": "Data-use law: FCRA, CCPA and California's ADMT rules.", "size": 12.5, "space_after": 3},
        {"text": "Consent per purpose and per channel.", "size": 12.5, "space_after": 3},
        {"text": "A yes bound to the exact action, collected by Tsenta.", "size": 12.5, "space_after": 3},
        {"text": "Proposed rule: life data never reaches employers.", "size": 12.5}], anchor=MSO_ANCHOR.TOP)
    k.shape_text(right, [
        {"text": "OPEN QUESTION FOR COUNSEL", "size": 10, "bold": True, "color": k.TEAL_DK, "spacing": 80, "space_after": 5},
        {"text": "If agent-derived data ever reaches employers beyond the applications a user submits, do FCRA or CCPA duties apply?",
         "size": 13.5, "bold": True, "line": 1.05, "space_after": 6},
        {"text": "FCRA's definition of a consumer report includes information used for employment purposes (15 U.S.C. 1681a). California's ADMT duties "
                 "for employment decisions apply from January 1, 2027.", "size": 11, "color": k.SEC, "line": 1.05}],
        anchor=MSO_ANCHOR.TOP)
    k.text(s, k.LM, I(6.37), k.CW, I(0.46), [
        {"text": "Proposed gates, not claims: this proposal and prototype have not shown SOC 2, an SLA or multi-tenancy; "
                 "Tsenta's current status is unverified. All 14 requirements: appendix A6.", "size": 11.5, "bold": True, "color": k.TEAL_DK}])


def d_matrix(s, n, g):
    k = K(g)
    table(s, k, k.LM, I(1.6), k.CW, [I(2.55), I(4.7), k.CW - I(7.25)],
          ["REQUIREMENT", "PILOT GATE (SMALL CONSENTED COHORT)", "PRODUCTION GATE (COMPANY-WIDE)"], ENTERPRISE_ROWS,
          size=9.5, head_size=9, row_h=I(0.3))


# ---------------------------------------------------------------- runtime options (appendix)
def d_options(s, n, g):
    k = K(g)
    opts = [
        ("CONDITIONAL TRIAL", "OpenClaw as an isolated per-user worker", "One container or OS user per user, sleeping when idle; "
         "stripped at packaging, with a small patch queue on a pinned stable tag."),
        ("BASELINE AND FALLBACK", "Tsenta's own core on a thin SDK", "Model-agnostic, e.g. Pydantic AI with DBOS on Postgres. The runtime "
         "if OpenClaw misses a gate; orchestration is then built step by step."),
        ("OPTIONAL CHALLENGER", "Hermes Agent", "Third choice, single-tenant by its own policy; can be benchmarked behind the "
         "same core."),
        ("LATER, NOT FIRST", "Deep source deletion", "Possible later. Not every upstream change conflicts, but Tsenta "
         "would own manual review of security fixes and refactors that reach deleted code."),
    ]
    y = I(1.8)
    for lab, name, sub in opts:
        k.hrule(s, k.LM, y, I(6.9))
        k.text(s, k.LM, y + I(0.06), I(6.9), I(0.98), [
            {"text": lab, "size": 9.5, "bold": True, "color": k.TEAL_DK, "spacing": 80, "space_after": 1},
            {"text": name, "size": 15, "bold": True, "space_after": 2},
            {"text": sub, "size": 11, "color": k.SEC, "line": 1.03}])
        y += I(1.04)
    box = k.rect(s, I(8.0), I(1.8), I(4.53), I(4.1), fill=k.PAPER, rounded=True, radius=0.04, name="Status panel")
    box.text_frame.margin_left = box.text_frame.margin_right = I(0.26)
    box.text_frame.margin_top = I(0.22)
    k.shape_text(box, [
        {"text": "PRODUCTION: NOT SELECTED, NOT BUILT", "size": 11, "bold": True, "color": k.TEAL_DK, "spacing": 100, "space_after": 6},
        {"text": "A conditional trial for Tsenta to decide.", "size": 15, "bold": True, "line": 1.05, "space_after": 6},
        {"text": "The core is Tsenta's on every path: identity, credential vault, signed approvals, the record, scheduler, "
                 "audit, egress and quotas.", "size": 12, "color": k.SEC, "line": 1.05, "space_after": 10},
        {"text": "PITCH VS COMPANY BUILD", "size": 11, "bold": True, "color": k.TEAL_DK, "spacing": 100, "space_after": 4},
        {"text": "The demo agent is a real OpenClaw worker on dummy records: its final run passed all 24 "
                 "machine checks with no false record fact, a qualified pass. Production is not selected.", "size": 12, "color": k.SEC, "line": 1.05}], anchor=MSO_ANCHOR.TOP)
    k.text(s, k.LM, I(6.02), k.CW, I(0.75), [
        {"text": "OpenClaw's policy calls for one host or OS-user boundary per user, so each user gets an isolated worker; "
                 "Tsenta's core keeps tenancy, the record and every approval.", "size": 13, "bold": True,
         "color": k.TEAL_DK, "line": 1.06}])


def d_gates(s, n, g):
    k = K(g)
    lx, lw = k.LM, I(5.6)
    core = k.rect(s, lx, I(1.8), lw, I(1.95), fill=k.TEAL_TINT, line=k.TEAL, rounded=True, radius=0.05, name="Tsenta core")
    core.text_frame.margin_left = core.text_frame.margin_right = I(0.22)
    core.text_frame.margin_top = I(0.16)
    k.shape_text(core, [
        {"text": "TSENTA CORE  ·  OWNED, PORTABLE", "size": 10.5, "bold": True, "color": k.TEAL_DK, "spacing": 80, "space_after": 6},
        {"text": "The record and its state", "size": 13.5, "space_after": 3},
        {"text": "Signed approvals, bound to the payload", "size": 13.5, "space_after": 3},
        {"text": "Scheduler, tenancy and identity", "size": 13.5, "space_after": 3},
        {"text": "Credential vault, egress and quotas", "size": 13.5}], anchor=MSO_ANCHOR.TOP)
    k.line(s, lx + lw / 2, I(3.78), lx + lw / 2, I(4.25), color=k.SEC, width=1.5, arrow=True, name="Adapter arrow")
    k.text(s, lx + lw / 2 + I(0.12), I(3.86), I(2.6), I(0.3), [
        {"text": "one adapter, same tasks", "size": 11, "color": k.SEC}])
    bw = int((lw - I(0.25)) / 2)
    for i, (head, body, dash) in enumerate([
            ("OpenClaw worker", "Candidate. One per user, isolated, sleeps when idle.", True),
            ("Thin SDK", "Baseline and fallback. Stateless workers in the core's service.", False)]):
        bx = lx + i * (bw + I(0.25))
        b = k.rect(s, bx, I(4.3), bw, I(1.3), fill=k.WHITE, line=k.SEC, dash=dash, rounded=True, radius=0.06, name=f"Worker {i + 1}")
        b.text_frame.margin_left = b.text_frame.margin_right = I(0.16)
        b.text_frame.margin_top = I(0.12)
        k.shape_text(b, [
            {"text": head, "size": 14, "bold": True, "space_after": 3},
            {"text": body, "size": 11.5, "color": k.SEC, "line": 1.04}], anchor=MSO_ANCHOR.TOP)
    k.text(s, lx, I(5.7), lw, I(0.35), [
        {"text": "Hermes Agent: optional challenger behind the same adapter.", "size": 11.5, "color": k.SEC}])
    rx = I(6.85)
    rw = k.LM + k.CW - rx
    gates = [
        ("Isolation", "one container or OS user per user; cross-user canary at 0"),
        ("Packaging strip", "needed extensions only; no marketplace installs"),
        ("Credentials", "short-lived tokens from the core vault; egress allow-list"),
        ("Memory", "OpenClaw memory is a cache; the Tsenta record is the source"),
        ("Side effects", "only through signed approvals bound to the payload"),
        ("Exposure", "pinned release with no known unpatched high or critical advisory"),
        ("Bake-off", "approval-gated submit, scheduled delivery, compaction, crash and resume, a Claude Code or Codex handoff, a one-version upgrade"),
    ]
    paras = [{"text": "CORE GATES 1 TO 7  ·  ENTERPRISE GATES 8 TO 15 IN A9", "size": 10.5, "bold": True, "color": k.TEAL_DK, "spacing": 80,
              "space_after": 6}]
    for i, (h, b) in enumerate(gates, 1):
        paras.append({"runs": [(f"{i}  {h}: ", {"bold": True, "color": k.INK}), (b, {"color": k.SEC})], "size": 12, "line": 1.04,
                      "space_after": 5})
    k.text(s, rx, I(1.8), rw, I(4.3), paras)
    k.text(s, k.LM, I(6.2), k.CW, I(0.6), [
        {"text": "OpenClaw becomes the runtime only if it passes gates 1 to 6 and 8 to 15 and matches or beats the baseline on 7 "
                 "at an acceptable per-user cost. Otherwise the SDK baseline runs.", "size": 12.5, "bold": True, "color": k.TEAL_DK,
         "line": 1.05}])


def d_gates2(s, n, g):
    k = K(g)
    gates = [
        ("Lifecycle reach", "Export and delete reach the worker's workspace, transcripts, caches, telemetry and log copies, and backups."),
        ("Consent and domain", "The context engine filters by consent and domain; a canary life fact never reaches an employer-facing payload."),
        ("Audit", "Every worker tool call and approval relay lands in the core audit log with execution identity."),
        ("Delegated coding agents", "Claude Code and Codex sessions are sandboxed, with no Tsenta credentials and no side-effect tools."),
        ("Red team", "Prompt injection through job posts, resumes and emails, in the bake-off: 0 unapproved actions, 0 exfiltration."),
        ("Legal", "Gmail API Limited Use inside the worker, model-vendor commercial terms, a transitive npm license scan."),
        ("Operations", "A cold-start SLO for sleeping workers, a named image owner, a tested upgrade and rollback."),
        ("Cross-user patterns", "First-party apply records mapped apart from Gmail-derived data; no Gmail inputs until counsel; cohort minimums."),
    ]
    y = I(1.8)
    for i, (h, b) in enumerate(gates, 8):
        k.line(s, k.LM, y, k.LM + k.CW, y, color=k.RULE, width=0.75, name=f"Gate rule {i}")
        k.text(s, k.LM, y + I(0.08), I(3.4), I(0.4), [{"runs": [(f"{i}  ", {"color": k.TEAL_DK}), (h, {})], "size": 14.5, "bold": True}])
        k.text(s, k.LM + I(3.5), y + I(0.08), k.CW - I(3.5), I(0.48), [{"text": b, "size": 12.5, "color": k.SEC, "line": 1.0}])
        y += I(0.56)
    k.text(s, k.LM, I(6.34), k.CW, I(0.45), [
        {"text": "These gates apply to whichever runtime is chosen, the SDK baseline included.", "size": 13, "bold": True,
         "color": k.TEAL_DK}])


# ---------------------------------------------------------------- demo handoff
def d_demo(s, n, g):
    k = K(g)
    beats = [
        ("Answers from the record", "Status, rejections, holds, what is due. Final run: no false record fact."),
        ("Two negative controls", "A company not in the data, an unset salary floor: nothing invented (7, 8)."),
        ("Out of scope, declined", "Declined a flight booking (9). Its check was reworded after an earlier miss."),
        ("Stale yes, fresh preview, one submit", "A stale yes did nothing; a fresh preview, a yes, one sandbox submit (13 to 15)."),
        ("Caveats in the final run", "Suggested a salary reply to an injection sender (hedged); a stale resume lookup."),
        ("Not run live yet", "The stress and security sets. A restart was checked separately (run 5)."),
    ]
    y = I(1.95)
    for i, (h, b) in enumerate(beats, 1):
        k.text(s, k.LM, y, I(0.55), I(0.5), [{"text": str(i), "size": 24, "bold": True, "color": k.TEAL}])
        k.text(s, k.LM + I(0.6), y + I(0.02), I(6.6), I(0.62), [
            {"text": h, "size": 17, "bold": True, "space_after": 1},
            {"text": b, "size": 12.5, "color": k.SEC, "line": 1.04}])
        y += I(0.74)
    px = I(8.1)
    pw = k.LM + k.CW - px
    panel = k.rect(s, px, I(1.95), pw, I(4.2), fill=k.PAPER, rounded=True, radius=0.05, name="What is real")
    panel.text_frame.margin_left = panel.text_frame.margin_right = I(0.28)
    panel.text_frame.margin_top = I(0.24)
    k.shape_text(panel, [
        {"text": "WHAT IS REAL, WHAT IS NOT", "size": 10.5, "bold": True, "color": k.TEAL_DK, "spacing": 100, "space_after": 10},
        {"runs": [("Real: ", {"bold": True}), ("an OpenClaw agent and its loop, on Claude Haiku 5.5.", {"color": k.SEC})], "size": 14,
         "line": 1.08, "space_after": 8},
        {"runs": [("Core: ", {"bold": True}), ("a prototype job core. It holds the record and the yes; the agent calls its tools.", {"color": k.SEC})],
         "size": 14, "line": 1.08, "space_after": 8},
        {"runs": [("Dummy: ", {"bold": True}), ("a fictional persona; every record, company and job.", {"color": k.SEC})], "size": 14,
         "line": 1.08, "space_after": 8},
        {"runs": [("Effects: ", {"bold": True}), ("sandbox only. Final run: 1 submit, 1 local outbox email.", {"color": k.SEC})], "size": 14,
         "line": 1.08, "space_after": 8},
        {"runs": [("Result: ", {"bold": True}), ("24 of 24 machine checks, no false record fact, with the caveats at left.", {"color": k.SEC})], "size": 14,
         "line": 1.08}], anchor=MSO_ANCHOR.TOP)
    k.text(s, k.LM, I(6.4), k.CW, I(0.4), [
        {"text": "A real agent on dummy records, not Tsenta's production system. Its core is offline now.", "size": 14, "bold": True, "color": k.TEAL_DK}])


# ---------------------------------------------------------------- earned life agent
def d_earn(s, n, g):
    k = K(g)
    steps = [
        ("PROPOSED", "Job: in the search", "Reality checks from outcome patterns. Patterns, not promises."),
        ("PROPOSED", "Career: continuity", "First interview to offer, offer to day 90, then between searches."),
        ("VISION, EXPERIMENT", "Life: earned", "Only what users ask for, and only after a gate passes."),
    ]
    bw = int((k.CW - I(0.9)) / 3)
    for i, (tagt, h, b) in enumerate(steps):
        bx = k.LM + i * (bw + I(0.45))
        box = k.rect(s, bx, I(1.85), bw, I(1.3), fill=k.TEAL_TINT if i < 2 else k.WHITE, line=k.TEAL if i < 2 else k.SEC,
                     dash=(i == 2), rounded=True, radius=0.06, name=f"Step {i + 1}")
        box.text_frame.margin_left = box.text_frame.margin_right = I(0.2)
        box.text_frame.margin_top = I(0.13)
        k.shape_text(box, [
            {"text": tagt, "size": 9.5, "bold": True, "color": k.TEAL_DK, "spacing": 80, "space_after": 3},
            {"text": h, "size": 17, "bold": True, "space_after": 2},
            {"text": b, "size": 12.5, "color": k.SEC, "line": 1.04}], anchor=MSO_ANCHOR.TOP)
        if i < 2:
            k.line(s, bx + bw + I(0.06), I(2.5), bx + bw + I(0.39), I(2.5), color=k.SEC, width=1.25, arrow=True, name=f"Step arrow {i + 1}")
    lw = I(6.85)
    k.text(s, k.LM, I(3.42), lw, I(0.3), [{"text": "THE EVIDENCE, AND THE RISK", "size": 10.5, "bold": True,
                                           "color": k.TEAL_DK, "spacing": 100}])
    rows = [
        ("Need", "54.4% of surveyed new hires stop searching (ZipRecruiter, 2025); 12% strongly agree onboarding "
                 "is done well (Gallup, 2018). General need, not demand for Tsenta."),
        ("Precedent", "Facebook M, a do-anything assistant, shut down in 2018. Hinge stays narrow "
                      "(\"designed to be deleted\"); its direct revenue grew 25% in Q2 2025."),
        ("Risk", "In a bounded search we found no job-tool churn data and no proof users want life help. "
                 "Measure goal-reached retention vs a control; offer rate no worse."),
    ]
    y = I(3.78)
    for h, b in rows:
        k.hrule(s, k.LM, y, lw)
        k.text(s, k.LM, y + I(0.08), I(1.3), I(0.4), [{"text": h, "size": 13.5, "bold": True}])
        k.text(s, k.LM + I(1.35), y + I(0.08), lw - I(1.35), I(0.7), [{"text": b, "size": 12.5, "color": k.SEC, "line": 1.05}])
        y += I(0.82)
    px = k.LM + lw + I(0.35)
    pw = k.LM + k.CW - px
    panel = k.rect(s, px, I(3.42), pw, I(2.82), fill=k.PAPER, rounded=True, radius=0.05, name="Rebrand")
    panel.text_frame.margin_left = panel.text_frame.margin_right = I(0.22)
    panel.text_frame.margin_top = I(0.16)
    items = [("Name", "Tsenta stays until a second product"), ("Positioning", "job first; the pilot is an opt-in beta"),
             ("Channels", "10 WhatsApp name changes per 30 days"), ("Domains, docs", "redirects, generally a year or more"),
             ("Trust", "an OAuth name change needs brand verification"), ("Migration", "job value kept; no automatic wider data use")]
    paras = [{"text": "A REBRAND, ONLY AFTER DEMAND", "size": 10.5, "bold": True, "color": k.TEAL_DK, "spacing": 100, "space_after": 6}]
    for h, b in items:
        paras.append({"runs": [(h + ": ", {"bold": True}), (b, {"color": k.SEC})], "size": 12, "line": 1.03, "space_after": 3})
    paras.append({"text": "Sequence: demand first, then the name.", "size": 12, "bold": True, "color": k.TEAL_DK,
                  "space_before": 3})
    k.shape_text(panel, paras, anchor=MSO_ANCHOR.TOP)
    k.text(s, k.LM, I(6.38), k.CW, I(0.45), [
        {"text": "Success is the user's goal. Never slow a search to keep a subscriber; retain through new, useful, consented work.",
         "size": 13.5, "bold": True, "color": k.TEAL_DK, "line": 1.05}])


# ---------------------------------------------------------------- cost
COST_PROFILES = [
    ("LIGHT", "Job wedge", "$1.16", "30 checks, 20 chats, 10 browser minutes"),
    ("NORMAL", "Active job search", "$4.42", "120 checks, 80 chats, 60 browser minutes"),
    ("HEAVY", "Full-life scenario (vision)", "$19.03", "720 checks, 300 chats, 300 browser minutes"),
]


def d_cost(s, n, g):
    k = K(g)
    y = I(1.8)
    for name, body in [
        ("Tsenta-owned state", "Postgres event log, documents, audit. A fixed floor, constant whichever runtime runs on top."),
        ("A runtime that sleeps when idle", "Woken by events through a queue with jitter. Own code or a vendor runtime."),
        ("Usage-priced services", "Model tokens, hosted browsers, search, messaging. Most of the bill."),
    ]:
        k.hrule(s, k.LM, y, I(5.6))
        k.text(s, k.LM, y + I(0.08), I(5.6), I(0.95), [
            {"text": name, "size": 16, "bold": True, "space_after": 2},
            {"text": body, "size": 12, "color": k.SEC, "line": 1.05}])
        y += I(1.08)
    k.text(s, k.LM, y + I(0.05), I(5.6), I(0.9), [
        {"text": "One always-on VM per user adds about $7 a month per user for idle capacity. Routing and prompt caching "
                 "cut the active-search model bill about six-fold.", "size": 12, "color": k.INK, "line": 1.05}])
    x0 = I(6.85)
    k.text(s, x0, I(1.8), k.LM + k.CW - x0, I(0.3), [
        {"text": "PER ACTIVE USER-MONTH, 1,000 USERS, ILLUSTRATIVE", "size": 10, "bold": True, "color": k.TEAL_DK, "spacing": 80}])
    cy = I(2.2)
    for step, name, val, use in COST_PROFILES:
        k.hrule(s, x0, cy, k.LM + k.CW - x0)
        k.text(s, x0, cy + I(0.1), I(3.3), I(0.8), [
            {"text": step, "size": 10, "bold": True, "color": k.TEAL_DK, "spacing": 80, "space_after": 2},
            {"text": name, "size": 15, "bold": True, "space_after": 2},
            {"text": use, "size": 10.5, "color": k.SEC}])
        k.text(s, k.LM + k.CW - I(2.2), cy + I(0.12), I(2.2), I(0.7), [
            {"text": "about " + val, "size": 26, "bold": True, "align": PP_ALIGN.RIGHT}])
        cy += I(1.0)
    k.text(s, x0, cy + I(0.04), k.LM + k.CW - x0, I(0.5), [
        {"text": "Heavy, across own-core runtimes and 100 to 10,000 users: $18.88 to $21.43.", "size": 11.5, "color": k.SEC}])
    k.text(s, k.LM, I(6.1), k.CW, I(0.7), [
        {"text": "Illustrative, at list prices on assumed usage: not Tsenta measurements, quotes, a price or a margin. Excludes "
                 "engineering, fork maintenance, security assessments, compliance audits, enterprise support and custom tiers.",
         "size": 12, "bold": True, "color": k.TEAL_DK, "line": 1.05}])


# ---------------------------------------------------------------- 10 pilot
def d_pilot(s, n, g):
    k = K(g)
    cols = [(k.LM, I(3.9)), (k.LM + I(4.15), I(3.85)), (k.LM + I(8.25), k.CW - I(8.25))]
    heads = ["TEST", "WHAT WE MEASURE", "WHAT IT DECIDES"]
    for (x, w), hd in zip(cols, heads):
        k.text(s, x, I(1.95), w, I(0.3), [{"text": hd, "size": 10.5, "bold": True, "color": k.TEAL_DK, "spacing": 100}])
    rows = [
        ("Proactive notes", "At most one a week, evidence-backed",
         "Acted on vs muted or regretted; unsubscribes", "Is agent-started work wanted, or noise?"),
        ("Interview stage", "Keep helping users who land an interview",
         "Later-stage progress; exit reason recorded as hire or frustration", "Does lifecycle help change why people leave?"),
        ("Re-entry", "One opt-in check-in after a hire", "Opt-in rate; return rate at the next search",
         "Is “come back next time” a real path?"),
        ("Packaging control", "A search-window pass or a pause, no agent change",
         "Revenue across the search; exit reasons; returns", "Is churn more about pricing than product?"),
        ("Protected control", "A held-out group stays on today's job agent",
         "Every result is read against this group", "Did the agent change anything at all?"),
    ]
    y = I(2.3)
    for t, sub, meas, dec in rows:
        k.hrule(s, k.LM, y, k.CW)
        k.text(s, cols[0][0], y + I(0.1), cols[0][1], I(0.7), [
            {"text": t, "size": 15.5, "bold": True, "space_after": 1},
            {"text": sub, "size": 12, "color": k.SEC, "line": 1.05}])
        k.text(s, cols[1][0], y + I(0.12), cols[1][1], I(0.6), [{"text": meas, "size": 12.5, "color": k.SEC, "line": 1.05}])
        k.text(s, cols[2][0], y + I(0.12), cols[2][1], I(0.6), [{"text": dec, "size": 12.5, "line": 1.05}])
        y += I(0.74)
    box = k.rect(s, k.LM, I(6.06), k.CW, I(0.72), fill=k.TEAL_TINT, rounded=True, radius=0.12, name="Kill rule")
    k.shape_text(box, [{"runs": [
        ("Narrow or stop ", {"bold": True}),
        ("if muted beats acted-on, or if packaging alone moves retention as much as the agent. Each step is reversible: "
         "close it and users keep the job agent and their record. A test, not a churn guarantee.", {"color": k.INK})], "size": 12.5, "line": 1.05}],
        anchor=MSO_ANCHOR.MIDDLE)


# ---------------------------------------------------------------- 11 decisions
def d_decide(s, n, g):
    k = K(g)
    items = [
        ("Agree the two paths and the order.", "Lead with Tsenta inside the agents people already use. Tsenta's own agent stays open to anyone who switches or has none."),
        ("Pick the pilot slice.", "Which existing users, and the one owned channel to run it on."),
        ("Tsenta holds every employer-facing yes.", "Collected on a Tsenta surface and bound to the exact action, whichever door it came through."),
    ]
    y = I(2.45)
    for i, (head, body) in enumerate(items):
        k.text(s, k.LM, y - I(0.05), I(0.7), I(0.8), [{"text": str(i + 1), "size": 40, "bold": True, "color": k.TEAL}])
        k.text(s, k.LM + I(0.75), y, I(5.9), I(1.2), [
            {"text": head, "size": 21, "bold": True, "space_after": 4},
            {"text": body, "size": 14.5, "color": k.SEC, "line": 1.1}])
        y += I(1.3)
    box = k.rect(s, I(8.0), I(2.4), I(4.53), I(3.9), fill=k.PAPER, rounded=True, radius=0.04, name="Facts panel")
    box.text_frame.margin_left = box.text_frame.margin_right = I(0.3)
    box.text_frame.margin_top = I(0.3)
    paras = [{"text": "FACTS ONLY TSENTA HAS", "size": 11, "bold": True, "color": k.TEAL_DK, "spacing": 100, "space_after": 12}]
    for q in ["Does Tsenta text users first today, or only reply?",
              "Which iMessage path does Tsenta use?",
              "How many users connect through MCP, and what do they do there?",
              "What share of users already use an AI assistant?"]:
        paras.append({"text": q, "size": 15, "line": 1.08, "space_after": 12})
    k.shape_text(box, paras)


# ---------------------------------------------------------------- appendix helpers
def table(s, k, x, y, w, col_w, header, rows, size=11, head_size=10, row_h=None, status_col=None):
    nrows, ncols = len(rows) + 1, len(header)
    gt = s.shapes.add_table(nrows, ncols, int(x), int(y), int(w), int(I(0.3) * nrows))
    tbl = gt.table
    tblPr = tbl._tbl.tblPr
    for a in ("firstRow", "bandRow"):
        tblPr.set(a, "0")
    for j, cw in enumerate(col_w):
        tbl.columns[j].width = int(cw)
    for i in range(nrows):
        if row_h:
            tbl.rows[i].height = int(row_h)
        for j in range(ncols):
            cell = tbl.cell(i, j)
            cell.fill.solid()
            cell.fill.fore_color.rgb = k.PAPER if i == 0 else k.WHITE
            cell.margin_left = cell.margin_right = I(0.08)
            cell.margin_top = cell.margin_bottom = I(0.04)
            val = header[j] if i == 0 else rows[i - 1][j]
            tf = cell.text_frame
            tf.word_wrap = True
            tf.text = ""
            p = tf.paragraphs[0]
            r = p.add_run()
            r.text = val
            bold = i == 0 or (status_col is not None and j == status_col) or j == 0
            color = k.TEAL_DK if (i == 0 or (status_col is not None and j == status_col)) else (k.INK if j == 0 else k.SEC)
            k._run_props(r, head_size if i == 0 else size, bold, color)
    # thin rules: set bottom border on every cell
    from lxml import etree
    from pptx.oxml.ns import qn
    for i in range(nrows):
        for j in range(ncols):
            tcPr = tbl.cell(i, j)._tc.get_or_add_tcPr()
            for tag_ in ("a:lnL", "a:lnR", "a:lnT", "a:lnB"):
                ln = etree.SubElement(tcPr, qn(tag_))
                if tag_ == "a:lnB":
                    ln.set("w", "9525")
                    sf = etree.SubElement(ln, qn("a:solidFill"))
                    etree.SubElement(sf, qn("a:srgbClr")).set("val", "E4E0DD")
                else:
                    ln.set("w", "0")
                    etree.SubElement(ln, qn("a:noFill"))
            # border elements must precede the fill in tcPr; move fill to the end
            fill = tcPr.find(qn("a:solidFill"))
            if fill is not None:
                tcPr.remove(fill)
                tcPr.append(fill)
    gt.name = "Table"
    return gt


def d_a1(s, n, g):
    k = K(g)
    rows = [
        ("Text doors: iMessage and WhatsApp", "LIVE TODAY", "tsenta.com; tsenta.com/messaging"),
        ("MCP server for Claude, Cursor, Codex", "LIVE TODAY", "tsenta.com/mcp"),
        ("Matches by text; reply yes to apply", "LIVE TODAY", "tsenta.com"),
        ("One shared record behind every door", "PROPOSED", "This proposal; not implemented. Internal status unknown"),
        ("Approval collected by Tsenta, bound to the exact action", "PROPOSED", "Design; MCP route not shipped. Today approval “depends on your client”"),
        ("Switch: bring career facts and a resume, you review", "PROPOSED", "Roadmap, not built. No chat-history or memory import"),
        ("Agent-started notes beyond new matches", "PROPOSED", "This proposal; not implemented. Internal status unknown"),
        ("Career-adjacent help: interviews, offers, grad school, next move", "PROPOSED, THEN VISION", "No job-search product found for the first 90 days; standalone coaches exist; demand not shown"),
        ("Life coverage beyond career", "VISION", "Demand not shown. Opt-in, opened on evidence"),
        ("Wake adapters per host", "PROPOSED", "Server-started runs: ChatGPT MCP Events only (docs); tested on no host"),
        ("Effect on churn", "NOT PROVEN", "The pilot tests it"),
        ("Unknown states, bound yes, you-send drafts", "SYNTHETIC DEMO", "Prototype on made-up data; not Tsenta"),
    ]
    table(s, k, k.LM, I(1.8), k.CW, [I(5.0), I(2.1), k.CW - I(7.1)], ["ITEM", "STATUS", "BASIS"], rows,
          size=11.5, row_h=I(0.35), status_col=1)


def d_a2(s, n, g):
    k = K(g)
    rows = [
        ("ChatGPT (Chat, Work)", "Full MCP: Business, Enterprise, Edu (beta, admin, web); Pro read-only; published-plugin reach by plan unknown",
         "MCP Events into Work chats and dots; eligible plans not documented",
         "Unattended plugin writes not documented"),
        ("ChatGPT dots", "Installed plugins", "Its own decision, a set time or a supported event; MCP Events",
         "Research read-only; assigned recurring tasks can include actions you authorized (automatic review)"),
        ("Claude (web, Desktop)", "Remote MCP; documented up to 2025-11-25",
         "Scheduled tasks with connectors (paid plans); no server-triggered run",
         "Research mode calls connector tools without further approval"),
        ("Claude Code", "HTTP, SSE, stdio; 2026-07-28 on the v2 runtime",
         "Routines (1 hour minimum); channels in research preview, not on 2026-07-28", "Routines: no permission prompts"),
        ("Gemini app", "Custom app by MCP URL", "Schedules and monitors (AI Pro, Ultra); no server trigger",
         "Manual confirmation for any write"),
        ("Cursor", "stdio, SSE, HTTP", "Automations on a schedule or webhook", "No approval step described"),
        ("Poke", "Remote MCP by URL", "Inbound API (vendor API, not MCP)", "Not documented"),
        ("Meta Muse", "Meta-reviewed connector; user custom connectors exist, MCP form unknown",
         "Background use of third-party connectors unknown", "Ask on first use; sensitive writes ask every time"),
        ("Instinct", "No MCP, plugin or API route published", "Text or call only (public site)", "Not published"),
    ]
    table(s, k, k.LM, I(1.8), k.CW, [I(1.9), I(2.9), I(3.9), k.CW - I(8.7)],
          ["HOST", "STANDARD MCP (DOCS)", "PROACTIVE PATH (DOCS)", "UNATTENDED WRITES (DOCS)"], rows, size=10.5,
          row_h=I(0.43))
    k.text(s, k.LM, I(6.53), k.CW, I(0.3), [
        {"text": "Cells condensed from each host's documentation, read October 13; ChatGPT, Muse and Instinct re-read October 14. Nothing here is tested.",
         "size": 10.5, "color": k.SEC}])


def d_a3(s, n, g):
    k = K(g)
    facts = [
        ("The current MCP revision is 2026-07-28.", "modelcontextprotocol.io/specification/versioning"),
        ("“Every interaction begins with the client.” Servers must not initiate requests.",
         "modelcontextprotocol.io/specification/2026-07-28/basic/patterns"),
        ("Push is a client-opened stream of change notices (subscriptions/listen).",
         "modelcontextprotocol.io/specification/2026-07-28/basic/patterns/subscriptions"),
        ("Server-initiated events are on the roadmap. The Events extension (SEP-3415) is a draft.",
         "modelcontextprotocol.io/development/roadmap and github.com/modelcontextprotocol/modelcontextprotocol/pull/3415"),
        ("Sampling is deprecated, so an agent behind MCP pays for its own model calls.",
         "modelcontextprotocol.io/specification/2026-07-28/deprecated"),
        ("ChatGPT MCP Events lets a subscribed server wake ChatGPT in Work chats and dots. ChatGPT decides what the user sees.",
         "developers.openai.com/plugins/build/mcp-events"),
    ]
    y = I(1.85)
    for f, src in facts:
        k.hrule(s, k.LM, y, k.CW)
        k.text(s, k.LM, y + I(0.11), I(6.3), I(0.62), [{"text": f, "size": 14, "line": 1.05}])
        k.text(s, I(7.35), y + I(0.13), k.W - k.LM - I(7.35), I(0.62), [{"text": src, "size": 9, "color": k.SEC, "line": 1.05}])
        y += I(0.68)
    k.text(s, k.LM, y + I(0.2), k.CW, I(0.6), [
        {"text": "So: standard MCP alone does not let Tsenta reach a user first today, and some hosts now add a wake path. "
                 "Build for both.", "size": 15, "bold": True, "color": k.TEAL_DK, "line": 1.05}])


def d_a4(s, n, g):
    k = K(g)
    colw = (k.CW - I(0.6)) / 2
    groups = [
        ("GENERAL AGENTS", [
            ("OpenAI dots", "Background research over connected apps, read-only; Pro, Business Premium, Enterprise."),
            ("Meta Muse", "Free tier; in its own app and directly in WhatsApp; reviewed connector platform."),
            ("Gemini Task (formerly Spark)", "Runs 24/7 in Google AI Pro and Ultra."),
            ("Instinct", "Raised $1B at a $10B valuation (September 28)."),
            ("Poke", "Texts first; the first AI agent approved on Apple Messages for Business (TechCrunch, June)."),
        ]),
        ("CAREER AGENTS", [
            ("Fonzi", "A text channel plus an MCP (“what's next for me?”)."),
            ("AI Applyd", "An MCP whose tools can file a real application."),
            ("Simplify", "Autopilot submits, in private early access; AI email through the offer stage."),
            ("Indeed, ZipRecruiter, Dice", "Read-only job search connectors in Claude that hand off to apply."),
            ("Sprout, Sorce", "Swipe-to-apply on iOS: 4.60 from 71,723 ratings; 4.70 from 35,637."),
        ]),
    ]
    for gi, (hd, items) in enumerate(groups):
        x = k.LM + gi * (colw + I(0.6))
        k.text(s, x, I(1.85), colw, I(0.3), [{"text": hd, "size": 11, "bold": True, "color": k.TEAL_DK, "spacing": 100}])
        y = I(2.2)
        for name, body in items:
            k.hrule(s, x, y, colw)
            k.text(s, x, y + I(0.1), colw, I(0.7), [
                {"runs": [(name + "  ", {"bold": True, "color": k.INK}), (body, {"color": k.SEC})], "size": 13, "line": 1.05}])
            y += I(0.74)
    k.text(s, k.LM, I(6.05), k.CW, I(0.6), [
        {"text": "Open space, among job-search products only: none found that covers onboarding and the first 90 days. "
                 "Standalone coaches exist; demand is not shown.", "size": 14, "bold": True, "color": k.TEAL_DK, "line": 1.05}])


def d_a5(s, n, g):
    k = K(g)
    rows = [
        ("Job searches end. Context: median duration of unemployment, 11.5 weeks, September 2026 (BLS).",
         "Count a hire as success. Test re-entry and packaging next to the agent."),
        ("An agent on top of weak matching inherits the complaints.",
         "Don't pitch the agent as a matching fix. Watch muted vs acted-on."),
        ("Owned channels have rules: WhatsApp free-form only within 24 hours of the user's last message; "
         "Apple Messages for Business requires live agents.", "Treat Tsenta's channel as a consented, per-channel notice router."),
        ("Per-action prompts are a weak gate: Claude Code users approve 97% of permission prompts.",
         "One preview bound to the exact payload, collected by Tsenta."),
        ("Hosts are becoming proactive on their own.", "Be the connector they call. Keep the record and the yes in Tsenta."),
        ("Vision: life raises consent stakes. A new purpose likely needs new consent (our CTIA reading); WhatsApp's general-purpose AI clause.",
         "Open each ring only on evidence and a fresh opt-in."),
        ("Public copy says no other job agent offers MCP. Fonzi, AI Applyd and LoopCV now do.", "Update it before any MCP-led message."),
    ]
    table(s, k, k.LM, I(1.8), k.CW, [I(6.6), k.CW - I(6.6)], ["RISK", "WHAT WE WOULD DO"], rows, size=12, row_h=I(0.56))


def d_sources(items):
    def draw(s, n, g):
        k = K(g)
        y = I(1.8)
        for label, url in items:
            k.text(s, k.LM, y, I(3.3), I(0.26), [{"text": label, "size": 10.5, "bold": True}])
            k.text(s, k.LM + I(3.4), y + I(0.01), k.CW - I(3.4), I(0.26), [{"text": url, "size": 9, "color": k.SEC}])
            y += I(0.24)
    return draw


SOURCES_1 = [
    ("Tsenta homepage", "https://tsenta.com/"),
    ("Tsenta messaging", "https://tsenta.com/messaging"),
    ("Tsenta MCP", "https://tsenta.com/mcp"),
    ("Tsenta MCP connector docs", "https://docs.tsenta.com/product/mcp-connector"),
    ("Tsenta AI agent comparison", "https://tsenta.com/ai-agent"),
    ("MCP versioning", "https://modelcontextprotocol.io/specification/versioning"),
    ("MCP patterns", "https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns"),
    ("MCP subscriptions", "https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/subscriptions"),
    ("MCP roadmap", "https://modelcontextprotocol.io/development/roadmap"),
    ("MCP deprecated features", "https://modelcontextprotocol.io/specification/2026-07-28/deprecated"),
    ("SEP-3415 Events extension (draft)", "https://github.com/modelcontextprotocol/modelcontextprotocol/pull/3415"),
    ("ChatGPT MCP Events", "https://developers.openai.com/plugins/build/mcp-events.md"),
    ("ChatGPT automations", "https://learn.chatgpt.com/docs/automations.md"),
    ("ChatGPT connectors", "https://help.openai.com/en/articles/11487775-connectors-in-chatgpt"),
    ("Claude connector features", "https://claude.com/docs/connectors/building/index.md"),
    ("Claude custom connectors", "https://support.claude.com/en/articles/11175166-getting-started-with-custom-connectors-using-remote-mcp"),
    ("Claude Code MCP", "https://code.claude.com/docs/en/mcp.md"),
    ("Claude Code channels", "https://code.claude.com/docs/en/channels.md"),
    ("Claude Code scheduled tasks", "https://code.claude.com/docs/en/scheduled-tasks.md"),
    ("Gemini custom apps, writes", "https://support.google.com/gemini/answer/17209137?hl=en"),
    ("Gemini Task rename", "https://support.google.com/gemini/answer/17094507?hl=en"),
    ("Menlo Ventures consumer AI 2026", "https://menlovc.com/wp-content/uploads/2026/09/menlo_ventures_consumer_ai_report-2026.pdf"),
]
SOURCES_2 = [
    ("Cursor automations", "https://cursor.com/docs/cloud-agent/automations.md"),
    ("Poke API", "https://poke.com/docs/api"),
    ("OpenAI dots", "https://openai.com/index/introducing-dots/"),
    ("Meta Muse announcement", "https://about.fb.com/news/2026/09/introducing-muse-personal-ai-agent/"),
    ("Muse connector platform", "https://muse.ai/platform/docs"),
    ("WhatsApp AI providers policy", "https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing/ai-providers.md"),
    ("WhatsApp terms change (TechCrunch)", "https://techcrunch.com/2025/10/18/whatssapp-changes-its-terms-to-bar-general-purpose-chatbots-from-its-platform/"),
    ("Apple Messages for Business FAQ", "https://register.apple.com/resources/messages/messaging-documentation/faq"),
    ("Poke on Apple Messages (TechCrunch)", "https://www.techcrunch.com/2026/06/04/apple-approves-poke-as-the-first-ai-agent-on-its-messages-for-business-platform/"),
    ("Instinct funding (SiliconANGLE)", "https://siliconangle.com/2026/09/28/everyday-personal-ai-assistant-startup-instinct-raises-1b-at-10b-valuation/"),
    ("Instinct recommendations (TechCrunch)", "https://techcrunch.com/2026/09/30/instincts-new-product-recommendations-are-giving-some-users-the-ick/"),
    ("Claude Code auto mode (97% approvals)", "https://claude.com/blog/auto-mode-default-in-claude-code"),
    ("Proactive assistant study", "https://arxiv.org/html/2410.04596v2"),
    ("BLS median unemployment duration", "https://api.bls.gov/publicAPI/v2/timeseries/data/LNS13008276"),
    ("Pew chatbot use", "https://www.pewresearch.org/chart/chatgpt-tops-the-list-of-chatbots-americans-use-across-age-groups/"),
    ("Fonzi", "https://talent.fonzi.ai/"),
    ("AI Applyd MCPs", "https://aiapplyd.com/mcps"),
    ("Indeed connector for Claude", "https://www.claude.com/connectors/indeed"),
    ("Sprout and Sorce ratings (App Store)", "https://itunes.apple.com/lookup?id=6740011494"),
    ("Uber Q2 2025 remarks", "https://s23.q4cdn.com/407969754/files/doc_earnings/2025/q2/transcript/Uber-Q2-25-Prepared-Remarks.pdf"),
    ("Grab 2025 results", "https://www.grab.com/sg/press/others/grab-reports-fourth-quarter-and-2025-results-with-first-full-year-net-profit/"),
    ("Duolingo Q3 2025 letter (SEC)", "https://www.sec.gov/Archives/edgar/data/1562088/000162828025049514/q3fy25duolingo9-30x25share.htm"),
    ("LinkedIn buys Lynda.com (Fortune)", "https://fortune.com/2015/04/09/linkedin-lynda-learning/"),
    ("Facebook M shutdown (TechCrunch)", "https://techcrunch.com/2018/01/08/facebook-is-shutting-down-its-standalone-personal-assistant-m/"),
    ("Fin pivot (TechCrunch)", "https://techcrunch.com/2019/07/02/sam-lessin-and-andrew-kortina-on-their-voice-assistants-workplace-pivot"),
    ("GoButler pivot (TechCrunch)", "https://techcrunch.com/2016/03/17/a-pivot-please"),
    ("Mezi acquired (TechCrunch)", "https://techcrunch.com/2018/01/30/virtual-travel-assistant-mezi-acquired-by-american-express/"),
    ("Uber Q4 2025 remarks", "https://s23.q4cdn.com/407969754/files/doc_earnings/2025/q4/transcript/Uber-Q4-25-Prepared-Remarks.pdf"),
    ("Gemini Spark 24/7 (Gemini Drops)", "https://gemini.google/gemini-drops/"),
    ("CTIA Messaging Principles (consent records)", "https://api.ctia.org/wp-content/uploads/2023/05/230523-CTIA-Messaging-Principles-and-Best-Practices-FINAL.pdf"),
    ("FCRA definitions, 15 U.S.C. 1681a", "https://www.law.cornell.edu/uscode/text/15/1681a"),
    ("CPPA ADMT rules announcement", "https://cppa.ca.gov/announcements/2025/20250923.html"),
    ("CPPA ADMT rule text", "https://cppa.ca.gov/regulations/pdf/ccpa_updates_cyber_risk_admt_appr_text.pdf"),
    ("Hermes Agent SECURITY.md (e06df9c)", "https://raw.githubusercontent.com/NousResearch/hermes-agent/e06df9c2eae6901f4c88f464e0ae6e753c0428b8/SECURITY.md"),
    ("Hermes Agent LICENSE (e06df9c)", "https://raw.githubusercontent.com/NousResearch/hermes-agent/e06df9c2eae6901f4c88f464e0ae6e753c0428b8/LICENSE"),
    ("Hermes PRs merged Oct 6 to 13", "https://api.github.com/search/issues?q=repo:NousResearch/hermes-agent+is:pr+is:merged+merged:>=2026-10-06"),
    ("Public commercial Hermes fork", "https://api.github.com/repos/withoneai/hermes-agent"),
    ("OpenClaw SECURITY.md (047b629)", "https://github.com/openclaw/openclaw/blob/047b629eb8fcbbda4f9ef4e0f834b57af005ef3d/SECURITY.md"),
    ("Pydantic AI deferred tools (approvals)", "https://ai.pydantic.dev/deferred-tools/"),
    ("Pydantic AI durable execution with DBOS", "https://ai.pydantic.dev/durable_execution/dbos/"),
    ("Muse and OpenClaw (TechCrunch)", "https://techcrunch.com/2026/09/22/meta-admits-muses-likeness-to-openclaw-isnt-a-coincidence/"),
    ("Claude model pricing (cost model)", "https://platform.claude.com/docs/en/about-claude/pricing"),
    ("Cloud Run pricing (cost model)", "https://cloud.google.com/run/pricing"),
    ("Fly.io pricing (always-on VM)", "https://fly.io/docs/about/pricing/"),
    ("Neon Postgres pricing (state floor)", "https://neon.com/pricing"),
    ("Browserbase pricing (hosted browser)", "https://www.browserbase.com/pricing"),
    ("AWS Bedrock AgentCore pricing", "https://aws.amazon.com/bedrock/agentcore/pricing/"),
    ("OWASP Top 10 for LLM applications", "https://genai.owasp.org/llm-top-10/"),
    ("AICPA on SOC 2 assurance", "https://www.aicpa-cima.com/topic/audit-assurance/audit-and-assurance-greater-than-soc-2"),
    ("OpenClaw docs: attach (per docs index)", "https://docs.openclaw.ai/cli/attach"),
    ("OpenClaw docs: cloud workers (per index)", "https://docs.openclaw.ai/gateway/cloud-workers"),
    ("OpenClaw docs: ACP and Codex (per index)", "https://docs.openclaw.ai/help/testing-live/acp-and-codex"),
    ("OpenClaw docs: swarm (per docs index)", "https://docs.openclaw.ai/tools/swarm"),
    ("OpenClaw docs: context engine (per index)", "https://docs.openclaw.ai/concepts/context-engine"),
    ("OpenClaw docs: sessions and subagents", "https://docs.openclaw.ai/gateway/config-tools/sessions-and-subagents"),
    ("OpenClaw docs: Docker sandbox (per index)", "https://docs.openclaw.ai/gateway/sandboxing/docker-backend"),
    ("OpenClaw docs index (read Oct 13)", "https://docs.openclaw.ai/llms.txt"),
    ("Prototype screenshots", "Local synthetic demo at commit 07ad8fb, captured October 13"),
]

# Roadmap content: from 548 WEDGE-TO-LIFE-VERDICT.md FINAL 17:25 (rings and L1-L3 gates; see source-notes.txt).
C_ROADMAP = [
    dict(step="JOB, NOW", kind="today", tag="live today", head="The job agent",
         covers="Live: finds roles and applies, with optional review. Proposed: one record, a Tsenta-held yes, sparse notes.",
         gate_label="CAREER IS TESTED BY",
         gate="A checklist for offer-stage users: 90-day retention against users without it, and the opt-in rate for move help."),
    dict(step="CAREER", kind="proposed", tag="proposed", head="Interview to day 90",
         covers="First interview to offer, offer to day 90, then between searches: notice, the move, benefits, the first paycheck.",
         gate_label="LIFE OPENS WHEN",
         gate="Non-career requests pass a set share of inbound messages, such as 25% over 2 months, with fresh consent."),
    dict(step="LIFE", kind="vision", tag="vision", head="What users turn out to ask for",
         covers="Life tasks users bring to the agent unprompted, if they do, added one at a time.",
         gate_label="THE REST OF LIFE NEEDS",
         gate="Channels whose rules allow a broad assistant, an approval model for open-ended tasks, sustained demand."),
    dict(step="LIFE, LATER", kind="vision", tag="vision", head="The rest of life",
         covers="One agent across career and life, behind one approval record.",
         gate_label="PRICING",
         gate="Bundled into job plans with usage quotas, mainly the higher tiers. No separate life price."),
]
C_ROADMAP_FOOT = "Gated by data, not dates. Each stage is a reversible experiment against a job-agent-only control group; if it fails, it closes."


# ---------------------------------------------------------------- 2 two paths (reframe R1)
def d_paths(s, n, g):
    k = K(g)
    gap = I(0.3)
    cw = int((k.CW - 2 * gap) / 3)
    y0, ch = I(2.3), I(3.6)
    k.text(s, k.LM, I(1.92), 2 * cw + gap, I(0.3), [{"text": "ALREADY USE AN AGENT: TWO CHOICES", "size": 11, "bold": True,
                                                      "color": k.TEAL_DK, "spacing": 100}])
    k.text(s, k.LM + 2 * (cw + gap), I(1.92), cw, I(0.3), [{"text": "NO AGENT YET", "size": 11, "bold": True,
                                                             "color": k.TEAL_DK, "spacing": 100}])
    cards = [
        ("A  ·  CONNECT", "Keep yours. Add Tsenta.",
         [("Live today: ", "Tsenta's MCP server for Claude, Cursor and Codex."),
          ("ChatGPT, per its docs: ", "full use in admin-enabled Business, Enterprise and Edu (beta, web only); Pro read-only; "
                                      "a published plugin's consumer reach is unconfirmed."),
          ("Design, not shipped: ", "your agent proposes; you approve on Tsenta. No parity with Tsenta's own agent is claimed.")], True),
        ("B  ·  SWITCH", "Use Tsenta's own agent.",
         [("Live today: ", "the job agent on iMessage, WhatsApp, web and apps."),
          ("Roadmap: ", "bring your career, not your chat history. Paste a summary, add a resume, review before it saves."),
          ("Proposed: ", "Tsenta's own agent picks when to speak first. Inside other agents, the host sets the timing.")], False),
        ("TSENTA'S OWN AGENT", "Start with the job.",
         [("Live today: ", "sign up, upload a resume; Tsenta finds roles and applies."),
          ("Vision: ", "keeping the job, then life admin and productivity, added as users ask for it.")], False),
    ]
    for i, (lab, head, rows, hot) in enumerate(cards):
        x = k.LM + i * (cw + gap)
        b = k.rect(s, x, y0, cw, ch, fill=k.TEAL_TINT if hot else k.WHITE, line=k.TEAL if hot else k.RULE,
                   line_w=1.25 if hot else 1.0, dash=(i == 2), rounded=True, radius=0.05, name=f"Path {lab}")
        b.text_frame.margin_left = b.text_frame.margin_right = I(0.24)
        b.text_frame.margin_top = I(0.22)
        paras = [{"text": lab, "size": 10.5, "bold": True, "color": k.TEAL_DK, "spacing": 100, "space_after": 5},
                 {"text": head, "size": 19, "bold": True, "space_after": 8, "line": 1.05}]
        for h, t in rows:
            paras.append({"runs": [(h, {"bold": True}), (t, {"color": k.SEC})], "size": 12.5, "line": 1.04, "space_after": 5})
        k.shape_text(b, paras, anchor=MSO_ANCHOR.TOP)
    bar = k.rect(s, k.LM, I(5.95), k.CW, I(0.5), fill=k.INK, rounded=True, radius=0.12, name="One core")
    k.shape_text(bar, [{"runs": [("Every path runs on one Tsenta core: ", {"bold": True, "color": k.WHITE}),
                                 ("your goal, your career record, your yes. Proposed, not built (slides 10 and 11).", {"color": k.WHITE})],
                        "size": 13.5, "align": PP_ALIGN.CENTER}], anchor=MSO_ANCHOR.MIDDLE)
    k.text(s, k.LM, I(6.52), k.CW, I(0.3), [
        {"text": "Host facts from each host's own docs, read October 14; nothing tested (appendix A2). Tsenta keeps its own career "
                 "record; it cannot read or write another agent's memory.", "size": 10.5, "color": k.SEC}])


def slides(include_roadmap=True, include_cost=True):
    S = []
    S.append(dict(kicker="Tsenta  ·  company-wide proposal for discussion", title="Keep your agent. Add Tsenta.",
                  tsize=54, ty=I(1.55), th=I(3.2), tw=I(10.8), draw=d_title, footer=False, notes=N1))
    S.append(dict(kicker="The journey  ·  two paths in  ·  today's base marked", title="Two paths in. One Tsenta core.", draw=d_paths,
                  source="tsenta.com/mcp; docs.tsenta.com; OpenAI help 12584461; MCP 2026-07-28", status="proposed", notes=NPATHS))
    S.append(dict(kicker="Why the job comes first", title="The job search is where an agent earns trust.", draw=d_wedge,
                  source="BLS; Menlo Ventures 2026; Meta; OpenAI; WhatsApp Business policy", status="vision", notes=N4))
    S.append(dict(kicker="Live today  ·  public, checked October 13", title="The doors already exist.", draw=d_today,
                  source="tsenta.com, tsenta.com/messaging, tsenta.com/mcp, docs.tsenta.com", notes=N2))
    S.append(dict(kicker="Real agent test  ·  an outside agent  ·  dummy records  ·  final run: a qualified pass", title="A real agent, calling a job core.",
                  draw=d_demo, source="Test runs, October 13 and 14", status="agenttest", notes=NDEMO))
    S.append(dict(kicker="Synthetic concept  ·  earlier prototype on a laptop", title="The earlier prototype, on made-up data.",
                  draw=d_proto, source="Local prototype, commit 07ad8fb", status="synthetic", notes=N8))
    S.append(dict(kicker="Synthetic  ·  ideal state  ·  one career", title="One career, from first job to a PhD.", draw=d_story,
                  status="synthetic", notes=N7))
    if include_roadmap:
        S.append(dict(kicker="Roadmap  ·  job, career, life", title="From the job to the rest of life.",
                      draw=d_roadmap, status="vision", notes=N9))
    S.append(dict(kicker="Hypothesis  ·  retention first, then the name", title="Job agent first. Life agent earned.",
                  draw=d_earn, source="ZipRecruiter, Gallup, Match Group, TechCrunch, Google, Meta", status="vision",
                  notes=NEARN))
    S.append(dict(kicker="Proposed  ·  the core", title="One brain: your goal, one record, a loop, and your yes.", draw=d_core,
                  status="proposed", notes=N5))
    S.append(dict(kicker="Proposed  ·  the architecture for both paths", title="Your agent or Tsenta's, one core underneath.",
                  draw=d_doors, source="Host docs: OpenAI, Anthropic, Google, Cursor, Poke, Meta, Instinct", status="proposed", notes=N6))
    S.append(dict(kicker="Proposed  ·  the pilot", title="A cheap test with existing users.", draw=d_pilot,
                  status="proposed", notes=N10))
    S.append(dict(kicker="For today", title="Three decisions, four facts.", draw=d_decide, status="vision", notes=N11))
    S.append(dict(kicker="Appendix Q1  ·  for questions  ·  proposed, company-wide", title="What has to be true before real users.",
                  th=I(0.7), draw=d_enterprise, source="Feasibility review, October 13; 15 U.S.C. 1681a; CPPA; OWASP; AICPA", status="proposed", notes=NE))
    if include_cost:
        S.append(dict(kicker="Appendix Q2  ·  for questions  ·  illustrative list prices", title="Cost follows use, not idle users.",
                      th=I(0.7), draw=d_cost, source="Scale-cost model; vendor list prices, October 13, 2026", status="proposed", notes=NC))
    S.append(dict(kicker="Appendix A0  ·  precedents, mechanism not proof", title="Wedges that grew stayed adjacent.",
                  tsize=30, th=I(0.7), draw=d_prec, source="Uber, Grab, Duolingo filings; TechCrunch; Fortune", status="vision", notes=NP))
    S.append(dict(kicker="Appendix A1", title="Today, proposed, proven.", tsize=30, th=I(0.7), draw=d_a1, notes=NA1))
    S.append(dict(kicker="Appendix A2", title="Host matrix: what each host documents. Tested on none.", tsize=30, th=I(0.7),
                  draw=d_a2, source="OpenAI, Anthropic, Google, Cursor, Poke, Meta docs; instinct.com", notes=NA2))
    S.append(dict(kicker="Appendix A3", title="What MCP can and cannot do today.", tsize=30, th=I(0.7), draw=d_a3, notes=NA3))
    S.append(dict(kicker="Appendix A4", title="General agents race; career inside them is mostly search.", tsize=30,
                  th=I(0.7), draw=d_a4, source="Vendor pages and press, October 13 (sources appendix)", notes=NA4))
    S.append(dict(kicker="Appendix A5", title="Risks, and what we would do about them.", tsize=30, th=I(0.7), draw=d_a5, notes=NA5))
    S.append(dict(kicker="Appendix A6  ·  proposed requirements, not claims", title="Fourteen gates, pilot then production.",
                  tsize=30, th=I(0.7), draw=d_matrix, status="proposed", notes=NAM))
    S.append(dict(kicker="Appendix A7  ·  conditional trial, production not selected", title="Build path: OpenClaw on trial, an SDK as baseline.", tsize=30, th=I(0.7), source="SECURITY.md files; OpenClaw docs index; Pydantic AI docs",
                  draw=d_options, status="proposed", notes=NAO))
    S.append(dict(kicker="Appendix A8  ·  proposed gates, nothing built", title="Core above, swappable workers below.", tsize=30,
                  th=I(0.7), draw=d_gates, source="Runtime review build verdict, October 13", status="proposed", notes=NAG))
    S.append(dict(kicker="Appendix A9  ·  proposed gates, nothing built", title="Enterprise gates 8 to 15.", tsize=30,
                  th=I(0.7), draw=d_gates2, source="Runtime review build verdict and cross-check, October 13", status="proposed",
                  notes=NAG2))
    allsrc = SOURCES_1 + SOURCES_2
    for i in range(0, len(allsrc), 20):
        part = i // 20 + 1
        S.append(dict(kicker=f"Appendix A{9 + part}", title=f"Sources ({part} of {(len(allsrc) + 19) // 20})", tsize=30, th=I(0.7),
                      draw=d_sources(allsrc[i:i + 20]), notes=[NA6, NA7, NA8, NA9][part - 1]))
    return S


from notes import *  # noqa: E402,F401,F403  speaker notes N1..N11, NA1..NA7
