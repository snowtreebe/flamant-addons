from odoo import api, fields, models


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

    def action_flamant_remap(self):
        """Re-run the auto-mapping of channel / country / shop for all teams.

        Teams with an explicit (non-'other') channel are preserved; teams on
        the 'other' fallback are re-evaluated against the latest rules in
        `hooks.TEAM_DEFAULTS`. Callable from the backend or via XMLRPC.
        """
        from ..hooks import _flamant_remap
        _flamant_remap(self.env)
        return True
