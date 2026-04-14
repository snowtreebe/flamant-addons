from odoo import api, fields, models


class CrmTeam(models.Model):
    _inherit = 'crm.team'

    x_channel = fields.Selection(
        [
            ('shops',        'Shops'),
            ('ecommerce',    'Online / E-Commerce'),
            ('wholesale',    'Wholesale'),
            ('franchise',    'Franchise'),
            ('flamant_home', 'Flamant@Home'),
            ('other',        'Other'),
        ],
        string='Sales Channel',
        help='Top-level channel used in the consolidated sales report.',
    )
    x_country_code = fields.Selection(
        [
            ('BE',    'Belgium'),
            ('FR',    'France'),
            ('INT',   'International'),
            ('OTHER', 'Other'),
        ],
        string='Shop Country',
        help='Country dimension used in the consolidated sales report.',
    )
    x_shop_label = fields.Char(
        string='Shop Label',
        help='Human-readable shop name for the report. Falls back to the team name when empty.',
    )
    x_shop_cluster = fields.Char(
        string='Shop Cluster',
        help='Most granular reporting unit (e.g. "Flamant Sablon", "Wholesale - Internal", "E-Comm BE").',
    )
    x_comp_status = fields.Selection(
        [
            ('comparible',     'Comparible'),
            ('non_comparible', 'Non-Comparible'),
        ],
        string='Comparability',
        default='comparible',
        help='Used for Year-over-Year comparisons. New or temporary shops (pop-ups, new openings) are Non-Comparible.',
    )

    def action_flamant_remap(self):
        """Re-run the auto-mapping of channel / country / shop / cluster / comp."""
        from ..hooks import _flamant_remap
        _flamant_remap(self.env)
        return True
