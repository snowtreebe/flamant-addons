from odoo import fields, models


class AccountMoveLine(models.Model):
    """Expose move_id.team_id as a stored, searchable field on the
    journal item itself so that account.report drilldowns (groupby=...)
    can use it. Required for the per-shop drilldown on the BU margin
    report.
    """

    _inherit = 'account.move.line'

    team_id = fields.Many2one(
        'crm.team',
        related='move_id.team_id',
        store=True,
        index=True,
        readonly=True,
    )
