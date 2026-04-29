from odoo import fields, models


class CrmTeam(models.Model):
    """Extends crm.team with Flamant-specific reporting metadata.

    These fields drive the channel/country/shop dimensions in
    flamant.daily.sales and flamant.monthly.budget views.
    """

    _inherit = 'crm.team'

    x_channel = fields.Selection(
        [
            ('shops',        'Shops'),
            ('ecommerce',    'Online / E-Commerce'),
            ('wholesale',    'Wholesale'),
            ('franchise',    'Franchise'),
            ('flamant_home', 'Flamant@Home'),
            ('outlet',       'Outlet'),
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
        help='Most granular reporting unit (e.g. "Flamant Sablon", "Wholesale - Internal").',
    )
    x_analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Budget Analytic Account',
        help='Analytic account used to pull budget data from account.budget. '
             'One analytic account per sales team / shop cluster.',
    )

    def action_flamant_remap(self):
        """Re-run the auto-mapping of channel / country / shop / cluster."""
        from ..hooks import _flamant_remap
        _flamant_remap(self.env)
        return True
