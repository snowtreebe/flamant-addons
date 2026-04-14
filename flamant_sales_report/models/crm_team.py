from odoo import fields, models


class CrmTeam(models.Model):
    _inherit = 'crm.team'

    x_channel = fields.Selection(
        [
            ('wholesale', 'Wholesale'),
            ('shops', 'Shops'),
            ('ecommerce', 'E-Commerce'),
            ('other', 'Other'),
        ],
        string='Sales Channel',
        help='Top-level channel used in the consolidated sales report.',
    )
    x_country_code = fields.Selection(
        [
            ('BE', 'Belgium'),
            ('FR', 'France'),
            ('OTHER', 'Other'),
        ],
        string='Shop Country',
        help='Country dimension used in the consolidated sales report.',
    )
    x_shop_label = fields.Char(
        string='Shop Label',
        help='Human-readable shop name for the report. Falls back to the team name when empty.',
    )
