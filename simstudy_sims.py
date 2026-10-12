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
    try:
        import services
        import services
        household = services.active_household()
        if household is None or not os.path.isfile(BINDING):
            return
        binding = read(BINDING)
        d = rewards()
        if str(household.id) != binding.get("sims_household_id") or d["household_id"] != binding.get("anki_household_id"):
            return
        prior = binding.get("last_synced_earned")
        if type(prior) is not int or prior < 0:
            return
        delta = d["simoleons_earned"] - prior
        if delta <= 0:
            return
        if delta > 100000:
            log("Blocked unusually large reward delta")
            return
        before = int(household.funds.money)
        # Verify the game truly applied the funds before recording a sync.
        sims4.commands.execute("sims.modify_funds {}".format(delta), connection)
        after = int(household.funds.money)
        if after - before != delta:
            log("Funds change not verified: {} to {} expected {}".format(before, after, delta))
            return
        binding["last_synced_earned"] = d["simoleons_earned"]
        write(BINDING, binding)
        if not quiet and connection is not None:
            say(connection, "SimStudy awarded {} Simoleons".format(delta))
    except Exception:
        log(traceback.format_exc())
        if connection is not None and not quiet:
            say(connection, "SimStudy sync failed. Inspect sims4_bridge.log")

def tick(handle):
    sync(quiet=True)

@sims4.commands.Command("simstudy.ping", command_type=sims4.commands.CommandType.Live)
def ping(_connection=None):
    say(_connection, "SimStudy experimental bridge loaded")

@sims4.commands.Command("simstudy.status", command_type=sims4.commands.CommandType.Live)
def status(_connection=None):
    try:
        d = rewards()
        say(_connection, "Cards {} | Earned {} | Auto {}".format(d.get("total_cards"), d["simoleons_earned"], ALARM is not None))
    except Exception:
        log(traceback.format_exc())
        say(_connection, "Reward data unavailable")

@sims4.commands.Command("simstudy.bind", command_type=sims4.commands.CommandType.Live)
def bind(_connection=None):
    try:
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
    except Exception:
        log(traceback.format_exc())
        say(_connection, "Binding failed")

@sims4.commands.Command("simstudy.start", command_type=sims4.commands.CommandType.Live)
def start(_connection=None):
    global ALARM
    try:
        household = services.active_household()
        binding = read(BINDING)
        if household is None or str(household.id) != binding.get("sims_household_id"):
            say(_connection, "BLOCKED: open bound study household")
            return
        if ALARM is None:
            import alarms
            import clock
            ALARM = alarms.add_alarm(household, clock.interval_in_sim_minutes(1), tick, repeating=True)
        say(_connection, "SimStudy checking earnings every in-game minute")
        sync(_connection)
    except Exception:
        log(traceback.format_exc())
        say(_connection, "Auto sync could not start")

@sims4.commands.Command("simstudy.stop", command_type=sims4.commands.CommandType.Live)
def stop(_connection=None):
    global ALARM
    if ALARM is not None:
        import alarms
        alarms.cancel_alarm(ALARM)
        ALARM = None
    say(_connection, "SimStudy auto sync stopped")

@sims4.commands.Command("simstudy.sync", command_type=sims4.commands.CommandType.Live)
def sync_command(_connection=None):
    sync(_connection)
