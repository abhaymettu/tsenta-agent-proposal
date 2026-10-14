"""Worker client: one OpenClaw Gateway agent turn per user message (548 s2, s8; 551 v32/v33).

The Gateway (pinned openclaw@2026.10.3) runs in the oc551-worker container, holds the model key and the proxy config, and
calls this core's MCP tools through the edge. A turn is two fixed commands, both operator constants:
  1. the task text goes over `docker exec -i` STDIN into /demo/io/task.md (tmpfs); never argv, never /demo/ping.md
  2. `docker exec oc551-worker /opt/demo/agent-turn.sh <session key>`, which runs `openclaw agent --agent main
     --session-key <key> --message-file /demo/io/task.md --json`. Without --local the CLI sends the agent RPC and the run
     executes inside the Gateway; there is no embedded fallback (551, agent-via-gateway at the pin :747-751).
The exec'd CLI holds only the gateway token, so the key never leaves the Gateway. Never --local, never `agent exec`
(asserted on the argv). The result needs a runId and a result object; origin, which the pin sets only on a failed Gateway
run, must be absent or "gateway" (551 v55). Without WORKER_CONTAINER the worker is offline and the
server fails closed. There is no fallback to a direct model call anywhere in this repo; the core never holds a model key.
"""
import json, os, re, subprocess, threading

DOCKER = ['docker', '--context', 'desktop-linux', 'exec']
TASK_FILE = '/demo/io/task.md'
TURN_SCRIPT = '/opt/demo/agent-turn.sh'
SESSION_KEY = re.compile(r'tsenta-demo-g[0-9]+-P[0-9][0-9]')   # agent-turn.sh enforces the same shape


class WorkerOffline(Exception):
    pass


class TurnUnknown(WorkerOffline):
    """The turn command timed out or could not be waited on; the Gateway may still be running it. Shown as UNKNOWN, never
    as success or as "nothing was done", and never retried (G-i)."""


def safe_argv(argv):
    """The turn never runs the agent embedded in the exec'd process (it would need the key) and never runs `agent exec`."""
    if '--local' in argv or any(a == 'agent' and b == 'exec' for a, b in zip(argv, argv[1:])):
        raise WorkerOffline('refused: a worker command may never use --local or agent exec')
    return argv


class Worker:
    def __init__(self, gateway_url=None, container=None, run=subprocess.run):
        self.url = gateway_url or os.environ.get('OPENCLAW_GATEWAY_URL')
        self.container = container or os.environ.get('WORKER_CONTAINER')
        self.run = run
        self.lock = threading.Lock()   # one fixed task file, so one turn at a time: write plus turn (551 v33 W-1)

    def status(self):
        if not self.container:
            return {'state': 'offline', 'reason': 'no worker container configured (WORKER_CONTAINER unset)'}
        return {'state': 'configured', 'container': self.container}

    def run_turn(self, session_key, text, turn):
        """Returns {reply, run_id, session_key, version, pid, model, usage}; raises WorkerOffline on any failure."""
        if not self.container:
            raise WorkerOffline(self.status()['reason'])
        if not SESSION_KEY.fullmatch(session_key):
            raise WorkerOffline('refused: bad session key')
        with self.lock:
            try:
                w = self.run(safe_argv(DOCKER + ['-i', '-u', 'node', self.container, 'sh', '-c', f'umask 077; cat > {TASK_FILE}']),
                             input=text.encode(), capture_output=True, timeout=15)
            except (OSError, subprocess.TimeoutExpired):
                raise WorkerOffline('could not hand the task to the worker')   # W-3: no turn was started
            if w.returncode != 0:
                raise WorkerOffline('could not hand the task to the worker')
            try:
                r = self.run(safe_argv(DOCKER + ['-u', 'node', self.container, TURN_SCRIPT, session_key]),
                             capture_output=True, timeout=660)
            except (OSError, subprocess.TimeoutExpired):
                raise TurnUnknown('turn timed out; outcome UNKNOWN')   # W-2: the Gateway run may still be going
        out, err = r.stdout.decode(errors='replace'), r.stderr.decode(errors='replace')
        if 'sk-ant-' in out or 'sk-ant-' in err:   # counted, never shown
            raise WorkerOffline('refused: the worker output held a key-shaped token, so nothing from it is used')
        try:
            res = json.loads(out)
        except ValueError:
            raise WorkerOffline(f'the worker returned no result (exit {r.returncode})')
        # 551 v55: the pin attaches origin "gateway" only to a failed Gateway run (failure-output:12-16); a success prints the
        # agent RPC's final response, which has no origin. So: origin absent or "gateway", a runId, and a result object.
        if (not isinstance(res, dict) or res.get('origin', 'gateway') != 'gateway'
                or not isinstance(res.get('runId'), str) or not res['runId'] or not isinstance(res.get('result'), dict)):
            raise WorkerOffline('refused: the result is not a Gateway agent response')
        if r.returncode != 0 or res.get('status') not in ('ok', 'completed'):
            raise WorkerOffline(f'the agent turn did not finish (status {str(res.get("status"))[:40]})')
        result = res.get('result') if isinstance(res.get('result'), dict) else {}
        payloads = result.get('payloads') if isinstance(result.get('payloads'), list) else []
        meta = result.get('meta') if isinstance(result.get('meta'), dict) else {}
        agent = meta.get('agentMeta') if isinstance(meta.get('agentMeta'), dict) else {}
        return {'reply': '\n\n'.join(p['text'] for p in payloads if isinstance(p, dict) and isinstance(p.get('text'), str)),
                'run_id': res.get('runId'), 'session_key': session_key, 'version': '2026.10.3',
                'pid': None, 'model': agent.get('model'), 'usage': agent.get('usage')}

    def reset(self, generation):
        """Reset hook: the session key rotates with the generation, so old transcripts are never resumed (548 s9)."""
        return {'deleted': 0, 'generation': generation}
