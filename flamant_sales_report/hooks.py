"""Post-install hook: auto-map existing sales teams to channel/country/shop."""
import logging

_logger = logging.getLogger(__name__)

# Best-guess mapping by team name. Each tuple = (lowercase match, channel, country, shop_label).
# The match is case-insensitive contains.
TEAM_DEFAULTS = [
    ('brussel',              'shops',     'BE',    'Brussels'),
    ('paris',                'shops',     'FR',    'Paris'),
    ('sint-martens-latem',   'shops',     'BE',    'Sint-Martens-Latem'),
    ('martens',              'shops',     'BE',    'Sint-Martens-Latem'),
    ('sint-genesius',        'shops',     'BE',    'Sint-Genesius-Rode'),
    ('genesius',             'shops',     'BE',    'Sint-Genesius-Rode'),
    ('aix',                  'shops',     'FR',    'Aix-en-Provence'),
    ('flamant@home',         'shops',     'BE',    'Flamant@Home'),
    ('wholesale',            'wholesale', 'OTHER', ''),
    ('website',              'ecommerce', 'OTHER', 'Website'),
    ('e-commerce',           'ecommerce', 'OTHER', 'E-Commerce'),
    ('ecommerce',            'ecommerce', 'OTHER', 'E-Commerce'),
]


def post_init_hook(env):
    teams = env['crm.team'].search([])
    updated = 0
    for team in teams:
        name = (team.name or '').lower()
        for needle, channel, country, label in TEAM_DEFAULTS:
            if needle in name:
                vals = {}
                if not team.x_channel:
                    vals['x_channel'] = channel
                if not team.x_country_code:
                    vals['x_country_code'] = country
                if label and not team.x_shop_label:
                    vals['x_shop_label'] = label
                if vals:
                    team.write(vals)
                    updated += 1
                break
        else:
            # no match: mark as Other so the team still shows up in the report
            if not team.x_channel:
                team.write({'x_channel': 'other', 'x_country_code': 'OTHER'})
                updated += 1
    _logger.info('flamant_sales_report: auto-mapped %s sales teams', updated)
