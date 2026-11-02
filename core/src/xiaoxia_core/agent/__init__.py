"""简单 Agent、会话和技能管理公共入口。
Created on 2026-11-01; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""

from importlib import import_module

__all__ = ["AgentEvent", "SimpleAgent", "SessionSnapshot", "SessionStore", "Skill", "SkillRegistry"]


def __getattr__(name):
    modules = {"AgentEvent": "runtime", "SimpleAgent": "runtime", "SessionSnapshot": "sessions",
               "SessionStore": "sessions", "Skill": "skills", "SkillRegistry": "skills"}
    if name not in modules:
        raise AttributeError(name)
    value = getattr(import_module('.' + modules[name], __name__), name)
    globals()[name] = value
    return value
