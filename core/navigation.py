"""Shared role-specific, accessible navigation definitions for IhingaAI.

Pure Python by design: navigation roles and item uniqueness can be regression tested
without importing Streamlit or starting the machine-learning models.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class NavItem:
    page: str
    label: str
    icon: str
    group: str
    rw_label: str = ''


ROLE_NAV = {
    'farmer': (
        NavItem('Home', 'Dashboard', 'space_dashboard', 'OVERVIEW', 'Ahabanza'),
        NavItem('My farming season', 'My farming season', 'agriculture', 'FARM MANAGEMENT', 'Igihembwe cyanjye'),
        NavItem('My fields', 'My fields', 'grass', 'FARM MANAGEMENT', 'Imirima yanjye'),
        NavItem('Estimate', 'Harvest estimates', 'monitoring', 'FARM MANAGEMENT', 'Gereranya umusaruro'),
        NavItem('Guided recommendations', 'AI recommendations', 'tips_and_updates', 'FARM MANAGEMENT'),
        NavItem('Crop monitoring', 'Crop health & progress', 'health_and_safety', 'FARM MANAGEMENT'),
        NavItem('Farm finances', 'Farm finances', 'account_balance_wallet', 'FARM MANAGEMENT'),
        NavItem('Market Prices', 'Market Prices', 'storefront', 'INSIGHTS & SUPPORT', 'Ibiciro ku masoko'),
        NavItem('Farm Risk Assessment', 'Farm Risk Assessment', 'health_and_safety', 'INSIGHTS & SUPPORT', 'Isuzuma ry’ingaruka'),
        NavItem('Smart alerts', 'Smart alerts', 'notifications_active', 'INSIGHTS & SUPPORT'),
        NavItem('Weather', 'Weather', 'partly_cloudy_day', 'INSIGHTS & SUPPORT', 'Ikirere'),
        NavItem('Farmer community', 'Farmer community', 'groups', 'INSIGHTS & SUPPORT'),
        NavItem('Agronomist support', 'Agronomist support', 'support_agent', 'INSIGHTS & SUPPORT'),
        NavItem('AI assistant', 'AI Assistant', 'smart_toy', 'INSIGHTS & SUPPORT'),
        NavItem('Profile', 'My profile', 'person', 'ACCOUNT', 'Umwirondoro'),
        NavItem('About IhingaAI', 'About & Data Sources', 'info', 'ABOUT'),
    ),
    'agronomist': (
        NavItem('Overview', 'Dashboard', 'space_dashboard', 'OVERVIEW'),
        NavItem('Shared fields', 'Assigned fields', 'grass', 'FIELD OPERATIONS'),
        NavItem('Field monitoring', 'Field monitoring', 'clinical_notes', 'FIELD OPERATIONS'),
        NavItem('Consultations', 'Consultations', 'forum', 'FIELD OPERATIONS'),
        NavItem('Advisory notes', 'Advisory notes', 'edit_note', 'FIELD OPERATIONS'),
        NavItem('AI Assistant', 'AI Assistant', 'smart_toy', 'INTELLIGENCE'),
        NavItem('About IhingaAI', 'About & Data Sources', 'info', 'ABOUT'),
    ),
    'planner': (
        NavItem('Overview', 'Dashboard', 'space_dashboard', 'OVERVIEW'),
        NavItem('Farm Risk Assessment', 'Farm Risk Assessment', 'health_and_safety', 'INTELLIGENCE'),
        NavItem('District analytics', 'District analytics', 'map', 'INTELLIGENCE'),
        NavItem('Historical survey', 'Historical survey', 'dataset', 'INTELLIGENCE'),
        NavItem('Harvest performance', 'Harvest performance', 'show_chart', 'INTELLIGENCE'),
        NavItem('Crop monitoring', 'Crop monitoring', 'health_and_safety', 'INTELLIGENCE'),
        NavItem('Farmer assignments', 'Farmer assignments', 'group_add', 'OPERATIONS'),
        NavItem('Resource planning', 'Resource planning', 'inventory_2', 'OPERATIONS'),
        NavItem('AI Assistant', 'AI Assistant', 'smart_toy', 'ASSISTANCE'),
        NavItem('About IhingaAI', 'About & Data Sources', 'info', 'ABOUT'),
    ),
}


def nav_items(role: str, guest: bool = False):
    """Return only authorized navigation choices (guest can estimate only)."""
    if role not in ROLE_NAV:
        raise ValueError(f'Unknown role: {role}')
    if guest:
        if role != 'farmer':
            raise ValueError('Only farmers have a guest mode')
        return tuple(x for x in ROLE_NAV['farmer'] if x.page == 'Estimate')
    return ROLE_NAV[role]


def selected_page(role: str, proposed: str | None, guest: bool = False) -> str:
    """Keep navigation within current role's allowed pages."""
    choices = nav_items(role, guest=guest)
    allowed = {x.page for x in choices}
    return proposed if proposed in allowed else choices[0].page


def page_slug(page: str) -> str:
    return ''.join(c if c.isalnum() else '_' for c in page).strip('_').lower()
