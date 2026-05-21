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

    flamant_margin_locked = fields.Monetary(
        string='Locked Margin',
        currency_field='currency_id',
        readonly=True,
        copy=False,
        help='Cached margin (revenue - cost) for the Invoiced Sales Lines report. '
             'Refreshed daily for the current invoice month; finalized on the 1st '
             'of the next month. Captures purchasing-cost drift between invoice '
             'issue date and later SVL / standard_price changes.',
    )
