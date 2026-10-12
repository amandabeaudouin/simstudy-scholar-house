"""Isolated SimStudy bridge test. Read-only; does not modify Sims or Anki data."""
import sims4.commands

@sims4.commands.Command("simstudy.ping", command_type=sims4.commands.CommandType.Live)
def simstudy_ping(_connection=None):
    sims4.commands.CheatOutput(_connection)("SimStudy bridge stage 1 loaded")

@sims4.commands.Command("simstudy.status", command_type=sims4.commands.CommandType.Live)
def simstudy_status(_connection=None):
    sims4.commands.CheatOutput(_connection)("SimStudy bridge stage 1: commands working; rewards not yet connected")
