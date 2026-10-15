"""Experimental SimStudy Sims 4 script mod. Python 3.7 game bytecode required."""
import os
import json
import traceback
import sims4.commands

# Import game services lazily so optional game APIs cannot prevent command registration.

ROOT = os.path.join(os.path.expanduser("~"), "Documents", "SimStudyBridge")
REWARDS = os.path.join(ROOT, "rewards.json")
BINDING = os.path.join(ROOT, "sims_binding.json")
LOG = os.path.join(ROOT, "sims4_bridge.log")
ALARM = None
AUTO_CONNECTION = None
AUTO_TICKS = 0
AUTO_LAST_RESULT = "not started"

def log(message):
    try:
        os.makedirs(ROOT, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(str(message) + "\n")
    except Exception:
        pass

def read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def write(path, data):
    os.makedirs(ROOT, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)

def say(connection, message):
    sims4.commands.CheatOutput(connection)(message)

def rewards():
    d = read(REWARDS)
    if d.get("schema") != "simstudy.v1":
        raise ValueError("Unknown rewards schema")
    if not isinstance(d.get("household_id"), str) or not d["household_id"]:
        raise ValueError("Household ID missing")
    if not isinstance(d.get("household_name"), str):
        raise ValueError("Household name missing")
    amount = d.get("simoleons_earned")
    if type(amount) is not int or not 0 <= amount <= 100000000:
        raise ValueError("Bad amount")
    return d

def sync(connection=None, quiet=False):
    global AUTO_LAST_RESULT
    AUTO_LAST_RESULT = "checking"
    try:
        import services
        household = services.active_household()
        if household is None or not os.path.isfile(BINDING):
            AUTO_LAST_RESULT = "household or binding missing"
            return
        binding = read(BINDING)
        d = rewards()
        if str(household.id) != binding.get("sims_household_id") or d["household_id"] != binding.get("anki_household_id"):
            AUTO_LAST_RESULT = "household ID mismatch"
            return
        prior = binding.get("last_synced_earned")
        if type(prior) is not int or prior < 0:
            AUTO_LAST_RESULT = "invalid sync baseline"
            return
        delta = d["simoleons_earned"] - prior
        if delta <= 0:
            AUTO_LAST_RESULT = "no new earnings"
            return
        if delta > 100000:
            AUTO_LAST_RESULT = "reward safety limit"
            log("Blocked unusually large reward delta")
            return
        before = int(household.funds.money)
        # Verify the game truly applied the funds before recording a sync.
        sims4.commands.execute("sims.modify_funds {}".format(delta), connection)
        after = int(household.funds.money)
        if after - before != delta:
            AUTO_LAST_RESULT = "funds change unverified"
            log("Funds change not verified: {} to {} expected {}".format(before, after, delta))
            return
        binding["last_synced_earned"] = d["simoleons_earned"]
        write(BINDING, binding)
        AUTO_LAST_RESULT = "awarded {}".format(delta)
        if not quiet and connection is not None:
            say(connection, "SimStudy awarded {} Simoleons".format(delta))
    except Exception as exc:
        AUTO_LAST_RESULT = "sync error: {}".format(type(exc).__name__)
        log(traceback.format_exc())
        if connection is not None and not quiet:
            say(connection, "SimStudy sync failed: {}".format(type(exc).__name__))

def tick(handle):
    global AUTO_TICKS
    AUTO_TICKS += 1
    # A timer callback has no cheat-console connection of its own.
    # Reuse the connection captured by simstudy.start, otherwise the funds
    # command executes as session 0 and may silently fail.
    sync(connection=AUTO_CONNECTION, quiet=True)

@sims4.commands.Command("simstudy.ping", command_type=sims4.commands.CommandType.Live)
def ping(_connection=None):
    say(_connection, "SimStudy binding repair loaded")

@sims4.commands.Command("simstudy.status", command_type=sims4.commands.CommandType.Live)
def status(_connection=None):
    # Confirm command invocation before any file I/O.
    say(_connection, "SimStudy status running; checking rewards...")
    try:
        d = rewards()
        say(_connection, "Cards {} | Earned {} | Auto {} | Ticks {}".format(d.get("total_cards"), d["simoleons_earned"], ALARM is not None, AUTO_TICKS))
    except Exception as exc:
        say(_connection, "Rewards read error: {}".format(type(exc).__name__))
        log(traceback.format_exc())

@sims4.commands.Command("simstudy.path", command_type=sims4.commands.CommandType.Live)
def show_path(_connection=None):
    say(_connection, "SimStudy path test started")
    try:
        candidates = [
            os.path.join(os.path.expanduser("~"), "Documents", "SimStudyBridge", "rewards.json"),
            os.path.join(os.path.expanduser("~"), "Library", "Mobile Documents", "com~apple~CloudDocs", "Documents", "SimStudyBridge", "rewards.json"),
        ]
        for idx, candidate in enumerate(candidates):
            say(_connection, "Location {}: {}".format(idx + 1, "found" if os.path.isfile(candidate) else "not found"))
    except Exception as exc:
        say(_connection, "Path check error: {}".format(type(exc).__name__))

@sims4.commands.Command("simstudy.bindcheck", command_type=sims4.commands.CommandType.Live)
def bindcheck(_connection=None):
    say(_connection, "SimStudy household check running")
    try:
        import services
        household = services.active_household()
        if household is None:
            say(_connection, "No active household. Open a household in Live Mode.")
            return
        d = rewards()
        live_name = str(household.name).strip()
        study_name = str(d["household_name"]).strip()
        say(_connection, "Sims household: {}".format(live_name))
        say(_connection, "Anki household: {}".format(study_name))
        say(_connection, "Names match: {}".format(live_name.lower() == study_name.lower()))
    except Exception as exc:
        say(_connection, "Check error: {}".format(type(exc).__name__))

@sims4.commands.Command("simstudy.bind", command_type=sims4.commands.CommandType.Live)
def bind(_connection=None):
    say(_connection, "SimStudy binding started")
    try:
        import services
        household = services.active_household()
        d = rewards()
        if household is None or household.name.strip().lower() != d["household_name"].strip().lower():
            say(_connection, "BLOCKED: household name mismatch")
            return
        if os.path.isfile(BINDING):
            old = read(BINDING)
            if old.get("sims_household_id") != str(household.id):
                say(_connection, "BLOCKED: another household already bound")
                return
            say(_connection, "Study household already bound")
            return
        write(BINDING, {"sims_household_id": str(household.id), "anki_household_id": d["household_id"], "last_synced_earned": d["simoleons_earned"]})
        say(_connection, "Household bound. Future earnings can sync.")
    except Exception as exc:
        say(_connection, "Binding error: {}".format(type(exc).__name__))
        log(traceback.format_exc())

@sims4.commands.Command("simstudy.start", command_type=sims4.commands.CommandType.Live)
def start(_connection=None):
    global ALARM, AUTO_CONNECTION
    try:
        import services
        household = services.active_household()
        binding = read(BINDING)
        if household is None or str(household.id) != binding.get("sims_household_id"):
            say(_connection, "BLOCKED: open bound study household")
            return
        AUTO_CONNECTION = _connection
        if ALARM is None:
            import alarms
            import clock
            interval = clock.interval_in_sim_minutes(1)
            ALARM = alarms.add_alarm(household, interval, tick, repeating=True, repeating_time_span=interval)
        say(_connection, "SimStudy checking earnings every in-game minute (auto fix)")
        sync(_connection)
    except Exception:
        log(traceback.format_exc())
        say(_connection, "Auto sync could not start")

@sims4.commands.Command("simstudy.stop", command_type=sims4.commands.CommandType.Live)
def stop(_connection=None):
    global ALARM, AUTO_CONNECTION
    if ALARM is not None:
        import alarms
        alarms.cancel_alarm(ALARM)
        ALARM = None
    AUTO_CONNECTION = None
    say(_connection, "SimStudy auto sync stopped")

@sims4.commands.Command("simstudy.autostatus", command_type=sims4.commands.CommandType.Live)
def autostatus(_connection=None):
    say(_connection, "Auto {} | Ticks {} | Connection {} | Last {}".format(ALARM is not None, AUTO_TICKS, AUTO_CONNECTION is not None, AUTO_LAST_RESULT))

@sims4.commands.Command("simstudy.sync", command_type=sims4.commands.CommandType.Live)
def sync_command(_connection=None):
    sync(_connection)
