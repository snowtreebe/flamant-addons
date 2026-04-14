"""Post-install hook: auto-map existing sales teams to channel/country/shop."""
import logging

_logger = logging.getLogger(__name__)

# Best-guess mapping by team name. Each tuple = (lowercase match, channel, country, shop_label).
# The match is case-insensitive contains.
TEAM_DEFAULTS = [
    # Full names (real Flamant)
    ('brussel',              'shops',     'BE',    'Brussels'),
    ('paris',                'shops',     'FR',    'Paris'),
    ('sint-martens-latem',   'shops',     'BE',    'Sint-Martens-Latem'),
    ('martens',              'shops',     'BE',    'Sint-Martens-Latem'),
    ('sint-genesius',        'shops',     'BE',    'Sint-Genesius-Rode'),
    ('genesius',             'shops',     'BE',    'Sint-Genesius-Rode'),
    ('aix',                  'shops',     'FR',    'Aix-en-Provence'),
    ('flamant@home',         'shops',     'BE',    'Flamant@Home'),
    # Short codes (demo / abbreviated)
    ('sml',                  'shops',     'BE',    'Sint-Martens-Latem'),
    ('sgr',                  'shops',     'BE',    'Sint-Genesius-Rode'),
    ('bru',                  'shops',     'BE',    'Brussels'),
    ('par',                  'shops',     'FR',    'Paris'),
    # Wholesale / e-commerce
    ('wholesale',            'wholesale', 'OTHER', ''),
    ('website',              'ecommerce', 'OTHER', 'Website'),
    ('e-commerce',           'ecommerce', 'OTHER', 'E-Commerce'),
    ('ecommerce',            'ecommerce', 'OTHER', 'E-Commerce'),
]


def post_init_hook(env):
    """Auto-map sales teams on install and on module upgrade.

    Runs `env['crm.team']._flamant_remap()` — defined below. Already-tagged
    teams with a specific (non-'other') channel are left untouched; teams
    still on the 'other' fallback are re-evaluated so that re-running the
    upgrade picks up mapping improvements.
    """
    _flamant_remap(env)


def _flamant_remap(env):
    teams = env['crm.team'].search([])
    updated = 0
    for team in teams:
        name = (team.name or '').lower()
        # Only re-map teams that have no channel yet OR are on the 'other'
        # fallback — preserves explicit manual tagging.
        can_remap = not team.x_channel or team.x_channel == 'other'
        matched = False
        for needle, channel, country, label in TEAM_DEFAULTS:
            if needle in name:
                matched = True
                vals = {}
                if can_remap:
                    vals['x_channel'] = channel
                    vals['x_country_code'] = country
                if label and (not team.x_shop_label or can_remap):
                    vals['x_shop_label'] = label
                if vals:
                    team.write(vals)
                    updated += 1
                break
        if not matched and not team.x_channel:
            team.write({'x_channel': 'other', 'x_country_code': 'OTHER'})
            updated += 1
    _logger.info('flamant_sales_report: auto-mapped %s sales teams', updated)
