from odoo import fields, models


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    flamant_margin_locked_currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        readonly=True,
    )
    flamant_margin_locked = fields.Monetary(
        string='Locked Margin',
        currency_field='flamant_margin_locked_currency_id',
        readonly=True,
        copy=False,
        help='Cached margin (revenue - cost) computed by the Flamant locked-margin '
             'cron. Refreshed daily for the current month; finalized on the 1st of '
             'the next month and never written again. Captures drift between POS '
             'sale date and physical delivery for Flamant shops where furniture '
             'leaves the warehouse after payment.',
    )
