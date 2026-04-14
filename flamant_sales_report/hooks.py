"""Post-install / upgrade hook: auto-map sales teams to channel/country/shop/cluster/comparability."""
import logging

_logger = logging.getLogger(__name__)

# Mapping table. Each tuple: (lowercase substring match, channel, country, shop_label, shop_cluster, comp_status).
# The match is case-insensitive substring.
TEAM_DEFAULTS = [
    # === Shops BE ===
    ('brussel',              'shops',        'BE',    'Brussels',            'Flamant Sablon',      'comparible'),
    ('sablon',               'shops',        'BE',    'Brussels',            'Flamant Sablon',      'comparible'),
    ('bru',                  'shops',        'BE',    'Brussels',            'Flamant Sablon',      'comparible'),
    ('sint-martens-latem',   'shops',        'BE',    'Sint-Martens-Latem',  'Flamant SML',         'comparible'),
    ('martens',              'shops',        'BE',    'Sint-Martens-Latem',  'Flamant SML',         'comparible'),
    ('sml',                  'shops',        'BE',    'Sint-Martens-Latem',  'Flamant SML',         'comparible'),
    ('sint-genesius',        'shops',        'BE',    'Sint-Genesius-Rode',  'Flamant SGR',         'comparible'),
    ('genesius',             'shops',        'BE',    'Sint-Genesius-Rode',  'Flamant SGR',         'comparible'),
    ('sgr',                  'shops',        'BE',    'Sint-Genesius-Rode',  'Flamant SGR',         'comparible'),
    ('antwerpen',            'shops',        'BE',    'Antwerpen',           'Flamant Antwerpen',   'non_comparible'),
    ('knokke',               'shops',        'BE',    'Knokke',              'Flamant Knokke',      'non_comparible'),
    ('kortrijk',             'shops',        'BE',    'Kortrijk',            'Flamant Kortrijk',    'non_comparible'),
    # === Shops FR ===
    ('paris',                'shops',        'FR',    'Paris',               'Flamant PSG',         'comparible'),
    ('par',                  'shops',        'FR',    'Paris',               'Flamant PSG',         'comparible'),
    ('psg',                  'shops',        'FR',    'Paris',               'Flamant PSG',         'comparible'),
    ('aix',                  'shops',        'FR',    'Aix-en-Provence',     'Flamant Aix',         'non_comparible'),
    ('bhv',                  'shops',        'FR',    'BHV Paris',           'BHV Paris',           'non_comparible'),
    # === Online / E-Commerce ===
    ('e-comm be',            'ecommerce',    'BE',    'E-Comm BE',           'E-Comm BE',           'comparible'),
    ('e-comm fr',            'ecommerce',    'FR',    'E-Comm FR',           'E-Comm FR',           'comparible'),
    ('e-comm int',           'ecommerce',    'INT',   'E-Comm INT',          'E-Comm INT',          'comparible'),
    ('website',              'ecommerce',    'INT',   'Website',             'E-Comm INT',          'comparible'),
    ('e-commerce',           'ecommerce',    'INT',   'E-Commerce',          'E-Comm INT',          'comparible'),
    ('ecommerce',            'ecommerce',    'INT',   'E-Commerce',          'E-Comm INT',          'comparible'),
    ('online',               'ecommerce',    'INT',   'Online',              'E-Comm INT',          'comparible'),
    # === Wholesale ===
    ('wholesale - internal', 'wholesale',    'INT',   'Wholesale Internal',  'Wholesale - Internal','comparible'),
    ('wholesale - agent',    'wholesale',    'INT',   'Wholesale Agent',     'Wholesale - Agent',   'comparible'),
    ('wholesale',            'wholesale',    'INT',   'Wholesale',           'Wholesale - Internal','comparible'),
    # === Franchise ===
    ('jordan',               'franchise',    'INT',   'Jordan',              'Flamant Jordan',      'non_comparible'),
    ('franchise',            'franchise',    'INT',   'Franchise',           'Franchise',           'non_comparible'),
    # === Flamant@Home ===
    ('flamant@home',         'flamant_home', 'BE',    'Flamant@Home',        'Flamant at Home',     'non_comparible'),
    ('at home',              'flamant_home', 'BE',    'Flamant@Home',        'Flamant at Home',     'non_comparible'),
    ('home',                 'flamant_home', 'BE',    'Flamant@Home',        'Flamant at Home',     'non_comparible'),
    # === Catch-all ===
    ('showroom',             'other',        'BE',    'Showroom',            'Flamant at Showroom', 'non_comparible'),
    ('point of sale',        'other',        'OTHER', 'Point of Sale',       '',                    'non_comparible'),
    ('sales',                'other',        'OTHER', 'Sales',               '',                    'non_comparible'),
]


def post_init_hook(env):
    """Auto-map sales teams on install and on module upgrade."""
    _flamant_remap(env)


def _flamant_remap(env):
    """Re-evaluate team mappings based on TEAM_DEFAULTS.

    Teams with an explicit (non-'other') channel are preserved; teams on the
    'other' fallback are re-evaluated so that updated rules take effect.
    """
    teams = env['crm.team'].search([])
    updated = 0
    for team in teams:
        name = (team.name or '').lower()
        can_remap = not team.x_channel or team.x_channel == 'other'
        matched = False
        for needle, channel, country, label, cluster, comp in TEAM_DEFAULTS:
            if needle in name:
                matched = True
                vals = {}
                if can_remap:
                    vals['x_channel'] = channel
                    vals['x_country_code'] = country
                    vals['x_comp_status'] = comp
                if label and (not team.x_shop_label or can_remap):
                    vals['x_shop_label'] = label
                if cluster and (not team.x_shop_cluster or can_remap):
                    vals['x_shop_cluster'] = cluster
                if vals:
                    team.write(vals)
                    updated += 1
                break
        if not matched and not team.x_channel:
            team.write({
                'x_channel': 'other',
                'x_country_code': 'OTHER',
                'x_comp_status': 'non_comparible',
            })
            updated += 1
    _logger.info('flamant_sales_report: auto-mapped %s sales teams', updated)
