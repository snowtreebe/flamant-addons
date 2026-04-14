"""Post-install / upgrade hook: auto-map sales teams to channel/country/shop/cluster/comparability.

Mapping table mirrors the ListDATA sheet of the Flamant master dashboard
(see 02_Data/Reports/Flamant - DASHBOARD- Marge.xlsx). Each tuple:
    (lowercase substring match, channel, country, shop_label, shop_cluster, comp_status)

The first matching rule wins, so more specific patterns (e.g. "flamant at
showroom") must come before broader ones (e.g. "showroom").
"""
import logging

_logger = logging.getLogger(__name__)

TEAM_DEFAULTS = [
    # =====================================================================
    # OTHER channel: internal / non-commercial buckets (Showroom + Personnel)
    # These are intentional categories, NOT a catch-all.
    # =====================================================================
    ('flamant at showroom',  'other',        'BE',    'Showroom',            'Flamant at Showroom',  'non_comparible'),
    ('at showroom',          'other',        'BE',    'Showroom',            'Flamant at Showroom',  'non_comparible'),
    ('flamant personeel',    'other',        'BE',    'Personeel',           'Flamant Personeel',    'non_comparible'),
    ('personeel',            'other',        'BE',    'Personeel',           'Flamant Personeel',    'non_comparible'),
    ('personel',             'other',        'BE',    'Personeel',           'Flamant Personeel',    'non_comparible'),

    # =====================================================================
    # OUTLET channel
    # =====================================================================
    ('flamant outlet',       'outlet',       'BE',    'Outlet',              'Flamant Outlet Geraardsbergen', 'non_comparible'),
    ('outlet',               'outlet',       'BE',    'Outlet',              'Flamant Outlet Geraardsbergen', 'non_comparible'),

    # =====================================================================
    # FRANCHISE channel
    # =====================================================================
    ('flamant jordan',       'franchise',    'INT',   'Jordan',              'Flamant Jordan',       'non_comparible'),
    ('jordan',               'franchise',    'INT',   'Jordan',              'Flamant Jordan',       'non_comparible'),
    ('franchise',            'franchise',    'INT',   'Franchise',           'Franchise',            'non_comparible'),

    # =====================================================================
    # FLAMANT@HOME channel (FL@H)
    # =====================================================================
    ('flamant at home',      'flamant_home', 'BE',    'Flamant@Home',        'Flamant at Home',      'non_comparible'),
    ('flamant@home',         'flamant_home', 'BE',    'Flamant@Home',        'Flamant at Home',      'non_comparible'),
    ('at home',              'flamant_home', 'BE',    'Flamant@Home',        'Flamant at Home',      'non_comparible'),
    ('fl@h',                 'flamant_home', 'BE',    'Flamant@Home',        'Flamant at Home',      'non_comparible'),

    # =====================================================================
    # SHOPS — BE (comparible = established, non_comparible = pop-ups / new)
    # =====================================================================
    ('brussel-sablon',       'shops',        'BE',    'Brussels',            'Flamant Brussel-Sablon', 'comparible'),
    ('brussel',              'shops',        'BE',    'Brussels',            'Flamant Brussel-Sablon', 'comparible'),
    ('sablon',               'shops',        'BE',    'Brussels',            'Flamant Brussel-Sablon', 'comparible'),
    ('bru',                  'shops',        'BE',    'Brussels',            'Flamant Brussel-Sablon', 'comparible'),
    ('sint martens latem',   'shops',        'BE',    'Sint-Martens-Latem',  'Flamant Sint Martens Latem', 'comparible'),
    ('sint-martens-latem',   'shops',        'BE',    'Sint-Martens-Latem',  'Flamant Sint Martens Latem', 'comparible'),
    ('martens',              'shops',        'BE',    'Sint-Martens-Latem',  'Flamant Sint Martens Latem', 'comparible'),
    ('sml',                  'shops',        'BE',    'Sint-Martens-Latem',  'Flamant Sint Martens Latem', 'comparible'),
    ('sint-genesius',        'shops',        'BE',    'Sint-Genesius-Rode',  'Flamant Sint-Genesius-Rode', 'comparible'),
    ('genesius',             'shops',        'BE',    'Sint-Genesius-Rode',  'Flamant Sint-Genesius-Rode', 'comparible'),
    ('sgr',                  'shops',        'BE',    'Sint-Genesius-Rode',  'Flamant Sint-Genesius-Rode', 'comparible'),
    ('antwerpen',            'shops',        'BE',    'Antwerpen',           'Flamant Antwerpen - Koetshuis', 'non_comparible'),
    ('koetshuis',            'shops',        'BE',    'Antwerpen',           'Flamant Antwerpen - Koetshuis', 'non_comparible'),
    ('knokke',               'shops',        'BE',    'Knokke',              'Flamant Knokke POP-UP', 'non_comparible'),
    ('kortrijk',             'shops',        'BE',    'Kortrijk',            'Flamant Kortrijk pop-up','non_comparible'),

    # =====================================================================
    # SHOPS — FR
    # =====================================================================
    ('paris-germain',        'shops',        'FR',    'Paris',               'Flamant Paris-Germain','comparible'),
    ('flamant paris',        'shops',        'FR',    'Paris',               'Flamant Paris-Germain','comparible'),
    ('paris',                'shops',        'FR',    'Paris',               'Flamant Paris-Germain','comparible'),
    ('psg',                  'shops',        'FR',    'Paris',               'Flamant Paris-Germain','comparible'),
    ('par',                  'shops',        'FR',    'Paris',               'Flamant Paris-Germain','comparible'),
    ('aix',                  'shops',        'FR',    'Aix-en-Provence',     'Flamant Aix-en-Provence','non_comparible'),
    ('bhv',                  'shops',        'FR',    'BHV Paris',           'BHV Paris',            'non_comparible'),
    ('galeries lafayette',   'shops',        'FR',    'GL Nice',             'Galeries Lafayette Nice', 'non_comparible'),
    ('gl nice',              'shops',        'FR',    'GL Nice',             'Galeries Lafayette Nice', 'non_comparible'),

    # =====================================================================
    # ONLINE channel (E-Commerce)
    # Cluster granularity: E-Comm BE / FR / INT
    # =====================================================================
    ('e-comm be',            'ecommerce',    'INT',   'E-Comm BE',           'E-Comm BE',            'comparible'),
    ('flamant online shop le 02', 'ecommerce','INT',  'E-Comm BE',           'E-Comm BE',            'comparible'),
    ('online shop returns',  'ecommerce',    'INT',   'E-Comm BE',           'E-Comm BE',            'comparible'),
    ('e-comm fr',            'ecommerce',    'FR',    'E-Comm FR',           'E-Comm FR',            'comparible'),
    ('online le 03',         'ecommerce',    'FR',    'E-Comm FR',           'E-Comm FR',            'comparible'),
    ('e-comm int',           'ecommerce',    'INT',   'E-Comm INT',          'E-Comm INT',           'comparible'),
    ('online le',            'ecommerce',    'INT',   'E-Comm INT',          'E-Comm INT',           'comparible'),
    ('online shop le',       'ecommerce',    'INT',   'E-Comm INT',          'E-Comm INT',           'comparible'),
    ('online 07',            'ecommerce',    'INT',   'E-Comm INT',          'E-Comm INT',           'comparible'),
    ('flamant online',       'ecommerce',    'INT',   'E-Comm INT',          'E-Comm INT',           'comparible'),
    ('website',              'ecommerce',    'INT',   'Website',             'E-Comm INT',           'comparible'),
    ('e-commerce',           'ecommerce',    'INT',   'E-Commerce',          'E-Comm INT',           'comparible'),
    ('ecommerce',            'ecommerce',    'INT',   'E-Commerce',          'E-Comm INT',           'comparible'),
    ('online',               'ecommerce',    'INT',   'Online',              'E-Comm INT',           'comparible'),

    # =====================================================================
    # WHOLESALE channel
    # =====================================================================
    ('wholesale - internal', 'wholesale',    'INT',   'Wholesale Internal',  'Wholesale - Internal', 'comparible'),
    ('wholesale internal',   'wholesale',    'INT',   'Wholesale Internal',  'Wholesale - Internal', 'comparible'),
    ('wholesale - agent',    'wholesale',    'INT',   'Wholesale Agent',     'Wholesale - Agent',    'comparible'),
    ('wholesale agent',      'wholesale',    'INT',   'Wholesale Agent',     'Wholesale - Agent',    'comparible'),
    ('wholesale',            'wholesale',    'INT',   'Wholesale',           'Wholesale - Internal', 'comparible'),
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
