from .scripts.active_directory_get_inactive_computers import get_inactive_computers as _get_inactive_computers
from .scripts.active_directory_query import active_directory_query
from .scripts.active_directory_query_assistant import active_directory_query_assistant
from ldap3 import SUBTREE, ALL_ATTRIBUTES

def get_inactive_computers(days=30, base_dn='DC=win,DC=dtu,DC=dk'):
    return _get_inactive_computers(days=days, base_dn=base_dn)
    

def execute_active_directory_query(*, base_dn, search_filter, search_attributes=ALL_ATTRIBUTES, limit=None, excluded_attributes=[]):
    return active_directory_query(base_dn=base_dn, search_filter=search_filter, search_attributes=search_attributes, limit=limit, excluded_attributes=excluded_attributes)


def execute_active_directory_query_assistant(*, user_prompt):
    return active_directory_query_assistant(user_prompt=user_prompt)
