"""Minimal loading diagnostic: no Anki data, household calls, or save changes."""
import sims4.commands

@sims4.commands.Command('simstudy.test', command_type=sims4.commands.CommandType.Live)
def simstudy_test(_connection=None):
    sims4.commands.CheatOutput(_connection)('SimStudy diagnostic loaded successfully')
