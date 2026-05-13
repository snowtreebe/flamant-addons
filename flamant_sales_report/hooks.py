"""Post-install / upgrade hook: auto-map sales teams to channel/country/shop/cluster.

Mapping table mirrors the ListDATA sheet of the Flamant master dashboard
(see 02_Data/Reports/Flamant - DASHBOARD- Marge.xlsx). Each tuple:
    (lowercase substring match, channel, country, shop_label, shop_cluster)

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
    ('flamant at showroom',  'other',        'BE',    'Showroom',            'Flamant at Showroom'),
    ('at showroom',          'other',        'BE',    'Showroom',            'Flamant at Showroom'),
    ('flamant personeel',    'other',        'BE',    'Personeel',           'Flamant Personeel'),
    ('personeel',            'other',        'BE',    'Personeel',           'Flamant Personeel'),
    ('personel',             'other',        'BE',    'Personeel',           'Flamant Personeel'),

    # =====================================================================
    # OUTLET channel
    # =====================================================================
    ('flamant outlet',       'outlet',       'BE',    'Outlet',              'Flamant Outlet Geraardsbergen'),
    ('outlet',               'outlet',       'BE',    'Outlet',              'Flamant Outlet Geraardsbergen'),

    # =====================================================================
    # FRANCHISE channel
    # =====================================================================
    ('flamant jordan',       'franchise',    'INT',   'Jordan',              'Flamant Jordan'),
    ('jordan',               'franchise',    'INT',   'Jordan',              'Flamant Jordan'),
    ('franchise',            'franchise',    'INT',   'Franchise',           'Franchise'),

    # =====================================================================
    # FLAMANT@HOME channel (FL@H)
    # =====================================================================
    ('flamant at home',      'flamant_home', 'BE',    'Flamant@Home',        'Flamant at Home'),
    ('flamant@home',         'flamant_home', 'BE',    'Flamant@Home',        'Flamant at Home'),
    ('at home',              'flamant_home', 'BE',    'Flamant@Home',        'Flamant at Home'),
    ('fl@h',                 'flamant_home', 'BE',    'Flamant@Home',        'Flamant at Home'),

    # =====================================================================
    # SHOPS — BE
    # =====================================================================
    ('brussel-sablon',       'shops',        'BE',    'Brussels',            'Flamant Brussel-Sablon'),
    ('brussel',              'shops',        'BE',    'Brussels',            'Flamant Brussel-Sablon'),
    ('sablon',               'shops',        'BE',    'Brussels',            'Flamant Brussel-Sablon'),
    ('bru',                  'shops',        'BE',    'Brussels',            'Flamant Brussel-Sablon'),
    ('sint martens latem',   'shops',        'BE',    'Sint-Martens-Latem',  'Flamant Sint Martens Latem'),
    ('sint-martens-latem',   'shops',        'BE',    'Sint-Martens-Latem',  'Flamant Sint Martens Latem'),
    ('martens',              'shops',        'BE',    'Sint-Martens-Latem',  'Flamant Sint Martens Latem'),
    ('sml',                  'shops',        'BE',    'Sint-Martens-Latem',  'Flamant Sint Martens Latem'),
    ('sint-genesius',        'shops',        'BE',    'Sint-Genesius-Rode',  'Flamant Sint-Genesius-Rode'),
    ('genesius',             'shops',        'BE',    'Sint-Genesius-Rode',  'Flamant Sint-Genesius-Rode'),
    ('sgr',                  'shops',        'BE',    'Sint-Genesius-Rode',  'Flamant Sint-Genesius-Rode'),
    ('antwerpen',            'shops',        'BE',    'Antwerpen',           'Flamant Antwerpen - Koetshuis'),
    ('koetshuis',            'shops',        'BE',    'Antwerpen',           'Flamant Antwerpen - Koetshuis'),
    ('knokke',               'shops',        'BE',    'Knokke',              'Flamant Knokke POP-UP'),
    ('kortrijk',             'shops',        'BE',    'Kortrijk',            'Flamant Kortrijk pop-up'),

    # =====================================================================
    # SHOPS — FR
    # =====================================================================
    ('paris-germain',        'shops',        'FR',    'Paris',               'Flamant Paris-Germain'),
    ('flamant paris',        'shops',        'FR',    'Paris',               'Flamant Paris-Germain'),
    ('paris',                'shops',        'FR',    'Paris',               'Flamant Paris-Germain'),
    ('psg',                  'shops',        'FR',    'Paris',               'Flamant Paris-Germain'),
    ('par',                  'shops',        'FR',    'Paris',               'Flamant Paris-Germain'),
    ('aix',                  'shops',        'FR',    'Aix-en-Provence',     'Flamant Aix-en-Provence'),
    ('bhv',                  'shops',        'FR',    'BHV Paris',           'BHV Paris'),
    ('galeries lafayette',   'shops',        'FR',    'GL Nice',             'Galeries Lafayette Nice'),
    ('gl nice',              'shops',        'FR',    'GL Nice',             'Galeries Lafayette Nice'),

    # =====================================================================
    # ONLINE channel (E-Commerce)
    # Cluster granularity: E-Comm BE / FR / INT
    # =====================================================================
    ('e-comm be',            'ecommerce',    'INT',   'E-Comm BE',           'E-Comm BE'),
    ('flamant online shop le 02', 'ecommerce','INT',  'E-Comm BE',           'E-Comm BE'),
    ('online shop returns',  'ecommerce',    'INT',   'E-Comm BE',           'E-Comm BE'),
    ('e-comm fr',            'ecommerce',    'FR',    'E-Comm FR',           'E-Comm FR'),
    ('online le 03',         'ecommerce',    'FR',    'E-Comm FR',           'E-Comm FR'),
    ('e-comm int',           'ecommerce',    'INT',   'E-Comm INT',          'E-Comm INT'),
    ('online le',            'ecommerce',    'INT',   'E-Comm INT',          'E-Comm INT'),
    ('online shop le',       'ecommerce',    'INT',   'E-Comm INT',          'E-Comm INT'),
    ('online 07',            'ecommerce',    'INT',   'E-Comm INT',          'E-Comm INT'),
    ('flamant online',       'ecommerce',    'INT',   'E-Comm INT',          'E-Comm INT'),
    ('website',              'ecommerce',    'INT',   'Website',             'E-Comm INT'),
    ('e-commerce',           'ecommerce',    'INT',   'E-Commerce',          'E-Comm INT'),
    ('ecommerce',            'ecommerce',    'INT',   'E-Commerce',          'E-Comm INT'),
    ('online',               'ecommerce',    'INT',   'Online',              'E-Comm INT'),

    # =====================================================================
    # WHOLESALE channel
    # =====================================================================
    ('wholesale - internal', 'wholesale',    'INT',   'Wholesale Internal',  'Wholesale - Internal'),
    ('wholesale internal',   'wholesale',    'INT',   'Wholesale Internal',  'Wholesale - Internal'),
    ('wholesale - agent',    'wholesale',    'INT',   'Wholesale Agent',     'Wholesale - Agent'),
    ('wholesale agent',      'wholesale',    'INT',   'Wholesale Agent',     'Wholesale - Agent'),
    ('wholesale',            'wholesale',    'INT',   'Wholesale',           'Wholesale - Internal'),
]


def post_init_hook(env):
    """Auto-map sales teams and backfill account tags on install."""
    _flamant_remap(env)
    _flamant_tag_accounts(env)


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
        for needle, channel, country, label, cluster in TEAM_DEFAULTS:
            if needle in name:
                matched = True
                vals = {}
                if can_remap:
                    vals['x_channel'] = channel
                    vals['x_country_code'] = country
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
            })
            updated += 1
    _logger.info('flamant_sales_report: auto-mapped %s sales teams', updated)


# ---------------------------------------------------------------------------
# Account tagging: backfill the Flamant Omzet / COGS / Discount tags on
# accounts that historically were classified by code pattern (70% / 604% /
# 708-709%). Once tagged, end users manage scope via Accounting ->
# Configuration -> Account Tags or the Account form's Tags field.
# ---------------------------------------------------------------------------

ACCOUNT_TAG_RULES = [
    # (tag_xmlid_suffix, list of code prefixes)
    ('tag_flamant_discount', ('708', '709')),
    ('tag_flamant_omzet',    ('70',)),   # caught AFTER discount so 708/709 stay tagged for both
    ('tag_flamant_cogs',     ('604',)),
]


def _flamant_tag_accounts(env):
    """Tag accounts matching the seed code prefixes with the Flamant
    Omzet / COGS / Discount tags. Idempotent: re-running adds nothing
    new."""
    by_tag = {}
    for suffix, prefixes in ACCOUNT_TAG_RULES:
        tag = env.ref(f'flamant_sales_report.{suffix}', raise_if_not_found=False)
        if not tag:
            _logger.warning('flamant_sales_report: tag %s not found, skipping', suffix)
            continue
        domain = ['|'] * (len(prefixes) - 1) + [
            ('code', '=like', f'{prefix}%') for prefix in prefixes
        ]
        accounts = env['account.account'].search(domain)
        if not accounts:
            continue
        to_link = accounts.filtered(lambda a, t=tag: t not in a.tag_ids)
        if to_link:
            to_link.write({'tag_ids': [(4, tag.id)]})
        by_tag[suffix] = (len(accounts), len(to_link))
    _logger.info(
        'flamant_sales_report: tag backfill -> %s',
        ', '.join(f'{k}={v[1]}/{v[0]}' for k, v in by_tag.items()),
    )
