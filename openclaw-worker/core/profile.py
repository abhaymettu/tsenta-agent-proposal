"""Profile source (551 s2a, 548 TSENTA-PROFILE-ADAPTER.md). FAKE (the fixture persona) is the default and the only
mode this build runs. REAL-READ and REAL-WRITE need, together: the config value, a matching start flag, a vault
credential loaded by the tool server, and a written allowlist of upstream methods. None exist yet (OAuth not
obtained), so a real request refuses and the source stays FAKE. No tool argument or record content can change this.
"""

FAKE, REAL_MODES = 'fixture', ('real_read', 'real_write')
FIELDS = ('name', 'field', 'seniority', 'location', 'tz', 'families', 'goal', 'salary_floor', 'visa', 'start_date', 'workplace', 'canary_fact')
UNSET_CHECK = ('salary_floor', 'visa', 'start_date', 'workplace')


class ProfileSource:
    def __init__(self, mode=FAKE, start_flag=FAKE, credential=None, allowlist=None):
        self.mode, self.refused = FAKE, None
        if (mode, start_flag) != (FAKE, FAKE):
            missing = [n for n, ok in (('matching start flag', mode == start_flag and mode in REAL_MODES),
                                       ('vault credential', bool(credential)), ('written allowlist', bool(allowlist))) if not ok]
            # Even with all three present this build has no real client yet; it must be added through a standard MCP client.
            self.refused = f"refused {mode!r}/{start_flag!r}: missing {', '.join(missing) or 'a real MCP client in this build'}; running fixture"

    def get(self, persona):
        return {'profile': {k: persona.get(k) for k in FIELDS}, 'unset': [k for k in UNSET_CHECK if persona.get(k) is None],
                'mode': self.mode, 'source': 'fictional fixture persona'}
